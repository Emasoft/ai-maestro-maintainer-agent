---
trdd-id: HDO00XSF
title: This repo ships the 17-column kanban vocabulary that 3-pillars 3.0.0 replaced with 22
column: backburner
created: 2026-08-23T16:29:29+0200
updated: 2026-08-23T16:49:47+0200
relevant-rules: [1.2, 8.1]
current-owner: ai-maestro-maintainer-agent
task-type: docs
min-approval-requirement: manager
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

**Six live files that DEFINE the vocabulary.** Confirmed by the UNION of two
independent searches — and the word "exhaustive" is not claimed for either one alone,
because neither is a superset of the other:

- **Mesh A** (shape-dependent): the NUMBER (`17-column`, `exactly 17`), the terminal
  column (`live_auditing`), the ORDER (`backburner … todo` on one line). A file can be
  stale on the order alone — 3.0.0 moves `design` to *before* `todo`.
- **Mesh B** (shape-independent, tracked + untracked via
  `git ls-files --cached --others --exclude-standard`): the bare tokens
  `backburner|live_auditing|human_review`, no number, arrow, adjacency or line shape.

**Each mesh caught a file the other missed**, which is the whole reason both are
recorded here:

- Mesh A alone missed nothing new, but only after a fifth pattern was hand-added on a
  hunch when `seed-readmes.md` failed to appear.
- **Mesh B missed `skills/the-skills-menu/SKILL.md`** — ✓ VERIFIED by grepping that
  file directly for all three bare tokens: no match. Its text is "17-column kanban".
- **Mesh A missed `.cspell-project-words.txt`** — a spellcheck dictionary carrying
  `backburner` as a word (line 46). Not a governance definition. **POSSIBLE**
  dependent site, deliberately not stated as more: `.cspell.json`, `.mega-linter.yml`
  and `.github/workflows/ci.yml` all exist, so a gate plausibly exists — but nothing
  here verifies that cspell runs on the files carrying columns, how it splits
  `snake_case`, or whether an unknown word fails or merely warns. This repo's memory
  already records cspell running **dictionary-less for months** behind
  `VALIDATE_ALL_CODEBASE: false`, so "a green gate may be pointed at nothing" cuts
  both ways: an unverified gate may also fire on nothing. Check it when the edit is
  authorized; do not plan around it before.

Mesh B also returned 8 files that merely USE a column value in their own `column:`
field (5 live cards, 2 archived cards, `CHANGELOG.md`). Verified none of them define
the vocabulary. High recall, low precision — the delta had to be classified by hand,
not counted.

| file | what it is |
|---|---|
| `tests/test_persona_governance.py` | the gate — see the section below, it is real and two-sided |
| `agents/ai-maestro-maintainer-agent-main-agent.md` | the SHIPPED persona — `### The board: exactly 17 columns` at :469 |
| `skills/maintainer-trdd-adr/references/trdd-template.md` | lifecycle order handed to every authored TRDD |
| `skills/maintainer-trdd-adr/references/seed-readmes.md` | lifecycle order seeded into new repos' `design/` READMEs — **matches on ORDER only**, carries neither the number nor `live_auditing` |
| `design/tasks/README.md` | this repo's own board legend |
| `skills/the-skills-menu/SKILL.md` | menu row 17 names "17-column kanban" — **invisible to Mesh B** |
| `.cspell-project-words.txt` | dependent site, not a definition — carries `backburner` as a dictionary word |

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

## This card was itself written from a stale global rule — measured, not theorised

Its frontmatter originally read `approval-tier: 2`. That field is **RETIRED**
(USER ruling 2026-07-10); the live field is `min-approval-requirement:` on the ladder
`none < orchestrator < chief-of-staff < manager < user`. It has been corrected to
`min-approval-requirement: manager`.

✓ VERIFIED first-hand in this repo, not taken from the peer:
`skills/maintainer-aimaestro-trdd/references/instructions.md:186` — *"Approval authority
is read from the card's own `min-approval-requirement:`"* — and the persona suite that
was run for this card already proves it, with
`test_persona_carries_the_full_approval_floor_enum[none|orchestrator|chief-of-staff|manager|user]`
(5 IDs, passing) plus `test_persona_treats_the_numeric_tier_field_as_decode_only`.

The wrong field was written by following `~/.claude/rules/trdd-approval-tiers.md`, a
janitor-shipped GLOBAL rule that still teaches the retired numeric tier. That is the
exact hazard this card is about, reproduced inside the card that reports it: a stale
global rule reads as current to every session on the machine, and this repo's own
shipped persona already contradicts it — a contradiction no test can see, because the
test guards the persona, not the rules file.

### …and the FIRST correction repeated the same mistake one level down

The replacement value `manager` was originally derived from the Tier-2 → MANAGER row
of that same stale global rule. Rejecting a source's *schema* while trusting its
*semantics* three lines later is not a correction, it is the same error wearing a new
value — and it fails **silently**, because nothing tests a card's floor: `verify`
checks the issuer's title *against* whatever the card claims, so a floor that is too
low does not error, it **approves**.

### Re-derived — and the chain was walked to its end this time

`maintainer-approval-gate` defers to
`skills/maintainer-trdd-adr/references/trdd-template.md:43-98`, which states:

- `min-approval-requirement:` floor is `none | orchestrator | chief-of-staff | manager
  | user`; **`user` is the TOP rung**; `maestro` is a read-alias, never written.
- `approval-tier:` is deprecated, **decode-only**, migrating on next touch —
  `0 → none`, `1 → chief-of-staff`, `2 → manager`, `3 → user`.

But `trdd-template.md:70` **disclaims being the authority** and names its own upstream:
`rules/aimaestro/aimaestro-trdd-approval.md`, "seeded into agent workdirs as
`.claude/rules/aimaestro-trdd-approval.md`". ✓ CHECKED: that file does **not** exist
here — `.claude/rules/` does not exist at all, and no `rules/aimaestro/` directory is
anywhere in the repo. So `trdd-template.md` is the **best available local source**,
not the canonical one, and this card says so rather than promoting a waypoint to a
terminus.

**RESOLVED as `manager`** — on the PRRD, which is the thing the trigger points AT.

The persona states a `user` trigger (`agents/ai-maestro-maintainer-agent-main-agent.md:449-454`):

> "any proposal you cannot self-authorize (Tier 2 — `min-approval-requirement:
> manager`) goes straight to MANAGER, and MANAGER forwards the **highest-stakes
> (golden / owner-identity)** ones (Tier 3 — `min-approval-requirement: user`) to
> USER."

That sentence alone does **not** settle it, and the earlier version of this card
pretended otherwise: "(golden / owner-identity)" reads as much like a gloss on
"highest-stakes" as like a closed enum, and the reading chosen was the one that
confirmed the value already written. So the antecedent was checked instead —
`design/requirements/PRRD.md`, **read whole** (42 lines), not through a window:

- **Exactly ONE golden rule exists: `G1.2`** — GitHub authorship self-identification.
  It says nothing about the kanban vocabulary, the column enum, the persona, or any
  shipped governance surface. The negative half of the argument is now GROUNDED rather
  than assumed from a general model of what a PRRD contains.
- No overlay can change that: `.claude/rules/` does not exist here (established
  above), so no seeded `aimaestro-prrd-governance.md` authority matrix is in play, and
  the PRRD's own frontmatter carries `mirrors: []`.

**A previous version of this card argued from `S8.1` being SILVER. That was a
non-sequitur and is withdrawn.** "Silver" says who may edit *the rule*; it says nothing
about the floor for *work touching the rule's subject*. Rule-mutability and
work-authorization are different axes. Worse, S8.1's scope is *"TRDDs use the v2
`column:` schema…"*, and four of the six files here are not TRDDs and are not about
what TRDDs use (the persona, `seed-readmes.md`, the skills menu, the test). Reaching
for the nearest rule containing the word `column:` was topical adjacency dressed as
governance.

**The floor comes from the floor-assignment table, read whole**
(`skills/maintainer-approval-gate/references/approval-request.md:19-24`):

| Trigger | Floor |
|---|---|
| Destructive git — force-push, history rewrite, tag/branch deletion (R19.7) | `manager` |
| Deviating from the ratified baseline rulesets | `manager` |
| **Entering the release pipeline on a TRDD you own** | **`manager`** |
| Anything golden / owner-identity — MANAGER forwards it to USER | `user` |

The migration must ship via `publish.py` (S2.1 — no other push path exists), so it
matches the third row **by name**. `manager`. Not by inheritance, not by fallback, not
by analogy.

### The falsification search — the shape never run until now

Four derivations of the same value, and every search behind them was
**confirmation-shaped**: *where is the floor defined*, *what does the trigger say*,
*what does the PRRD contain*. None asked what would make it `user`. That was run:

```
git ls-files -z | xargs -0 grep -nEi 'tier.?3|highest-stakes|owner-identity|owner-facing|breaking.*public|governance-layer|shipped surface'
```

30 hits, **clean**. Four independent enumerations of the Tier-3 set — persona `:453`,
persona `:530-531` ("GOLDEN PRRD changes, rule promote/demote, and irreversible /
owner-identity / shared-credential actions"), approval-gate `:24`, `README.md:146` —
and they agree. **None names personas, shipped artifacts, docs, or governance text.**
`skills/maintainer-prrd-trdd-kanban/SKILL.md`, whose whole subject is this
intersection, returned no escalation trigger at all.

**`manager` is SETTLED. Stop re-deriving it.** Further confirmation-shaped search has
negative value; the unfinished work on this card is the unfetchable 3.0.0 artifact.

### Found while checking: the shipped persona VIOLATES PRRD S8.1

S8.1 forbids the v1 `status:` field. The persona's folder table
(`agents/…-main-agent.md:456-465`) is headed `` | Folder | `status:` | Meaning | ``
and its prose instructs **"the approver sets `status: planned`"** — teaching the
retired field, in shipped governance text, to every reader of the persona.

✓ VERIFIED nothing guards it: `grep -n "status:" tests/test_persona_governance.py`
returns nothing. The suite that proves the persona names all 17 columns and carries
the full 5-value approval floor has **no assertion about the v1 field S8.1 bans**.
This is the same class as the whole card — a governance defect in prose that no test
can see — but unlike the 17→22 drift it is live *today* and does not wait on 3.0.0.
Out of scope here: **filed separately as `TRDD-3EI7X5DT`.**

(The "no test guards it" grep was one literal string and is weak on its own. The
stronger argument does not depend on it: the suite is 36/36 GREEN while a real
violation is present — any test that effectively guarded the banned field would be
RED. That holds whatever string was grepped.)

Two supports used in the previous pass have been **dropped as unsound**, not merely
softened: "absent/unknown resolves to `manager`" is a fallback for cards whose author
did not decide and says nothing about a case that was decided; and `:96` ("the
MAINTAINER files manager-floor proposals directly to MANAGER") is a **routing** rule
that presupposes the floor rather than assigning it. Neither supports the value; the
persona quote above does, on its own.

### A further finding: the shipped persona POINTS AT the stale rule

`agents/…-main-agent.md:445` closes the approval section with
**"Reference: `~/.claude/rules/trdd-approval-tiers.md`"** — the same janitor-shipped
global rule that still teaches the retired `approval-tier:`. The persona's own text is
correct; its *pointer* sends the reader to superseded governance. That raises the
stale-rule issue from "a session might read it" to "this project's persona cites it".
Worth attaching to whatever goes to the USER about those two global files.

⚠ Not claimed: how far that pointer travels. "Ships to every entrusted downstream
repo" was asserted repeatedly earlier in this thread **without ever verifying the
distribution mechanism** — whether downstream repos receive this persona file, or
merely have the plugin installed, is a different claim and an unchecked one. Check it
before repeating it.

## Do NOT

- Edit `~/.claude/rules/universal-kanban.md` (still says 17) or
  `~/.claude/rules/trdd-approval-tiers.md` (still teaches `approval-tier:`). Both are
  janitor-shipped global rules asserting superseded governance, both are the USER's
  own files, and neither is this repo's to fix. The peer is raising both to the USER.
  Do not "restore the ratified baseline" from either text.
- Touch the ratified GitHub branch-ruleset baseline. The peer confirmed 3.0.0 does
  not change `baseline-history-protect` / `baseline-pr-and-checks` /
  `baseline-tag-protect`, and this repo's memory already records that slice as done.
- Re-evaluate non-archived cards. The USER's mandate to do that was issued about
  ai-maestro's corpus and does not cross the repo boundary.

## BLOCKER — the 3.0.0 artifact is UNPUBLISHED

The same peer corrected itself on 2026-08-23: `governance-rules` is **unpushed**
(it reported 282 commits ahead, then 284 — the number moves as it works), published
state is **2026-08-21**. It cited the branch as fetchable; it is not. So step 1 below
is **not runnable today** — there is nothing to read, and the vocabulary in this card
remains hearsay with no path to verification from this repo. Everything in this
section is the peer's assertion recorded AS the peer's assertion; none of it is
measured here.

Five spec repairs the peer reported after the first message (from commit `928c96b3`
onward), all found by peers, none by any test:

- **3P-KAN-20** — the legal `column:` set is **27**, not 22; the 5 bracket values sit
  outside the board. (This card already said 27/22/5 — consistent, no change.)
- **3P-KAN-10** — `human_review` is now a **RESTING** column. If that lands here it
  matters to this board directly: two cards (`TRDD-DBT8UACO`, `TRDD-PY5QXSBU`) sit at
  `human_review` and would be correctly *parked* rather than stalled.
- **3P-KAN-21** (later WIDENED) — grandfathering is not just `todo`: **three** columns
  changed meaning, and `design` and `backburner` drift in **opposite directions**.
  That reaches this board directly — four live cards sit at `backburner`, including
  this one. Read the widened text before re-columning anything.
- **3P-KAN-22** — the approver is DERIVED from the column or from
  `min-approval-requirement:`; no new field is minted. Consistent with this repo,
  where `min-approval-requirement:` is already the only floor field.

## Next action when authorized AND the artifact is published

1. Read the real 3.0.0 artifact from `Emasoft/ai-maestro@governance-rules` — do not
   trust the list above. **Blocked until it is pushed** (see above).
2. Update the 6 live files in one batch, persona first.
3. Update `tests/test_persona_governance.py` in the SAME change — not optional
   tidiness: the negative gate (test 3 above) turns the suite red the instant the
   persona names a 3.0.0-only column, and a test edit landing without the persona
   edit is a gate pointed at nothing. All three tests move together, and the
   function names carrying the literal `17` must be renamed too.
4. Delivery requires a `publish.py` release (the pre-push hook refuses every other
   push), which is NON-EXEMPT and needs USER authorization separately.

## Approval log
