"""
Tests for maintainer-guardian skill helpers.

Spec: skills/maintainer-guardian/SKILL.md
      skills/maintainer-guardian/references/threat-classes.md

Focus areas covered (6 tests):
  - T5 secret-leak regex sweep (positive + negative matching)
  - T4 protected-path last-commit-SHA capture against a real git repo
  - Atomic-write pattern for guardian-baseline.json
  - Baseline JSON shape (T1-T5 aggregation)

NO mocks — uses real git, real tmp_path, real regex.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from conftest import HAS_GIT
from skill_helpers import (
    atomic_write_json,
    last_commit_sha_for,
    scan_for_secrets,
    state_dir,
)


def test_t5_detects_aws_github_slack_secrets() -> None:
    """T5 regex sweep flags AWS / GitHub PAT / Slack tokens in commit text."""
    # Real-shape tokens (not real credentials — they don't authenticate to
    # anything). These match the documented regex patterns exactly.
    sample = "AWS key: AKIA1234567890ABCDEF in line 1\nGitHub PAT: ghp_abcdefghijklmnopqrstuvwxyz0123456789\nSlack: xoxb-stuff\n"
    hits = scan_for_secrets(sample)
    kinds = {kind for kind, _ in hits}
    assert "aws_access_key" in kinds
    assert "github_pat" in kinds
    assert "slack_token" in kinds


def test_t5_no_false_positive_on_clean_text() -> None:
    """T5 sweep returns empty on benign diff text — no false positives."""
    sample = "diff --git a/README.md b/README.md\n+ a small docs change describing AKIA (mentioning the prefix only)\n+ and a partial ghp_ token that's too short to match\n"
    # Note: the README mentions AKIA but does NOT include 16 trailing alphanums,
    # and ghp_ alone is not a full 36-char PAT shape. Both are below the regex
    # length requirement so they MUST NOT match.
    hits = scan_for_secrets(sample)
    assert hits == []


def test_t5_openai_anthropic_key_shape_detected() -> None:
    """T5 catches the sk-XXX...32 chars... shape used by OpenAI/Anthropic."""
    sample = "API_KEY=sk-abcdefghijklmnopqrstuvwxyz0123456789ABC"  # 32+ chars
    hits = scan_for_secrets(sample)
    kinds = {kind for kind, _ in hits}
    assert "openai_anthropic_key" in kinds


@pytest.mark.skipif(not HAS_GIT, reason="git binary required")
def test_t4_last_commit_sha_for_existing_path(tmp_git_repo: Path) -> None:
    """T4 detector returns a 40-char SHA for a tracked file."""
    # Add a fake protected file and commit
    wf = tmp_git_repo / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "ci.yml").write_text("name: ci\non: push\njobs: {}\n")
    subprocess.run(
        ["git", "add", ".github/workflows/ci.yml"],
        cwd=tmp_git_repo,
        check=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "add ci.yml"],
        cwd=tmp_git_repo,
        check=True,
    )
    sha = last_commit_sha_for(tmp_git_repo, ".github/workflows/ci.yml")
    assert sha is not None
    assert len(sha) == 40
    assert all(c in "0123456789abcdef" for c in sha)


@pytest.mark.skipif(not HAS_GIT, reason="git binary required")
def test_t4_last_commit_sha_for_untracked_path_is_none(tmp_git_repo: Path) -> None:
    """T4 detector returns None when the path has never been committed."""
    sha = last_commit_sha_for(tmp_git_repo, "never-existed.yml")
    assert sha is None


def test_baseline_atomic_write_replaces_previous_file(tmp_path: Path) -> None:
    """guardian-baseline.json atomic write produces the documented file at the documented path."""
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    env = {"AGENT_WORK_DIR": str(agent_dir)}
    sd = state_dir(env=env)
    target = sd / "guardian-baseline.json"

    # First write
    first_baseline = {
        "t1": {"zizmor": {"critical": 0, "high": 0, "medium": 2, "low": 0}, "actionlint": {"errors": 0}},
        "t2": {"stale_pins": 0, "dependabot_open_prs": 0},
        "t3": {"ruleset_id": None, "enforcement": "unknown"},
        "t4": {"paths": {}},
        "t5": {"matches": 0, "last_scanned_sha": None},
    }
    atomic_write_json(target, json.dumps(first_baseline))
    assert target.exists()
    assert json.loads(target.read_text())["t1"]["zizmor"]["medium"] == 2

    # Second write replaces atomically
    second_baseline = dict(first_baseline)
    second_baseline["t1"] = {"zizmor": {"critical": 0, "high": 1, "medium": 0, "low": 0}, "actionlint": {"errors": 0}}
    atomic_write_json(target, json.dumps(second_baseline))
    assert json.loads(target.read_text())["t1"]["zizmor"]["high"] == 1
    # No tmp files left behind
    leftover = list(sd.glob("guardian-baseline.json.tmp.*"))
    assert leftover == [], f"tmp file leak: {leftover}"
