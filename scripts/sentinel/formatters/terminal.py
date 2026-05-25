"""Coloured terminal formatter. Port of lib/formatter/terminal.rb."""

from __future__ import annotations

from sentinel.finding import SEVERITIES, Finding

_COLORS = {
    "critical": "\033[31m",  # red
    "high": "\033[33m",  # yellow
    "medium": "\033[36m",  # cyan
    "low": "\033[90m",  # dim
    "reset": "\033[0m",
    "bold": "\033[1m",
    "green": "\033[32m",
}


def _c(name: str) -> str:
    """ANSI code for a colour name, or '' when unknown."""
    return _COLORS.get(name, "")


class Terminal:
    """Human-readable coloured report."""

    def format(self, *, repo: str, workflow_count: int, findings: list[Finding]) -> str:
        """Render the findings block with a per-severity summary line."""
        lines: list[str] = []
        lines.append("")
        lines.append(f"{_c('bold')}=== {repo} ({workflow_count} workflows) ==={_c('reset')}")
        lines.append("")

        if not findings:
            lines.append(f"  {_c('green')}No findings.{_c('reset')}")
        else:
            for f in sorted(findings):
                sev = f.severity.upper().ljust(10)
                lines.append(f"  {_c(f.severity)}{sev}{_c('reset')} {_c('bold')}{f.rule}{_c('reset')}  {f.file}:{f.line}")
                lines.append(f"            {f.message}")
                if f.fix:
                    lines.append(f"            {_c('green')}Fix: {f.fix}{_c('reset')}")
                lines.append("")

            parts = []
            for s in SEVERITIES:
                count = sum(1 for f in findings if f.severity == s)
                if count:
                    parts.append(f"{_c(s)}{count} {s}{_c('reset')}")
            summary = ", ".join(parts)
            lines.append(f"  --- Summary: {summary} ---")

        lines.append("")
        return "\n".join(lines)
