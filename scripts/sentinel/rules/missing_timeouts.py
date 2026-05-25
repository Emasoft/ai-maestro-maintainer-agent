"""Job without timeout-minutes.

Port of lib/rules/missing_timeouts.rb. A job with no ``timeout-minutes``
inherits the 360-minute (6-hour) default — flag each such job.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow


class MissingTimeouts(Rule):
    """Job has no timeout-minutes (defaults to 6 hours)."""

    name = "missing-timeouts"
    description = "Job without timeout-minutes"
    severity = "low"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list["Finding"] = []

        for job_id, job in workflow.jobs().items():
            if isinstance(job, dict) and "timeout-minutes" in job:
                continue

            line = workflow.line_of(re.compile(r"^\s+" + re.escape(job_id) + r":"))
            findings.append(
                self.finding(
                    workflow,
                    line=line or 0,
                    code=f"{job_id}:",
                    message=f"Job '{job_id}' has no timeout-minutes — default is 360 minutes (6 hours)",
                    fix="Add timeout-minutes: appropriate for the job type (5-30 min)",
                )
            )

        return findings
