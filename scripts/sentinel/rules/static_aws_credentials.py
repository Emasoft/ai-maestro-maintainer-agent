"""AWS credentials using static keys instead of OIDC.

Port of lib/rules/static_aws_credentials.rb. A configure-aws-credentials
step carrying ``aws-access-key-id`` but no ``role-to-assume`` relies on
long-lived static keys that never auto-expire; OIDC federation is the
fix.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow


class StaticAwsCredentials(Rule):
    """Flag configure-aws-credentials steps using static keys instead of OIDC."""

    name = "static-aws-credentials"
    description = "AWS credentials using static keys instead of OIDC"
    severity = "medium"

    def check(self, workflow: "Workflow") -> list[Finding]:
        """Flag AWS credential steps with static keys and no role-to-assume."""
        findings: list[Finding] = []
        for job in workflow.jobs().values():
            for step in workflow.steps(job):
                uses = step.get("uses") if isinstance(step, dict) else None
                if not (uses and "configure-aws-credentials" in uses):
                    continue

                with_block = step.get("with") or {}
                has_static = "aws-access-key-id" in with_block
                has_oidc = "role-to-assume" in with_block

                if has_static and not has_oidc:
                    line = workflow.line_of(re.compile(r"aws-access-key-id"))
                    findings.append(
                        self.finding(
                            workflow,
                            line=line or 0,
                            code="aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}",
                            message="Static AWS access keys — long-lived credentials that don't auto-expire",
                            fix="Use OIDC federation: role-to-assume with id-token: write permission",
                        )
                    )
        return findings
