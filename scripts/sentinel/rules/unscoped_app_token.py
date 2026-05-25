"""GitHub App token minted without scoped permissions.

Port of lib/rules/unscoped_app_token.rb. create-github-app-token without
any permission-<name> input inherits the App installation's blanket
permissions. Faithful 1:1 behaviour.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.finding import Finding
from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.workflow import Workflow

_TOKEN_RX = re.compile(r"create-github-app-token")


class UnscopedAppToken(Rule):
    """Medium: create-github-app-token without any permission-<name> scoping."""

    name = "unscoped-app-token"
    description = "GitHub App token without scoped permissions"
    severity = "medium"

    def check(self, workflow: "Workflow") -> list[Finding]:
        """Flag app-token steps that lack a permission-* input."""
        findings: list[Finding] = []

        for _job_id, job in workflow.jobs().items():
            for step in workflow.steps(job):
                uses = step.get("uses") if isinstance(step, dict) else None
                if not (uses and "create-github-app-token" in str(uses)):
                    continue

                with_block = step.get("with") if isinstance(step.get("with"), dict) else {}
                has_permissions = any(str(k).startswith("permission-") for k in with_block.keys())

                if not has_permissions:
                    line = workflow.line_of(_TOKEN_RX)
                    findings.append(
                        self.finding(
                            workflow,
                            line=line or 0,
                            message="App token inherits blanket installation permissions",
                            fix="Add permission-<name>: write inputs to scope the token",
                        )
                    )

        return findings
