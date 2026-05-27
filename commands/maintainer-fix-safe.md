---
description: Apply mechanical workflow hardening via zizmor --fix=safe + targeted edits. Commits on the current branch; never force-pushes.
argument-hint: "[--issue <issue-number>]"
---

Run mechanical security fixes on `.github/workflows/`:

- `zizmor --fix=safe` (only fixes upstream marks as safe)
- Add missing top-level `permissions: contents: read` blocks
- Add missing `concurrency:` and `timeout-minutes:` blocks
- Set `persist-credentials: false` on `actions/checkout`
- Audit jq command substitutions for the `--arg` trap (rewrite
  `${VAR}` inside double-quoted jq filter strings to `--arg name
  "$VAR"` + `$name` filter ref)

Loads skill: **workflow-fix-safe**

Commits each category of fix as a separate atomic commit on the
current branch. Refuses to force-push (R19.7). The diff is
filtered against the approval-gate's protected-paths list — any
hit halts before commit and requests `approve-protected-edit`
from the authorized user.

Pair with `/maintainer-pin-actions` to also resolve unpinned
action references to SHAs.
