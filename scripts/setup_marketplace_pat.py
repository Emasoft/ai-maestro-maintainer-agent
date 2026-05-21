#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Set the MARKETPLACE_PAT secret on the plugin repo + the marketplace repo.

One-time setup helper for the notify-marketplace workflow. The workflow
needs a personal-access token (PAT) on BOTH this plugin's repo AND the
marketplace hub repo so it can dispatch a `plugin-updated` event when
plugin files change on the default branch.

Usage:
    uv run scripts/setup_marketplace_pat.py
    uv run scripts/setup_marketplace_pat.py \
        --plugin-repo Emasoft/ai-maestro-maintainer-agent \
        --marketplace-repo Emasoft/ai-maestro-plugins

Prerequisites:
    - gh CLI on PATH and authenticated (`gh auth status`).
    - $MARKETPLACE_PAT exported in the environment (or loaded from a
      .env file outside the repo). The script reads it directly — it
      never accepts it on the command line (would leak into shell
      history and process listings).
    - Authenticated user has `admin` permission on both target repos.

Idempotent: re-running overwrites the existing secret with the same
value. Verifies each set by listing secrets afterwards.

IMPORTANT — always uses `gh secret set -b "$VALUE"`:
    The `-b` / `--body` flag is the ONLY reliable way to pass a secret
    value to `gh secret set`. The stdin fallback path (piping the value
    in, or letting gh prompt interactively) has failure modes that
    produce subtly broken secrets — trailing newline included in the
    value, non-TTY stdin issues, etc. GitHub Actions then fails opaquely
    because the deployed secret does not match what the workflow
    expects. See the project memory note `gh-secret-set-needs-body-flag`
    for the full explanation.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

DEFAULT_PLUGIN_REPO = "Emasoft/ai-maestro-maintainer-agent"
DEFAULT_MARKETPLACE_REPO = "Emasoft/ai-maestro-plugins"
SECRET_NAME = "MARKETPLACE_PAT"  # noqa: S105 — the secret's NAME, not a value


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a subprocess, capture output, optionally fail-fast on non-zero."""
    print(f"  $ {' '.join(cmd)}", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    if check and result.returncode != 0:
        sys.exit(f"FAILED (exit {result.returncode}): {' '.join(cmd)}")
    return result


def gh_auth_ok() -> None:
    """Verify gh CLI is authenticated; fail fast otherwise."""
    r = subprocess.run(
        ["gh", "auth", "status"], capture_output=True, text=True, timeout=30
    )
    if r.returncode != 0:
        sys.exit(
            "FAILED: gh CLI is not authenticated. Run `gh auth login` first, "
            "or ensure AI Maestro exported a valid gh auth token."
        )


def admin_on(repo: str) -> None:
    """Verify the authenticated user has admin on the repo; fail fast otherwise."""
    r = subprocess.run(
        ["gh", "api", f"repos/{repo}", "--jq", ".permissions.admin"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if r.returncode != 0:
        sys.exit(f"FAILED: cannot read repos/{repo} via gh api. Network or 404?")
    if r.stdout.strip() != "true":
        sys.exit(
            f"FAILED: authenticated user lacks `admin` permission on {repo} "
            "(needed to set repo secrets)."
        )


def set_secret(repo: str, name: str, value: str) -> None:
    """Set the secret on the repo via `gh secret set NAME -b VALUE --repo R`.

    Always uses `-b` for the value — never stdin, never interactive prompt.
    """
    # subprocess.run with a list argv passes `value` directly to gh as one
    # argument — no shell parsing, no quoting surprises, no escaping risk.
    run(["gh", "secret", "set", name, "-b", value, "--repo", repo])


def verify_secret(repo: str, name: str) -> None:
    """List repo secrets and confirm `name` is present."""
    r = run(["gh", "secret", "list", "--repo", repo], check=True)
    if name not in r.stdout:
        sys.exit(f"VERIFY FAILED: {name} not visible in `gh secret list` on {repo}.")
    print(f"  ok: {name} is set on {repo}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Set MARKETPLACE_PAT on plugin + marketplace repos."
    )
    parser.add_argument(
        "--plugin-repo",
        default=DEFAULT_PLUGIN_REPO,
        help=f"OWNER/REPO of the plugin repo (default: {DEFAULT_PLUGIN_REPO})",
    )
    parser.add_argument(
        "--marketplace-repo",
        default=DEFAULT_MARKETPLACE_REPO,
        help=f"OWNER/REPO of the marketplace hub (default: {DEFAULT_MARKETPLACE_REPO})",
    )
    parser.add_argument(
        "--secret-name",
        default=SECRET_NAME,
        help=f"Secret name (default: {SECRET_NAME})",
    )
    args = parser.parse_args()

    value = os.environ.get(args.secret_name)
    if not value:
        sys.exit(
            f"FAILED: ${args.secret_name} is not set in the environment.\n"
            f"  export {args.secret_name}=<your-PAT>  (or load from a .env)"
        )

    gh_auth_ok()

    for repo in (args.plugin_repo, args.marketplace_repo):
        admin_on(repo)
        set_secret(repo, args.secret_name, value)
        verify_secret(repo, args.secret_name)

    print(
        f"\nok: {args.secret_name} is set on both "
        f"{args.plugin_repo} and {args.marketplace_repo}.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
