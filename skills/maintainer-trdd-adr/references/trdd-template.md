# TRDD template (canonical — v2 `column:` schema)

## Table of Contents

- [Frontmatter rules](#frontmatter-rules-mandatory-per-claude-rules-trdd-design-tasks-md)
- [Column enum + approval overlay](#column-enum--approval-overlay)
- [Body sections](#body-sections)
- [Template](#template)

The template below is what `new-trdd` mode writes after
substituting `$UID` (full UUID), `$SHORT` (first 8 chars),
`$ISO` (full ISO 8601 datetime with TZ offset), and `$SLUG`
(short kebab-case summary).

The substituted file goes to:
`design/tasks/TRDD-<TS>-<SHORT>-<SLUG>.md` (a Tier-0 / already-authorized
TRDD), or `design/proposals/TRDD-<TS>-<SHORT>-<SLUG>.md` (a TRDD that needs
approval before it may run — see the approval overlay below).

Where `<TS>` is the compact `%Y%m%d_%H%M%S%z` form (no `:` in the
offset — Windows filesystem-safe).

## Frontmatter rules (mandatory per ~/.claude/rules/trdd-design-tasks.md)

- `trdd-id:` — full RFC 4122 UUID, matches the filename's `<SHORT>` prefix.
- `title:` — single line, no colons, ≤ 80 chars. Use `—` or `-` for sub-clauses.
- `column:` — bare kebab-case v2 kanban state (see the enum below). **There is
  no v1 `status:` field** — the `column:` field is the single source of state.
- `created:` — ISO 8601 datetime with TZ offset (e.g. `2026-05-27T14:00:00+0200`).
- `updated:` — same shape; bump on every edit.
- `blocked-by:` — required iff `column: blocked`. Flow-style list: `[TRDD-<uid-1>, TRDD-<uid-2>]`.
- `superseded-by:` — required iff `column: superseded`. Flow-style list.

Optional v2 fields, added when their value is known (absent = documented
default): `current-owner:`, `assignee:`, `priority:`, `task-type:`
(`feature`|`bugfix`|`refactor`|`docs`|`infra`|`security`|`artifact`|`spike`|`audit`),
`release-via:` (`publish`|`deploy`|`none`, default `none`),
`test-requirements:`, `relevant-rules:` (PRRD rule numbers), `npt:`/`eht:`
(prerequisite / effect-handling child TRDDs), `approval-tier:` (the tier the
TRDD needs — see overlay).

## Column enum + approval overlay

`column:` moves through the v2 pipeline (lifecycle order):

`backburner → todo → design → dispatch → dev → testing → ai_review →
(human_review) → complete` — then for tool TRDDs `→ publish → published`, for
service TRDDs `→ deploy → live → (live_auditing)`. Exceptions, orthogonal to
the pipeline: `blocked` (🔴 `blocked-by:` non-empty; restores to
`pre-block-column:` when cleared), `failed` (retryable — stays in
`design/tasks/`), `superseded` (terminal).

**Approval overlay (location = authorization).** A TRDD that needs approval is
authored in `design/proposals/` with `column: proposal`; on approval the
approver sets `column: planned` and `git mv`s it into `design/tasks/`; on
refusal it becomes `column: refused` in `design/refused/`. Terminal-DONE TRDDs
(`completed`/`cancelled`/`superseded`) are `git mv`-ed to `design/archived/`.
A **Tier-0** TRDD (the agent's own in-scope DERIVED NPT/EHT work, or applying
the ratified baseline as-is) skips the proposal stage — author it directly in
`design/tasks/` as `column: planned`. The MAINTAINER is a governance-layer peer
and files Tier-2 proposals DIRECTLY to MANAGER (no CHIEF-OF-STAFF hop) — see
`~/.claude/rules/trdd-approval-tiers.md`.

## Body sections

1. **Context** — what's the problem? Why does this matter now?
2. **Scope** — what does this TRDD cover (and explicitly NOT cover)?
3. **Implementation order** — phased file list. ≤ 5 files per phase per CLAUDE.md.
4. **Critical files** — paths only; what changes, why.
5. **Reused utilities + existing patterns** — what existing code patterns are mirrored.
6. **Verification** — how do we know the TRDD landed correctly? Concrete commands.
7. **Out of scope (deferred)** — what we deliberately punted.

## Template

```markdown
---
trdd-id: ${UID}
title: <single line, no colon, ≤ 80 chars>
column: backburner
created: ${ISO}
updated: ${ISO}
current-owner: ai-maestro-maintainer-agent
task-type: <feature|bugfix|refactor|docs|infra|security|audit>
release-via: none
relevant-rules: []
---

# TRDD-${SHORT} — <human-readable title>

**Filename:** \`design/tasks/TRDD-<TS>-${SHORT}-${SLUG}.md\`
**Tracked in:** this repo (design/tasks/ is git-tracked)

## Context

<What is the problem? Why does this matter now? Include the user's
original request verbatim if there is one, plus the surrounding
constraints / motivations.>

## Scope

<What does this TRDD cover? List the domains touched and explicitly
exclude what is NOT in scope.>

## Implementation order

### Phase A (mechanical, low-risk first)

- File 1: <path> — <what changes>
- File 2: <path> — <what changes>

### Phase B (core change)

- File 3: <path> — <what changes>

…etc.

## Critical files

- \`<path>\` — <what + why>
- \`<path>\` — <what + why>

## Reused utilities + existing patterns

- <Pattern 1> — mirrored from <existing file>
- <Pattern 2> — same as <existing skill>

## Verification

\`\`\`bash
# Concrete commands a reviewer can run to verify the TRDD landed.
<command 1>
<command 2>
\`\`\`

## Out of scope (deferred)

- <Thing 1> — why deferred
- <Thing 2> — why deferred
```

## Notes on grep-friendliness

The frontmatter is engineered so every important field can be
grep'd in one line:

- `grep -H "^column:" design/tasks/*.md` returns every TRDD's column.
- `grep -l "^column: dev$" design/tasks/*.md` lists all in-development TRDDs.
- `grep -lE "^column: (dev|testing|ai_review|human_review)$" design/tasks/*.md` lists the whole WORK group.
- `grep -H "^updated:" design/tasks/*.md | sort -t: -k2 | tail -5` returns the 5 most recently-touched TRDDs chronologically.
- `grep -H "^blocked-by:" design/tasks/*.md` returns every blocked TRDD with its full blocker list on one line (flow-style lists, never block-style).

Do not break these invariants when filling the template:

- One field per line.
- Lists are flow-style (`[a, b, c]`) — never block-style.
- Enum values are bare kebab-case — never quoted.
- Titles never contain colons.
- Dates are full ISO 8601 datetimes with TZ offset.
