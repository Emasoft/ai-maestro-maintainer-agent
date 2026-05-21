---
description: |
  Use when maintainer-triage returns action=fix or the user wants
  to fix, work on, or implement a GitHub issue on the maintained
  repo. Runs the full clone, branch, edit, test, optional workflow
  audit, commit, publish, and close workflow against the agent's
  assigned githubRepo. Reads CLAUDE_CODE_SESSION_ID (Claude Code
  2.1.132+) to isolate the per-session workspace under
  ~/.aimaestro/maintainer/AGENT_ID/SESSION/. Enforces governance
  R19.7 (no force-push, no history rewrite, no tag or branch
  deletion without MANAGER approval) and R19.8 (all tests must
  pass before any push). For Python repos delegates the publish
  step to the repo's strict scripts/publish.py uv pipeline; for
  other ecosystems mirrors the equivalent build-and-test flow with
  npm, cargo, or go. Closes the issue with a link to the merged
  commit on success; on test failure comments the log and does NOT
  push. Do NOT trigger on triage dispositions other than fix, on
  rejected, duplicate, or needs-info dispositions, or on read-only
  inspection queries — those bypass the fix workflow entirely.
  Trigger with phrases like "fix issue #N", "work on issue #N",
  or "implement issue #N".
---

# maintainer-fix — clone → branch → fix → test → publish → close

## Overview

Handles the complete fix lifecycle for a triaged GitHub issue.
Clones (or updates) the maintained repo into a per-session
workspace, creates an isolated feature branch, applies the code
fix, runs the test suite, optionally audits any touched
workflows, commits with a conventional message, publishes via
the repo's pipeline, and closes the issue with a commit link.

## Prerequisites

- Issue triaged with `action: fix` by `maintainer-triage`.
- `gh` CLI authenticated; `git` configured with user identity.
- The repo's `scripts/publish.py` exists (or an equivalent
  ecosystem pipeline: npm / cargo / go).

Copy this checklist and track your progress (per-fix):

- [ ] Issue triaged with action=fix
- [ ] Feature branch created
- [ ] Code changes applied
- [ ] Tests passing
- [ ] Workflow audit run (only if `.github/workflows/` touched)
- [ ] Published via pipeline
- [ ] Issue closed

## Instructions

1. Prepare the workspace at
   `$HOME/agents/<name>/workspace[-<sid8>]` (per-session via
   `$CLAUDE_CODE_SESSION_ID`).
2. Create a feature branch `fix/<issue-number>-<slug>`.
3. Read the issue body, search related code, plan the fix.
4. Apply the minimum changes; match existing style.
5. Run the test suite — ALL tests must pass (R19.8).
6. If `.github/workflows/` was touched, chain the
   **workflow-scan** skill; it auto-creates the
   `workflow-security-review-needed` label via
   `gh label create --force` if it needs to flag a regression.
   Non-blocking.
7. Commit: `fix: <description> (closes #N)`.
8. Publish: `uv run python scripts/publish.py --patch` (or the
   repo's pipeline equivalent).
9. Comment on the issue with the commit SHA + new version, then
   close it.
10. Return to patrol: `git checkout main && git pull origin main`.

Full step-by-step commands are in
[references/fix-steps.md](references/fix-steps.md).

## Output

A closed GitHub issue with a comment linking to the fix commit
and the new version, plus a merged (or PR-created) branch with
the code change.

## Error Handling

| Error | Action |
|-------|--------|
| Tests fail after 3 attempts | Label `fix-failed`, comment with log, return error |
| Publish pipeline fails | Comment on issue, keep branch for manual review |
| `gh` not authenticated | Stop, report to main agent |
| Push rejected | Investigate (e.g. needs rebase) — NEVER force-push |
| `.github/workflows/` audit surfaces NEW high finding | Comment on issue, tag `workflow-security-review-needed`, continue |

## Examples

Fix a verified bug:

```
User: "fix issue #42"
→ Clone/update repo, create branch fix/42-null-pointer
→ Edit the offending code
→ All tests pass
→ git commit -m "fix: handle null pointer (closes #42)"
→ uv run python scripts/publish.py --patch
→ gh issue close 42 with commit link
```

## Constraints

- NEVER force-push (R19.7).
- NEVER rewrite history or delete tags/branches without MANAGER.
- ALL tests must pass before push (R19.8).
- Pre-push hooks must pass — NEVER `--no-verify`.
- One fix per issue — never bundle multiple fixes in one commit.

## Resources

- [Step-by-step reference](references/fix-steps.md):
  - Step 1: Prepare the Workspace
  - Step 2: Create a Feature Branch
  - Step 3: Understand the Issue
  - Step 4: Make the Code Changes
  - Step 5: Run Tests
  - Step 6: Commit
  - Step 7: Publish
  - Step 8: Close the Issue
  - Step 9: Return to Patrol
- Conventional Commits: <https://www.conventionalcommits.org/>
- GitHub CLI: <https://cli.github.com/manual/>
