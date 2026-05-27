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

## Frontmatter (mandatory)

```yaml
---
trdd-id: <full UUID>
title: <single line, no colon, ≤ 80 chars>
status: not-started
created: <ISO 8601 datetime with TZ offset>
updated: <same shape>
---
```

## Status enum

| Value | Meaning | Terminal? |
|---|---|---|
| `not-started` | Authored; no implementation yet | no |
| `in-progress` | At least one commit references this TRDD | no |
| `completed` | Acceptance criteria met | yes |
| `failed` | Attempted and abandoned (do not retry without reading the post-mortem) | yes |
| `blocked` | Waiting on another TRDD (must add `blocked-by: [TRDD-<uid>]` list) | no |
| `superseded` | Replaced by a newer TRDD (must add `superseded-by: [TRDD-<uid>]` list) | yes |

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
