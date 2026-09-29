"""Hardcoded-secret detector.

Port of lib/rules/hardcoded_secrets.rb. Scans every raw line for known
secret/token shapes and for hardcoded passwords, skipping comment lines,
``${{ ... }}`` / ``$ENV`` references, and a small allowlist of common
test/placeholder passwords.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

# label -> compiled pattern (mirrors the Ruby PATTERNS hash, same order).
# Deliberately NOT extended with the GitLab gl*- token families that
# scripts/security_catalog.json carries: this file is a faithful port of the
# Ruby rule and adding families here would silently fork it from upstream.
# Catalog-only families are still caught by fast_security_scan.py.
PATTERNS: dict[str, "re.Pattern[str]"] = {
    "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "GitHub personal access token": re.compile(r"ghp_[A-Za-z0-9]{36}"),
    "GitHub fine-grained PAT": re.compile(r"github_pat_[A-Za-z0-9_]{82}"),
    "GitHub OAuth token": re.compile(r"gho_[A-Za-z0-9]{36}"),
    "GitHub server token": re.compile(r"ghs_[A-Za-z0-9]{36}"),
    "Private key": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    "Slack webhook": re.compile(r"hooks\.slack\.com\/services\/T[A-Z0-9]+\/B[A-Z0-9]+\/[A-Za-z0-9]+"),
    "Generic API key": re.compile(r"(?:api[_-]?key|apikey|secret[_-]?key|auth[_-]?token)\s*[:=]\s*['\"][A-Za-z0-9]{30,}['\"]", re.IGNORECASE),
}

PASSWORD_PATTERN = re.compile(r"password:\s*[^\s${#]+", re.IGNORECASE)
PASSWORD_VALUE_PATTERN = re.compile(r"password:\s*(.+)", re.IGNORECASE)
SAFE_VALUE_PATTERN = re.compile(r"\$\{\{.*\}\}|\$[A-Z_]+")
SAFE_PASSWORDS = ["postgres", "password", "test", "example", "changeme", "admin", "root", "dummy", "placeholder", "true", "false"]


class HardcodedSecrets(Rule):
    """Detects hardcoded secrets, tokens, keys, and passwords in workflows."""

    name = "hardcoded-secrets"
    description = "Hardcoded secret, token, or key in workflow"
    severity = "critical"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list[Finding] = []

        for idx, line in enumerate(workflow.raw_lines):
            line_num = idx + 1
            stripped = line.strip()

            # Skip comment lines
            if stripped.startswith("#"):
                continue

            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(
                        self.finding(
                            workflow,
                            line=line_num,
                            code=stripped,
                            message=f"{label} found hardcoded in workflow",
                            fix="Move to GitHub Actions secrets: ${{ secrets.SECRET_NAME }}",
                        )
                    )

            # Check for hardcoded passwords (skip safe references and common test values)
            if PASSWORD_PATTERN.search(line):
                # Extract the value after password:
                m = PASSWORD_VALUE_PATTERN.search(line)
                value = m.group(1).strip() if m else None
                if value and not SAFE_VALUE_PATTERN.search(value) and not value.startswith("#"):
                    if value.strip().lower() in SAFE_PASSWORDS:
                        continue
                    findings.append(
                        self.finding(
                            workflow,
                            line=line_num,
                            code=stripped,
                            message="Hardcoded password found in workflow",
                            fix="Move to GitHub Actions secrets: ${{ secrets.SECRET_NAME }}",
                        )
                    )

        return findings
