"""Shared guard-detection helpers (mixin).

Port of lib/rules/concerns/guard_patterns.rb. Rules that need to know
whether a flagged line sits behind a safe `if:` guard or is reachable
only from safe triggers mix this in alongside ``Rule``:

    class MyRule(Rule, GuardPatterns): ...

The two upward line-walkers reproduce the Ruby indent heuristics exactly,
including the step- vs job-boundary detection.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentinel.workflow import Workflow

# Triggers that an attacker on a fork PR cannot influence.
SAFE_TRIGGERS: list[str] = [
    "workflow_dispatch",
    "schedule",
    "push",
    "workflow_call",
    "release",
    "deployment",
    "deployment_status",
    "create",
    "delete",
    "page_build",
    "watch",
    "fork",
    "star",
    "gollum",
]

# Reserved job-level keys — used to tell a job key from a job *property*.
JOB_PROPERTIES: list[str] = [
    "steps",
    "runs-on",
    "env",
    "strategy",
    "permissions",
    "outputs",
    "concurrency",
    "services",
    "needs",
    "container",
    "timeout-minutes",
    "if",
    "name",
    "defaults",
]

# Attacker-controllable expression contexts.
DANGEROUS_CONTEXTS: list[str] = [
    "github.event.pull_request.title",
    "github.event.pull_request.body",
    "github.event.pull_request.head.ref",
    "github.event.pull_request.head.label",
    "github.event.issue.title",
    "github.event.issue.body",
    "github.event.comment.body",
    "github.event.review.body",
    "github.event.discussion.title",
    "github.event.discussion.body",
    "github.event.workflow_run.head_branch",
    "github.head_ref",
]


def _indent(line: str) -> int:
    """Length of the leading-whitespace run (Ruby line[/^\\s*/].length)."""
    m = re.match(r"[ \t]*", line)
    return len(m.group(0)) if m else 0


class GuardPatterns:
    """Mixin: trigger-safety + `if:`-guard detection over raw workflow lines."""

    def safe_trigger_only(self, workflow: "Workflow") -> bool:
        """True iff every workflow trigger is in SAFE_TRIGGERS (and there's ≥1)."""
        t = workflow.triggers()
        if isinstance(t, dict):
            names = [str(k) for k in t.keys()]
        elif isinstance(t, list):
            names = [str(x) for x in t]
        elif isinstance(t, str):
            names = [t]
        else:
            names = []
        return bool(names) and all(n in SAFE_TRIGGERS for n in names)

    def guarded_by_safe_event(self, workflow: "Workflow", line_num: int) -> bool:
        """True iff the line is guarded by a safe step- or job-level `if:`."""
        return self._guarded_by_step_if(workflow, line_num) or self._guarded_by_job_if(workflow, line_num)

    def strip_inline_comment(self, line: str) -> str:
        """Strip a trailing `# comment`, respecting single/double quotes."""
        in_single = False
        in_double = False
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double
            elif ch == "#" and not in_single and not in_double:
                # Only strip when preceded by whitespace (or at line start).
                if i == 0 or re.match(r"\s", line[i - 1]):
                    return line[:i].rstrip()
            i += 1
        return line

    # -- private upward line-walkers ---------------------------------------

    def _guarded_by_step_if(self, workflow: "Workflow", line_num: int) -> bool:
        """Walk up to 30 lines looking for a step-level `if:` guard, stopping
        at a step boundary (`- ` at step indent) or a shallow job key."""
        lower = max(line_num - 30, 0)
        for i in range(line_num - 2, lower - 1, -1):
            if i < 0 or i >= len(workflow.raw_lines):
                continue
            content = workflow.raw_lines[i]

            if re.match(r"^\s+if:\s*", content):
                m = re.search(r"if:\s*(.+)", content)
                condition = m.group(1).strip() if m else None
                if condition:
                    return self._safe_guard_condition(condition)

            if re.match(r"^\s+-\s+\S", content):
                # The dash line itself may carry the guard: `- if: ...`.
                if re.match(r"^\s+-\s+if:\s*", content):
                    m = re.search(r"if:\s*(.+)", content)
                    condition = m.group(1).strip() if m else None
                    if condition:
                        return self._safe_guard_condition(condition)
                break

            # A job-level key (no dash, shallow indent) means we left the step.
            if re.match(r"^\s+\w[\w-]*:", content) and not re.match(r"^\s+-", content):
                if _indent(content) <= 6:
                    break

        return False

    def _guarded_by_job_if(self, workflow: "Workflow", line_num: int) -> bool:
        """Walk up looking for a job-level `if:` guard, stopping at `jobs:` or
        when crossing into a different job."""
        job_keys_seen = 0
        enclosing_job_line: int | None = None

        for i in range(line_num - 2, -1, -1):
            if i < 0 or i >= len(workflow.raw_lines):
                continue
            content = workflow.raw_lines[i]

            # `jobs:` — gone too far without finding a job-level if:.
            if re.match(r"^jobs:\s*$", content):
                return False

            m_key = re.match(r"^\s+(\w[\w-]*):\s*$", content)
            if m_key:
                key_name = m_key.group(1)
                key_indent = _indent(content)
                if key_indent <= 4 and key_name not in JOB_PROPERTIES:
                    job_keys_seen += 1
                    if job_keys_seen == 1:
                        enclosing_job_line = i
                    if job_keys_seen > 1:
                        return False

            if re.match(r"^\s+if:\s*", content):
                if_indent = _indent(content)
                lower2 = max(i - 15, 0)
                for j in range(i - 1, lower2 - 1, -1):
                    if j < 0 or j >= len(workflow.raw_lines):
                        continue
                    above = workflow.raw_lines[j]
                    if re.match(r"^\s+\w[\w-]*:\s*$", above):
                        above_indent = _indent(above)
                        if if_indent == above_indent + 2 and (enclosing_job_line is None or j == enclosing_job_line):
                            m = re.search(r"if:\s*(.+)", content)
                            condition = m.group(1).strip() if m else None
                            if condition:
                                return self._safe_guard_condition(condition)
                        break

            # `steps:` — passing from steps into job-level territory.
            if re.match(r"^\s+steps:\s*$", content):
                continue

        return False

    def _safe_guard_condition(self, condition: str) -> bool:
        """True iff a simple `if:` clearly restricts to a safe trigger."""
        condition = re.sub(r"\$\{\{\s*", "", condition)
        condition = re.sub(r"\s*\}\}", "", condition).strip()

        # Reject complex boolean expressions — can't reason about them simply.
        if re.search(r"(\|\||&&|always\s*\(|failure\s*\(|cancelled\s*\()", condition):
            return False

        m = re.match(r"\Agithub\.event_name\s*==\s*['\"](\w+)['\"]\Z", condition)
        if m:
            return m.group(1) in SAFE_TRIGGERS

        return False
