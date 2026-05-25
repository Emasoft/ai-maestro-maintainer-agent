"""SARIF 2.1.0 formatter for the GitHub Security tab. Port of lib/formatter/sarif.rb."""

from __future__ import annotations

import json as _json

from sentinel import VERSION
from sentinel.finding import Finding


def _sarif_level(severity: str) -> str:
    """Map a finding severity to a SARIF result level."""
    if severity in ("critical", "high"):
        return "error"
    if severity == "medium":
        return "warning"
    if severity == "low":
        return "note"
    return "none"


def _build_uri(finding: Finding) -> str:
    """Resolve a finding's file to a repo-relative SARIF artifact URI."""
    file = finding.file
    if "/" in file or file == "(missing)":
        return file
    if file == "dependabot.yml":
        return f".github/{file}"
    return f".github/workflows/{file}"


class Sarif:
    """SARIF 2.1.0 report (one run, rules de-duplicated by id)."""

    def format(self, *, repo: str, workflow_count: int, findings: list[Finding]) -> str:
        """Serialize findings as a SARIF 2.1.0 document."""
        ordered = sorted(findings)
        sarif = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "sentinel",
                            "informationUri": "https://sentinel.copilotkit.dev",
                            "version": VERSION,
                            "rules": self._build_rules(ordered),
                        }
                    },
                    "results": [self._build_result(f) for f in ordered],
                }
            ],
        }
        return _json.dumps(sarif, indent=2)

    def _build_rules(self, findings: list[Finding]) -> list[dict[str, object]]:
        seen: list[str] = []
        for f in findings:
            if f.rule not in seen:
                seen.append(f.rule)
        rules: list[dict[str, object]] = []
        for rule_id in seen:
            first = next(f for f in findings if f.rule == rule_id)
            rules.append(
                {
                    "id": rule_id,
                    "shortDescription": {"text": rule_id},
                    "defaultConfiguration": {"level": _sarif_level(first.severity)},
                }
            )
        return rules

    def _build_result(self, finding: Finding) -> dict[str, object]:
        text = f"{finding.message}. Fix: {finding.fix}" if finding.fix else finding.message
        return {
            "ruleId": finding.rule,
            "level": _sarif_level(finding.severity),
            "message": {"text": text},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": _build_uri(finding), "uriBaseId": "%SRCROOT%"},
                        "region": {"startLine": max(finding.line, 1)},
                    }
                }
            ],
        }
