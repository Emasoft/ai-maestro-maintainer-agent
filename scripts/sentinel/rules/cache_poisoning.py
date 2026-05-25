"""Cache-key poisoning detector.

Port of lib/rules/cache_poisoning.rb. Flags cache actions whose ``key``
embeds a mutable, fork-controllable reference (``github.head_ref``, the PR
head ref, or ``github.ref`` on a pull_request trigger).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

_CACHE_ACTIONS = (
    "actions/cache",
    "actions/cache/restore",
    "actions/cache/save",
)

# Fork-controllable refs that should never appear in cache keys.
_DANGEROUS_KEY_PATTERNS = [
    re.compile(r"\$\{\{\s*github\.head_ref\s*\}\}"),
    re.compile(r"\$\{\{\s*github\.event\.pull_request\.head\.ref\s*\}\}"),
]

# github.ref on pull_request triggers resolves to the PR merge ref.
_GITHUB_REF_PATTERN = re.compile(r"\$\{\{\s*github\.ref\s*\}\}")

_PR_TRIGGERS = ("pull_request", "pull_request_target")


class CachePoisoning(Rule):
    """Cache key uses mutable, fork-controllable reference."""

    name = "cache-poisoning"
    description = "Cache key uses mutable, fork-controllable reference"
    severity = "medium"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list["Finding"] = []
        has_pr_trigger = self._pr_triggered(workflow)

        for action in workflow.uses_actions():
            uses = action["uses"]
            if not any(uses and uses.startswith(ca) for ca in _CACHE_ACTIONS):
                continue

            step = action["step"]
            with_block = step.get("with") if isinstance(step, dict) else None
            key_value = with_block.get("key") if isinstance(with_block, dict) else None
            if not key_value:
                continue

            # Check for directly dangerous patterns.
            for pattern in _DANGEROUS_KEY_PATTERNS:
                if pattern.search(key_value):
                    findings.append(
                        self.finding(
                            workflow,
                            line=action["line"] or 0,
                            code=f"key: {key_value}",
                            message="Cache key contains fork-controllable reference — risk of cache poisoning",
                            fix="Use hashFiles() for cache keys, not branch refs. Consider prefixing fork PR cache keys.",
                        )
                    )
                    break

            # Check for github.ref on PR-triggered workflows.
            if has_pr_trigger and _GITHUB_REF_PATTERN.search(key_value):
                findings.append(
                    self.finding(
                        workflow,
                        line=action["line"] or 0,
                        code=f"key: {key_value}",
                        message="Cache key uses github.ref on pull_request trigger — resolves to mutable PR merge ref",
                        fix="Use hashFiles() for cache keys, not branch refs. Consider prefixing fork PR cache keys.",
                    )
                )

        return findings

    def _pr_triggered(self, workflow: "Workflow") -> bool:
        triggers = workflow.triggers()
        if isinstance(triggers, dict):
            return any(str(t) in _PR_TRIGGERS for t in triggers.keys())
        if isinstance(triggers, list):
            return any(str(t) in _PR_TRIGGERS for t in triggers)
        if isinstance(triggers, str):
            return triggers in _PR_TRIGGERS
        return False
