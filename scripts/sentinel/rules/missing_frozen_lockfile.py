"""Flag package installs that bypass lockfile enforcement.

Port of lib/rules/missing_frozen_lockfile.rb. Walks every raw line (so
multi-line ``run:`` blocks are covered), skips comment lines, and for each
package manager flags an install command unless a "safe" flag (or, for pip,
a local-install form) is present. Behaviour is 1:1 with the Ruby original.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from sentinel.rules.base import Rule

if TYPE_CHECKING:
    from sentinel.finding import Finding
    from sentinel.workflow import Workflow

# JavaScript/TypeScript
NPM_INSTALL = re.compile(r"\bnpm\s+install\b")
NPM_SAFE = re.compile(r"--ci\b|\bnpm\s+ci\b")
# A global install (`npm install -g <tool>`) installs a CLI tool, not project
# dependencies — `npm ci` (which reads package-lock.json into node_modules) does
# not apply, and such tools are usually version-pinned anyway
# (`npm install -g npm@11.12.0` in astral-sh/ruff). The "use npm ci" premise is
# false, so a global install must not be flagged.
NPM_GLOBAL = re.compile(r"\s-g(?=\s|$)|--global\b")

PNPM_INSTALL = re.compile(r"\bpnpm\s+install\b")
PNPM_SAFE = re.compile(r"--frozen-lockfile")

YARN_INSTALL = re.compile(r"\byarn\s+install\b")
YARN_SAFE = re.compile(r"--frozen-lockfile|--immutable")

BUN_INSTALL = re.compile(r"\bbun\s+install\b")
BUN_SAFE = re.compile(r"--frozen-lockfile")

# Python
PIP_INSTALL = re.compile(r"\b(?:pip3?|uv\s+pip)\s+install\b")
PIP_SAFE = re.compile(r"-r\b|--requirement\b|-c\b|--constraint\b|--require-hashes")
# Install forms that do NOT fetch unpinned deps from a package index, so the
# "unpinned packages" premise is false:
#   --no-index ........ registry disabled (installs only from local --find-links)
#   -e / --editable ... editable install of a local path
#   *.whl / *.tar.gz .. a specific local (or fixed-URL) wheel / sdist artifact
#   . / .[extra] / ./x  current-dir or relative-path install
PIP_LOCAL = re.compile(
    r"--no-index"
    r"|(?:\s-e\b|--editable\b)"
    r"|\.(?:whl|tar\.gz|tgz|zip|tar\.bz2)(?:\b|$)"
    r"|\binstall\s+(?:-e\s+)?\.(?:\s|$|\[|/)"
)
# Bootstrapping the packaging toolchain (`pip install -U pip`,
# `pip install --upgrade pip setuptools wheel`, `.venv/bin/pip install --upgrade
# pip;`) is not a project-dependency install — the rule's remedy
# (`-r requirements.txt --require-hashes`) is inapplicable to upgrading pip
# itself, so flagging it is noise. Matches `install [-U|--upgrade] <tool>...`
# only when EVERY target is a packaging tool and nothing else follows (a real
# package alongside pip, e.g. `pip install -U pip mypkg`, still fails to match
# and is flagged). astral-sh/uv build-release-binaries.yml has ~13 of these.
# `(?:[=<>!~][^\s;#&|]*)?` tolerates a version pin on a tool so a pinned
# toolchain install (`pip install build==1.4.0`, `pip install pip==26.0.1` in
# psf/requests) is exempted just like the unpinned `pip install -U pip` form —
# installing the packaging toolchain is never the project-dependency install the
# rule targets, pinned or not.
_BOOT_TOOL = r"(?:pip|setuptools|wheel|build|uv|virtualenv|pip-tools)(?:[=<>!~][^\s;#&|]*)?"
PIP_BOOTSTRAP = re.compile(
    r"\binstall\s+(?:(?:-U|--upgrade)\s+)?"
    + _BOOT_TOOL
    + r"(?:\s+"
    + _BOOT_TOOL
    + r")*\s*(?:[;#&|]|$)"
)

# Ruby
BUNDLE_INSTALL = re.compile(r"\bbundle\b(?:\s+install\b)?")
BUNDLE_SAFE = re.compile(r"--frozen|--deployment|BUNDLE_FROZEN\s*=\s*(?:true|1)")
BUNDLE_OTHER = re.compile(r"\bbundle\s+(?:exec|add|update|show|list|info|outdated|check|config|lock|cache|clean|console|open|gem|platform|env|doctor|viz|version|init|binstubs|pristine|plugin)\b")

# Go
GO_GET = re.compile(r"\bgo\s+get\b")

# Rust
CARGO_INSTALL = re.compile(r"\bcargo\s+install\b")
CARGO_SAFE = re.compile(r"--locked")

# PHP
COMPOSER_UPDATE = re.compile(r"\bcomposer\s+update\b")

CHECKS: list[dict[str, Any]] = [
    {
        "match": NPM_INSTALL,
        "safe": NPM_SAFE,
        "safe_alt": NPM_GLOBAL,
        "message": "npm install without lockfile enforcement — dependency resolution may differ from tested versions",
        "fix": "Use `npm ci` instead of `npm install`",
    },
    {
        "match": PNPM_INSTALL,
        "safe": PNPM_SAFE,
        "message": "pnpm install without --frozen-lockfile — dependency resolution may differ from tested versions",
        "fix": "Use `pnpm install --frozen-lockfile`",
    },
    {
        "match": YARN_INSTALL,
        "safe": YARN_SAFE,
        "message": "yarn install without lockfile enforcement — dependency resolution may differ from tested versions",
        "fix": "Use `yarn install --frozen-lockfile` or `yarn install --immutable`",
    },
    {
        "match": BUN_INSTALL,
        "safe": BUN_SAFE,
        "message": "bun install without --frozen-lockfile — dependency resolution may differ from tested versions",
        "fix": "Use `bun install --frozen-lockfile`",
    },
    {
        "match": PIP_INSTALL,
        "safe": PIP_SAFE,
        "safe_alt": PIP_LOCAL,
        "safe_alt2": PIP_BOOTSTRAP,
        "message": "pip install with unpinned packages — no lockfile or constraints file ensuring reproducibility",
        "fix": "Use `pip install -r requirements.txt --require-hashes` or a constraints file",
    },
    {
        "match": BUNDLE_INSTALL,
        "safe": BUNDLE_SAFE,
        "skip": BUNDLE_OTHER,
        "message": "bundle install without --frozen — Gemfile.lock may be modified during install",
        "fix": "Use `bundle install --frozen` or `bundle install --deployment`",
    },
    {
        "match": GO_GET,
        "message": "go get in CI is non-deterministic — resolved versions may change between runs",
        "fix": "Use `go mod download` instead (uses go.sum for verification)",
    },
    {
        "match": CARGO_INSTALL,
        "safe": CARGO_SAFE,
        "message": "cargo install without --locked — Cargo.lock will be ignored and dependencies re-resolved",
        "fix": "Use `cargo install --locked`",
    },
    {
        "match": COMPOSER_UPDATE,
        "message": "composer update in CI resolves fresh dependencies, ignoring composer.lock",
        "fix": "Use `composer install` instead (respects composer.lock)",
    },
]


class MissingFrozenLockfile(Rule):
    """Package install without lockfile enforcement."""

    name = "missing-frozen-lockfile"
    description = "Package install without lockfile enforcement"
    severity = "medium"

    def check(self, workflow: "Workflow") -> list["Finding"]:
        findings: list[Finding] = []

        for i, line in enumerate(workflow.raw_lines):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            for chk in CHECKS:
                if not chk["match"].search(line):
                    continue
                if chk.get("skip") and chk["skip"].search(line):
                    continue
                if chk.get("safe") and chk["safe"].search(line):
                    continue
                if chk.get("safe_alt") and chk["safe_alt"].search(line):
                    continue
                if chk.get("safe_alt2") and chk["safe_alt2"].search(line):
                    continue

                findings.append(
                    self.finding(
                        workflow,
                        line=i + 1,
                        code=stripped,
                        message=chk["message"],
                        fix=chk["fix"],
                    )
                )

        return findings
