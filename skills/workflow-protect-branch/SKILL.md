---
description: |
  Use when the user wants to QUERY or APPLY the maintained repo's
  default-branch rulesets via the GitHub Rulesets API. SHOW =
  read-only fetch + cache. APPLY = auto-detect CI job names, POST/PUT
  TWO rulesets — a no-bypass history-protect ruleset and an
  admin-bypass PR-and-checks ruleset. Idempotent.
  Trigger with phrases like "protect main branch", "apply branch
  rules" (apply), or "show branch rules" (show).
---

# workflow-protect-branch — idempotent default-branch rulesets

Applies a deterministic TWO-ruleset split to the maintained repo's
default branch via the GitHub Rulesets REST API. Idempotent —
re-running converges to the same state.

## Overview

Two modes: **SHOW** (read-only — fetches + caches the deployed
rulesets; run by the main agent at startup and after each push) and
**APPLY** (auto-detects status check names, then POSTs/PUTs **two**
rulesets):

| Ruleset | Rules | `bypass_actors` |
|---|---|---|
| `baseline-history-protect` | `deletion`, `non_fast_forward`, `required_linear_history` | `[]` (nobody, incl. admin) |
| `baseline-pr-and-checks` | `pull_request`, `required_status_checks` (strict) | admin RepositoryRole, `always` |

Two, not one, because `bypass_actors` applies to the WHOLE ruleset,
never per-rule: a single combined ruleset with an admin bypass would
also let admin force-push/delete. The split lets `publish.py`'s direct
push bypass the PR + checks gate (checks are un-greenable before a push
→ `GH013`) while force-push, deletion, and non-linear history stay
blocked for all.

## Prerequisites

- `gh auth token` returns a value (both modes).
- For APPLY only: authenticated user has `admin` permission on
  the repo. SHOW only requires read access.

## Instructions

**SHOW** (trigger: "show / fetch / refresh / what rules"):

1. `GET /repos/$REPO/rulesets`; for each, `GET .../rulesets/<id>`
   for the full body.
2. Atomically write the array to
   `$AGENT_DIR/.aimaestro/state/branch-rules.json`.
3. Emit the summary disposition (see Output).

**APPLY** (trigger: "protect / apply / harden / set up"):

1. Run SHOW first to capture the pre-state.
2. Auto-detect status check names by YAML-parsing every
   `.github/workflows/*.y*ml` and reading the `jobs:` keys. Never
   grep+awk — shell heuristics over-match and the POST 422s with
   "Expected context to be present".
3. Build BOTH ruleset JSON bodies in tmpfiles (no inline `${{ }}`):
   the no-bypass history-protect ruleset and the admin-bypass
   PR-and-checks ruleset.
4. For EACH ruleset, POST or PUT to `/repos/$REPO/rulesets`
   depending on whether one of that name already exists.
5. Run SHOW again to refresh the cache + emit a diff.

Full commands + both JSON bodies: see Resources.

## Output

- **SHOW**: `{mode, ruleset_count, rulesets, cache_path}` + refreshed
  cache at `$AGENT_DIR/.aimaestro/state/branch-rules.json` (the full
  ruleset array — covers both).
- **APPLY**: `{mode, history_ruleset:{id,action},
  checks_ruleset:{id,action}, required_checks, report, cache_path}`.

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

"apply branch protection to main"
→ APPLY → detect jobs → POST/PUT history ruleset (no bypass) +
  POST/PUT checks ruleset (admin bypass) → SHOW refresh
```

## Scope

ONLY queries (SHOW) or applies (APPLY) the two canonical
default-branch rulesets (`baseline-history-protect` +
`baseline-pr-and-checks`) via the GitHub Rulesets REST API.
Does NOT:

- Manage non-default branches — both target `~DEFAULT_BRANCH`.
- Touch environment- or org-level rulesets — repo-level only.
- Push, commit, or modify the entrusted repo's working tree.
- Manage rules beyond the ratified baseline — exactly `deletion`,
  `non_fast_forward`, `required_linear_history` (history) plus
  `pull_request` (1 approval) + `required_status_checks` (PR + checks).
- Add bypass actors beyond admin RepositoryRole on the pr-and-checks
  ruleset; the history ruleset stays bypass-less for all.

Idempotent — APPLY converges to the same two-ruleset state.

## Resources

- Rulesets API: <https://docs.github.com/en/rest/repos/rules>
- Companion: `workflow-scan`, `workflow-fix-safe`,
  `workflow-pin-actions`.
- [Full step-by-step instructions](references/instructions.md):
  - Why two rulesets, not one
  - Step 0: Decide mode (SHOW vs APPLY)
  - Step 1: Verify admin permission (APPLY only)
  - Step 2: Auto-detect required checks (APPLY only)
  - Step 3: Build the two ruleset JSON bodies (APPLY only)
  - Step 4: Discover both existing rulesets
  - Step 5: POST or PUT each ruleset (APPLY only)
  - Step 6: Verify both present post-apply
  - Step 6.5: Delete orphaned legacy rulesets (APPLY only)
  - Step 7: Write report + refresh agent cache
