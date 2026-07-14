"""
Regression tests for required-status-check CONTEXT derivation in the
workflow-protect-branch skill.

Why this file exists: the skill auto-detects which CI checks to mark required in
the `baseline-pr-and-checks` ruleset. It used to emit the job KEY as the context.
GitHub names a check run after the job's `name:` when one is set (falling back to
the key only when absent), and required-check contexts are matched
CASE-SENSITIVELY. So a job

    validate:
      name: Validate

reports the context `Validate`, while the ruleset required `validate` — a check
that never arrives. With `strict_required_status_checks_policy` that does not
merely weaken the gate, it makes EVERY pull request in the repo permanently
unmergeable, while the PR page cheerfully shows all checks green.

That is exactly what happened to this plugin: four dependabot PRs sat unmergeable
for weeks. The bug is worse than a local annoyance because this skill APPLIES the
baseline to every entrusted downstream repo — one wrong field would strand all of
them the same way.

These tests run the REAL recipe, extracted verbatim from the shipped SKILL
reference, against REAL workflow files on disk. Nothing is mocked and the logic is
not copied — if someone edits the recipe in the markdown, these tests execute the
edited version, which is the only way a doc-embedded script can actually be gated.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SKILL_DOC = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "workflow-protect-branch"
    / "references"
    / "instructions.md"
)


def _extract_recipe() -> str:
    """Pull the python snippet the skill actually ships out of the markdown.

    The recipe lives inside  CHECKS_JSON="$(python3 -c " ... ")"  — we take the
    body so the tests exercise the shipped text rather than a copy of it that
    could silently drift away from what the skill runs.
    """
    doc = SKILL_DOC.read_text(encoding="utf-8")
    m = re.search(r'CHECKS_JSON="\$\(python3 -c "\n(.*?)\n"\)"', doc, re.DOTALL)
    assert m, "could not locate the CHECKS_JSON python recipe in the skill doc"
    return m.group(1)


def _run_recipe(repo: Path) -> tuple[list[str], str]:
    """Execute the recipe with `repo` as cwd. Returns (contexts, stderr)."""
    proc = subprocess.run(
        [sys.executable, "-c", _extract_recipe()],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )
    return [c["context"] for c in json.loads(proc.stdout)], proc.stderr


def _write_workflow(repo: Path, name: str, body: str) -> None:
    d = repo / ".github" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


def test_context_is_the_job_name_when_the_job_declares_one(repo: Path) -> None:
    """A job with `name:` yields that NAME as the context — not its key.

    This is the exact bug that made every PR in this repo unmergeable.
    """
    _write_workflow(
        repo,
        "ci.yml",
        "on:\n  pull_request:\njobs:\n  validate:\n    name: Validate\n    runs-on: ubuntu-latest\n    steps:\n      - run: 'true'\n",
    )
    contexts, _ = _run_recipe(repo)
    assert contexts == ["Validate"]
    assert "validate" not in contexts, "emitted the job KEY — the check would never report"


def test_context_falls_back_to_the_job_key_when_no_name_is_declared(repo: Path) -> None:
    """A job with no `name:` reports under its key, so the key is the right context."""
    _write_workflow(
        repo,
        "ci.yml",
        "on:\n  pull_request:\njobs:\n  workflow-security:\n    runs-on: ubuntu-latest\n    steps:\n      - run: 'true'\n",
    )
    contexts, _ = _run_recipe(repo)
    assert contexts == ["workflow-security"]


def test_context_derivation_is_case_sensitive(repo: Path) -> None:
    """The emitted context must match the declared name EXACTLY.

    GitHub compares contexts case-sensitively; a lowercased `validate` against a
    reported `Validate` is the silent deadlock this whole file exists to prevent.
    """
    _write_workflow(
        repo,
        "ci.yml",
        "on:\n  pull_request:\njobs:\n  test-gate:\n    name: Test\n    runs-on: ubuntu-latest\n    steps:\n      - run: 'true'\n",
    )
    contexts, _ = _run_recipe(repo)
    assert contexts == ["Test"]
    assert contexts != ["test"]


def test_matrix_jobs_are_skipped_and_the_skip_is_announced(repo: Path) -> None:
    """A matrix job is omitted from the required set, loudly.

    Its check runs are named per-combination — `Test matrix (ubuntu-latest)` —
    so no single context can be required. Requiring the bare name would deadlock
    the branch, so the fail-safe is to skip and say so, never to guess.
    """
    _write_workflow(
        repo,
        "ci.yml",
        "on:\n  pull_request:\njobs:\n"
        "  test:\n    name: Test matrix\n    runs-on: ${{ matrix.os }}\n"
        "    strategy:\n      matrix:\n        os: [ubuntu-latest, macos-latest]\n"
        "    steps:\n      - run: 'true'\n"
        "  validate:\n    name: Validate\n    runs-on: ubuntu-latest\n    steps:\n      - run: 'true'\n",
    )
    contexts, stderr = _run_recipe(repo)
    assert contexts == ["Validate"], "the matrix job must not become a required context"
    assert "Test matrix" not in contexts
    assert "skipping matrix job" in stderr, "a silent skip would narrow the gate invisibly"


def test_push_only_workflows_contribute_no_contexts(repo: Path) -> None:
    """A push-only job never reports on a PR, so requiring it would deadlock too."""
    _write_workflow(
        repo,
        "release.yml",
        "on:\n  push:\n    tags: ['v*']\njobs:\n  publish:\n    name: Publish\n    runs-on: ubuntu-latest\n    steps:\n      - run: 'true'\n",
    )
    contexts, _ = _run_recipe(repo)
    assert contexts == []


def test_the_live_workflows_derive_exactly_the_contexts_github_reports() -> None:
    """End-to-end against THIS repo's real workflows.

    These five strings are the check-run names GitHub actually reports on a PR
    here (observed on PRs #21/#22/#23/#25). If the derivation drifts from what
    GitHub reports, the ruleset silently stops being satisfiable — so pin it.
    """
    repo_root = Path(__file__).resolve().parents[1]
    contexts, _ = _run_recipe(repo_root)
    assert "Validate" in contexts
    assert "workflow-security" in contexts
    # the job KEY of a named job must never appear
    assert "validate" not in contexts
    assert "test-gate" not in contexts
    # the matrix job is skipped, under neither its key nor its bare name
    assert "test" not in contexts
    assert "Test matrix" not in contexts
