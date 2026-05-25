r"""Flag jq --arg values containing backslash escape sequences.

Port of lib/rules/jq_arg_escape.rb. jq treats ``--arg`` values as raw
literals, so ``\n`` / ``\t`` / ``\\`` are passed through verbatim instead
of being interpreted — usually a bug. Behaviour is 1:1 with the Ruby
original.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

PATTERN = re.compile(r'jq\s.*--arg\s+\w+\s+"[^"]*\\[nt\\][^"]*"')


class JqArgEscape(Rule):
    """jq --arg value contains backslash escape sequences that won't be interpreted."""

    name = "jq-arg-escape-sequences"
    description = "jq --arg value contains backslash escape sequences that won't be interpreted"
    severity = "medium"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list[Finding] = []

        for i, line in enumerate(workflow.raw_lines):
            if line.strip().startswith("#"):
                continue
            if not PATTERN.search(line):
                continue

            findings.append(
                self.finding(
                    workflow,
                    line=i + 1,
                    code=line.strip(),
                    message="jq --arg treats values as raw literals — \\n becomes literal backslash-n, not a newline",
                    fix="Use real newlines via $'\\n' or multi-line variable, or use --argjson with pre-escaped JSON",
                )
            )

        return findings
