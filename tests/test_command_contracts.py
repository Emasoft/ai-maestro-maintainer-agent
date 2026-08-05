"""
The contract every `commands/*.md` file must satisfy.

Why this file exists: `test_skill_contracts.py` pins the SKILL side thoroughly,
and nothing pinned the COMMAND side. CPV's coverage check names 14 of these 23
commands as having no discoverable test, and it is right about the commands even
though it is wrong about two skills it also lists (`maintainer-redact` and
`maintainer-sandbox` do have suites).

A command is not decoration: it is a user-invocable entry point that names a
skill to load. Two of the assertions below catch failures that are silent at
author time and total at run time --

  * a `Loads skill: **x**` line naming a skill that does not exist. The command
    still parses, still renders, still appears in the menu, and does nothing.
  * a relative path in the body that does not resolve. The agent follows it,
    finds nothing, and improvises.

MEASURED WHEN THIS LANDED (2026-08-05): 23 commands, 0 findings. So this is not
fixing a live break -- it is closing the gap that would let the first one ship
unnoticed, which is the same reason every other guard in this suite exists.

Nothing is mocked: these read the shipped files.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
COMMANDS_ROOT = REPO / "commands"
SKILLS_ROOT = REPO / "skills"

# AI Maestro manages the tool surface dynamically, so no shipped component may
# freeze it (ADR-0002 / PRRD S7 — the same rule test_skill_contracts pins for
# skills; a command is just as capable of violating it).
TOOL_GRANT_KEYS = ("allowed-tools", "disallowed-tools", "tools")

COMMANDS = sorted(p.name for p in COMMANDS_ROOT.glob("*.md"))
SKILL_NAMES = frozenset(p.parent.name for p in SKILLS_ROOT.glob("*/SKILL.md"))

# `Loads skill: **name**` — the command's declaration of what it dispatches to.
LOADS_SKILL = re.compile(r"Loads skill:\s*\*\*([a-z0-9][a-z0-9-]*)\*\*")

# A backticked path that is plugin-local: it starts with one of our own top-level
# directories. Anything else in backticks is a shell fragment, an external path,
# or prose, and is none of this test's business.
LOCAL_PATH = re.compile(r"`((?:skills|commands|scripts|hooks|agents)/[A-Za-z0-9._/-]+)`")


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter, body). Mirrors the skill-contract parser deliberately.

    Same shape as test_skill_contracts._split_frontmatter so the two contracts
    cannot drift into disagreeing about what a valid header is.
    """
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert m, "a command must open with a --- frontmatter block"
    return (yaml.safe_load(m.group(1)) or {}), m.group(2)


def _text(command: str) -> str:
    p = COMMANDS_ROOT / command
    assert p.is_file(), f"missing command {command}"
    return p.read_text(encoding="utf-8")


def test_the_command_corpus_is_not_empty() -> None:
    """Guard the guard: an empty glob would make every parametrized test vacuous."""
    assert len(COMMANDS) >= 20, f"expected the command corpus, found {len(COMMANDS)}"
    assert SKILL_NAMES, "no skills discovered — the resolve check below would be vacuous"


@pytest.mark.parametrize("command", COMMANDS)
def test_frontmatter_valid_with_nonempty_description(command: str) -> None:
    """Every command's frontmatter parses as YAML and carries a real description.

    The description is what the user reads in the command menu, so an empty or
    placeholder one makes the command undiscoverable in practice.
    """
    fm, _ = _split_frontmatter(_text(command))
    desc = fm.get("description")
    assert isinstance(desc, str) and desc.strip(), f"{command}: empty description"
    assert len(desc.strip()) > 20, f"{command}: description too thin to pick from a menu"


@pytest.mark.parametrize("command", COMMANDS)
def test_no_tool_grant_frontmatter(command: str) -> None:
    """No command freezes the tool surface (ADR-0002 / PRRD S7).

    AI Maestro manages tools dynamically; a hardcoded grant silently narrows what
    the agent can do the moment the surface changes, and nothing reports it.
    """
    fm, _ = _split_frontmatter(_text(command))
    present = [k for k in TOOL_GRANT_KEYS if k in fm]
    assert not present, f"{command}: declares {present} — the tool surface is not ours to pin"


@pytest.mark.parametrize("command", COMMANDS)
def test_declared_skill_exists(command: str) -> None:
    """`Loads skill: **x**` must name a skill that ships.

    THE SILENT FAILURE THIS CATCHES: rename or retire a skill and the command
    still parses, still renders, still shows up in the menu — and dispatches to
    nothing. There is no runtime error to notice.
    """
    body = _text(command)
    declared = LOADS_SKILL.findall(body)
    assert declared, f"{command}: no `Loads skill: **name**` line — what does it dispatch to?"
    missing = [s for s in declared if s not in SKILL_NAMES]
    assert not missing, f"{command}: declares skill(s) that do not exist: {missing}"


@pytest.mark.parametrize("command", COMMANDS)
def test_backticked_local_paths_resolve(command: str) -> None:
    """A plugin-local path in the body points at a file that exists.

    An agent follows the path, finds nothing, and improvises — which is worse
    than an error, because it produces plausible output from no source.
    """
    broken = [
        p for p in LOCAL_PATH.findall(_text(command)) if not (REPO / p).exists()
    ]
    assert not broken, f"{command}: broken local path(s): {broken}"


@pytest.mark.parametrize("command", COMMANDS)
def test_argument_hint_is_a_slot_not_a_sentence(command: str) -> None:
    """When present, `argument-hint` describes ARGUMENTS, not behaviour.

    It renders inline next to the command name, so a sentence there is noise at
    exactly the moment the user is choosing.

    THE DISCRIMINATOR MATTERS, and my first one was wrong: "contains a period"
    rejected `[--threats T1,T2,...]`, where `...` is an ellipsis meaning "more
    values" — correct slot syntax, flagged as prose. A guard that reddens on
    correct writing gets muted, and a muted guard protects nothing. So the test
    is for a real SENTENCE TERMINATOR (a word character followed by a final
    period), which `...` and `]` cannot produce.
    """
    fm, _ = _split_frontmatter(_text(command))
    hint = fm.get("argument-hint")
    if hint is None:
        return
    assert isinstance(hint, str), f"{command}: argument-hint must be a string"
    assert "\n" not in hint, f"{command}: argument-hint spans lines; it renders inline"
    assert len(hint) <= 120, f"{command}: argument-hint too long to render inline ({len(hint)})"
    assert not re.search(r"\w\.$", hint), (
        f"{command}: argument-hint ends as a sentence, not a slot list: {hint!r}"
    )


def test_the_argument_hint_discriminator_is_calibrated() -> None:
    """It must accept real slot syntax and still reject a real sentence.

    Pinned because this assertion was wrong once already — encoding both
    directions is what stops the next "loosen it until it stops complaining".
    """
    for ok in (
        "[--since <baseline>] [--threats T1,T2,...] [--dry-run]",
        "[search|read <id>|verify <id>]",
        "<owner/repo> [--json]",
    ):
        assert not re.search(r"\w\.$", ok), f"slot syntax wrongly rejected: {ok!r}"
    for prose in (
        "Scans the repository for drift.",
        "Runs the guardian baseline.",
    ):
        assert re.search(r"\w\.$", prose), f"prose wrongly accepted: {prose!r}"


def test_every_shipped_skill_is_reachable_from_some_command_or_is_chained() -> None:
    """Report skills no command exposes — they are reachable only by chaining.

    Not a failure: several skills are deliberately internal (invoked BY another
    skill, never by a user). This asserts the number does not silently grow, so a
    newly-orphaned skill is visible rather than quietly unreachable.
    """
    declared: set[str] = set()
    for command in COMMANDS:
        declared.update(LOADS_SKILL.findall(_text(command)))
    orphans = sorted(SKILL_NAMES - declared)
    # Pinned to the measured value. RAISING this number is a decision, not an
    # accident: it means a skill lost its entry point. Lower it freely.
    assert len(orphans) <= 14, (
        f"{len(orphans)} skills have no command entry point (was 14 when pinned). "
        f"If a skill just lost its command, that is the bug:\n  " + "\n  ".join(orphans)
    )
