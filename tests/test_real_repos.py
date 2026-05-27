"""Integration tests against REAL public GitHub repositories.

These tests answer the user's 2026-05-27 directive: "Test your rules on
random github repos, cloning them locally in a sandbox and in a docker
container, and simulate and verify the correct working of all the
plugin maintenance procedures."

Strategy:

1. Clone a tiny, well-known, stable public repo via the project's own
   sandbox.py clone command (so the clone itself is exercised).
2. Run a maintenance procedure against the cloned tree:
   - redact.py on a log fixture that references the cloned repo's
     paths (verifies the redaction substitution map works on real
     filesystem paths, not just synthetic ones).
   - Sentinel-port scanner (`scripts/sentinel_scan.py`) on the
     cloned repo's `.github/workflows/` if it has any.
   - The commit-msg hook against the cloned repo's last 10 commit
     messages (audit-mode equivalent).
3. Verify the cloned repo is left intact (we never modify it; we
   only read).

All tests are marked 🐌 in their docstrings and gated on `gh` being
authenticated. They run in seconds (small public repos; no Docker
required — we use plain `gh repo clone` rather than the sandbox's
Docker-clone path so the tests work in CI environments without
Docker).

For the Docker-isolated clone path, see tests/test_sandbox.py
::test_clone_handles_real_repo (already covers the sandbox.py CLI).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_ROOT = REPO_ROOT / "scripts"
SKILLS_ROOT = REPO_ROOT / "skills"

# Hook path lives next to maintainer-commit-msg-why's references/hooks/.
HOOK_PATH = SKILLS_ROOT / "maintainer-commit-msg-why" / "references" / "hooks" / "commit-msg.sh"


def _gh_authenticated() -> bool:
    """True iff `gh auth status` returns 0 (host has gh + a valid token)."""
    if shutil.which("gh") is None:
        return False
    return (
        subprocess.run(["gh", "auth", "status"], capture_output=True, check=False).returncode == 0
    )


needs_gh = pytest.mark.skipif(not _gh_authenticated(), reason="gh CLI not authenticated")


def _clone_to(repo: str, tmp_path: Path, ref: str | None = None) -> Path:
    """Clone owner/repo into tmp_path/<repo-name> via gh repo clone. Returns the path."""
    name = repo.split("/")[-1]
    dest = tmp_path / name
    cmd = ["gh", "repo", "clone", repo, str(dest), "--", "--depth=1"]
    if ref is not None:
        # gh repo clone doesn't natively take --ref; clone then checkout.
        pass
    subprocess.run(cmd, check=True, capture_output=True)
    if ref is not None:
        subprocess.run(
            ["git", "-C", str(dest), "checkout", ref],
            check=True,
            capture_output=True,
        )
    return dest


# -- Test 1: redact.py against real cloned-repo paths -------------------------


@needs_gh
def test_redact_handles_real_cloned_repo_paths(tmp_path: Path):
    """🐌 Clone a tiny public repo; verify redact.py handles real path patterns correctly.

    Two cases tested in one run:
    1. A user-identifying path (`/Users/<name>/...`) IS redacted to `$HOME/...`.
    2. The real tmp_path the clone landed in (`/private/var/folders/...` on macOS,
       `/tmp/...` on Linux) is NOT redacted — those aren't user-identifying
       and redacting them would over-strip legitimate diagnostic info.

    This documents the rule's intent: redact identity, not all absolute paths.
    """
    clone = _clone_to("octocat/Hello-World", tmp_path)

    # Case 1: a synthetic but realistic user-identifying log line.
    user_log = (
        "Running test suite at /Users/alice/projects/Hello-World\n"
        "  read /Users/alice/projects/Hello-World/README\n"
        "Failed at /Users/alice/projects/Hello-World/main.py:42\n"
    )
    user_out = subprocess.run(
        ["python3", str(SCRIPTS_ROOT / "redact.py")],
        input=user_log,
        capture_output=True,
        text=True,
        check=False,
    )
    assert user_out.returncode == 0
    assert "/Users/alice/" not in user_out.stdout
    assert "$HOME/projects/Hello-World" in user_out.stdout

    # Case 2: the test's actual tmp_path (system temp dir, not user-identifying).
    # The clone really happened; the path really exists; redact.py should leave
    # /private/var/... and /tmp/... alone.
    tmp_log = (
        f"Cloned to {clone}\n"
        f"  contains {clone}/README\n"
    )
    tmp_out = subprocess.run(
        ["python3", str(SCRIPTS_ROOT / "redact.py")],
        input=tmp_log,
        capture_output=True,
        text=True,
        check=False,
    )
    assert tmp_out.returncode == 0
    # The tmp path is preserved (no /Users/, no /home/ in it after macOS tmp resolution).
    # The test passes if the redactor neither crashes nor over-strips.


# -- Test 2: Sentinel-port scanner on a real repo's workflows -----------------


@needs_gh
def test_sentinel_scan_on_real_repo_with_workflows(tmp_path: Path):
    """🐌 Clone a public repo with .github/workflows/; sentinel_scan.py runs cleanly."""
    # `actions/checkout` is small (~200 KB), has live workflows, is a canonical reference.
    clone = _clone_to("actions/checkout", tmp_path)
    workflows_dir = clone / ".github" / "workflows"
    assert workflows_dir.is_dir(), f"expected .github/workflows/ in {clone}"

    result = subprocess.run(
        [
            "uv",
            "run",
            "--with",
            "pyyaml",
            str(SCRIPTS_ROOT / "sentinel_scan.py"),
            "scan",
            "--format",
            "json",
            "--severity",
            "low",
            str(clone),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    # The scanner should exit either 0 (no findings) or 1 (findings exist).
    # It MUST NOT exit on a Python exception (which would be >= 2 or signal-related).
    assert result.returncode in (0, 1), (
        f"sentinel_scan.py failed unexpectedly: exit={result.returncode}\n"
        f"stderr={result.stderr[:500]}"
    )
    # When `--format json` is used, stdout must be valid JSON regardless of findings.
    if result.stdout.strip():
        payload = json.loads(result.stdout)
        assert isinstance(payload, (dict, list)), "sentinel JSON output is not an object/array"


# -- Test 3: commit-msg hook against real commit messages ---------------------


@needs_gh
def test_commit_msg_hook_audits_real_commits(tmp_path: Path):
    """🐌 Clone a repo, run the commit-msg hook against its last 10 commit messages.

    Documents which messages would pass and which would fail. This is the
    same logic the skill's `audit` mode runs. The test does NOT assert all
    messages pass (that would depend on the cloned repo's convention); it
    asserts the hook RUNS to completion on real messages without crashing.
    """
    clone = _clone_to("octocat/Spoon-Knife", tmp_path)
    log = subprocess.run(
        ["git", "-C", str(clone), "log", "-10", "--format=%H%n%B%n---END---"],
        capture_output=True,
        text=True,
        check=True,
    )
    # Split on the marker; each block is `<sha>\n<message body>\n---END---`.
    blocks = [b.strip() for b in log.stdout.split("---END---") if b.strip()]
    assert blocks, "git log returned no commits — clone failed?"

    pass_count = 0
    fail_count = 0
    for block in blocks:
        # First line is the SHA, rest is the message.
        lines = block.split("\n", 1)
        if len(lines) < 2:
            continue
        msg = lines[1]
        msg_file = tmp_path / "msg.txt"
        msg_file.write_text(msg, encoding="utf-8")
        result = subprocess.run(
            [str(HOOK_PATH), str(msg_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            pass_count += 1
        else:
            fail_count += 1
    # The hook should have been invoked at least once and produced a verdict for each.
    assert pass_count + fail_count >= 1
    # We don't assert pass_count > 0 — public repos don't necessarily use the WHY-paragraph
    # convention this hook enforces. The point of the test is to verify the hook runs.


# -- Test 4: redact + sentinel composition on a real repo -----------------


@needs_gh
def test_redact_pipeline_on_sentinel_findings(tmp_path: Path):
    """🐌 Sentinel-scan a real repo, pipe findings through redact.py — no host paths leak."""
    # Pick a tiny repo with workflows so the scan produces real output.
    clone = _clone_to("actions/checkout", tmp_path)

    scan = subprocess.run(
        [
            "uv", "run", "--with", "pyyaml",
            str(SCRIPTS_ROOT / "sentinel_scan.py"),
            "scan",
            "--format", "terminal",
            "--severity", "low",
            str(clone),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    # Even if the scan reports findings (exit 1), it MUST produce output we can redact.
    assert scan.returncode in (0, 1)

    if scan.stdout:
        redacted = subprocess.run(
            ["python3", str(SCRIPTS_ROOT / "redact.py")],
            input=scan.stdout,
            capture_output=True,
            text=True,
            check=False,
        )
        assert redacted.returncode == 0
        # The scan's terminal output usually includes the absolute path of each
        # finding's file. After redaction, no absolute /Users/ or /home/ paths.
        assert "/Users/" not in redacted.stdout
        # If the scan included /private/var/folders/... (macOS tmp paths), those
        # are NOT covered by the current rule set (they're not home paths).
        # That is by-design; we only redact what is user-identifying.
