---
description: |
  Use when the user wants ONLY safe zizmor auto-fixes applied to
  the maintained repo's workflows. Runs zizmor --fix=safe, layers
  idempotent hardening (top-level permissions, concurrency,
  timeout-minutes, persist-credentials, jq --arg trap audit),
  commits on the current branch. NEVER force-push (R19.7),
  --fix=all, or --no-verify.
  Trigger with phrases like "fix workflow security", "harden
  workflows", or "apply safe workflow fixes".
---

# workflow-fix-safe — apply only conservative auto-fixes

Pipeline: scan → `zizmor --fix=safe` → idempotent hardening
edits → stage by name → commit on current branch. Caller pushes.

## Overview

Conservative auto-fix only. NEVER `--fix=all` or
`--fix=unsafe-only` (those need human review). Runs
`zizmor --fix=safe`, then layers idempotent hardening (top-level
permissions, concurrency, timeout-minutes, persist-credentials),
re-scans for regressions, and commits the diff on the current
branch. Pushing is the caller's responsibility.

## Prerequisites

- `uvx` on PATH; `gh auth token` returns a value.
- Working tree clean (or only `.github/workflows/` already
  staged).
- Current branch is NOT `main` / `master` / `release/*` — skill
  aborts if so (protected-branch guard).

## Instructions

1. Pre-scan baseline via the **workflow-scan** skill.
2. Run `uvx zizmor --gh-token "$(gh auth token)" --fix=safe
   .github/workflows/`.
3. Layer idempotent hardening on each `.github/workflows/*.yml`:
   top-level `permissions: contents: read`, `concurrency:`,
   per-job `timeout-minutes:`, per-checkout
   `persist-credentials: false`, plus a jq `--arg` trap audit
   (rewrite any `${VAR}` inside a double-quoted jq filter to use
   `--arg name "$VAR"`). Use the Read+Edit tools — never sed/awk
   for YAML edits.
4. Post-scan via workflow-scan; abort if new findings appeared.
5. Stage by name (NEVER `git add -A`) and commit:
   `chore(ci): apply safe workflow hardening`.

Full commands: see
[references/instructions.md](references/instructions.md).

## Output

A JSON object with `fixed_by_zizmor`, `hardening_edits`,
`held_back`, `commit`, and `report_md` fields, plus a commit on
the current branch.

## Error Handling

| Error | Action |
|-------|--------|
| Protected branch checked out | Stop, surface "needs a feature branch" |
| Pre-commit hook fails | Stop, surface the failure (no --no-verify) |
| Working tree dirty with non-workflow changes | Stop, ask caller to commit first |
| New zizmor findings in post-scan | Stop, no commit (regression guard) |
| `gh auth token` empty | Stop, surface |

## Examples

```
User: "fix the safe zizmor findings"
→ workflow-scan baseline
→ uvx zizmor --fix=safe .github/workflows/
→ Edit validate.yml + release.yml to add missing permissions
→ workflow-scan post — clean
→ git add .github/workflows/validate.yml .github/workflows/release.yml
→ git commit -m "chore(ci): apply safe workflow hardening"
→ Return: {fixed_by_zizmor: 3, hardening_edits: 2, held_back: 5, ...}
```

## Resources

- zizmor fix-mode reference: <https://docs.zizmor.sh/usage/#auto-fixing>
- Companion skills: `workflow-scan`, `workflow-pin-actions`,
  `workflow-protect-branch`.
- [Full step-by-step instructions](references/instructions.md):
  - Step 1: Protected-branch guard
  - Step 2: Pre-scan baseline
  - Step 3: Run zizmor --fix=safe
  - Step 4: Hardening edits
  - Step 5: Post-scan regression guard
  - Step 6: Stage by name and commit
