"""Git credentials configured far before the push step.

Port of lib/rules/credential_window.rb. When git credentials are set up
many steps before the push that needs them, every intervening step runs
with the token available — widening the credential-exposure window.
Faithful 1:1 behaviour.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.finding import Finding
from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.workflow import Workflow

MAX_STEPS_BETWEEN = 5

_CRED_RX = re.compile(r"git config.*insteadOf|git remote set-url")
_PUSH_RX = re.compile(r"git push")


class CredentialWindow(Rule):
    """High: git credentials set up more than MAX_STEPS_BETWEEN steps before push."""

    name = "credential-window"
    description = "Git credentials configured far before push step"
    severity = "high"

    def check(self, workflow: "Workflow") -> list[Finding]:
        """Flag jobs where the credential-config step precedes push by too many steps."""
        findings: list[Finding] = []

        for _job_id, job in workflow.jobs().items():
            steps = workflow.steps(job)
            cred_step: int | None = None
            push_step: int | None = None

            for i, step in enumerate(steps):
                run = str(step.get("run")) if (isinstance(step, dict) and step.get("run") is not None) else None
                if run is not None and _CRED_RX.search(run):
                    if cred_step is None:
                        cred_step = i
                if run is not None and _PUSH_RX.search(run):
                    push_step = i

            if cred_step is None or push_step is None:
                continue
            gap = push_step - cred_step

            if gap > MAX_STEPS_BETWEEN:
                line = workflow.line_of(_CRED_RX)
                findings.append(
                    self.finding(
                        workflow,
                        line=line or 0,
                        message=f"Git credentials configured {gap} steps before push — {gap - 1} steps have access to the token",
                        fix="Move credential configuration to immediately before the push step",
                    )
                )

        return findings
