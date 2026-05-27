"""Tests for the maintainer-commit-msg-why bash hook.

The hook lives at
`skills/maintainer-commit-msg-why/references/hooks/commit-msg.sh` and
is installed into the entrusted repo's `.git/hooks/commit-msg`. Each
test invokes the hook directly against a temporary file holding a
candidate commit message and asserts the exit code.

The hook is pure bash + grep — no Docker, no external deps. Tests
run in milliseconds.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

HOOK_PATH = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "maintainer-commit-msg-why"
    / "references"
    / "hooks"
    / "commit-msg.sh"
)


def _run_hook(commit_msg: str, tmp_path: Path, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Write commit_msg to a tmp file + invoke the hook with that path as argv[1]."""
    msg_file = tmp_path / "COMMIT_EDITMSG"
    msg_file.write_text(commit_msg, encoding="utf-8")

    # The hook is in the SOURCE tree — make sure it's executable for the test.
    HOOK_PATH.chmod(HOOK_PATH.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    full_env = {**os.environ}
    if env:
        full_env.update(env)

    return subprocess.run(
        [str(HOOK_PATH), str(msg_file)],
        capture_output=True,
        text=True,
        check=False,
        env=full_env,
    )


# -- happy-path tests ---------------------------------------------------------


def test_hook_accepts_valid_conventional_commit_with_why_paragraph(tmp_path: Path) -> None:
    """A well-formed conventional commit with a WHY paragraph in body passes."""
    msg = (
        "fix(scanner): handle empty input gracefully\n"
        "\n"
        "The scanner crashed on empty input because the regex assumed\n"
        "at least one match. Why: empty inputs are valid (e.g. a freshly\n"
        "scaffolded repo with no workflows yet); crashing on them blocks\n"
        "the Guardian's first baseline.\n"
    )
    result = _run_hook(msg, tmp_path)
    assert result.returncode == 0, f"unexpected exit: stderr={result.stderr}"


def test_hook_accepts_chore_with_rationale_keyword(tmp_path: Path) -> None:
    """A chore commit with the WHY marker "rationale" in the body passes."""
    msg = (
        "chore(deps): bump zizmor 1.25.0 -> 1.25.2\n"
        "\n"
        "Picks up the false-positive fix for excessive-permissions in\n"
        "matrix jobs.\n"
        "\n"
        "Rationale: our matrix CI was getting flagged on every PR; the\n"
        "upstream fix lands cleanly with no breaking changes.\n"
    )
    assert _run_hook(msg, tmp_path).returncode == 0


def test_hook_accepts_docs_with_context_keyword(tmp_path: Path) -> None:
    """`context:` counts as a WHY marker."""
    msg = (
        "docs: clarify the approval-gate semantics\n"
        "\n"
        "The previous wording made it sound like the gate ran AFTER the\n"
        "commit; it actually runs BEFORE.\n"
        "\n"
        "Context: a contributor opened issue #88 confused about the\n"
        "ordering. The clarification prevents future similar confusion.\n"
    )
    assert _run_hook(msg, tmp_path).returncode == 0


# -- subject-line gate failures -----------------------------------------------


def test_hook_rejects_missing_type_prefix(tmp_path: Path) -> None:
    """A subject without `type(scope):` prefix is rejected."""
    msg = (
        "just a casual message here\n"
        "\n"
        "There's a body, and the body talks about why this matters.\n"
    )
    result = _run_hook(msg, tmp_path)
    assert result.returncode != 0
    assert "subject" in result.stderr.lower() or "conventional" in result.stderr.lower()


def test_hook_rejects_invalid_type(tmp_path: Path) -> None:
    """A subject with a non-canonical type is rejected."""
    msg = (
        "wibble(scanner): does something\n"
        "\n"
        "Body explains why this is needed.\n"
    )
    result = _run_hook(msg, tmp_path)
    assert result.returncode != 0


def test_hook_rejects_overlong_subject(tmp_path: Path) -> None:
    """Subjects > 70 chars are rejected."""
    long_subject = "fix(scanner): " + ("x" * 80)  # > 70 chars total
    msg = f"{long_subject}\n\nWhy: long subjects are hard to read in git log.\n"
    result = _run_hook(msg, tmp_path)
    assert result.returncode != 0


# -- body gate failures -------------------------------------------------------


def test_hook_rejects_missing_body(tmp_path: Path) -> None:
    """A subject-only commit (no body) is rejected — no WHY paragraph."""
    msg = "fix(scanner): handle empty input\n"
    result = _run_hook(msg, tmp_path)
    assert result.returncode != 0


def test_hook_rejects_body_without_why_marker(tmp_path: Path) -> None:
    """A body that doesn't contain any of {why, rationale, context, reason, because} is rejected."""
    msg = (
        "fix(scanner): handle empty input\n"
        "\n"
        "Updated the regex to allow zero matches. Added a unit test.\n"
        "Also reformatted the comment block.\n"
    )
    result = _run_hook(msg, tmp_path)
    assert result.returncode != 0
    assert "why" in result.stderr.lower() or "rationale" in result.stderr.lower()


# -- bypass tests -------------------------------------------------------------


def test_hook_respects_bypass_env_var(tmp_path: Path) -> None:
    """COMMIT_MSG_HOOK_BYPASS=1 lets a bad message through but logs to stderr."""
    msg = "wibble: a message that would normally fail\n"
    result = _run_hook(msg, tmp_path, env={"COMMIT_MSG_HOOK_BYPASS": "1"})
    assert result.returncode == 0
    # The hook should log the bypass to stderr for the audit script to find.
    assert "bypass" in result.stderr.lower()


def test_hook_no_bypass_by_default(tmp_path: Path) -> None:
    """Without the env var, a bad commit is still rejected (no silent acceptance)."""
    msg = "wibble: same bad message\n"
    # Note: explicitly remove the env var if it happens to be set in the parent shell.
    env = {k: v for k, v in os.environ.items() if k != "COMMIT_MSG_HOOK_BYPASS"}
    result = subprocess.run(
        [str(HOOK_PATH), str(tmp_path / "msg")],
        input=msg,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    # Either argv path or stdin path: the hook reads from argv[1]; write the
    # file so the hook can read it.
    msg_path = tmp_path / "msg"
    msg_path.write_text(msg, encoding="utf-8")
    result = subprocess.run(
        [str(HOOK_PATH), str(msg_path)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode != 0


# -- comment-stripping tests --------------------------------------------------


def test_hook_ignores_comment_lines(tmp_path: Path) -> None:
    """Lines starting with `#` are stripped before validation (git's editor convention)."""
    msg = (
        "fix(scanner): handle empty input\n"
        "\n"
        "# This is a comment from `git commit` that should be ignored\n"
        "# Please enter the commit message for your changes. Lines starting\n"
        "# with '#' will be ignored, and an empty message aborts the commit.\n"
        "\n"
        "Body explains the why: empty inputs are valid, the scanner just\n"
        "wasn't handling that case.\n"
    )
    result = _run_hook(msg, tmp_path)
    assert result.returncode == 0
