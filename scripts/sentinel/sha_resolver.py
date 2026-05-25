"""Resolve a GitHub action tag to its commit SHA.

Port of lib/sha_resolver.rb. The Ruby original hit the GitHub REST API
directly with Net::HTTP + a GITHUB_TOKEN bearer header. This port instead
shells out to the `gh` CLI (the plugin's standard GitHub client), which
already handles authentication, base URL, and API versioning — so there
is no token plumbing here and no urllib/requests dependency.

Resolution is `gh api repos/{owner}/{repo}/commits/{tag} --jq .sha`. On any
failure (gh missing, non-zero exit, timeout) a one-line note is printed to
stderr and ``None`` is returned, exactly like the Ruby fail-safe path.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

# Match the Ruby read_timeout (30s) — a single API GET should never take
# longer; a hung call must fail-safe to None rather than block a fix run.
_GH_TIMEOUT = 30


class ShaResolver:
    """Resolves ``owner/repo@tag`` to a commit SHA via the `gh` CLI, cached."""

    def __init__(self) -> None:
        # Cache keyed "owner/repo@tag" — identical refs resolve once per run,
        # mirroring the Ruby ``@cache[key] ||= fetch_sha(...)`` memoization.
        self._cache: dict[str, str | None] = {}

    def resolve(self, owner_action: str, tag: str) -> str | None:
        """Return the commit SHA for ``owner_action@tag``, or None on failure."""
        repo = self._extract_repo(owner_action)
        key = f"{repo}@{tag}"
        if key not in self._cache:
            self._cache[key] = self._fetch_sha(repo, tag)
        return self._cache[key]

    @staticmethod
    def _extract_repo(owner_action: str) -> str:
        """First two path segments of a (possibly subpath) action reference."""
        # "actions/cache/restore" -> "actions/cache"; mirrors the Ruby
        # ``parts[0]/parts[1]`` slice so subpath actions resolve to their repo.
        parts = owner_action.split("/")
        return f"{parts[0]}/{parts[1]}"

    def _fetch_sha(self, repo: str, tag: str) -> str | None:
        """Query `gh api .../commits/{tag}` for the SHA; None + stderr on failure."""
        if shutil.which("gh") is None:
            print("ShaResolver: gh CLI not found on PATH", file=sys.stderr)
            return None
        try:
            proc = subprocess.run(
                ["gh", "api", f"repos/{repo}/commits/{tag}", "--jq", ".sha"],
                capture_output=True,
                text=True,
                timeout=_GH_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            print(f"SHA resolve failed for {repo}@{tag}: gh api timed out", file=sys.stderr)
            return None
        except OSError as exc:  # gh vanished between which() and run(), or exec error
            print(f"SHA resolve failed for {repo}@{tag}: {exc}", file=sys.stderr)
            return None

        if proc.returncode != 0:
            detail = proc.stderr.strip() or f"exit {proc.returncode}"
            print(f"ShaResolver: API error for {repo}@{tag}: {detail}", file=sys.stderr)
            return None

        sha = proc.stdout.strip()
        if not sha:
            print(f"ShaResolver: empty SHA for {repo}@{tag}", file=sys.stderr)
            return None
        return sha
