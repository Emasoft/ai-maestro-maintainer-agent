"""
Containment invariants for an ENTRUSTED repo — rows B2, B4 and B5 of the joint
migration test plan (ai-maestro#27).

Context that makes these worth having: the migration adopts each existing project
folder under ~/Code AS the MAINTAINER agent's working directory. That repo is not
a scratch checkout — it is someone's real project, and it already has its own
`.claude/`, its own `CLAUDE.md`, its own `settings.local.json` and its own git
history. Three invariants follow, and none of them was tested before this file:

  B2  Adoption must not CLOBBER the repo's own Claude configuration.
  B4  The agent must not write outside its workdir (+ /tmp).
  B5  Reports go to $MAIN_ROOT/reports/<component>/ with a local-time+offset stamp.

All three currently HOLD. That is exactly why they are worth pinning: an invariant
that is true by habit rather than by test is one careless skill away from being
false, and the failure would land in a user's real repository — silently, because
nothing else checks.

These tests read the SHIPPED artifacts (skills, commands, agents, scripts, hooks),
which are the things an agent actually executes. Nothing is mocked.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from skill_helpers import resolve_agent_dir, state_dir

REPO = Path(__file__).resolve().parents[1]
SHIPPED_DIRS = ("scripts", "skills", "commands", "agents", "hooks")


def _shipped_files() -> list[Path]:
    """Every git-tracked file an agent could execute or follow as instructions.

    Uses `git ls-files` rather than a glob so that untracked scratch, reports/,
    and the _dev trees can never leak into the assertions.
    """
    out = subprocess.run(
        ["git", "ls-files", "--", *SHIPPED_DIRS],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.split()
    skip = {".json", ".lock", ".png", ".jpg", ".ico"}
    return [REPO / f for f in out if Path(f).suffix not in skip]


# ─────────────────── B2 — do not clobber the repo's own config ───────────────────

# A redirect or tee INTO the entrusted repo's own Claude config. `>>` (append) is
# just as destructive in spirit for settings.local.json, so both are matched.
CLOBBER = re.compile(
    r"""(?:>>?|\btee\b\s+(?:-a\s+)?)\s*["']?(?:\./)?(?:CLAUDE\.md|\.claude/)""",
    re.IGNORECASE,
)


def test_no_shipped_component_writes_to_the_repos_own_claude_config() -> None:
    """B2 — nothing may write into `CLAUDE.md` or `.claude/` of the entrusted repo.

    Every repo we are about to adopt already has these, authored by a human. A
    skill that redirects into them destroys the user's own configuration, and the
    plugin's state has no business living there anyway — it belongs in
    `.aimaestro/state` (see state_dir()).
    """
    offenders = [
        f"{p.relative_to(REPO)}:{i}"
        for p in _shipped_files()
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
        if CLOBBER.search(line)
    ]
    assert not offenders, (
        "these shipped components write into the entrusted repo's own Claude config "
        f"and would clobber a real user's setup: {offenders}"
    )


def test_plugin_state_never_lands_in_the_dot_claude_directory() -> None:
    """B2 — the plugin's own state lives in `.aimaestro/`, never in `.claude/`.

    This is what makes collision-freedom structural rather than a matter of care:
    two different namespaces cannot collide.
    """
    d = state_dir(env={"AGENT_WORK_DIR": "/somewhere/entrusted-repo"})
    assert ".claude" not in d.parts
    assert d == Path("/somewhere/entrusted-repo/.aimaestro/state")


# ─────────────────────────── B4 — write containment ───────────────────────────


def test_state_stays_inside_the_agent_workdir_for_every_resolution_path() -> None:
    """B4 — state is under the agent dir whichever cascade rung supplies it.

    The cascade is AGENT_WORK_DIR -> CLAUDE_PROJECT_DIR -> cwd. If any rung let
    the path escape, the agent would write into someone else's project.
    """
    for env, expected in (
        ({"AGENT_WORK_DIR": "/w/a", "CLAUDE_PROJECT_DIR": "/w/b"}, Path("/w/a")),
        ({"CLAUDE_PROJECT_DIR": "/w/b"}, Path("/w/b")),
        ({}, Path("/w/c")),
    ):
        agent = resolve_agent_dir(env=env, cwd="/w/c")
        assert agent == expected
        assert state_dir(env=env, cwd="/w/c").is_relative_to(agent)


def test_agent_work_dir_wins_over_claude_project_dir() -> None:
    """B4 — AI Maestro's variable is authoritative.

    A stale CLAUDE_PROJECT_DIR inherited from another session must never redirect
    writes into that other session's repo.
    """
    assert resolve_agent_dir(
        env={"AGENT_WORK_DIR": "/w/authoritative", "CLAUDE_PROJECT_DIR": "/w/stale"}
    ) == Path("/w/authoritative")


# Absolute writes to a HOME-anchored or system path. `~/.claude/` and `$HOME` are
# the realistic escapes; /etc and /usr are the catastrophic ones.
#
# The (?<!-) lookbehind matters: without it the ASCII arrow in a comment
# ("home paths -> $HOME/<rest>") reads as a shell redirect and the test cries
# wolf. A containment test that fires on prose gets muted, and a muted test
# protects nothing.
ESCAPE = re.compile(
    r"""(?:(?<!-)>>?|\btee\b\s+(?:-a\s+)?)\s*["']?(?:~/|\$HOME|\$\{HOME\}|/etc/|/usr/|/Library/)""",
)

# A Dockerfile `RUN` step writes into the CONTAINER IMAGE, not the host workdir.
# That is not an escape — it is the whole point of a sandbox image, and the
# sandbox runs --network=none --read-only --cap-drop=ALL. Matching them would
# make this test fire on every Dockerfile forever.
DOCKER_RUN = re.compile(r"^\s*RUN\b")

# Writes that ARE outside the workdir and are nonetheless correct. Each entry must
# say why. This list is deliberately hostile to grow: a new entry is a claim that
# an agent scoped to one repo may mutate the machine, and it should have to be
# argued for in review.
ESCAPE_ALLOWLIST = {
    # Registering the GitHub CLI apt source is machine tooling INSTALLATION, run
    # deliberately and visibly (with sudo) by the bootstrap skill — not an agent
    # write leaking out of its workdir at runtime. Installing a package manager
    # source is definitionally a system-level act; the containment invariant is
    # about where the agent puts its OWN artifacts.
    "skills/maintainer-tooling-bootstrap/references/install-recipes.md:54",
}


def test_no_shipped_component_writes_outside_the_workdir() -> None:
    """B4 — no shipped component redirects a write to $HOME, ~, /etc, /usr, /Library.

    Reading from $HOME is fine and common (rules, caches). WRITING there is the
    escape: it is how an agent scoped to one repo quietly mutates the whole
    machine — and on the adopted ~/Code repos that machine is the user's.

    Container-internal `RUN` steps and the allowlisted tooling install are
    excluded; see the constants above for why each is not an escape.
    """
    offenders = [
        f"{p.relative_to(REPO)}:{i}"
        for p in _shipped_files()
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1)
        if ESCAPE.search(line)
        and not DOCKER_RUN.match(line)
        and f"{p.relative_to(REPO)}:{i}" not in ESCAPE_ALLOWLIST
    ]
    assert not offenders, (
        f"these shipped components write outside the agent workdir: {offenders}"
    )


def test_the_escape_detector_actually_detects_an_escape() -> None:
    """The containment test above is only worth having if its regex still bites.

    A regex loosened over time to silence false positives can end up matching
    nothing at all, and a test that cannot fail is worse than no test — it reports
    safety it never checked. So assert the detector still fires on the real shapes,
    and still ignores the two it is supposed to ignore.
    """
    assert ESCAPE.search('echo x > ~/.claude/settings.json')
    assert ESCAPE.search('echo x >> $HOME/.bashrc')
    assert ESCAPE.search('tee -a /etc/hosts')
    # ...and does NOT fire on an ASCII arrow in prose, or a container-internal RUN
    assert not ESCAPE.search('# home paths -> $HOME/<rest>')
    assert DOCKER_RUN.match('RUN cat >/usr/local/bin/entrypoint <<EOF')


# ───────────────────────── B5 — reports land in one place ─────────────────────────

REPORT_DIR_ASSIGN = re.compile(r'REPORT_DIR=(?P<val>.+)')
# The canonical stamp: local time + GMT offset, e.g. 20260714_183911+0200.
CANONICAL_STAMP = "%Y%m%d_%H%M%S%z"


def _report_writers() -> list[Path]:
    return [p for p in _shipped_files() if "REPORT_DIR=" in p.read_text(encoding="utf-8", errors="replace")]


def test_every_report_writer_targets_main_root_reports() -> None:
    """B5 — a report goes to `$MAIN_ROOT/reports/<component>/`, never anywhere else.

    `$MAIN_ROOT` is resolved from `git worktree list | head -n1`, which names the
    MAIN checkout even when invoked from a linked worktree — a worktree's own
    reports/ dies with the branch, taking the audit trail with it.
    """
    writers = _report_writers()
    assert writers, "expected at least one shipped component to write a report"
    for p in writers:
        text = p.read_text(encoding="utf-8", errors="replace")
        for m in REPORT_DIR_ASSIGN.finditer(text):
            val = m.group("val")
            assert "MAIN_ROOT" in val and "/reports/" in val, (
                f"{p.relative_to(REPO)} sets REPORT_DIR={val.strip()!r}; reports must live "
                "under $MAIN_ROOT/reports/<component>/"
            )
        assert "git worktree list" in text, (
            f"{p.relative_to(REPO)} writes a report but never resolves MAIN_ROOT from "
            "`git worktree list` — from a linked worktree it would write to the wrong root"
        )


def test_every_report_writer_uses_the_local_time_plus_offset_stamp() -> None:
    """B5 — the timestamp is local time WITH the GMT offset (`%Y%m%d_%H%M%S%z`).

    A bare YYYYMMDD_HHMMSS is ambiguous across machines and shared filesystems, and
    UTC forces a human to do timezone arithmetic to tie a report to their own day.
    """
    for p in _report_writers():
        text = p.read_text(encoding="utf-8", errors="replace")
        assert CANONICAL_STAMP in text, (
            f"{p.relative_to(REPO)} writes a report without the canonical "
            f"{CANONICAL_STAMP} timestamp"
        )
        assert "date -u" not in text, f"{p.relative_to(REPO)} stamps reports in UTC"


def test_reports_directories_are_gitignored() -> None:
    """B5 — `reports/` and `reports_dev/` must both be ignored.

    Reports routinely carry absolute paths, usernames, internal hostnames and
    proprietary source. Committing one is a data leak, so the ignore is part of
    the containment guarantee, not housekeeping.
    """
    ignored = REPO / ".gitignore"
    body = ignored.read_text(encoding="utf-8")
    for entry in ("reports/", "reports_dev/"):
        assert re.search(rf"^/?{re.escape(entry)}", body, re.MULTILINE), (
            f"{entry} is not gitignored — a report committed from an entrusted repo is a leak"
        )


@pytest.mark.parametrize("bad", ["reports", "reports_dev"])
def test_no_report_is_tracked_in_git(bad: str) -> None:
    """B5 — and nothing under those directories is tracked TODAY.

    The .gitignore only protects files added after it; this catches one that was
    committed before the rule existed.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "--", bad],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert not tracked, f"reports are tracked in git under {bad}/: {tracked.splitlines()[:5]}"
