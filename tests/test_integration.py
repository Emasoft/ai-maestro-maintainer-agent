"""
Integration / cross-skill tests.

These tests exercise multi-skill flows end-to-end using real binaries:
  - Real `gh` CLI to verify the authenticated user is reachable.
  - Real `git` against a tmp repo to verify the T4 detector + planned-diff
    pipeline composes correctly with the protected-paths matcher.
  - Real reading of skill markdown files to verify documented invariants.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from conftest import (
    GH_AUTHENTICATED,
    HAS_GH,
    HAS_GIT,
    SKILLS_ROOT,
    run,
)
from skill_helpers import (
    CANONICAL_PROTECTED_GLOBS,
    last_commit_sha_for,
    planned_diff_hits,
)


@pytest.mark.skipif(
    not (HAS_GH and GH_AUTHENTICATED),
    reason="gh CLI must be authenticated for this test",
)
def test_gh_auth_returns_authorized_user_login() -> None:
    """`gh api user --jq .login` returns a non-empty username — fuels $AUTHORIZED_USER."""
    r = run(["gh", "api", "user", "--jq", ".login"], timeout=20)
    assert r.returncode == 0, f"gh failed: {r.stderr}"
    login = r.stdout.strip()
    assert login, "empty login from gh api user"
    # The username should match what the CLAUDE.md user identity expects.
    assert login == "Emasoft"


@pytest.mark.skipif(not HAS_GIT, reason="git binary required")
def test_t4_protected_path_change_detected_across_commits(
    tmp_git_repo: Path,
) -> None:
    """
    Two commits change the same protected path → the SHA captured at baseline
    differs from the SHA captured at scan, so T4 fires.
    """
    # Add a protected file and commit (baseline)
    wf = tmp_git_repo / ".github" / "workflows"
    wf.mkdir(parents=True)
    target = wf / "validate.yml"
    target.write_text("name: validate\non: push\njobs: {}\n")
    subprocess.run(
        ["git", "add", str(target.relative_to(tmp_git_repo))],
        cwd=tmp_git_repo,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "init validate.yml"],
        cwd=tmp_git_repo,
        check=True,
    )
    sha_baseline = last_commit_sha_for(tmp_git_repo, ".github/workflows/validate.yml")

    # Modify the protected file and commit again (scan time)
    target.write_text("name: validate\non: push\njobs:\n  v:\n    runs-on: ubuntu-latest\n")
    subprocess.run(
        ["git", "add", str(target.relative_to(tmp_git_repo))],
        cwd=tmp_git_repo,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "update validate.yml"],
        cwd=tmp_git_repo,
        check=True,
    )
    sha_scan = last_commit_sha_for(tmp_git_repo, ".github/workflows/validate.yml")

    assert sha_baseline is not None
    assert sha_scan is not None
    assert sha_baseline != sha_scan, "T4 must detect a SHA change"


@pytest.mark.skipif(not HAS_GIT, reason="git binary required")
def test_planned_diff_intersection_against_real_git_tree(
    tmp_git_repo: Path,
) -> None:
    """
    Plant changes touching one protected file + one normal file.
    Compute `git diff --name-only HEAD`; verify planned_diff_hits returns
    only the protected one.
    """
    # Stage a protected change (LICENSE)
    (tmp_git_repo / "LICENSE").write_text("MIT-ish\n")
    # And a non-protected change (src/foo.py)
    (tmp_git_repo / "src").mkdir()
    (tmp_git_repo / "src" / "foo.py").write_text("def x(): pass\n")

    # Compute the planned diff exactly as the SKILL doc says:
    # `git diff --name-only HEAD --`
    r = run(["git", "add", "-N", "LICENSE", "src/foo.py"], cwd=tmp_git_repo)
    assert r.returncode == 0, r.stderr
    r = run(["git", "diff", "--name-only", "HEAD", "--"], cwd=tmp_git_repo)
    assert r.returncode == 0, r.stderr
    planned = [ln for ln in r.stdout.splitlines() if ln.strip()]

    hits = planned_diff_hits(planned, CANONICAL_PROTECTED_GLOBS)
    assert "LICENSE" in hits
    assert "src/foo.py" not in hits


def test_all_skill_md_files_have_yaml_frontmatter() -> None:
    """
    Every SKILL.md in skills/ must start with a YAML frontmatter block —
    Claude Code's skill loader requires it. Catches regressions where a
    new skill ships without the `description:` field.
    """
    skill_files = list(SKILLS_ROOT.glob("*/SKILL.md"))
    assert skill_files, "no skill markdown files found"
    for f in skill_files:
        text = f.read_text()
        first_line = text.splitlines()[0] if text else ""
        assert first_line == "---", f"missing frontmatter open in {f}"
        # And the `description:` field is present.
        assert "description:" in text.split("---")[1], f"missing description in {f}"
