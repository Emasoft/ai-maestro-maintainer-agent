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

# Run commands that require write access. The `git push` form must tolerate
# git's global options between `git` and the subcommand — `git -C <dir> push`,
# `git -c user.name=x push`, `git --git-dir=... push` are all real pushes (the
# strict `\bgit\s+push\b` missed `git -C ruff push --force` in
# astral-sh/ruff sync_typeshed.yaml, producing a false "excessive permissions"
# finding on a job that genuinely pushes). A looser push detector can only
# *reduce* this rule's findings (it fires when NO write op is found), so erring
# toward "this job writes" is the safe direction.
WRITE_COMMANDS: list["re.Pattern[str]"] = [
    re.compile(r"\bgit\s+(?:-C\s+\S+\s+|-c\s+\S+\s+|--?[\w][\w-]*(?:=\S+)?\s+)*push\b"),
    re.compile(r"\bgh\s+pr\s+create\b"),
    re.compile(r"\bgh\s+pr\s+merge\b"),
    re.compile(r"\bgh\s+pr\s+comment\b"),
    re.compile(r"\bgh\s+pr\s+review\b"),
    # `gh release` writes via create AND upload/edit/delete — the strict
    # `create`-only form missed `gh release upload` (zizmorcore/zizmor
    # release-binaries.yml), flagging a job that genuinely needs contents:write.
    re.compile(r"\bgh\s+release\s+(?:create|upload|edit|delete)\b"),
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
            # A reusable-workflow-call job has no inspectable steps — the work
            # lives in the called workflow, so we cannot conclude the grant is
            # excessive. Asserting "no steps need it" would be a false positive;
            # the called workflow is audited as its own file.
            if isinstance(job, dict) and "uses" in job:
                continue

            steps = workflow.steps(job)
            if self._has_write_operations(steps):
                continue

            line = workflow.job_line(job_id)
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
            # Explicit `persist-credentials: true` on a checkout step is a
            # deliberate write-intent signal — the author keeps the token in
            # git config to push later, often from inside a script the run:
            # text can't reveal (tiangolo/fastapi's contributors.py /
            # translate.py / people.py jobs, whose own comments say
            # "Required for git push"). Treat it as a genuine write need.
            if uses and "actions/checkout" in str(uses):
                with_block = step.get("with")
                if isinstance(with_block, dict) and with_block.get("persist-credentials") is True:
                    return True

            run = step.get("run")
            if run and any(pattern.search(run) for pattern in WRITE_COMMANDS):
                return True

        return False
