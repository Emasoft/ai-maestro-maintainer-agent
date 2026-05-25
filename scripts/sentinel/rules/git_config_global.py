"""Flag `git config --global` writes that persist credentials.

Port of lib/rules/git_config_global.rb. Only the credential-bearing forms
(insteadOf / url. rewrites / credential helpers) are flagged — a global
``user.name`` is benign. Behaviour is 1:1 with the Ruby original.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

_GLOBAL_PATTERN = re.compile(r"git config --global")
_CREDENTIAL_PATTERN = re.compile(r"insteadOf|url\.|credential")


class GitConfigGlobal(Rule):
    """git config --global persists credentials beyond the repo clone."""

    name = "git-config-global"
    description = "git config --global persists credentials beyond the repo clone"
    severity = "low"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list[Finding] = []

        for line_num in workflow.lines_of(_GLOBAL_PATTERN):
            line = workflow.line_content(line_num)
            if not (line and _CREDENTIAL_PATTERN.search(line)):
                continue

            findings.append(
                self.finding(
                    workflow,
                    line=line_num,
                    code=line.strip(),
                    message="git config --global writes credentials to ~/.gitconfig — accessible to all subsequent git operations",
                    fix="Use --local instead of --global to scope to the repo clone",
                )
            )

        return findings
