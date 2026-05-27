#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Redact host-specific paths and leftover secrets from agent-authored text.

The maintainer agent must NEVER ship raw user-home paths, absolute repo
paths, or unmasked credentials into a public GitHub artefact (issue
comment, PR body, release notes, commit message). This helper applies an
idempotent substitution map to stdin (or `--file <path>`) and writes the
sanitised text to stdout.

Idempotence is mandatory: running redact.py twice on the same input MUST
produce the same output as one pass. Every regex is anchored so it does
not re-match the placeholder it just inserted.

Usage:
  echo "$BODY" | uv run scripts/redact.py
  uv run scripts/redact.py --file path/to/draft.md
  echo "$BODY" | uv run scripts/redact.py --check   # exit 1 if any sub fires

Substitution map (see skills/maintainer-redact/references/redaction-map.md
for the full rationale).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Rule:
    """One redaction rule. `flags` defaults to 0; set re.IGNORECASE etc. as needed."""

    name: str
    pattern: str
    replacement: str
    flags: int = 0


def _path_rules() -> list[Rule]:
    """Rules that strip absolute host paths.

    The PROJECT_DIR / AGENT_DIR rules consult env vars when available so a
    repo-aware caller (the maintainer agent itself) can additionally
    redact the absolute path of the entrusted repo and the agent's own
    working dir. When the env vars are absent the rules are a no-op.
    """
    rules: list[Rule] = []

    # macOS / Linux / Volume home paths -> $HOME/<rest>
    # The user segment is `[^/]+` (one path component, no slashes). We
    # require the trailing `/` so we only redact ANCHORED home-style
    # paths, never a string that happens to start with "/Users".
    rules.append(
        Rule(
            name="home-mac",
            pattern=r"/Users/[^/\s]+(/[^\s]*)?",
            replacement=r"$HOME\1",
        )
    )
    rules.append(
        Rule(
            name="home-linux",
            pattern=r"/home/[^/\s]+(/[^\s]*)?",
            replacement=r"$HOME\1",
        )
    )
    rules.append(
        Rule(
            name="home-volumes",
            pattern=r"/Volumes/[^/\s]+(/[^\s]*)?",
            replacement=r"$HOME\1",
        )
    )
    # Windows %USERPROFILE%. Two backslashes in the raw string match ONE
    # backslash in the input (the shell escapes them); the replacement
    # uses doubled backslashes so the literal "\\" appears in output.
    rules.append(
        Rule(
            name="home-windows",
            pattern=r"C:\\Users\\[^\\\s]+(\\[^\s]*)?",
            replacement=r"%USERPROFILE%\1",
            flags=re.IGNORECASE,
        )
    )

    # Caller-provided repo paths. These rules run BEFORE the generic home
    # rules above so the more specific override wins; but since they all
    # use unique markers they never collide. Skipped if env unset.
    project_dir = os.environ.get("MAINTAINER_REPO_PATH")
    if project_dir:
        rules.insert(
            0,
            Rule(
                name="project-dir",
                pattern=re.escape(project_dir.rstrip("/")) + r"(/[^\s]*)?",
                replacement=r"$PROJECT_DIR\1",
            ),
        )
    agent_dir = os.environ.get("MAINTAINER_AGENT_PATH")
    if agent_dir:
        rules.insert(
            0,
            Rule(
                name="agent-dir",
                pattern=re.escape(agent_dir.rstrip("/")) + r"(/[^\s]*)?",
                replacement=r"$AGENT_DIR\1",
            ),
        )

    return rules


def _secret_rules() -> list[Rule]:
    """Rules that mask leftover credentials that escaped the secret-scan
    gate. These are belt-and-braces — the secret-scan should have failed
    publish already — but the agent must still scrub before posting.
    """
    return [
        # GitHub personal-access tokens. Exactly 36 chars after ghp_.
        Rule(
            name="github-pat",
            pattern=r"\bghp_[A-Za-z0-9]{36}\b",
            replacement="ghp_<REDACTED>",
        ),
        Rule(
            name="github-oauth",
            pattern=r"\bgho_[A-Za-z0-9]{36}\b",
            replacement="gho_<REDACTED>",
        ),
        Rule(
            name="github-server-token",
            pattern=r"\bghs_[A-Za-z0-9]{36}\b",
            replacement="ghs_<REDACTED>",
        ),
        Rule(
            name="github-user-token",
            pattern=r"\bghu_[A-Za-z0-9]{36}\b",
            replacement="ghu_<REDACTED>",
        ),
        Rule(
            name="github-refresh-token",
            pattern=r"\bghr_[A-Za-z0-9]{36}\b",
            replacement="ghr_<REDACTED>",
        ),
        # Anthropic API keys. Variable suffix length; we anchor on prefix.
        # The audit map specifies `[A-Za-z0-9_-]+` (one-or-more) — Anthropic
        # has shipped keys of varying lengths over time, so the rule does
        # NOT impose a minimum length on the suffix.
        Rule(
            name="anthropic-api-key",
            pattern=r"\bsk-ant-api03-[A-Za-z0-9_\-]+",
            replacement="sk-ant-api03-<REDACTED>",
        ),
        # OpenAI project keys. Same shape: prefix + one-or-more suffix chars.
        Rule(
            name="openai-project-key",
            pattern=r"\bsk-proj-[A-Za-z0-9_\-]+",
            replacement="sk-proj-<REDACTED>",
        ),
        # AWS access-key IDs.
        Rule(
            name="aws-access-key-id",
            pattern=r"\bAKIA[0-9A-Z]{16}\b",
            replacement="AKIA<REDACTED>",
        ),
        # Slack bot / user tokens. Per the audit map, both follow shape
        # `xox[bp]-[0-9-]+-[A-Za-z0-9]+`: a hyphen-separated run of
        # digits, then a final alphanumeric block. The character class
        # `[0-9-]+` matches one numeric segment OR several hyphen-
        # separated numeric segments interchangeably.
        Rule(
            name="slack-bot-token",
            pattern=r"\bxoxb-[0-9\-]+-[A-Za-z0-9]+\b",
            replacement="xoxb-<REDACTED>",
        ),
        Rule(
            name="slack-user-token",
            pattern=r"\bxoxp-[0-9\-]+-[A-Za-z0-9]+\b",
            replacement="xoxp-<REDACTED>",
        ),
        # PEM-encoded private keys. We redact the body, keep the BEGIN
        # marker so the reader knows what was redacted. The pattern
        # is non-greedy to stop at the FIRST -----END line.
        Rule(
            name="pem-private-key",
            pattern=(
                r"-----BEGIN (?P<kind>[A-Z ]*?PRIVATE KEY)-----"
                r".*?-----END (?P=kind)-----"
            ),
            replacement=r"-----BEGIN \g<kind>----- <REDACTED> -----END \g<kind>-----",
            flags=re.DOTALL,
        ),
    ]


def all_rules() -> list[Rule]:
    """Return path rules first, then secret rules.

    Order matters only insofar as path rules never overlap secret rules
    (different prefixes). Within each group, ordering is alphabetical
    by rule name for determinism.
    """
    return _path_rules() + _secret_rules()


def redact(text: str, rules: list[Rule] | None = None) -> tuple[str, list[str]]:
    """Apply every rule to `text`. Return (sanitised_text, rules_fired).

    `rules_fired` is the list of rule names that produced at least one
    substitution. Empty list = nothing to redact.
    """
    if rules is None:
        rules = all_rules()
    fired: list[str] = []
    for rule in rules:
        new_text, count = re.subn(rule.pattern, rule.replacement, text, flags=rule.flags)
        if count > 0:
            fired.append(rule.name)
        text = new_text
    return text, fired


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Reads stdin (default) or --file. Writes redacted text to stdout.
    --check exits non-zero if any rule fired (no output mutation — the
    caller usually re-runs without --check to actually get the sanitised
    text).
    """
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", type=Path, default=None, help="Read input from FILE instead of stdin.")
    ap.add_argument("--check", action="store_true", help="Exit 1 if any redaction would fire; do not modify output.")
    ap.add_argument("--list-rules", action="store_true", help="Print the rule names that would be applied, one per line, then exit.")
    args = ap.parse_args(argv)

    if args.list_rules:
        for r in all_rules():
            print(r.name)
        return 0

    text = args.file.read_text(encoding="utf-8") if args.file else sys.stdin.read()
    sanitised, fired = redact(text)

    if args.check:
        if fired:
            print(f"[redact] would fire: {', '.join(fired)}", file=sys.stderr)
            return 1
        return 0

    sys.stdout.write(sanitised)
    return 0


if __name__ == "__main__":
    sys.exit(main())
