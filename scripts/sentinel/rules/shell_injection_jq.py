"""Shell-injection-via-jq/curl-argument detector.

Port of lib/rules/shell_injection_jq.rb. Flags an attacker-controllable
shell variable interpolated inside a double-quoted jq ``--arg`` value or a
double-quoted ``curl -d`` JSON payload, where bash command substitution
``$(...)`` could fire — unless the workflow is safe-triggered or guarded.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule
from sentinel.rules.guard_patterns import GuardPatterns

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

ATTACKER_ENV_VARS = ["PR_TITLE", "PR_BODY", "PR_AUTHOR", "HEAD_REF", "ISSUE_TITLE", "ISSUE_BODY", "COMMENT_BODY", "PR_HEAD_REF", "BRANCH_NAME"]

# `[a-zA-Z\s-]*` is a FLAT character class (no nested quantifier) so the
# optional-flags prefix cannot cause catastrophic backtracking — the old
# `([a-zA-Z-]+\s+)*` form was ReDoS-prone.
JQ_PATTERN = re.compile(r'jq\s+[a-zA-Z\s-]*--arg\s+\w+\s+"[^"]*\$\{')
CURL_JSON_PATTERN = re.compile(r'curl\s.*-d\s+"[^"]*\$\{')
VAR_PATTERN = re.compile(r"\$\{(\w+)\}")
ATTACKER_NAME_PATTERN = re.compile(r"^(PR_|ISSUE_|COMMENT_)?(TITLE|BODY|HEAD_REF|BRANCH_NAME|COMMENT_BODY|AUTHOR)$", re.IGNORECASE)


class ShellInjectionJq(Rule, GuardPatterns):
    """Detects attacker-controllable vars interpolated into jq/curl JSON args."""

    name = "shell-injection-jq"
    description = "Shell variable interpolated in double-quoted jq/curl JSON argument"
    severity = "critical"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list[Finding] = []

        if self.safe_trigger_only(workflow):
            return []

        for i, line in enumerate(workflow.raw_lines):
            line_num = i + 1
            if line.strip().startswith("#"):
                continue
            if not self._in_run_block(workflow, line_num):
                continue
            if self.guarded_by_safe_event(workflow, line_num):
                continue

            if JQ_PATTERN.search(line):
                var_match = VAR_PATTERN.search(line)
                if not var_match:
                    continue
                var_name = var_match.group(1)
                if not self._potentially_attacker_controlled(var_name):
                    continue

                findings.append(
                    self.finding(
                        workflow,
                        line=line_num,
                        code=line.strip(),
                        message=f"${{{var_name}}} interpolated in double-quoted jq argument — $(command) executes via bash substitution",
                        fix=f"Use jq --arg: jq -nc --arg {var_name.lower()} \"${var_name}\" '{{text: ${var_name.lower()}}}'",
                    )
                )

            if CURL_JSON_PATTERN.search(line):
                var_match = VAR_PATTERN.search(line)
                if not var_match:
                    continue
                var_name = var_match.group(1)
                if not self._potentially_attacker_controlled(var_name):
                    continue

                findings.append(
                    self.finding(
                        workflow,
                        line=line_num,
                        code=line.strip(),
                        message=f"${{{var_name}}} interpolated in double-quoted curl JSON — command substitution risk",
                        fix="Build JSON payload with jq -nc --arg instead of string interpolation",
                    )
                )

        return findings

    def _in_run_block(self, workflow: "Workflow", target_line: int) -> bool:
        target_content = workflow.raw_lines[target_line - 1] if target_line - 1 < len(workflow.raw_lines) else None
        m_indent = re.match(r"^\s*", target_content) if target_content else None
        target_indent = len(m_indent.group(0)) if m_indent else 0

        lower = max(target_line - 20, 0)
        for i in range(target_line - 1, lower - 1, -1):
            if i < 0 or i >= len(workflow.raw_lines):
                continue
            content = workflow.raw_lines[i]

            if re.search(r"^\s+run:\s*[|>]?\s*$", content) or re.search(r"^\s+run:\s+\S", content):
                return True
            if re.search(r"^\s+-\s+run:\s*[|>]?\s*$", content) or re.search(r"^\s+-\s+run:\s+\S", content):
                return True

            if re.search(r"^\s+(uses|with|if|id|name|env):", content) or re.search(r"^\s+-\s+name:", content):
                m = re.match(r"^\s*", content)
                line_indent = len(m.group(0)) if m else 0
                if target_indent <= line_indent + 2:
                    return False
        return False

    def _potentially_attacker_controlled(self, var_name: str) -> bool:
        return any(var_name.upper() == v for v in ATTACKER_ENV_VARS) or bool(ATTACKER_NAME_PATTERN.search(var_name))
