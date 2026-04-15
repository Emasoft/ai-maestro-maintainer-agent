---
description: >
  Use when MAINTAINER starts, resumes, or patrol is requested. Polls a
  GitHub repo at a configurable interval (default 5 min), detects new
  issues via ledger, triggers maintainer-triage per issue. Trigger with
  "start patrol".
allowed-tools: "Bash(gh:*), Bash(git:*), Read, Write, Glob, Grep"
---

# Maintainer Patrol — GitHub Issues Polling

Poll the assigned `githubRepo` for new open issues at a configurable interval
(default 5 minutes). Track which issues have already been processed in a
persistent ledger so the same issue is never triaged twice.

## Overview

This skill runs a continuous polling loop against a GitHub repository. It
fetches open issues, compares them against a local ledger of processed issues,
triggers triage for each new unprocessed issue, waits for the configured
interval, and repeats. The ledger persists across hibernation so the patrol
resumes cleanly on wake.

## Poll interval

The default poll interval is **5 minutes (300000 ms)**. Override with the
`MAINTAINER_POLL_INTERVAL_MS` environment variable at agent launch, e.g.
`MAINTAINER_POLL_INTERVAL_MS=60000` for 1 minute, or
`MAINTAINER_POLL_INTERVAL_MS=900000` for 15 minutes.

Floor is **10000 ms (10 s)** to protect against runaway GitHub API calls —
values below the floor are clamped. Ceiling is **3600000 ms (1 hour)** —
values above are clamped.

At the top of every patrol run, compute the interval once:

```bash
POLL_MS="${MAINTAINER_POLL_INTERVAL_MS:-300000}"
[ "$POLL_MS" -lt 10000 ] && POLL_MS=10000
[ "$POLL_MS" -gt 3600000 ] && POLL_MS=3600000
POLL_SECONDS=$(( POLL_MS / 1000 ))
```

Use `$POLL_SECONDS` as the argument to every `sleep` call in the loop.

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
3. Compute `POLL_SECONDS` from `MAINTAINER_POLL_INTERVAL_MS` (see "Poll interval" above). Default 300.
4. Fetch open issues: `gh issue list --repo "$REPO" --state open --limit 50 --json number,title,author,labels,createdAt,body`.
5. Load the ledger JSON and identify issues whose `number` is NOT already in `processed`.
6. For each new issue, invoke the **maintainer-triage** skill passing number, title, author, labels, and body.
7. Record each triaged issue in the ledger with its disposition (`triaged`, `fixed`, `rejected`, `duplicate`, `needs-info`, `manual`).
8. After processing all new issues (or if none), `sleep "$POLL_SECONDS"` then repeat from step 4.

## Output

A continuously running patrol that:
- Detects new issues in real-time (delay bounded by `MAINTAINER_POLL_INTERVAL_MS`, default 5 min)
- Triggers triage automatically for each new issue
- Maintains a persistent ledger so no issue is processed twice
- Reports patrol cycle results to the agent's session

## Error Handling

| Error | Action |
|-------|--------|
| `gh issue list` fails (network, auth) | Log error, `sleep "$POLL_SECONDS"`, retry |
| Triage fails for one issue | Record as `error` in ledger with message, continue to next issue |
| Ledger file corrupted | Recreate as `{"processed":{}}`, re-process all current open issues |
| `githubRepo` not set | Stop patrol, report to user |

## Examples

**Normal patrol cycle (default 5-minute interval):**
```
→ gh issue list returns issues 40, 41, 42
→ Ledger shows 40 already processed
→ Triage issues 41 and 42
→ Record 41: triaged/fix, 42: rejected/unauthorized-feature
→ sleep $POLL_SECONDS   # default 300, overridable via MAINTAINER_POLL_INTERVAL_MS
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
