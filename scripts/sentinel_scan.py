#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Sentinel — deterministic GitHub Actions security scanner (Python port).

A faithful Python port of the Ruby `sentinel-ci` gem (v1.3.0). Scans a
local checkout's `.github/workflows/*.{yml,yaml}` against 32 deterministic
rules, plus two repo-level checks (missing Dependabot github-actions
config, missing zizmor workflow). The maintainer Guardian runs this as a
deterministic engine alongside zizmor.

Usage:
    sentinel_scan.py [scan] [PATH] [--local PATH | --workflows]
                     [--format terminal|json|sarif] [--severity LEVEL]
    sentinel_scan.py fix  [PATH] [--local PATH] [--dry-run] [--rule NAME ...]

    PATH defaults to "." (the current checkout). `--workflows` is a
    shorthand for scanning the current directory's workflows.

Severity levels (high→low): critical, high, medium, low (default: low).

Policy: a `.sentinel-ci.yml` at the scan root is read automatically
(severity floor, per-rule overrides, ignore globs, exceptions).

Exit codes:
    0  no critical/high findings
    1  critical or high findings present
    2  usage error / malformed policy
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# Make the bundled `sentinel` package importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sentinel.formatters.json import Json  # noqa: E402
from sentinel.formatters.sarif import Sarif  # noqa: E402
from sentinel.formatters.terminal import Terminal  # noqa: E402
from sentinel.local_client import LocalClient  # noqa: E402
from sentinel.policy import Policy  # noqa: E402
from sentinel.scanner import Scanner  # noqa: E402

_REPO_SLUG = re.compile(r"^[\w.-]+/[\w.-]+$")


def _resolve_path(args: argparse.Namespace, parser: argparse.ArgumentParser) -> str:
    """Resolve the scan/fix target from --local / --workflows / positional."""
    modes = [m for m in (args.local, args.workflows, args.path) if m]
    if len(modes) > 1:
        parser.error("specify only one of --local, --workflows, or a PATH")
    if args.local:
        return args.local
    if args.workflows:
        return "."
    if args.path:
        # Helpful guard: this port scans LOCAL checkouts, not remote slugs.
        if _REPO_SLUG.match(args.path) and not os.path.isdir(args.path):
            parser.error(f"'{args.path}' looks like a remote owner/repo. This port scans local checkouts only — clone the repo and run with --local PATH.")
        return args.path
    return "."


def _make_formatter(fmt: str) -> Json | Sarif | Terminal:
    """Instantiate the requested output formatter."""
    if fmt == "json":
        return Json()
    if fmt == "sarif":
        return Sarif()
    return Terminal()


def _load_policy(root: str) -> Policy:
    """Load <root>/.sentinel-ci.yml when present, else an empty policy."""
    policy_path = os.path.join(root, ".sentinel-ci.yml")
    return Policy(policy_path) if os.path.exists(policy_path) else Policy()


def _cmd_scan(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="sentinel_scan.py scan",
        description="Scan local GitHub Actions workflows for security issues.",
    )
    parser.add_argument("path", nargs="?", help="path to a local checkout (default: .)")
    parser.add_argument("--local", metavar="PATH", help="scan a local directory")
    parser.add_argument("--workflows", action="store_true", help="scan ./.github/workflows (shorthand for PATH=.)")
    parser.add_argument("--format", choices=["terminal", "json", "sarif"], default="terminal", help="output format")
    parser.add_argument("--severity", choices=["critical", "high", "medium", "low"], help="minimum severity (default: low)")
    args = parser.parse_args(argv)

    root = _resolve_path(args, parser)

    policy = _load_policy(root)
    if policy.errors:
        for err in policy.errors:
            print(f"Policy error: {err}", file=sys.stderr)
        return 2

    # Policy severity floor applies only when not overridden on the CLI.
    severity = args.severity
    if severity is None:
        severity = policy.min_severity() if policy.loaded() else "low"

    formatter = _make_formatter(args.format)
    client = LocalClient(root)
    scanner = Scanner(client=client, formatter=formatter, min_severity=severity, policy=policy)

    result = scanner.scan(root)
    print(result["output"])

    has_critical_or_high = any(f.is_critical() or f.is_high() for f in result["findings"])
    return 1 if has_critical_or_high else 0


def _cmd_fix(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="sentinel_scan.py fix",
        description="Apply mechanical fixes to local GitHub Actions workflows.",
    )
    parser.add_argument("path", nargs="?", help="path to a local checkout (default: .)")
    parser.add_argument("--local", metavar="PATH", help="fix a local directory")
    parser.add_argument("--workflows", action="store_true", help="fix ./.github/workflows (shorthand for PATH=.)")
    parser.add_argument("--dry-run", action="store_true", help="preview changes without writing files")
    parser.add_argument("--rule", action="append", default=[], metavar="NAME", help="limit to a rule (repeatable)")
    parser.add_argument("--format", choices=["terminal", "json"], default="terminal", help="output format")
    args = parser.parse_args(argv)

    root = _resolve_path(args, parser)

    # Lazy import: keeps `scan` fast and dependency-light.
    from sentinel.autofix import run_fix

    return run_fix(
        root=root,
        dry_run=args.dry_run,
        only_rules=set(args.rule),
        output_format=args.format,
    )


_TOP_HELP = """\
Usage: sentinel_scan.py <command> [options] [PATH]

Commands:
    scan [PATH]    Scan local workflows for security issues (default command)
    fix  [PATH]    Apply mechanical fixes to local workflows

Run 'sentinel_scan.py scan --help' or 'sentinel_scan.py fix --help' for options.
"""


def main(argv: list[str] | None = None) -> int:
    """Dispatch to the scan (default) or fix subcommand."""
    args = list(sys.argv[1:] if argv is None else argv)

    if args and args[0] in ("-h", "--help"):
        print(_TOP_HELP)
        return 0

    sub = "scan"
    if args and args[0] in ("scan", "fix"):
        sub = args.pop(0)

    if sub == "fix":
        return _cmd_fix(args)
    return _cmd_scan(args)


if __name__ == "__main__":
    sys.exit(main())
