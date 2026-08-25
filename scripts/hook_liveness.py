#!/usr/bin/env python3
"""Guardian T7 — hook liveness: what does git ACTUALLY execute? (TRDD-G88RIN1C)

A guard can be committed, reviewed, and inert: git resolves ONE hooks dir
(`core.hooksPath`, else `.git/hooks`), so a shipped hook file git never
resolves is DECORATIVE and a leftover file in an overridden `.git/hooks` is
SHADOWED. Nothing is red in either state, because nothing ran — which is why
this detector reports what git RESOLVES, never what exists.

Report-only by design: it never writes to any repo's git config. It takes ONE
repo path; iterating a fleet is the CALLER's job, and the caller MUST resolve
entrusted repos BY NAME from the ecosystem SSOT — never a directory glob,
which is both too wide (the owner's private projects) and too narrow (in-scope
repos nest below depth 1).

Classification is per ARTIFACT and per HOOK TYPE, never one state per repo
(a repo can be LIVE and SHADOWED at once). Rules the retracted census bugs
force (see the TRDD):
- the resolved dir comes from `git rev-parse --path-format=absolute
  --git-path hooks` and is NEVER string-concatenated with the repo root
  (core.hooksPath is frequently absolute; concatenation yields a path that
  cannot exist and every branch then reports "not live" for any input);
- shipped hooks are DISCOVERED via `git ls-files` by basename, never assumed
  to live in a known directory;
- the resolved dir is ENUMERATED (executable, non-.sample), never probed for
  a hardcoded name list — the two filters fail in opposite directions;
- a missing hook is a LOSS only beside a usage signal that the hook had work
  (LFS hooks vs `filter=lfs` patterns + `git lfs ls-files`); otherwise it is
  a benign absence, reported as such.

Exit 0 with a JSON report on stdout; exit 2 only when the target is not a git
repository (a detector that cannot measure must say so, not report clean).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Client-side hooks git can execute (githooks(5)). Used only to RECOGNIZE a
# tracked file as a shipped hook by basename; enumeration of the resolved dir
# is deliberately not filtered by this list.
KNOWN_HOOK_NAMES = frozenset(
    {
        "applypatch-msg",
        "pre-applypatch",
        "post-applypatch",
        "pre-commit",
        "pre-merge-commit",
        "prepare-commit-msg",
        "commit-msg",
        "post-commit",
        "pre-rebase",
        "post-checkout",
        "post-merge",
        "pre-push",
        "pre-auto-gc",
        "post-rewrite",
        "sendemail-validate",
        "fsmonitor-watchman",
        "push-to-checkout",
        "reference-transaction",
    }
)

# The hooks `git lfs install` provides; their only work is LFS content.
LFS_HOOKS = frozenset({"pre-push", "post-checkout", "post-commit", "post-merge"})


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _git_ok(repo: Path, *args: str) -> str | None:
    try:
        return _git(repo, *args)
    except subprocess.CalledProcessError:
        return None


def _executable_hooks(hooks_dir: Path) -> list[Path]:
    """Enumerate what git could run there: executable files, .sample excluded.

    Both filters are load-bearing and fail in OPPOSITE directions: a name list
    misses every hook outside it, while an unfiltered count over-reports by 14
    on any repo using its default .git/hooks (14 executable .sample files).
    """
    if not hooks_dir.is_dir():
        return []
    return sorted(
        p
        for p in hooks_dir.iterdir()
        if p.is_file() and not p.name.endswith(".sample") and p.stat().st_mode & 0o100
    )


def _lfs_usage(repo: Path) -> dict[str, object]:
    """The usage signal: does this repo have LFS work for the LFS hooks to do?

    Directory existence is NOT usage (.git/lfs holds install residue in most
    repos) — only tracked filter=lfs patterns or actual LFS-tracked files count.
    """
    patterns = _git_ok(repo, "grep", "-l", "filter=lfs", "--", ".gitattributes", "**/.gitattributes")
    lfs_files = _git_ok(repo, "lfs", "ls-files")
    return {
        "filter_lfs_patterns": bool(patterns),
        "lfs_tracked_files": bool(lfs_files),
        "in_use": bool(patterns) or bool(lfs_files),
    }


def scan(repo: Path) -> dict[str, object]:
    repo = repo.resolve()
    if _git_ok(repo, "rev-parse", "--is-inside-work-tree") != "true":
        raise SystemExit(2)

    top = Path(_git(repo, "rev-parse", "--show-toplevel"))
    hooks_path_cfg = _git_ok(repo, "config", "--get", "core.hooksPath")
    # The ONLY sanctioned resolution — absolute straight from git, no
    # concatenation with the repo root ever (the retracted-census bug).
    resolved_dir = Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-path", "hooks"))
    default_dir = Path(_git(repo, "rev-parse", "--path-format=absolute", "--git-dir")) / "hooks"

    resolved_execs = {p.name: p for p in _executable_hooks(resolved_dir)}

    # Shipped hooks: DISCOVERED by basename anywhere in the tracked tree.
    shipped: list[dict[str, object]] = []
    for rel in _git(repo, "ls-files").splitlines():
        name = Path(rel).name
        if name not in KNOWN_HOOK_NAMES:
            continue
        abs_path = (top / rel).resolve()
        resolved = resolved_execs.get(name)
        try:
            is_live = resolved is not None and resolved.resolve().samefile(abs_path)
        except OSError:
            is_live = False
        shipped.append(
            {
                "hook": name,
                "shipped_at": rel,
                "state": "LIVE" if is_live else "DECORATIVE",
                "resolved_to": str(resolved.resolve()) if resolved else None,
            }
        )

    # SHADOWED: executables in the default .git/hooks that git ignores because
    # core.hooksPath points elsewhere. Harmless to execution, misleading to
    # anyone opening .git/hooks to learn "what runs".
    shadowed: list[str] = []
    if resolved_dir.resolve() != default_dir.resolve():
        shadowed = [p.name for p in _executable_hooks(default_dir)]

    # DEPRIVED (observation, never breakage on its own): core.hooksPath
    # REPLACES the global hooks dir wholesale, so hooks the global dir provides
    # vanish. A missing hook is a LOSS only where it had work.
    deprived: list[dict[str, object]] = []
    global_dir_cfg = _git_ok(repo, "config", "--global", "core.hooksPath")
    if hooks_path_cfg and global_dir_cfg:
        global_dir = Path(global_dir_cfg).expanduser()
        if global_dir.resolve() != resolved_dir.resolve():
            usage = _lfs_usage(repo)
            for p in _executable_hooks(global_dir):
                if p.name in resolved_execs:
                    continue
                had_work = p.name in LFS_HOOKS and bool(usage["in_use"])
                deprived.append(
                    {
                        "hook": p.name,
                        "provided_by_global": str(p),
                        "usage_signal": usage,
                        "loss": had_work,
                    }
                )

    return {
        "repo": str(top),
        "core_hooks_path": hooks_path_cfg,
        "resolved_hooks_dir": str(resolved_dir.resolve()),
        "resolved_executables": sorted(resolved_execs),
        "shipped_hooks": shipped,
        "shadowed_in_default_dir": shadowed,
        "deprived": deprived,
    }


def main(argv: list[str]) -> int:
    repo = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    print(json.dumps(scan(repo), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
