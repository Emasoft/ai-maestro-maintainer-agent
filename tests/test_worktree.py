"""
Tests for scripts/worktree.py — the git-worktree lifecycle engine.

Why this file exists
--------------------
Two independent reasons, and both are regressions waiting to happen.

1. THE TRUNCATION BUG. Every report-writing skill in this plugin used to resolve
   its output root with `git worktree list | head -n1 | awk '{print $1}'`. That
   output is `<path> <sha> [<branch>]`, so the awk splits on the FIRST SPACE —
   and a macOS path with a space in it (iCloud Drive, "My Project") gets
   truncated. The skill then writes its audit trail into a directory nobody
   looks at, and reports success. `test_the_old_awk_idiom_is_genuinely_broken`
   is the control that proves this is a real bug and not a story: it asserts the
   OLD idiom truncates. `test_main_root_survives_a_path_with_a_space` asserts
   the new one does not. Without the control, the second test could pass for a
   trivial reason and nobody would know.

2. THE DESTROY GUARD. An agent working inside a worktree can check out a
   different branch or detach HEAD. If the orchestrator then removes that
   worktree — still believing it holds the branch it created — the agent's work
   is deleted with no error and no trace. Three tests cover the three shapes of
   that (wrong branch / detached / dirty), because each is a distinct data-loss
   scenario and a guard that catches two of three is not a guard.

Nothing is mocked. Every test runs against a REAL git repo on disk.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

import worktree  # scripts/ is on sys.path via conftest
from worktree import WorktreeError

REPO_ROOT = Path(__file__).resolve().parent.parent


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


def _init(path: Path, *, branch: str = "main", commit: bool = True) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q", "-b", branch)
    _git(path, "config", "user.email", "713559+Emasoft@users.noreply.github.com")
    _git(path, "config", "user.name", "Emasoft")
    if commit:
        (path / "README.md").write_text("# repo\n")
        _git(path, "add", "README.md")
        _git(path, "commit", "-qm", "init")
    return path


@pytest.fixture
def spaced_repo(tmp_path: Path) -> Path:
    """A real git repo whose PATH CONTAINS A SPACE — the regression's whole point.

    `my project` is not exotic: it is what you get from iCloud Drive, Google
    Drive, and every user who named a folder in a GUI.

    Its .gitignore deliberately carries BOTH shapes of ignore pattern, because
    they behave differently and the exclude-anchoring tests turn on that:
      - `node_modules/` — no leading slash, so it matches at ANY depth.
      - `/dist`         — leading slash, so it matches ONLY at the root, and a
                          nested `src/dist/` stays tracked.
    """
    repo = _init(tmp_path / "my project")
    (repo / ".gitignore").write_text("node_modules/\n.venv/\n/dist\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-qm", "ignore")
    nm = repo / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("module.exports = 1;\n")
    dist = repo / "dist"
    dist.mkdir()
    (dist / "bundle.js").write_text("// built\n")
    return repo


# ---------------------------------------------------------------------------
# 1. The truncation bug — the reason this module exists
# ---------------------------------------------------------------------------


def test_the_old_awk_idiom_is_genuinely_broken(spaced_repo: Path) -> None:
    """The CONTROL: prove the idiom we removed really does truncate a spaced path."""
    out = subprocess.run(
        ["bash", "-c", "git worktree list | head -n1 | awk '{print $1}'"],
        cwd=spaced_repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    # It stops at the space, so it names a directory that does not even exist.
    assert out != str(spaced_repo)
    assert out.endswith("/my")
    assert not Path(out).exists(), "the truncated path must NOT exist — that is precisely why a skill using the old idiom would mkdir -p a wrong directory and write its report there"


def test_main_root_survives_a_path_with_a_space(spaced_repo: Path) -> None:
    """main_root() returns a spaced repo path intact, where the awk idiom truncated it."""
    assert worktree.main_root(spaced_repo) == spaced_repo


def test_the_shipped_shell_prologue_survives_a_path_with_a_space(spaced_repo: Path) -> None:
    """The one-liner the SKILLS run (not just the Python) resolves a spaced root."""
    out = subprocess.run(
        ["bash", "-c", "git worktree list --porcelain | sed -n '1s/^worktree //p'"],
        cwd=spaced_repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert out == str(spaced_repo)
    assert Path(out).is_dir()


def test_main_root_from_inside_a_linked_worktree_returns_the_main_root(
    spaced_repo: Path,
) -> None:
    """From INSIDE a worktree, main_root() names the main checkout — not the worktree."""
    wt = worktree.create_worktree(spaced_repo, "feat")
    assert worktree.main_root(wt.path) == spaced_repo
    assert wt.path != spaced_repo


def test_main_root_outside_a_repo_falls_back_to_the_project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Outside any git repo, main_root() falls back to $CLAUDE_PROJECT_DIR, not '/'."""
    plain = tmp_path / "not a repo"
    plain.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(plain))
    assert worktree.main_root(plain) == plain


# ---------------------------------------------------------------------------
# 2. Reading the worktree list
# ---------------------------------------------------------------------------


def test_list_worktrees_parses_spaces_branches_and_detached_head(spaced_repo: Path) -> None:
    """list_worktrees() reports the spaced path, the branch, and a detached HEAD."""
    wt = worktree.create_worktree(spaced_repo, "feat")
    _git(wt.path, "checkout", "-q", "--detach")

    entries = {w.path: w for w in worktree.list_worktrees(spaced_repo)}
    assert spaced_repo in entries, "the main checkout's spaced path must parse intact"
    assert entries[spaced_repo].branch == "main"

    linked = entries[wt.path]
    assert linked.detached is True
    assert linked.branch is None
    assert linked.head is not None


def test_current_branch_is_none_when_detached(spaced_repo: Path) -> None:
    """current_branch() returns None on a detached HEAD rather than an empty string."""
    wt = worktree.create_worktree(spaced_repo, "feat")
    assert worktree.current_branch(wt.path) == "wt/feat"
    _git(wt.path, "checkout", "-q", "--detach")
    assert worktree.current_branch(wt.path) is None


# ---------------------------------------------------------------------------
# 3. detect_main_branch — never hardcode main-or-master
# ---------------------------------------------------------------------------


def test_detect_main_branch_finds_main_with_no_remote(tmp_path: Path) -> None:
    """With no remote at all, a repo on `main` is detected as `main`."""
    repo = _init(tmp_path / "solo", branch="main")
    assert worktree.detect_main_branch(repo) == "main"


def test_detect_main_branch_finds_master_in_a_legacy_repo(tmp_path: Path) -> None:
    """A repo whose only branch is `master` is detected as `master`, not `main`."""
    repo = _init(tmp_path / "legacy", branch="master")
    assert worktree.detect_main_branch(repo) == "master"


def test_detect_main_branch_recovers_from_a_stale_origin_head(tmp_path: Path) -> None:
    """A STALE origin/HEAD (pointing at a branch the remote no longer has) is repaired.

    origin/HEAD is written once at clone time. When the remote later renames its
    default branch, every existing clone still points at the old name. Trusting
    it blindly picks a branch that does not exist.
    """
    upstream = _init(tmp_path / "upstream", branch="master")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(upstream), str(clone)], check=True, capture_output=True)
    assert worktree.detect_main_branch(clone) == "master"

    # The remote renames master -> main. The clone's origin/HEAD is now stale.
    _git(upstream, "branch", "-m", "master", "main")
    _git(clone, "fetch", "-q", "--prune", "origin")

    assert worktree.detect_main_branch(clone) == "main", "detect_main_branch must notice origin/HEAD no longer resolves and re-point it"


def test_detect_main_branch_prefers_the_remote_over_a_stale_local_master(
    tmp_path: Path,
) -> None:
    """A leftover local `master` must not outvote the remote's `main`."""
    upstream = _init(tmp_path / "up2", branch="main")
    clone = tmp_path / "clone2"
    subprocess.run(["git", "clone", "-q", str(upstream), str(clone)], check=True, capture_output=True)
    _git(clone, "branch", "master")  # a stale local branch from an old workflow
    assert worktree.detect_main_branch(clone) == "main"


# ---------------------------------------------------------------------------
# 4. create — the two guards git only explains cryptically
# ---------------------------------------------------------------------------


def test_create_refuses_an_empty_repo_with_an_actionable_message(tmp_path: Path) -> None:
    """`worktree add` needs a commit; an empty repo gets a message saying so."""
    repo = _init(tmp_path / "empty", commit=False)
    with pytest.raises(WorktreeError, match="no commits yet"):
        worktree.create_worktree(repo, "feat")


def test_create_refuses_a_branch_that_collides_with_an_existing_prefix(
    spaced_repo: Path,
) -> None:
    """Branch `fix` exists, so `fix/a` is impossible — refs are FILES on disk.

    Git's own error is `cannot lock ref 'refs/heads/fix/a': 'refs/heads/fix'
    exists`, which is opaque unless you already know refs are files. We say why.
    """
    _git(spaced_repo, "branch", "fix")
    with pytest.raises(WorktreeError, match="refs as files on disk"):
        worktree.create_worktree(spaced_repo, "nested", branch="fix/a")


def test_create_refuses_the_reverse_prefix_collision(spaced_repo: Path) -> None:
    """Branch `fix/a` exists, so plain `fix` is impossible too — the collision is symmetric."""
    _git(spaced_repo, "branch", "fix/a")
    with pytest.raises(WorktreeError, match="refs as files on disk"):
        worktree.create_worktree(spaced_repo, "plain", branch="fix")


def test_create_refuses_an_existing_directory(spaced_repo: Path) -> None:
    """A leftover .worktrees/<name> is not silently reused — it points at `recover`."""
    (spaced_repo / worktree.WORKTREE_DIR / "feat").mkdir(parents=True)
    with pytest.raises(WorktreeError, match="recover"):
        worktree.create_worktree(spaced_repo, "feat")


def test_create_branches_from_the_detected_main_branch(tmp_path: Path) -> None:
    """A `master`-only repo gets its worktree branched off master, not a guessed `main`."""
    repo = _init(tmp_path / "legacy2", branch="master")
    wt = worktree.create_worktree(repo, "feat")
    assert wt.branch == "wt/feat"
    assert _git(repo, "rev-parse", "master").strip() == _git(wt.path, "rev-parse", "HEAD").strip()


# ---------------------------------------------------------------------------
# 5. THE DESTROY GUARD — three data-loss scenarios, three tests
# ---------------------------------------------------------------------------


def test_remove_refuses_when_the_worktree_is_on_a_different_branch(
    spaced_repo: Path,
) -> None:
    """An agent checked out its own branch; removing would delete work we never made."""
    wt = worktree.create_worktree(spaced_repo, "feat")
    _git(wt.path, "checkout", "-q", "-b", "agent-did-this-instead")

    with pytest.raises(WorktreeError, match="not the expected"):
        worktree.remove_worktree(spaced_repo, "feat")
    assert wt.path.exists(), "the refusal must leave the worktree untouched"


def test_remove_refuses_when_head_is_detached(spaced_repo: Path) -> None:
    """A detached HEAD's commits are reachable from no branch — removal would orphan them."""
    wt = worktree.create_worktree(spaced_repo, "feat")
    _git(wt.path, "checkout", "-q", "--detach")

    with pytest.raises(WorktreeError, match="DETACHED"):
        worktree.remove_worktree(spaced_repo, "feat")
    assert wt.path.exists()


def test_remove_refuses_when_the_tree_is_dirty(spaced_repo: Path) -> None:
    """Uncommitted changes are reachable from nothing — removal would discard them."""
    wt = worktree.create_worktree(spaced_repo, "feat")
    (wt.path / "work-in-progress.txt").write_text("hours of it\n")

    with pytest.raises(WorktreeError, match="uncommitted change"):
        worktree.remove_worktree(spaced_repo, "feat")
    assert (wt.path / "work-in-progress.txt").exists()


def test_force_is_the_explicit_opt_out(spaced_repo: Path) -> None:
    """force=True removes a dirty, wandered-off worktree — the guard is a default, not a wall."""
    wt = worktree.create_worktree(spaced_repo, "feat")
    (wt.path / "junk.txt").write_text("throwaway\n")
    _git(wt.path, "checkout", "-q", "--detach")

    worktree.remove_worktree(spaced_repo, "feat", force=True)
    assert not wt.path.exists()


def test_force_still_does_not_delete_someone_elses_branch(spaced_repo: Path) -> None:
    """Forcing discards OUR worktree and OUR branch — never the branch the agent made."""
    wt = worktree.create_worktree(spaced_repo, "feat")
    _git(wt.path, "checkout", "-q", "-b", "agent-did-this-instead")

    worktree.remove_worktree(spaced_repo, "feat", force=True)

    branches = _git(spaced_repo, "branch", "--format=%(refname:short)").split()
    assert "wt/feat" not in branches, "our own branch was the one we were told to discard"
    assert "agent-did-this-instead" in branches, "the agent's branch holds its commits; --force discards the WORKTREE, not work we never created"


def test_remove_never_deletes_a_branch_we_did_not_create(spaced_repo: Path) -> None:
    """Our branch is gone, so the guard retargets — but the delete target must not follow it."""
    wt = worktree.create_worktree(spaced_repo, "feat")
    # The agent renames our branch away and commits: wt/feat no longer exists,
    # and the worktree now sits on a branch we never created. The guard has to
    # compare HEAD against THAT branch to be meaningful -- but discarding it is
    # not ours to do.
    _git(wt.path, "branch", "-m", "wt/feat", "agent-owns-this")
    (wt.path / "work.txt").write_text("hours of committed work\n")
    _git(wt.path, "add", "work.txt")
    _git(wt.path, "commit", "-q", "-m", "agent work")

    worktree.remove_worktree(spaced_repo, "feat")

    branches = _git(spaced_repo, "branch", "--format=%(refname:short)").split()
    assert "agent-owns-this" in branches, "we never created that branch, so removing the worktree must not delete it; the guard's comparison target is not the deletion target"


def test_remove_is_idempotent(spaced_repo: Path) -> None:
    """Removing an already-removed worktree is a no-op, not an error."""
    worktree.create_worktree(spaced_repo, "feat")
    worktree.remove_worktree(spaced_repo, "feat")
    worktree.remove_worktree(spaced_repo, "feat")  # must not raise


def test_remove_deletes_the_branch_by_default_and_keeps_it_on_request(
    spaced_repo: Path,
) -> None:
    """delete_branch=False removes the worktree but preserves the branch for later."""
    worktree.create_worktree(spaced_repo, "keepme")
    worktree.remove_worktree(spaced_repo, "keepme", delete_branch=False)
    assert "wt/keepme" in _git(spaced_repo, "branch", "--format=%(refname:short)").split()


# ---------------------------------------------------------------------------
# 6. recover — the crashed-session case
# ---------------------------------------------------------------------------


def test_recover_cleans_an_orphan_directory(spaced_repo: Path) -> None:
    """A .worktrees/<x> dir git knows nothing about (a crashed create) is removed."""
    orphan = spaced_repo / worktree.WORKTREE_DIR / "crashed"
    orphan.mkdir(parents=True)
    (orphan / "half-written.txt").write_text("...\n")

    cleaned = worktree.recover_stale(spaced_repo)

    assert not orphan.exists()
    assert any("orphan directory" in c for c in cleaned)


def test_recover_prunes_a_worktree_whose_directory_vanished(spaced_repo: Path) -> None:
    """A registration git still holds for a directory that is gone gets pruned."""
    import shutil as _shutil

    wt = worktree.create_worktree(spaced_repo, "feat")
    _shutil.rmtree(wt.path)  # simulate the crash: the dir is gone, git's record is not

    worktree.recover_stale(spaced_repo)

    paths = [w.path for w in worktree.list_worktrees(spaced_repo)]
    assert wt.path not in paths


def test_recover_never_deletes_branches(spaced_repo: Path) -> None:
    """recover() cleans WRECKAGE, not work — a stale worktree's branch may hold commits."""
    wt = worktree.create_worktree(spaced_repo, "feat")
    (wt.path / "committed.txt").write_text("real work\n")
    _git(wt.path, "add", "committed.txt")
    _git(wt.path, "commit", "-qm", "work the session did before it crashed")

    import shutil as _shutil

    _shutil.rmtree(wt.path)
    worktree.recover_stale(spaced_repo)

    assert "wt/feat" in _git(spaced_repo, "branch", "--format=%(refname:short)").split(), "the branch is the only copy of that commit — recover must not guess it away"


def test_recover_dry_run_changes_nothing(spaced_repo: Path) -> None:
    """--dry-run reports what it WOULD clean and leaves the filesystem alone."""
    orphan = spaced_repo / worktree.WORKTREE_DIR / "crashed"
    orphan.mkdir(parents=True)

    cleaned = worktree.recover_stale(spaced_repo, dry_run=True)

    assert orphan.exists(), "dry-run must not delete"
    assert any("orphan directory" in c for c in cleaned)


def test_recover_refuses_to_delete_an_independent_git_repo(spaced_repo: Path) -> None:
    """A real repo someone cloned under .worktrees/ has a .git DIRECTORY — never ours to delete."""
    nested = spaced_repo / worktree.WORKTREE_DIR / "somebody-elses-clone"
    _init(nested)
    assert (nested / ".git").is_dir()

    cleaned = worktree.recover_stale(spaced_repo)

    assert nested.exists(), "an independent repo must survive recover()"
    assert any("SKIPPED" in c for c in cleaned)


# ---------------------------------------------------------------------------
# 7. Symlinking gitignored dirs — a fresh worktree is otherwise born broken
# ---------------------------------------------------------------------------


def test_gitignored_paths_finds_node_modules(spaced_repo: Path) -> None:
    """The ignored paths that actually exist in the main checkout are discovered."""
    assert worktree.gitignored_paths(spaced_repo) == ["dist", "node_modules"]


def test_gitignored_paths_never_offers_to_link_the_worktree_dir(spaced_repo: Path) -> None:
    """.worktrees must never be symlinked into a worktree — it would contain itself."""
    (spaced_repo / worktree.WORKTREE_DIR).mkdir()
    (spaced_repo / ".gitignore").write_text("node_modules/\n.venv/\n/dist\n.worktrees/\n")
    assert worktree.WORKTREE_DIR not in worktree.gitignored_paths(spaced_repo)


def test_claude_managed_worktrees_dir_is_never_linked(spaced_repo: Path) -> None:
    """`.claude/worktrees/` — Claude Code's OWN worktree dir — must not be linked either.

    Since CC 2.1.178 the harness keeps its worktrees in `.claude/worktrees/`. That
    path is the reason NEVER_LINK had to become a set of PATH PREFIXES rather than
    bare first-segment names: its first component is `.claude`, a directory we very
    much DO descend into (it holds the local skills, settings, and the memgrep
    index). A first-component check would wave it straight through — and symlinking
    it into a worktree makes that worktree contain the directory that contains it.
    """
    (spaced_repo / ".claude" / "worktrees" / "cc-managed").mkdir(parents=True)
    (spaced_repo / ".claude" / "skills").mkdir(parents=True)
    (spaced_repo / ".claude" / "skills" / "s.md").write_text("local\n")
    (spaced_repo / ".gitignore").write_text("node_modules/\n.venv/\n/dist\n.claude/\n")

    found = worktree.gitignored_paths(spaced_repo)

    assert not any(p.startswith(".claude/worktrees") for p in found), f"a worktree-holding dir must never be offered for linking, got: {found}"
    # And the guard must be surgical, not a blanket ban on .claude:
    assert worktree._is_never_link(".claude/worktrees")
    assert worktree._is_never_link(".claude/worktrees/cc-managed")
    assert not worktree._is_never_link(".claude/skills"), "the rest of .claude must still be linkable"
    assert not worktree._is_never_link(".claude")


def test_create_symlinks_node_modules_into_the_worktree(spaced_repo: Path) -> None:
    """The worktree is usable on creation: node_modules resolves to the main checkout's."""
    wt = worktree.create_worktree(spaced_repo, "feat")
    link = wt.path / "node_modules"
    assert link.is_symlink()
    assert (link / "pkg" / "index.js").read_text() == "module.exports = 1;\n"


def test_the_symlinked_worktree_has_a_clean_git_status(spaced_repo: Path) -> None:
    """THE SUBTLE ONE: `node_modules/` in .gitignore does NOT match a SYMLINK.

    A trailing-slash pattern matches a directory. The symlink we create is not a
    directory, so without the .git/info/exclude entry it shows up as untracked in
    every `git status` the agent runs — and is one careless `git add` away from
    being committed as a link into someone's home directory.
    """
    wt = worktree.create_worktree(spaced_repo, "feat")
    status = _git(wt.path, "status", "--porcelain").strip()
    assert status == "", f"worktree must be clean, got: {status!r}"


def test_the_exclude_file_is_resolved_via_git_common_dir(spaced_repo: Path) -> None:
    """In a LINKED worktree `.git` is a FILE — the naive path join writes nowhere.

    `<worktree>/.git` contains `gitdir: <repo>/.git/worktrees/<name>`. Joining
    `<worktree>/.git/info/exclude` therefore names a path that cannot exist, and
    an implementation that writes there reports success while the exclusions
    silently never take effect.
    """
    wt = worktree.create_worktree(spaced_repo, "feat")

    assert (wt.path / ".git").is_file(), "precondition: a linked worktree's .git is a FILE"
    assert not (wt.path / ".git" / "info").exists()

    resolved = worktree.git_info_exclude_path(wt.path)
    assert resolved == worktree.safe_realpath(spaced_repo / ".git") / "info" / "exclude"
    assert resolved.is_file()
    assert "/node_modules" in resolved.read_text().splitlines()


def test_exclude_entries_are_root_anchored(spaced_repo: Path) -> None:
    """`/dist`, not `dist` — a bare exclude pattern would ALSO hide a nested src/dist.

    This is the difference that has teeth. The repo's .gitignore anchors dist at
    the root (`/dist`), so a nested `src/dist/` is a perfectly normal TRACKED
    directory. We add an exclude entry for the root `dist` because we symlinked
    it — and a symlink is not matched by a trailing-slash ignore pattern.

    If that entry were written bare (`dist`), git would apply it at every depth
    and `src/dist/` would vanish from `git status` — invisible, uncommittable,
    and lost the next time someone trusts a clean status. Anchoring it to the
    root (`/dist`) hides exactly the one symlink we created and nothing else.
    """
    wt = worktree.create_worktree(spaced_repo, "feat")
    lines = worktree.git_info_exclude_path(wt.path).read_text().splitlines()
    assert "/dist" in lines
    assert "dist" not in lines, "a bare pattern would match at every depth"

    nested = wt.path / "src" / "dist"
    nested.mkdir(parents=True)
    (nested / "source.js").write_text("this is tracked source, not a build artifact\n")

    # -uall: the default collapses untracked dirs to `?? src/`, which would hide
    # the very distinction this test is about.
    untracked = _git(wt.path, "status", "--porcelain", "-uall").strip()
    assert "src/dist/source.js" in untracked, "a nested src/dist is legitimately tracked and must stay VISIBLE to git — only the root dist symlink is hidden"

    # THE COUNTERFACTUAL. Without it, the assertion above could pass for a
    # trivial reason and this test would be decoration. Append the BARE pattern
    # an unanchored implementation would have written, and watch src/dist vanish.
    exclude = worktree.git_info_exclude_path(wt.path)
    with exclude.open("a", encoding="utf-8") as fh:
        fh.write("dist\n")
    swallowed = _git(wt.path, "status", "--porcelain", "-uall").strip()
    assert "src/dist/source.js" not in swallowed, "precondition of this whole test: a bare `dist` pattern DOES swallow a nested src/dist — which is exactly the overreach root-anchoring prevents"


def test_ensure_symlink_excludes_is_idempotent(spaced_repo: Path) -> None:
    """Creating a second worktree must not duplicate the exclude entries."""
    wt = worktree.create_worktree(spaced_repo, "one")
    worktree.create_worktree(spaced_repo, "two")

    lines = worktree.git_info_exclude_path(wt.path).read_text().splitlines()
    assert lines.count("/node_modules") == 1
    assert lines.count(worktree.EXCLUDE_HEADER) == 1


def test_link_gitignored_paths_refuses_a_path_escape(spaced_repo: Path) -> None:
    """A link path must stay INSIDE the worktree — `../../.ssh` must not be linkable.

    The original guard was "a link name must be ONE path component", which made
    escape impossible by construction. Nested paths (`.claude/skills`) broke that
    rule, so the guard had to be REPLACED, not dropped — relaxing a constraint
    that was doing security work is how a path traversal gets introduced.
    """
    wt = worktree.create_worktree(spaced_repo, "feat", link_gitignored=False)
    for evil in ("../escape", "..", "/etc/passwd", "~/.ssh/id_rsa", "a/../../b", ""):
        with pytest.raises(WorktreeError, match="refusing to link"):
            worktree.link_gitignored_paths(spaced_repo, wt.path, [evil])


def test_link_gitignored_paths_allows_a_legitimate_nested_path(spaced_repo: Path) -> None:
    """A nested path is NOT an escape — it is the entire point of the change.

    `.claude/skills` contains a separator and is perfectly safe. A guard that
    rejected it would be rejecting the feature.
    """
    (spaced_repo / ".claude" / "skills").mkdir(parents=True)
    (spaced_repo / ".claude" / "skills" / "s.md").write_text("local\n")
    wt = worktree.create_worktree(spaced_repo, "feat", link_gitignored=False)

    linked = worktree.link_gitignored_paths(spaced_repo, wt.path, [".claude/skills"])

    assert linked == [".claude/skills"]
    assert (wt.path / ".claude" / "skills").is_symlink()
    assert (wt.path / ".claude" / "skills" / "s.md").read_text() == "local\n"


def test_no_link_leaves_the_worktree_bare(spaced_repo: Path) -> None:
    """--no-link is honoured: no symlink, and the worktree is still clean."""
    wt = worktree.create_worktree(spaced_repo, "feat", link_gitignored=False)
    assert not (wt.path / "node_modules").exists()
    assert _git(wt.path, "status", "--porcelain").strip() == ""


# ---------------------------------------------------------------------------
# 7b. The `.claude` case — a PARTIALLY tracked directory
# ---------------------------------------------------------------------------


@pytest.fixture
def claude_repo(spaced_repo: Path) -> Path:
    """A repo whose `.claude/` is PARTIALLY tracked — the shape that broke the first cut.

    Two scopes live side by side in one directory, and they must reach the
    worktree by two different routes:

      - **project-scoped** = git-TRACKED  -> git checks it out. Free.
      - **local-scoped**   = git-IGNORED  -> nothing brings it across unless we
                             symlink it.

    The local half is not incidental: it holds a locally-installed skill, the
    memgrep INDEX (three levels down, inside a tracked directory), and per-machine
    state. Without it an agent in the worktree has the memory `.md` files but
    cannot `memgrep recall` — a silent, empty-result failure, not an error.
    """
    c = spaced_repo / ".claude"
    (c / "project" / "memory").mkdir(parents=True)
    (c / "project" / "memory" / "MEMORY.md").write_text("# shared, committed\n")  # project-scoped

    # local-scoped (all gitignored):
    (c / "skills" / "my-local-skill").mkdir(parents=True)
    (c / "skills" / "my-local-skill" / "SKILL.md").write_text("---\nname: local\n---\n")
    (c / "project" / "memory" / ".memgrep").mkdir()
    (c / "project" / "memory" / ".memgrep" / "index.db").write_text("sqlite\n")
    (c / "janitor").mkdir()
    (c / "janitor" / "state.json").write_text("{}\n")
    (c / "settings.local.json").write_text('{"local": true}\n')  # a FILE, not a dir

    (spaced_repo / ".gitignore").write_text("node_modules/\n.venv/\n/dist\n.claude/skills/\n.claude/janitor/\n.claude/settings.local.json\n.memgrep/\n")
    _git(spaced_repo, "add", ".gitignore", ".claude/project/memory/MEMORY.md")
    _git(spaced_repo, "commit", "-qm", "claude")
    return spaced_repo


def test_gitignored_paths_descends_into_a_partially_tracked_directory(claude_repo: Path) -> None:
    """The local-scoped half of `.claude/` is found — at any depth, files included.

    A top-level-only scan (the first cut) returns NONE of these, because `.claude`
    itself is tracked and git therefore descends into it rather than collapsing it.
    """
    found = worktree.gitignored_paths(claude_repo)
    assert ".claude/skills" in found, "a locally-installed skill must be discovered"
    assert ".claude/janitor" in found
    assert ".claude/settings.local.json" in found, "an ignored FILE, not just a dir"
    assert ".claude/project/memory/.memgrep" in found, "nested 3 deep INSIDE a tracked dir"
    assert ".claude/project/memory/MEMORY.md" not in found, "tracked — git checks it out"


def test_worktree_sees_both_the_tracked_and_the_local_half_of_claude(claude_repo: Path) -> None:
    """The whole point: a worktree gets project-scoped AND local-scoped `.claude`."""
    wt = worktree.create_worktree(claude_repo, "feat")
    c = wt.path / ".claude"

    # project-scoped: a REAL file, checked out by git — never a symlink.
    assert (c / "project" / "memory" / "MEMORY.md").read_text() == "# shared, committed\n"
    assert not (c / "project" / "memory" / "MEMORY.md").is_symlink()

    # local-scoped: symlinked to the main checkout's.
    assert (c / "skills").is_symlink()
    assert (c / "skills" / "my-local-skill" / "SKILL.md").exists(), "the local skill must be usable"
    assert (c / "project" / "memory" / ".memgrep" / "index.db").exists(), "memgrep index must resolve"
    assert (c / "janitor" / "state.json").exists()
    assert (c / "settings.local.json").read_text() == '{"local": true}\n'


def test_the_claude_symlinks_leave_the_worktree_status_clean(claude_repo: Path) -> None:
    """None of the linked local state shows up as untracked.

    The nested ones are the risk: an exclude entry must be the FULL root-anchored
    path (`/.claude/project/memory/.memgrep`), because a bare `.memgrep` would
    match at every depth and hide directories we never touched.
    """
    wt = worktree.create_worktree(claude_repo, "feat")
    status = _git(wt.path, "status", "--porcelain").strip()
    assert status == "", f"worktree must be clean, got: {status!r}"

    lines = worktree.git_info_exclude_path(wt.path).read_text().splitlines()
    assert "/.claude/project/memory/.memgrep" in lines, "the exclude must be root-anchored and FULL"
    assert ".memgrep" not in lines, "a bare basename would match at any depth"


def test_writing_through_the_link_reaches_the_main_checkout(claude_repo: Path) -> None:
    """The links are live, not copies — an agent's local state is SHARED, not forked.

    This is deliberate. A copy would drift: the agent would write a memory in the
    worktree, the worktree would be destroyed, and the memory would go with it.
    """
    wt = worktree.create_worktree(claude_repo, "feat")
    (wt.path / ".claude" / "janitor" / "written-in-worktree.txt").write_text("hello\n")
    assert (claude_repo / ".claude" / "janitor" / "written-in-worktree.txt").read_text() == "hello\n"


# ---------------------------------------------------------------------------
# 8. This repo's own configuration
# ---------------------------------------------------------------------------


def test_this_repo_gitignores_the_worktree_dir() -> None:
    """.worktrees/ MUST be gitignored, or the next release aborts.

    Not housekeeping. publish.py's staging guard (_unmanaged_dirty_paths) refuses
    to cut a release when the tree has dirty paths it does not manage. An
    unignored worktree is untracked, so merely CREATING one would brick the
    release pipeline until it was removed.
    """
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", f"{worktree.WORKTREE_DIR}/x"],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    assert ignored.returncode == 0, f"{worktree.WORKTREE_DIR}/ is not gitignored in this repo"


# The rule: every INVOCATION of `git worktree list` in an executable recipe carries
# --porcelain. Getting this detector right took three tries, and each failure is
# worth keeping, because each one is a way a guard can lie:
#
#   1. `"awk" in text and "worktree list" in text` (file-wide) flagged two skills
#      that merely list awk among their POSIX dependencies while using --porcelain
#      correctly. Prose is not code.
#   2. Any check keyed on the literal `"worktree list"` MISSES the Python form,
#      because subprocess spells it `["git", "worktree", "list"]` — the substring
#      never appears. That was sandbox.py's exact shape, so the detector would have
#      certified the buggiest file in the repo as clean.
#   3. Flagging every line that merely NAMES `git worktree list` made the result
#      depend on where prose happened to line-wrap: SKILL.md passed only because
#      "git worktree / list" broke across two lines, and instructions.md passed only
#      because it said "--porcelain" in the same sentence. A guard whose verdict
#      turns on typography is not a guard.
#
# So: an INVOCATION is a line that names worktree-list AND captures or pipes it —
# `$(…)`, a `|`, or a subprocess arg-list. Prose mentions do none of those.
_WORKTREE_LIST = re.compile(r"worktree[\"',\s]+list")
_INVOCATION = ("$(", "|", "subprocess", '["git"', "['git'")

# Directories whose JOB is to record the bug verbatim. Neither is ever executed as
# a recipe: tests reproduce the idiom to prove it truncates, and design/ TRDDs quote
# it to explain what was fixed and why. Scanning them would mean the only way to
# document a bug is to misspell it.
_DOCUMENTS_THE_BUG = ("tests/", "design/")


def _truncating_worktree_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if _WORKTREE_LIST.search(line) and "--porcelain" not in line and any(tok in line for tok in _INVOCATION)]


def test_no_shipped_file_still_uses_the_truncating_awk_idiom() -> None:
    """The 16-file regression: every `git worktree list` we ship must use --porcelain.

    This is the test that keeps the fix fixed. A new skill copy-pasted from an old
    one is exactly how the bug reached sixteen files the first time.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")

    offenders: dict[str, list[str]] = {}
    for rel in tracked:
        if not rel or rel.startswith(_DOCUMENTS_THE_BUG):
            continue
        p = REPO_ROOT / rel
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        bad = _truncating_worktree_lines(text)
        if bad:
            offenders[rel] = bad

    assert not offenders, f"these files parse `git worktree list` by column, which truncates any path containing a space. Use `--porcelain`: {offenders}"


def test_the_offender_detector_actually_detects_an_offender() -> None:
    """The detector above must not be a rubber stamp — feed it the real bug and the real fix.

    A guard that cannot fail is worse than no guard: it certifies a safety it never
    checked. Both directions are asserted, on the EXACT strings that shipped.
    """
    # The two forms that were actually in the tree before this change.
    assert _truncating_worktree_lines("MAIN_ROOT=\"$(git worktree list | head -n1 | awk '{print $1}')\""), "must catch the shell idiom that shipped in 13 files"
    assert _truncating_worktree_lines('subprocess.run(["git", "worktree", "list"], capture_output=True)'), "must catch the Python arg-list form from sandbox.py — a literal 'worktree list' check misses it"

    # The fix, in both languages.
    assert not _truncating_worktree_lines("MAIN_ROOT=\"$(git worktree list --porcelain | sed -n '1s/^worktree //p')\""), "the porcelain shell form is the fix and must NOT be flagged"
    assert not _truncating_worktree_lines('subprocess.run(["git", "worktree", "list", "--porcelain"], capture_output=True)'), "the porcelain Python form is the fix and must NOT be flagged"

    # PROSE is not an invocation. This is failure mode 3 from the comment above: an
    # earlier detector flagged these, which made its verdict depend on where the
    # prose happened to line-wrap. A doc must be able to NAME the bug it warns about.
    assert not _truncating_worktree_lines("Plain `git worktree list` prints `<path> <sha> [<branch>]`, so a column split truncates."), "a prose mention of the bug is documentation, not an invocation"
    assert not _truncating_worktree_lines("`git worktree list` always lists the main checkout first."), "a bare prose mention must not be flagged"


def test_worktree_py_is_executable() -> None:
    """The engine ships with its exec bit set — the skill invokes it directly."""
    assert os.access(REPO_ROOT / "scripts" / "worktree.py", os.X_OK)
