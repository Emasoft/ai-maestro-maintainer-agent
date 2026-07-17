#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Git worktree lifecycle for the maintainer agent — create, inspect, destroy.

Why this module exists at all
-----------------------------
Two reasons, and the second is the one that bites.

1. Isolation. Dispatching work into a worktree keeps a risky edit, a dependency
   bump, or an agent's whole session off the main checkout. Cheap to create,
   cheap to throw away.

2. `git worktree list` cannot be parsed by splitting on whitespace, and the
   whole plugin was doing exactly that. Its output is

       <path> <sha> [<branch>]

   so `awk '{print $1}'` TRUNCATES any path containing a space — routine on
   macOS (iCloud Drive, "My Project"). Every report-writing skill resolved its
   output root that way, which means on such a machine they would `mkdir -p` a
   *wrong* directory and quietly write the audit trail somewhere nobody looks.
   The fix is `--porcelain`, which puts the path alone on its own line. Putting
   it in ONE module is the point: the idiom was copy-pasted into 16 files, and
   that is how a one-line bug becomes a sixteen-line bug.

Every guard below is here because git's own failure mode for it is a cryptic
error or, worse, silence. See the individual docstrings.

CLI:
    worktree.py root                     Print the MAIN checkout's root
    worktree.py list [--json]            List worktrees
    worktree.py create <name> [...]      Create .worktrees/<name> on a new branch
    worktree.py remove <name> [--force]  Destroy it (guarded — see below)
    worktree.py recover [--dry-run]      Clean up after a crashed session
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

# Worktrees live under the repo so they share the same filesystem (cheap
# symlinks, no cross-device copies). This directory MUST be gitignored — an
# unignored worktree shows up as untracked, and publish.py's release guard
# refuses to cut a release with unmanaged dirty paths.
WORKTREE_DIR = ".worktrees"

# Idempotency marker for the block we append to .git/info/exclude. Presence of
# this header is how we know not to write the block a second time.
EXCLUDE_HEADER = "# maintainer-worktree: symlinked gitignored dirs"

# Never symlink these into a worktree. These are PATH PREFIXES, not bare names,
# and that distinction is load-bearing:
#
#   - `.worktrees` (ours) and `.claude/worktrees` (Claude Code's own, since
#     CC 2.1.178) both HOLD worktrees. Linking either one into a worktree makes
#     that worktree contain the directory that contains it — the symlink resolves
#     back to its own parent.
#   - `.git` is per-worktree state and must never be shared.
#
# A first-component check is NOT enough: `.claude/worktrees` has the first
# component `.claude`, which is a directory we very much DO want to descend into
# (it holds the local-scoped skills, settings, and the memgrep index). So the
# guard has to match the path, not its first segment.
NEVER_LINK = (".git", WORKTREE_DIR, ".claude/worktrees")


def _is_never_link(rel: str) -> bool:
    """True when `rel` is, or lives under, a path we must never symlink."""
    posix = PurePosixPath(rel).as_posix()
    return any(posix == p or posix.startswith(p + "/") for p in NEVER_LINK)


class WorktreeError(RuntimeError):
    """A refusal or a failure, phrased so the caller knows what to do next.

    Every raise site explains WHY git would otherwise fail cryptically, or why
    proceeding would destroy work.
    """


@dataclass(frozen=True)
class Worktree:
    path: Path
    head: str | None = None
    branch: str | None = None  # short name; None when detached
    detached: bool = False
    bare: bool = False
    locked: bool = False
    prunable: bool = False

    def as_dict(self) -> dict[str, object]:
        d = asdict(self)
        d["path"] = str(self.path)
        return d


def _git(
    *args: str,
    cwd: Path | str | None = None,
    check: bool = True,
) -> str:
    """Run git and return stdout. On check=False a failure yields ""."""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        if not check:
            return ""
        raise WorktreeError(f"git {' '.join(args)} failed ({proc.returncode}): {(proc.stderr or proc.stdout).strip()}")
    return proc.stdout


def _git_ok(*args: str, cwd: Path | str | None = None) -> bool:
    """Run git and report whether it SUCCEEDED, by return code.

    Distinct from _git(), which returns STDOUT. Testing _git()'s result for
    truthiness to detect failure is a trap: the commands that matter here
    (`worktree remove`, `worktree prune`) print NOTHING on success, so their
    stdout is "" — identical to the "" _git() returns on failure. That test is
    therefore true on every call, success or not, and always takes the failure
    branch. Only the return code separates the two.
    """
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def safe_realpath(p: Path | str) -> Path:
    """Resolve symlinks, tolerating a path that does not exist.

    macOS makes this mandatory: /tmp is a symlink to /private/tmp, so a worktree
    created via one spelling and compared via the other looks like a DIFFERENT
    worktree. That false mismatch would trip the destroy guard on a perfectly
    healthy worktree.
    """
    try:
        return Path(p).resolve()
    except OSError:
        return Path(p)


# --------------------------------------------------------------------------
# Reading the worktree list
# --------------------------------------------------------------------------


def main_root(cwd: Path | str | None = None) -> Path:
    """The MAIN checkout's root — correct from a linked worktree too.

    Space-safe by construction: `--porcelain` emits `worktree <path>` with the
    path alone on the line, so there is nothing to mis-split. Git always lists
    the main checkout first.

    Falls back to $CLAUDE_PROJECT_DIR (then cwd) when this is not a git repo, so
    a report still lands somewhere sane instead of at the filesystem root.
    """
    out = _git("worktree", "list", "--porcelain", cwd=cwd, check=False)
    for line in out.splitlines():
        if line.startswith("worktree "):
            return Path(line[len("worktree ") :])
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or (cwd or Path.cwd()))


def list_worktrees(cwd: Path | str | None = None) -> list[Worktree]:
    """Parse `git worktree list --porcelain` into records.

    The porcelain format is line-oriented and blank-line-separated:

        worktree /path/to/main
        HEAD 1a2b3c...
        branch refs/heads/main
        <blank>
        worktree /path/to/wt
        HEAD 4d5e6f...
        detached

    Keys with no value (`bare`, `detached`) are bare words. Parsing this by
    LINE rather than by COLUMN is what makes it immune to spaces in paths.
    """
    out = _git("worktree", "list", "--porcelain", cwd=cwd, check=False)
    entries: list[Worktree] = []
    cur: dict[str, str] = {}

    def flush() -> None:
        if not cur.get("worktree"):
            cur.clear()
            return
        branch = cur.get("branch")
        if branch and branch.startswith("refs/heads/"):
            branch = branch[len("refs/heads/") :]
        entries.append(
            Worktree(
                path=Path(cur["worktree"]),
                head=cur.get("HEAD") or None,
                branch=branch or None,
                detached="detached" in cur,
                bare="bare" in cur,
                locked="locked" in cur,
                prunable="prunable" in cur,
            )
        )
        cur.clear()

    for line in out.splitlines():
        if not line.strip():
            flush()
            continue
        key, _, val = line.partition(" ")
        cur[key] = val
    flush()
    return entries


def current_branch(path: Path | str) -> str | None:
    """The worktree's checked-out branch, or None when HEAD is detached."""
    return _git("symbolic-ref", "--quiet", "--short", "HEAD", cwd=path, check=False).strip() or None


def _ref_exists(root: Path, ref: str) -> bool:
    proc = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", ref],
        cwd=str(root),
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def _has_commits(root: Path) -> bool:
    return bool(_git("rev-parse", "--verify", "--quiet", "HEAD", cwd=root, check=False).strip())


def detect_main_branch(root: Path | str) -> str:
    """The repo's default branch. NEVER hardcode main-or-master.

    Order, and why each step exists:

    1. `origin/HEAD` — the remote's own answer, and therefore the only
       authoritative one. But a symref GOES STALE: it is written once at clone
       time, so a repo cloned before the remote renamed master->main still
       points at a branch that no longer exists. So we verify the target
       resolves, and if it does not we re-point it with `remote set-head --auto`
       and read it again.
    2. Conventional names, remote-tracking BEFORE local — a local `master` left
       over from an old clone must not outvote the remote's `main`.
    3. `init.defaultBranch`, then "main". Reached only in a repo with no remote
       and no conventional branch.
    """
    root = Path(root)
    for attempt in (1, 2):
        ref = _git("symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD", cwd=root, check=False).strip()
        if ref.startswith("origin/"):
            name = ref[len("origin/") :]
            if _ref_exists(root, f"refs/remotes/origin/{name}"):
                return name
        if attempt == 1:
            # The symref is absent or stale — ask the remote to re-point it.
            _git("remote", "set-head", "origin", "--auto", cwd=root, check=False)

    for name in ("main", "master"):
        if _ref_exists(root, f"refs/remotes/origin/{name}"):
            return name
    for name in ("main", "master"):
        if _ref_exists(root, f"refs/heads/{name}"):
            return name

    return _git("config", "--get", "init.defaultBranch", cwd=root, check=False).strip() or "main"


def _default_base(root: Path) -> str:
    """A commit-ish to branch from that is guaranteed to resolve.

    detect_main_branch() can legitimately return a name that does not exist as a
    ref (a repo whose only branch is `trunk` falls through to "main"). Handing
    that to `worktree add` produces git's "invalid reference" error, which tells
    the user nothing. Fall back to HEAD, which always resolves in a repo that
    has commits — and _has_commits() has already established that it does.
    """
    name = detect_main_branch(root)
    if _ref_exists(root, f"refs/heads/{name}") or _ref_exists(root, f"refs/remotes/origin/{name}"):
        return name
    return "HEAD"


# --------------------------------------------------------------------------
# Gitignored-dir symlinking — without it a fresh worktree is born broken
# --------------------------------------------------------------------------


def gitignored_paths(root: Path | str) -> list[str]:
    """EVERY gitignored path that exists in the main checkout — files and dirs, at ANY depth.

    A fresh worktree contains only TRACKED files. No node_modules, no .venv, no
    target/. An agent dropped into one cannot install, build, or test — the
    worktree is born broken, and its first act is a dependency install it should
    never have had to do.

    Two things this must NOT assume, both of which were wrong in the first cut:

    - **Not just top-level.** `.claude/` is a *partially* tracked directory: its
      project memory is committed, while `.claude/chat_history/`,
      `.claude/janitor/`, `.claude/scheduled_tasks.json`, and — three levels
      down — `.claude/project/memory/.memgrep/` are ignored. A top-level-only
      scan returns NONE of them, so an agent in the worktree gets the memory
      `.md` files but no memgrep INDEX, and `memgrep recall` silently finds
      nothing. Local state has to be linked where it actually lives.
    - **Not just directories.** `.claude/scheduled_tasks.json` is a file.

    Git does the hard part: `--ignored` (traditional mode) COLLAPSES a fully
    ignored directory to one `!! node_modules/` entry instead of listing every
    file inside it, and descends only where a directory is partially tracked —
    which is exactly the granularity we want. `-z` gives NUL separators with no
    shell quoting, so a path containing a space survives intact.
    """
    out = _git("status", "--porcelain", "-z", "--ignored", cwd=root, check=False)
    paths: set[str] = set()
    for entry in out.split("\0"):
        if not entry.startswith("!! "):
            continue
        rel = entry[3:].rstrip("/")
        if not rel or _is_never_link(rel):
            # A worktree-holding directory would make the worktree contain itself;
            # `.git` is per-worktree state that must never be shared.
            continue
        paths.add(rel)
    return sorted(paths)


def _safe_link_target(worktree: Path, rel: str) -> Path:
    """Resolve `rel` inside `worktree`, refusing anything that escapes it.

    The destination is now a nested path (`.claude/project/memory/.memgrep`), so
    the old rule — "a link name must be a single path component" — no longer
    holds. That rule WAS the escape guard, so relaxing it means REPLACING it, not
    dropping it: a crafted `../../.ssh` or an absolute `/etc` would otherwise put
    a symlink outside the worktree, or overwrite something.

    Two checks, because either alone is bypassable:
      1. the string is relative, has no `..` component, and no `~`;
      2. the resolved parent really is inside the worktree — which catches the
         case where a directory on the path is itself a symlink pointing out.
    """
    p = PurePosixPath(rel)
    if not rel or p.is_absolute() or ".." in p.parts or rel.startswith("~") or "\\" in rel:
        raise WorktreeError(f"refusing to link {rel!r}: a link path must be relative and inside the worktree. An absolute path, a '..' component, or a '~' would place the symlink OUTSIDE it.")

    dst = worktree / Path(rel)
    parent = safe_realpath(dst.parent)
    wt = safe_realpath(worktree)
    if parent != wt and wt not in parent.parents:
        raise WorktreeError(f"refusing to link {rel!r}: it resolves to {parent}, outside the worktree {wt}")
    return dst


def link_gitignored_paths(root: Path | str, worktree: Path | str, paths: list[str] | None = None) -> list[str]:
    """Symlink the main checkout's gitignored files and dirs into the worktree.

    Returns the paths actually linked. A path whose source is gone, or whose
    destination already exists, is skipped — so this is idempotent and safe to
    re-run.
    """
    root = safe_realpath(root)
    worktree = safe_realpath(worktree)
    paths = gitignored_paths(root) if paths is None else paths

    linked: list[str] = []
    for rel in sorted(paths):
        # VALIDATE FIRST, unconditionally. The existence check below must not come
        # before this: an escaping path that happens not to exist would then be
        # silently `continue`d instead of refused, and the guard would be armed only
        # for paths that already exist — which is exactly the set an attacker does
        # not need it for. A security check that runs conditionally is not a check.
        dst = _safe_link_target(worktree, rel)

        if _is_never_link(rel):
            continue
        src = root / Path(rel)
        if not src.exists():
            continue
        if dst.exists() or dst.is_symlink():
            continue
        # A nested target's parents are usually already present (they are tracked —
        # that is WHY git descended into them). Create them if not: a directory
        # holding nothing but an excluded symlink is invisible to `git status`,
        # because git does not report an untracked directory with no untracked
        # contents.
        dst.parent.mkdir(parents=True, exist_ok=True)
        _safe_link_target(worktree, rel)  # re-check: the mkdir must not have escaped
        dst.symlink_to(src, target_is_directory=src.is_dir())
        linked.append(rel)
    return linked


def git_info_exclude_path(worktree: Path | str) -> Path:
    """Resolve `info/exclude` for a worktree — the part that is easy to get wrong.

    In a LINKED worktree, `.git` is a FILE, not a directory: it contains
    `gitdir: /path/to/repo/.git/worktrees/<name>`. So joining
    `<worktree>/.git/info/exclude` names a path that does not exist. A naive
    implementation writes the exclusions there, reports success, and the
    exclusions silently never take effect.

    `rev-parse --git-common-dir` returns the SHARED git directory, which is
    where `info/exclude` actually lives and is read from.
    """
    worktree = Path(worktree)
    common = _git("rev-parse", "--git-common-dir", cwd=worktree).strip()
    if not common:
        raise WorktreeError(f"{worktree} is not inside a git repository")
    p = Path(common)
    if not p.is_absolute():
        p = worktree / p
    return safe_realpath(p) / "info" / "exclude"


def ensure_symlink_excludes(worktree: Path | str, paths: list[str]) -> Path | None:
    """Make the symlinks invisible to git. Without this, every `git status` lies.

    The subtle half of symlinking. A `.gitignore` entry written with a trailing
    slash — `node_modules/`, which is how essentially everyone writes it —
    matches a DIRECTORY. A symlink is not a directory, so the symlink we just
    created is NOT ignored: it shows up as an untracked entry in every
    `git status` the agent runs inside the worktree, and it is one careless
    `git add` away from being committed as a link to someone's home directory.

    A pattern in `info/exclude` without the trailing slash matches both.

    Entries are ROOT-ANCHORED — `/node_modules`, and for a nested path the FULL
    path from the repo root (`/.claude/project/memory/.memgrep`), never a bare
    basename. A bare pattern matches at ANY depth, so `memgrep` would hide every
    directory of that name anywhere in the tree, and `node_modules` would hide a
    legitimately tracked `packages/foo/node_modules` in a monorepo. Anchoring
    hides exactly the one symlink we created and nothing else.
    """
    if not paths:
        return None
    path = git_info_exclude_path(worktree)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    present = set(existing.splitlines())
    wanted = [f"/{p}" for p in paths]
    missing = [w for w in wanted if w not in present]
    if not missing:
        return path

    block = ""
    if existing and not existing.endswith("\n"):
        block += "\n"
    if EXCLUDE_HEADER not in existing:
        block += EXCLUDE_HEADER + "\n"
    block += "\n".join(missing) + "\n"

    with path.open("a", encoding="utf-8") as fh:
        fh.write(block)
    return path


# --------------------------------------------------------------------------
# Create
# --------------------------------------------------------------------------

_BRANCH_ILLEGAL = re.compile(r"[\s~^:?*\[\\]|\.\.|^-|@\{|\.lock$|^$")


def _assert_valid_branch(branch: str) -> None:
    if _BRANCH_ILLEGAL.search(branch):
        raise WorktreeError(f"{branch!r} is not a valid branch name (no whitespace, ~^:?*[\\, '..', leading '-', '@{{', or a '.lock' suffix)")


def _branch_prefix_conflict(root: Path, branch: str) -> str | None:
    """Find an existing branch that cannot coexist with `branch`.

    Git stores refs as FILES on disk, so `refs/heads/fix` is a file and
    `refs/heads/fix/a` needs `refs/heads/fix` to be a DIRECTORY. Both cannot
    exist. Git's own error for this is

        fatal: cannot lock ref 'refs/heads/fix/a': 'refs/heads/fix' exists

    which is accurate and completely opaque unless you already know refs are
    files. We detect it up front and say what to do instead.
    """
    existing = _git("for-each-ref", "--format=%(refname:short)", "refs/heads", cwd=root).split()
    for b in existing:
        if branch.startswith(b + "/") or b.startswith(branch + "/"):
            return b
    return None


def _resolve_worktree_path(root: Path, name: str) -> Path:
    """A name is either a bare label (-> .worktrees/<name>) or a path."""
    p = Path(name)
    if p.is_absolute() or len(p.parts) > 1:
        return safe_realpath(p)
    return safe_realpath(root) / WORKTREE_DIR / name


def create_worktree(
    root: Path | str,
    name: str,
    *,
    branch: str | None = None,
    base: str | None = None,
    link_gitignored: bool = True,
) -> Worktree:
    """Create `.worktrees/<name>` on a new branch, usable the moment it exists."""
    root = safe_realpath(root)

    if not _has_commits(root):
        raise WorktreeError("this repository has no commits yet, and `git worktree add` needs a commit to branch from. Make the initial commit first.")

    branch = branch or f"wt/{name}"
    _assert_valid_branch(branch)

    conflict = _branch_prefix_conflict(root, branch)
    if conflict:
        raise WorktreeError(f"cannot create branch {branch!r}: branch {conflict!r} already exists. Git stores refs as files on disk, so {conflict!r} would have to be both a file and a directory for these to coexist. Pick a name that neither extends nor prefixes an existing branch.")
    if _ref_exists(root, f"refs/heads/{branch}"):
        raise WorktreeError(f"branch {branch!r} already exists. Pass an explicit branch name, or remove the existing worktree/branch first.")

    path = _resolve_worktree_path(root, name)
    if path.exists():
        raise WorktreeError(f"{path} already exists. If a previous session crashed and left it behind, run `worktree.py recover` to clean it up.")

    base = base or _default_base(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    _git("worktree", "add", "-b", branch, str(path), base, cwd=root)

    if link_gitignored:
        linked = link_gitignored_paths(root, path)
        ensure_symlink_excludes(path, linked)

    return Worktree(path=path, branch=branch, head=_git("rev-parse", "HEAD", cwd=path).strip())


# --------------------------------------------------------------------------
# Destroy — the half that must be trusted
# --------------------------------------------------------------------------


def assert_safe_to_destroy(path: Path | str, expected_branch: str | None, *, force: bool = False) -> None:
    """Refuse to destroy a worktree that is not where we left it.

    THIS IS A DATA-LOSS GUARD. It is the entire reason the destroy half can be
    trusted, and it exists because of a failure mode the reference implementation
    hit in production: an agent working inside a worktree checks out a different
    branch, or detaches HEAD, and then the orchestrator — still believing the
    worktree holds `wt/foo` — removes the directory and deletes `wt/foo`. The
    agent's actual work was on some other ref, reachable from nothing, and it is
    now gone with no error and no trace.

    Three ways that happens, so three checks:
      - HEAD detached  -> commits are reachable from no branch at all.
      - Wrong branch   -> we would delete a branch nobody asked us to.
      - Dirty tree     -> uncommitted work, reachable from nothing.

    `force=True` is the explicit, auditable opt-out. It is not the default, and
    the CLI spells it `--force` so it appears in the shell history.
    """
    if force:
        return
    path = Path(path)
    if not path.exists():
        return  # nothing to destroy; remove_worktree is idempotent

    actual = current_branch(path)
    if actual is None:
        raise WorktreeError(f"refusing to remove {path}: HEAD is DETACHED. Any commits made there are reachable from no branch and would be lost. Inspect it first (`git -C '{path}' log HEAD`), then re-run with --force to discard.")
    if expected_branch is not None and actual != expected_branch:
        raise WorktreeError(f"refusing to remove {path}: it is on branch {actual!r}, not the expected {expected_branch!r}. Something checked out a different branch there, and removing it now would discard that work. Inspect it first, then re-run with --force to discard.")
    dirty = _git("status", "--porcelain", cwd=path, check=False).strip()
    if dirty:
        n = len(dirty.splitlines())
        raise WorktreeError(f"refusing to remove {path}: {n} uncommitted change(s). Commit or stash them, or re-run with --force to discard.")


def _rmtree_with_backoff(path: Path, attempts: int = 4) -> None:
    """rmtree, retrying briefly.

    `git worktree remove` can fail, and a plain rmtree right after it can fail
    too, while a handle or a bind mount is still releasing — a sandboxed agent
    that just exited is the usual culprit. The failure is transient and clears in
    milliseconds, so a short backoff turns a spurious hard error into a no-op.
    """
    last: OSError | None = None
    for i in range(attempts):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError as exc:
            last = exc
            time.sleep(0.1 * (2**i))
    if path.exists():
        raise WorktreeError(f"could not remove {path}: {last}")


def remove_worktree(
    root: Path | str,
    name: str,
    *,
    branch: str | None = None,
    force: bool = False,
    delete_branch: bool = True,
) -> None:
    """Destroy a worktree and (by default) its branch. Idempotent.

    Guarded by assert_safe_to_destroy() BEFORE anything is touched.
    """
    root = safe_realpath(root)
    path = _resolve_worktree_path(root, name)

    # Two DIFFERENT branches, deliberately kept apart:
    #   `ours`     — the branch we created (or the caller explicitly named). The
    #                ONLY thing we may ever discard.
    #   `expected` — what the guard compares the worktree's real HEAD against.
    # They used to be one variable, and that was a data-loss bug: when `ours`
    # did not exist, `expected` was reassigned to whatever the agent had checked
    # out — and that same variable was then the `branch -D` target, so we
    # force-deleted a branch we never created. --force must discard the
    # WORKTREE, never work we did not make (tests at test_worktree.py:310).
    ours = branch or (f"wt/{name}" if len(Path(name).parts) == 1 else None)
    ours_exists = ours is not None and _ref_exists(root, f"refs/heads/{ours}")

    expected = ours
    if expected is not None and not ours_exists and path.exists():
        # The conventional branch does not exist, so we cannot have created this
        # worktree under that name. Guard against whatever IS checked out instead
        # of against a name we invented.
        expected = current_branch(path)

    assert_safe_to_destroy(path, expected, force=force)

    if path.exists():
        # _git_ok, not _git: `git worktree remove` is SILENT on success, so its
        # stdout is "" either way and `not _git(...)` would take the fallback on
        # every call — rm-rf'ing a directory git had already removed cleanly.
        if not _git_ok("worktree", "remove", "--force", str(path), cwd=root):
            # `git worktree remove` refused (a lock, a stale registration, a
            # sandbox still holding the mount). Take the directory ourselves and
            # let `prune` reconcile git's bookkeeping below.
            _rmtree_with_backoff(path)

    _git("worktree", "prune", cwd=root, check=False)

    # `ours`, never `expected`: only the branch WE created is ours to discard.
    # ours_exists is read BEFORE the removal above, which does not touch refs.
    if delete_branch and ours and ours_exists:
        # -D not -d: the branch is by definition unmerged in the throw-it-away
        # case, and the guard above has already established that discarding it is
        # safe (or that --force was passed). check=False tolerates "not found",
        # which is the normal state on a second call.
        _git("branch", "-D", ours, cwd=root, check=False)


def recover_stale(root: Path | str, *, dry_run: bool = False) -> list[str]:
    """Clean up after a crashed session, WITHOUT deleting anyone's commits.

    Two kinds of wreckage:
      - a worktree git still has registered whose directory is gone (`prunable`),
      - a directory under .worktrees/ that git does not know about at all.

    Note what this deliberately does NOT do: delete branches. A stale worktree's
    branch may hold the only copy of an interrupted session's commits, and the
    whole point of the destroy guard is that we do not throw work away on a
    guess. Branch deletion belongs to `remove`, which checks first.
    """
    root = safe_realpath(root)
    cleaned: list[str] = []

    for wt in list_worktrees(root):
        if wt.prunable:
            cleaned.append(f"prunable registration: {wt.path}")

    known = {safe_realpath(wt.path) for wt in list_worktrees(root)}
    wt_dir = root / WORKTREE_DIR
    if wt_dir.is_dir():
        for child in sorted(wt_dir.iterdir()):
            if not child.is_dir() or safe_realpath(child) in known:
                continue
            if (child / ".git").is_dir():
                # A .git DIRECTORY means an independent repo, not a linked
                # worktree of ours. Never ours to delete.
                cleaned.append(f"SKIPPED (independent git repo): {child}")
                continue
            cleaned.append(f"orphan directory: {child}")
            if not dry_run:
                _rmtree_with_backoff(child)

    if not dry_run:
        _git("worktree", "prune", cwd=root, check=False)
    return cleaned


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _cmd_root(_args: argparse.Namespace) -> int:
    print(main_root())
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    wts = list_worktrees()
    if args.json:
        print(json.dumps([w.as_dict() for w in wts], indent=2))
        return 0
    for w in wts:
        state = w.branch or ("detached" if w.detached else "?")
        flags = "".join(f" [{f}]" for f, on in (("locked", w.locked), ("prunable", w.prunable)) if on)
        print(f"{w.path}  ({state}){flags}")
    return 0


def _cmd_create(args: argparse.Namespace) -> int:
    wt = create_worktree(
        main_root(),
        args.name,
        branch=args.branch,
        base=args.base,
        link_gitignored=not args.no_link,
    )
    print(f"created {wt.path} on branch {wt.branch}")
    return 0


def _cmd_remove(args: argparse.Namespace) -> int:
    remove_worktree(
        main_root(),
        args.name,
        branch=args.branch,
        force=args.force,
        delete_branch=not args.keep_branch,
    )
    print(f"removed {args.name}")
    return 0


def _cmd_recover(args: argparse.Namespace) -> int:
    cleaned = recover_stale(main_root(), dry_run=args.dry_run)
    if not cleaned:
        print("nothing to recover")
        return 0
    prefix = "would clean" if args.dry_run else "cleaned"
    for item in cleaned:
        print(f"{prefix}: {item}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    # `python -OO` strips docstrings, so __doc__ can be None at runtime.
    summary = (__doc__ or "Git worktree lifecycle.").splitlines()[0]
    p = argparse.ArgumentParser(prog="worktree.py", description=summary)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("root", help="print the MAIN checkout's root").set_defaults(func=_cmd_root)

    pl = sub.add_parser("list", help="list worktrees")
    pl.add_argument("--json", action="store_true")
    pl.set_defaults(func=_cmd_list)

    pc = sub.add_parser("create", help="create .worktrees/<name> on a new branch")
    pc.add_argument("name")
    pc.add_argument("--branch", help="branch name (default: wt/<name>)")
    pc.add_argument("--base", help="commit-ish to branch from (default: the repo's main branch)")
    pc.add_argument(
        "--no-link",
        action="store_true",
        help="do NOT symlink gitignored dirs (node_modules, .venv, ...) into the worktree",
    )
    pc.set_defaults(func=_cmd_create)

    pr = sub.add_parser("remove", help="destroy a worktree and its branch")
    pr.add_argument("name")
    pr.add_argument("--branch", help="the branch you EXPECT it to be on (default: wt/<name>)")
    pr.add_argument(
        "--force",
        action="store_true",
        help="discard work: remove even when on another branch, detached, or dirty",
    )
    pr.add_argument("--keep-branch", action="store_true", help="remove the worktree, keep the branch")
    pr.set_defaults(func=_cmd_remove)

    pv = sub.add_parser("recover", help="clean up worktrees left by a crashed session")
    pv.add_argument("--dry-run", action="store_true")
    pv.set_defaults(func=_cmd_recover)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except WorktreeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
