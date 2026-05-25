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

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

PATTERN: "re.Pattern[str]" = re.compile(r"\$\{\{\s*(?:inputs\.|github\.event\.inputs\.)")

# NOTE: This rule intentionally does NOT use safe_trigger_only because
# dispatch inputs are user-controlled. workflow_dispatch IS in SAFE_TRIGGERS
# for other rules, but this rule specifically targets ${{ inputs.* }} in
# run blocks — those inputs are always attacker-controlled.

_INPUT_CAPTURE: "re.Pattern[str]" = re.compile(r"\$\{\{\s*((?:inputs|github\.event\.inputs)\.[^\s}]+)")


class WorkflowDispatchInjection(Rule):
    """${{ inputs.* }} interpolated into a run: block (shell injection)."""

    name = "workflow-dispatch-injection"
    description = "User-controlled workflow_dispatch input in run: block"
    severity = "high"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list["Finding"] = []
        run_lines = workflow.run_content_lines()

        for line_num in workflow.lines_of(PATTERN):
            line = workflow.line_content(line_num)
            if line is None:
                continue
            if line.strip().startswith("#"):
                continue
            if line_num not in run_lines:
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
