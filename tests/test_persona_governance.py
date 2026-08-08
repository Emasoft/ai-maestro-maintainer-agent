"""
The governance contract the FLEET reads out of this agent's persona.

Why this file exists: the persona is the only artifact that rides every single
turn, so it is where a fleet-facing fact has to live to be reliably acted on —
and until now NO test read it for content. That is how two of the three facts
asked for in the FLEET-STATUS thread (Emasoft/ai-maestro-maintainer-agent#29,
Q4) sat missing for three weeks while everything else stayed green: the gap was
invisible because nothing was looking.

Each assertion below is a claim some OTHER agent in the fleet acts on. If one
regresses, the failure is not local — a MANAGER dispatches against a column
vocabulary this agent does not know, or this agent "fixes" a seeded overlay the
server silently restores. So these are pinned as tests rather than trusted to
review.

Nothing is mocked: every test reads the shipped persona file byte-for-byte.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PERSONA = REPO / "agents" / "ai-maestro-maintainer-agent-main-agent.md"

# The ratified 17-column kanban vocabulary, in pipeline order (14 lifecycle),
# plus the 3 exception columns. Canonical source: the universal-kanban rule.
# Written out in full rather than derived, because a test that computes the
# expected value from the file under test proves nothing.
LIFECYCLE_COLUMNS = (
    "backburner",
    "todo",
    "design",
    "dispatch",
    "dev",
    "testing",
    "ai_review",
    "human_review",
    "complete",
    "publish",
    "published",
    "deploy",
    "live",
    "live_auditing",
)
EXCEPTION_COLUMNS = ("blocked", "failed", "superseded")

# The approval floor's total order. `maestro` is a deprecated READ-alias and is
# deliberately NOT here: it must never be written.
APPROVAL_TITLES = ("none", "orchestrator", "chief-of-staff", "manager", "user")


@pytest.fixture(scope="module")
def persona() -> str:
    assert PERSONA.is_file(), f"persona missing at {PERSONA}"
    return PERSONA.read_text(encoding="utf-8")


# ───────────────────────── the board (#29 Q4, bullet 2) ─────────────────────────


def test_persona_states_the_kanban_has_exactly_17_columns(persona: str) -> None:
    """The persona names the board's size as exactly 17 — the ratified count."""
    assert re.search(r"\b17\b", persona), "the persona never states the column count"
    assert re.search(r"(?i)17[- ]column|exactly\s+\*{0,2}17\*{0,2}\s+column", persona), "the persona mentions 17 but not as the column count — a bare number is not a contract a reader can act on"


@pytest.mark.parametrize("column", LIFECYCLE_COLUMNS + EXCEPTION_COLUMNS)
def test_persona_names_every_one_of_the_17_columns(persona: str, column: str) -> None:
    """Each of the 17 column names appears verbatim.

    Parametrized one-per-column on purpose: a single test asserting "all 17"
    reports one failure no matter how many are missing, which is exactly the
    information you need and do not get.
    """
    assert column in persona, f"column {column!r} is absent from the persona"


def test_persona_states_the_board_must_drain(persona: str) -> None:
    """A card that stops moving is a defect unless `blocked-by:` names a blocker.

    The vocabulary alone is inert. The rule that makes the board mean anything is
    that work FLOWS through it — a board every agent files into and none pulls
    from accumulates stalled cards whose column lies about them.
    """
    assert "blocked-by:" in persona, "the blocked-licence field is never named"
    assert re.search(r"(?i)\bdrain\b", persona), "the persona never says the pipeline must drain — without it the 17 columns are a filing cabinet"


def test_persona_does_not_invent_columns_outside_the_ratified_set(persona: str) -> None:
    """No `column: <x>` example in the persona uses a non-vocabulary value.

    The vocabulary is canonical, so an illustrative example with a made-up column
    teaches a value the rest of the fleet will reject.
    """
    known = (
        set(LIFECYCLE_COLUMNS)
        | set(EXCEPTION_COLUMNS)
        | {
            # The folder-lifecycle values BRACKET the pipeline; they are legal values
            # of the same field, documented in the TRDD rules.
            "proposal",
            "planned",
            "refused",
            "cancelled",
            "completed",
            "superseded",
        }
    )
    used = set(re.findall(r"^column:\s*([a-z_]+)\s*$", persona, re.MULTILINE))
    assert used <= known, f"persona uses non-vocabulary column(s): {sorted(used - known)}"


# ─────────────────── seeded read-only overlays (#29 Q4, bullet 3) ───────────────────


def test_persona_knows_the_seeded_aimaestro_rules_are_read_only(persona: str) -> None:
    """The overlays are seeded, read-only, and RESTORED if edited.

    Restore-on-edit is the load-bearing half: without it a reader concludes an
    edit is a legitimate way to disagree, spends a turn making one, and never
    learns it was reverted.
    """
    assert ".claude/rules/aimaestro-" in persona, "the seeded overlay path is never named"
    assert re.search(r"(?i)read-only", persona), "the overlays are not described as read-only"
    assert re.search(r"(?i)restore[sd]?\s+(them\s+)?if\s+edited", persona), "the persona never says the server restores an edited overlay"


def test_persona_gives_a_precedence_tie_break_for_the_overlays(persona: str) -> None:
    """ "Must not fight them" is unmechanizable; a tie-break is not.

    A rule an agent cannot mechanically apply is a rule it will apply
    inconsistently, which is worse than none — the inconsistency is invisible.
    """
    assert re.search(r"(?i)precedence", persona), "no precedence rule for overlay-vs-persona"
    assert re.search(r"(?i)report the contradiction", persona), "the persona resolves a contradiction without escalating it — a silent divergence is a fleet inconsistency nobody can grep for"


def test_persona_gates_on_the_overlay_text_not_a_version(persona: str) -> None:
    """Capability probing is by CONTENT, never by version or branch.

    Verified the hard way (TRDD-27IG72GX): the deployed `aimaestro-trdd.sh` was
    330 lines / 7 verbs and LACKED `verify` while the manifest documented it, so
    `command -v` passed and the verb still failed. Presence is not capability.
    """
    assert "grep -q min-approval-requirement" in persona, "the persona shows no concrete capability probe against the seeded overlay"
    assert re.search(r"(?i)never\s+(gate\s+)?on\s+a\s+(branch\s+or\s+)?version", persona), "the persona does not forbid version-gating"


# ───────────────────── approval floor (#29 Q4, bullet 1 — already closed) ─────────────────────


@pytest.mark.parametrize("title", APPROVAL_TITLES)
def test_persona_carries_the_full_approval_floor_enum(persona: str, title: str) -> None:
    """Every rung of `min-approval-requirement:` is named.

    `orchestrator` is the rung that proves the retired numeric scheme could not
    express the ladder — it has no number at all — so its absence is the specific
    regression to catch.
    """
    assert "min-approval-requirement" in persona, "the approval floor field is absent"
    assert title in persona, f"approval rung {title!r} is missing from the persona"


def test_persona_treats_the_numeric_tier_field_as_decode_only(persona: str) -> None:
    """`approval-tier: N` is retired — read to decode legacy, never written."""
    assert re.search(r"(?i)approval-tier.{0,120}?(decode-only|decode only|never written)", persona, re.DOTALL), "the persona does not mark approval-tier as decode-only"
    assert "maestro" in persona and re.search(r"(?i)never write", persona), "the deprecated `maestro` read-alias is not marked never-write"


# ───────────────────── the invariants the fleet audits us on ─────────────────────


def test_persona_declares_manager_and_human_as_its_only_direct_edges(persona: str) -> None:
    """R6.5b: MAINTAINER has no COS; every team title is reachable only via MANAGER."""
    assert re.search(r"(?i)no\s+cos|have\s+no\s+chief-of-staff|NO\s+CHIEF-OF-STAFF", persona), "the persona does not state that MAINTAINER has no CHIEF-OF-STAFF"
    assert re.search(r"(?i)sub-?agents.{0,80}?cannot send", persona, re.DOTALL), "the persona does not state that spawned subagents have no AMP identity"


def test_persona_requires_draining_the_amp_inbox_on_every_wake(persona: str) -> None:
    """Not "each cycle" — EVERY wake.

    The original wording scoped the duty to a patrol cycle, so a heartbeat- or
    notification-fired turn had no instruction at all and a delivered mandate
    rotted (#33). The word that fixes it is the one asserted here.
    """
    assert re.search(r"(?i)drain the inbox on EVERY wake", persona), "inbox drain is not scoped to every wake"
    assert "amp-inbox" in persona, "no concrete inbox command — prose without a mechanism"


def test_persona_forbids_direct_api_calls_with_no_escape_hatch(persona: str) -> None:
    """The frozen-CLI rule is an IRON RULE: no fallback, no tagged exception.

    The revoked escape hatch is named explicitly so that re-adding one has to
    argue with a test rather than slip in as a helpful-looking fallback.
    """
    assert re.search(r"(?i)iron rule", persona), "the frozen-CLI rule is not marked IRON"
    assert "DECOUPLE-BLOCKED" in persona and re.search(r"(?i)revoked", persona), "the revoked escape hatch is not recorded as revoked"
    assert re.search(r"(?i)gh|package-registry", persona), "the rule does not carve out gh / package-registry APIs, so a reader would over-apply it and stop using gh"


def test_persona_mandates_the_self_id_line_verbatim(persona: str) -> None:
    """PRRD G1.1 / R22 — every AMP and GitHub body opens with this exact line."""
    assert "This is the Claude responsible for the ai-maestro-maintainer-agent project." in persona, "the self-id line is absent or reworded — it must be byte-exact"


def test_persona_does_not_claim_403_covers_every_transport(persona: str) -> None:
    """R6's 403 is AMP-only — the direct session channel has no enforcement point.

    Claude Code 2.1.224 added session-to-session `SendMessage`/`ListAgents`, which
    does not traverse the ai-maestro server. Every role-plugin persona in the fleet
    (7 of 7, ai-maestro#131) told its agent "the graph is enforced server-side;
    violations return 403" — true of AMP, and a complete-sounding account of a
    surface that is now half unpoliced.

    The danger is not a weakened rule, it is a persona that reads as though every
    send is checked: an agent then routes around its own comm graph believing the
    server has it covered, and a send that SUCCEEDS is mistaken for a send that was
    PERMITTED. This asserts the persona keeps both halves — the 403 claim scoped to
    the transport that can produce one, and the unpoliced channel named.
    """
    para = persona[persona.index("Communication Permissions") :][:2500]
    assert "403" in para, "the AMP 403 claim vanished — it is still true on that transport"
    assert re.search(r"(?i)AMP transport only|on the AMP transport", para), "the 403 claim is unscoped, so it reads as covering every transport"
    assert re.search(r"(?i)SendMessage", para) and re.search(r"(?i)no enforcement point|nothing polices", para), "the persona does not name the direct session channel as unpoliced, so an agent reading only this section believes every send is server-checked"
