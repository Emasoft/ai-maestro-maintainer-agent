"""download-artifact without a specific artifact name.

Port of lib/rules/unpinned_artifact.rb. A `download-artifact` step with
no `with.name` downloads every artifact in the run, which may include
attacker-produced content from an earlier untrusted job.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

DOWNLOAD_ARTIFACT_PATTERN = re.compile(r"\bactions/download-artifact\b")


class UnpinnedArtifact(Rule):
    """Flag actions/download-artifact steps that omit a specific artifact name."""

    name = "unpinned-artifact"
    description = "download-artifact without specific artifact name"
    severity = "low"

    def check(self, workflow: "Workflow") -> list[Finding]:
        """Flag download-artifact steps with no non-empty `with.name`."""
        findings: list[Finding] = []
        for action in workflow.uses_actions():
            uses = action["uses"]
            if not (uses and DOWNLOAD_ARTIFACT_PATTERN.search(uses)):
                continue

            step = action["step"]
            with_block = step.get("with")
            with_block = with_block if isinstance(with_block, dict) else {}

            # download-artifact@v4+ narrows the download with `name:` (exact),
            # `pattern:` (glob), OR `artifact-ids:` (explicit IDs). Only a step
            # with none of these actually downloads every artifact in the run —
            # the message's premise. (pallets/flask and psf/requests both select
            # via `artifact-ids: ${{ needs.build.outputs.artifact-id }}`, which
            # is just as specific as a name and must NOT be flagged.)
            has_selector = any(with_block.get(k) is not None and str(with_block.get(k)).strip() != "" for k in ("name", "pattern", "artifact-ids"))

            if not has_selector:
                findings.append(
                    self.finding(
                        workflow,
                        line=action["line"] or 0,
                        code=f"uses: {uses}",
                        message="download-artifact without specific name downloads ALL artifacts — may include untrusted content",
                        fix="Specify artifact name: in download-artifact to avoid downloading unintended artifacts",
                    )
                )
        return findings
