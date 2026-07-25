"""Flag workflows a dependency's CLI writes, so provenance gets checked.

A dependency CLI can drop a file into `.github/workflows/` as the DEFAULT
branch of a documented command — no install-time hook required, so nothing
in the supply chain fires and no reviewer is prompted. The developer runs
one setup command and acquires a workflow they did not author.

This rule answers only the cheap, deterministic half of "who wrote this
workflow?": the filename matches one a known generator emits. That is the
*files are present on disk* state — actionable, not proof of compromise.
Deliberately NOT conflated with the two other states, because reporting a
documented opt-in feature at critical severity teaches readers to discount
the detector for the day a genuinely malicious package arrives:

    package CAN write agent-context files  → informational (dependency scan)
    package DOES at install time           → critical (its package.json scripts)
    the files are actually present         → actionable  ← this rule

Reported at medium: the file is really there and its provenance is unknown,
but presence alone is not evidence of an install-time trigger. Confirm
authorship from git before deleting anything — a maintainer may have adopted
the generated workflow deliberately, which is a legitimate choice.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

# Known (package, command, emitted workflow) triples. Keyed by the emitted
# BASENAME because that is what survives into the repo. Keep entries factual
# and verifiable — a speculative entry costs a false positive on every scan.
GENERATED_WORKFLOWS: dict[str, dict[str, str]] = {
    "copilot-setup-steps.yml": {
        "package": "playwright",
        "command": "playwright init-agents",
        "note": (
            "written by the Copilot generator, which is the fall-through when "
            "no --loop flag is given, so the bare command emits it"
        ),
    },
}


class GeneratedWorkflowProvenance(Rule):
    """Workflow filename matches one a dependency CLI generates."""

    name = "generated-workflow-provenance"
    description = "Workflow matches a known dependency-generated filename — verify who authored it"
    severity = "medium"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        entry = GENERATED_WORKFLOWS.get(os.path.basename(workflow.filename))
        if entry is None:
            return []

        return [
            self.finding(
                workflow,
                line=1,
                code=os.path.basename(workflow.filename),
                message=(
                    f"{os.path.basename(workflow.filename)} is the filename "
                    f"`{entry['command']}` ({entry['package']}) emits — "
                    f"{entry['note']}. A workflow nobody on the team authored "
                    f"runs in CI with the repo's permissions."
                ),
                fix=(
                    "Establish provenance before trusting it: "
                    "`git log --follow --format='%an %ae %s' -- <this file>`. "
                    "A human author who intended it means this is adopted, not "
                    "injected — keep it (and silence this rule for the file via "
                    "policy). No human author, or a commit that only says a tool "
                    "ran, means it arrived as a side effect: delete it, or adopt "
                    "it deliberately with a reviewed commit. Check the install-time "
                    "question separately — `scripts` in the package's package.json "
                    "is what would make this critical rather than actionable."
                ),
            )
        ]
