# TRDDs (Task Requirement Design Documents)

TRDDs document **what we intend to build** — specifications,
acceptance criteria, file lists, test plans. They survive session
compaction and branch switches because they live in git.

Companion class: ADRs under `../adrs/` document **why** a particular
technical approach was chosen. A PR may add a TRDD, an ADR, both, or
neither — depending on whether the work is non-trivial (TRDD) and
whether it commits to a non-obvious technical choice (ADR).

## When to author a TRDD

- The work touches > 3 files OR > 200 lines.
- The work is deferred to a future session (not done in the current
  one).
- The work introduces a new public API or skill.
- The work requires multiple commits to land safely.

For trivial changes (one-file fix, < 50 lines), skip the TRDD and
use a conventional commit message instead.

## Filename

```
TRDD-<YYYYMMDD_HHMMSS+ZHHMM>-<uid-first-8>-<short-slug>.md
```

Three components separated by `-`:

- `<YYYYMMDD_HHMMSS+ZHHMM>` — local datetime + GMT offset (compact
  form, no colon in the offset). Generate via
  `date +%Y%m%d_%H%M%S%z`.
- `<uid-first-8>` — first 8 hex chars of an RFC 4122 UUID. Generate
  via `python3 -c "import uuid; print(uuid.uuid4())"`.
- `<short-slug>` — kebab-case summary (2-4 words).

## Frontmatter (mandatory — v2 `column:` schema)

```yaml
---
trdd-id: <full UUID>
title: <single line, no colon, ≤ 80 chars>
column: backburner
created: <ISO 8601 datetime with TZ offset>
updated: <same shape>
---
```

State is the single `column:` field (the v2 kanban schema). There is **no v1
`status:` field**.

## Column enum (the v2 kanban pipeline + exceptions — 3-pillars 3.0.0, 22 board columns)

Lifecycle order: `backburner → approval → design → design_ai_review →
(design_human_review) → todo → verify_assumptions → plan → dispatch → dev →
testing → ai_review → (human_review) → complete`, then tool TRDDs
`→ publish → published` and service TRDDs `→ deploy → live → (live_auditing)`.

| Group | Columns | Terminal? |
|---|---|---|
| Intake | `backburner` (not yet approved), `approval` (awaiting its `min-approval-requirement:` authority), `live_auditing` (entry) | no |
| Design | `design`, `design_ai_review`, `design_human_review` (skipped at floor `none`) | no |
| Gates + queue | `todo`, `verify_assumptions` (no unverified claims), `plan` (complete plan file exists), `dispatch` | no |
| Work | `dev`, `testing`, `ai_review`, `human_review` (resting — waits on the USER) | no |
| Ready | `complete` | no (internal-done) |
| Ship | `publish` → `published` / `deploy` → `live` | `published`/`live` terminal |
| Exceptions | `blocked` 🔴 (add `blocked-by: [...]`), `failed` (retryable), `superseded` (add `superseded-by: [...]`) | only `superseded` terminal |

The five bracket states (`proposal`, `planned`, `refused`, `completed`,
`cancelled`) are legal `column:` values OUTSIDE the board — board 22, legal set
27 (3P-KAN-20). Pre-3.0.0 cards in `todo`/`design`/`backburner` are
grandfathered (3P-KAN-21): per-card judgment on next touch, never a sweep.

**Approval overlay (location = authorization):** `design/proposals/`
(`column: proposal`, awaiting approval) → `design/tasks/` (`column: planned`,
authorized) → terminal-DONE TRDDs `git mv` to `design/archived/`
(`completed`/`cancelled`/`superseded`); refused proposals `git mv` to
`design/refused/` (`column: refused`). Tier-0 work authors directly in
`design/tasks/` as `planned`. Full model:
`~/.claude/rules/trdd-approval-tiers.md`.

## Body sections

Context · Scope · Implementation order · Critical files · Reused
utilities · Verification · Out of scope.

## Tooling

The `maintainer-trdd-adr` skill (from the ai-maestro-maintainer-agent
plugin) scaffolds and validates TRDDs. See its `SKILL.md` for the
canonical commands.

## Reference

- Full authoring rule: `~/.claude/rules/trdd-design-tasks.md`
- This repo's ADRs: `../adrs/`
