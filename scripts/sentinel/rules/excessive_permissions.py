"""Job has contents: write but no steps that appear to need it.

Port of lib/rules/excessive_permissions.rb. A job granted
``contents: write`` that performs no write operation (no git push, no
gh write subcommand, no known write action) is over-privileged.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

# Actions that perform write operations.
WRITE_ACTIONS: list["re.Pattern[str]"] = [
    re.compile(r"peter-evans/create-pull-request"),
    re.compile(r"stefanzweifel/git-auto-commit-action"),
    re.compile(r"ad-m/github-push-action"),
    re.compile(r"EndBug/add-and-commit"),
]

# Run commands that require write access.
WRITE_COMMANDS: list["re.Pattern[str]"] = [
    re.compile(r"\bgit\s+push\b"),
    re.compile(r"\bgh\s+pr\s+create\b"),
    re.compile(r"\bgh\s+pr\s+merge\b"),
    re.compile(r"\bgh\s+pr\s+comment\b"),
    re.compile(r"\bgh\s+pr\s+review\b"),
    re.compile(r"\bgh\s+release\s+create\b"),
    re.compile(r"\bgh\s+api\b"),
]


class ExcessivePermissions(Rule):
    """Job with contents: write but no apparent write operation in its steps."""

    name = "excessive-permissions"
    description = "Job has write permissions but no steps that appear to need them"
    severity = "low"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list["Finding"] = []

        for job_id, job in workflow.jobs().items():
            job_perms = workflow.permissions(scope="job", job=job)
            if not isinstance(job_perms, dict):
                continue
            if job_perms.get("contents") != "write":
                continue

            steps = workflow.steps(job)
            if self._has_write_operations(steps):
                continue

            line = workflow.line_of(re.compile(r"^\s+" + re.escape(job_id) + r":"))
            findings.append(
                self.finding(
                    workflow,
                    line=line or 0,
                    code=f"{job_id}: permissions: contents: write",
                    message="This job has contents: write permission but no steps that appear to need it",
                    fix="This job has write permissions but no steps that appear to need them. Consider restricting to contents: read.",
                )
            )

        return findings

    def _has_write_operations(self, steps: list[Any]) -> bool:
        for step in steps:
            if not isinstance(step, dict):
                continue

            uses = step.get("uses")
            if uses and any(pattern.search(uses) for pattern in WRITE_ACTIONS):
                return True

            run = step.get("run")
            if run and any(pattern.search(run) for pattern in WRITE_COMMANDS):
                return True

        return False
