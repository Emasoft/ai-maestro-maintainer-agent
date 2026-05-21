---
description: |
  Use when the user wants to apply ONLY safe auto-fixes to the
  maintained repo's GitHub Actions workflows — never destructive,
  never unsafe. Runs zizmor in safe-fix mode (the conservative
  default, no human review needed), then layers idempotent
  hardening edits: top-level permissions: contents: read,
  concurrency: { group, cancel-in-progress }, timeout-minutes
  on every job, persist-credentials: false on every checkout.
  Commits the resulting diff DIRECTLY on the current git branch
  with a conventional message. NEVER force-pushes (governance
  R19.7). NEVER pushes — pushing is the caller's responsibility.
  NEVER uses --fix=all or --fix=unsafe-only (those need human
  review and a different skill). Assumes secrets and the gh auth
  token are exported by AI Maestro on the host; reads the token
  via $(gh auth token). Honours pre-commit hooks — if a hook
  fails the skill stops and surfaces the failure rather than
  bypassing with --no-verify. Skips silently when
  .github/workflows/ is missing or when the working tree is dirty
  with non-workflow changes (caller should commit those first).
  Do NOT trigger on read-only audit requests (use workflow-scan)
  or on SHA-pinning requests (use workflow-pin-actions). Trigger
  with phrases like "fix workflow security", "harden workflows",
  "apply safe workflow fixes", or "auto-fix workflow findings".
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
   `persist-credentials: false`. Use the Read+Edit tools — never
   sed/awk for YAML edits.
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

- zizmor fix modes: <https://docs.zizmor.sh/usage/#auto-fixing>
- Companion skills: `workflow-scan`, `workflow-pin-actions`,
  `workflow-protect-branch`.
- [Full step-by-step instructions](references/instructions.md)
