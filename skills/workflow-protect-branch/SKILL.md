---
description: |
  Use when the user wants to QUERY or APPLY the maintained repo's
  default-branch + release-tag rulesets via the GitHub Rulesets API.
  SHOW = read-only fetch + cache. APPLY = auto-detect CI job names,
  POST/PUT THREE rulesets — no-bypass history-protect, admin-bypass
  PR-and-checks, and no-bypass tag-protect. Idempotent.
  Trigger with phrases like "protect main branch", "apply branch
  rules" (apply), or "show branch rules" (show).
---

# workflow-protect-branch — idempotent branch + tag rulesets

Applies a deterministic THREE-ruleset baseline to the maintained repo
via the GitHub Rulesets REST API. Idempotent — re-running converges to
the same state.

## Overview

Two modes: **SHOW** (read-only — fetches + caches the deployed
rulesets; run by the main agent at startup and after each push) and
**APPLY** (auto-detects status check names, then POSTs/PUTs **three**
rulesets):

| Ruleset | `target` | Rules | `bypass_actors` |
|---|---|---|---|
| `baseline-history-protect` | branch | `deletion`, `non_fast_forward`, `required_linear_history` | `[]` (nobody, incl. admin) |
| `baseline-pr-and-checks` | branch | `pull_request`, `required_status_checks` (strict) | admin RepositoryRole, `always` |
| `baseline-tag-protect` | tag | `deletion`, `update` (scope `refs/tags/v*.*.*`) | `[]` (nobody) |

The two branch rulesets are split (not combined) because `bypass_actors`
applies to the WHOLE ruleset, never per-rule: a single combined ruleset
with an admin bypass would also let admin force-push/delete. The split
lets `publish.py`'s direct push bypass the PR + checks gate (checks are
un-greenable before a push → `GH013`) while force-push, deletion, and
non-linear history stay blocked for all. The tag ruleset is independent
(`target: tag`): `[deletion, update]` makes published `v*.*.*` tags
immutable (no move, no delete) while leaving tag *creation* open, so
publish.py still cuts releases — no bypass actor needed.

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
3. Build ALL THREE ruleset JSON bodies in tmpfiles (no inline `${{ }}`):
   no-bypass history-protect, admin-bypass PR-and-checks, no-bypass
   tag-protect.
4. For EACH ruleset, POST or PUT to `/repos/$REPO/rulesets`
   depending on whether one of that name already exists.
5. Verify each landed with the ratified rules + bypass shape; on the
   first apply, readback-pin the tag ruleset's `ref_name.include`.
6. Run SHOW again to refresh the cache + emit a diff.

Full commands + all three JSON bodies: see Resources.

## Output

- **SHOW**: `{mode, ruleset_count, rulesets, cache_path}` + refreshed
  cache at `$AGENT_DIR/.aimaestro/state/branch-rules.json` (the full
  ruleset array — covers all three).
- **APPLY**: `{mode, history_ruleset:{id,action},
  checks_ruleset:{id,action}, tag_ruleset:{id,action},
  required_checks, report, cache_path}`.

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
→ APPLY → detect jobs → POST/PUT history (no bypass) + checks (admin
  bypass) + tag-protect (no bypass) → verify → SHOW refresh
```

## Scope

ONLY queries (SHOW) or applies (APPLY) the three canonical baseline
rulesets (`baseline-history-protect` + `baseline-pr-and-checks` +
`baseline-tag-protect`) via the GitHub Rulesets REST API. Does NOT:

- Manage non-default branches — both branch rulesets target
  `~DEFAULT_BRANCH`; the tag ruleset targets `refs/tags/v*.*.*`.
- Touch environment- or org-level rulesets — repo-level only.
- Push, commit, or modify the entrusted repo's working tree.
- Manage rules beyond the ratified baseline — `deletion`,
  `non_fast_forward`, `required_linear_history` (history),
  `pull_request` + `required_status_checks` (pr-and-checks),
  `deletion` + `update` (tag-protect).
- Add bypass actors beyond admin RepositoryRole on the pr-and-checks
  ruleset; the history + tag rulesets stay bypass-less for all.

Idempotent — APPLY converges to the same three-ruleset state.

## Single-writer ownership (ruleset-config domain)

The **MAINTAINER is the single authoritative writer of the ruleset-config
domain** (branch + tag protection) on every repo it guards (PRRD S9):

- **INTEGRATOR** does not write rulesets directly; it coordinates any ruleset
  change through MANAGER, who relays to the MAINTAINER.
- **ai-maestro-janitor** auto-enforces the same ratified baseline as a safety
  net. On a repo where both would apply it, the **janitor yields to the
  MAINTAINER's explicit APPLY** — both emit the byte-identical ratified triple,
  so the converged state is identical regardless of who wins the race; the
  janitor's job is to catch drift when the maintainer is absent, not to
  contend for the write.
- A genuine *deviation* from the ratified baseline is never a single-writer
  decision: it is Tier-2 and needs MANAGER approval BEFORE apply, by whoever
  raises it.

## Resources

- Rulesets API: <https://docs.github.com/en/rest/repos/rules>
- Companion: `workflow-scan`, `workflow-fix-safe`,
  `workflow-pin-actions`.
- [Full step-by-step instructions](references/instructions.md):
  - Why two rulesets, not one
  - The third ruleset: tag protection
  - Step 0: Decide mode (SHOW vs APPLY)
  - Step 1: Verify admin permission (APPLY only)
  - Step 2: Auto-detect required checks (APPLY only)
  - Step 3: Build the three ruleset JSON bodies (APPLY only)
  - Step 4: Discover all existing rulesets
  - Step 5: POST or PUT each ruleset (APPLY only)
  - Step 6: Verify all present post-apply
  - Step 6.5: Delete orphaned legacy rulesets (APPLY only)
  - Step 7: Write report + refresh agent cache
