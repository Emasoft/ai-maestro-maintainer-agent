"""
Tests for the state-path resolution helper.

Spec: skills/maintainer-guardian/references/threat-classes.md
      > "Atomic write pattern" section. The cascade is:
      1) $AGENT_WORK_DIR  2) $CLAUDE_PROJECT_DIR  3) $PWD

AGENT_WORK_DIR is the variable AI Maestro actually exports (baked into the
pane env at `tmux new-session -e` time; the directory-guard hook treats it as
the sandbox boundary). These tests previously asserted the cascade led with
$AIMAESTRO_AGENT_DIR — a name that was only ever *proposed* and is set by
nothing, so the chain always fell through to $PWD in production while this
suite stayed green. See ai-maestro#57.
"""

from __future__ import annotations

from pathlib import Path


from skill_helpers import resolve_agent_dir, state_dir


def test_state_path_prefers_agent_work_dir(tmp_path: Path) -> None:
    """$AGENT_WORK_DIR wins when set, even with the other two also set."""
    agent_work = tmp_path / "agent_work"
    claude = tmp_path / "claude"
    pwd = tmp_path / "pwd"
    for d in (agent_work, claude, pwd):
        d.mkdir()
    env = {
        "AGENT_WORK_DIR": str(agent_work),
        "CLAUDE_PROJECT_DIR": str(claude),
    }
    assert resolve_agent_dir(env=env, cwd=str(pwd)) == agent_work


def test_state_path_falls_back_to_claude_project_dir(tmp_path: Path) -> None:
    """$CLAUDE_PROJECT_DIR is used when AGENT_WORK_DIR is unset."""
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
    """An EMPTY $AGENT_WORK_DIR must NOT win — empty strings fall through.

    This matches the shell semantics `${VAR:-default}` which treats unset AND
    empty as both triggering the default. Critical for AI Maestro hosts where
    the env var is exported but blank.
    """
    claude = tmp_path / "claude"
    pwd = tmp_path / "pwd"
    for d in (claude, pwd):
        d.mkdir()
    env = {"AGENT_WORK_DIR": "", "CLAUDE_PROJECT_DIR": str(claude)}
    assert resolve_agent_dir(env=env, cwd=str(pwd)) == claude


def test_state_path_ignores_the_never_set_legacy_name(tmp_path: Path) -> None:
    """$AIMAESTRO_AGENT_DIR is NOT consulted — it is a name nothing ever sets.

    A regression guard, not a compatibility shim. If someone reintroduces the
    proposed-but-never-implemented variable into the cascade, the resolver
    would once again appear to work in tests while silently resolving to $PWD
    on a real fleet host. Setting it here must change nothing: resolution must
    still fall through to $CLAUDE_PROJECT_DIR.
    """
    claude = tmp_path / "claude"
    pwd = tmp_path / "pwd"
    for d in (claude, pwd):
        d.mkdir()
    env = {
        "AIMAESTRO_AGENT_DIR": str(tmp_path / "phantom"),
        "CLAUDE_PROJECT_DIR": str(claude),
    }
    assert resolve_agent_dir(env=env, cwd=str(pwd)) == claude


def test_state_dir_composes_aimaestro_state_subpath(tmp_path: Path) -> None:
    """state_dir() always returns <agent_dir>/.aimaestro/state."""
    agent = tmp_path / "agent"
    agent.mkdir()
    env = {"AGENT_WORK_DIR": str(agent)}
    sd = state_dir(env=env)
    assert sd == agent / ".aimaestro" / "state"
    # And it does not pre-create the directory (skill code is responsible).
    assert not sd.exists()
