"""Core-engine tests for the Sentinel Python port (no rule-specific logic).

Exercises the foundation the rule swarm builds on: the registry/engine,
the YAML-aware Workflow (including the on->True quirk), the Scanner's two
synthetic findings + severity filter, the .sentinel-ci.yml policy engine,
and the three formatters. No mocks — real Workflow/Scanner/Policy objects
built from inline YAML and pytest tmp_path checkouts.
"""

from __future__ import annotations

import json
from pathlib import Path

import sentinel_scan
from sentinel.finding import Finding
from sentinel.formatters.json import Json
from sentinel.formatters.sarif import Sarif
from sentinel.formatters.terminal import Terminal
from sentinel.local_client import LocalClient
from sentinel.policy import Policy
from sentinel.rule_engine import RuleEngine
from sentinel.scanner import Scanner
from sentinel.workflow import Workflow

# 30 rule modules + 2 synthetic checks (missing-dependabot/zizmor) = 32 total.
EXPECTED_RULE_COUNT = 30

_CLEAN_WF = """\
name: CI
on:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4
        with:
          persist-credentials: false
      - run: echo hi
"""


def _make_checkout(tmp_path: Path, *, workflow: str = _CLEAN_WF, name: str = "ci.yml", dependabot: str | None = None, zizmor: bool = False) -> Path:
    """Build a tmp repo checkout with one workflow (+ optional dependabot/zizmor)."""
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True)
    (wf_dir / name).write_text(workflow)
    if zizmor:
        (wf_dir / "zizmor.yml").write_text("name: zizmor\non:\n  push:\njobs:\n  z:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo z\n")
    if dependabot is not None:
        (tmp_path / ".github" / "dependabot.yml").write_text(dependabot)
    return tmp_path


def _scan(root: Path, *, min_severity: str = "low", policy: Policy | None = None) -> list[Finding]:
    """Run a full Scanner pass over a checkout and return findings."""
    scanner = Scanner(client=LocalClient(str(root)), formatter=Json(), min_severity=min_severity, policy=policy or Policy())
    return scanner.scan(str(root))["findings"]


def test_engine_registers_all_rules():
    """RuleEngine auto-discovers exactly the 30 ported rule modules."""
    engine = RuleEngine()
    assert len(engine.rules) == EXPECTED_RULE_COUNT


def test_engine_rules_are_severity_sorted():
    """Engine orders rules by severity rank (critical first, low last)."""
    from sentinel.finding import SEVERITY_ORDER

    ranks = [SEVERITY_ORDER[r.severity] for r in RuleEngine().rules]
    assert ranks == sorted(ranks)


def test_rule_names_are_unique():
    """No two ported rules share a name (registry has no duplicates)."""
    names = [r.name for r in RuleEngine().rules]
    assert len(names) == len(set(names))


def test_workflow_on_true_quirk_hash():
    """`on:` parsed as the YAML boolean True key is still resolved by triggers()."""
    wf = Workflow(filename="x.yml", content="on:\n  push:\n  pull_request:\njobs: {}\n")
    assert set(wf.triggers().keys()) == {"push", "pull_request"}


def test_workflow_on_string_form():
    """A scalar `on: push` resolves to the string 'push'."""
    wf = Workflow(filename="x.yml", content="on: push\njobs: {}\n")
    assert wf.triggers() == "push"


def test_workflow_parse_error_is_safe():
    """Malformed YAML sets parse_error() and yields empty data, never raises."""
    wf = Workflow(filename="bad.yml", content="on: [unterminated\n")
    assert wf.parse_error() is True
    assert wf.data == {}


def test_workflow_line_helpers():
    """line_of/lines_of/line_content map patterns to 1-based line numbers."""
    wf = Workflow(filename="x.yml", content="a: 1\nrun: echo\nrun: echo2\n")
    assert wf.line_of(r"^run:") == 2
    assert wf.lines_of(r"^run:") == [2, 3]
    assert wf.line_content(2) == "run: echo"
    assert wf.line_content(999) is None


def test_scanner_emits_both_synthetic_findings(tmp_path: Path):
    """A clean checkout with no dependabot/zizmor flags both synthetic lows."""
    rules = {f.rule for f in _scan(_make_checkout(tmp_path))}
    assert "missing-dependabot" in rules
    assert "missing-zizmor" in rules


def test_scanner_dependabot_actions_suppresses_synthetic(tmp_path: Path):
    """A github-actions dependabot ecosystem suppresses missing-dependabot."""
    depa = 'version: 2\nupdates:\n  - package-ecosystem: "github-actions"\n    directory: "/"\n    schedule:\n      interval: "weekly"\n'
    rules = {f.rule for f in _scan(_make_checkout(tmp_path, dependabot=depa))}
    assert "missing-dependabot" not in rules


def test_scanner_zizmor_workflow_suppresses_synthetic(tmp_path: Path):
    """A workflow whose name contains 'zizmor' suppresses missing-zizmor."""
    rules = {f.rule for f in _scan(_make_checkout(tmp_path, zizmor=True))}
    assert "missing-zizmor" not in rules


def test_severity_filter_drops_low(tmp_path: Path):
    """min_severity=critical removes the low synthetic findings."""
    findings = _scan(_make_checkout(tmp_path), min_severity="critical")
    assert all(f.is_critical() for f in findings)


def test_policy_rule_off_removes_findings(tmp_path: Path):
    """A `rules: { missing-zizmor: off }` policy drops that rule's findings."""
    root = _make_checkout(tmp_path)
    (root / ".sentinel-ci.yml").write_text("rules:\n  missing-zizmor: off\n")
    policy = Policy(str(root / ".sentinel-ci.yml"))
    assert not policy.errors
    rules = {f.rule for f in _scan(root, policy=policy)}
    assert "missing-zizmor" not in rules
    assert "missing-dependabot" in rules


def test_policy_severity_override(tmp_path: Path):
    """A per-rule override raises missing-zizmor from low to critical."""
    root = _make_checkout(tmp_path)
    (root / ".sentinel-ci.yml").write_text("rules:\n  missing-zizmor: critical\n")
    policy = Policy(str(root / ".sentinel-ci.yml"))
    findings = _scan(root, policy=policy)
    zizmor = next(f for f in findings if f.rule == "missing-zizmor")
    assert zizmor.severity == "critical"


def test_policy_ignore_glob(tmp_path: Path):
    """An ignore glob matching the file removes its findings."""
    root = _make_checkout(tmp_path)
    (root / ".sentinel-ci.yml").write_text("ignore:\n  - 'dependabot.yml'\n")
    policy = Policy(str(root / ".sentinel-ci.yml"))
    rules = {f.rule for f in _scan(root, policy=policy)}
    assert "missing-dependabot" not in rules


def test_policy_exception_requires_reason(tmp_path: Path):
    """An exception entry without a reason is a policy error (no silent suppress)."""
    cfg = tmp_path / ".sentinel-ci.yml"
    cfg.write_text("exceptions:\n  - rule: missing-zizmor\n")
    policy = Policy(str(cfg))
    assert any("reason" in e for e in policy.errors)


def test_policy_unknown_rule_is_error(tmp_path: Path):
    """An unknown rule name in the policy is reported as an error."""
    cfg = tmp_path / ".sentinel-ci.yml"
    cfg.write_text("rules:\n  not-a-real-rule: high\n")
    policy = Policy(str(cfg))
    assert any("Unknown rule" in e for e in policy.errors)


def test_json_formatter_shape():
    """Json formatter emits {repo, workflows, findings[], summary{}}."""
    f = Finding(rule="r", severity="high", file="x.yml", line=3, message="m", fix="do x")
    out = json.loads(Json().format(repo="o/r", workflow_count=1, findings=[f]))
    assert out["repo"] == "o/r"
    assert out["summary"]["high"] == 1
    assert out["findings"][0]["rule"] == "r"


def test_sarif_formatter_shape():
    """Sarif formatter emits SARIF 2.1.0 with one run and a result per finding."""
    f = Finding(rule="r", severity="critical", file="x.yml", line=3, message="m")
    out = json.loads(Sarif().format(repo="o/r", workflow_count=1, findings=[f]))
    assert out["version"] == "2.1.0"
    assert out["runs"][0]["results"][0]["ruleId"] == "r"
    assert out["runs"][0]["results"][0]["level"] == "error"


def test_terminal_formatter_no_findings():
    """Terminal formatter prints 'No findings.' on an empty result."""
    out = Terminal().format(repo="o/r", workflow_count=0, findings=[])
    assert "No findings." in out


def test_finding_sort_orders_critical_first():
    """Findings sort by severity rank: critical before high before low."""
    fs = [Finding("a", "low", "f", 1), Finding("b", "critical", "f", 1), Finding("c", "high", "f", 1)]
    assert [f.severity for f in sorted(fs)] == ["critical", "high", "low"]


def test_cli_main_clean_checkout_returns_zero(tmp_path: Path):
    """sentinel_scan.main returns 0 when no critical/high findings are present."""
    root = _make_checkout(tmp_path, dependabot='version: 2\nupdates:\n  - package-ecosystem: "github-actions"\n    directory: "/"\n    schedule:\n      interval: "weekly"\n', zizmor=True)
    rc = sentinel_scan.main(["scan", "--format", "json", str(root)])
    assert rc == 0


def test_cli_main_vulnerable_checkout_returns_one(tmp_path: Path):
    """sentinel_scan.main returns 1 when critical/high findings are present."""
    vuln = 'name: evil\non:\n  pull_request_target:\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo "${{ github.event.pull_request.title }}"\n'
    root = _make_checkout(tmp_path, workflow=vuln, name="evil.yml")
    rc = sentinel_scan.main(["scan", "--format", "json", str(root)])
    assert rc == 1


def test_cli_main_remote_slug_rejected(tmp_path: Path, capsys):
    """A remote owner/repo positional is rejected with a usage error (exit 2)."""
    import pytest

    with pytest.raises(SystemExit) as exc:
        sentinel_scan.main(["scan", "owner/repo"])
    assert exc.value.code == 2


# --- run-block detection (false-positive regression, calibration 2026-05-25) ---

# Unsafe trigger (pull_request_target) so shell-injection-expr does not
# short-circuit on safe_trigger_only and actually reaches the run-content test.
_WF_OUTPUTS_FP = """\
on:
  workflow_dispatch:
    inputs:
      tag:
        type: string
  pull_request_target:
jobs:
  plan:
    runs-on: ubuntu-latest
    outputs:
      tag: ${{ inputs.tag }}
      tag-flag: ${{ inputs.tag && inputs.tag != 'dry-run' && format('--tag={0}', inputs.tag) || '' }}
      title: ${{ github.event.pull_request.title }}
    steps:
      - run: echo done
"""

_WF_RUN_TP = """\
on:
  workflow_dispatch:
    inputs:
      tag:
        type: string
  pull_request_target:
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo "${{ inputs.tag }}"
      - run: |
          echo "building"
          echo "${{ github.event.pull_request.title }}"
"""


def test_run_content_lines_inline_and_block():
    """run_content_lines() includes inline run: lines and block-scalar content."""
    wf = Workflow("ci.yml", _WF_RUN_TP)
    lines = wf.run_content_lines()
    # `- run: echo "${{ inputs.tag }}"` is line 10 (inline).
    assert wf.line_of(r'run: echo "\$\{\{ inputs') in lines
    # The block-scalar body lines are included.
    assert wf.line_of(r"echo \"building\"") in lines
    assert wf.line_of(r"github\.event\.pull_request\.title") in lines


def test_run_content_lines_excludes_outputs_block():
    """Expressions in a job outputs: block are NOT counted as run content."""
    wf = Workflow("ci.yml", _WF_OUTPUTS_FP)
    lines = wf.run_content_lines()
    assert wf.line_of(r"tag-flag:") not in lines
    assert wf.line_of(r"title: \$\{\{ github") not in lines


def test_dispatch_injection_no_fp_in_outputs():
    """workflow-dispatch-injection does NOT flag ${{ inputs.* }} in outputs:."""
    from sentinel.rules.workflow_dispatch_injection import WorkflowDispatchInjection

    assert WorkflowDispatchInjection().check(Workflow("ci.yml", _WF_OUTPUTS_FP)) == []


def test_dispatch_injection_flags_run_block():
    """workflow-dispatch-injection DOES flag ${{ inputs.* }} inside run:."""
    from sentinel.rules.workflow_dispatch_injection import WorkflowDispatchInjection

    findings = WorkflowDispatchInjection().check(Workflow("ci.yml", _WF_RUN_TP))
    assert len(findings) == 1
    assert findings[0].rule == "workflow-dispatch-injection"


def test_shell_injection_expr_no_fp_in_outputs():
    """shell-injection-expr does NOT flag github.event.* in outputs:."""
    from sentinel.rules.shell_injection_expr import ShellInjectionExpr

    assert ShellInjectionExpr().check(Workflow("ci.yml", _WF_OUTPUTS_FP)) == []


def test_shell_injection_expr_flags_run_block():
    """shell-injection-expr DOES flag github.event.* inside a run: block."""
    from sentinel.rules.shell_injection_expr import ShellInjectionExpr

    findings = ShellInjectionExpr().check(Workflow("ci.yml", _WF_RUN_TP))
    assert len(findings) == 1
    assert findings[0].rule == "shell-injection-expr"


# --- job-line resolver + per-rule false-positive regressions (calibration 2026-05-25) ---

_WF_JOB_NAME_COLLISION = """\
on: push
jobs:
  plan:
    runs-on: ubuntu-latest
    outputs:
      build: ${{ steps.x.outputs.build }}
    steps:
      - run: echo plan
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo build
"""


def test_job_line_targets_job_def_not_outputs_entry():
    """job_line() returns the job definition, not a same-named outputs: entry."""
    wf = Workflow("ci.yml", _WF_JOB_NAME_COLLISION)
    # `build:` appears first as an outputs entry (line 6, 6-space indent), then
    # as the job key (line 9, 2-space indent) — job_line must return the latter.
    assert wf.job_line("build") == 9
    assert wf.job_line("plan") == 3
    assert wf.job_line("does-not-exist") is None


def test_excessive_permissions_git_dash_c_push_counts_as_write():
    """`git -C <dir> push` (git global option) is recognised as a write op."""
    from sentinel.rules.excessive_permissions import ExcessivePermissions

    yaml = "on: push\njobs:\n  sync:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: write\n    steps:\n      - run: git -C ruff push --force --set-upstream origin x\n"
    assert ExcessivePermissions().check(Workflow("ci.yml", yaml)) == []


def test_excessive_permissions_gh_release_upload_counts_as_write():
    """`gh release upload` (not just create) is a write op."""
    from sentinel.rules.excessive_permissions import ExcessivePermissions

    yaml = "on: push\njobs:\n  rel:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: write\n    steps:\n      - run: gh release upload v1 dist/*\n"
    assert ExcessivePermissions().check(Workflow("ci.yml", yaml)) == []


def test_excessive_permissions_persist_credentials_true_is_write_intent():
    """Explicit persist-credentials: true signals a push (often via a script)."""
    from sentinel.rules.excessive_permissions import ExcessivePermissions

    yaml = "on: push\njobs:\n  pub:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: write\n    steps:\n      - uses: actions/checkout@v4\n        with:\n          persist-credentials: true\n      - run: uv run ./scripts/push.py\n"
    assert ExcessivePermissions().check(Workflow("ci.yml", yaml)) == []


def test_excessive_permissions_skips_reusable_workflow_call():
    """A reusable-call job has no visible steps — cannot conclude excess."""
    from sentinel.rules.excessive_permissions import ExcessivePermissions

    yaml = "on: push\njobs:\n  call:\n    permissions:\n      contents: write\n    uses: ./.github/workflows/x.yml\n"
    assert ExcessivePermissions().check(Workflow("ci.yml", yaml)) == []


def test_excessive_permissions_flags_genuinely_unused_write():
    """A contents: write job with no write op at all is still flagged."""
    from sentinel.rules.excessive_permissions import ExcessivePermissions

    yaml = "on: push\njobs:\n  idle:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: write\n    steps:\n      - run: echo nothing\n"
    findings = ExcessivePermissions().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1
    assert findings[0].rule == "excessive-permissions"


def test_missing_timeouts_skips_reusable_workflow_call():
    """A reusable-call job cannot legally carry timeout-minutes — not flagged."""
    from sentinel.rules.missing_timeouts import MissingTimeouts

    yaml = "on: push\njobs:\n  call:\n    uses: ./.github/workflows/x.yml\n"
    assert MissingTimeouts().check(Workflow("ci.yml", yaml)) == []


def test_missing_timeouts_flags_steps_job_without_timeout():
    """A normal steps job with no timeout-minutes is still flagged."""
    from sentinel.rules.missing_timeouts import MissingTimeouts

    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n"
    assert len(MissingTimeouts().check(Workflow("ci.yml", yaml))) == 1


def test_missing_permissions_skips_when_all_jobs_scoped():
    """No top-level block but every job scopes its own permissions — not flagged."""
    from sentinel.rules.missing_permissions import MissingPermissions

    yaml = "on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    permissions:\n      id-token: write\n    steps:\n      - run: echo a\n"
    assert MissingPermissions().check(Workflow("ci.yml", yaml)) == []


def test_missing_permissions_flags_when_a_job_is_unscoped():
    """If any job lacks its own permissions, it inherits the broad default — flag."""
    from sentinel.rules.missing_permissions import MissingPermissions

    yaml = "on: push\njobs:\n  a:\n    runs-on: ubuntu-latest\n    permissions:\n      id-token: write\n    steps:\n      - run: echo a\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo b\n"
    assert len(MissingPermissions().check(Workflow("ci.yml", yaml))) == 1


def test_unpinned_artifact_artifact_ids_is_a_selector():
    """download-artifact with artifact-ids: narrows the download — not flagged."""
    from sentinel.rules.unpinned_artifact import UnpinnedArtifact

    yaml = "on: push\njobs:\n  pub:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/download-artifact@v4\n        with:\n          artifact-ids: ${{ needs.build.outputs.id }}\n          path: dist/\n"
    assert UnpinnedArtifact().check(Workflow("ci.yml", yaml)) == []


def test_unpinned_artifact_flags_when_no_selector():
    """download-artifact with only a path (no name/pattern/artifact-ids) flags."""
    from sentinel.rules.unpinned_artifact import UnpinnedArtifact

    yaml = "on: push\njobs:\n  pub:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/download-artifact@v4\n        with:\n          path: dist/\n"
    assert len(UnpinnedArtifact().check(Workflow("ci.yml", yaml))) == 1


def test_frozen_lockfile_skips_pip_toolchain_bootstrap():
    """`pip install -U pip setuptools wheel` is toolchain bootstrap, not deps."""
    from sentinel.rules.missing_frozen_lockfile import MissingFrozenLockfile

    yaml = "on: push\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: pip install -U pip setuptools wheel\n"
    assert MissingFrozenLockfile().check(Workflow("ci.yml", yaml)) == []


def test_frozen_lockfile_skips_pinned_toolchain_tool():
    """A pinned toolchain tool (`pip install build==1.4.0`) is still bootstrap."""
    from sentinel.rules.missing_frozen_lockfile import MissingFrozenLockfile

    yaml = "on: push\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: python -m pip install build==1.4.0\n"
    assert MissingFrozenLockfile().check(Workflow("ci.yml", yaml)) == []


def test_frozen_lockfile_skips_npm_global_install():
    """`npm install -g <tool>` is a CLI tool install — npm ci does not apply."""
    from sentinel.rules.missing_frozen_lockfile import MissingFrozenLockfile

    yaml = "on: push\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: npm install -g npm@11.12.0\n"
    assert MissingFrozenLockfile().check(Workflow("ci.yml", yaml)) == []


def test_frozen_lockfile_flags_unpinned_dependency_install():
    """An unpinned project-dependency install (`uv pip install anyio`) flags."""
    from sentinel.rules.missing_frozen_lockfile import MissingFrozenLockfile

    yaml = "on: push\njobs:\n  b:\n    runs-on: ubuntu-latest\n    steps:\n      - run: uv pip install anyio\n"
    assert len(MissingFrozenLockfile().check(Workflow("ci.yml", yaml))) == 1


def test_missing_persist_creds_explicit_true_exempts_script_push():
    """Explicit persist-credentials: true exempts even a script-based push."""
    from sentinel.rules.missing_persist_creds import MissingPersistCreds

    yaml = "on: push\njobs:\n  pub:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n        with:\n          persist-credentials: true\n      - run: uv run ./scripts/push.py\n"
    assert MissingPersistCreds().check(Workflow("ci.yml", yaml)) == []


def test_scanner_zizmor_precommit_suppresses_synthetic(tmp_path: Path):
    """zizmor run via .pre-commit-config.yaml suppresses missing-zizmor."""
    root = _make_checkout(tmp_path)
    (tmp_path / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: https://github.com/zizmorcore/zizmor-pre-commit\n    rev: v1.0.0\n    hooks:\n      - id: zizmor\n"
    )
    assert not any(f.rule == "missing-zizmor" for f in _scan(root))


def test_scanner_zizmor_workflow_content_suppresses_synthetic(tmp_path: Path):
    """zizmor invoked in a workflow run step (uvx zizmor) suppresses missing-zizmor."""
    wf = "name: sec\non:\n  push:\njobs:\n  audit:\n    runs-on: ubuntu-latest\n    steps:\n      - run: uvx zizmor .\n"
    root = _make_checkout(tmp_path, workflow=wf, name="audit.yml")
    assert not any(f.rule == "missing-zizmor" for f in _scan(root))


def test_scanner_zizmor_ignore_comment_does_not_suppress(tmp_path: Path):
    """A bare `# zizmor: ignore` comment is not a zizmor invocation."""
    wf = "name: CI\non:\n  push:\n    branches: [main]\npermissions:\n  contents: read\njobs:\n  build:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n    steps:\n      - run: echo hi # zizmor: ignore[template-injection]\n"
    root = _make_checkout(tmp_path, workflow=wf)
    assert any(f.rule == "missing-zizmor" for f in _scan(root))
