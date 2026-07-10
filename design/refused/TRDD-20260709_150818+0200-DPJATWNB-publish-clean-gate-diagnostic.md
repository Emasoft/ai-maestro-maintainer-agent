---
trdd-id: DPJATWNB
title: Diagnose stray runtime artifacts in the publish.py clean-tree gate
column: refused
approval-tier: 2
created: 2026-07-09T15:08:18+0200
updated: 2026-07-09T15:24:00+0200
current-owner: ai-maestro-maintainer-agent
task-type: infra
priority: 5
severity: LOW
effort: S
labels: [publish, fleet-readiness, diagnostics]
release-via: none
delivery: direct-push
target-branch: main
test-requirements: []
audit-requirements: []
review-requirements: []
relevant-rules: []
parent-trdd: null
supersedes: []
impacts: []
implementation-commits: []
published-version: null
published-at: null
external-refs: ["github.com/Emasoft/ai-maestro-maintainer-agent/issues/26"]
---

# TRDD-DPJATWNB — Diagnose stray runtime artifacts in the publish.py clean-tree gate

## STATE — READ THIS FIRST ON RESUME (authoritative) — 2026-07-09T15:24:00+0200

**Current state: REFUSED. Never approved, never implemented. Its premise was FALSE.
NEXT ACTION: none. This file is an audit record only. Do NOT resurrect it without first
re-reading `scripts/publish.py::stage_check_clean` — the behaviour it complains about does
not exist.**

- **SUPERSEDED — do NOT carry forward:** the claims "the gate prints no paths", "the
  operator sees only `Working tree is dirty` with no clue which file caused it", and "would
  silently block every future publish". All three are false. See "Why this was refused".
- `scripts/publish.py` was NOT modified. No protected-path edit was made.

## Why this was refused (post-mortem)

The proposal was authored from the #26 B2 audit report. That report quoted
`stage_check_clean` as a four-statement function: a docstring, a capture of the porcelain
status, a red "Working tree is dirty. Commit or stash changes first." message, and a
non-zero exit.

**The quote was truncated.** The real function (`scripts/publish.py`, lines 887-895) carries
two further statements the report silently dropped: a step banner, and — decisively — a
second print at **line 893** which emits the captured porcelain listing verbatim before the
exit.

Because of that one dropped line, an un-ignored AI-Maestro runtime artifact surfaces **by
name** (`?? .claude/some-new-artifact`) whenever the gate trips. The failure is loud and
self-describing, not silent. The operator's next step — gitignore it, in a deliberate
reviewed edit — is obvious from the output.

(Read the function in `scripts/publish.py` for the exact code; it is deliberately not
reproduced here, so this design document stays inert prose rather than executable-looking
source.)

What remained after the correction was only a cosmetic nicety: an extra hint line
classifying the path as "probably an AI-Maestro runtime artifact". That does not justify
editing `scripts/publish.py`, which is (a) a **protected path** and (b) the **only** push
path in this repo — a regression there bricks every future release. Weighed against a
cosmetic hint, the change is over-engineering and net-negative risk. Refused on the merits.

## Lessons

1. **Verify a quoted snippet against the source before building on it.** The audit was an
   agent-produced report; its `stage_check_clean` quote silently dropped two lines
   (the porcelain-listing print and the step banner). Everything downstream — this TRDD's Problem
   statement, its "silently bricks publish" framing, its acceptance criteria — inherited the
   error. A single `Read` of the real function would have (and finally did) catch it.
2. **A report is evidence, not truth.** Reports get promoted into decisions; a wrong line in
   a report becomes a wrong line in a spec, then a wrong edit to a protected file. Re-read
   the primary source at the moment of the decision, not just at the moment of the audit.
3. **A refused proposal is a success of the gate, not a waste.** The proposal → verify →
   refuse loop cost one file and zero risk. Had it been a direct edit to `publish.py` under
   "fix everything", it would have modified the sole push path for no benefit.

## Original problem statement (RETAINED FOR THE RECORD — factually WRONG, see above)

> `stage_check_clean` is an unconditional hard-fail on ANY non-ignored dirty or untracked
> path, with no distinction and no diagnostic. The message prints no paths, so the operator
> sees only `Working tree is dirty` with no clue which file caused it. Because #26 makes this
> repo self-maintaining, a future AI-Maestro runtime artifact landing outside the ignore set
> would silently brick every publish of this repo — including self-publish — with a message
> naming no file.

Both italicised claims are false. The gate prints every offending path and exits non-zero.

## What IS still true (and needs no change)

- The clean-tree gate is a correct fail-fast: it exits `1` on any non-ignored dirty path and
  names the paths. Preserved as-is.
- Packaging is git-native (the GitHub release is cut from the pushed tag; no filesystem-walking
  bundler), so there is no exclusion list to maintain — `.gitignore` is the single source of
  truth. Audited PASS under #26 ITEM 2.
- `.gitignore` today covers every path the persona/skills declare they write. Verified
  path-by-path on 2026-07-09.

## Approval log

- 2026-07-09T15:24:00+0200 — REFUSED by ai-maestro-maintainer-agent (self-withdrawn before
  any approver acted; tier 2 never exercised). Rationale: the proposal's core factual premise
  was wrong — `stage_check_clean` already prints every offending path (at line 893).
  The residual change was a cosmetic hint on a protected, release-critical file. Refused on
  the merits; `scripts/publish.py` left untouched.
