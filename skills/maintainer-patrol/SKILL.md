---
description: >
  Use when MAINTAINER agent starts or resumes, or user says "start patrol".
  Polls a GitHub repository every 5 minutes, detects new issues via a
  persistent ledger, triggers maintainer-triage for each.
  Trigger with "start patrol".
allowed-tools: "Bash(gh:*), Bash(git:*), Read, Write, Glob, Grep"
---

# Maintainer Patrol — GitHub Issues Polling

Poll the assigned `githubRepo` for new open issues every 5 minutes. Track
which issues have already been processed in a persistent ledger so the
same issue is never triaged twice.

## Overview

This skill runs a continuous polling loop against a GitHub repository. It
fetches open issues, compares them against a local ledger of processed issues,
triggers triage for each new unprocessed issue, waits 5 minutes, and repeats.
The ledger persists across hibernation so the patrol resumes cleanly on wake.

## Prerequisites

Verify before starting the patrol loop:

1. `gh auth status` succeeds (gh CLI authenticated)
2. The agent's `githubRepo` attribute is set (e.g. `Emasoft/my-project`)
3. The ledger directory exists (create if missing)

```bash
REPO="<githubRepo from agent registry>"
AGENT_ID="<agentId>"
LEDGER_DIR="$HOME/.aimaestro/maintainer/$AGENT_ID"
LEDGER="$LEDGER_DIR/processed-issues.json"
mkdir -p "$LEDGER_DIR"
[ -f "$LEDGER" ] || echo '{"processed":{}}' > "$LEDGER"
```

Copy this checklist and track your progress:
- [ ] gh auth status passes
- [ ] githubRepo attribute set on agent
- [ ] Ledger directory created
- [ ] Patrol loop started

## Instructions

1. Verify prerequisites: `gh auth status` succeeds and `githubRepo` attribute is set on agent.
2. Initialize ledger if missing: `mkdir -p ~/.aimaestro/maintainer/<agentId> && echo '{"processed":{}}' > <ledger>`.
3. Fetch open issues: `gh issue list --repo "$REPO" --state open --limit 50 --json number,title,author,labels,createdAt,body`.
4. Load the ledger JSON and identify issues whose `number` is NOT already in `processed`.
5. For each new issue, invoke the **maintainer-triage** skill passing number, title, author, labels, and body.
6. Record each triaged issue in the ledger with its disposition (`triaged`, `fixed`, `rejected`, `duplicate`, `needs-info`, `manual`).
7. After processing all new issues (or if none), sleep 300 seconds then repeat from step 3.

## Output

A continuously running patrol that:
- Detects new issues in real-time (up to 5-minute delay)
- Triggers triage automatically for each new issue
- Maintains a persistent ledger so no issue is processed twice
- Reports patrol cycle results to the agent's session

## Error Handling

| Error | Action |
|-------|--------|
| `gh issue list` fails (network, auth) | Log error, wait 5 minutes, retry |
| Triage fails for one issue | Record as `error` in ledger with message, continue to next issue |
| Ledger file corrupted | Recreate as `{"processed":{}}`, re-process all current open issues |
| `githubRepo` not set | Stop patrol, report to user |

## Examples

**Normal patrol cycle:**
```
→ gh issue list returns issues 40, 41, 42
→ Ledger shows 40 already processed
→ Triage issues 41 and 42
→ Record 41: triaged/fix, 42: rejected/unauthorized-feature
→ sleep 300
→ Repeat
```

**Resume after hibernation:**
```
→ Wake from hibernation
→ Load ledger (last entry: issue 42)
→ gh issue list returns 43, 44 (new while hibernated)
→ Triage 43 and 44
→ Continue patrol loop
```

## Resources

- GitHub CLI: https://cli.github.com/manual/gh_issue_list
- Ledger location: `~/.aimaestro/maintainer/<agentId>/processed-issues.json`

## Stopping the Patrol

The patrol loop runs until the session ends. To stop manually:
- The user says "stop patrol" or "pause monitoring"
- The session is terminated or hibernated

On stop, the current ledger state is already saved (written after each
issue). No special shutdown procedure needed.
