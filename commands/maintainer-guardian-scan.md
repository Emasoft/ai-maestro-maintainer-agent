---
description: Scan the maintained repo for T1-T6 threat deltas since the last Guardian baseline. Routes critical deltas to auto-fix / file-issue / alert.
argument-hint: "[--since <baseline>] [--threats T1,T2,...] [--dry-run]"
---

Diff the maintained repo's current threat state against the last
Guardian baseline (captured by
`/maintainer-guardian-baseline`). Critical deltas are routed:

- T1 zizmor/actionlint/Sentinel-port HIGH or CRITICAL → fire
  `workflow-fix-safe` to auto-PR a safe fix
- T2 stale SHA pin → file a tracking issue (`gh issue create`)
- T3 branch-rule change → alert the authorized user (R6 direct
  edge)
- T4 protected-path activity → require
  `approve-protected-edit` from the authorized user on the
  originating issue before any further action
- T5 secret leak in a recent commit → **STOP** the cycle and
  alert the authorized user immediately. Do NOT proceed.
- T6 package-manager knob drift → file a tracking issue + propose
  the corrected `.npmrc` / `pnpm-workspace.yaml` / `[tool.uv]`
  block in the issue body

Loads skill: **maintainer-guardian** (mode=SCAN)

The cycle's per-cycle state is written to
`$AGENT_DIR/.aimaestro/state/guardian-state.json` for the next
SCAN to diff against. Routes that fired are listed there with
their target ids (issue numbers, PR numbers, alert ids).

This command runs automatically at the start of every patrol
cycle (pre-cycle); the slash command is the manual on-demand
entry.

If the baseline file is missing, this command refuses to run and
points the user at `/maintainer-guardian-baseline`. A "phantom
delta" (every finding flagged as new) would be the alternative —
unhelpful.
