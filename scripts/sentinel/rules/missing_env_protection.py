"""Publish/deploy job without GitHub Environment protection.

Port of lib/rules/missing_env_protection.rb. A job that publishes a
package or deploys infrastructure (or holds an OIDC ``id-token: write``)
but has no ``environment:`` lacks a human gate before publication.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

# Regexp.union of every publish/deploy command indicator (alternation).
_PUBLISH_SOURCES: list[str] = [
    # JavaScript / TypeScript
    r"\bnpm\s+publish\b",
    r"\bpnpm\s+publish\b",
    r"\byarn\s+publish\b",
    r"\bnpx\s+pkg-pr-new\b",
    # Python
    r"\btwine\s+upload\b",
    r"\bpoetry\s+publish\b",
    r"\bflit\s+publish\b",
    r"\buv\s+publish\b",
    # Ruby
    r"\bgem\s+push\b",
    r"\brake\s+release\b",
    # Rust
    r"\bcargo\s+publish\b",
    # Java / Kotlin
    r"\bmvn\s+deploy\b",
    r"\bgradle\s+publish\b",
    r"\./gradlew\s+publish\b",
    # .NET
    r"\bdotnet\s+nuget\s+push\b",
    r"\bnuget\s+push\b",
    # Docker
    r"\bdocker\s+push\b",
    r"\bdocker\s+buildx\s+build\b.*--push",
    # Infrastructure
    r"\brailway\s+up\b",
    r"\bcdk\s+deploy\b",
    r"\bterraform\s+apply\b",
    r"\bpulumi\s+up\b",
    r"\bfly\s+deploy\b",
    r"\bheroku\s+container:push\b",
    # Homebrew
    r"\bbrew\s+bump-formula-pr\b",
]

PUBLISH_INDICATORS: "re.Pattern[str]" = re.compile("|".join(_PUBLISH_SOURCES))


class MissingEnvProtection(Rule):
    """Publish/deploy (or OIDC) job missing GitHub Environment protection."""

    name = "missing-env-protection"
    description = "Publish/deploy job without GitHub Environment protection"
    severity = "medium"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list["Finding"] = []

        for job_id, job in workflow.jobs().items():
            if isinstance(job, dict) and "environment" in job:
                continue

            steps = workflow.steps(job)
            has_publish = any(isinstance(s, dict) and s.get("run") and PUBLISH_INDICATORS.search(s["run"]) for s in steps)

            has_oidc = self._oidc_id_token(workflow.permissions(scope="job", job=job)) or self._oidc_id_token(workflow.permissions(scope="workflow"))

            if has_publish or has_oidc:
                line = workflow.line_of(re.compile(r"^\s+" + re.escape(job_id) + r":"))
                findings.append(
                    self.finding(
                        workflow,
                        line=line or 0,
                        code=f"{job_id}:",
                        message="Publish/deploy job without environment protection — no human gate before publication",
                        fix="Add environment: <name> with required reviewers",
                    )
                )

        return findings

    def _oidc_id_token(self, perms: Any) -> bool:
        if not isinstance(perms, dict):
            return False
        return perms.get("id-token") == "write"
