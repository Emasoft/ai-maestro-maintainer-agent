"""User-controlled workflow_dispatch input in a run: block.

Port of lib/rules/workflow_dispatch_injection.rb. A ``${{ inputs.* }}``
or ``${{ github.event.inputs.* }}`` expression interpolated directly
into a ``run:`` block is a shell-injection sink — dispatch inputs are
always user-controlled, so this rule does NOT exempt safe triggers.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule
from sentinel.rules.guard_patterns import GuardPatterns

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

PATTERN: "re.Pattern[str]" = re.compile(r"\$\{\{\s*(?:inputs\.|github\.event\.inputs\.)")

# NOTE: This rule intentionally does NOT use safe_trigger_only because
# dispatch inputs are user-controlled. workflow_dispatch IS in SAFE_TRIGGERS
# for other rules, but this rule specifically targets ${{ inputs.* }} in
# run blocks — those inputs are always attacker-controlled.

_INPUT_CAPTURE: "re.Pattern[str]" = re.compile(r"\$\{\{\s*((?:inputs|github\.event\.inputs)\.[^\s}]+)")


class WorkflowDispatchInjection(Rule, GuardPatterns):
    """${{ inputs.* }} interpolated into a run: block (shell injection)."""

    name = "workflow-dispatch-injection"
    description = "User-controlled workflow_dispatch input in run: block"
    severity = "high"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list["Finding"] = []

        for line_num in workflow.lines_of(PATTERN):
            line = workflow.line_content(line_num)
            if line is None:
                continue
            if line.strip().startswith("#"):
                continue
            if not self._in_run_block(workflow, line_num):
                continue
            match = _INPUT_CAPTURE.search(line)
            if not match:
                continue

            code = line.strip()
            findings.append(
                self.finding(
                    workflow,
                    line=line_num,
                    code=code,
                    message=f"User-controlled input ${{{{ {match.group(1)} }}}} in run: block — shell injection risk",
                    fix="Move to env: block and reference as $ENV_VAR",
                )
            )

        return findings

    def _in_run_block(self, workflow: "Workflow", target_line: int) -> bool:
        target_content = workflow.raw_lines[target_line - 1] if 0 <= target_line - 1 < len(workflow.raw_lines) else None
        target_indent = len(re.match(r"^\s*", target_content).group(0)) if target_content else 0  # type: ignore[union-attr]

        lower = max(target_line - 20, 0)
        for i in range(target_line - 1, lower - 1, -1):
            if i < 0 or i >= len(workflow.raw_lines):
                continue
            content = workflow.raw_lines[i]
            if not content:
                continue

            if re.search(r"^\s+run:\s*[|>]?\s*$", content) or re.search(r"^\s+run:\s+\S", content):
                return True
            if re.search(r"^\s+-\s+run:\s*[|>]?\s*$", content) or re.search(r"^\s+-\s+run:\s+\S", content):
                return True

            if re.search(r"^\s+(uses|with|if|id|name|env):", content) or re.search(r"^\s+-\s+name:", content):
                line_indent = len(re.match(r"^\s*", content).group(0))  # type: ignore[union-attr]
                if target_indent <= line_indent + 2:
                    return False

        return False
