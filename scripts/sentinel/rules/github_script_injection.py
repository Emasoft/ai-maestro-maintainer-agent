"""github-script JavaScript-injection detector.

Port of lib/rules/github_script_injection.rb. Flags an attacker-controllable
``${{ ... }}`` context interpolated inside an ``actions/github-script``
``script:`` block, unless the workflow is safe-triggered or the line sits
behind a safe ``if:`` guard.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule
from sentinel.rules.guard_patterns import DANGEROUS_CONTEXTS, GuardPatterns

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

PATTERN = re.compile(r"\$\{\{\s*(" + "|".join(re.escape(c) for c in DANGEROUS_CONTEXTS) + ")")


class GithubScriptInjection(Rule, GuardPatterns):
    """Detects attacker-controllable expressions in actions/github-script blocks."""

    name = "github-script-injection"
    description = "Attacker-controllable ${{ }} expression in actions/github-script"
    severity = "critical"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list[Finding] = []

        if self.safe_trigger_only(workflow):
            return []

        for idx, line in enumerate(workflow.raw_lines):
            line_num = idx + 1
            if line.strip().startswith("#"):
                continue
            if not PATTERN.search(line):
                continue
            if not self._in_github_script_block(workflow, line_num):
                continue
            if self.guarded_by_safe_event(workflow, line_num):
                continue

            match = PATTERN.search(line)
            if not match:
                continue

            findings.append(
                self.finding(
                    workflow,
                    line=line_num,
                    code=line.strip(),
                    message=f"Attacker-controllable expression ${{{{ {match.group(1)} }}}} in actions/github-script — JavaScript injection risk",
                    fix="Use context.payload instead: context.payload.pull_request.title",
                )
            )

        return findings

    def _in_github_script_block(self, workflow: "Workflow", target_line: int) -> bool:
        lower = max(target_line - 30, 0)
        for i in range(target_line - 1, lower - 1, -1):
            if i < 0 or i >= len(workflow.raw_lines):
                continue
            content = workflow.raw_lines[i]

            if re.search(r"^\s+script:\s*[|>]?\s*$", content) or re.search(r"^\s+script:\s+\S", content):
                lower2 = max(i - 15, 0)
                for j in range(i, lower2 - 1, -1):
                    if j < 0 or j >= len(workflow.raw_lines):
                        continue
                    step_line = workflow.raw_lines[j]
                    if re.search(r"uses:\s*actions\/github-script", step_line):
                        return True
                    if re.search(r"^\s+-\s+(name|uses|run|if|id):", step_line):
                        break
                return False

            if re.search(r"^\s+(uses|run|if|id|name|env|with):", content) or re.search(r"^\s+-\s+(name|uses|run):", content):
                return False

        return False
