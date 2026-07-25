---
description: |
  Use when MAINTAINER starts, resumes, or the user requests issue
  monitoring. Polls the assigned githubRepo (default 300s, bounded
  10s..3600s via MAINTAINER_POLL_INTERVAL_MS), tracks processed
  issues in the per-agent ledger, dispatches maintainer-triage
  per new issue. Honours the GitHub rate-limit hint.
  Trigger with phrases like "start patrol", "begin maintenance
  loop", or "watch for new issues".
---

# maintainer-patrol — GitHub issues polling loop

## Overview

Runs a continuous polling loop against the agent's assigned
GitHub repository. Fetches open issues, diffs against a local
ledger, dispatches `maintainer-triage` for each new issue,
records the disposition, sleeps the configured interval, and
repeats. The ledger persists across hibernation.

## Prerequisites

- `gh auth status` succeeds.
- Agent's `githubRepo` attribute is set
  (e.g. `Emasoft/my-project`).
- Ledger directory exists at
  `$AGENT_DIR/.aimaestro/state/` (auto-created on first
  run).

Copy this checklist and track your progress (pre-flight):

- [ ] gh auth status passes
- [ ] githubRepo attribute set on agent
- [ ] Ledger directory created
- [ ] Patrol loop started

## Instructions

1. Verify prerequisites (`gh auth status`, `githubRepo` set).
2. Initialize ledger at
   `$AGENT_DIR/.aimaestro/state/processed-issues.json`
   if missing. If
   `$AGENT_DIR/.aimaestro/state/guardian-baseline.json`
   is also missing, invoke **maintainer-guardian** in baseline
   mode first (the SessionStart hook normally does this, but
   patrol is the backstop).
3. Compute `$POLL_SECONDS` from `MAINTAINER_POLL_INTERVAL_MS`
   (default 300, floor 10, ceiling 3600).
4. **Pre-cycle Guardian scan** — invoke **maintainer-guardian**
   in scan mode. If it returns a T5 (secret leak) hit, STOP the
   patrol and alert the authorized user. For other critical
   deltas, file/auto-fix per the routing table and SKIP the issue
   loop this cycle (let the routed work land first).
5. Fetch open issues: `gh issue list --repo "$REPO" --state open
   --limit 50 --json number,title,author,labels,createdAt,body`.
6. Identify issues whose `number` is NOT in `ledger.processed`.
7. For each new issue, invoke **maintainer-triage** with number,
   title, author, labels, body. Record returned disposition.
8. **Post-cycle refresh** — chain **workflow-protect-branch** SHOW
   to refresh the branch-rules cache; the next Guardian scan diffs
   against the refreshed state.
9. `sleep "$POLL_SECONDS"`; repeat from step 4.

Detailed reference: [patrol-loop.md](references/patrol-loop.md):
- Poll interval and bounds
- Ledger setup
- Guardian pre/post hooks
- Per-cycle loop body
- Rate-limit handling
- Stopping the patrol

## Output

A continuously running patrol that detects new issues within
`$POLL_SECONDS` of their creation, dispatches triage for each,
maintains a per-agent ledger, and reports per-cycle results to
the agent session.

## Error Handling

| Error | Action |
|-------|--------|
| `gh issue list` fails (net / auth) | Log error, `sleep $POLL_SECONDS`, retry |
| `gh`-tool output reports "GitHub API rate limit" hint | Stop iterating, `sleep $POLL_SECONDS`, do NOT retry inside the same cycle |
| Triage fails for one issue | Record as `error` in ledger, continue to next |
| Ledger file corrupted | Recreate as `{"processed":{}}`, re-process all current open issues |
| `githubRepo` not set | Stop patrol, report to user |

## Examples

Normal cycle (5-minute default):

```
→ gh issue list returns issues 40, 41, 42
→ Ledger shows 40 already processed
→ Triage issues 41 and 42
→ Record 41: triaged/fix, 42: rejected/unauthorized-feature
→ sleep 300
→ Repeat
```

Resume after hibernation:

```
→ Wake from hibernation
→ Drain the AMP inbox FIRST — a mandate may have landed while asleep,
  and it outranks the issue list (persona: AMP discipline)
→ Load ledger (last entry: issue 42)
→ gh issue list returns 43, 44 (new while hibernated)
→ Triage 43 and 44
→ Continue patrol loop
```

## Scope

ONLY runs the patrol loop: pre-cycle Guardian → fetch open issues
→ dispatch triage → post-cycle workflow-protect-branch SHOW → sleep.
Does NOT:

- Triage issues itself — that's `maintainer-triage`'s job.
- Fix issues itself — triage's `action: fix` disposition routes
  to `maintainer-fix` separately.
- Process closed or already-ledgered issues.
- Override the configured interval at runtime — the bounds are
  enforced once at startup; mid-run mutation requires a restart.

Idempotent across hibernation: the ledger persists across session
boundaries and only NEW issues are re-triaged on resume.

## Resources

- [Patrol loop reference](references/patrol-loop.md):
  - Poll interval and bounds
  - Ledger setup
  - Guardian pre/post hooks
  - Per-cycle loop body
  - Rate-limit handling
  - Stopping the patrol
- [Patrol handoff template](references/messages/handoff.md) — the R15.7
  message shape for passing patrol state to a successor session
  (hibernation, host migration), including the three things a successor
  cannot recover from the files alone.
- GitHub CLI: <https://cli.github.com/manual/gh_issue_list>
- Ledger location: `$AGENT_DIR/.aimaestro/state/processed-issues.json`
