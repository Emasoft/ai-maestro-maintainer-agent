"""
Regression tests for WHAT THE RELEASE COMMIT STAGES (publish.py).

Why this file exists: `stage_commit_and_push` used to run `git add -A`. The tree
is verified clean at stage [1/11], but roughly nine gates run between there and
the commit at [10/11] — lint, tests, CPV, consistency — and any of them can leave
an artifact behind. `git add -A` sweeps that artifact into the release commit and
PUSHES it to a public repo. That is exactly how a scratch file, a tool's output,
or a credential-bearing log becomes a permanent part of git history.

It is also the thing this plugin tells everyone else not to do: its own skills
(`workflow-fix-safe`, `maintainer-fix`) instruct "stage by name, NEVER `git add
-A`", and so does the user's global rule. The release script was the one place
that broke its own rule.

Nothing is mocked: every test runs against a REAL git repo on disk. The abort path
is exercised through the real `stage_commit_and_push`, which fails BEFORE it
reaches git commit or the gh-auth precheck — so the whole guard is testable with
no network and no GitHub account.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import publish  # scripts/ is on sys.path via conftest

VERSION = "9.9.9"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout


@pytest.fixture
def repo(tmp_git_repo: Path) -> Path:
    """A real git repo carrying the files a release actually rewrites."""
    (tmp_git_repo / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (tmp_git_repo / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "demo-plugin", "version": VERSION}, indent=2) + "\n",
        encoding="utf-8",
    )
    (tmp_git_repo / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (tmp_git_repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_git_repo / "pyproject.toml").write_text('[project]\nversion = "9.9.9"\n', encoding="utf-8")
    _git(tmp_git_repo, "add", "-f", "--",
         ".claude-plugin/plugin.json", "CHANGELOG.md", "README.md", "pyproject.toml")
    _git(tmp_git_repo, "commit", "-m", "seed")
    return tmp_git_repo


# ───────────────────────── _release_managed_paths ─────────────────────────


def test_managed_paths_cover_the_files_a_bump_actually_rewrites(repo: Path) -> None:
    """The staged set must contain every file the update_* helpers write.

    If a file the bump rewrites is missing here, the release commit silently omits
    it and the published version is internally inconsistent.
    """
    managed = publish._release_managed_paths(repo)
    for expected in (".claude-plugin/plugin.json", "CHANGELOG.md", "README.md", "pyproject.toml"):
        assert expected in managed


def test_managed_paths_omit_files_that_do_not_exist(repo: Path) -> None:
    """`git add` on a nonexistent path is an error — never offer one.

    marketplace.json only exists in a Layout-C plugin; this repo has none.
    """
    managed = publish._release_managed_paths(repo)
    assert ".claude-plugin/marketplace.json" not in managed
    for p in managed:
        assert (repo / p).exists()


def test_managed_paths_include_only_scripts_carrying_a_version(repo: Path) -> None:
    """A script is staged iff it declares __version__ — the SAME predicate that decides
    whether update_python_versions rewrites it.

    Staging a script the bump never touches would let an unrelated local edit ride
    the release commit; not staging one it DOES touch would ship a stale version.
    """
    scripts = repo / "scripts"
    scripts.mkdir(exist_ok=True)
    (scripts / "versioned.py").write_text('__version__ = "1.0.0"\n', encoding="utf-8")
    (scripts / "plain.py").write_text("x = 1\n", encoding="utf-8")

    managed = publish._release_managed_paths(repo)
    assert "scripts/versioned.py" in managed
    assert "scripts/plain.py" not in managed


# ───────────────────────── _unmanaged_dirty_paths ─────────────────────────


def test_no_leftovers_when_only_managed_files_are_dirty(repo: Path) -> None:
    """The happy path: the bump dirtied exactly the files it owns → nothing to refuse."""
    (repo / "CHANGELOG.md").write_text("# Changelog\n\n## 9.9.9\n", encoding="utf-8")
    (repo / "README.md").write_text("# Demo\n\nbadge\n", encoding="utf-8")
    managed = publish._release_managed_paths(repo)
    assert publish._unmanaged_dirty_paths(repo, managed) == []


def test_a_stray_untracked_file_is_detected(repo: Path) -> None:
    """An artifact a gate left behind must be SEEN.

    This is the whole point: under `git add -A` this file would have been committed
    and pushed to a public repo without anyone reading it.
    """
    (repo / "leaked-scan-output.txt").write_text("secrets go here\n", encoding="utf-8")
    managed = publish._release_managed_paths(repo)
    assert "leaked-scan-output.txt" in publish._unmanaged_dirty_paths(repo, managed)


def test_a_modified_tracked_file_outside_the_managed_set_is_detected(repo: Path) -> None:
    """A linter's auto-fix must not silently ride the release commit either."""
    (repo / "src.py").write_text("print(1)\n", encoding="utf-8")
    _git(repo, "add", "-f", "--", "src.py")
    _git(repo, "commit", "-m", "add src")
    (repo / "src.py").write_text("print(2)  # a gate rewrote this\n", encoding="utf-8")

    managed = publish._release_managed_paths(repo)
    assert "src.py" in publish._unmanaged_dirty_paths(repo, managed)


def test_gitignored_artifacts_are_not_flagged(repo: Path) -> None:
    """reports/ and *_dev/ are gitignored, so they must NOT trip the guard.

    Agents write reports on every run; if those tripped the release, publishing
    would be impossible in practice and the guard would be disabled — which is how
    a good check dies.
    """
    (repo / ".gitignore").write_text("reports/\nreports_dev/\n", encoding="utf-8")
    _git(repo, "add", "-f", "--", ".gitignore")
    _git(repo, "commit", "-m", "ignore reports")
    (repo / "reports").mkdir()
    (repo / "reports" / "audit.md").write_text("private\n", encoding="utf-8")

    managed = publish._release_managed_paths(repo)
    assert publish._unmanaged_dirty_paths(repo, managed) == []


# ─────────────────── the guard, through the real call site ───────────────────


def test_publish_refuses_to_commit_when_a_gate_left_a_stray_file(repo: Path) -> None:
    """stage_commit_and_push ABORTS rather than sweeping an unknown file into a release.

    Fail-fast: refusing a release is cheap and reversible; pushing an unreviewed file
    to a public repo is neither. The guard fires before git commit and before the
    gh-auth precheck, so this runs with no network.
    """
    (repo / "stray-artifact.log").write_text("...\n", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        publish.stage_commit_and_push(repo, VERSION, dry_run=False)
    assert e.value.code == 1

    # and it must NOT have committed anything
    assert "stray-artifact.log" not in _git(repo, "show", "--stat", "HEAD")


def test_the_release_commit_contains_only_managed_files(repo: Path) -> None:
    """The positive half: a clean bump commits exactly the version-bearing files.

    Guards the obvious wrong fix — a guard so strict that the real pipeline can no
    longer commit its own bump.
    """
    (repo / "CHANGELOG.md").write_text("# Changelog\n\n## 9.9.9\n", encoding="utf-8")
    managed = publish._release_managed_paths(repo)
    assert publish._unmanaged_dirty_paths(repo, managed) == []

    subprocess.run(["git", "add", "--", *managed], cwd=repo, check=True)
    staged = _git(repo, "diff", "--cached", "--name-only").split()
    assert staged == ["CHANGELOG.md"], f"expected only the changed managed file, got {staged}"
