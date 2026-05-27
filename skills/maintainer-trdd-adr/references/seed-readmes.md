# Seed README content for bootstrap mode

## Table of Contents

- [design/tasks/README.md](#designtasksreadmemd)
- [design/adrs/README.md](#designadrsreadmemd)

The bootstrap mode drops two README files under the entrusted
repo's `design/` directory. Both READMEs are short, self-contained
explanations of how to use TRDDs and ADRs in THAT repo — the
contributor doesn't need access to the canonical rule file
(`~/.claude/rules/trdd-design-tasks.md`) to author a valid TRDD.

The bootstrap mode also drops `ADR-0001-introduce-trdd-adr-split.md`
which documents *why* this repo uses both artifact classes. The
content of that ADR comes from `adr-template.md` substituted with
boilerplate values; the maintainer reviews and tweaks before
committing.

## design/tasks/README.md

```markdown
# TRDDs (Task Requirement Design Documents)

TRDDs document what we intend to build — specifications,
acceptance criteria, file lists, test plans. They survive session
compaction and branch switches because they live in git.

## When to author a TRDD

- The work touches > 3 files OR > 200 lines.
- The work is deferred to a future session (not done in the
  current one).
- The work introduces a new public API or skill.
- The work requires multiple commits to land safely.

For trivial changes (one-file fix, < 50 lines), skip the TRDD
and use a conventional commit message instead.

## Filename

`TRDD-<YYYYMMDD_HHMMSS+ZHHMM>-<uid-first-8>-<short-slug>.md`

Three components separated by `-`:
- `<YYYYMMDD_HHMMSS+ZHHMM>` — local datetime + GMT offset
  (compact form, no `:` in the offset). Generate via
  `date +%Y%m%d_%H%M%S%z`.
- `<uid-first-8>` — first 8 hex chars of an RFC 4122 UUID.
  Generate via `python3 -c "import uuid; print(uuid.uuid4())"`.
- `<short-slug>` — kebab-case summary (2-4 words).

## Frontmatter (mandatory)

\`\`\`yaml
---
trdd-id: <full UUID>
title: <single line, no colon, ≤ 80 chars>
status: not-started
created: <ISO 8601 datetime with TZ offset>
updated: <same shape>
---
\`\`\`

## Status enum

| Value | Meaning |
|---|---|
| not-started | Authored; no implementation yet |
| in-progress | At least one commit references this TRDD |
| completed | Acceptance criteria met |
| failed | Attempted and abandoned (do NOT retry without reading the post-mortem) |
| blocked | Waiting on another TRDD (must add `blocked-by: [TRDD-<uid>]` list) |
| superseded | Replaced by a newer TRDD (must add `superseded-by: [TRDD-<uid>]` list) |

## Body sections

Context · Scope · Implementation order · Critical files · Reused
utilities · Verification · Out of scope.

## Tooling

The `maintainer-trdd-adr` skill (from the ai-maestro-maintainer-agent
plugin) scaffolds and validates TRDDs. See its SKILL.md for the
canonical commands.
```

## design/adrs/README.md

```markdown
# Architecture Decision Records (ADRs)

ADRs document why we chose a particular technical approach. They
complement TRDDs (which document what to build) and the git
history (which documents what was actually done).

## When to author an ADR

- The PR commits to a non-obvious technical choice (e.g. "use
  sqlite3, not LMDB").
- A future reader would ask "why didn't we do the obvious thing
  here?"
- The decision overturns a prior decision (then the ADR has
  `Status: supersedes ADR-NNNN`).

For obvious decisions (matching existing patterns), skip the ADR.

## Format (Michael Nygard)

\`\`\`markdown
# ADR-NNNN — <Short title>

Status: <proposed | accepted | rejected | superseded by ADR-MMMM>
Date: <ISO 8601 date>
Authors: <names>

## Context
…
## Decision
…
## Consequences

### Easier
- …
### More difficult
- …
### Neutral
- …
\`\`\`

## Conventions

- Filename: `ADR-NNNN-<short-slug>.md`. NNNN is zero-padded to 4
  digits, monotonically increasing.
- Numbering: assign the next NNNN at PR time, not at draft time
  (avoids collisions in parallel branches).
- Once `Status: accepted`, the ADR body is FROZEN. To change a
  decision, author a new ADR.
- One decision per ADR.

## Reference

- [Documenting Architecture Decisions — Michael Nygard, 2011](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)

## Index

| ADR | Title | Status |
|---|---|---|
| 0001 | Introduce TRDD/ADR split | accepted |

(Append a row for every new ADR.)
```

## ADR-0001-introduce-trdd-adr-split.md (boilerplate for bootstrap mode)

The bootstrap mode authors the first ADR with this content,
substituting `$AUTHOR` and `$ISO`:

```markdown
# ADR-0001 — Introduce TRDD/ADR split

Status: accepted
Date: <substituted ISO 8601 date>
Authors: <substituted from git config user.name>

## Context

This repo accumulates two kinds of long-lived design artifacts:

1. **Specifications of work to be done** — implementation plans,
   acceptance criteria, file lists.
2. **Decisions of how to solve a problem** — why we chose approach
   X over approach Y; what trade-offs we accepted.

Conflating both in a single file class produces docs that are
either too dense (decisions buried in spec text) or too thin
(specs that don't justify their non-obvious choices).

## Decision

We adopt both artifact classes in parallel under `design/`:

- `design/tasks/TRDD-<...>.md` — task / specification documents.
- `design/adrs/ADR-NNNN-<...>.md` — decision records.

A PR may add a TRDD, an ADR, both, or neither — depending on
whether the work is non-trivial (TRDD) and whether it commits to
a non-obvious technical choice (ADR).

## Consequences

### Easier

- A reader looking for "why is X this way" goes to `design/adrs/`
  and finds focused decision records.
- ADRs are easy to grep — one file per decision, monotonic
  numbering.
- The format is familiar — any reader who has seen ADRs elsewhere
  understands it immediately.

### More difficult

- Two artifact classes means contributors must learn which to use
  when. The READMEs in both directories explain the rule.
- A naïve search might land only on the TRDD or only on the ADR.
  Cross-reference in both bodies to mitigate.

### Neutral

- Some decisions fit in a commit body without an ADR. Use the
  rule: if a future reader would ask "why didn't we do the
  obvious thing", author an ADR.

## References

- TRDD authoring rule (user-scope): `~/.claude/rules/trdd-design-tasks.md`
- Michael Nygard, "Documenting Architecture Decisions" (2011):
  <https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions>
```
