"""Fork-artifact download in a privileged context detector.

Port of lib/rules/allow_forks_artifact.rb. Flags ``allow_forks: true`` on
an artifact download — fork-produced artifacts then enter a privileged
``workflow_run`` context.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

_ALLOW_FORKS_TRUE = re.compile(r"allow_forks:\s*true")


class AllowForksArtifact(Rule):
    """Artifact download with allow_forks: true in privileged context."""

    name = "allow-forks-artifact"
    description = "Artifact download with allow_forks: true in privileged context"
    severity = "medium"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list["Finding"] = []

        for line_num in workflow.lines_of(_ALLOW_FORKS_TRUE):
            content = workflow.line_content(line_num)
            findings.append(
                self.finding(
                    workflow,
                    line=line_num,
                    code=content.strip() if content else "",
                    message="Downloading fork-produced artifacts in a privileged workflow_run context",
                    fix="Ensure fork-produced artifact content is not executed or processed unsafely",
                )
            )

        return findings
