"""Action referenced by tag instead of SHA pin.

Port of lib/rules/unpinned_actions.rb. Severity varies: first-party
(actions/, github/) tag refs are low; third-party tag refs are medium.
Constructs Finding directly (like the Ruby rule) because severity is
per-finding, not the class default.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.finding import Finding
from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.workflow import Workflow

SHA_PATTERN = re.compile(r"@[0-9a-f]{40}\b")
FIRST_PARTY = ["actions/", "github/"]


class UnpinnedActions(Rule):
    """Flag actions pinned by mutable tag instead of an immutable commit SHA."""

    name = "unpinned-actions"
    description = "Action referenced by tag instead of SHA pin"
    severity = "medium"

    def check(self, workflow: "Workflow") -> list[Finding]:
        """Flag every `uses:` step pinned to a tag rather than a 40-char SHA."""
        findings: list[Finding] = []
        for action in workflow.uses_actions():
            uses = action["uses"]
            if uses is None:
                continue
            if uses.startswith("./"):
                continue
            if uses.startswith("docker://"):
                continue
            if SHA_PATTERN.search(uses):
                continue

            first_party = any(uses.startswith(prefix) for prefix in FIRST_PARTY)
            sev = "low" if first_party else "medium"

            findings.append(
                Finding(
                    rule=self.name,
                    severity=sev,
                    file=workflow.filename,
                    line=action["line"] or 0,
                    code=f"uses: {uses}",
                    message=f"Action '{uses}' is not SHA-pinned — tag references are mutable",
                    fix=f"Pin to a commit SHA: uses: {uses.split('@')[0]}@<commit-sha> # {uses.split('@')[-1]}",
                )
            )
        return findings
