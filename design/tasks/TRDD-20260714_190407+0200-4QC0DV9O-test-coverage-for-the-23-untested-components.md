---
trdd-id: 4QC0DV9O
title: Ship a test for each of the 23 components that have none — almost all of commands/
column: backburner
created: 2026-07-14T19:04:07+0200
updated: 2026-08-01T02:17:20+0200
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

**SUPERSEDED — do NOT carry forward:** "23 of 56", "suite of 41 test files", and the
component list in `## Why` below. Re-derive, never cite them.

**Found while recounting, unrelated to this TRDD** — CPV also reports
`RC-DEP-TAG-PIPELINE`: `scripts/publish.py` tags `v{version}` but never
`ai-maestro-maintainer-agent--v{version}`, so any plugin that depends on this one installs
with `no-matching-tag` and is DISABLED. Advisory, invisible until someone installs clean.
Needs its own TRDD — it is not test coverage.

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

`RC-TEST-COVERAGE` no longer fires under CPV `--strict`, **and** every new test fails when
its subject is broken (verify by breaking it, once, deliberately).

## Notes and lessons learned

[^1]: [ocd:2026-07-14 lmd:2026-07-14] This gap surfaced only because CPV's advisory warning
  was *read* rather than skimmed past as non-blocking. Two of the three defects fixed in
  `TRDD-A6NY2TJU` were likewise invisible to every green check — the cspell gate was armed
  and pointed at nothing, and the branch ruleset sealed the repo while showing all-green.
  Lesson: the findings that matter most are the ones nothing is failing on. A non-blocking
  warning is not a lesser finding, it is an unexamined one.
