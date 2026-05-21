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
allowed-tools: "Bash(gh:*), Bash(git:*), Bash(grep:*), Read, Write, Grep, Glob"
---

# workflow-protect-branch — idempotent default-branch ruleset

Uses the GitHub Rulesets REST API (stable since 2022-11-28) to
apply a deterministic ruleset to the maintained repo's default
branch. Fully idempotent — re-running converges to the same state.

## Prerequisites (auto-checked)

- `gh auth token` returns a value.
- Authenticated user has `admin` permission on the repo:
  ```bash
  gh api "repos/$REPO" --jq '.permissions.admin'  # → true
  ```
  Otherwise the skill stops with a clear "needs admin" message.

## Workflow

1. Auto-detect required status checks from local workflows:
   ```bash
   CHECKS=$(grep -REn '^[[:space:]]{2}[a-z0-9_-]+:' \
     .github/workflows/*.yml \
     | awk -F: '/^[^:]+:[0-9]+:  /{print $NF}' \
     | tr -d ' ' | sort -u)
   ```
   Expected for this plugin: `validate` and `workflow-security`.
2. Build the canonical ruleset JSON (write to a tmpfile —
   never inline in the shell with `${{ }}` interpolation):
   ```json
   {
     "name": "default-branch-ruleset",
     "target": "branch",
     "enforcement": "active",
     "conditions": {
       "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] }
     },
     "rules": [
       {
         "type": "required_status_checks",
         "parameters": {
           "strict_required_status_checks_policy": true,
           "required_status_checks": [
             { "context": "validate" },
             { "context": "workflow-security" }
           ]
         }
       },
       { "type": "non_fast_forward" },
       { "type": "deletion" }
     ]
   }
   ```
3. Discover existing ruleset by name:
   ```bash
   RULESET_ID=$(gh api "repos/$REPO/rulesets" \
     --jq '[.[] | select(.name=="default-branch-ruleset")] | .[0].id // empty')
   ```
4. POST or PUT:
   ```bash
   if [ -z "$RULESET_ID" ]; then
     gh api -X POST "repos/$REPO/rulesets" --input /tmp/ruleset-$$.json
   else
     gh api -X PUT "repos/$REPO/rulesets/$RULESET_ID" --input /tmp/ruleset-$$.json
   fi
   ```
5. Verify post-apply:
   ```bash
   gh ruleset list --repo "$REPO" | grep default-branch-ruleset
   ```
6. Write report under
   `$MAIN_ROOT/reports/workflow-protect-branch/<ts>-ruleset.json`
   (before + after states + diff).
7. Return:
   ```json
   {
     "action": "created" | "updated" | "noop",
     "ruleset_id": <int>,
     "required_checks": ["validate", "workflow-security"],
     "report": "<path>"
   }
   ```

## Constraints

- ONLY targets the default branch (`~DEFAULT_BRANCH` magic ref).
- Does NOT require PR reviews (single-maintainer plugin pattern).
- Stops if `gh auth token` lacks admin permission on the repo.
- NEVER deletes a ruleset.
- NEVER edits any other ruleset (only `default-branch-ruleset`).
- All API writes via `--input <tmpfile>` — no inline JSON with
  context interpolation.

## Resources

- Rulesets REST API: <https://docs.github.com/en/rest/repos/rules>
- Companion skills: `workflow-scan`, `workflow-fix-safe`, `workflow-pin-actions`.
