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
