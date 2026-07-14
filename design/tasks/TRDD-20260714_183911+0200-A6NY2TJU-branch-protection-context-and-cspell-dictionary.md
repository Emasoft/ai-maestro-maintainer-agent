---
trdd-id: A6NY2TJU
title: Two latent defects that made every PR in this repo unmergeable — required-check context and the missing cspell dictionary
column: dev
created: 2026-07-14T18:39:11+0200
updated: 2026-07-14T18:39:11+0200
current-owner: ai-maestro-maintainer-agent
task-type: bugfix
release-via: publish
relevant-rules: [1]
---

# Two latent defects that made every PR in this repo unmergeable

## ⏵ STATE — READ THIS FIRST ON RESUME (authoritative; supersedes the body) — 2026-07-14

**Where it stands:** both defects FIXED. The cspell half shipped in **v1.7.11**. The
branch-protection half is committed locally and NOT yet released.

| Component | State |
|---|---|
| `.cspell.json` + `.cspell-project-words.txt` | SHIPPED v1.7.11 — 554 unknown words → 0 |
| Live `baseline-pr-and-checks` ruleset (id `17471105`) | FIXED via API — context `validate` → `Validate`; readback verified |
| `skills/workflow-protect-branch/references/instructions.md` | FIXED — derives the job NAME, skips matrix jobs |
| `tests/test_protect_branch_contexts.py` | NEW — 6 tests, runs the REAL recipe extracted from the shipped doc |
| dependabot PRs #21 #22 #23 #25 | ALL MERGED (the first PRs ever to merge here) |

**NEXT ACTION:** release the branch-protection skill fix, then reply to ai-maestro **#27**
and **#29 Q2–Q7**.

## The bug that mattered: no PR in this repo could ever be merged

`baseline-pr-and-checks` required the status check `validate`. CI reports `Validate`.

GitHub names a check run after the job's **`name:`** when one is set, falling back to the
job **key** only when it is absent — and required-check contexts are matched
**case-sensitively**. So the required check `validate` waited on something that never
arrives. With `strict_required_status_checks_policy: true`, the branch was not merely
over-gated: it was **sealed**. Every PR showed all checks green and `mergeState=BLOCKED`
forever.

Four dependabot PRs had been rotting on that for weeks. Nothing was wrong with any of them.

### Root cause — the right method, the wrong field

`skills/workflow-protect-branch/references/instructions.md` derived contexts with:

```python
for job_id in (wf.get('jobs') or {}):
    checks.append({'context': job_id})
```

An earlier fix (recorded in memory as "workflow job-id extraction needs a YAML parser")
had correctly replaced a `grep` with `yaml.safe_load` — and then read the **wrong field**
out of the correctly-parsed tree. Fixing *how* you read a config says nothing about
*which key* is the right one. The parser change was necessary and not sufficient, and the
note celebrating it hid that.

### Why this is a CAPABILITY bug, not a local one

This skill is how the maintainer applies the ratified baseline to **every entrusted
downstream repo**. Shipped as-is, it would have sealed each of them the same way — a
silent, self-inflicted denial of service across the fleet, presenting as "all checks
green".

### The matrix trap, found while fixing it

A job with `strategy.matrix` reports one check run **per combination** — `Test matrix
(ubuntu-latest)` — never the bare name. Requiring the bare name never matches either, and
a guessed expansion breaks the moment the matrix comes from `fromJSON`, an expression, or
`include`/`exclude`. Since naming a context that never reports **deadlocks the branch**,
matrix jobs are now **skipped with a loud warning** rather than guessed at. A gate that is
slightly narrower than intended is recoverable; a branch nobody can merge into is not.

Verified against the live workflows: the fixed recipe emits exactly
`Lint, Commitlint, Validate, Test, workflow-security` — the five contexts GitHub actually
reports — and skips the matrix job. The old recipe emitted six, of which **one** could
ever report.

## The bug that hid it: cspell was armed with no dictionary

`SPELL_CSPELL` was enabled in `.mega-linter.yml:18` with **no cspell config in the repo**,
so it ran on stock dictionaries. 554 words of ordinary vocabulary — `zizmor`, `sarif`,
`pinact`, `wagoid`, `kubeconform`, `TRDD` — were "misspelled".

`VALIDATE_ALL_CODEBASE` is `false`, so MegaLinter lints only CHANGED files. A release's tip
commit is the version bump, touching `plugin.json` (excluded) and `CHANGELOG.md` — files
cspell skips. **`main` went green not because the repo was clean but because the gate was
handed nothing to check.** It fired the instant a PR touched a workflow.

Fixed with a real dictionary, not a suppression: `en-GB` alongside `en_US` (the prose here
is British — *behaviour*, *authorised*, *artefacts*: correct English was failing the
build); `ignoreRegExpList` for the mechanical noise a spell-checker must never gate on
(40-char action SHA pins — **dependabot rewrites those on every bump, so gating on them
guarantees a permanently red build**); and 353 words of genuine domain vocabulary in a
plain newline file.

Three of the 554 looked like real typos. **None were mine to fix**, and checking rather
than assuming is the only reason the fix is correct:

- `biuld` and `ubuntu-lastest` are **deliberate** misspellings — the sample broken
  workflows the `workflow-scan` skill teaches you to recognise. "Correcting" them would
  have destroyed the lesson. They carry an inline `cspell:ignore` **at their own site**,
  not a global dictionary entry, so a genuine `biuld` typo anywhere else still fails.
- `maintainance` sits in `TRDD-e1c2677a`, which is `column: complete` — **frozen by rule** —
  quoting the user verbatim.

That last one generalises: a spell finding inside a frozen document is **unfixable** and
would red the build forever. Hence `design/**` in `ignorePaths` — not muting a live
finding, but acknowledging that the TRDD corpus is immutable by design.

## Verification

- cspell: **0 issues across 257 files** (was 554 unknown words); 0 on the exact two
  workflows CI flagged.
- Tests: **574/574** (was 568; +6 for the context derivation).
- CPV `--strict` (exact CI command): `CRITICAL=0 MAJOR=0 MINOR=0 NIT=0`.
- Ruleset readback echoes `Validate` verbatim.
- All four dependabot PRs merged green.

## Notes and lessons learned

[^1]: [ocd:2026-07-14 lmd:2026-07-14] **A green `main` is not evidence of a working gate —
  it may be evidence of a gate with nothing to check.** cspell had been enabled and
  dictionary-less for months; `main` passed every time because `VALIDATE_ALL_CODEBASE:
  false` meant a release's tip commit handed it only files it skips. The gate was armed,
  pointed at nothing, and indistinguishable from a healthy one. Lesson: when a linter is
  enabled but has *never* failed, do not read that as passing — check what it actually
  examined. A gate's *coverage* is a separate question from its *result*, and only the
  result is visible.

[^2]: [ocd:2026-07-14 lmd:2026-07-14] **Fixing HOW you read a config does not mean you are
  reading the RIGHT KEY.** The prior fix here replaced a `grep` with a YAML parser and was
  written up as solved. It was still emitting the job KEY where GitHub wants the job NAME —
  correctly parsed, wrong field. The memory note recording that fix described the *method*
  and never stated the *contract* (what GitHub actually matches on), so it read as complete
  while the defect survived. Lesson: a fix is only finished when the note says what the
  external system EXPECTS, not merely how we now compute it.

[^3]: [ocd:2026-07-14 lmd:2026-07-14] **The failure mode of a wrong required-check context
  is a DEADLOCK, not a weakened gate** — and it presents as all-green. That asymmetry
  decides the design: when a context cannot be named with certainty (matrix jobs), the
  fail-safe is to OMIT it and warn, never to guess. Guessing wrong seals the branch;
  omitting merely narrows the gate, and a narrower gate is recoverable. Prefer the
  recoverable failure whenever the alternative is unrecoverable.

[^4]: [ocd:2026-07-14 lmd:2026-07-14] Four PRs sat unmergeable for weeks and nobody
  (including me) suspected the *ruleset* — the PR page said "all checks passed" next to a
  merge button that refused. Lesson: when CI is green and the merge is still refused, read
  the RULESET, not the checks. `gh api repos/OWNER/REPO/rulesets/<id>` and compare its
  required contexts **character-for-character** against `statusCheckRollup`. The two are
  matched case-sensitively and nothing in the UI shows you the mismatch.
