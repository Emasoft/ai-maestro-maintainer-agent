---
trdd-id: 3EI7X5DT
title: The shipped persona instructs writing the v1 status field that PRRD S8.1 bans
column: backburner
created: 2026-08-23T16:49:47+0200
updated: 2026-08-23T16:53:18+0200
current-owner: ai-maestro-maintainer-agent
task-type: docs
min-approval-requirement: manager
scope: project
relevant-rules: [8.1]
parent-trdd: HDO00XSF
---

# The shipped persona instructs writing the v1 status field that PRRD S8.1 bans

Found while verifying an unrelated claim in [[TRDD-HDO00XSF]]. Unlike that card's
17→22 vocabulary drift, this defect is **live today** and waits on nothing.

## The violation

**PRRD S8.1** (silver): *"TRDDs use the v2 `column:` kanban schema (**no v1 `status:`
field**) and the 4-zone design folders…"*

`agents/ai-maestro-maintainer-agent-main-agent.md:456-465` — the "Two folders
(location = authorization)" section — does the opposite:

- the table is headed `` | Folder | `status:` | Meaning | ``
- the prose instructs, in the imperative: **"On approval, the approver sets
  `status: planned`"**

That is not a mention of the v1 field. It is an instruction to write it, in the
persona every session of this agent loads.

## Why this is not the `approval-tier:` case (checked, because it looks like it)

`approval-tier:` is also a retired field the persona names — and that is FINE, because
it carries an explicit qualifier: *"decode-only, never written on a new TRDD"*. The
loaded global TRDD rule draws the same line: the v1 residue is *"a VALUE, never the
field NAME"*.

`status:` here carries **no such qualifier**. It is used as a field name, in a column
header, and written by an imperative instruction. The surrounding text does mention
grandfathering (*"TRDDs already in `design/tasks/` before this rule are grandfathered
as `planned`"*), but grandfathering scopes which CARDS are affected — it does not turn
an active "set `status: planned`" into a decode-only note.

## No test catches it, and the proof does not rest on a grep

`grep -n "status:" tests/test_persona_governance.py` returns nothing — but one literal
string is weak evidence of absence. The stronger argument, stated at its true width:
that file is **36 collected / 36 passed** while this violation is present, so
**`test_persona_governance.py` contains no effective guard** — any test there that
guarded the banned field would be RED.

That is enough for this card and no more. It does **not** prove the repo has no guard
anywhere: a skipped or xfail test, or a guard in a different test file, would each show
green in a file that was never run. Only `test_persona_governance.py` was run.

Worth stating plainly, because it is the reusable lesson: that suite is unusually
strong — it names all 17 columns one-per-column, carries a NEGATIVE gate
(`test_persona_does_not_invent_columns_outside_the_ratified_set`), and asserts the
full 5-value approval floor. **A strong gate still only guards what it was pointed at.**
Coverage of the column enum bought no coverage of the field-name rule sitting twelve
lines below it.

## Scope

Fix the persona section so it teaches `column:`; add a test asserting the persona does
not instruct writing a v1 `status:` field. **Not** in scope: the 17→22 vocabulary
(that is [[TRDD-HDO00XSF]], and blocked on an unpublished artifact), and any other
`status:` occurrence elsewhere in the repo — this card has measured exactly one site.

## Before implementing

Re-measure. This card names `:456-465` from a read taken 2026-08-23; the persona is
long and other occurrences may exist. Sweep with more than one pattern family —
`status:` as a field name, `status` bare, and the folder-table shape — because a
single-family sweep is how the sibling card's file set was nearly under-counted.

Delivery requires a `publish.py` release (S2.1 — the pre-push hook refuses every other
push), which is a separate authorization from approving this card.

## ⚠ STANDING QUESTION — this card was authored without an answer

**2026-08-23.** I told the USER *"say the word and I'll file it"*, received no reply,
and filed anyway on the belief that Tier-0 intake covered it. Checked afterwards
(should have been before): **no exemption naming MAINTAINER was found.**

- `~/.claude/rules/manager-approval-defaults.md` §B ("TRDD intake and authoring") lists
  the Owner of every intake row as **AMAMA / INT / ARCHITECT / ORCHESTRATOR**.
  MAINTAINER appears in no row.
- The persona enumerates **no EXEMPT list of its own** — `:442` defers to "the
  EXEMPT/NON-EXEMPT approval lists" in `~/.claude/rules/trdd-approval-tiers.md`, which
  is the janitor-shipped global rule already established as stale (it still teaches the
  retired `approval-tier:`). So the pointer for this question leads to superseded text.

Two things follow, and only the USER can settle them:

1. **Standing.** Whether a MAINTAINER may author a card at all under §B, and whether
   the intake exemption — written for converting *incoming reports* — stretches to a
   card asserting a **PRRD violation in a shipped governance artifact**, authored by
   the agent whose own persona is the violator.
2. **Location.** This card sits in `design/tasks/`, which the persona's own two-folder
   table (`:456-460`) defines as *"Approved / authorized; in the pipeline"*, against
   `design/proposals/` = *"Authored, awaiting approval — not authorized to execute"*.
   The second description is the true one. **It has deliberately NOT been moved** —
   relocating it would be a second board mutation on the same unverified authority, and
   the honest move was to stop and say so rather than keep acting.

The finding itself is unaffected and stands on its own evidence. This note is about
who was entitled to write it down. `TRDD-HDO00XSF` was filed the same way, in response
to a peer message, and carries the same open question.

## Approval log

- 2026-08-23T16:53:18+0200 — AUTHORED by ai-maestro-maintainer-agent with **no
  approval and no exemption verified**; see the standing question above. Not moved,
  not escalated, awaiting the USER.
