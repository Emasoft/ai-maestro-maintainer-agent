---
description: >
  Use when maintainer-triage returns `action: fix` or the user says
  "fix issue #N" / "work on issue #N" / "implement issue #N". Runs
  the full clone → branch → understand → edit → test → commit →
  publish → close workflow against the agent's assigned
  `githubRepo`. Reads `$CLAUDE_CODE_SESSION_ID` (Claude Code ≥
  2.1.132) to isolate the per-session workspace under
  `~/.aimaestro/maintainer/<agentId>/<session>/`, so concurrent fix
  sessions never trample each other's clones. Enforces governance
  rules R19.7 (no force-push, no history rewrite, no tag or branch
  deletion without MANAGER approval) and R19.8 (all tests must pass
  before any push). For Python repos, delegates the publish step
  to the repo's own strict `scripts/publish.py` pipeline (uv-based
  release flow with conventional-commit tagging); for other
  ecosystems, mirrors the equivalent build-and-test pipeline with
  `npm`/`cargo`/`go` before push. Closes the GitHub issue with a
  link to the merged commit on success; on test failure, opens a
  comment on the issue with the failure log and does NOT push.
  Do NOT trigger on triage dispositions other than `action: fix`,
  on rejected/duplicate/needs-info dispositions, or on read-only
  inspection queries — those bypass the fix workflow entirely.
# Reviewed 2026-04-15: all 12 tools required for clone→edit→test→publish workflow
allowed-tools: "Bash(git:*), Bash(gh:*), Bash(uv:*), Bash(npm:*), Bash(cargo:*), Bash(go:*), Read, Write, Edit, Grep, Glob, Agent"
---

# Maintainer Fix — Clone, Branch, Fix, Test, Publish

Fix a triaged issue in the maintained repository. The full workflow is:
clone → branch → understand → edit → test → commit → publish → close.

## Overview

This skill handles the complete fix lifecycle for a triaged GitHub issue.
It clones the repository (or updates an existing clone), creates an isolated
feature branch, applies the code fix, runs the test suite, commits with a
conventional message, publishes via the pipeline, and closes the issue with
a commit link.

## Prerequisites

- Issue has been triaged with `action: fix` by the maintainer-triage skill
- `gh` CLI authenticated (`gh auth status`)
- `git` configured with user identity
- The repo's `scripts/publish.py` exists and follows the strict pipeline

Copy this checklist and track your progress:
- [ ] Issue triaged with action=fix
- [ ] gh CLI authenticated
- [ ] Feature branch created
- [ ] Code changes applied
- [ ] Tests passing
- [ ] Workflow audit run (skip if no .github/workflows/ changes)
- [ ] Published via pipeline
- [ ] Issue closed

## Instructions

1. Prepare the workspace: clone or update the repo to `$HOME/agents/<name>/workspace[-<sid8>]`. The optional `-<sid8>` suffix (first 8 chars of `$CLAUDE_CODE_SESSION_ID`, exported by Claude Code ≥ 2.1.132) isolates concurrent MAINTAINER sessions on the same repo. See [Step 1](references/fix-steps.md#step-1-prepare-the-workspace).
2. Create a feature branch: `fix/<issue-number>-<short-slug>`. Branch collisions are detected at push time (R19.7 — never force-push).
3. Read the issue body (`gh issue view`), search related code, plan the fix.
4. Apply the minimum code changes needed; follow existing style conventions.
5. Run the test suite (pytest / npm test / cargo test / go test) — all must pass.
6. If the fix touched anything under `.github/workflows/`, chain the **maintainer-workflow-audit** skill in `audit-and-comment` mode. It runs zizmor against the changed workflows and, if NEW high-severity findings appear on the touched files, comments on the issue with the diff and tags `workflow-security-review-needed`. This step is **non-blocking** — patrol continues even if findings are surfaced. Skip if no workflow files were modified.
7. Commit with a conventional message: `fix: <description> (closes #N)`.
8. Publish via `uv run python scripts/publish.py --patch` or push and create a PR.
9. Comment on the issue with commit hash and new version, then close it.
10. Return to patrol: `git checkout main && git pull origin main`.

For detailed commands, see [Step-by-Step Reference](references/fix-steps.md):
  - Step 1: Prepare the Workspace
  - Step 2: Create a Feature Branch
  - Step 3: Understand the Issue
  - Step 4: Make the Code Changes
  - Step 5: Run Tests
  - Step 6: Workflow audit (conditional — chains **maintainer-workflow-audit**)
  - Step 7: Commit
  - Step 8: Publish
  - Step 9: Close the Issue
  - Step 10: Return to Patrol

## Output

A closed GitHub issue with a comment linking to the fix commit and new version,
plus a merged (or PR-created) branch with the code change.

## Error Handling

| Error | Action |
|-------|--------|
| Tests fail after 3 attempts | Label `fix-failed`, comment on issue, return error to patrol |
| Publish pipeline fails | Comment on issue, keep branch for manual review |
| `gh` not authenticated | Stop, report to main agent |
| Push rejected | Investigate reason, do NOT force-push |

## Examples

**Fix a verified bug:**
```
User: "fix issue #42"
→ Clone/update repo, create branch fix/42-null-pointer
→ Edit the offending code
→ All tests pass
→ git commit -m "fix: handle null pointer (closes #42)"
→ uv run python scripts/publish.py --patch
→ gh issue close 42 with commit link
```

## Resources

- [Step-by-Step Reference](references/fix-steps.md)
  - Step 1: Prepare the Workspace
  - Step 2: Create a Feature Branch
  - Step 3: Understand the Issue
  - Step 4: Make the Code Changes
  - Step 5: Run Tests
  - Step 6: Commit
  - Step 7: Publish
  - Step 8: Close the Issue
  - Step 9: Return to Patrol
- Conventional Commits: https://www.conventionalcommits.org/
- GitHub CLI: https://cli.github.com/manual/

## Constraints

- No force-push — ever. If push is rejected, investigate why (R19.7).
- No history rewrite, no tag/branch deletion without MANAGER approval.
- All tests must pass before any push (R19.8).
- Honor pre-push hooks — if a hook exists, it must pass.
- One fix per issue — never bundle multiple fixes in one commit.
