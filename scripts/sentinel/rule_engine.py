"""Loads every rule and runs them against a workflow.

Port of lib/rule_engine.rb. Importing this module triggers rule
auto-discovery (via the rules package), then instantiates each registered
rule ordered by severity. A rule that raises is logged to stderr and
skipped — one broken rule never aborts the scan.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from . import rules as _rules  # noqa: F401  # import triggers rule registration
from .finding import SEVERITY_ORDER, Finding
from .rules.base import Rule

if TYPE_CHECKING:
    from .workflow import Workflow


class RuleEngine:
    """Holds one instance of every registered rule, severity-ordered."""

    def __init__(self) -> None:
        self.rules: list[Rule] = [cls() for cls in Rule.registry]
        self.rules.sort(key=lambda r: SEVERITY_ORDER.get(r.severity, 99))

    def scan(self, workflow: "Workflow") -> list[Finding]:
        """Run every rule against `workflow`; collect + severity-sort findings."""
        findings: list[Finding] = []
        for rule in self.rules:
            try:
                findings.extend(rule.check(workflow))
            except Exception as exc:  # noqa: BLE001  # mirror Ruby rescue => e
                print(f"Rule {rule.name} failed on {workflow.filename}: {exc}", file=sys.stderr)
        findings.sort()
        return findings
