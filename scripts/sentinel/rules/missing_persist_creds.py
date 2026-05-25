"""actions/checkout without persist-credentials: false.

Port of lib/rules/missing_persist_creds.rb. The default checkout leaves
the job token in .git/config, where any later step (or compromised
dependency) can read it. Faithful 1:1 behaviour.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from sentinel.finding import Finding
from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.workflow import Workflow

_CHECKOUT_RX = re.compile(r"actions/checkout[@\s]|actions/checkout$")
_PUSH_RUN_RX = re.compile(r"git push|gh pr create|peter-evans/create-pull-request")
_PUSH_USES_RX = re.compile(r"create-pull-request|yaml-update-action")


class MissingPersistCreds(Rule):
    """High: actions/checkout left with credentials persisted in .git/config."""

    name = "missing-persist-credentials"
    description = "actions/checkout without persist-credentials: false"
    severity = "high"

    def check(self, workflow: "Workflow") -> list[Finding]:
        """Flag each checkout step that does not disable credential persistence."""
        findings: list[Finding] = []
        seen_checkout_lines: dict[str, int] = {}

        for _job_id, job in workflow.jobs().items():
            job_pushes = self._job_does_push(job, workflow)

            for step in workflow.steps(job):
                uses = step.get("uses") if isinstance(step, dict) else None
                if not (uses and _CHECKOUT_RX.search(str(uses))):
                    continue

                with_block = step.get("with") if isinstance(step.get("with"), dict) else {}
                persist = with_block.get("persist-credentials")

                # Ruby: next if persist == false || persist == "false"
                if persist is False or persist == "false":
                    continue
                # Ruby: next if job_pushes && persist == true
                if job_pushes and persist is True:
                    continue

                all_lines = workflow.lines_of(re.compile(r"uses:\s*" + re.escape(str(uses))))
                idx = seen_checkout_lines.get(str(uses), 0)
                line = all_lines[idx] if idx < len(all_lines) else (all_lines[-1] if all_lines else None)
                seen_checkout_lines[str(uses)] = idx + 1

                findings.append(
                    self.finding(
                        workflow,
                        line=line or 0,
                        code=f"uses: {uses}",
                        message="Checkout without persist-credentials: false — token persists in .git/config",
                        fix="Add persist-credentials: false to the with: block",
                    )
                )

        return findings

    def _job_does_push(self, job: Any, workflow: "Workflow") -> bool:
        """True iff any step in the job pushes via git, gh, or a PR-creating action."""
        for s in workflow.steps(job):
            if not isinstance(s, dict):
                continue
            run = str(s.get("run")) if s.get("run") is not None else None
            if run is not None and _PUSH_RUN_RX.search(run):
                return True
            uses = s.get("uses")
            if uses and _PUSH_USES_RX.search(str(uses)):
                return True
        return False
