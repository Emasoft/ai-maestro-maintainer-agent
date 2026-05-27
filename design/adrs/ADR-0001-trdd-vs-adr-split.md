# ADR-0001 — TRDD vs ADR split

Status: accepted
Date: 2026-05-27
Authors: Emasoft

## Context

The repo accumulates two distinct kinds of long-lived design
artifacts:

1. **Specifications of work to be done** — e.g. "we want to add a
   Guardian threat class T6 that detects package-manager safety
   knob drift; here are the detectors, the data flow, the test
   plan, the file list, and the acceptance criteria."
2. **Decisions of how to solve a problem** — e.g. "we chose to port
   jpr5/sentinel to Python rather than runtime-depend on the Ruby
   gem because <reasons>; the trade-off is <X>."

These two artifacts have different lifecycles and different reader
expectations:

- A spec is read by the implementer (often the agent itself, on a
  later patrol cycle) and answers "what do I have to ship?"
- A decision is read by the maintainer six months later when the
  context has decayed and answers "why is this not the obvious
  approach?"

Conflating them in a single file class produces docs that are
either too dense (decisions buried in spec text) or too thin (specs
that don't justify their non-obvious choices).

The Claude Code ecosystem has the user-scope `~/.claude/rules/trdd-design-tasks.md`
convention for TRDDs but says nothing about ADRs. We have to decide
locally whether to extend the TRDD format to cover decisions, or
adopt the conventional ADR format alongside.

## Decision

We adopt **both**, as parallel artifacts in `design/`:

- `design/tasks/TRDD-<TS>-<uid-first-8>-<slug>.md` — task /
  specification documents. Frontmatter per
  `~/.claude/rules/trdd-design-tasks.md`. Lifecycle: in-progress
  while work is underway; terminal status when complete.
- `design/adrs/ADR-NNNN-<slug>.md` — decision records using the
  Michael Nygard format. Lifecycle: accepted once merged;
  superseded by a later ADR when revisited.

A PR may add a TRDD, an ADR, both, or neither — depending on
whether the work is non-trivial (TRDD) and whether it commits to a
non-obvious technical choice (ADR).

The two are cross-referenced where relevant: a TRDD that
implements a decision references the ADR; an ADR that motivates a
new line of work references the TRDD.

## Consequences

**Easier:**

- A reader (human or agent) looking for "why is X this way" goes to
  `design/adrs/` and finds a small set of focused decision
  records. The git log + TRDD bodies remain the source of "how it
  was done."
- ADRs are easy to grep — one file = one decision, monotonic
  numbering.
- The format is familiar to any reader who has seen ADRs
  elsewhere, so no project-specific onboarding cost.

**More difficult:**

- Two artifact classes means contributors must learn which to use
  when. The README in `design/adrs/` and `CONTRIBUTING.md` both
  cover this; we accept the small extra cognitive cost.
- A naïve search for the rationale behind a feature might land
  only on the TRDD or only on the ADR, missing the other. We
  cross-reference in the body of each to mitigate.

**Neutral:**

- Some decisions will be small enough that they fit in a commit
  body without needing an ADR. We use the rule: "if a future
  reader (or you in six months) would ask 'why didn't we do the
  obvious thing here', author an ADR."

## References

- TRDD frontmatter rule: `~/.claude/rules/trdd-design-tasks.md`
- Michael Nygard, "Documenting Architecture Decisions", 2011-11-15:
  <https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions>
- This decision is independent of the TRDD format (the TRDD format
  is set by an external rule we do not own); we simply choose to
  not extend it to cover decisions.
