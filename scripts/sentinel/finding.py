"""Finding data structure + severity ordering.

Port of lib/finding.rb. Severity is a lowercase string (Ruby used a
symbol; `.to_s` gives the same wire value). Findings sort by severity
rank only — Python's stable sort preserves rule-execution order within a
severity band, matching the Ruby engine's intent.
"""

from __future__ import annotations

from dataclasses import dataclass

# Ordered most-severe first; index == rank.
SEVERITIES: tuple[str, ...] = ("critical", "high", "medium", "low")
SEVERITY_ORDER: dict[str, int] = {s: i for i, s in enumerate(SEVERITIES)}


@dataclass
class Finding:
    """One security finding. Mirrors the Ruby Finding struct fields exactly."""

    rule: str
    severity: str
    file: str
    line: int
    code: str | None = None
    message: str | None = None
    fix: str | None = None

    @property
    def severity_rank(self) -> int:
        """Numeric rank for sorting; unknown severities sort last."""
        return SEVERITY_ORDER.get(self.severity, 99)

    def __lt__(self, other: "Finding") -> bool:
        """Order by severity rank only (critical < high < medium < low)."""
        return self.severity_rank < other.severity_rank

    def is_critical(self) -> bool:
        """True iff this finding is critical severity."""
        return self.severity == "critical"

    def is_high(self) -> bool:
        """True iff this finding is high severity."""
        return self.severity == "high"

    def is_medium(self) -> bool:
        """True iff this finding is medium severity."""
        return self.severity == "medium"

    def is_low(self) -> bool:
        """True iff this finding is low severity."""
        return self.severity == "low"

    def to_dict(self) -> dict[str, object]:
        """Serialize to the JSON wire shape used by the json/sarif formatters."""
        return {
            "rule": self.rule,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "code": self.code,
            "message": self.message,
            "fix": self.fix,
        }
