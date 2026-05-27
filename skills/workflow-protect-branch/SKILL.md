---
description: |
  Use when the user wants to QUERY or APPLY the maintained repo's
  default-branch ruleset via the GitHub Rulesets API. SHOW =
  read-only fetch + cache. APPLY = auto-detect CI job names,
  POST/PUT a ruleset requiring those checks, blocks
  non-fast-forward + deletion. Idempotent.
  Trigger with phrases like "protect main branch", "apply branch
  rules" (apply), or "show branch rules" (show).
---

# workflow-protect-branch — idempotent default-branch ruleset

Uses the GitHub Rulesets REST API (stable, see
`docs.github.com/en/rest/repos/rules`) to apply a deterministic
ruleset to the maintained repo's default branch. Fully idempotent
— re-running converges to the same state.

## Overview

Two modes sharing one skill: **SHOW** (read-only — fetches the
deployed ruleset and caches it for downstream skills) and
**APPLY** (read+write — auto-detects status check names from
local workflows, POSTs/PUTs the `default-branch-ruleset` that
requires those checks, blocks force-push, blocks deletion). SHOW
is what the main agent runs at session startup and after every
push to stay aware of the live state. APPLY is idempotent.

## Prerequisites

- `gh auth token` returns a value (both modes).
- For APPLY only: authenticated user has `admin` permission on
  the repo. SHOW only requires read access.

## Instructions

**SHOW** (default when the trigger is read-only — "show / fetch /
refresh / what rules"):

1. `GET /repos/$REPO/rulesets` and for each, `GET
   /repos/$REPO/rulesets/<id>` for the full body.
2. Atomically write the array to
   `$AGENT_DIR/.aimaestro/state/branch-rules.json`.
3. Emit the summary disposition (see Output).

**APPLY** (when the trigger is "protect / apply / harden /
set up"):

1. Run SHOW first to capture the pre-state.
2. Auto-detect status check names by YAML-parsing every
   `.github/workflows/*.yml` and reading the `jobs:` keys. Never
   grep+awk — shell heuristics over-match and the resulting POST
   422s with "Expected context to be present".
3. Build the canonical ruleset JSON in a tmpfile (no inline
   `${{ }}` interpolation).
4. POST or PUT to `/repos/$REPO/rulesets` depending on whether
   `default-branch-ruleset` already exists.
5. Run SHOW again to refresh the cache + emit a diff.

Full commands + the canonical JSON body:
[references/instructions.md](references/instructions.md).

## Output

- **SHOW**: `{mode, ruleset_count, default_branch_ruleset,
  cache_path}` + refreshed cache at
  `$AGENT_DIR/.aimaestro/state/branch-rules.json`.
- **APPLY**: `{mode, action, ruleset_id, required_checks, report,
  cache_path}` + post-apply ruleset + refreshed cache.

## Error Handling

| Error | Action |
|-------|--------|
| `gh auth token` empty | Stop, surface |
| `.permissions.admin` returns `false` | Stop, surface "needs admin" |
| `gh api -X POST` returns 4xx (other than 404) | Stop, capture response body in report |
| `gh api -X PUT` returns 404 (ruleset deleted concurrently) | Retry as POST |
| Rate-limit hint | Stop, return partial-progress disposition |

## Examples

```
"what branch rules are active?"
→ SHOW → GET /rulesets → cache → return summary
```

```
"apply branch protection to main"
→ APPLY → detect jobs → POST or PUT → SHOW refresh
```

More walk-throughs (first-time apply, idempotent re-apply,
fresh-repo zero-rulesets case):
[references/instructions.md](references/instructions.md).

## Scope

ONLY queries (SHOW) or applies (APPLY) the
`default-branch-ruleset` via the GitHub Rulesets REST API. Does NOT:

- Manage non-default branches — ruleset target is hard-coded to
  `~DEFAULT_BRANCH`.
- Set or modify environment-level protections (those are a separate
  API surface).
- Apply org-level rulesets — repo-level only.
- Push, commit, or modify the entrusted repo's working tree.
- Configure required reviews — only required_status_checks +
  non_fast_forward + deletion blocking.

Idempotent — re-running APPLY converges to the same ruleset state.

## Resources

- Rulesets API: <https://docs.github.com/en/rest/repos/rules>
- Companion: `workflow-scan`, `workflow-fix-safe`,
  `workflow-pin-actions`.
- [Full step-by-step instructions](references/instructions.md):
  - Step 0: Decide mode (SHOW vs APPLY)
  - Step 1: Verify admin permission (APPLY only)
  - Step 2: Auto-detect required checks (APPLY only)
  - Step 3: Build the ruleset JSON (APPLY only)
  - Step 4: Discover existing ruleset
  - Step 5: POST or PUT (APPLY only)
  - Step 6: Verify post-apply
  - Step 7: Write report + refresh agent cache
