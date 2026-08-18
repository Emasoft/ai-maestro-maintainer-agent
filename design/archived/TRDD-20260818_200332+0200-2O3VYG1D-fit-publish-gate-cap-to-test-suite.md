---
trdd-id: 2O3VYG1D
title: Fit the publish stage_tests cap to the suite it gates (375s suite vs 300s cap)
column: completed
created: 2026-08-18T20:03:32+0200
updated: 2026-08-18T20:55:00+0200
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

- [x] the pytest stage can no longer be killed by the cap on a passing suite:
      `run()` gained `timeout: int = 300` and the stage_tests call passes
      `timeout=1200` (v1.13.9's publish run also passed live minutes earlier)
- [x] no other stage changed: every other `run()` caller keeps the 300s
      default; the two direct `subprocess.run(..., timeout=300)` at :834/:872
      (jscpd/validate) untouched — they complete well under 300s
- [x] choice recorded: RAISE, not split. WHY: CI already runs the full suite
      under a 25-min ceiling; the local gate's cap exists to catch a HANG, not
      to race the suite — 1200s fits even the contended 971s measurement while
      still bounding a hang, and splitting would make the local gate weaker
      than CI for no cost saving. ruff+mypy clean; the 3 publish-importing
      test files pass (27 passed).

## Approval log

- 2026-08-18T20:55:00+0200 — COMPLETED by maintainer-agent-session (Tier-0,
  hub-endorsed card). Rides the next release; not worth a same-day re-cut.
