"""pull_request_target + fork-code checkout detector.

Port of lib/rules/dangerous_triggers.rb. Flags a ``pull_request_target``
workflow that checks out the PR head ref/sha — fork-controlled code then
runs with the base repo's secrets.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

# Fork-controllable head refs in a checkout `ref:` (Ruby /.../i alternation).
_HEAD_REF = re.compile(r"\bgithub\.event\.pull_request\.head\b|\.head_ref\b|pull_request\.head\.sha", re.IGNORECASE)
_HEAD_REF_EXPR = re.compile(r"\$\{\{\s*github\.head_ref\s*\}\}")
_LINE_REF_HEAD = re.compile(r"ref:.*head", re.IGNORECASE)
_LINE_CHECKOUT = re.compile(r"checkout")


class DangerousTriggers(Rule):
    """pull_request_target with fork code checkout."""

    name = "dangerous-triggers"
    description = "pull_request_target with fork code checkout"
    severity = "critical"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list["Finding"] = []
        triggers = workflow.triggers()

        if isinstance(triggers, dict):
            has_prt = "pull_request_target" in triggers
        elif isinstance(triggers, list):
            has_prt = "pull_request_target" in triggers
        elif isinstance(triggers, str):
            has_prt = triggers == "pull_request_target"
        else:
            has_prt = False

        if not has_prt:
            return findings

        for job in workflow.jobs().values():
            for step in workflow.steps(job):
                uses = step.get("uses") if isinstance(step, dict) else None
                if not (uses and "checkout" in uses):
                    continue

                with_block = step.get("with") or {}
                ref = str(with_block.get("ref")) if with_block.get("ref") is not None else ""

                if _HEAD_REF.search(ref) or _HEAD_REF_EXPR.search(ref):
                    line = workflow.line_of(_LINE_REF_HEAD) or workflow.line_of(_LINE_CHECKOUT)
                    findings.append(
                        self.finding(
                            workflow,
                            line=line or 0,
                            code=f"ref: {ref}",
                            message="pull_request_target + checkout of PR head — fork code runs with base repo secrets",
                            fix="Use pull_request trigger instead, or don't checkout PR head code",
                        )
                    )

        return findings
