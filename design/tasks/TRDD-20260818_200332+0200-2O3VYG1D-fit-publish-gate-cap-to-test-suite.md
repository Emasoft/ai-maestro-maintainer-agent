---
trdd-id: 2O3VYG1D
title: Fit the publish stage_tests cap to the suite it gates (375s suite vs 300s cap)
column: todo
created: 2026-08-18T20:03:32+0200
updated: 2026-08-18T20:03:32+0200
current-owner: maintainer-agent-session
task-type: infra
approval-tier: 0
created-by: hub endorsement 2026-08-18 (release-authorization message)
---

# Fit the publish stage_tests cap to the suite it gates

The full test suite takes **375s** (honest figure; the 971s measurement was
contention and is RETRACTED). The local publish gate runs it through the
shared `run()` helper at `scripts/publish.py:165` with `timeout=300`, which
`stage_tests` inherits at `:1061` — so a healthy suite can abort the local
release cut. CI is unaffected (`.github/workflows/ci.yml:208` runs pytest
directly under `timeout-minutes: 25`); this blocks the LOCAL cut only
(audit finding C4-1, downgraded scope).

## Decision to make (either resolves the card)

1. **Raise the stage_tests timeout** to fit the suite (e.g. 600s override at
   the `:1061` call site, leaving the 300s default for the other stages), or
2. **Split the suite** so the gate runs a fast subset locally (the 🐌-marked
   slow tests already exist as a category) and CI runs everything.

The gate must fit the suite it gates — a gate that times out on a passing
suite is a false red. Do NOT lower coverage and do NOT bypass the gate.

## Acceptance

- [ ] `uv run scripts/publish.py --gate` completes without a timeout kill on
      a passing tree
- [ ] no other stage's timeout changed unintentionally
- [ ] the choice (raise vs split) recorded here with the WHY

## Approval log
