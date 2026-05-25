"""Build and publish in the same job with publish secrets in scope.

Port of lib/rules/build_publish_same_job.rb. When a single job both
installs dependencies and publishes a package while a publish credential
is present in its env, a compromised dependency can read that credential
during the build phase. Faithful 1:1 behaviour.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from sentinel.finding import Finding
from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.workflow import Workflow

# Ruby Regexp.union(...) -> alternation of each source pattern.
INSTALL_PATTERNS = re.compile(
    "|".join(
        [
            # JavaScript / TypeScript
            r"\bnpm\s+(install|ci)\b",
            r"\bpnpm\s+install\b",
            r"\byarn\s+install\b",
            r"\byarn\b(?!\s+(publish|add|remove|run|build|test|lint))",
            r"\bbun\s+install\b",
            # Python
            r"\bpip3?\s+install\b",
            r"\buv\s+(pip\s+install|sync)\b",
            r"\bpoetry\s+install\b",
            r"\bpipenv\s+install\b",
            r"\bconda\s+install\b",
            # Ruby
            r"\bbundle\s+install\b",
            r"\bbundle\b(?!\s+(exec|push|open|show|update|outdated|gem))",
            r"\bgem\s+install\b",
            # Go
            r"\bgo\s+mod\s+download\b",
            r"\bgo\s+get\b",
            r"\bgo\s+install\b",
            # Rust
            r"\bcargo\s+(build|fetch)\b",
            # Java / Kotlin
            r"\bmvn\s+(install|package)\b",
            r"\bgradle\s+build\b",
            r"\./gradlew\s+build\b",
            # .NET
            r"\bdotnet\s+restore\b",
            r"\bnuget\s+restore\b",
            # PHP
            r"\bcomposer\s+(install|update)\b",
            # Elixir
            r"\bmix\s+deps\.get\b",
            # Swift
            r"\bswift\s+package\s+resolve\b",
        ]
    )
)

PUBLISH_PATTERNS = re.compile(
    "|".join(
        [
            # JavaScript / TypeScript
            r"\bnpm\s+publish\b",
            r"\bpnpm\s+publish\b",
            r"\bnpx\s+pkg-pr-new\b",
            r"\byarn\s+publish\b",
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
            # Homebrew
            r"\bbrew\s+tap\b",
            r"\bbrew\s+bump-formula-pr\b",
        ]
    )
)

PUBLISH_SECRETS = re.compile(
    "|".join(
        [
            # JavaScript
            r"\bNPM_TOKEN\b",
            r"\bNODE_AUTH_TOKEN\b",
            r"\bNPM_AUTH_TOKEN\b",
            # Python
            r"\bPYPI_TOKEN\b",
            r"\bPYPI_API_TOKEN\b",
            r"\bTWINE_PASSWORD\b",
            r"\bPOETRY_PYPI_TOKEN_PYPI\b",
            # Ruby
            r"\bGEM_HOST_API_KEY\b",
            r"\bRUBYGEMS_API_KEY\b",
            r"\bRUBYGEMS_AUTH_TOKEN\b",
            # Rust
            r"\bCARGO_REGISTRY_TOKEN\b",
            r"\bCRATES_IO_TOKEN\b",
            # Java / Gradle
            r"\bMAVEN_PASSWORD\b",
            r"\bMAVEN_GPG_PASSPHRASE\b",
            r"\bGRADLE_PUBLISH_KEY\b",
            r"\bOSSRH_PASSWORD\b",
            r"\bSONATYPE_PASSWORD\b",
            # .NET
            r"\bNUGET_API_KEY\b",
            r"\bNUGET_AUTH_TOKEN\b",
            # Docker
            r"\bDOCKER_PASSWORD\b",
            r"\bDOCKER_TOKEN\b",
            r"\bDOCKERHUB_TOKEN\b",
            # General
            r"\bREGISTRY_TOKEN\b",
            r"\bPUBLISH_TOKEN\b",
        ]
    )
)

_SECRETS_CTX = re.compile(r"secrets\.")


class BuildPublishSameJob(Rule):
    """High: install + publish in one job while a publish secret is in scope."""

    name = "build-publish-same-job"
    description = "Build and publish in same job with publish secrets available during build"
    severity = "high"

    def check(self, workflow: "Workflow") -> list[Finding]:
        """Flag any job that both installs and publishes with a publish credential present."""
        findings: list[Finding] = []

        for job_id, job in workflow.jobs().items():
            steps = workflow.steps(job)
            has_install = any(self._run_matches(s, INSTALL_PATTERNS) for s in steps)
            has_publish = any(self._run_matches(s, PUBLISH_PATTERNS) for s in steps)

            if not (has_install and has_publish):
                continue

            # Ruby: job["env"]&.to_s || "" — str() of a dict still carries
            # the token names + `secrets.` substrings, so regex matches hold.
            job_env = str(job.get("env")) if (isinstance(job, dict) and job.get("env") is not None) else ""
            step_envs = " ".join(str(s.get("env") or {}) for s in steps if isinstance(s, dict))
            all_env = job_env + step_envs

            if PUBLISH_SECRETS.search(all_env) or _SECRETS_CTX.search(all_env):
                line = workflow.job_line(job_id)
                findings.append(
                    self.finding(
                        workflow,
                        line=line or 0,
                        code=f"job: {job_id}",
                        message="Build and publish in same job — a compromised dependency could read the publish credentials",
                        fix="Split into separate build (read-only) and publish (with secrets) jobs connected via artifacts",
                    )
                )

        return findings

    def _run_matches(self, step: Any, rx: "re.Pattern[str]") -> bool:
        """True iff the step's `run:` exists and matches the given pattern."""
        run = step.get("run") if isinstance(step, dict) else None
        return bool(run) and bool(rx.search(str(run)))
