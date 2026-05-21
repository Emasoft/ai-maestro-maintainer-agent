---
description: |
  Use when the maintainer agent needs to proactively scan the
  maintained repo for supply-chain threats — at session start to
  capture a baseline, or at every patrol cycle to detect new
  threats as a delta. Two modes. (1) BASELINE — invoked once at
  session start by the SessionStart hook; aggregates FIVE threat
  classes (T1 zizmor/actionlint findings, T2 stale SHA pins,
  T3 branch-rule state, T4 protected-path activity, T5 secret-leak
  markers in recent commits) into a JSON snapshot cached to
  $HOME/.aimaestro/maintainer/AGENT_ID/guardian-baseline.json.
  (2) SCAN — invoked at every patrol pre-cycle; re-runs the same
  five detectors, diffs against the baseline, writes the running
  tally to guardian-state.json, returns a disposition. Critical
  T1-T5 deltas route to one of three responses: auto-fix-PR
  (workflow-fix-safe for safe zizmor findings), file-tracking-issue
  (stale pins, drift), or alert-authorized-user (protected-path
  edits, secret leaks). Idempotent — re-running either mode just
  refreshes its file. Reports under
  $MAIN_ROOT/reports/maintainer-guardian/. Do NOT trigger on
  one-shot audit requests (use workflow-scan) or on issue triage
  (use maintainer-triage).
  Trigger with phrases like "guardian baseline", "scan for
  threats", "run guardian scan", or "check for supply-chain drift".
---

# maintainer-guardian — proactive supply-chain sentinel

## Overview

The maintainer agent IS the guardian of the repo. This skill runs
the proactive half of that job. BASELINE captures a clean snapshot
at session start; SCAN diffs every patrol cycle against it and
routes T1-T5 detections to auto-fix / file-issue / alert. The
inspiration is Atai Barkai's 2026-05-20 supply-chain article — the
maintainer no longer waits for someone to file an issue saying
"your CI is broken", it watches and reacts.

## Prerequisites

- `gh auth token` returns a value.
- `uvx` on PATH (for the chained `workflow-scan` zizmor run).
- The maintained repo is checked out (working tree may be dirty).

## Instructions

**BASELINE** (mode=baseline, invoked at session start):

1. Chain **workflow-scan** to capture zizmor + actionlint state.
2. Chain **workflow-protect-branch** SHOW to capture branch rules.
3. Inventory the canonical protected-paths list (see
   `maintainer-approval-gate/references/protected-paths.md`); for
   each path, capture its last-modified commit SHA.
4. Run the secret-leak regex scan on the last 50 commits.
5. Aggregate into `guardian-baseline.json` and write atomically to
   `~/.aimaestro/maintainer/$AGENT_ID/guardian-baseline.json`.

**SCAN** (mode=scan, invoked at every patrol pre-cycle):

1. Re-run all 5 detectors.
2. Diff against the baseline; produce a per-class delta.
3. Route each delta:
   - T1 new zizmor finding → if safe-fixable, propose workflow-fix-safe
     auto-fix PR; else file tracking issue + label.
   - T2 stale SHA pin → file tracking issue with Dependabot PR link.
   - T3 branch-rule drift → alert authorized user; refuse to push.
   - T4 protected-path touched → alert authorized user.
   - T5 secret-leak marker → STOP everything, alert immediately.
4. Write the running tally to `guardian-state.json`.
5. Return disposition; patrol decides whether to early-exit the cycle.

Full per-class commands + routing tables:
[references/threat-classes.md](references/threat-classes.md).

## Output

- **BASELINE**: `{mode, snapshot_path, t1_count, t2_count, t3_status,
  t4_count, t5_count}` + the refreshed snapshot file.
- **SCAN**: `{mode, delta, route_decisions[], state_path, report}`
  + the refreshed state file + (optionally) issues/PRs filed.

## Error Handling

| Error | Action |
|-------|--------|
| `gh auth token` empty | Stop, surface |
| `workflow-scan` chain fails | Skip T1/T2, continue T3/T4/T5 |
| `workflow-protect-branch` SHOW fails | Mark T3 status `unknown`, continue |
| Baseline file missing during SCAN | Re-run BASELINE first, retry |
| T5 hit (suspected secret leak) | Stop, alert authorized user, do NOT scan further |

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

## Resources

- [Threat classes + routing](references/threat-classes.md):
  - T1 workflow drift
  - T2 stale SHA pins
  - T3 branch-rule drift
  - T4 protected-path activity
  - T5 secret-leak markers
- Companions: `workflow-scan`, `workflow-fix-safe`,
  `workflow-protect-branch`, `maintainer-approval-gate`.
- Inspiration: Atai Barkai, "Supply chain attacks are at an
  all-time high" (X.com, 2026-05-20).
