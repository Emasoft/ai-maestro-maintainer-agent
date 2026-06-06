"""
Tests for maintainer-approval-gate skill helpers.

Spec: skills/maintainer-approval-gate/SKILL.md
      skills/maintainer-approval-gate/references/protected-paths.md

Focus areas:
  - Protected-path glob matching for the canonical list
  - Per-repo override file loading
  - VERIFY-mode classify_approval semantics (D2 fingerprint-bound):
      * authorized approve WITH current fingerprint → ok
      * authorized reject → rejected (wins over approve)
      * non-authorized approve → pending (impostor rejected silently)
      * authorized approve with STALE fingerprint → pending (replay-proof)
      * authorized approve with NO fingerprint → pending (fail-closed)
  - diff_fingerprint matches real `git hash-object` (D2)
  - Canonical glob list is parseable from the markdown reference
"""

from __future__ import annotations

import subprocess

from skill_helpers import (
    CANONICAL_PROTECTED_GLOBS,
    classify_approval,
    diff_fingerprint,
    matches_protected,
    parse_protected_globs,
    planned_diff_hits,
)

# A representative 12-char fingerprint used across the classify_approval tests.
_FP = "a1b2c3d4e5f6"


def test_protected_glob_matches_workflows_recursively() -> None:
    """`.github/workflows/**` matches files at any depth under that prefix."""
    hits = matches_protected(".github/workflows/validate.yml", CANONICAL_PROTECTED_GLOBS)
    assert ".github/workflows/**" in hits

    # A subdirectory (nested workflow include) also matches.
    hits_deep = matches_protected(".github/workflows/release/publish.yml", CANONICAL_PROTECTED_GLOBS)
    assert ".github/workflows/**" in hits_deep


def test_protected_glob_does_not_match_unrelated_files() -> None:
    """README.md and src/lib.py are not on the protected list."""
    assert matches_protected("README.md", CANONICAL_PROTECTED_GLOBS) == []
    assert matches_protected("src/lib.py", CANONICAL_PROTECTED_GLOBS) == []
    assert matches_protected("tests/test_foo.py", CANONICAL_PROTECTED_GLOBS) == []


def test_protected_glob_matches_exact_filenames() -> None:
    """Exact-name globs catch LICENSE / .gitignore / scripts/publish.py."""
    assert "LICENSE" in matches_protected("LICENSE", CANONICAL_PROTECTED_GLOBS)
    assert ".gitignore" in matches_protected(".gitignore", CANONICAL_PROTECTED_GLOBS)
    assert "scripts/publish.py" in matches_protected("scripts/publish.py", CANONICAL_PROTECTED_GLOBS)


def test_protected_glob_matches_agents_pattern() -> None:
    """`agents/**/*.md` matches an agent definition file."""
    hits = matches_protected("agents/maintainer/spec.md", CANONICAL_PROTECTED_GLOBS)
    assert "agents/**/*.md" in hits


def test_per_repo_override_parses_one_glob_per_line_with_comments() -> None:
    """parse_protected_globs ignores blank lines and # comments."""
    override = """
# This is a comment
src/auth/**

# Another comment
config/secrets-policy.yaml
   # indented comment is still a comment
"""
    parsed = parse_protected_globs(override)
    assert parsed == ["src/auth/**", "config/secrets-policy.yaml"]


def test_classify_approval_authorized_user_approve_with_fingerprint_returns_ok() -> None:
    """approve-protected-edit + the CURRENT fingerprint by AUTHORIZED_USER → 'ok'."""
    comments = [
        {"author": {"login": "someone-else"}, "body": "looks good!"},
        {"author": {"login": "Emasoft"}, "body": f"yes — approve-protected-edit {_FP}, see #41"},
    ]
    assert classify_approval(comments, "Emasoft", _FP) == "ok"


def test_classify_approval_authorized_reject_wins_over_approve() -> None:
    """reject-protected-edit by AUTHORIZED_USER overrides any approval (no fp needed)."""
    comments = [
        {"author": {"login": "Emasoft"}, "body": f"approve-protected-edit {_FP}"},
        {"author": {"login": "Emasoft"}, "body": "wait — reject-protected-edit"},
    ]
    assert classify_approval(comments, "Emasoft", _FP) == "rejected"


def test_classify_approval_impostor_approve_returns_pending() -> None:
    """Approval phrase + fingerprint by NON-authorized user → pending (impostor)."""
    comments = [
        {"author": {"login": "random-drive-by"}, "body": f"approve-protected-edit {_FP}"},
    ]
    assert classify_approval(comments, "Emasoft", _FP) == "pending"


def test_classify_approval_stale_fingerprint_returns_pending() -> None:
    """D2: an approval bound to a DIFFERENT (stale) fingerprint → pending, never ok.

    Models a re-scoped fix: the user approved an earlier diff, but the live
    fingerprint has since changed. The stale approval must not release the gate.
    """
    comments = [
        {"author": {"login": "Emasoft"}, "body": "approve-protected-edit 0000deadbeef"},
    ]
    assert classify_approval(comments, "Emasoft", _FP) == "pending"


def test_classify_approval_bare_approval_without_fingerprint_returns_pending() -> None:
    """D2: the phrase ALONE (no fingerprint) is fail-closed → pending, never ok."""
    comments = [
        {"author": {"login": "Emasoft"}, "body": "approve-protected-edit"},
    ]
    assert classify_approval(comments, "Emasoft", _FP) == "pending"


def test_diff_fingerprint_matches_real_git_hash_object() -> None:
    """D2: diff_fingerprint reproduces `git hash-object --stdin | cut -c1-12` exactly.

    No mock — pipes the same bytes through the real git binary and compares.
    """
    sample = "diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -1 +1 @@\n-old\n+new\n"
    proc = subprocess.run(
        ["git", "hash-object", "--stdin"],
        input=sample.encode(),
        capture_output=True,
        check=True,
    )
    git_short = proc.stdout.decode().strip()[:12]
    assert diff_fingerprint(sample) == git_short


def test_diff_fingerprint_changes_when_diff_changes() -> None:
    """D2: a different planned diff yields a different fingerprint (the whole point)."""
    fp_a = diff_fingerprint("@@ -1 +1 @@\n-a\n+b\n")
    fp_b = diff_fingerprint("@@ -1 +2 @@\n-a\n+b\n+c\n")
    assert fp_a != fp_b
    assert len(fp_a) == 12 and len(fp_b) == 12


def test_planned_diff_hits_intersects_two_protected_paths() -> None:
    """planned_diff_hits returns every planned path that matches any glob."""
    planned = [
        "src/lib.py",
        ".github/workflows/validate.yml",
        "README.md",
        "scripts/publish.py",
    ]
    hits = planned_diff_hits(planned, CANONICAL_PROTECTED_GLOBS)
    assert ".github/workflows/validate.yml" in hits
    assert "scripts/publish.py" in hits
    assert "src/lib.py" not in hits
    assert "README.md" not in hits
