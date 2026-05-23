"""
Tests for maintainer-approval-gate skill helpers.

Spec: skills/maintainer-approval-gate/SKILL.md
      skills/maintainer-approval-gate/references/protected-paths.md

Focus areas (6 tests):
  - Protected-path glob matching for the canonical list
  - Per-repo override file loading
  - VERIFY-mode classify_approval semantics:
      * authorized approve → ok
      * authorized reject → rejected (wins over approve)
      * non-authorized approve → pending (impostor rejected silently)
      * reject + approve order → reject still wins
  - Canonical glob list is parseable from the markdown reference
"""

from __future__ import annotations


from skill_helpers import (
    CANONICAL_PROTECTED_GLOBS,
    classify_approval,
    matches_protected,
    parse_protected_globs,
    planned_diff_hits,
)


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


def test_classify_approval_authorized_user_approve_returns_ok() -> None:
    """An approve-protected-edit comment by AUTHORIZED_USER → 'ok'."""
    comments = [
        {"author": {"login": "someone-else"}, "body": "looks good!"},
        {"author": {"login": "Emasoft"}, "body": "yes — approve-protected-edit, see #41"},
    ]
    assert classify_approval(comments, "Emasoft") == "ok"


def test_classify_approval_authorized_reject_wins_over_approve() -> None:
    """reject-protected-edit by AUTHORIZED_USER overrides any approval."""
    comments = [
        {"author": {"login": "Emasoft"}, "body": "approve-protected-edit"},
        {"author": {"login": "Emasoft"}, "body": "wait — reject-protected-edit"},
    ]
    assert classify_approval(comments, "Emasoft") == "rejected"


def test_classify_approval_impostor_approve_returns_pending() -> None:
    """Approval phrase by NON-authorized user is rejected silently → pending."""
    comments = [
        {"author": {"login": "random-drive-by"}, "body": "approve-protected-edit"},
    ]
    assert classify_approval(comments, "Emasoft") == "pending"


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
