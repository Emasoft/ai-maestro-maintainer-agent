"""Direct GitHub commit/branch reference in a package install.

Port of lib/rules/github_dependency_refs.rb. Installing a dependency
straight from a GitHub ref (``github:owner/repo#sha`` or
``git+https://github.com/...``) bypasses the registry's integrity
checks, so a compromised ref ships unverified code.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

# Each raw_lines element is one line, so no re.MULTILINE is needed.
GITHUB_DEP = re.compile(r"(?:npm|pnpm|yarn|bun)\s+(?:install|add)\s+.*(?:github:|git\+https://github\.com)")


class GithubDependencyRefs(Rule):
    """Flag npm/pnpm/yarn/bun installs that pull a dependency from a GitHub ref."""

    name = "github-dependency-refs"
    description = "Direct GitHub commit/branch reference in package install"
    severity = "medium"

    def check(self, workflow: "Workflow") -> list[Finding]:
        """Flag package-install lines that reference a GitHub commit/branch."""
        findings: list[Finding] = []
        for i, line in enumerate(workflow.raw_lines):
            if line.strip().startswith("#"):
                continue

            if GITHUB_DEP.search(line):
                findings.append(
                    self.finding(
                        workflow,
                        line=i + 1,
                        code=line.strip(),
                        message="Package installed from GitHub commit/branch ref — bypasses registry integrity checks",
                        fix="Install from the package registry instead of GitHub refs",
                    )
                )
        return findings
