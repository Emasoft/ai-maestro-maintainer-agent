"""Docker image referenced by the mutable :latest tag.

Port of lib/rules/unpinned_docker_image.rb. Scans every line containing
``:latest`` and flags the ones that anchor it to a docker image, service
container, or container action reference.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

# Each line is a single raw_lines element, so no re.MULTILINE is needed.
_LATEST_LINE = re.compile(r"docker://.*:latest|image:.*:latest|uses:.*:latest|docker:.*:latest|container:.*:latest")
# A digest pin (`@sha256:...`) makes the reference immutable regardless of the
# tag — `python:latest-dev@sha256:abc…` is reproducible, so it must NOT flag.
_DIGEST_PINNED = re.compile(r"@sha256:[0-9a-fA-F]{64}")


class UnpinnedDockerImage(Rule):
    """Flag Docker images pinned to :latest — mutable and non-reproducible."""

    name = "unpinned-docker-image"
    description = "Docker image referenced by :latest tag"
    severity = "low"

    def check(self, workflow: "Workflow") -> list[Finding]:
        """Flag image/container/uses lines that reference the :latest tag."""
        findings: list[Finding] = []
        for line_num in workflow.lines_of(re.compile(r":latest\b")):
            line = workflow.line_content(line_num)
            if not (line and _LATEST_LINE.search(line)):
                continue
            # Digest-pinned references are immutable despite the tag.
            if _DIGEST_PINNED.search(line):
                continue

            findings.append(
                self.finding(
                    workflow,
                    line=line_num,
                    code=line.strip(),
                    message="Docker image uses :latest tag — mutable, not reproducible",
                    fix="Pin to a specific digest: image@sha256:...",
                )
            )
        return findings
