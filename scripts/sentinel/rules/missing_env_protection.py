"""Publish/deploy job without GitHub Environment protection.

Port of lib/rules/missing_env_protection.rb, with one calibrated divergence.

The Ruby original treats a bare OIDC ``id-token: write`` permission as a
sufficient publish/deploy signal on its own. In practice ``id-token: write``
is used for far more than publishing — codecov uploads, cloud-auth in
integration tests, Sigstore attestation, GitHub Pages deploys — so the
standalone-OIDC trigger fired on ordinary CI/test/scan jobs and labelled them
"publish/deploy job", a false positive (observed on astral-sh/ruff ci.yaml,
astral-sh/uv ci.yml's ``test-integration`` reusable-workflow call, and
expressjs/express scorecard.yml). This port therefore requires a *concrete*
publish indicator: a real publish/deploy **run command** (``PUBLISH_INDICATORS``
minus ``--dry-run``) or a known publish **action** (``PUBLISH_ACTIONS``). A job
whose only publish signal is ``id-token: write`` is no longer flagged. True
positives — e.g. a job running ``uv publish`` with no ``environment:`` — are
unaffected; a publish job that delegates to a reusable workflow is caught when
that reusable workflow is scanned as its own file (the ``environment:`` belongs
on the real publish job, not the caller).
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

# A `--dry-run` publish (e.g. `cargo publish --dry-run`, `npm publish
# --dry-run`) uploads nothing, so it is NOT a real publication and must not
# trigger the rule — astral-sh/uv check-publish.yml runs `cargo publish
# --workspace --dry-run` purely as a CI smoke check.
_DRY_RUN = re.compile(r"--dry-run\b")

# Known publish/deploy *actions* (the `uses:` equivalents of PUBLISH_INDICATORS).
# These cover trusted-publishing-via-action, where there is no run command to
# match. Kept deliberately narrow to unambiguous registry-publish actions so a
# build/test job that merely happens to use them is not misclassified.
PUBLISH_ACTIONS: list["re.Pattern[str]"] = [
    re.compile(r"\bpypa/gh-action-pypi-publish\b"),
    re.compile(r"\bJS-DevTools/npm-publish\b"),
    re.compile(r"\brubygems/release-gem\b"),
]


class MissingEnvProtection(Rule):
    """Publish/deploy job missing GitHub Environment protection."""

    name = "missing-env-protection"
    description = "Publish/deploy job without GitHub Environment protection"
    severity = "medium"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list["Finding"] = []

        for job_id, job in workflow.jobs().items():
            if isinstance(job, dict) and "environment" in job:
                continue

            steps = workflow.steps(job)
            if not self._publishes(steps):
                continue

            line = workflow.job_line(job_id)
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

    def _publishes(self, steps: list[Any]) -> bool:
        """True iff a step performs a real publish — a non-dry-run publish run
        command or a known publish action. OIDC alone is intentionally NOT a
        publish signal here (see module docstring)."""
        for step in steps:
            if not isinstance(step, dict):
                continue
            run = step.get("run")
            if isinstance(run, str) and PUBLISH_INDICATORS.search(run) and not _DRY_RUN.search(run):
                return True
            uses = step.get("uses")
            if isinstance(uses, str) and any(p.search(uses) for p in PUBLISH_ACTIONS):
                return True
        return False
