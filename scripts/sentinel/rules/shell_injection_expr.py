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

        for line_num in workflow.lines_of(PATTERN):
            line = workflow.line_content(line_num)
            if line is None or line.strip().startswith("#"):
                continue
            if not self._in_run_block(workflow, line_num):
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

    def _in_run_block(self, workflow: "Workflow", target_line: int) -> bool:
        target_content = workflow.raw_lines[target_line - 1] if target_line - 1 < len(workflow.raw_lines) else None
        m_indent = re.match(r"^\s*", target_content) if target_content else None
        target_indent = len(m_indent.group(0)) if m_indent else 0

        lower = max(target_line - 20, 0)
        for i in range(target_line - 1, lower - 1, -1):
            if i < 0 or i >= len(workflow.raw_lines):
                continue
            content = workflow.raw_lines[i]

            if re.search(r"^\s+run:\s*[|>]?\s*$", content) or re.search(r"^\s+run:\s+\S", content):
                return True
            if re.search(r"^\s+-\s+run:\s*[|>]?\s*$", content) or re.search(r"^\s+-\s+run:\s+\S", content):
                return True

            # Stop at step-level keys, but only if the target line is at or
            # shallower than this key's indent (meaning the target is a sibling
            # or child of this key, not content of a deeper run: block).
            if re.search(r"^\s+(uses|with|if|id|name|env):", content) or re.search(r"^\s+-\s+name:", content):
                m = re.match(r"^\s*", content)
                line_indent = len(m.group(0)) if m else 0
                if target_indent <= line_indent + 2:
                    return False
        return False
