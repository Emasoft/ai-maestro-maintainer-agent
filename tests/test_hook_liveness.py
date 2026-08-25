"""Guardian T7 hook-liveness detector (TRDD-G88RIN1C) — real repos, no mocks.

Every test builds a real git repository and asks the detector what git would
actually execute there. The positive control is the load-bearing one: a
detector that cannot flag a known-DECORATIVE fixture, or that reddens on a
correctly-wired one, measures nothing — the exact defect class this card is
about (the retracted census printed `live=no` by construction, for any input).
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "hook_liveness.py"


def _run(repo: Path) -> dict:
    """Run the detector CLI on a repo and parse its JSON report."""
    out = subprocess.run(
        [sys.executable, str(SCRIPT), str(repo)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return json.loads(out)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def isolated_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Cut fixture repos off from the HOST's global git config.

    This machine (like any with `git lfs install`) sets a global
    core.hooksPath, so a fixture repo with no local override would resolve its
    hooks to the host's global dir — the INHERITED state the detector exists
    to measure, but nondeterministic across hosts. Tests of the detector's own
    logic pin an empty global config; the deprived test builds its own.
    """
    empty = tmp_path / "gitconfig-empty"
    empty.write_text("")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(empty))


def _mkrepo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.name", "test")
    _git(path, "config", "user.email", "test@example.invalid")
    return path


def _ship_hook(repo: Path, rel: str) -> Path:
    """Track an executable hook file at rel and commit it."""
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("#!/bin/sh\nexit 0\n")
    p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", f"ship {rel}")
    return p


@pytest.mark.usefixtures("isolated_git")
def test_positive_control_decorative_is_flagged(tmp_path: Path) -> None:
    """A shipped hook git never resolves MUST be reported DECORATIVE.

    This is the AI-MAESTRO-WEBDESIGN-AGENT shape: ships .githooks/pre-push
    while core.hooksPath names a DIFFERENT directory — the reviewed file is
    not the executed file, and nothing else reports it.
    """
    repo = _mkrepo(tmp_path / "decorative")
    _ship_hook(repo, ".githooks/pre-push")
    (repo / "git-hooks").mkdir()
    _git(repo, "config", "core.hooksPath", "git-hooks")
    report = _run(repo)
    states = {h["hook"]: h["state"] for h in report["shipped_hooks"]}
    assert states == {"pre-push": "DECORATIVE"}


@pytest.mark.usefixtures("isolated_git")
def test_correctly_wired_hook_is_live_never_flagged(tmp_path: Path) -> None:
    """A guard that reddens on correct configuration gets deleted — so the
    correctly-wired twin of the positive control MUST report LIVE."""
    repo = _mkrepo(tmp_path / "live")
    _ship_hook(repo, ".githooks/pre-push")
    _git(repo, "config", "core.hooksPath", ".githooks")
    report = _run(repo)
    states = {h["hook"]: h["state"] for h in report["shipped_hooks"]}
    assert states == {"pre-push": "LIVE"}


@pytest.mark.usefixtures("isolated_git")
def test_absolute_hookspath_is_never_concatenated(tmp_path: Path) -> None:
    """core.hooksPath is frequently ABSOLUTE; string-concatenating it with the
    repo root yields a path that cannot exist, and every branch then reports
    'not live' for any input — the exact bug behind the retracted census. A
    hook shipped OUTSIDE the assumed directories (scripts/hooks/) must also be
    discovered, not missed by a directory assumption."""
    repo = _mkrepo(tmp_path / "abs")
    shipped = _ship_hook(repo, "scripts/hooks/pre-push")
    _git(repo, "config", "core.hooksPath", str(shipped.parent))
    report = _run(repo)
    states = {h["hook"]: h["state"] for h in report["shipped_hooks"]}
    assert states == {"pre-push": "LIVE"}


@pytest.mark.usefixtures("isolated_git")
def test_shadowed_leftover_in_default_dir_is_reported(tmp_path: Path) -> None:
    """core.hooksPath REPLACES .git/hooks, so a leftover executable there is
    ignored by git — harmless to execution, actively misleading to inspection."""
    repo = _mkrepo(tmp_path / "shadowed")
    _ship_hook(repo, ".githooks/pre-push")
    _git(repo, "config", "core.hooksPath", ".githooks")
    leftover = repo / ".git" / "hooks" / "pre-push"
    leftover.parent.mkdir(parents=True, exist_ok=True)
    leftover.write_text("#!/bin/sh\nexit 0\n")
    leftover.chmod(0o755)
    report = _run(repo)
    assert report["shadowed_in_default_dir"] == ["pre-push"]


@pytest.mark.usefixtures("isolated_git")
def test_sample_files_are_never_counted(tmp_path: Path) -> None:
    """A default .git/hooks ships executable .sample files; counting them
    over-reports by the whole set. With no hooksPath and only samples, the
    resolved dir must enumerate empty and nothing is shadowed."""
    repo = _mkrepo(tmp_path / "samples")
    (repo / "f.txt").write_text("x\n")
    _git(repo, "add", "f.txt")
    _git(repo, "commit", "-q", "-m", "init")
    sample = repo / ".git" / "hooks" / "pre-push.sample"
    sample.parent.mkdir(parents=True, exist_ok=True)
    sample.write_text("#!/bin/sh\nexit 0\n")
    sample.chmod(0o755)
    report = _run(repo)
    assert report["resolved_executables"] == []
    assert report["shadowed_in_default_dir"] == []


def test_deprived_reports_loss_only_with_usage_signal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing hook is a LOSS only where the hook had work: an LFS hook lost
    to a local hooksPath override matters only in a repo with filter=lfs
    patterns. Reported otherwise, the check files benign absence as breakage
    in every repo that never used the feature — and gets muted."""
    global_hooks = tmp_path / "global-hooks"
    global_hooks.mkdir()
    gh = global_hooks / "post-checkout"
    gh.write_text("#!/bin/sh\nexit 0\n")
    gh.chmod(0o755)
    gcfg = tmp_path / "gitconfig-global"
    gcfg.write_text(f"[core]\n\thooksPath = {global_hooks}\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gcfg))

    repo = _mkrepo(tmp_path / "deprived")
    _ship_hook(repo, ".githooks/pre-push")
    _git(repo, "config", "core.hooksPath", ".githooks")

    # No LFS usage: the absence is an observation, never a loss.
    report = _run(repo)
    deprived = {d["hook"]: d for d in report["deprived"]}
    assert "post-checkout" in deprived
    assert deprived["post-checkout"]["loss"] is False

    # With a tracked filter=lfs pattern the same absence becomes a loss.
    (repo / ".gitattributes").write_text("*.bin filter=lfs diff=lfs merge=lfs\n")
    _git(repo, "add", ".gitattributes")
    _git(repo, "commit", "-q", "-m", "track lfs pattern")
    report = _run(repo)
    deprived = {d["hook"]: d for d in report["deprived"]}
    assert deprived["post-checkout"]["loss"] is True


def test_this_repo_is_classified_and_the_expectation_is_measured() -> None:
    """The detector runs against THIS repo on every test run, and the expected
    state is computed from what git actually resolves here — LIVE on a wired
    dev machine, DECORATIVE on a fresh clone whose local hooksPath was never
    set (which is the true state of such a clone, not a false alarm)."""
    report = _run(REPO)
    shipped = {h["shipped_at"]: h for h in report["shipped_hooks"]}
    assert ".githooks/pre-push" in shipped, "this repo no longer ships its pre-push guard?"
    resolved = Path(
        subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "--path-format=absolute", "--git-path", "hooks"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    expected = "LIVE" if resolved.resolve() == (REPO / ".githooks").resolve() else "DECORATIVE"
    assert shipped[".githooks/pre-push"]["state"] == expected


def test_non_repo_exits_2(tmp_path: Path) -> None:
    """A detector that cannot measure must say so, never report clean."""
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(tmp_path)}
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), str(plain)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 2
