"""
Shared pytest fixtures and helpers for ai-maestro-maintainer-agent tests.

No mocks. All fixtures provide REAL filesystem / subprocess interactions via
pytest's tmp_path and the host's installed binaries (git, gh, jq, python3).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_ROOT = REPO_ROOT / "scripts"
# Put scripts/ on sys.path so tests can `import sentinel` (the package at
# scripts/sentinel/) directly instead of shelling out per case.
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

SKILLS_ROOT = REPO_ROOT / "skills"
GUARDIAN_REFS = SKILLS_ROOT / "maintainer-guardian" / "references"
APPROVAL_REFS = SKILLS_ROOT / "maintainer-approval-gate" / "references"
BOOTSTRAP_REFS = SKILLS_ROOT / "workflow-bootstrap" / "references"
FIXSAFE_REFS = SKILLS_ROOT / "workflow-fix-safe" / "references"


def _has_binary(name: str) -> bool:
    """Return True iff the host has the named binary on PATH."""
    return shutil.which(name) is not None


HAS_GIT = _has_binary("git")
HAS_GH = _has_binary("gh")
HAS_JQ = _has_binary("jq")
HAS_UVX = _has_binary("uvx")
HAS_PYTHON3 = _has_binary("python3")


def _gh_authenticated() -> bool:
    """True iff `gh auth status` exits 0."""
    if not HAS_GH:
        return False
    try:
        r = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, timeout=15)
        return r.returncode == 0
    except Exception:
        return False


GH_AUTHENTICATED = _gh_authenticated()


@pytest.fixture
def tmp_git_repo(tmp_path: Path) -> Path:
    """A real git repo in tmp_path with one initial commit on branch `main`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    # Configure git user locally; use the public NOREPLY pair from CLAUDE.md.
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Emasoft"
    env["GIT_AUTHOR_EMAIL"] = "713559+Emasoft@users.noreply.github.com"
    env["GIT_COMMITTER_NAME"] = "Emasoft"
    env["GIT_COMMITTER_EMAIL"] = "713559+Emasoft@users.noreply.github.com"
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True, env=env)
    subprocess.run(
        ["git", "config", "user.email", "713559+Emasoft@users.noreply.github.com"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Emasoft"], cwd=repo, check=True)
    (repo / "README.md").write_text("# tmp repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True, env=env)
    return repo


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear AIMAESTRO_AGENT_DIR + CLAUDE_PROJECT_DIR so state-path tests start clean."""
    monkeypatch.delenv("AIMAESTRO_AGENT_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a command, capture output, never raise on non-zero."""
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
