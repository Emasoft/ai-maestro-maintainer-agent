"""Flag workflows that write to IDE / AI-agent config files.

Port of lib/rules/ide_config_injection.rb. Writing to ``.claude/``,
``.vscode/`` or ``.cursor/`` config from CI can plant code that
auto-executes when a developer next opens the project. Behaviour is 1:1
with the Ruby original.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

WRITE_PATTERN = re.compile(r"(echo|cat|tee|printf|cp|mv|install|sed|>|>>).*\.(claude|vscode|cursor)/")


class IdeConfigInjection(Rule):
    """Workflow writes to IDE/AI agent config files that auto-execute code."""

    name = "ide-config-injection"
    description = "Workflow writes to IDE/AI agent config files that auto-execute code"
    severity = "critical"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list[Finding] = []

        for i, line in enumerate(workflow.raw_lines):
            if line.strip().startswith("#"):
                continue

            if WRITE_PATTERN.search(line):
                findings.append(
                    self.finding(
                        workflow,
                        line=i + 1,
                        code=line.strip(),
                        message="Workflow writes to IDE/AI config files — can execute arbitrary code on project open",
                        fix="Remove IDE config file writes from workflows, or validate content before writing",
                    )
                )

        return findings
