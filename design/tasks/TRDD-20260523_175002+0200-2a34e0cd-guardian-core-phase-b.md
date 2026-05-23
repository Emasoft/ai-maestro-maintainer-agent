---
trdd-id: 2a34e0cd-01fa-4241-80d8-8ab37105b17c
title: Guardian Mode core — proactive supply-chain sentinel with 5 threat classes (Phase B)
status: completed
created: 2026-05-23T17:50:02+0200
updated: 2026-05-23T17:50:02+0200
---

## TRDD-2a34e0cd — Guardian Mode core — proactive supply-chain sentinel with 5 threat classes (Phase B)

**Filename:** `design/tasks/TRDD-20260523_175002+0200-2a34e0cd-guardian-core-phase-b.md`
**Tracked in:** this repo (design/tasks/ is git-tracked)

## Implementing commit

- 193b361 — `feat(security): Guardian core — proactive supply-chain sentinel (Phase B)`

## User request (verbatim, reconstructed from commit body)

> Builds the proactive half of the maintainer's mandate. The agent is
> no longer a reactive issue-fixer; it watches every patrol cycle for
> five threat classes, auto-fixes the safe ones, files tracking issues
> for the rest, and refuses to commit changes that touch security-
> sensitive paths without explicit maintainer approval.

The trigger was the supply-chain audit (see sibling TRDD-c0734bde):
the article surfaced gap GAP-3, adversarial issue content, that
cannot be closed mechanically. Phase B authors the new skills and
hook infrastructure required to detect supply-chain drift and gate
maintainer-on-behalf-of-issue commits. Phase C (sibling
TRDD-2700e67d) wires these skills into the existing maintainer chain.

## Scope — three new pieces of infrastructure

### B1. maintainer-guardian (NEW skill)

A skill with **two modes** controlled by an argument:

- **BASELINE mode** — invoked once per session by the SessionStart
  hook. Reads the current state of all five threat classes and
  writes a snapshot to `~/.aimaestro/maintainer/<id>/guardian-baseline.json`.
  Subsequent SCAN calls diff against this baseline.
- **SCAN mode** — invoked at every patrol pre-cycle. Re-reads the
  five threat classes, computes the delta vs baseline, and routes
  each delta to one of three dispositions:
  - `auto-fix-PR` — the delta is mechanical and safe (e.g. a SHA pin
    drifted from upstream's published SHA → re-pin).
  - `file-issue` — the delta needs human attention but is not
    immediately exploitable (e.g. branch-rule weakened).
  - `alert-authorized-user` — the delta is a secret-leak or
    actively-exploited drift; halt the cycle and ping the
    authorized user immediately.

#### The five threat classes (T1–T5)

Documented in full at `skills/maintainer-guardian/references/threat-classes.md`:

| Class | Detects                                                             | Default disposition  |
|-------|---------------------------------------------------------------------|----------------------|
| T1    | `zizmor`/`actionlint` finding count drifted upward since baseline   | file-issue           |
| T2    | A pinned action SHA has been rewritten upstream (tj-actions class)  | auto-fix-PR          |
| T3    | A protected branch lost a required check or required-reviewer rule  | file-issue           |
| T4    | A protected-path file was modified outside the approval-gate flow   | alert-authorized-user|
| T5    | Secret-leak markers appeared in repo (committed token, .env, etc.)  | alert-authorized-user|

### B2. maintainer-approval-gate (NEW skill)

The agent-layer analogue of the article's "build/publish separation":
a trusted decision (maintainer says OK) is separated from an
untrusted spec (issue body). Also two modes:

- **CHECK mode** — inspects the planned diff against the canonical
  protected-paths list (plus per-repo `.aimaestro/protected-paths.txt`
  additive override). If any protected path is touched, posts an
  approval-request comment on the originating issue, labels it
  `awaiting-maintainer-approval`, halts the caller, returns
  disposition `needs-approval`.
- **VERIFY mode** — searches the issue for an `approve-protected-edit`
  comment by `$AUTHORIZED_USER` (the `gh`-authenticated MAESTRO user,
  NOT the issue author). Returns `ok` / `pending` / `rejected`.

#### Canonical protected paths

`.github/workflows/`, `.github/dependabot.yml`,
`.github/CODEOWNERS`, `scripts/publish.py`, `.gitignore`, `.npmrc`,
`LICENSE`, `SECURITY.md`, `.claude-plugin/` (plugin repos). Per-repo
files can ADD paths but cannot remove them.

#### Approval-comment grammar

Exact phrases — `approve-protected-edit` and `reject-protected-edit`.
Deliberately chosen to defeat the article's `jq --arg` trap class:
the phrase is a literal that does NOT contain shell expansion
characters, so a malicious commenter can't smuggle an approval by
posting `${approve-protected-edit}` or similar.

### B3. SessionStart hook (NEW)

`hooks/hooks.json` registers a SessionStart hook (fires on `startup`,
`resume`, `compact`) that reminds the agent to invoke
maintainer-guardian BASELINE before the first patrol cycle of the
session. The reminder is idempotent — if a baseline already exists
for the current session id, the hook is a no-op.

## Design decisions

1. **Two modes, one skill, for both Guardian and Approval-Gate.**
   Splitting BASELINE / SCAN or CHECK / VERIFY into separate skills
   would have doubled the skill count and forced the orchestrator
   to remember which-comes-before-which. One skill with a `mode`
   argument keeps the discovery surface tight.
2. **Threat classes are data, not code.** The five-class taxonomy
   lives in `references/threat-classes.md` as prose + a routing
   table. Adding T6 is a documentation edit, not a code change.
3. **Approval-comment grammar is a literal, not a regex.** Exact
   string match for `approve-protected-edit`. No fuzzy match. The
   maintainer types the phrase literally; nothing else passes.
4. **Per-repo override is additive only.** Per-repo
   `.aimaestro/protected-paths.txt` can ADD paths to the canonical
   list but cannot REMOVE them. This prevents a compromised repo
   from neutralising the guard.
5. **The SessionStart hook is a backstop, not a primary trigger.**
   Phase C wires patrol Step 2 to also invoke BASELINE on first
   cycle if no baseline exists. The hook handles the case where
   patrol is invoked from a fresh session before the user runs the
   patrol command — the baseline is ready by the time patrol Step 4
   runs SCAN.
6. **Baseline file location at this point: `~/.aimaestro/maintainer/<id>/`.**
   This was the choice at Phase B. Phase D (sibling TRDD-49d054cc)
   reverses it — see that TRDD for the rationale.

## Files touched (commit 193b361)

```
hooks/hooks.json                                                    (MOD, +SessionStart)
skills/maintainer-approval-gate/SKILL.md                            (NEW)
skills/maintainer-approval-gate/references/protected-paths.md       (NEW, 190 LOC)
skills/maintainer-guardian/SKILL.md                                 (NEW)
skills/maintainer-guardian/references/threat-classes.md             (NEW, 203 LOC)
```

## Acceptance criteria (all met by 193b361)

- [x] maintainer-guardian skill exists with both BASELINE and SCAN
      modes documented.
- [x] threat-classes.md enumerates exactly five threat classes
      T1–T5 with detection rules and default dispositions.
- [x] maintainer-approval-gate skill exists with CHECK and VERIFY
      modes.
- [x] protected-paths.md lists the canonical paths and documents
      the additive-only per-repo override.
- [x] hooks/hooks.json registers a SessionStart hook that reminds
      the agent about BASELINE.
- [x] Approval-comment grammar is exact-string-match only.

## Post-mortem

**What worked:**
- The two-mode skill pattern (BASELINE/SCAN, CHECK/VERIFY) feels
  natural in practice — calling code asks for the mode it needs and
  doesn't have to chain skills.
- Documenting threat classes as a data table in `references/`
  instead of code paths in the skill means the next threat class
  added (e.g. T6 for prompt-injection markers in PRs) is a doc edit.
- The SessionStart hook + Phase C patrol-Step-2 backstop is
  redundant in a good way — either path produces a baseline, but
  neither path REQUIRES the other.

**What was tricky:**
- The approval-comment grammar took an iteration. Initially it was
  a regex with optional whitespace and case-insensitive matching;
  this was attack-surface — a malicious commenter could potentially
  smuggle the phrase via fuzzy match. Tightening to literal exact
  match (case-sensitive, no whitespace flexibility) closed it.
- Deciding which dispositions correspond to which threat classes
  was a real judgment call. T2 (SHA drift) is auto-fix because the
  remediation is unambiguous and reversible (re-pin). T1 (zizmor
  drift) is file-issue because zizmor's findings need triage.
  T4/T5 are alert because they may indicate active compromise.
- Choosing `~/.aimaestro/maintainer/<id>/` for the baseline file
  was the right call locally but the WRONG call from AI Maestro's
  perspective — see TRDD-49d054cc Phase D for the rollback.

**Lessons for future work:**
- The hook surface (`hooks.json`) is the right place for
  "remind-the-agent" prompts that don't require deterministic
  execution. The orchestrator may skip them, which is OK because
  the backstop in patrol Step 2 will catch the omission.
- Reserving "alert-authorized-user" for active-compromise classes
  (T4/T5) and "file-issue" for drift classes (T1/T3) keeps the
  signal-to-noise on the maintainer's inbox clean.
