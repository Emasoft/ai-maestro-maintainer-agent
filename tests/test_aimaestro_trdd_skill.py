"""
Structural-invariant tests for the `maintainer-aimaestro-trdd` skill and its
command (TRDD-27IG72GX, Phase 3 — SCRIPT-MANIFEST §5.4 adoption).

The universal skill contract (frontmatter validity, no-tool-grant keys, core
body sections, local references resolve) is covered for this skill by
`test_skill_contracts.py`, which globs every shipped skill. This
module adds the invariants unique to THIS skill — every one of them a fact
that, if it silently rotted out of the doc, would make an agent do something
wrong on a real host:

  * the capability probe (an install.sh host does not ship the CLI),
  * the never-gate-on-version rule,
  * `archive --state` refusing `failed`,
  * verify's three exit codes, and that exit 2 is an ANSWER not an error,
  * verify reading the TOKEN rather than the card's prose,
  * the identity-not-content caveat (the security-relevant limit),
  * the two authority limits (no self-approval, no agent approves user-tier),
  * "nothing is committed for you".

NO MOCKS — every assertion reads the REAL shipped .md files on disk.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skills" / "maintainer-aimaestro-trdd"
SKILL_MD = SKILL_DIR / "SKILL.md"
INSTRUCTIONS_MD = SKILL_DIR / "references" / "instructions.md"
COMMAND_MD = REPO_ROOT / "commands" / "maintainer-aimaestro-trdd.md"

DOCS = (SKILL_MD, INSTRUCTIONS_MD, COMMAND_MD)


def _text(p: Path) -> str:
    assert p.is_file(), f"missing shipped file: {p.relative_to(REPO_ROOT)}"
    return p.read_text(encoding="utf-8")


def _flat(p: Path) -> str:
    """The doc with every whitespace run collapsed to one space.

    Markdown prose WRAPS. Asserting against raw text makes a test fail on
    `ledger\\nanchor` or `**by\\nname**` — i.e. on where the author happened to
    hit 88 columns, which is not a contract. These tests pin FACTS that must be
    documented, not the line breaks around them, so prose assertions run against
    this flattened view.
    """
    return re.sub(r"\s+", " ", _text(p))


def test_all_three_docs_ship() -> None:
    """The skill ships SKILL.md, references/instructions.md, and its command."""
    for p in DOCS:
        assert p.is_file(), f"missing: {p.relative_to(REPO_ROOT)}"


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_capability_probe_is_documented(doc: Path) -> None:
    """Every doc tells the agent to probe with `command -v` before calling the CLI.

    An install.sh-provisioned host tracks `main` and does not ship
    aimaestro-trdd.sh; a doc that omits the probe teaches the agent to assume
    presence, which fails on exactly the hosts this plugin is meant to serve.
    """
    assert "command -v aimaestro-trdd.sh" in _text(doc), f"{doc.name}: no `command -v aimaestro-trdd.sh` capability probe"


@pytest.mark.parametrize("doc", (SKILL_MD, INSTRUCTIONS_MD, COMMAND_MD), ids=lambda p: p.name)
def test_never_gate_on_version_is_stated(doc: Path) -> None:
    """Every doc forbids gating on a version string.

    The manifest is a contract, not a presence guarantee: a version tells you
    what a tree intends to ship, not what this host has.
    """
    text = _text(doc).lower()
    assert "version string" in text, f"{doc.name}: does not forbid gating on a version string"


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_probe_is_verb_granular_not_just_script_granular(doc: Path) -> None:
    """Every doc probes the VERB via the script's own --help, not just `command -v`.

    THE REGRESSION THIS PINS (verified 2026-07-16, ai-maestro#69): the deployed
    ~/.local/bin/aimaestro-trdd.sh is 330 lines and dispatches 7 verbs; the
    governance-rules source is 387 lines and dispatches 8. The missing one is
    `verify`. So a script-granular `command -v` probe PASSES on that host and the
    verb still fails — the exact "skill teaching a verb the shipped CLI lacks"
    failure the manifest's own §5 warns about, arrived at from the other side.

    The script's own `--help` is the only source that describes THIS host: not the
    manifest (it documents verify), not a version string, not a doc.
    """
    text = _flat(doc)
    assert re.search(r"--help.{0,80}grep", text), f"{doc.name}: no per-VERB probe (script's own --help) — `command -v` alone is not enough; it passes on a host whose CLI lacks the verb"


# THE DRIFT RECORD — the two dated measurements of the same deployed path, required to
# sit NEAR a mention of `verify` (see `_verify_drift_record`). A doc carrying both has
# recorded that the verb table MOVES. It does NOT follow that such a doc cannot also
# assert a standing state — an earlier version of this comment claimed exactly that, and
# it is false: a history section plus a contradicting body sentence satisfies it, which
# is measured and is why the literal tripwire below was restored. Dates are chosen
# because they are literals nobody rewords while "improving" prose.
VERIFY_MEASURED_ABSENT = "2026-07-16"  # deployed: 330 lines / 7 verbs, no `verify`
VERIFY_MEASURED_PRESENT = "2026-08-21"  # deployed: 627 lines / 9 verbs, `verify` dispatched

# The literal phrasing of the expired claim. NOT a guard against the claim-CLASS — it is
# defeated by one word ("not PRESENT on the deployed", "ABSENT FROM the deployed"), which
# is measured and stated in the docstring. It is kept as a cheap TRIPWIRE for the exact
# historical sentence, because the realistic way this falsehood returns is someone
# copying the old text back, not inventing a new synonym for it.
VERIFY_OLD_LITERAL_CLAIM = re.compile(r"not\s+on\s+the\s+deployed", re.I)

DRIFT_WINDOW = 400


def _verify_drift_record(text: str) -> bool:
    """True when some mention of `verify` carries BOTH dates within DRIFT_WINDOW chars.

    Binding the dates to the SUBJECT is the whole point. Asserting the two dates appear
    anywhere in the file is satisfied by a frontmatter date, an unrelated citation, or a
    stray literal left behind after the drift paragraph is deleted — none of which say
    anything about `verify`.
    """
    for m in re.finditer(r"verify", text, re.I):
        window = text[max(0, m.start() - DRIFT_WINDOW) : m.end() + DRIFT_WINDOW]
        if VERIFY_MEASURED_ABSENT in window and VERIFY_MEASURED_PRESENT in window:
            return True
    return False


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_verify_is_probe_gated_not_asserted_either_way(doc: Path) -> None:
    """Every doc gates `verify` on the PROBE rather than asserting its availability.

    Teaching `verify` as unconditionally available is a false capability claim, and an
    agent that believes it can check authenticity but cannot may fall back to trusting
    the card's prose — precisely what the token design exists to stop.

    THIS TEST USED TO ASSERT THE OPPOSITE FACT, AND THE FACT EXPIRED. It required each
    doc to state `verify` is "not on the deployed script", measured 2026-07-16 (330
    lines / 7 verbs, ai-maestro#69). Re-measured 2026-08-21 the same path is 627 lines
    / 9 verbs and DOES dispatch `verify`. So the docs were corrected, and this test —
    written to prevent a false capability claim — became the thing enforcing one, in
    the opposite direction: it would have failed the release until the docs re-asserted
    something untrue.

    The lesson, and why the assertion now reads this way: PIN THE METHOD, NEVER THE
    MEASUREMENT. The deployed CLI drifts in BOTH directions and announces neither, so
    any test that hardcodes a verb's presence or absence has a shelf life. The probe is
    what stays correct on every host on every day, and it is the only thing worth
    asserting. A dated number belongs in prose as history, never in an assertion.

    THE FIRST REPLACEMENT WAS A RUBBER STAMP, AND IT PERMITTED THE FALSEHOOD. It
    asserted `verify.{0,400}?probe|probe.{0,400}?verify` — token CO-OCCURRENCE read as a
    semantic tie. Measured: 10 / 5 / 3 matches across the three docs, because both words
    appear 8-24 times each; the assert could not fail whatever the prose said. Worse, the
    exact sentence the OLD test demanded — "verify is NOT on the deployed script — probe
    before calling" — MATCHES it. A guard written to stop a falsehood being re-asserted
    admitted it verbatim. Proximity is not entailment; a needle nobody has shown can MISS
    is not a guard.

    THE SECOND ATTEMPT FAILED THE SAME WAY, IN BOTH HALVES. It paired a fitted phrase
    allowlist ("only where the probe says so|probe before calling|...") with a negative
    regex `not\\s+on\\s+the\\s+deployed`. Measured against rewordings:
      * NEGATIVE caught 1 of 6. "not PRESENT on the deployed", "ABSENT FROM the deployed",
        "the deployed copy LACKS verify", "does not DISPATCH verify" — every one is the
        expired falsehood, stated plainly, sailing past. One intervening word defeats it.
      * POSITIVE rejected 3 of 3 correct-but-unlisted gatings ("available only where the
        host --help lists it", "gate verify on the capability probe"). It was enumerated
        FROM these three docs, so it described today's text rather than constraining
        tomorrow's — and it would have reddened on correct writing, which is how a repo
        loses a guard it still needs.

    THE CATEGORY ERROR, stated plainly so nobody repeats it a fourth time: **absence of a
    CLAIM-CLASS is not checkable by a regex over prose.** "The doc must not assert the
    verb is missing" has unbounded phrasings; each round of tightening buys one more
    wording and leaves the next one free. Refining that regex again is whack-a-mole that
    yields false assurance — the worst outcome, because a guard believed to cover
    something stops anyone from checking it by hand.

    SO THE ASSERTION PINS THE ONE THING A LITERAL MATCH CAN HOLD: the DRIFT RECORD. Each
    doc must carry BOTH dated measurements of the same deployed path — absent
    2026-07-16, dispatched 2026-08-21. That is positive (regexes are reliable at finding
    committed literals, unreliable at proving a claim absent), it is not fitted to any
    phrasing (dates do not get reworded during a prose cleanup), and it is semantically
    load-bearing: a doc showing the reader two OPPOSITE measured states of one file
    cannot coherently also assert a standing presence or absence. It encodes the lesson
    itself — record the drift, never a state.

    ATTEMPT 3 WAS ALSO DEFEATED, AND THE ROOT WAS THE SAME ONE A THIRD TIME. It asserted
    the two dates appeared ANYWHERE in the file, unbound to the subject. Measured: a doc
    reading "Capability history: absent 2026-07-16, dispatched 2026-08-21 (ai-maestro#69).
    verify is not on the deployed script" PASSED it — while the regex deleted in attempt 2
    had CAUGHT that exact string. So on the property this test claims to protect, attempt
    3 was strictly WEAKER than what it replaced. A literal is immune to matching
    everything; it is wide open to matching something IRRELEVANT — a frontmatter date, an
    unrelated citation, or a date left behind after the drift paragraph is deleted. Note
    attempt 1 at least required proximity between `verify` and `probe`; attempt 3 dropped
    the binding entirely, which is why it regressed.

    SO THE RECORD IS NOW BOUND TO ITS SUBJECT: `_verify_drift_record` requires some
    mention of `verify` to carry BOTH dates within a window. Delete the record and it
    fails; a stray date elsewhere cannot rescue it.

    The literal tripwire is restored alongside it, honestly scoped: it catches the exact
    historical sentence and NOT the class, because the realistic re-entry path is someone
    pasting the old text back rather than inventing a synonym. 1-of-6 coverage stated as
    1-of-6 is a tripwire; 1-of-6 presented as a guard is the false assurance that made
    deleting it correct in the first place.

    PROVEN BY MUTATION ON A REAL FILE (2026-08-22): collapsing the two dates to either one
    alone in `commands/maintainer-aimaestro-trdd.md` fails, and each collapse fails a
    DIFFERENT half — A leaves 4x07-16/0x08-21, B leaves 0x07-16/4x08-21. Restoring returns
    an empty `git diff`.

    WHAT IS DELIBERATELY NOT ASSERTED, and must not be "fixed" by adding a regex: that
    the prose never re-asserts absence in some new wording. That property is real and
    unpinnable here; it belongs to review, not to this file. The per-verb probe MECHANISM
    is separately covered by `test_the_docs_teach_a_per_verb_probe` above, which matches
    the runnable `--help | grep` recipe rather than prose about it.
    """
    text = _flat(doc)
    assert _verify_drift_record(text), (
        f"{doc.name}: no drift record BOUND to `verify` — some mention of the verb must carry both {VERIFY_MEASURED_ABSENT} (absent) and {VERIFY_MEASURED_PRESENT} (dispatched) within {DRIFT_WINDOW} chars, so that deleting the record fails and a stray date elsewhere in the file cannot satisfy it"
    )
    assert not VERIFY_OLD_LITERAL_CLAIM.search(text), f"{doc.name}: contains the literal expired claim 'not on the deployed' (measured present {VERIFY_MEASURED_PRESENT}: 627 lines, 9 verbs). Tripwire only — see the docstring: rewordings of this claim are NOT caught and never will be"
    assert "69" in text, f"{doc.name}: does not cite ai-maestro#69 for the verify capability history"


def test_the_drift_record_binding_bites() -> None:
    """Control for BOTH halves — the control attempt 3 shipped without.

    Every fixture here is a real defeat of a real previous attempt, kept so a future
    author can see what each half is for rather than inferring it from the regex.
    """
    # The counter-example that defeated attempt 3: both dates + #69 + the falsehood.
    # It satisfies the binding (the dates ARE near `verify`), so the TRIPWIRE must reject.
    hostile = "Capability history: absent 2026-07-16, dispatched 2026-08-21 (ai-maestro#69). verify is not on the deployed script - do not call it."
    assert _verify_drift_record(hostile), "fixture drifted: it should satisfy the binding half"
    assert VERIFY_OLD_LITERAL_CLAIM.search(hostile), "the tripwire no longer catches the literal historical sentence"

    # Dates present but bound to nothing — a changelog line, or a leftover after the
    # drift paragraph was deleted. Attempt 3 accepted this; the binding must reject it.
    stray = f"{VERIFY_MEASURED_ABSENT} and {VERIFY_MEASURED_PRESENT} in a changelog. " + ("x" * 900) + " verify the token."
    assert not _verify_drift_record(stray), "unbound dates satisfy the guard — the binding is decorative, which is exactly how attempt 3 regressed"

    # One date only is not a drift record: it reads as a single state.
    assert not _verify_drift_record(f"verify was absent {VERIFY_MEASURED_ABSENT}.")

    # And correct writing must pass, or the guard gets deleted.
    good = f"`verify` was ABSENT {VERIFY_MEASURED_ABSENT} and is dispatched as of {VERIFY_MEASURED_PRESENT} — probe anyway."
    assert _verify_drift_record(good)
    assert not VERIFY_OLD_LITERAL_CLAIM.search(good)


def test_docs_forbid_substituting_prose_when_verify_is_unavailable() -> None:
    """When verify is absent the docs must forbid falling back to the card's prose.

    The dangerous move is not "verify is missing" — it is an agent deciding that
    `approval-judge:` looks fine, which is exactly what a forger writes.

    The regex REQUIRES the prose context (prose / approval-judge / Approval log)
    within reach of the prohibition. An earlier version matched a bare
    `(do not|never)\\s+(infer|substitute)` and was a RUBBER STAMP: it kept passing
    with this ban deleted, because it was matching the UNRELATED sentence "never
    infer a verb from docs/SCRIPT-MANIFEST.md". Caught by mutation testing — a
    prohibition test must pin the thing being prohibited, not any nearby "never".
    """
    for doc in (SKILL_MD, INSTRUCTIONS_MD, COMMAND_MD):
        text = _flat(doc)
        assert re.search(
            r"(do\s+not|never)\s+(infer|substitute)\b.{0,90}?(prose|approval-judge|approval log)",
            text,
            re.I,
        ), f"{doc.name}: does not forbid substituting the card's PROSE for a real verify"


def test_tier_is_documented_as_a_claim_not_a_grant() -> None:
    """`--tier` is a claim the server validates by AID — never a grant to trust.

    Per ai-maestro#69 §2 the CLI is a thin passthrough that JSON-encodes --tier
    verbatim, so a doc implying the typed number confers authority describes a
    privilege-escalation surface as if it were a feature.
    """
    for doc in (SKILL_MD, COMMAND_MD):
        text = _flat(doc)
        assert re.search(r"`?--tier`?\s+is\s+a\s+\*{0,2}CLAIM", text, re.I), f"{doc.name}: does not frame --tier as a CLAIM the server validates"


def test_probe_miss_degrades_explicitly_with_exit_3() -> None:
    """A probe miss is a loud, explicit degrade (exit 3) — never a silent skip.

    A silently-skipped probe is indistinguishable from "the CLI ran and found
    nothing", which is the failure mode that makes absence invisible.
    """
    for doc in (SKILL_MD, INSTRUCTIONS_MD):
        text = _flat(doc)
        assert "NOT AVAILABLE" in text, f"{doc.name}: probe miss does not announce itself"
        assert "exit 3" in text, f"{doc.name}: probe miss does not exit 3"


def test_archive_refuses_failed() -> None:
    """`archive --state` accepts completed|cancelled|superseded and REFUSES failed.

    Load-bearing: a failed TRDD is retryable and stays open in design/tasks/.
    "Archive as failed" would silently file a retryable card away as a
    conclusion; giving up is an explicit `cancel`.
    """
    for doc in DOCS:
        text = _flat(doc)
        assert re.search(r"refuses?\s+`?failed`?", text, re.I), f"{doc.name}: does not state that archive refuses `failed`"
        for state in ("completed", "cancelled", "superseded"):
            assert state in text, f"{doc.name}: archive state `{state}` undocumented"


def test_verify_documents_all_three_exit_codes() -> None:
    """verify's contract is 0 verified / 2 NOT verified / 1 error — all three stated.

    Exit 2 is the one that matters: a caller that treats non-zero as "error"
    would retry away a real negative verdict.

    Accepts EITHER the prose form (``0` verified · `2` NOT verified · `1` error`)
    or the runnable `case $? in 0) ... 2) ... 1) ...` form — instructions.md uses
    the latter, which documents the same contract in a shape you can paste.
    """
    for doc in DOCS:
        text = _flat(doc)
        # NOT-verified must be tied to 2 in either shape, and checked FIRST:
        # a bare `verified` search would match inside "NOT VERIFIED".
        assert re.search(r"[`\s]2[`)\s].{0,40}?NOT[ _-]?VERIFIED", text, re.I), f"{doc.name}: exit 2 (NOT verified) undocumented"
        assert re.search(r"[`\s]0[`)\s].{0,40}?VERIFIED", text, re.I), f"{doc.name}: exit 0 (verified) undocumented"
        assert re.search(r"[`\s]1[`)\s].{0,40}?ERROR", text, re.I), f"{doc.name}: exit 1 (error) undocumented"


def test_exit_2_is_framed_as_an_answer_not_a_retryable_failure() -> None:
    """The docs frame exit 2 as a finding to report, not an error to retry."""
    for doc in (SKILL_MD, INSTRUCTIONS_MD, COMMAND_MD):
        text = _text(doc).lower()
        assert "retry" in text, f"{doc.name}: says nothing about not retrying a NOT-verified verdict"
        assert "finding" in text or "answer" in text, f"{doc.name}: does not frame exit 2 as an answer/finding"


def test_verify_reads_the_token_not_the_prose() -> None:
    """verify answers from the signed token; approval-judge / Approval log are ignored.

    This is the whole point of the token: prose is exactly what a forger
    rewrites. A doc that let an agent 'verify' by reading approval-judge:
    would defeat ai-maestro#47 entirely.
    """
    for doc in DOCS:
        text = _text(doc)
        assert "approval-token" in text, f"{doc.name}: never mentions the approval-token"
        assert "approval-judge" in text, f"{doc.name}: does not say approval-judge is IGNORED by verify"


def test_verify_checks_signature_anchor_title_and_floor() -> None:
    """The four things verify actually checks are documented (not just 'it verifies')."""
    text = _flat(INSTRUCTIONS_MD).lower()
    for claim in ("signature", "ledger anchor", "still", "min-approval-requirement"):
        assert claim in text, f"instructions.md: verify's check of '{claim}' undocumented"


def test_identity_not_content_caveat_is_present() -> None:
    """Every doc states that a verified approval does NOT vouch for the card's body.

    The token binds an approval to the card's IDENTITY, not its CONTENT: a body
    edited after approval still verifies, because the approval is authentic.
    Overstating this is a false security claim — and precisely the claim someone
    editing a body post-approval would want made on their behalf.
    """
    for doc in DOCS:
        text = _flat(doc)
        assert re.search(r"identity,?\s*(\*\*)?\s*not\s+(its\s+)?content", text, re.I), f"{doc.name}: missing the identity-not-content caveat"


def test_authority_ladder_and_its_two_hard_limits() -> None:
    """The ladder plus: no agent approves a user-floor card; no one self-approves."""
    for doc in DOCS:
        text = _flat(doc)
        assert "min-approval-requirement" in text, f"{doc.name}: authority source undocumented"
        for rung in ("none", "orchestrator", "chief-of-staff", "manager", "user"):
            assert rung in text, f"{doc.name}: ladder rung `{rung}` missing"
        assert re.search(r"own\s+proposal", text, re.I), f"{doc.name}: the no-self-approval limit is missing"
        assert re.search(r"MANAGER\s+included", text, re.I), f"{doc.name}: does not state that no-self-approval binds MANAGER too"


def test_nothing_is_committed_for_you() -> None:
    """The docs state the CLI commits nothing, and that staging is BY NAME.

    Pairs the CLI's own contract with this repo's never-`git add -A` rule: an
    agent told 'commit the result' without 'by name' is one habit away from
    staging whatever else is untracked.
    """
    for doc in DOCS:
        assert re.search(r"[Nn]othing is committed for you", _flat(doc)), f"{doc.name}: does not warn that the CLI commits nothing"
    for doc in (SKILL_MD, INSTRUCTIONS_MD):
        assert re.search(r"by name", _flat(doc), re.I), f"{doc.name}: staging-by-name unstated"


def test_all_eight_verbs_documented_in_skill_and_command() -> None:
    """All eight subcommands appear in both the skill and the command doc."""
    verbs = ("search", "read", "verify", "edit", "approve", "refuse", "promote", "archive")
    for doc in (SKILL_MD, COMMAND_MD):
        text = _text(doc)
        missing = [v for v in verbs if f"`{v}" not in text]
        assert not missing, f"{doc.name}: undocumented verb(s): {missing}"


def test_instructions_toc_matches_its_headings() -> None:
    """The TOC anchors in instructions.md all resolve to real `##` headings.

    A rotted TOC is the classic broken-reference: the doc looks navigable and
    silently isn't.
    """
    text = _text(INSTRUCTIONS_MD)
    headings = re.findall(r"^##\s+(.+?)\s*$", text, re.M)

    def slug(h: str) -> str:
        s = h.lower()
        s = re.sub(r"[^\w\s-]", "", s)
        return re.sub(r"\s+", "-", s.strip())

    real = {slug(h) for h in headings}
    anchors = set(re.findall(r"^-\s+\[[^\]]+\]\(#([a-z0-9-]+)\)", text, re.M))
    assert anchors, "instructions.md: no TOC anchors found"
    dangling = anchors - real
    assert not dangling, f"instructions.md: TOC anchors with no heading: {sorted(dangling)}"


def test_skill_body_links_instructions_as_markdown_link() -> None:
    """SKILL.md links references/instructions.md as a real markdown link.

    A bare backtick path is a CPV MINOR and, more importantly, is not clickable
    for the agent reading it.
    """
    assert "[Full step-by-step instructions](references/instructions.md)" in _text(SKILL_MD), "SKILL.md: instructions.md is not linked as a markdown link"


def test_report_path_uses_porcelain_not_a_column_split() -> None:
    """The report recipe resolves MAIN_ROOT with --porcelain.

    Plain `git worktree list` prints `<path> <sha> [<branch>]`, so any column
    split truncates a path containing a space (routine on macOS) and writes the
    audit trail to a directory that does not exist, while reporting success.
    """
    text = _text(INSTRUCTIONS_MD)
    assert "git worktree list --porcelain" in text, "instructions.md: report path not --porcelain"
    assert "awk '{print $1}'" not in text, "instructions.md: uses the truncating awk idiom"
