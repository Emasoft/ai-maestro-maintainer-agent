"""Unfiltered push / pull_request trigger detector.

Port of lib/rules/overly_broad_triggers.rb. Flags a ``push`` or
``pull_request`` trigger that carries no branch/tag/path filter, so it
fires on every branch.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

# Filter keys whose presence scopes a trigger.
_FILTER_KEYS = ("branches", "branches-ignore", "tags", "tags-ignore", "paths", "paths-ignore")


class OverlyBroadTriggers(Rule):
    """Push or pull_request trigger without branch filter."""

    name = "overly-broad-triggers"
    description = "Push or pull_request trigger without branch filter"
    severity = "low"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list["Finding"] = []
        triggers = workflow.triggers()

        if not isinstance(triggers, dict):
            return findings

        for trigger in ("push", "pull_request"):
            if trigger not in triggers:
                continue
            config = triggers[trigger]

            if config is None or config is True or (isinstance(config, dict) and not any(k in config for k in _FILTER_KEYS)):
                line = workflow.line_of(re.compile(r"^\s+" + trigger + r":"))
                findings.append(
                    self.finding(
                        workflow,
                        line=line or 0,
                        code=f"{trigger}:",
                        message=f"'{trigger}' trigger with no branch filter — runs on all branches",
                        fix="Add branches: [main] to scope the trigger",
                    )
                )

        return findings
