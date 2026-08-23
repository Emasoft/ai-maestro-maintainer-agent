---
trdd-id: 3EI7X5DT
title: The shipped persona instructs writing the v1 status field that PRRD S8.1 bans
column: backburner
created: 2026-08-23T16:49:47+0200
updated: 2026-08-23T16:49:47+0200
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
string is weak evidence of absence. The argument that does hold: the suite is
**36 collected / 36 passed** while this violation is present. Any test that
effectively guarded the banned field would be RED. There is no effective guard.

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

## Approval log
