---
description: |
  Use when the user wants to QUERY or APPLY the maintained repo's
  default-branch ruleset via the GitHub Rulesets API. Two modes:
  (1) SHOW — read-only fetch of the currently-deployed ruleset,
  cached to $HOME/.aimaestro/maintainer/AGENT_ID/branch-rules.json
  so other skills and the main agent stay aware of the live rule
  state across the session. (2) APPLY — auto-detects every CI job
  name from .github/workflows/*.yml, then POSTs (or PUTs if it
  already exists) a ruleset named `default-branch-ruleset` that
  targets the default branch via the ~DEFAULT_BRANCH magic ref,
  requires the discovered status checks to pass with strict-policy
  (must be up to date with base), blocks non-fast-forward pushes,
  and blocks branch deletion. Does NOT require pull request
  reviews (single-maintainer plugin pattern; the validate gate is
  the review). Fully idempotent — re-running APPLY converges to
  the same state; re-running SHOW just refreshes the cache. The
  authenticated user must have admin rights on the repo for APPLY
  (SHOW only requires read access). Reports under
  $MAIN_ROOT/reports/workflow-protect-branch/. Do NOT trigger on
  audit requests for workflow CONTENTS (use workflow-scan) or on
  requests to modify branches other than the default.
  Trigger with phrases like "protect main branch", "apply branch
  rules", "set up branch protection" (apply mode); or "show branch
  rules", "what branch rules are active", "fetch the ruleset",
  "refresh branch-rule cache" (show mode).
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
   `~/.aimaestro/maintainer/$AGENT_ID/branch-rules.json`.
3. Emit the summary disposition (see Output).

**APPLY** (when the trigger is "protect / apply / harden /
set up"):

1. Run SHOW first to capture the pre-state.
2. Auto-detect status check names by greping every
   `.github/workflows/*.yml` for two-space-indented job keys.
3. Build the canonical ruleset JSON in a tmpfile (no inline
   `${{ }}` interpolation).
4. POST or PUT to `/repos/$REPO/rulesets` depending on whether
   `default-branch-ruleset` already exists.
5. Run SHOW again to refresh the cache + emit a diff.

Full commands + the canonical JSON body:
[references/instructions.md](references/instructions.md).

## Output

- **SHOW**: `{mode, ruleset_count, default_branch_ruleset,
  cache_path}` plus the refreshed cache at
  `~/.aimaestro/maintainer/<agentId>/branch-rules.json`.
- **APPLY**: `{mode, action, ruleset_id, required_checks, report,
  cache_path}` plus the post-apply ruleset on the default branch
  AND the refreshed cache.

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
