# ADR template (canonical Michael Nygard format)

The template below is what `new-adr` mode writes after substituting
`$NNNN` (zero-padded 4-digit number from the index in
`design/adrs/README.md`), `$SLUG` (short kebab-case), `$ISO` (full
ISO 8601 datetime with TZ offset), and `$AUTHOR` (from
`git config user.name`).

The substituted file goes to: `design/adrs/ADR-${NNNN}-${SLUG}.md`

## Format rules

- One decision per ADR. If a PR commits to two decisions, write two ADRs.
- Once `Status: accepted`, the ADR body is FROZEN. To change a decision,
  author a new ADR with `Status: supersedes ADR-NNNN` and flip the older
  ADR's status to `Status: superseded by ADR-MMMM`.
- `Status:` enum: `proposed` | `accepted` | `rejected` | `superseded by ADR-MMMM` | `supersedes ADR-NNNN`.
- `Date:` — ISO 8601 date (YYYY-MM-DD) is sufficient; full datetime not required for ADRs.
- `Authors:` — comma-separated list. Use the same name as `git config user.name`.

## Body sections

1. **Context** — what is the issue we're seeing that is motivating this decision?
2. **Decision** — what is the change we're proposing or doing?
3. **Consequences** — what becomes easier or more difficult because of this change?

Under Consequences, use three explicit subsections:
- **Easier:** what this change makes simpler / cheaper / safer.
- **More difficult:** what this change makes harder / introduces a new burden.
- **Neutral:** trade-offs that aren't clearly easier or harder.

## Template

```markdown
# ADR-${NNNN} — <Short title>

Status: proposed
Date: <YYYY-MM-DD>
Authors: ${AUTHOR}

## Context

<What is the issue we're seeing that motivates this decision?
Include the constraints, the alternatives we evaluated, and any
relevant code references or external sources. Aim for 2-4 paragraphs.>

## Decision

<What is the change we're proposing or doing? Be specific about
what changes and what doesn't. Reference files / line numbers
where the change lands.>

## Consequences

### Easier

<What becomes simpler / cheaper / safer because of this decision?
Use bullet points.>

### More difficult

<What becomes harder / introduces a new burden? Use bullet points.
Be honest — every decision has costs.>

### Neutral

<Trade-offs that aren't clearly easier or harder. Or migration
notes that aren't easier-or-harder themselves but are worth
recording.>

## References

- TRDD this ADR supports: \`design/tasks/TRDD-<...>.md\` (if relevant)
- Upstream docs / blog posts / RFCs
- Source files / line numbers where the decision lands
```

## Notes

- Keep ADRs short. A 200-word Context + a 100-word Decision + a
  150-word Consequences is plenty. If you need more, that's a
  signal the ADR covers too many decisions — split it.
- ADRs are accepted via PR like any other change. Once merged, the
  body is frozen.
- A naïve search for "why is X" should land on the ADR. Use clear
  titles and link liberally from code comments / TRDDs / commit
  messages.
- Index your ADR in `design/adrs/README.md` after creating it.
