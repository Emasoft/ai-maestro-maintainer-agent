"""
Tests for the state-path resolution helper.

Spec: skills/maintainer-guardian/references/threat-classes.md
      > "Atomic write pattern" section. The cascade is:
      1) $AIMAESTRO_AGENT_DIR  2) $CLAUDE_PROJECT_DIR  3) $PWD
"""

from __future__ import annotations

from pathlib import Path


from skill_helpers import resolve_agent_dir, state_dir


def test_state_path_prefers_aimaestro_env(tmp_path: Path) -> None:
    """$AIMAESTRO_AGENT_DIR wins when set, even with the other two also set."""
    aimaestro = tmp_path / "aimaestro"
    claude = tmp_path / "claude"
    pwd = tmp_path / "pwd"
    for d in (aimaestro, claude, pwd):
        d.mkdir()
    env = {
        "AIMAESTRO_AGENT_DIR": str(aimaestro),
        "CLAUDE_PROJECT_DIR": str(claude),
    }
    assert resolve_agent_dir(env=env, cwd=str(pwd)) == aimaestro


def test_state_path_falls_back_to_claude_project_dir(tmp_path: Path) -> None:
    """$CLAUDE_PROJECT_DIR is used when AIMAESTRO_AGENT_DIR is unset."""
    claude = tmp_path / "claude"
    pwd = tmp_path / "pwd"
    for d in (claude, pwd):
        d.mkdir()
    env = {"CLAUDE_PROJECT_DIR": str(claude)}
    assert resolve_agent_dir(env=env, cwd=str(pwd)) == claude


def test_state_path_final_fallback_uses_cwd(tmp_path: Path) -> None:
    """With neither env var set, the cwd is the last-resort fallback."""
    pwd = tmp_path / "pwd"
    pwd.mkdir()
    assert resolve_agent_dir(env={}, cwd=str(pwd)) == pwd


def test_state_path_empty_string_treated_as_unset(tmp_path: Path) -> None:
    """An EMPTY $AIMAESTRO_AGENT_DIR must NOT win — empty strings fall through.

    This matches the shell semantics `${VAR:-default}` which treats unset AND
    empty as both triggering the default. Critical for AI Maestro hosts where
    the env var is exported but blank.
    """
    claude = tmp_path / "claude"
    pwd = tmp_path / "pwd"
    for d in (claude, pwd):
        d.mkdir()
    env = {"AIMAESTRO_AGENT_DIR": "", "CLAUDE_PROJECT_DIR": str(claude)}
    assert resolve_agent_dir(env=env, cwd=str(pwd)) == claude


def test_state_dir_composes_aimaestro_state_subpath(tmp_path: Path) -> None:
    """state_dir() always returns <agent_dir>/.aimaestro/state."""
    agent = tmp_path / "agent"
    agent.mkdir()
    env = {"AIMAESTRO_AGENT_DIR": str(agent)}
    sd = state_dir(env=env)
    assert sd == agent / ".aimaestro" / "state"
    # And it does not pre-create the directory (skill code is responsible).
    assert not sd.exists()
