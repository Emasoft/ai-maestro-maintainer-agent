---
trdd-id: VLIP8CHM
title: Close the two remaining FLEET-STATUS Q4 persona gaps and pin the governance contract with tests
column: dev
created: 2026-08-05T15:29:24+0200
updated: 2026-08-05T16:24:00+0200
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
- **`tests/test_persona_governance.py` added — 33 tests, no mocks.** Shipped in
  **v1.9.0**.
- **SLICE 2 — `ai-maestro#107` clause 2 (same TRDD, second commit).** The iron rule
  had to move from the persona into the **decision surfaces**. Measured, then fixed
  3 real gaps: `commands/maintainer-aimaestro-trdd.md` (a command runs with NO skill
  loaded), `skills/maintainer-aimaestro-trdd/SKILL.md` (the prohibition was a
  *descriptive* line in `## Scope`, not a prerequisite — the skill whose whole job is
  driving the CLI carried the weakest form), and `hooks/hooks.json` (a hook runs with
  no skill loaded either). Guarded by `tests/test_frozen_cli_prohibition.py`
  (147 tests). Full suite **926/926**.
- **SLICE 3 — the results table was lying about 310 tests.** Every PARAMETRIZED row
  rendered `(no docstring)`: `run-all-tests.py` keyed the lookup on the bracketed
  nodeid (`test_foo[SKILL.md]`) while the collector keys on the bare `def test_foo`.
  310 → 0.
- **SLICE 4 — the mention guard exempted its own worst case.** `_strip_code` blanked
  EVERY fence, so a fence containing `gh issue comment --body "… @handle …"` or
  `amp-send … "<body>"` was treated as inert. It is inert *where it sits* and its
  **output is a comment body carrying the handle bare**. Hole found by the CORE
  plugin on `ai-maestro#109` (fixed there in `07db70e`); adopted here. Measured
  first: **20 emitter fences, 0 leaks** — no live hole, but nothing would have
  reported the first one.
- **SLICE 5 — the command contract was unenforced.** 23 commands, and no test read
  them; CPV names 14 as untested. `tests/test_command_contracts.py` (118) pins
  frontmatter, description, no tool-grant keys, **`Loads skill:` resolving to a real
  skill**, local paths resolving, and the argument-hint shape. Measured: **0 findings**
  — closing the gap, not a break.
- **SLICE 5b — a CPV "dead URL" that must NOT be fixed.** `cli.github.com/packages`
  404s as a bare path and is cited 3× in the gh install recipe. It is an apt
  *repository root*: nothing fetches it. The three URLs the recipe really requests all
  return 200 (verified). "Fixing" the base would break gh install on apt AND dnf, so
  the file now carries the measurement and a DO-NOT-FIX note.
- **NEXT ACTION:** none in this repo. **PR #34** (dependabot, 10/10 checks green, both
  SHAs verified against upstream tags) is `BLOCKED` solely on `REVIEW_REQUIRED` — a
  human-approval control this agent must not satisfy itself. Handed to the USER.
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

## Slice 2 — where the iron rule actually has to live (`ai-maestro#107`)

The USER's 2026-08-02 iron rule has two clauses, and this repo passed the first
while quietly failing part of the second.

| Clause | Measured 2026-08-05 |
|---|---|
| 1 — no direct `/api/*` call | **CLEAN.** Every hit is the prohibition itself, GitLab's CI-lint endpoint, crates.io, a container healthcheck on its own `localhost:8080`, or a YAML error example. Zero target ai-maestro. |
| 2 — the SKILLS layer must *instruct* it | **3 gaps**, all fixed here. |

The argument that makes clause 2 non-cosmetic is not mine — it is
`ai-maestro-autonomous-agent`'s on `#107`: **skills load on demand and in
isolation**, so an agent that consults one skill to decide *"may I do this?"*
never sees the persona. A command and a hook are worse: they run with **no skill
loaded at all**, so "no skill instructed it" is structurally true there rather
than an oversight.

Two detector traps, both adopted from that thread rather than rediscovered:

- **Match the prohibition, not the vocabulary.** The MANAGER's first sweep grepped
  `frozen CLI` and reported 3 of 10 skills compliant; re-reading the hits showed
  two merely *used* the sanctioned path. The real number was 1. A skill that calls
  the CLI is textually indistinguishable from one that forbids the API unless you
  match on the forbidding.
- **The inverse overcount is equally real.** `maintainer-trdd-adr`'s template names
  `aimaestro-trdd.sh approve` while explaining a frontmatter field. It instructs
  nothing, and demanding a prohibition block there is how a rule becomes furniture.
  So the test's notion of "instructs" is an **executable position** — inside a
  fence, at the start of a line, or behind a `command -v` probe — never mere prose.

Both traps are pinned as their own tests, so the detector cannot drift into
matching everything or nothing.

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
- **A rule is only enforced where it is READ AT DECISION TIME.** Persona-only is
  not enforcement for a surface that loads in isolation — and a command or hook
  inherits nothing at all. Slice 2 is that lesson applied.
- **A results table that says `(no docstring)` for a third of its rows is a broken
  table, not a documentation debt.** The instinct is to go add docstrings; the
  docstrings were there. The lookup key was wrong. Read the mechanism before
  believing what a report says about the code.
- **A link checker cannot tell a dead URL from a repository root.** `…/packages`
  404s because it is not a page; the paths a consumer actually requests all
  return 200. Probe what the CONSUMER fetches, never the base — the naive fix
  here would have broken gh installation on two package managers while turning
  the warning green.
- **My own guard fired on correct writing, and I nearly "fixed" the data.**
  `argument-hint: "[--threats T1,T2,...]"` tripped a "contains a period ⇒ prose"
  check; `...` is an ellipsis, not a sentence. A guard that reddens on correct
  writing gets muted, and a muted guard protects nothing — so the discriminator
  was corrected (a word char followed by a FINAL period) and pinned in BOTH
  directions, which is what stops the next round of loosening-until-quiet.

## Approval log

- 2026-08-05T15:29:24+0200 — Tier 0, no approval required (`min-approval-requirement: none`):
  documentation of already-ratified governance vocabulary inside this agent's own
  entrusted repo, no baseline deviation, no cross-project change, reversible.
  Directed by USER in session ("fix all issues. check the issues on github.").
