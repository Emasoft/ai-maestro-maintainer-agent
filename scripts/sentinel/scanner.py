"""Scan orchestrator.

Port of lib/scanner.rb (local-scanning path). Runs every rule against
each workflow, adds the two synthetic repo-level findings
(missing-dependabot, missing-zizmor), applies the severity filter, then
applies policy overrides (ignore globs, exceptions, per-rule severity).
"""

from __future__ import annotations

import re
from typing import Any, Protocol

from sentinel.finding import SEVERITY_ORDER, Finding
from sentinel.policy import Policy
from sentinel.rule_engine import RuleEngine
from sentinel.workflow import Workflow


class _Client(Protocol):
    """Minimal client surface the scanner needs (LocalClient implements it)."""

    def fetch_workflows(self, repo: Any = None) -> list[dict[str, str]]: ...
    def fetch_dependabot_config(self, repo: Any = None) -> dict[str, Any] | None: ...
    def fetch_precommit_config(self, repo: Any = None) -> str | None: ...


# Real zizmor invocation (NOT a bare `# zizmor: ignore` suppression comment,
# which would falsely imply analysis). Covers the action / pre-commit repo refs
# (`zizmorcore/zizmor`, `zizmorcore/zizmor-action`, `zizmorcore/zizmor-pre-commit`),
# CLI invocations (`uvx zizmor`, `uv run zizmor`, `pipx run zizmor`,
# `pip install … zizmor`), and pre-commit hook declarations (`id: zizmor`,
# `entry: … zizmor`). astral-sh/ruff and tiangolo/fastapi run zizmor via
# pre-commit (no zizmor-named workflow file), so a filename-only probe flagged
# them as missing-zizmor — a false positive this widens detection to remove.
_ZIZMOR_INVOKE = re.compile(
    r"zizmorcore/zizmor"
    r"|uvx\s+zizmor"
    r"|uv\s+run\s+zizmor"
    r"|pipx\s+run\s+zizmor"
    r"|pip\s+install\s+[^\n]*\bzizmor\b"
    r"|^\s*-?\s*id:\s*zizmor\b"
    r"|entry:[^\n]*\bzizmor\b",
    re.IGNORECASE | re.MULTILINE,
)


class _Formatter(Protocol):
    def format(self, *, repo: str, workflow_count: int, findings: list[Finding]) -> str: ...


class Scanner:
    """Wires a client + formatter + policy to the rule engine."""

    def __init__(
        self,
        client: _Client,
        formatter: _Formatter,
        min_severity: str = "low",
        policy: Policy | None = None,
    ) -> None:
        self.client = client
        self.formatter = formatter
        self.min_severity = min_severity
        self.policy = policy or Policy()
        self.engine = RuleEngine()

    def scan(self, repo: str) -> dict[str, Any]:
        """Scan one repo/path; return {output, findings, workflow_count, workflows}."""
        findings: list[Finding] = []

        raw_workflows = self.client.fetch_workflows(repo)
        workflows = [Workflow(filename=w["filename"], content=w["content"]) for w in raw_workflows]
        workflow_count = len(workflows)

        dependabot = self.client.fetch_dependabot_config(repo)
        precommit = self.client.fetch_precommit_config(repo)
        has_zizmor = (
            any(re.search(r"zizmor", w.filename, re.IGNORECASE) for w in workflows)
            or any(_ZIZMOR_INVOKE.search(w.raw) for w in workflows)
            or (precommit is not None and bool(_ZIZMOR_INVOKE.search(precommit)))
        )
        has_dependabot_actions = self._dependabot_has_actions(dependabot)

        for wf in workflows:
            if wf.parse_error():
                continue
            findings.extend(self.engine.scan(wf))

        if not has_dependabot_actions:
            findings.append(
                Finding(
                    rule="missing-dependabot",
                    severity="low",
                    file="dependabot.yml",
                    line=0,
                    code=None,
                    message="No Dependabot configuration for github-actions ecosystem",
                    fix="Add package-ecosystem: github-actions to .github/dependabot.yml",
                )
            )

        if not has_zizmor:
            findings.append(
                Finding(
                    rule="missing-zizmor",
                    severity="low",
                    file="(missing)",
                    line=0,
                    code=None,
                    message="No zizmor static analysis workflow found",
                    fix="Add a security_zizmor.yml workflow for GitHub Actions static analysis",
                )
            )

        findings = [f for f in findings if self._severity_passes(f.severity)]

        if self.policy.loaded():
            findings = [f for f in findings if not self.policy.ignored(f.file)]
            findings = [f for f in findings if not self.policy.excepted(f)]

            overridden: list[Finding] = []
            for f in findings:
                override = self.policy.rule_severity(f.rule)
                if override == "off":
                    continue
                if override:
                    overridden.append(
                        Finding(
                            rule=f.rule,
                            severity=override,
                            file=f.file,
                            line=f.line,
                            code=f.code,
                            message=f.message,
                            fix=f.fix,
                        )
                    )
                else:
                    overridden.append(f)
            findings = [f for f in overridden if self._severity_passes(f.severity)]

        output = self.formatter.format(repo=repo, workflow_count=workflow_count, findings=findings)
        return {
            "output": output,
            "findings": findings,
            "workflow_count": workflow_count,
            "workflows": raw_workflows,
        }

    @staticmethod
    def _dependabot_has_actions(config: Any) -> bool:
        """True iff dependabot config has a github-actions ecosystem update."""
        if not isinstance(config, dict):
            return False
        updates = config.get("updates")
        if not isinstance(updates, list):
            return False
        return any(isinstance(u, dict) and u.get("package-ecosystem") == "github-actions" for u in updates)

    def _severity_passes(self, sev: str) -> bool:
        """True iff `sev` is at or above the configured minimum severity."""
        return SEVERITY_ORDER.get(sev, 99) <= SEVERITY_ORDER.get(self.min_severity, 99)
