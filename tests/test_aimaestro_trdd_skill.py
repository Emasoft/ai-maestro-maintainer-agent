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


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_verify_is_marked_absent_on_the_deployed_script(doc: Path) -> None:
    """Every doc flags that `verify` is NOT on the deployed CLI and must be probed.

    Teaching `verify` as unconditionally available is a false capability claim: it
    exists on governance-rules and in the manifest, but not on the deployed copy.
    An agent that believes it can check authenticity, and cannot, is worse off than
    one that knows it cannot — it may fall back to trusting the card's prose, which
    is precisely what the token design exists to stop.
    """
    text = _flat(doc)
    assert re.search(r"not\s+(on\s+the\s+deployed|implemented\s+on\s+this\s+host)", text, re.I), f"{doc.name}: does not state that `verify` is absent from the deployed script"
    assert "69" in text, f"{doc.name}: does not cite ai-maestro#69 for the verify gap"


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
