"""Every CLI a command doc tells the agent to run must actually accept it.

`test_command_contracts.py` pins the STRUCTURE of a command (frontmatter, the
skill it loads, that its backticked paths resolve). It cannot tell whether the
invocation the doc prints is one the script would accept — a path can exist while
the verb next to it no longer does.

THE FAILURE THIS CATCHES, and why nothing else would: rename an argparse
subcommand or drop a flag, and the script keeps working, its own tests keep
passing, and the command doc keeps printing the old spelling. The agent runs it,
argparse exits 2, and the user sees a command that is simply broken — with
nothing in the repo having failed on the way there. It is the same shape as a
`Loads skill: **x**` line naming a retired skill, one layer further down.

These run the REAL scripts' `--help` and compare against the REAL shipped docs.
Nothing is mocked, and the expected values are not written out here: both sides
are derived, so the test cannot drift into asserting yesterday's CLI.
"""

from __future__ import annotations

import functools
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
COMMANDS_ROOT = REPO / "commands"
COMMANDS = sorted(p.name for p in COMMANDS_ROOT.glob("*.md"))

# An INVOCATION, not a mention. `scripts/publish.py` appearing in a list of
# protected paths is not a claim that you can run it, and neither is
# "Engine: `scripts/worktree.py`" — only a runner prefix makes it one. Without
# this restriction the test would demand a CLI contract from prose.
INVOCATION = re.compile(r"(?:uv run |python3? )(scripts/[A-Za-z0-9_./-]+\.py)([^\n`]*)")

# argparse renders its subcommands as `{a,b,c}` in the usage line.
SUBCOMMAND_SET = re.compile(r"\{([a-z0-9_,-]+)\}")


def _logical_lines(text: str) -> str:
    """Join backslash-continued lines so a wrapped invocation reads as one.

    `sandbox.py precheck <pkg-spec> \\` puts `--ecosystem` on the next line; a
    line-oriented scan would see the invocation and the flag as unrelated and
    check neither against the other.
    """
    return re.sub(r"\\\n\s*", " ", text)


@functools.lru_cache(maxsize=None)
def _help_text(script: str) -> str:
    """`--help` for one shipped script. Cached: each call is a real subprocess."""
    proc = subprocess.run(
        ["uv", "run", script, "--help"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, f"{script} --help exited {proc.returncode}: {proc.stderr[-400:]}"
    return proc.stdout


def _invocations(command: str) -> list[tuple[str, str, list[str]]]:
    """(script, verb, flags) for every runnable invocation in one command doc."""
    out: list[tuple[str, str, list[str]]] = []
    for m in INVOCATION.finditer(_logical_lines((COMMANDS_ROOT / command).read_text(encoding="utf-8"))):
        script, tail = m.group(1), m.group(2)
        # The verb is the first bare word after the script. A placeholder
        # (`<pkg-spec>`), a flag, or a pipe means there is no verb.
        verb_m = re.match(r"\s+([a-z][a-z0-9-]*)(?=\s|$)", tail)
        flags = re.findall(r"(--[a-z][a-z0-9-]*)", tail)
        out.append((script, verb_m.group(1) if verb_m else "", flags))
    return out


ALL_INVOCATIONS = [(c, *inv) for c in COMMANDS for inv in _invocations(c)]


def test_some_command_documents_a_runnable_cli() -> None:
    """Guard the guard: an empty extraction makes every case below vacuous.

    The regex demands a `uv run` / `python` prefix, so a docs-wide reformat that
    dropped the prefix would silently empty this suite while it stayed green.
    """
    assert ALL_INVOCATIONS, "no command documents a script invocation — the extractor has stopped matching"
    assert len({i[1] for i in ALL_INVOCATIONS}) >= 2, "invocations found for only one script; expected several"


@pytest.mark.parametrize(("command", "script", "verb", "flags"), ALL_INVOCATIONS)
def test_documented_script_exists(command: str, script: str, verb: str, flags: list[str]) -> None:
    """The script a command tells the agent to run is shipped."""
    assert (REPO / script).is_file(), f"{command}: documents `{script}`, which does not exist"


@pytest.mark.parametrize(("command", "script", "verb", "flags"), [i for i in ALL_INVOCATIONS if i[2]])
def test_documented_verb_is_a_real_subcommand(command: str, script: str, verb: str, flags: list[str]) -> None:
    """A documented subcommand appears in the script's own `--help`.

    Derived from argparse's `{a,b,c}` usage line rather than a hardcoded list, so
    adding a verb needs no edit here and REMOVING one fails immediately.
    """
    sets = SUBCOMMAND_SET.findall(_help_text(script))
    assert sets, f"{script}: --help exposes no subcommand set, but {command} documents the verb `{verb}`"
    available = {v for s in sets for v in s.split(",")}
    assert verb in available, f"{command}: documents `{script} {verb}`, but the script accepts only {sorted(available)}"


@pytest.mark.parametrize(("command", "script", "verb", "flags"), [i for i in ALL_INVOCATIONS if i[3]])
def test_documented_flags_are_accepted(command: str, script: str, verb: str, flags: list[str]) -> None:
    """Every `--flag` a command prints is one the script (or its verb) accepts.

    The subcommand's own help is consulted when the invocation names a verb —
    `sandbox.py precheck --ecosystem` is documented on `precheck`, not on the
    top-level parser, and checking the wrong one would report a false break.
    """
    help_text = _help_text(script)
    if verb:
        proc = subprocess.run(["uv", "run", script, verb, "--help"], cwd=REPO, capture_output=True, text=True, timeout=180)
        if proc.returncode == 0:
            help_text += proc.stdout
    missing = [f for f in flags if f not in help_text]
    target = f"{script} {verb}".strip()
    assert not missing, f"{command}: documents flag(s) {missing} for `{target}`, which its --help does not list"


def test_the_verb_and_flag_checks_can_actually_fail() -> None:
    """Positive control — both assertions must reject something fabricated.

    A contract test that only ever sees correct docs proves nothing about its own
    sensitivity, and this file's whole value is catching the day they diverge.
    """
    scripts = {i[1] for i in ALL_INVOCATIONS if SUBCOMMAND_SET.search(_help_text(i[1]))}
    assert scripts, "no multi-verb script among the invocations — the control cannot run"
    script = sorted(scripts)[0]
    available = {v for s in SUBCOMMAND_SET.findall(_help_text(script)) for v in s.split(",")}
    assert "definitely-not-a-verb" not in available, "the verb check would pass a fabricated subcommand"
    assert "--definitely-not-a-flag" not in _help_text(script), "the flag check would pass a fabricated flag"


def test_the_worktree_command_documents_exactly_the_engine_s_verbs() -> None:
    """`commands/maintainer-worktree.md` lists five verbs; the engine must have them.

    Called out on its own because the doc enumerates the verbs in PROSE rather
    than as invocations, so the extractor above cannot see them — and a prose
    list is precisely the kind that keeps reading correctly after the code
    beneath it has moved. Both sides are derived: the doc's bullets and the
    script's argparse.
    """
    doc = (COMMANDS_ROOT / "maintainer-worktree.md").read_text(encoding="utf-8")
    documented = {m for m in re.findall(r"^- `([a-z][a-z0-9-]*)(?: <[^>]+>)?` — ", doc, re.M)}
    assert documented, "no verb bullets found in the worktree command — the doc's shape changed"
    available = {v for s in SUBCOMMAND_SET.findall(_help_text("scripts/worktree.py")) for v in s.split(",")}
    assert documented <= available, f"the command documents verb(s) the engine does not accept: {sorted(documented - available)}"
    assert available <= documented, f"the engine accepts verb(s) the command never mentions: {sorted(available - documented)}"
