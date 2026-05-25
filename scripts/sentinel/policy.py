"""Policy-as-code engine for `.sentinel-ci.yml`.

Port of lib/policy.rb. Supports a minimum severity, per-rule severity
overrides (including ``off``), file ignore globs, and findings exceptions
(which must carry a ``reason`` — no silent suppressions). Malformed config
populates ``errors`` rather than raising.
"""

from __future__ import annotations

import fnmatch
import os
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from sentinel.finding import Finding

KNOWN_TOP_KEYS = ["severity", "rules", "policy", "ignore", "exceptions"]
KNOWN_POLICY_KEYS = ["require", "recommend"]
_VALID_SEVERITIES = ("critical", "high", "medium", "low")


class Policy:
    """Reads + validates a `.sentinel-ci.yml`; applied by the Scanner."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path
        self.config: dict[str, Any] = {}
        self.errors: list[str] = []
        if path and os.path.exists(path):
            self._load_config()

    def loaded(self) -> bool:
        """True iff a non-empty config was loaded."""
        return bool(self.config)

    def min_severity(self) -> str:
        """Configured minimum severity, defaulting to 'low'."""
        sev = self.config.get("severity")
        return str(sev) if sev else "low"

    def rule_severity(self, rule_name: str) -> str | None:
        """Override severity for a rule: a severity string, 'off', or None."""
        rules = self.config.get("rules") or {}
        if rule_name not in rules:
            return None
        override = rules[rule_name]
        # YAML parses a bare `off` as boolean False.
        if override is False or str(override) == "off":
            return "off"
        return str(override)

    def ignored(self, filename: str) -> bool:
        """True iff `filename` matches any ignore glob."""
        patterns = self.config.get("ignore") or []
        return any(fnmatch.fnmatch(filename, pat) for pat in patterns)

    def excepted(self, finding: "Finding") -> bool:
        """True iff an exception entry waives this finding (rule [+ file])."""
        exceptions = self.config.get("exceptions") or []
        return any(isinstance(ex, dict) and ex.get("rule") == finding.rule and (ex.get("file") is None or ex.get("file") == finding.file) for ex in exceptions)

    def required_policies(self) -> list[Any]:
        """The `policy.require` list (empty when unset)."""
        policy = self.config.get("policy")
        return (policy.get("require") or []) if isinstance(policy, dict) else []

    def recommended_policies(self) -> list[Any]:
        """The `policy.recommend` list (empty when unset)."""
        policy = self.config.get("policy")
        return (policy.get("recommend") or []) if isinstance(policy, dict) else []

    # -- loading + validation ----------------------------------------------

    def _load_config(self) -> None:
        try:
            with open(self.path) as fh:  # type: ignore[arg-type]
                raw = yaml.safe_load(fh.read())
        except yaml.YAMLError as exc:
            self.errors.append(f"{self.path}: YAML syntax error: {exc}")
            return
        if not isinstance(raw, dict):
            self.errors.append(f"{self.path}: expected a YAML mapping, got {type(raw).__name__}")
            return
        self.config = raw
        self._validate()

    def _validate(self) -> None:
        for key in self.config.keys():
            if key not in KNOWN_TOP_KEYS:
                self.errors.append(f"Unknown key '{key}' in {self.path}")

        if self.config.get("severity"):
            if str(self.config["severity"]) not in _VALID_SEVERITIES:
                self.errors.append(f"Invalid severity '{self.config['severity']}' — must be critical, high, medium, or low")

        rules = self.config.get("rules")
        if rules:
            known = self._load_known_rules()
            for rule, val in rules.items():
                if rule not in known:
                    self.errors.append(f"Unknown rule '{rule}' in rules section")
                normalized = "off" if val is False else str(val)
                if normalized not in (*_VALID_SEVERITIES, "off"):
                    self.errors.append(f"Invalid severity '{val}' for rule '{rule}' — must be critical, high, medium, low, or off")

        policy = self.config.get("policy")
        if isinstance(policy, dict):
            for key in policy.keys():
                if key not in KNOWN_POLICY_KEYS:
                    self.errors.append(f"Unknown key '{key}' in policy section")

        for i, ex in enumerate(self.config.get("exceptions") or []):
            if not (isinstance(ex, dict) and ex.get("rule")):
                self.errors.append(f"Exception #{i + 1} missing required 'rule' field")
            if not (isinstance(ex, dict) and ex.get("reason")):
                self.errors.append(f"Exception #{i + 1} missing required 'reason' field — no silent suppressions")

    def _load_known_rules(self) -> list[str]:
        # Importing the rules package populates Rule.registry via auto-discovery.
        from sentinel.rules.base import Rule

        names = [cls.name for cls in Rule.registry]
        return names + ["missing-dependabot", "missing-zizmor"]
