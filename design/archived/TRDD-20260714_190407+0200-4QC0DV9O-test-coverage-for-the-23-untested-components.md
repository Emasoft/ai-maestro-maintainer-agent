---
trdd-id: 4QC0DV9O
title: Ship a test for each of the 23 components that have none — almost all of commands/
column: published
created: 2026-07-14T19:04:07+0200
updated: 2026-08-12T19:52:00+0200
implementation-commits: [d98ebab, eedc3e8, 7974049]
current-owner: ai-maestro-maintainer-agent
task-type: audit
release-via: publish
relevant-rules: [1]
parent-trdd: A6NY2TJU
---

# Ship a test for each of the 23 components that have none

## ⏵ STATE — READ THIS FIRST ON RESUME (authoritative; supersedes the body) — 2026-08-01

**Re-derived from CPV v2.158.0 `--strict` on 2026-08-01** (the body's figures are the
2026-07-14 snapshot and are SUPERSEDED):

| | 2026-07-14 | 2026-08-01 |
|---|---|---|
| untested components | 23 | **21** |
| testable components | 56 | **63** |
| test files CPV counts | 41 | **47** |

**The gap did not close — it churned.** Three components the original list named now have
tests (`maintainer-prrd-trdd-kanban`, the `maintainer-secrets-scan` skill, `the-skills-menu`),
and four NEW untested components arrived in the same window:
`skills/maintainer-worktree/SKILL.md`, `commands/maintainer-worktree.md`,
`commands/maintainer-show-branch-rules.md`, `commands/maintainer-triage-pr.md`. Net −2 over
18 days, while the testable surface grew by 7. **A component is still shipping without its
test** — that is the finding, not the count.

**NEXT ACTION** — unchanged and still step 1 of Approach: a table-driven contract test over
`commands/` (16 of the 21 are commands). Re-derive the list at the time of work; it moves.

### 2026-08-11 — step 1 SHIPPED, and the pass criterion is unreachable BY DESIGN

**Step 1 is done.** `tests/test_command_contracts.py` landed 2026-08-05: 23 commands ×
6 parametrized assertions (frontmatter valid, no tool-grant keys, `Loads skill: **x**`
resolves to a real skill, backticked local paths resolve, `argument-hint` is a slot list),
plus 2 calibration tests and an orphan-skill counter. The STATE above predated it and kept
asserting it as pending — the second stale card found today.

**Re-derived from CPV v5.3.0 `--strict`, 2026-08-11:** `RC-TEST-COVERAGE` = **16 of 64**
untested (was 21 of 63). Fifteen are commands — *including all the ones
`test_command_contracts.py` covers.* So shipping step 1 moved the number by zero.

**Why: the metric matches a component's NAME as a literal string inside test sources.**
Measured, with perfect separation across all 23 commands:

| | literal name in some `tests/*.py` | CPV verdict |
|---|---|---|
| the 8 unflagged commands | yes, all 8 | "tested" |
| `protect-branch`, `commit-msg-hook`, `redact-text`, `worktree` | no, none | "untested" |

It is wrong in **both** directions, and each half is checkable:

- **OVER-CREDIT.** `commands/maintainer-config-lint.md` counts as tested. The only literal
  occurrence of that string in `tests/` is `test_skill_contracts.py:53`, which never reads
  `commands/` at all — it reads `skills/maintainer-config-lint/references/…`. The command is
  credited for a test of the same-named SKILL that cannot fail if the command breaks.
- **UNDER-CREDIT.** `test_command_contracts.py` covers every one of the 23 by globbing, so
  it names none of them literally, and earns credit for none.

**The Approach and the Pass criteria below therefore contradict each other:** step 1
prescribes a table-driven test, and a table-driven test can never clear the warning. That
conflict was invisible until the test was written and the number did not move.

**REVISED PASS CRITERION** (the old one is SUPERSEDED — do not carry it forward): every
command has an assertion that fails when *that* command breaks, verified by breaking one
deliberately. **Silencing `RC-TEST-COVERAGE` is explicitly NOT the goal** — the cheap way to
clear it is to spell each name in a string, which buys a number and no safety. That is the
gaming this plugin refuses when it audits others.

**Genuinely remaining**, after removing what the metric mis-reports: per-command EXECUTION
tests where a real fixture is cheap (the second half of step 1; `test_protect_branch_contexts.py`
is the reference shape — it extracts the recipe from the shipped doc and RUNS it), and
`skills/maintainer-worktree/SKILL.md`. Steps 2 and 3 are largely absorbed:
`cpv_network_resilience` has `test_network_resilience_classifiers.py`, and the card's own
body already notes `maintainer-redact` / `maintainer-sandbox` were mis-listed.

The metric defect is CPV's, not mine — reported upstream as **CPV#207** rather than worked
around here.

**SHIPPED THIS PASS — v1.13.6, commit `d98ebab`.** Re-deriving the coverage question found a
hole the metric never mentioned, on the SKILL side: `test_skill_contracts.py` parametrized
over a hand-maintained `AUDIT_UNCOVERED_SKILLS` holding **24 names while 32 skills shipped**,
so `maintainer-approval-gate`, `-commit-msg-why`, `-guardian`, `-macos-notarize`, `-redact`,
`-sandbox`, `-worktree` and `workflow-bootstrap` had no contract coverage at all — and the
file reported green, because a parametrized test over a short list passes exactly like a
complete one. The scope is now globbed from `skills/*/SKILL.md` (135 tests, up from 96; all
eight newly-covered skills pass, so this closed a prospective hole, not a live break), and
`test_the_contract_scope_is_derived_and_covers_every_shipped_skill` re-walks the filesystem
independently so it still bites if the glob is replaced by a list. Control: fed the exact
pre-fix 24-name list, it fails naming all eight.

Note what that says about the metric: the ONE genuine coverage hole in this repo was on a
surface `RC-TEST-COVERAGE` reported as fine, and it surfaced from reading the test source,
not the warning.

**SHIPPED v1.13.7, commit `eedc3e8` — the execution half, with the reference shape corrected.**
`tests/test_command_cli_contracts.py`: every `uv run scripts/*.py [verb] [--flags]` a command
doc prints is checked against that script's REAL `--help` (argparse's own `{a,b,c}` set), so a
renamed subcommand or dropped flag fails here instead of at the user's prompt. Both sides
derived; 4 invocations across 3 scripts today. Controls: a typo'd verb and a fabricated flag are
both rejected, and an empty extraction fails rather than passing vacuously.

**Correction to this card's own Approach, found by trying it.** `test_protect_branch_contexts.py`
was named as the shape to copy — extract the recipe from the doc and RUN it. That works on a
SKILL reference, which ships executable recipes. It does NOT transfer to `commands/`: of the four
commands with a bash fence, three hold a usage synopsis (`precheck <pkg-spec>`,
`--ecosystem npm|pypi`) or a slash-command example, and only one is a literal runnable line.
Executing those would be executing placeholders. What IS executable on a command doc is the
CLI CONTRACT — the verb and flags it advertises — which is what shipped.

**Also fixed while the release gate caught it (v1.13.7, `7974049`):** the publish blocked on a
leaked sandbox container, which turned out to be two defects — `_kill_orphans` swallowed a failed
`docker rm -f` (fire-and-forget, `check=False`), and the guard for it raced the asynchronous
`--rm` teardown. Both fixed with a control. Not in this card's scope; recorded here because the
card's own pass criterion is "every new test fails when its subject is broken", and this is what
that criterion looks like when it fires on the OLD tests.

**NEXT ACTION:** the remaining named component is `skills/maintainer-worktree/SKILL.md`, which
v1.13.6 already brought under the globbed skill contract — so re-derive before assuming there is
work left. If CPV still names it, that is CPV#207's name-matching, not a coverage gap; confirm by
reading the contract's parametrization, not the warning.

**SUPERSEDED — do NOT carry forward:** "23 of 56", "suite of 41 test files", and the
component list in `## Why` below. Re-derive, never cite them.

**Found while recounting, and then REFUTED — do not re-open.** CPV also reports
`RC-DEP-TAG-PIPELINE` ("publish.py tags `v{version}` but never
`ai-maestro-maintainer-agent--v{version}`, so dependents install with `no-matching-tag`").
**That warning is a FALSE POSITIVE on this repo.** Verified in source at HEAD `e9d7068`:
`scripts/publish.py:1685` builds `resolver_tag = f"{get_plugin_name(root)}--v{new_ver}"`,
`:1757` pushes it with `git push --atomic origin HEAD {tag} {resolver_tag}`, and `:302-312`
fail-fast rather than guess the plugin name. Both tags ship, atomically. I had recorded it
here as a real defect on CPV's word alone before reading the code — the correction is [^2].
Hypothesis for why CPV misses it, NOT verified: the tag is built by f-string interpolation,
so a literal scan for `<plugin-name>--v` finds nothing.

### 2026-08-12 — NEXT ACTION discharged, and a natural experiment that closes the card

Surfaced by the `[trdd-state-reconciliation]` detector as a partially-shipped-review drift
candidate. Re-derived rather than assumed, per the NEXT ACTION above.

**1. The last named component is resolved.** `skills/maintainer-worktree/SKILL.md` is no
longer on the `RC-TEST-COVERAGE` line. Confirmed from the contract's own parametrization
rather than the warning, as the NEXT ACTION required — `pytest --collect-only` yields 4
cases for it (`frontmatter_valid`, `no_tool_grant_frontmatter`, `has_core_body_sections`,
`referenced_files_resolve`), because v1.13.6 derives the scope by glob.

**2. The metric got WORSE as coverage got better — and the cause is a single commit.**
CPV v5.3.0 `--strict` now reports **29 of 64** untested, up from 16 of 64 on 2026-08-11,
while the suite grew 47 → 58 files. Of the 13 skills VISIBLE on that line (it truncates at
"+9 more", so 9 names are unseen and this is a sample, not a census), **13 of 13** are
exactly the skills whose literal name was deleted by `d98ebab` — the commit that replaced
the hand-maintained `AUDIT_UNCOVERED_SKILLS` list with `SKILLS_ROOT.glob("*/SKILL.md")`.

That is a natural experiment, and stronger evidence than the correlational separation
recorded on 2026-08-11. One commit, in one direction: coverage strictly improved (8
previously-uncovered skills gained tests, incl. `maintainer-worktree`), and the metric fell
by 13 — because the hand-maintained list of literal names was, incidentally, the corpus the
metric was scanning. **The metric was reading the list, not the coverage.**

**3. A trap I walked into while measuring it, worth more than the measurement.** My first
overlap check grepped the WHOLE CPV report for `skills/*/SKILL.md` and concluded
`maintainer-worktree` was still flagged. It was not: that name appears in an unrelated
time-sensitive-info warning, and the coverage line never mentions it. The corrected check
greps the `RC-TEST-COVERAGE` LINE only. Two of my own standing rules failed together here —
"never measure from a truncated tool result" (the line ends in "+9 more") and "grep is not
semantic" (the same string means different things in different warnings). Recorded as [^3].

**Conclusion: the work of this card is DONE and the residual warning is an artifact.**
Every shipped surface is under a derived-scope contract; the one genuine hole this card ever
found was invisible to the metric and was closed. Pursuing the original pass criterion would
now mean re-adding a literal-name list — reverting the fix — so the criterion was revised
rather than chased. Card closed; the metric defect is upstream at `CPV#207`.

## Why

CPV `--strict` (v2.158.0) reports `RC-TEST-COVERAGE`:

> 23 of 56 testable component(s) have no discoverable test (the plugin ships a suite of 41
> test file(s), so its coverage looks thin)

Advisory and non-blocking — but it is a **real** gap, and it is the plugin's own rule that
every skill, command, hook and runtime behaviour ships a test. "The publisher only *runs*
the tests; writing them is the plugin's job" is a rule this plugin enforces on others.

Named by CPV (the list is authoritative, re-derive it rather than trusting this copy):

- `scripts/cpv_network_resilience.py`, `scripts/setup_marketplace_pat.py`
- skills: `maintainer-prrd-trdd-kanban`, `maintainer-redact`, `maintainer-sandbox`,
  `maintainer-secrets-scan`, `the-skills-menu`
- **almost all of `commands/`** (14+): `maintainer-bootstrap-ci`, `maintainer-commit-msg-hook`,
  `maintainer-fix-safe`, `maintainer-guardian-baseline`, `maintainer-guardian-scan`,
  `maintainer-pin-actions`, `maintainer-protect-branch`, `maintainer-redact-text`,
  `maintainer-review-pr`, `maintainer-sandbox-precheck`, `maintainer-sandbox-preflight`,
  `maintainer-scan-workflows`, `maintainer-secrets-scan`, … (+3)

Note the shape of it: several of these *names* have tests (`test_redact.py`,
`test_sandbox.py`, `test_guardian.py`) — what is missing is a test for the **command**
surface that invokes them. A command is a contract with the user; an untested command can
drift from the skill it wraps and nobody finds out.

## What "a test" means here — and what it must not be

The lesson from `TRDD-A6NY2TJU` applies directly, so state it before any test gets written:
**a test that cannot fail is worse than no test — it reports a safety it never checked.**

So, per component, prove the thing that would actually break:

- the command's front-matter is valid and its name matches its file
- the skill/script it delegates to **exists** (a renamed skill silently orphans its command —
  this is exactly the class of bug that is invisible until a user types the command)
- any shell recipe it embeds is syntactically valid and, where feasible, is *executed*
  against a real fixture rather than pattern-matched
- the documented flags/args are the ones the underlying script accepts

`tests/test_protect_branch_contexts.py` is the reference shape: it **extracts the real
recipe from the shipped doc and runs it**, so an edit to the markdown is executed rather
than a copy of it. Doc-embedded scripts can only be gated that way.

## Approach

Batch by surface, one release per batch — not 23 tests in one commit:

1. `commands/` → a table-driven contract test (front-matter, target-exists, flags) covering
   all 14+ at once; then per-command execution tests where a real fixture is cheap.
2. The 2 `scripts/` (`cpv_network_resilience`, `setup_marketplace_pat`).
3. The 5 skills, reusing the extract-and-run shape.

Re-derive the list from CPV at the time of work — it moves.

## Pass criteria

**REVISED 2026-08-12 (the original is below, struck for the record).** Every shipped
component is covered by a test whose SCOPE IS DERIVED FROM THE FILESYSTEM, and every new
test fails when its subject is broken (verify by breaking it, once, deliberately).

~~`RC-TEST-COVERAGE` no longer fires under CPV `--strict`~~ — **retired as a criterion, and
not merely because it is unreachable: it is anti-correlated with the goal.** Measured
2026-08-12 (see the last dated section): replacing the hand-maintained 24-name skill list
with a filesystem glob closed the only genuine coverage hole in the repo *and moved this
warning 13 components in the WRONG direction*, because the list was the thing the metric
was reading. Satisfying the old criterion now requires re-adding a hand-maintained list of
literal names — i.e. reverting the fix. A criterion that can only be met by undoing the
work is not a criterion.

## Approval log

- 2026-08-12T19:52:00+0200 — CLOSED as `published` by ai-maestro-maintainer-agent. The work
  shipped in **v1.13.6** (`d98ebab` — derived-scope skill contract, closing the 8-skill hole)
  and **v1.13.7** (`eedc3e8` — CLI contract; `7974049` — sandbox orphan reap), both already
  released and published; this transition RECORDS those releases, it does not perform a new
  one. Closed against the **revised** pass criterion (see `## Pass criteria`), not the
  original — the original is anti-correlated with the goal and could now only be met by
  reverting `d98ebab`. Residual `RC-TEST-COVERAGE` noise is an upstream metric defect
  (`CPV#207`), evidenced by the natural experiment in the 2026-08-12 section. **Reopen if
  the revised criterion is not accepted** — that judgment is the one thing here I made
  rather than measured.

## Notes and lessons learned

[^1]: [ocd:2026-07-14 lmd:2026-07-14] This gap surfaced only because CPV's advisory warning
  was *read* rather than skimmed past as non-blocking. Two of the three defects fixed in
  `TRDD-A6NY2TJU` were likewise invisible to every green check — the cspell gate was armed
  and pointed at nothing, and the branch ruleset sealed the repo while showing all-green.
  Lesson: the findings that matter most are the ones nothing is failing on. A non-blocking
  warning is not a lesser finding, it is an unexamined one.

[^2]: [ocd:2026-08-01 lmd:2026-08-01] DO NOT record a scanner's WARNING into a TRDD (or
  report it to the user) as an established defect before reading the code it accuses,
  BECAUSE the warning is the tool's claim and the source is the evidence — I wrote
  `RC-DEP-TAG-PIPELINE` into this card as a real bug needing its own TRDD, and
  `publish.py:1685/1757` had been pushing the resolver tag atomically the whole time.
  DO open the accused file first; one grep would have cost less than the card.
  Note the trap is the exact mirror of `[^1]`: that lesson says a non-blocking warning
  is an *unexamined* finding, and the fix for unexamined is to EXAMINE it — not to
  promote it. Both failure modes are cheap to avoid and expensive to ship.

[^3]: [ocd:2026-08-12 lmd:2026-08-12] DO NOT compute a set-overlap by grepping a whole
  multi-warning scanner report for a path pattern, BECAUSE the same path appears under
  DIFFERENT warnings and the answer silently becomes about the wrong question — I grepped
  a CPV report for `skills/*/SKILL.md`, got `maintainer-worktree`, and concluded it was
  still flagged as untested when its only appearance was in a time-sensitive-info warning.
  DO extract the ONE finding's line first, then match within it. Two standing rules failed
  together and neither would have caught it alone: the line also ends in "+9 more", so even
  the corrected sample is 13 of 22 — say "sample", never "census", when the source
  truncates. The tell was that the conclusion *changed* between the two greps; a number
  that moves when you narrow the scope is a number you have not measured yet.
