---
trdd-id: VLIP8CHM
title: Close the two remaining FLEET-STATUS Q4 persona gaps and pin the governance contract with tests
column: dev
created: 2026-08-05T15:29:24+0200
updated: 2026-08-05T15:29:24+0200
current-owner: ai-maestro-maintainer-agent
created-by: ai-maestro-maintainer-agent
task-type: docs
release-via: publish
min-approval-requirement: none
approved: true
npt: []
eht: []
implementation-commits: []
relevant-rules: []
---

# Close the two remaining FLEET-STATUS Q4 persona gaps (issue #29)

## ⏵ STATE — READ THIS FIRST ON RESUME (authoritative; supersedes the body) — 2026-08-05

- **Both gaps CLOSED** in the persona `agents/ai-maestro-maintainer-agent-main-agent.md`:
  the 17-column board vocabulary (new `### The board: exactly 17 columns` subsection)
  and the seeded read-only `.claude/rules/aimaestro-*.md` overlays (new
  *Seeded rules are not yours to edit* Key Constraints row, with the precedence
  tie-break and the content-probe pattern).
- **`tests/test_persona_governance.py` added — 33 tests, no mocks.** Full suite
  **779/779**. `ruff check` + `mypy` clean.
- **NEXT ACTION:** none — released, and answered on #29.
- **THE BUG THE TESTS FOUND ON THEIR FIRST RUN:** the persona stated the mandatory
  byte-exact self-id line WRAPPED across a line break inside its backticks
  (`…the Claude responsible\n  for the ai-maestro-maintainer-agent…`). It is the
  canonical source every other site copies, and all 14 other sites happened to be
  unwrapped — so the one file that DEFINES the literal was the only one that could
  not be copied from. Fixed by lifting the line onto its own line with an inline
  comment saying why it must stay there.
- Load-bearing: the third Q4 bullet (`min-approval-requirement:`) was already
  closed by `TRDD-27IG72GX` — do NOT re-do it.

## Context

`Emasoft/ai-maestro-maintainer-agent#29` (FLEET-STATUS) asked, in Q4, whether this
persona knows three governance facts. The honest answer at the time was **NO** to
all three. One was closed three weeks ago by `TRDD-27IG72GX`; a grep on 2026-08-05
confirmed the other two were still open:

| Q4 bullet | State before this TRDD |
|---|---|
| TRDD is the unit of work; `column:` is the state machine | already **yes** |
| `min-approval-requirement:` + mandate semantics | **closed** by `TRDD-27IG72GX` (`cad3aae`) |
| the kanban has exactly **17 columns** | **open** — zero hits for `kanban` or `17 column` in the persona |
| seeded read-only `.claude/rules/aimaestro-*.md`, restored if edited | **open** — the persona knew the frozen CLI, not the seeded rule files |

Both gaps had survived three weeks of green builds because **no test read the
persona for content** — only `test_fast_security_scan.py` and
`test_sentinel_rules_a.py` touched the file, and both incidentally. A fact that
matters to other agents but is verified by nobody is a fact that quietly rots.

## Scope

The persona plus a test file that pins the fleet-facing contract. NOT in scope:
any change to ai-maestro's repo (cross-project — issues only), and the unanswered
half of #29 Q7.3 (which seeded files exist, exhaustively) — that is the server's
to enumerate.

## What changed

1. **`### The board: exactly 17 columns`** — the vocabulary in pipeline order, the
   3 exception columns, the `release-via:` terminal branch, the note that the
   folder-lifecycle values BRACKET the pipeline rather than extending it, and the
   drain obligation (`blocked-by:` is the only licence to sit still; one worker
   means roughly one card in `dev`).
2. **Key Constraints row *Seeded rules are not yours to edit*** — read-only,
   **restored if edited**, never copied into the repo; the **precedence tie-break**
   (the overlay is the host contract and wins on governance, the persona wins on
   how this agent works, and a genuine contradiction is followed *and reported* to
   MANAGER); and the **content probe**
   (`grep -q min-approval-requirement .claude/rules/aimaestro-trdd-approval.md`),
   never a version or branch check.
3. **`tests/test_persona_governance.py`** — 33 assertions over the shipped persona.

### Why the precedence rule is a derivation, not a guess

`#29` said only *"your persona must not fight them"*, and `#29` Q7.3 asked for a
tie-break that was never answered. The rule written here is not an invention: a
file the server **restores if edited** cannot be fought, so it necessarily wins —
the only open question was what happens to the disagreement, and dropping it
silently is the one answer that is definitely wrong. Hence: follow the overlay,
report the contradiction. If the server intends otherwise it is a one-line change,
and #29 now carries the claim explicitly so it can be corrected.

## Verification

- `uv run pytest tests/test_persona_governance.py -q` → 33 passed.
- `uv run tests/run-all-tests.py` → **779/779**.
- `uv run ruff check` + `mypy` on the new file → clean.
- CPV remote-validate `--strict` → 0 CRITICAL / 0 MAJOR / 0 MINOR / 0 NIT.
- The parametrized column test names each of the 17 columns individually, so a
  partial regression reports *which* columns went missing rather than one opaque
  failure.

## Notes and lessons learned

- **A parametrized assertion per item beats one assertion over a list.** The
  17-column test is `@pytest.mark.parametrize`d one-per-column deliberately: a
  single `all(c in persona for c in COLUMNS)` reports one failure whether one
  column or fourteen went missing, and the count is the whole diagnosis.
- **A test that derives its expected value from the file under test proves
  nothing.** The column tuple is written out longhand in the test rather than
  parsed out of the persona, which is the only version that can fail.
- **Wrapped verbatim strings.** A literal that MUST be byte-exact should never be
  laid out where prose wrapping can break it. The persona had exactly that defect
  in the one place it defines the string for everyone else.

## Approval log

- 2026-08-05T15:29:24+0200 — Tier 0, no approval required (`min-approval-requirement: none`):
  documentation of already-ratified governance vocabulary inside this agent's own
  entrusted repo, no baseline deviation, no cross-project change, reversible.
  Directed by USER in session ("fix all issues. check the issues on github.").
