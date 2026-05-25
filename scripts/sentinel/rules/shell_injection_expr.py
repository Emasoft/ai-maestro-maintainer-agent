"""Shell-injection-via-expression detector.

Port of lib/rules/shell_injection_expr.rb. Flags an attacker-controllable
``${{ ... }}`` context interpolated directly inside a ``run:`` block,
unless the workflow is triggered only by safe events or the line sits
behind a safe ``if:`` guard.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule
from sentinel.rules.guard_patterns import DANGEROUS_CONTEXTS, GuardPatterns

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

PATTERN = re.compile(r"\$\{\{\s*(" + "|".join(re.escape(c) for c in DANGEROUS_CONTEXTS) + ")")


class ShellInjectionExpr(Rule, GuardPatterns):
    """Detects attacker-controllable expressions interpolated in run: blocks."""

    name = "shell-injection-expr"
    description = "Attacker-controllable ${{ }} expression in run: block"
    severity = "critical"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list[Finding] = []

        if self.safe_trigger_only(workflow):
            return []

        run_lines = workflow.run_content_lines()
        for line_num in workflow.lines_of(PATTERN):
            line = workflow.line_content(line_num)
            if line is None or line.strip().startswith("#"):
                continue
            if line_num not in run_lines:
                continue
            if self.guarded_by_safe_event(workflow, line_num):
                continue

            match = PATTERN.search(line)
            if not match:
                continue

            code = workflow.line_content(line_num)
            findings.append(
                self.finding(
                    workflow,
                    line=line_num,
                    code=code.strip() if code else None,
                    message=f"Attacker-controllable expression ${{{{ {match.group(1)} }}}} in run: block — shell injection risk",
                    fix="Move to env: block and reference as $ENV_VAR in the shell",
                )
            )
        return findings
