---
trdd-id: HDO00XSF
title: This repo ships the 17-column kanban vocabulary that 3-pillars 3.0.0 replaced with 22
column: backburner
created: 2026-08-23T16:29:29+0200
updated: 2026-08-23T16:31:58+0200
current-owner: ai-maestro-maintainer-agent
task-type: docs
approval-tier: 2
scope: project
---

# This repo ships the 17-column kanban vocabulary that 3-pillars 3.0.0 replaced with 22

## Why this is intake only

A peer session (`ai-maestro-b9`) notified this session on 2026-08-23 that the USER
ratified **3-pillars spec 3.0.0**, widening the kanban vocabulary from 17 to 22
board columns. The peer was explicit that the artifacts live in
**Emasoft/ai-maestro, branch `governance-rules`**, and that 3.0.0 binds this repo
only once it arrives here as a real artifact. It has not.

So this card records a **measured drift**, not an authorized edit. A peer cannot
authorize a governance change (approval-tier 2: this repo's shipped persona is the
governance text every entrusted downstream repo inherits). Do not act on it until
the spec lands here or the USER says so.

## What was measured (this repo, 2026-08-23)

**Six live files.** Measured exhaustively over every tracked file
(`git ls-files | xargs grep`), matching the NUMBER (`17-column`, `exactly 17`), the
terminal column (`live_auditing`), and the ORDER (`backburner … todo`) — because a
file can be stale on the order alone: 3.0.0 moves `design` to *before* `todo`.

| file | what it is |
|---|---|
| `tests/test_persona_governance.py` | the gate — see the section below, it is real and two-sided |
| `agents/ai-maestro-maintainer-agent-main-agent.md` | the SHIPPED persona — `### The board: exactly 17 columns` at :469 |
| `skills/maintainer-trdd-adr/references/trdd-template.md` | lifecycle order handed to every authored TRDD |
| `skills/maintainer-trdd-adr/references/seed-readmes.md` | lifecycle order seeded into new repos' `design/` READMEs — **matches on ORDER only**, carries neither the number nor `live_auditing` |
| `design/tasks/README.md` | this repo's own board legend |
| `skills/the-skills-menu/SKILL.md` | menu row 17 names "17-column kanban" |

`design/archived/…-VLIP8CHM-…` also says 17 and is correctly excluded — a terminal
card is frozen historical record, not a site.

**Deliberately no per-file "site" count.** The first pass at this card published one
(7/5/3/3/3/1, "~22 sites"). Those were grep-matching LINES from an alternation that
included bare `ai_review|human_review` — tokens 3.0.0 does **not** change — so the
number counted lines needing no edit, while also missing second occurrences on a
single line. It measured the wrong population in both directions. Count the real
sites when the edit is authorized and the true vocabulary is in hand; a number that
looks precise and is not is worse than no number.

## The claimed 3.0.0 vocabulary (peer's words, NOT verified against an artifact)

```
backburner, approval, design, design_ai_review, design_human_review, todo,
verify_assumptions, plan, dispatch, dev, testing, ai_review, human_review,
complete, publish, published, deploy, live, live_auditing
+ blocked, failed, superseded
```

Five new; `design` MOVED to before `todo`; nothing removed; snake_case. Legal
`column:` set claimed to be 27 — the 5 bracket values (`proposal`, `planned`,
`refused`, `completed`, `cancelled`) unchanged and outside the board.

**Verify this list against the real artifact before writing a single character of
it into this repo.** It is currently hearsay relayed through a socket.

## The gate is real, and it is TWO-SIDED — verified by running it

✓ VERIFIED by `uv run pytest tests/test_persona_governance.py -v --no-header`:
36 collected, 36 passed, 0 skipped, 0 xfail. **Three** distinct tests bind the
vocabulary, and the third is the one that matters most:

1. `test_persona_states_the_kanban_has_exactly_17_columns` — hardcodes the number.
2. `test_persona_names_every_one_of_the_17_columns[…]` — 17 separately-collected
   parametrized IDs, one per column (`[backburner]` … `[superseded]`). Positive gate:
   fails if a ratified column disappears from the persona.
3. `test_persona_does_not_invent_columns_outside_the_ratified_set` — **negative gate**.
   Fails if the persona names a column *outside* the set.

Consequence for the migration: (3) means the persona **cannot** be updated to 3.0.0
first and the test second. Adding `approval`, `design_ai_review`,
`design_human_review`, `verify_assumptions`, `plan` to the persona turns the suite
red immediately. Persona and test must move in the SAME change — which is the
correct design, and is why this file is an asset here rather than an obstacle.

The uncovered half is the three skill/reference files and the two READMEs; nothing
fails if those stay on 17.

**How this was nearly gotten wrong.** The first pass at this card asserted the gate
was real *without opening or running anything* — inferred from an ARCHIVED card
(VLIP8CHM) that described what the test *would* do, plus two grep line numbers
proving a LIST exists. A plan is a proxy for an implementation, and a list is a
proxy for an assertion. The conclusion happened to hold; the method did not support
it, and this repo's own memory carries the note for exactly this trap
(*"a green gate may be pointed at nothing"*). One `pytest -v` settled it in 0.03s —
and paid for itself by surfacing the negative gate, which no amount of grepping
would have revealed.

## Do NOT

- Edit `~/.claude/rules/universal-kanban.md`. It is janitor-shipped, still says 17,
  and the peer flagged it as stale-not-authoritative. It is not this repo's to fix.
- Touch the ratified GitHub branch-ruleset baseline. The peer confirmed 3.0.0 does
  not change `baseline-history-protect` / `baseline-pr-and-checks` /
  `baseline-tag-protect`, and this repo's memory already records that slice as done.
- Re-evaluate non-archived cards. The USER's mandate to do that was issued about
  ai-maestro's corpus and does not cross the repo boundary.

## Next action when authorized

1. Read the real 3.0.0 artifact from `Emasoft/ai-maestro@governance-rules` — do not
   trust the list above.
2. Update the 6 live files in one batch, persona first.
3. Update `tests/test_persona_governance.py` in the SAME change — not optional
   tidiness: the negative gate (test 3 above) turns the suite red the instant the
   persona names a 3.0.0-only column, and a test edit landing without the persona
   edit is a gate pointed at nothing. All three tests move together, and the
   function names carrying the literal `17` must be renamed too.
4. Delivery requires a `publish.py` release (the pre-push hook refuses every other
   push), which is NON-EXEMPT and needs USER authorization separately.

## Approval log
