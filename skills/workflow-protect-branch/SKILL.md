---
description: |
  Use when the user wants idempotent branch-protection on the
  maintained repo's default branch via the GitHub Rulesets API.
  Discovers every CI job name across .github/workflows/*.yml,
  then POSTs (or PUTs if it already exists) a ruleset named
  `default-branch-ruleset` that: targets the default branch via
  the ~DEFAULT_BRANCH magic ref, requires the discovered status
  checks to pass with strict-policy (must be up to date with
  base), blocks non-fast-forward pushes, and blocks branch
  deletion. Does NOT require pull request reviews (this is a
  single-maintainer plugin pattern; the validate gate is the
  review). Fully idempotent — safe to re-run any number of times:
  GET the rulesets list first, find by name, PUT to update or
  POST to create. Assumes AI Maestro has exported the gh auth
  token; reads it via `$(gh auth token)`. The authenticated user
  must have admin rights on the repo — the skill verifies via
  `gh api repos/OWNER/REPO --jq .permissions.admin` before any
  write, and stops with a clear message if not. Reports the
  before/after ruleset state to
  $MAIN_ROOT/reports/workflow-protect-branch/. Do NOT trigger on
  read-only audit requests (use workflow-scan) or on requests to
  modify other branches — this skill ONLY protects the default
  branch. Trigger with phrases like "protect main branch", "apply
  branch rules", "set up branch protection", "harden default
  branch", or "apply default-branch ruleset".
---

# workflow-protect-branch — idempotent default-branch ruleset

Uses the GitHub Rulesets REST API (stable, see
`docs.github.com/en/rest/repos/rules`) to apply a deterministic
ruleset to the maintained repo's default branch. Fully idempotent
— re-running converges to the same state.

## Overview

Auto-detects required CI status check names from the local
workflows, then POSTs (create) or PUTs (update) a ruleset called
`default-branch-ruleset` that requires those checks, blocks
non-fast-forward pushes, and blocks branch deletion. Targets the
default branch via the `~DEFAULT_BRANCH` magic ref. No PR review
requirement (single-maintainer pattern). Idempotent.

## Prerequisites

- `gh auth token` returns a value.
- Authenticated user has `admin` permission on the repo
  (`gh api repos/$REPO --jq .permissions.admin` returns `true`).
  Otherwise stops with a clear "needs admin" message.

## Instructions

1. Auto-detect required status check names by greping every
   `.github/workflows/*.yml` for two-space-indented job keys.
2. Build the canonical ruleset JSON in a tmpfile (no inline
   `${{ }}` interpolation).
3. List existing rulesets, find one named
   `default-branch-ruleset`, capture its id (empty if none).
4. POST `/repos/{owner}/{repo}/rulesets` to create, or PUT
   `/repos/{owner}/{repo}/rulesets/{id}` to update.
5. Verify post-apply via `gh ruleset list` + `gh ruleset view`.
6. Write before/after ruleset state under
   `$MAIN_ROOT/reports/workflow-protect-branch/`.

Full commands and the canonical JSON body: see
[references/instructions.md](references/instructions.md).

## Output

A JSON object with `action` (`created` / `updated` / `noop`),
`ruleset_id`, `required_checks`, and `report` fields, plus the
post-apply ruleset in place on the default branch.

## Error Handling

| Error | Action |
|-------|--------|
| `gh auth token` empty | Stop, surface |
| `.permissions.admin` returns `false` | Stop, surface "needs admin" |
| `gh api -X POST` returns 4xx (other than 404) | Stop, capture response body in report |
| `gh api -X PUT` returns 404 (ruleset deleted concurrently) | Retry as POST |
| Rate-limit hint | Stop, return partial-progress disposition |

## Examples

First-time apply (no existing ruleset):

```
User: "apply branch protection to main"
→ Detect jobs: validate, workflow-security
→ GET /rulesets → empty
→ POST /rulesets with the canonical JSON
→ Return: {action: "created", ruleset_id: 12345, ...}
```

Re-run after the same skill:

```
User: "apply branch protection to main"
→ GET /rulesets → found id=12345 named default-branch-ruleset
→ PUT /rulesets/12345 with the same JSON
→ Return: {action: "updated", ruleset_id: 12345, ...}
```

## Resources

- Rulesets REST API:
  <https://docs.github.com/en/rest/repos/rules>
- Companion skills: `workflow-scan`, `workflow-fix-safe`,
  `workflow-pin-actions`.
- [Full step-by-step instructions](references/instructions.md):
  - Step 1: Verify admin permission
  - Step 2: Auto-detect required checks
  - Step 3: Build the ruleset JSON
  - Step 4: Discover existing ruleset
  - Step 5: POST or PUT
  - Step 6: Verify post-apply
  - Step 7: Write report
