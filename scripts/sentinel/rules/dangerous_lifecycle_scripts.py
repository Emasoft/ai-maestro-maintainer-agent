"""Flag package installs that run lifecycle scripts when secrets are present.

Port of lib/rules/dangerous_lifecycle_scripts.rb. Only fires when the
workflow references ``${{ secrets. }}`` — a compromised dependency's
postinstall hook can then read those credentials unless the install
ran with ``--ignore-scripts``. Behaviour is 1:1 with the Ruby original.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

INSTALL_CMDS: list[dict[str, Any]] = [
    {"match": re.compile(r"\bnpm\s+(install|ci)\b"), "safe": re.compile(r"--ignore-scripts"), "name": "npm"},
    {"match": re.compile(r"\bpnpm\s+install\b"), "safe": re.compile(r"--ignore-scripts"), "name": "pnpm"},
    {"match": re.compile(r"\byarn\s+install\b"), "safe": re.compile(r"--ignore-scripts"), "name": "yarn"},
    {"match": re.compile(r"\bbun\s+install\b"), "safe": re.compile(r"--ignore-scripts|--no-scripts"), "name": "bun"},
]

# Secrets reference that gates the whole rule.
_SECRETS_PATTERN = re.compile(r"\$\{\{\s*secrets\.")


class DangerousLifecycleScripts(Rule):
    """Package install without --ignore-scripts in workflow with secrets."""

    name = "dangerous-lifecycle-scripts"
    description = "Package install without --ignore-scripts in workflow with secrets"
    severity = "medium"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        if not self._workflow_has_secrets(workflow):
            return []

        findings: list[Finding] = []

        for i, line in enumerate(workflow.raw_lines):
            if line.strip().startswith("#"):
                continue

            for cmd in INSTALL_CMDS:
                if not cmd["match"].search(line):
                    continue
                if cmd["safe"].search(line):
                    continue

                findings.append(
                    self.finding(
                        workflow,
                        line=i + 1,
                        code=line.strip(),
                        message=f"{cmd['name']} install runs lifecycle scripts in a workflow with secrets — a compromised dependency can read the credentials in the job environment",
                        fix=f"Add --ignore-scripts, then explicitly rebuild trusted native deps: {cmd['name']} rebuild sharp esbuild",
                    )
                )

        return findings

    def _workflow_has_secrets(self, workflow: "Workflow") -> bool:
        return bool(_SECRETS_PATTERN.search(workflow.raw))
