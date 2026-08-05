---
description: |
  Use when maintainer-pr-triage returns any disposition other than
  reject-adversarial, or the user asks for a structured AI-assisted
  review of a pull request. Walks a 7-category checklist (workflow
  changes, protected paths, lifecycle scripts, lockfile churn, test
  coverage, diff size, untrusted-action additions), posts ONE
  structured review comment summarising every flag, and explicitly
  states that final approval requires a human reviewer. Does NOT
  auto-approve and NEVER calls `gh pr review --approve`.
  Trigger with phrases like "review PR #N", "AI-assisted review of
  pull request #N", "audit PR #N diff", or "check PR #N for
  reviewer flags".
---

# maintainer-pr-review — structured AI-assisted PR review

## Overview

Walks a fixed 7-category checklist over a PR's diff and posts ONE
structured review comment summarising every flag. Designed to
complement, not replace, a human reviewer. The skill:

- Reuses `workflow-scan` when `.github/workflows/` is touched
  (only step that mutates state, by way of `gh label create
  --force`).
- Reads the canonical protected-paths list from
  `maintainer-approval-gate/references/protected-paths.md`.
- Cross-references new lifecycle scripts (`preinstall`,
  `postinstall`, `prepare`) and new build-system hooks.
- Flags lockfile churn that introduces packages younger than 7
  days (typo-squat early-warning).
- Counts added prod code vs added test code; flags imbalance.
- Flags PRs larger than 500 added lines.
- Flags new `uses: <action>@<tag>` entries in workflow files.

The comment is template-driven (heredoc body) so PR content is
never injected into a shell expansion.

## Prerequisites

- `gh auth status` succeeds.
- `githubRepo` set on the calling agent.
- PR number passed by `maintainer-pr-triage` (or directly by the
  user).
- For category 1 (workflow changes): `uvx` + `actionlint` on
  PATH (same prereqs as `workflow-scan`).

Copy this checklist and track your progress (per-PR):

- [ ] PR diff fetched (full patch + per-file JSON)
- [ ] Cat 1: workflow changes scanned (if touched)
- [ ] Cat 2: protected paths enumerated
- [ ] Cat 3: lifecycle scripts diffed
- [ ] Cat 4: lockfile churn checked
- [ ] Cat 5: test/prod balance computed
- [ ] Cat 6: diff size measured
- [ ] Cat 7: new `uses:` actions listed
- [ ] Single review comment posted

## Instructions

Each category emits zero or more **flags**. The skill collects
flags into a single ordered list, renders them into the comment
template (see Resources for the file path and complete TOC), and
posts the comment. Every category has an early-exit on "not
applicable".

1. **Fetch the patch + file list** once:
   ```bash
   gh pr diff "$PR" --repo "$REPO" > /tmp/pr-$PR.diff
   gh api repos/$REPO/pulls/$PR/files --paginate > /tmp/pr-$PR-files.json
   ```
2. **Cat 1 — workflow changes** (touched
   `.github/workflows/`?): chain `workflow-scan`. Compare its
   `highest_severity` against the baseline from the prior scan
   on `main`. Any NEW high-severity finding becomes a flag.
3. **Cat 2 — protected-path edits**: load the canonical list,
   intersect with touched files, emit one flag per hit asking
   "why was this changed?". Do NOT auto-approve.
4. **Cat 3 — lifecycle-script additions**: parse the patch for
   new `preinstall` / `postinstall` / `prepare` keys in
   `package.json`, and new `[build-system]` / `[tool.poetry]`
   script-entry-points in `pyproject.toml`.
5. **Cat 4 — lockfile churn**: detect any lockfile that grew
   (`package-lock.json`, `pnpm-lock.yaml`, `uv.lock`, `Cargo.lock`,
   `go.sum`); for each new package version, query the registry's
   release date; if introduced < 7 days ago, flag.
6. **Cat 5 — test/prod balance**: count added LOC under common
   prod paths vs common test paths. Flag if prod > 0 AND test = 0.
   Flag any DELETED test files.
7. **Cat 6 — diff size**: if `additions > 500`, flag with a
   recommendation to split.
8. **Cat 7 — untrusted-action additions**: grep the patch for
   added lines matching `uses: <new-action>@<tag>` in workflow
   files. Existing actions (already pinned in `main`) are
   skipped — Dependabot covers updates.
9. **Render & post** the comment via heredoc (see the comment
   template in Resources for the file path and complete TOC).
10. **NEVER** call `gh pr review --approve`. Optionally call
    `gh pr review --comment --body-file <file>` to attach as a
    formal review-comment rather than a plain PR comment.

Per-category commands + grep recipes live in the review-checklist
reference (see Resources for the file path and complete TOC).

## Output

A single JSON object plus one posted PR comment.

```json
{
  "pr": 42,
  "comment_url": "<url>",
  "flags": [
    {"category": 1, "severity": "high", "label": "workflow.zizmor.new-high",  "detail": "…"},
    {"category": 3, "severity": "high", "label": "lifecycle.preinstall.added", "detail": "…"},
    {"category": 6, "severity": "medium", "label": "size.over-500", "detail": "…"}
  ],
  "flag_count": 3,
  "highest_severity": "high",
  "ai_assisted_only": true
}
```

The `ai_assisted_only` field is always `true` — it reminds the
caller (and the patrol ledger) that this skill never approves
on its own.

## Error Handling

| Error | Action |
|-------|--------|
| `gh pr diff` fails | Stop, surface to caller |
| `workflow-scan` returns error disposition | Record as a flag with `severity: "high"`, continue other categories |
| Registry lookup for lockfile age fails | Skip Cat 4 for that package; record `severity: "low"` flag noting the gap |
| `gh pr comment` fails | Save the comment body to `$MAIN_ROOT/reports/maintainer-pr-review/<ts>-pr-<N>-comment.md` and surface the path to caller |
| `gh pr review --approve` was about to be called | HARD ABORT — log a security event; this skill MUST NOT approve |
| Rate-limit hint | Save partial flags to a report under `reports/maintainer-pr-review/`, return `rate-limit deferred` |

## Examples

Clean PR — no flags:

```
PR #42 by <repo-owner>, +12 / -3 in src/utils/, tests included
→ 0 flags
→ comment: "AI-assisted review — no automated flags. Final
   approval requires a human reviewer."
```

Multi-category red:

```
PR #58 by <outside-contributor>, +600 lines, adds postinstall in package.json,
touches .github/workflows/, no tests
→ flags: workflow.zizmor.new-high (Cat 1),
         lifecycle.postinstall.added (Cat 3),
         tests.prod-without-test (Cat 5),
         size.over-500 (Cat 6)
→ post single structured comment
→ NEVER auto-approve
```

## Scope

Posts ONE comment per PR per review invocation. Does NOT push,
merge, or approve. Does NOT modify the PR branch. The only
mutation outside the comment is `gh label create --force
workflow-security-review-needed` when category 1 surfaces a new
high finding (inherited from `workflow-scan`).

## Resources

- [Review checklist (7 categories with commands)](references/review-checklist.md):
  - Cat 1 — Workflow changes
  - Cat 2 — Protected-path edits
  - Cat 3 — Lifecycle-script additions
  - Cat 4 — Lockfile churn
  - Cat 5 — Test/prod balance
  - Cat 6 — Diff size
  - Cat 7 — Untrusted-action additions
  - Shared diff helpers
- [Comment template](references/comment-template.md):
  - Header
  - Per-flag block
  - Footer
  - Heredoc invocation
  - Markdown invariants
  - Empty-flags variant
- Companion: `maintainer-pr-triage` (upstream stage),
  `workflow-scan` (Cat 1 implementation),
  `maintainer-approval-gate` (Cat 2 protected-paths source).
