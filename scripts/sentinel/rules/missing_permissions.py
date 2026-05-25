"""No top-level permissions block.

Port of lib/rules/missing_permissions.rb. When a workflow omits a
top-level ``permissions:`` block, jobs inherit the broad default token
permissions — flag it so the workflow opts into least privilege.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow


class MissingPermissions(Rule):
    """Workflow has no top-level permissions block (jobs inherit broad token)."""

    name = "missing-permissions"
    description = "No top-level permissions block"
    severity = "medium"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        # Ruby gate `return [] if workflow.permissions(...)` treats an empty
        # hash `permissions: {}` as truthy (no finding). Python's `{}` is
        # falsy, so test "key present" via `is not None` to preserve 1:1
        # behaviour — the key is absent (None) only when there's no block.
        if workflow.permissions(scope="workflow") is not None:
            return []

        # A job-level `permissions:` block fully replaces the default token for
        # that job, so if EVERY job scopes its own permissions, no job inherits
        # the broad default and the rule's premise is false. The Ruby original
        # only checked the workflow level and so flagged per-job-scoped publish
        # workflows (astral-sh/ruff publish-pypi.yml / publish-wasm.yml,
        # astral-sh/uv publish-pypi.yml / publish-crates.yml) as false positives.
        # A reusable-call job without its own block still forwards the default,
        # so it does NOT count as scoped — those workflows remain flagged.
        jobs = workflow.jobs()
        if jobs and all(isinstance(j, dict) and "permissions" in j for j in jobs.values()):
            return []

        line = workflow.line_of(re.compile(r"^jobs:")) or 1
        return [
            self.finding(
                workflow,
                line=line,
                message="No top-level permissions block — jobs inherit broad default token permissions",
                fix="Add permissions: contents: read at the workflow level",
            )
        ]
