---
description: >
  Poll a GitHub repository for new issues every 5 minutes. Detects
  unprocessed issues by comparing `gh issue list` output against a local
  ledger. Triggers the maintainer-triage skill for each new issue. Use
  when the MAINTAINER agent starts a session, resumes from hibernation,
  or when the user says "start patrol", "check for issues", "resume
  monitoring", or "begin maintenance loop".
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
---

# Maintainer Patrol — GitHub Issues Polling

Poll the assigned `githubRepo` for new open issues every 5 minutes. Track
which issues have already been processed in a persistent ledger so the
same issue is never triaged twice.

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

## Polling Protocol

### Step 1: Fetch open issues

```bash
gh issue list --repo "$REPO" --state open --limit 50 \
  --json number,title,author,labels,createdAt,body
```

### Step 2: Load the ledger

Read `$LEDGER`. It contains:

```json
{
  "processed": {
    "42": { "status": "fixed", "at": "2026-04-10T21:00:00Z" },
    "43": { "status": "rejected", "at": "2026-04-10T21:05:00Z" }
  }
}
```

### Step 3: Detect new issues

An issue is "new" if its `number` is NOT a key in `processed`. Filter the
fetched list to only new issues.

### Step 4: Triage each new issue

For each new issue, invoke the **maintainer-triage** skill with:
- Issue number, title, author login, labels, body
- The `githubRepo` value

After triage completes (regardless of outcome), record the issue in the
ledger with its disposition (`triaged`, `fixed`, `rejected`, `duplicate`,
`needs-info`, `manual`).

### Step 5: Sleep and repeat

After processing all new issues (or if there are none), wait 5 minutes
(300 seconds), then repeat from Step 1. Use:

```bash
sleep 300
```

## Ledger Location

```
~/.aimaestro/maintainer/<agentId>/processed-issues.json
```

The ledger persists across hibernation. On wake, the patrol resumes and
picks up any issues that arrived while the agent was asleep.

## Error Recovery

- If `gh issue list` fails (network, auth): log the error, wait 5 minutes,
  retry. Do NOT crash the patrol loop.
- If triage fails for one issue: record it as `error` in the ledger with
  the error message, continue to the next issue.
- If the ledger file is corrupted: recreate it as `{"processed":{}}` and
  re-process all currently open issues (safe because triage is idempotent).

## Stopping the Patrol

The patrol loop runs until the session ends. To stop manually:
- The user says "stop patrol" or "pause monitoring"
- The session is terminated or hibernated

On stop, the current ledger state is already saved (written after each
issue). No special shutdown procedure needed.
