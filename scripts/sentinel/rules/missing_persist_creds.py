"""actions/checkout without persist-credentials: false.

Port of lib/rules/missing_persist_creds.rb with one calibrated divergence on
the deliberate-persister exemption. The default checkout leaves the job token
in .git/config, where any later step (or compromised dependency) can read it.

The Ruby original exempted a checkout only when the job pushed AND the step set
``persist-credentials: true`` (it detected pushes by grepping run: blocks for
``git push`` etc.). That missed deliberate persisters whose push lives in a
called script or action — tiangolo/fastapi's contributors.py / latest-changes
jobs and astral-sh/ruff's ``git -C ruff push`` all set ``persist-credentials:
true`` explicitly but were still flagged as high-severity false positives whose
suggested fix (``persist-credentials: false``) would break the push. Here an
explicit ``persist-credentials: true`` is treated as the author's own
acknowledgment and always exempts the step, regardless of whether the push is
statically visible. The actionable finding stays the IMPLICIT default — no key
set, credentials persisted unintentionally (e.g. sindresorhus/got's read-only
CI checkout) — which is still flagged so the author opts in explicitly.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.finding import Finding
from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.workflow import Workflow

_CHECKOUT_RX = re.compile(r"actions/checkout[@\s]|actions/checkout$")


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
            for step in workflow.steps(job):
                uses = step.get("uses") if isinstance(step, dict) else None
                if not (uses and _CHECKOUT_RX.search(str(uses))):
                    continue

                # Evaluate step.get("with") ONCE into a variable so the
                # isinstance() narrows the same value that is assigned (a
                # second .get() call is a distinct expression Pyright cannot
                # link, leaving with_block typed as possibly-None).
                with_raw = step.get("with") if isinstance(step, dict) else None
                with_block = with_raw if isinstance(with_raw, dict) else {}
                persist = with_block.get("persist-credentials")

                # persist-credentials: false — mitigated, no finding.
                if persist is False or persist == "false":
                    continue
                # Explicit persist-credentials: true — deliberate persister (see
                # module docstring); exempt regardless of where the push lives.
                if persist is True or persist == "true":
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
