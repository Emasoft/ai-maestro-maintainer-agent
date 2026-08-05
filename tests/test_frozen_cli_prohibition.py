"""
R23 / the USER's IRON RULE: the frozen-CLI prohibition must live where the
DECISION is made, not only in the persona.

The rule (USER, 2026-08-02): "direct api calls are forbidden from agents! only
the ai-maestro scripts can execute the calls, and all plugins must instruct in
their skills to use the ai-maestro scripts, never the api directly!"

Two clauses, and the second is the one that fails silently:

  CLAUSE 1  no shipped surface may call the ai-maestro server /api/* .
  CLAUSE 2  every surface that INSTRUCTS a frozen-CLI invocation must also
            carry the prohibition, because skills load on demand and in
            ISOLATION -- an agent consulting one skill never sees the persona's
            rule, and a command or a hook runs with no skill loaded at all.

Two traps this file is written around, both learned from other role-plugins
reporting their own misses on Emasoft/ai-maestro#107:

  * MATCH THE PROHIBITION, NOT THE VOCABULARY. The MANAGER's first sweep grepped
    for "frozen CLI" and scored 3 of 10 skills compliant; re-reading the hits
    showed two of them merely USED the sanctioned path. The true number was 1.
    A skill that calls the CLI looks identical to a skill that forbids the API
    unless you match on the forbidding.
  * THE INVERSE OVERCOUNT IS ALSO REAL. A doc that merely NAMES a CLI verb while
    explaining a frontmatter field is not instructing a call, and demanding a
    prohibition there trains the reader to paste the block everywhere -- which
    is how a rule becomes furniture. So an "instruction" here means the CLI
    appears in an EXECUTABLE position, not anywhere in the prose.

Nothing is mocked: every assertion reads the shipped files.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# The frozen CLI families (SCRIPT-MANIFEST Tier A). `aid-*` and `amp-*` are
# prefix families; the `aimaestro-*.sh` scripts are matched by suffix.
CLI = re.compile(r"\b(?:amp-[a-z-]+|aid-[a-z-]+|aimaestro-[a-z-]+\.sh)\b")

# A PROHIBITION, not the vocabulary of one: a refusal verb within a short window
# of the thing refused. `re.DOTALL` so it survives the line wrapping that markdown
# prose imposes on every one of these blocks.
PROHIBITION = re.compile(
    r"(?i)(?:NEVER|do NOT|never)\s[^.]{0,120}?(?:/api/|server\s+API|HTTP API)",
    re.DOTALL,
)

# A real call to the AI Maestro server. Third-party APIs are explicitly out of
# scope by the USER's own carve-out (gh, crates.io, GitLab CI-lint), and a
# container healthcheck hitting its OWN localhost is not the ai-maestro server.
AIMAESTRO_CALL = re.compile(
    r"(?:localhost|127\.0\.0\.1):23000|\bhttps?://[^\s`\"']*/api/v\d+/(?:agents|governance|messages)\b"
)


def _instructs_invocation(text: str) -> bool:
    """True when the text tells the reader to RUN a frozen-CLI script.

    Executable positions only: inside a fenced block, at the start of a line, or
    behind a `command -v` probe. A CLI name sitting mid-sentence in prose ("...
    `aimaestro-trdd.sh approve` additionally MINTS a token ...") explains a field
    and instructs nothing, so it must not drag a prohibition block into a doc
    that never touches the server.
    """
    for block in re.findall(r"```.*?```", text, re.DOTALL):
        if CLI.search(block):
            return True
    for line in text.splitlines():
        stripped = line.strip().lstrip("-*>| ").strip("`")
        if CLI.match(stripped):
            return True
        if re.search(r"command -v\s+`?(?:amp-|aid-|aimaestro-)", line):
            return True
    return False


def _surfaces() -> list[Path]:
    """Every shipped file an agent reads as instructions."""
    out: list[Path] = []
    for pattern in ("skills/*/SKILL.md", "skills/*/references/*.md", "commands/*.md"):
        out.extend(sorted(REPO.glob(pattern)))
    hooks = REPO / "hooks" / "hooks.json"
    if hooks.is_file():
        out.append(hooks)
    return out


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ─────────────────────────────── CLAUSE 1 ───────────────────────────────


@pytest.mark.parametrize(
    "surface", _surfaces(), ids=lambda p: str(p.relative_to(REPO))
)
def test_no_shipped_surface_calls_the_aimaestro_server(surface: Path) -> None:
    """No shipped file reaches the ai-maestro server directly."""
    hits = AIMAESTRO_CALL.findall(_read(surface))
    assert not hits, (
        f"{surface.relative_to(REPO)} calls the ai-maestro server directly: {hits}. "
        "Use the frozen CLI; if no verb exists, the capability does not exist here."
    )


def test_the_call_detector_actually_detects_a_call() -> None:
    """The clause-1 detector must bite, or it is reporting a safety it never checked.

    A detector narrowed over time to silence false positives can end up matching
    nothing at all while still reporting green -- worse than no detector, because
    it is trusted.
    """
    assert AIMAESTRO_CALL.search("curl http://localhost:23000/api/v1/agents")
    assert AIMAESTRO_CALL.search("POST https://host/api/v1/governance/requests")
    # ...and must NOT bite on the carve-outs the USER's rule explicitly keeps.
    assert not AIMAESTRO_CALL.search("curl -s https://crates.io/api/v1/crates/serde")
    assert not AIMAESTRO_CALL.search('curl "$CI_SERVER_URL/api/v4/projects/1/ci/lint"')
    assert not AIMAESTRO_CALL.search("CMD curl -fsS http://localhost:8080/health")


# ─────────────────────────────── CLAUSE 2 ───────────────────────────────


def _invoking_surfaces() -> list[Path]:
    return [p for p in _surfaces() if _instructs_invocation(_read(p))]


def test_some_surface_actually_instructs_the_cli() -> None:
    """Guard the guard: if this list empties, clause 2 below passes vacuously."""
    found = _invoking_surfaces()
    assert found, (
        "no shipped surface instructs a frozen-CLI invocation — either the "
        "detector broke or the plugin stopped using the CLI; both invalidate "
        "every clause-2 assertion below"
    )


@pytest.mark.parametrize(
    "surface", _invoking_surfaces(), ids=lambda p: str(p.relative_to(REPO))
)
def test_every_cli_instructing_surface_carries_the_prohibition(surface: Path) -> None:
    """The surface that tells you to run the CLI must also forbid the API.

    For a skill, the prohibition may live in its SKILL.md rather than in each
    reference: SKILL.md always loads first, so the rule is present before the
    reference is opened. A COMMAND or a HOOK has no such parent — it runs with no
    skill loaded — so it must carry the rule itself.
    """
    text = _read(surface)
    if PROHIBITION.search(text):
        return
    if surface.parent.name == "references":
        skill_md = surface.parent.parent / "SKILL.md"
        assert skill_md.is_file() and PROHIBITION.search(_read(skill_md)), (
            f"{surface.relative_to(REPO)} instructs a frozen-CLI call, and neither it "
            f"nor its SKILL.md forbids the direct API"
        )
        return
    pytest.fail(
        f"{surface.relative_to(REPO)} instructs a frozen-CLI call but states no "
        "prohibition. A command and a hook run with NO skill loaded, so the rule "
        "cannot be inherited — it has to be here."
    )


def test_the_prohibition_pattern_does_not_match_mere_usage() -> None:
    """The clause-2 detector must not score USAGE as a PROHIBITION.

    This is the MANAGER's 3-of-10 → 1-of-10 correction encoded as a test: their
    grep matched the phrase "frozen CLI", so two skills that merely CALLED the
    sanctioned path were counted as skills that forbade the API.
    """
    usage = "The frozen CLI `aimaestro-agent.sh` is on $PATH and exposes the verbs."
    assert not PROHIBITION.search(usage), "usage of the CLI scored as a prohibition"
    chain = "…run the frozen CLI (`aimaestro-agent.sh` / `aimaestro-teams.sh`) → await ACK"
    assert not PROHIBITION.search(chain), "a call chain scored as a prohibition"
    real = "NEVER call the ai-maestro server `/api/*` directly, not even as a fallback."
    assert PROHIBITION.search(real), "a real prohibition was not recognised"


def test_prose_naming_a_verb_is_not_treated_as_an_invocation() -> None:
    """The inverse overcount: naming a verb while explaining a field instructs nothing.

    Without this discriminator the clause-2 sweep demands a prohibition block in
    every doc that mentions the CLI in passing — and a rule pasted everywhere
    stops being read anywhere.
    """
    prose = "`approval-datetime:`. `aimaestro-trdd.sh approve` additionally MINTS a token."
    assert not _instructs_invocation(prose)
    fenced = "Run it:\n\n```bash\namp-send \"$MANAGER\" \"subject\" \"body\"\n```\n"
    assert _instructs_invocation(fenced)
    probed = "check with `command -v amp-inbox` before calling it"
    assert _instructs_invocation(probed)


def test_hooks_carry_the_rule_because_no_skill_loads_for_them() -> None:
    """A hook fires with no skill loaded, so "no skill instructed it" is structural.

    Adopted from ai-maestro-autonomous-agent's finding on ai-maestro#107: their
    hooks.json was empty, so there was no live hole — but the rule as written
    would not have bound the first hook anyone added. A wording gap that only
    becomes a hole later is still worth closing before the hole exists.
    """
    hooks = REPO / "hooks" / "hooks.json"
    if not hooks.is_file():
        pytest.skip("plugin ships no hooks")
    raw = _read(hooks)
    json.loads(raw)  # a malformed hooks.json is its own failure
    if not _instructs_invocation(raw) and "amp-" not in raw:
        pytest.skip("hooks reference no frozen-CLI command")
    assert PROHIBITION.search(raw), (
        "hooks.json names a frozen-CLI command but states no prohibition"
    )
