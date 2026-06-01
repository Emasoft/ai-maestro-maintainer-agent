---
description: Capture a clean T1-T6 threat snapshot of the maintained repo. Idempotent — re-running refreshes the baseline.
argument-hint: "[--threats T1,T2,...] [--force]"
---

Capture a clean snapshot of the maintained repo's threat surface
across all six Guardian threat classes:

- **T1** — workflow drift (zizmor + actionlint + Sentinel-port
  findings on `.github/workflows/`)
- **T2** — stale SHA pins (actions referenced by tag or by
  outdated SHA)
- **T3** — branch-rule state (current default-branch ruleset(s)
  config)
- **T4** — protected-path activity (recent commits touching the
  canonical protected paths)
- **T5** — secret-leak markers in recent commits
  (`fast_security_scan.py` patterns)
- **T6** — package-manager safety-knob drift (`.npmrc`,
  `pnpm-workspace.yaml`, `pyproject.toml [tool.uv]`)

Loads skill: **maintainer-guardian** (mode=BASELINE)

The snapshot is written to
`$AGENT_DIR/.aimaestro/state/guardian-baseline.json`.

This command is **idempotent** — running it on an already-baselined
repo simply refreshes the snapshot. The SessionStart hook fires
this automatically at the start of every maintainer-agent session;
the maintainer-patrol skill is the backstop (auto-baselines if
the file is missing); this slash command is for manual refresh.

To detect drift since the baseline, use
`/maintainer-guardian-scan` (mode=SCAN).
