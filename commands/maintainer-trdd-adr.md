---
description: Bootstrap TRDDs + ADRs on a freshly-entrusted repo, scaffold new TRDDs and ADRs with valid frontmatter, or validate existing design docs.
argument-hint: "[bootstrap|new-trdd <slug>|new-adr <slug>|new-trdd-from-issue <pr-number> <repo> <slug>|validate]"
---

TRDDs document *what we intend to build*; ADRs document *why we
chose a particular technical approach*. Together they form the
durable design memory of a repo. This command sets up both
artifact classes on the maintained repo, scaffolds new entries
with valid frontmatter, and validates existing entries.

Loads skill: **maintainer-trdd-adr**

Modes:

- `bootstrap` — create `design/tasks/` + `design/adrs/`, seed both
  with READMEs explaining the conventions, author ADR-0001
  documenting the TRDD/ADR split. Refuses if either directory
  already exists.

- `new-trdd <slug>` — scaffold a new TRDD under
  `design/tasks/TRDD-<TS>-<uid-first-8>-<slug>.md` with the
  canonical frontmatter (UUID + ISO 8601 dates + `status:
  not-started`). Prints the filepath.

- `new-adr <slug>` — scaffold a new ADR under
  `design/adrs/ADR-NNNN-<slug>.md` with auto-incremented NNNN
  (from the index in `design/adrs/README.md`). Prints the
  filepath + reminder to update the index.

- `new-trdd-from-issue <pr-number> <repo> <slug>` — scaffold a
  TRDD using a GitHub issue body as the Context section.
  Typically invoked by `maintainer-fix` when triage flags a
  non-trivial bug.

- `validate` — parse every TRDD + ADR; verify frontmatter
  compliance (trdd-id UUID format, title no colon, status enum,
  ISO 8601 dates, flow-style `blocked-by` / `superseded-by`
  lists when applicable). Returns per-file errors.

Canonical authoring rule for TRDDs:
`~/.claude/rules/trdd-design-tasks.md` (user-scope; not in the
repo).

Templates the skill substitutes:
- TRDD: `skills/maintainer-trdd-adr/references/trdd-template.md`
- ADR: `skills/maintainer-trdd-adr/references/adr-template.md`
- Seed READMEs:
  `skills/maintainer-trdd-adr/references/seed-readmes.md`

Pair with `/maintainer-detect-stack` — the detect-stack output
includes a "design/tasks/ + design/adrs/ present?" check; if
absent, suggests `/maintainer-trdd-adr bootstrap`.
