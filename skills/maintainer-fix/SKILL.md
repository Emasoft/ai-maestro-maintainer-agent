---
description: |
  Use when maintainer-triage returns action=fix or the user wants
  to fix, work on, or implement a GitHub issue on the maintained
  repo. Runs the full clone, branch, edit, test, workflow audit,
  approval gate, commit, publish, and close lifecycle against the
  agent's assigned githubRepo. Reads CLAUDE_CODE_SESSION_ID
  (Claude Code 2.1.132+) to isolate the per-session workspace
  under ~/.aimaestro/maintainer/AGENT_ID/SESSION/. Enforces
  governance R19.7 (no force-push, no history rewrite, no
  tag/branch deletion without MANAGER) and R19.8 (all tests pass
  before push). Calls maintainer-approval-gate before every
  commit — if the planned diff touches a protected path, the fix
  halts pending approve-protected-edit from the authorized user.
  For Python repos publishes via scripts/publish.py; mirrors the
  build-and-test flow for npm / cargo / go. Closes the issue with
  a commit link on success; on failure comments the log and does
  NOT push. Do NOT trigger on triage dispositions other than fix,
  on rejected/duplicate/needs-info, or on read-only queries.
  Trigger with phrases like "fix issue #N", "work on issue #N",
  or "implement issue #N".
---

# maintainer-fix — clone → branch → fix → test → publish → close

## Overview

Handles the complete fix lifecycle: clone → branch → edit → test
→ workflow audit (if touched) → approval gate → commit → publish
→ close. The approval-gate step refuses to commit any diff that
touches a protected path without explicit maintainer approval.

## Prerequisites

- Issue triaged with `action: fix` by `maintainer-triage`.
- `gh` CLI authenticated; `git` configured with user identity.
- The repo's `scripts/publish.py` exists (or an equivalent
  ecosystem pipeline: npm / cargo / go).

Copy this checklist and track your progress (per-fix):

- [ ] Issue triaged with action=fix
- [ ] Feature branch created
- [ ] Code changes applied; tests passing
- [ ] Workflow audit (if `.github/workflows/` touched)
- [ ] Approval gate cleared (no protected-path hits OR approved)
- [ ] Published via pipeline; issue closed

## Instructions

1. Prepare the workspace at
   `$HOME/agents/<name>/workspace[-<sid8>]` (per-session via
   `$CLAUDE_CODE_SESSION_ID`).
2. Create a feature branch `fix/<issue-number>-<slug>`.
3. Read the issue body, search related code, plan the fix.
4. Apply the minimum changes; match existing style.
5. Run the test suite — ALL tests must pass (R19.8).
6. If `.github/workflows/` was touched, chain **workflow-scan**;
   it auto-creates `workflow-security-review-needed` via
   `gh label create --force` on regression. Non-blocking.
7. **Approval gate** — invoke **maintainer-approval-gate** CHECK.
   If the planned diff hits any protected path, the gate posts
   an approval-request comment and returns `needs-approval`.
   HALT — do NOT commit. Next cycle, the gate's VERIFY mode
   resumes the fix only if `$AUTHORIZED_USER` replied with
   `approve-protected-edit`.
8. Commit: `fix: <description> (closes #N)`.
9. Publish: `uv run python scripts/publish.py --patch` (or the
   repo's pipeline equivalent).
10. Comment on the issue with the commit SHA + new version, then
    close it.
11. Return to patrol: `git checkout main && git pull origin main`.

Full step-by-step commands are in
[references/fix-steps.md](references/fix-steps.md).

## Output

A closed issue with a commit-link comment and the new version,
plus a merged (or PR-created) branch with the code change.

## Error Handling

| Error | Action |
|-------|--------|
| Tests fail after 3 attempts | Label `fix-failed`, comment with log, return error |
| Publish pipeline fails | Comment on issue, keep branch for manual review |
| `gh` not authenticated | Stop, report to main agent |
| Push rejected | Investigate (e.g. needs rebase) — NEVER force-push |
| `.github/workflows/` audit surfaces NEW high finding | Comment on issue, tag `workflow-security-review-needed`, continue |
| Approval-gate returns `needs-approval` | HALT fix; do NOT commit; resume next cycle if authorized user replies `approve-protected-edit` |

## Examples

```
"fix #42" → clone, branch, edit, tests pass, approval-gate
noop, commit, publish, close
```

```
"fix #58" (touches .github/workflows/) → tests pass →
approval-gate CHECK requests approve-protected-edit → HALT;
next cycle VERIFY finds approval → RESUME → commit, publish
```

## Constraints

- NEVER force-push (R19.7); never rewrite history.
- ALL tests pass before push (R19.8); NEVER `--no-verify`.
- One fix per issue — never bundle multiple fixes.

## Resources

- [Step-by-step reference](references/fix-steps.md): workspace,
  branch, code changes, tests, workflow-scan, approval-gate,
  commit, publish, close, return to patrol
- Companion: `maintainer-approval-gate`, `maintainer-guardian`,
  `workflow-scan`, `workflow-fix-safe`.
- Conventional Commits: <https://www.conventionalcommits.org/>
