# Architecture Decision Records (ADRs)

ADRs document **why** we chose a particular technical approach. They
complement TRDDs (which document **what** we intend to build) and the
git history (which documents **what we actually did**).

Format follows Michael Nygard's template:

```markdown
# ADR-NNNN — <Short title>

Status: <proposed | accepted | rejected | superseded by ADR-MMMM>
Date: <ISO 8601 date>
Authors: <names>

## Context

What is the issue we're seeing that is motivating this decision?

## Decision

What is the change we're proposing or doing?

## Consequences

What becomes easier or more difficult to do because of this change?
```

## Conventions

- Filename: `ADR-NNNN-<short-slug>.md`. NNNN is zero-padded to 4
  digits, monotonically increasing.
- Numbering: assign the next NNNN at PR time, not at draft time.
- Status: once `accepted`, the ADR body is FROZEN. To change a
  decision, author a new ADR with `Status: supersedes ADR-NNNN` and
  flip the older ADR's status to `Status: superseded by ADR-MMMM`.
- One decision per ADR. If a PR commits to two decisions, write two
  ADRs.

## Reference

- [Documenting Architecture Decisions — Michael Nygard, 2011-11-15](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)
- TRDD authoring rule: `~/.claude/rules/trdd-design-tasks.md`
- This repo's TRDDs: `../tasks/`

## Index

| ADR | Title | Status |
|---|---|---|
| 0001 | TRDD vs ADR split | accepted |
| 0002 | No `allowed-tools` frontmatter — dynamic tool surface | accepted |
| 0003 | Per-agent state under `$AGENT_DIR/.aimaestro/state/`, not `$HOME` | accepted |
| 0004 | Python port of jpr5/sentinel rather than Ruby-gem runtime dep | accepted |
| 0005 | Skills as primary surface; slash-commands as discoverability layer | accepted |
