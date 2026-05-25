"""Secrets passed as Docker build-args (visible in image layers).

Port of lib/rules/docker_build_arg_secrets.rb. Values passed via
build-args are baked into image layers and recoverable with
`docker history`. Scans the lines following a `build-args:` key until the
block ends. Faithful 1:1 behaviour.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.finding import Finding
from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.workflow import Workflow

_BUILD_ARGS_RX = re.compile(r"build-args:")
_SECRETS_RX = re.compile(r"secrets\.")
_NEW_KEY_RX = re.compile(r"^\s*\w+:")
_ARG_ASSIGN_RX = re.compile(r"^\s+[\"']?[A-Z_]+=")


class DockerBuildArgSecrets(Rule):
    """Medium: a secret expression appears inside a Docker build-args block."""

    name = "docker-build-arg-secrets"
    description = "Secrets passed as Docker build-args (visible in image layers)"
    severity = "medium"

    def check(self, workflow: "Workflow") -> list[Finding]:
        """Scan each build-args block for `secrets.` references."""
        findings: list[Finding] = []

        for line_num in workflow.lines_of(_BUILD_ARGS_RX):
            # Ruby inclusive range (line_num..line_num+20).
            for i in range(line_num, line_num + 21):
                if i > len(workflow.raw_lines):
                    break
                line = workflow.line_content(i)
                # End of block: a new mapping key that isn't an ARG=value entry.
                if line is not None and _NEW_KEY_RX.search(line) and not _ARG_ASSIGN_RX.search(line):
                    break

                if line is not None and _SECRETS_RX.search(line):
                    findings.append(
                        self.finding(
                            workflow,
                            line=i,
                            code=line.strip(),
                            message="Secret in Docker build-arg — extractable via docker history",
                            fix="Use --secret flag or RUN --mount=type=secret instead of build-arg",
                        )
                    )

        return findings
