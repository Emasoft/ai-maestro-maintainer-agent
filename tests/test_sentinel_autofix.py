"""Tests for the six mechanical auto-fixers, run_fix(), and the SHA resolver.

Ported from the Ruby test/test_auto_fix.rb, test/test_sha_resolver.rb, and
the local path of test/test_cli_fix.rb. No mocks of the unit under test:
every fixer test builds real workflow text, runs the real fixer, then
re-reads the result and asserts the rewrite is correct. Round-trip tests
additionally re-scan with the real Scanner and assert the rule no longer
fires. The only injected dependency is a deterministic SHA-resolver
callable for unpinned-actions — that is the external GitHub network dep,
not the fixer under test.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Make the bundled `sentinel` package importable (same shim sentinel_scan.py uses).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from sentinel.autofix import apply, can_fix, run_fix  # noqa: E402
from sentinel.finding import Finding  # noqa: E402
from sentinel.local_client import LocalClient  # noqa: E402
from sentinel.scanner import Scanner  # noqa: E402
from sentinel.sha_resolver import ShaResolver  # noqa: E402
from sentinel.formatters.terminal import Terminal  # noqa: E402

# A deterministic 40-hex SHA — matches the unpinned rule's SHA_PATTERN so a
# re-scan of a pinned action reports nothing.
FAKE_SHA = "b4ffde65f46336ab88eb53be808477a3936bae11"


def _fake_resolver(_owner_action: str, _tag: str) -> str:
    """Deterministic SHA-resolver callable injected in place of the gh CLI."""
    return FAKE_SHA


def _finding(rule: str, line: int, code: str = "", message: str = "") -> Finding:
    """Build a Finding for the fixer (severity is irrelevant to the fixers)."""
    return Finding(rule=rule, severity="medium", file="ci.yml", line=line, code=code, message=message, fix="")


def _write_workflow(root: Path, name: str, content: str) -> Path:
    """Create <root>/.github/workflows/<name> and return its path."""
    wf_dir = root / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    path = wf_dir / name
    path.write_text(content, encoding="utf-8")
    return path


def _rule_fires(root: Path, rule: str) -> bool:
    """True iff a fresh scan of root reports at least one finding for `rule`."""
    scanner = Scanner(client=LocalClient(str(root)), formatter=Terminal(), min_severity="low")
    result = scanner.scan(str(root))
    return any(f.rule == rule for f in result["findings"])


# --------------------------------------------------------------------------
# can_fix detection (port of the test_can_fix_* cases)
# --------------------------------------------------------------------------


def test_can_fix_all_six_fixable_rules() -> None:
    """can_fix returns True for each of the six mechanically fixable rules."""
    for rule in ("unpinned-actions", "shell-injection-expr", "missing-persist-credentials", "workflow-dispatch-injection", "missing-permissions", "missing-timeouts"):
        assert can_fix(_finding(rule, 1)) is True


def test_cannot_fix_non_mechanical_rule() -> None:
    """can_fix returns False for a rule with no mechanical fixer."""
    assert can_fix(_finding("dangerous-triggers", 1)) is False


def test_apply_returns_content_for_unknown_rule() -> None:
    """apply returns the input unchanged for a rule it cannot fix."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n"
    assert apply(_finding("unknown-rule", 1), yaml) == yaml


# --------------------------------------------------------------------------
# unpinned-actions
# --------------------------------------------------------------------------

_UNPINNED_YAML = """name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""


def test_fix_unpinned_action_produces_sha() -> None:
    """unpinned-actions rewrites @tag to @<sha> with the tag preserved in a comment."""
    finding = _finding("unpinned-actions", 7, code="uses: actions/checkout@v4")
    result = apply(finding, _UNPINNED_YAML, sha_resolver=_fake_resolver)
    assert FAKE_SHA in result
    assert "# v4" in result
    assert f"actions/checkout@{FAKE_SHA} # v4" in result


def test_fix_unpinned_action_subpath() -> None:
    """unpinned-actions pins a subpath action (actions/cache/restore@v4) to its SHA."""
    yaml = _UNPINNED_YAML.replace("actions/checkout@v4", "actions/cache/restore@v4")
    finding = _finding("unpinned-actions", 7, code="uses: actions/cache/restore@v4")
    result = apply(finding, yaml, sha_resolver=_fake_resolver)
    assert f"actions/cache/restore@{FAKE_SHA}" in result


def test_fix_unpinned_action_idempotent_once_pinned(tmp_path: Path) -> None:
    """Once pinned to a SHA, the unpinned rule no longer flags it, so no re-fix occurs."""
    # The realistic idempotence guarantee: applying the fixer turns @tag into a
    # SHA pin, and a fresh scan of that result reports zero unpinned-actions
    # findings — so run_fix never calls the fixer a second time. (Re-feeding the
    # already-pinned line as a synthetic finding is not a real scenario, because
    # the rule itself skips SHA-pinned uses via its 40-hex SHA_PATTERN.)
    finding = _finding("unpinned-actions", 7, code="uses: actions/checkout@v4")
    pinned = apply(finding, _UNPINNED_YAML, sha_resolver=_fake_resolver)
    assert pinned.count(FAKE_SHA) == 1
    _write_workflow(tmp_path, "ci.yml", pinned)
    assert not _rule_fires(tmp_path, "unpinned-actions")


def test_unpinned_action_roundtrip_rescan(tmp_path: Path) -> None:
    """After pinning, a re-scan no longer reports unpinned-actions for that file."""
    _write_workflow(tmp_path, "ci.yml", _UNPINNED_YAML)
    assert _rule_fires(tmp_path, "unpinned-actions")
    run_fix(root=str(tmp_path), dry_run=False, only_rules={"unpinned-actions"}, output_format="terminal", sha_resolver=_fake_resolver)
    assert not _rule_fires(tmp_path, "unpinned-actions")


# --------------------------------------------------------------------------
# shell-injection-expr
# --------------------------------------------------------------------------

_SHELL_YAML = """name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Greet
        run: |
          echo "${{ github.event.pull_request.title }}"
"""


def test_fix_shell_injection_moves_to_env() -> None:
    """shell-injection-expr adds an env: block, maps the context, and uses $VAR in run."""
    finding = _finding("shell-injection-expr", 9, code='echo "${{ github.event.pull_request.title }}"')
    result = apply(finding, _SHELL_YAML)
    assert "env:" in result
    assert "PR_TITLE:" in result
    assert "$PR_TITLE" in result
    # The expression survives inside the env mapping value.
    assert "${{ github.event.pull_request.title }}" in result


def test_fix_shell_injection_with_existing_env_block() -> None:
    """shell-injection-expr merges into an existing step env: block, keeping its entries."""
    yaml = """name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Greet
        env:
          FOO: bar
        run: |
          echo "${{ github.event.pull_request.title }}"
"""
    finding = _finding("shell-injection-expr", 11, code='echo "${{ github.event.pull_request.title }}"')
    result = apply(finding, yaml)
    assert "PR_TITLE:" in result
    assert "FOO: bar" in result
    assert "$PR_TITLE" in result
    # Exactly one step-level env: block (no duplicate).
    assert sum(1 for line in result.splitlines() if line.rstrip() == "        env:") == 1


def test_fix_shell_injection_single_quoted_uses_double_quotes() -> None:
    """A single-quoted ${{ }} expression is replaced with a double-quoted $VAR (bash expands it)."""
    yaml = _SHELL_YAML.replace('echo "${{ github.event.pull_request.title }}"', "echo '${{ github.event.pull_request.title }}'")
    finding = _finding("shell-injection-expr", 9, code="echo '${{ github.event.pull_request.title }}'")
    result = apply(finding, yaml)
    run_section = result.split("run: |", 1)[1]
    assert "'$PR_TITLE'" not in run_section
    assert '"$PR_TITLE"' in run_section


def test_shell_injection_expression_in_with_block_not_fixed() -> None:
    """An expression in a with: block (not a run: block) is left unchanged."""
    yaml = """name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Comment
        uses: some/action@v1
        with:
          body: "${{ github.event.pull_request.title }}"
      - name: Build
        run: echo "hello"
"""
    finding = _finding("shell-injection-expr", 10, code='body: "${{ github.event.pull_request.title }}"')
    assert apply(finding, yaml) == yaml


def test_fix_shell_injection_idempotent() -> None:
    """Re-applying shell-injection-expr after the first fix is a no-op (expr already moved)."""
    finding = _finding("shell-injection-expr", 9, code='echo "${{ github.event.pull_request.title }}"')
    once = apply(finding, _SHELL_YAML)
    # The run line is now `echo "$PR_TITLE"`; the same finding line no longer
    # holds a dangerous expression, so a second pass changes nothing further.
    twice = apply(_finding("shell-injection-expr", 9, code='echo "$PR_TITLE"'), once)
    assert twice == once


def test_shell_injection_roundtrip_rescan(tmp_path: Path) -> None:
    """After moving the expr to env, a re-scan no longer reports shell-injection-expr."""
    # pull_request is NOT a safe trigger, so the rule fires on the original.
    yaml = _SHELL_YAML.replace("on: push", "on: pull_request")
    _write_workflow(tmp_path, "ci.yml", yaml)
    assert _rule_fires(tmp_path, "shell-injection-expr")
    run_fix(root=str(tmp_path), dry_run=False, only_rules={"shell-injection-expr"}, output_format="terminal")
    assert not _rule_fires(tmp_path, "shell-injection-expr")


# --------------------------------------------------------------------------
# missing-persist-credentials
# --------------------------------------------------------------------------

_PERSIST_YAML = """name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""


def test_fix_persist_credentials_adds_flag() -> None:
    """missing-persist-credentials adds a with: block with persist-credentials: false."""
    finding = _finding("missing-persist-credentials", 7, code="uses: actions/checkout@v4")
    result = apply(finding, _PERSIST_YAML)
    assert "persist-credentials: false" in result


def test_fix_persist_credentials_existing_with_block() -> None:
    """missing-persist-credentials injects into an existing with: block, keeping its entries."""
    yaml = _PERSIST_YAML + "        with:\n          ref: main\n"
    finding = _finding("missing-persist-credentials", 7, code="uses: actions/checkout@v4")
    result = apply(finding, yaml)
    assert "persist-credentials: false" in result
    assert "ref: main" in result


def test_fix_persist_credentials_idempotent() -> None:
    """missing-persist-credentials does not add a second flag when one is present."""
    finding = _finding("missing-persist-credentials", 7, code="uses: actions/checkout@v4")
    once = apply(finding, _PERSIST_YAML)
    twice = apply(finding, once)
    assert twice.count("persist-credentials: false") == 1


def test_persist_credentials_roundtrip_rescan(tmp_path: Path) -> None:
    """After adding the flag, a re-scan no longer reports missing-persist-credentials."""
    # The rule only fires when the job pushes — add a git push step.
    yaml = """name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: git push origin main
"""
    _write_workflow(tmp_path, "ci.yml", yaml)
    assert _rule_fires(tmp_path, "missing-persist-credentials")
    run_fix(root=str(tmp_path), dry_run=False, only_rules={"missing-persist-credentials"}, output_format="terminal")
    assert not _rule_fires(tmp_path, "missing-persist-credentials")


# --------------------------------------------------------------------------
# workflow-dispatch-injection
# --------------------------------------------------------------------------

_DISPATCH_YAML = """name: Deploy
on:
  workflow_dispatch:
    inputs:
      version:
        description: Version to deploy
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy
        run: |
          echo "Deploying ${{ inputs.version }}"
"""


def test_fix_dispatch_injection_moves_to_env() -> None:
    """workflow-dispatch-injection maps inputs.version to INPUT_VERSION and uses $VAR in run."""
    finding = _finding("workflow-dispatch-injection", 13, code='echo "Deploying ${{ inputs.version }}"')
    result = apply(finding, _DISPATCH_YAML)
    assert "env:" in result
    assert "INPUT_VERSION:" in result
    assert "${{ inputs.version }}" in result
    assert "$INPUT_VERSION" in result
    # The run block no longer holds the raw expression.
    assert "${{ inputs.version }}" not in result.split("run: |", 1)[1]


def test_fix_dispatch_injection_github_event_inputs() -> None:
    """workflow-dispatch-injection handles the github.event.inputs.* form too."""
    yaml = """name: Deploy
on: workflow_dispatch
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy
        run: |
          echo "${{ github.event.inputs.target }}"
"""
    finding = _finding("workflow-dispatch-injection", 9, code='echo "${{ github.event.inputs.target }}"')
    result = apply(finding, yaml)
    assert "INPUT_TARGET:" in result
    assert "${{ github.event.inputs.target }}" in result
    assert "$INPUT_TARGET" in result


def test_fix_dispatch_injection_idempotent() -> None:
    """Re-applying workflow-dispatch-injection after the first fix is a no-op."""
    finding = _finding("workflow-dispatch-injection", 13, code='echo "Deploying ${{ inputs.version }}"')
    once = apply(finding, _DISPATCH_YAML)
    twice = apply(_finding("workflow-dispatch-injection", 13, code='echo "Deploying $INPUT_VERSION"'), once)
    assert twice == once


def test_dispatch_injection_roundtrip_rescan(tmp_path: Path) -> None:
    """After moving the dispatch input to env, a re-scan no longer reports the rule."""
    _write_workflow(tmp_path, "deploy.yml", _DISPATCH_YAML)
    assert _rule_fires(tmp_path, "workflow-dispatch-injection")
    run_fix(root=str(tmp_path), dry_run=False, only_rules={"workflow-dispatch-injection"}, output_format="terminal")
    assert not _rule_fires(tmp_path, "workflow-dispatch-injection")


# --------------------------------------------------------------------------
# missing-permissions
# --------------------------------------------------------------------------

_PERMS_YAML = """name: CI
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""


def test_fix_missing_permissions_adds_block_before_jobs() -> None:
    """missing-permissions inserts permissions: contents: read after on: and before jobs:."""
    finding = _finding("missing-permissions", 1)
    result = apply(finding, _PERMS_YAML)
    assert "permissions:" in result
    assert "  contents: read" in result
    assert result.index("permissions:") < result.index("jobs:")


def test_fix_missing_permissions_with_multiline_on() -> None:
    """missing-permissions inserts after a multi-line on: block, before jobs:."""
    yaml = """name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""
    result = apply(_finding("missing-permissions", 1), yaml)
    assert result.index("on:") < result.index("permissions:") < result.index("jobs:")


def test_fix_missing_permissions_idempotent() -> None:
    """missing-permissions does not add a second block when one already exists."""
    yaml = """name: CI
on: push
permissions:
  contents: write
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""
    result = apply(_finding("missing-permissions", 1), yaml)
    assert sum(1 for line in result.splitlines() if line.startswith("permissions:")) == 1


def test_missing_permissions_roundtrip_rescan(tmp_path: Path) -> None:
    """After adding the permissions block, a re-scan no longer reports missing-permissions."""
    _write_workflow(tmp_path, "ci.yml", _PERMS_YAML)
    assert _rule_fires(tmp_path, "missing-permissions")
    run_fix(root=str(tmp_path), dry_run=False, only_rules={"missing-permissions"}, output_format="terminal")
    assert not _rule_fires(tmp_path, "missing-permissions")


# --------------------------------------------------------------------------
# missing-timeouts
# --------------------------------------------------------------------------

_TIMEOUT_YAML = """name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""


def test_fix_missing_timeouts_adds_timeout_at_runs_on_indent() -> None:
    """missing-timeouts inserts timeout-minutes: 30 at the same indent as runs-on:."""
    finding = _finding("missing-timeouts", 5, code="runs-on: ubuntu-latest", message="Job 'build' has no timeout-minutes")
    result = apply(finding, _TIMEOUT_YAML)
    assert "timeout-minutes: 30" in result
    lines = result.splitlines(keepends=True)
    runs_on = next(line for line in lines if "runs-on:" in line)
    timeout = next(line for line in lines if "timeout-minutes:" in line)
    assert runs_on[: len(runs_on) - len(runs_on.lstrip())] == timeout[: len(timeout) - len(timeout.lstrip())]


def test_fix_missing_timeouts_finds_runs_on_from_job_line() -> None:
    """missing-timeouts locates runs-on: by searching forward from the job-name line."""
    # The real rule reports the job-name line (code "build:"), not runs-on.
    finding = _finding("missing-timeouts", 4, code="build:", message="Job 'build' has no timeout-minutes")
    result = apply(finding, _TIMEOUT_YAML)
    assert "timeout-minutes: 30" in result


def test_fix_missing_timeouts_idempotent() -> None:
    """missing-timeouts does not add a second timeout when one already exists."""
    yaml = """name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
"""
    finding = _finding("missing-timeouts", 5, code="runs-on: ubuntu-latest", message="Job 'build' has no timeout-minutes")
    result = apply(finding, yaml)
    assert result.count("timeout-minutes:") == 1


def test_missing_timeouts_roundtrip_rescan(tmp_path: Path) -> None:
    """After adding timeout-minutes, a re-scan no longer reports missing-timeouts."""
    _write_workflow(tmp_path, "ci.yml", _TIMEOUT_YAML)
    assert _rule_fires(tmp_path, "missing-timeouts")
    run_fix(root=str(tmp_path), dry_run=False, only_rules={"missing-timeouts"}, output_format="terminal")
    assert not _rule_fires(tmp_path, "missing-timeouts")


# --------------------------------------------------------------------------
# run_fix flow: dry-run, only_rules filter, write
# --------------------------------------------------------------------------


def test_run_fix_dry_run_leaves_files_unchanged(tmp_path: Path) -> None:
    """run_fix with dry_run=True reports fixes but never writes the files."""
    path = _write_workflow(tmp_path, "ci.yml", _PERMS_YAML)
    before = path.read_text(encoding="utf-8")
    rc = run_fix(root=str(tmp_path), dry_run=True, only_rules=set(), output_format="terminal")
    assert rc == 0
    assert path.read_text(encoding="utf-8") == before


def test_run_fix_writes_files_without_dry_run(tmp_path: Path) -> None:
    """run_fix without dry_run applies network-free fixers (permissions + timeout) to disk."""
    # No persist/unpinned network deps needed: permissions + timeout cover the write path.
    yaml = """name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4
"""
    path = _write_workflow(tmp_path, "ci.yml", yaml)
    run_fix(root=str(tmp_path), dry_run=False, only_rules=set(), output_format="terminal")
    content = path.read_text(encoding="utf-8")
    assert "permissions:" in content
    assert "timeout-minutes: 30" in content


def test_run_fix_only_rules_filter(tmp_path: Path) -> None:
    """run_fix with only_rules applies just the named rule and skips the others."""
    yaml = """name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11 # v4
"""
    path = _write_workflow(tmp_path, "ci.yml", yaml)
    run_fix(root=str(tmp_path), dry_run=False, only_rules={"missing-permissions"}, output_format="terminal")
    content = path.read_text(encoding="utf-8")
    assert "permissions:" in content
    # missing-timeouts was NOT in the filter, so it must not have been applied.
    assert "timeout-minutes:" not in content


def test_run_fix_json_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """run_fix with output_format=json emits a JSON summary listing the fixed file."""
    _write_workflow(tmp_path, "ci.yml", _PERMS_YAML)
    run_fix(root=str(tmp_path), dry_run=True, only_rules={"missing-permissions"}, output_format="json")
    out = capsys.readouterr().out
    assert '"dry_run": true' in out
    assert "missing-permissions" in out


# --------------------------------------------------------------------------
# ShaResolver — pure unit behavior (no network)
# --------------------------------------------------------------------------


def test_sha_resolver_extract_repo_normal() -> None:
    """ShaResolver._extract_repo returns owner/repo for a normal action ref."""
    assert ShaResolver._extract_repo("pnpm/action-setup") == "pnpm/action-setup"


def test_sha_resolver_extract_repo_subpath() -> None:
    """ShaResolver._extract_repo strips the subpath of a nested action ref."""
    assert ShaResolver._extract_repo("actions/cache/restore") == "actions/cache"


def test_sha_resolver_extract_repo_deep_subpath() -> None:
    """ShaResolver._extract_repo keeps only the first two path segments."""
    assert ShaResolver._extract_repo("org/repo/sub/deep/path") == "org/repo"


def test_sha_resolver_caches_per_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """ShaResolver.resolve calls the backend once per owner/repo@tag, then caches."""
    resolver = ShaResolver()
    calls: list[tuple[str, str]] = []

    def fake_fetch(repo: str, tag: str) -> str:
        calls.append((repo, tag))
        return FAKE_SHA

    # Replace the network call (the external dep), not resolve() itself.
    monkeypatch.setattr(resolver, "_fetch_sha", fake_fetch)
    assert resolver.resolve("actions/checkout", "v4") == FAKE_SHA
    assert resolver.resolve("actions/checkout", "v4") == FAKE_SHA
    assert calls == [("actions/checkout", "v4")]


def test_sha_resolver_different_tags_are_separate_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    """ShaResolver caches v3 and v4 separately (one backend call each)."""
    resolver = ShaResolver()
    calls: list[tuple[str, str]] = []

    def fake_fetch(repo: str, tag: str) -> str:
        calls.append((repo, tag))
        return f"sha_for_{tag}"

    monkeypatch.setattr(resolver, "_fetch_sha", fake_fetch)
    assert resolver.resolve("actions/checkout", "v3") == "sha_for_v3"
    assert resolver.resolve("actions/checkout", "v4") == "sha_for_v4"
    assert len(calls) == 2


def test_sha_resolver_returns_none_when_gh_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """ShaResolver.resolve returns None (fail-safe) when the gh CLI is absent."""
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert ShaResolver().resolve("actions/checkout", "v4") is None


# --------------------------------------------------------------------------
# ShaResolver — real gh integration (slow, network)
# --------------------------------------------------------------------------


def _gh_ready() -> bool:
    """True iff gh is installed and authenticated (else the slow test is skipped)."""
    if shutil.which("gh") is None:
        return False
    try:
        return subprocess.run(["gh", "auth", "status"], capture_output=True, timeout=15).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


@pytest.mark.skipif(not _gh_ready(), reason="gh CLI unavailable or unauthenticated")
def test_sha_resolver_resolves_real_tag_via_gh_slow() -> None:
    """🐌 ShaResolver resolves a real public action@tag to a 40-hex SHA via gh."""
    sha = ShaResolver().resolve("actions/checkout", "v4.2.2")
    assert sha is not None
    assert len(sha) == 40
    assert all(c in "0123456789abcdef" for c in sha)
