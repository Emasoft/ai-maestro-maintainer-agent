"""Remote-script-piped-to-shell detector.

Port of lib/rules/curl_pipe_shell.rb. Flags installs that pipe a freshly
downloaded remote script straight into a shell interpreter (the
curl-pipe / wget-pipe install footgun) with no integrity verification.
The literal pipeline shapes live ONLY in _PIPE_SHELL_SOURCES below —
container-literal pattern data, never executed. Keep them out of this
docstring: prose carrying the executable shape trips security scanners
(CPV RC-136/RC-137) even though it is documentation.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

# The detector regex SOURCES live in a module-level pure-literal CONTAINER
# (a tuple). A pipe-to-shell shape is intrinsic to what this rule detects, so
# the source unavoidably contains `| sh`. CPV skillaudit (Issue #39/#41)
# recognises a match inside a module-level container literal as pattern data —
# never an executed payload — so the faithful regex stays readable instead of
# being obfuscated. (A bare `X = "..."` would NOT qualify; only container
# literals do.)
_PIPE_SHELL_SOURCES: tuple[str, str] = (
    r"curl\s.*\|\s*(sudo\s+)?(sh|bash|zsh|source|\.)",
    r"wget\s.*-O\s*-\s*\|\s*(sudo\s+)?(sh|bash|zsh)",
)
PIPE_PATTERN = re.compile(_PIPE_SHELL_SOURCES[0])
WGET_PIPE = re.compile(_PIPE_SHELL_SOURCES[1])


class CurlPipeShell(Rule):
    """Detects remote scripts piped directly into a shell interpreter."""

    name = "curl-pipe-shell"
    description = "Remote script piped directly to shell without integrity check"
    severity = "high"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list[Finding] = []

        for i, line in enumerate(workflow.raw_lines):
            if line.strip().startswith("#"):
                continue

            if PIPE_PATTERN.search(line) or WGET_PIPE.search(line):
                findings.append(
                    self.finding(
                        workflow,
                        line=i + 1,
                        code=line.strip(),
                        message="Remote script piped to shell — no integrity verification, mutable endpoint",
                        fix="Download first, verify checksum, then execute; or use a pinned GitHub Action instead",
                    )
                )

        return findings
