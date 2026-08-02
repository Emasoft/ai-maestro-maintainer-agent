---
description: |
  Use when the maintainer agent proactively scans the repo for
  supply-chain threats — at session start (BASELINE) or per
  patrol cycle (SCAN). Aggregates six threat classes (zizmor /
  stale pins / branch rules / protected-path activity / secret
  leaks / package-manager safety-config drift); SCAN diffs vs
  baseline and routes critical deltas.
  Trigger with phrases like "guardian baseline", "scan for
  threats", or "check for supply-chain drift".
---

# maintainer-guardian — proactive supply-chain sentinel

## Overview

The maintainer agent IS the guardian of the repo. This skill runs
the proactive half of that job. BASELINE captures a clean snapshot
at session start; SCAN diffs every patrol cycle against it and
routes T1-T6 detections to auto-fix / file-issue / alert. The
inspiration is Atai Barkai's 2026-05-20 supply-chain article — the
maintainer no longer waits for someone to file an issue saying
"your CI is broken", it watches and reacts.

## Prerequisites

- `gh auth token` returns a value.
- `uvx` on PATH (for the chained `workflow-scan` zizmor run).
- The maintained repo is checked out (working tree may be dirty).
- **Frozen CLI only (IRON RULE).** Every ai-maestro interaction goes through the
  frozen scripts — here, `amp-send` for the T5 escalation. NEVER call the
  ai-maestro server `/api/*` directly, not even to raise an urgent alert when
  `amp-send` is absent: alert the authorized user instead (threat-classes T5 →
  Route). (`gh` APIs are NOT covered — keep them.)

## Instructions

**BASELINE** (mode=baseline, invoked at session start):

1. Chain **workflow-scan** to capture zizmor + actionlint state.
2. Chain **workflow-protect-branch** SHOW to capture branch rules, AND
   assess them against the ratified baseline spec (T3-absolute) — record
   the `baseline_compliance` verdict so a repo already off-baseline at
   session start is flagged, not silently captured as "normal".
3. Inventory the canonical protected-paths list (see
   `maintainer-approval-gate/references/protected-paths.md`); for
   each path, capture its last-modified commit SHA.
4. Run the secret-leak regex scan on the last 50 commits.
5. If `package.json` exists, snapshot the four pkg-manager safety
   knobs from `.pnpm` / `.npmrc` / `pnpm-workspace.yaml` and the
   source-file SHAs (T6); else mark `is_node_repo: false` and skip.
6. Aggregate into `guardian-baseline.json` and write atomically to
   `$AGENT_DIR/.aimaestro/state/guardian-baseline.json`.

**SCAN** (mode=scan, invoked at every patrol pre-cycle):

1. Re-run all 6 detectors.
2. Diff against the baseline; produce a per-class delta.
3. Route each delta:
   - T1 new zizmor finding → if safe-fixable, propose workflow-fix-safe
     auto-fix PR; else file tracking issue + label.
   - T2 stale SHA pin → file tracking issue with Dependabot PR link.
   - T3 drift (vs snapshot) OR standing baseline non-compliance (vs the
     ratified spec) → alert authorized user; for non-compliance recommend
     `workflow-protect-branch` APPLY (re-apply ratified baseline — EXEMPT).
   - T4 protected-path touched → alert authorized user.
   - T5 secret-leak marker → STOP everything, alert immediately.
   - T6 pkg-manager safety knob weakened/stripped → alert authorized
     user, refuse to push; standing-missing on a Node repo → file
     tracking issue with template paste from workflow-bootstrap.
4. Write the running tally to `guardian-state.json`.
5. Return disposition; patrol decides whether to early-exit the cycle.

Full per-class commands + routing tables:
[threat-classes](references/threat-classes.md):

- T1 — Workflow drift
- T2 — Stale SHA pins
- T3 — Branch-rule drift
- T4 — Protected-path activity
- T5 — Secret-leak markers
- T6 — Package-manager safety-config drift
- Routing table
- Atomic write pattern

## Output

- **BASELINE**: `{mode, snapshot_path, t1_count, t2_count, t3_status,
  t3_compliance, t4_count, t5_count, t6_status}` + the refreshed snapshot
  file. (`t3_compliance` is `compliant` or a non-empty deviations list
  from the T3-absolute check; `t6_status` is `clean`, `missing-knobs`, or
  `not-a-node-repo`.)
- **SCAN**: `{mode, delta, route_decisions[], state_path, report}` plus the refreshed state file plus (optionally) issues/PRs filed.

## Error Handling

| Error | Action |
|-------|--------|
| `gh auth token` empty | Stop, surface |
| `workflow-scan` chain fails | Skip T1/T2, continue T3/T4/T5 |
| `workflow-protect-branch` SHOW fails | Mark T3 status `unknown`, continue |
| Baseline file missing during SCAN | Re-run BASELINE first, retry |
| T5 hit (suspected secret leak) | Stop; escalate URGENT to MANAGER via `amp-send` (self-id line in body) AND alert the authorized user; do NOT scan further (see threat-classes T5 → Route) |

## Examples

```
Session startup → SessionStart hook → guardian baseline
→ writes guardian-baseline.json (T1=0, T2=0, T3=active, T4=12, T5=0)
```

```
Patrol cycle 7 → guardian scan
→ T1 delta=+2 (new zizmor finding in validate.yml)
→ Route: workflow-fix-safe auto-fix PR
→ Returns: {delta: {t1: +2}, routes: ["auto-fix-pr#42"]}
```

```
Patrol cycle 11 → guardian scan
→ T6 delta: .npmrc shipped without minimum-release-age, or
  pyproject.toml [tool.uv] missing trust-policy=no-downgrade
→ Route: file tracking issue + alert authorized user
→ Returns: {delta: {t6: [".npmrc:5 missing min-release-age"]},
            routes: ["issue#88", "alert#$AUTHORIZED_USER"]}
```

## Scope

ONLY runs supply-chain detectors T1-T6 against the entrusted repo
(BASELINE writes a snapshot; SCAN diffs vs the snapshot). Does NOT:

- Apply fixes directly — it ROUTES findings to the right
  remediation skill (`workflow-fix-safe`, `workflow-pin-actions`,
  `maintainer-approval-gate`) or files a tracking issue.
- Push, force-push, or rewrite history.
- Trigger on a clean delta — every detection requires a concrete
  diff vs baseline.
- Run third-party scanners other than the documented six classes
  (zizmor + actionlint are reused via `workflow-scan`; everything
  else is in-repo logic).

Idempotent — re-running BASELINE replaces the snapshot atomically.

## Resources

- [Threat classes + routing](references/threat-classes.md):
  - T1 — Workflow drift
  - T2 — Stale SHA pins
  - T3 — Branch-rule drift
  - T4 — Protected-path activity
  - T5 — Secret-leak markers
  - T6 — Package-manager safety-config drift
  - Routing table
  - Atomic write pattern
- Companions: `workflow-scan`, `workflow-fix-safe`,
  `workflow-protect-branch`, `maintainer-approval-gate`.
- Inspiration: Atai Barkai, "Supply chain attacks are at an
  all-time high" (X.com, 2026-05-20).
