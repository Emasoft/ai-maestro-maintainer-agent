"""Self-hosted runner exposed to fork PRs detector.

Port of lib/rules/self_hosted_runner_fork.rb. Flags a job that runs on a
self-hosted runner under a ``pull_request`` / ``pull_request_target``
trigger that is not gated to label-only types — fork PRs can then run
arbitrary code on your infrastructure.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

_FORK_TRIGGERS = ("pull_request", "pull_request_target")
_SAFE_TYPES = ("labeled", "unlabeled")


class SelfHostedRunnerFork(Rule):
    """Self-hosted runner exposed to fork PRs."""

    name = "self-hosted-runner-fork"
    description = "Self-hosted runner exposed to fork PRs"
    severity = "high"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list["Finding"] = []
        triggers = workflow.triggers()

        fork_trigger = self._detect_fork_trigger(triggers)
        if not fork_trigger:
            return findings

        # Skip if the trigger is gated by label-based types.
        if self._gated_by_label(triggers, fork_trigger):
            return findings

        runs_on_lines = workflow.lines_of(re.compile(r"runs-on:"))
        runs_on_idx = 0

        for job in workflow.jobs().values():
            runs_on = job.get("runs-on") if isinstance(job, dict) else None
            if not runs_on:
                continue

            runs_on_str = ", ".join(runs_on) if isinstance(runs_on, list) else str(runs_on)

            # Advance through runs-on lines for each job regardless of self-hosted.
            line = runs_on_lines[runs_on_idx] if runs_on_idx < len(runs_on_lines) else None
            runs_on_idx += 1

            if "self-hosted" not in runs_on_str:
                continue

            findings.append(
                self.finding(
                    workflow,
                    line=line or 0,
                    code=f"runs-on: {runs_on_str}",
                    message=f"Self-hosted runner with '{fork_trigger}' trigger — fork PRs can run arbitrary code on your infrastructure",
                    fix="Use GitHub-hosted runners for fork PR workflows, or gate with a label-based trigger",
                )
            )

        return findings

    def _detect_fork_trigger(self, triggers: Any) -> str | None:
        for trigger in _FORK_TRIGGERS:
            if isinstance(triggers, dict):
                if trigger in triggers:
                    return trigger
            elif isinstance(triggers, list):
                if trigger in triggers:
                    return trigger
            elif isinstance(triggers, str):
                if triggers == trigger:
                    return trigger
        return None

    def _gated_by_label(self, triggers: Any, fork_trigger: str) -> bool:
        if not isinstance(triggers, dict):
            return False

        config = triggers.get(fork_trigger)
        if not isinstance(config, dict):
            return False

        types = config.get("types")
        if not isinstance(types, list):
            return False

        # Safe if ONLY label-based types (no code-execution types).
        return all(t in _SAFE_TYPES for t in types)
