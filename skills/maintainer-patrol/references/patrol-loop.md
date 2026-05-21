# Patrol loop reference

## Table of Contents

- [Poll interval and bounds](#poll-interval-and-bounds)
- [Ledger setup](#ledger-setup)
- [Per-cycle loop body](#per-cycle-loop-body)
- [Rate-limit handling](#rate-limit-handling)
- [Stopping the patrol](#stopping-the-patrol)

## Poll interval and bounds

Default poll interval is **5 minutes (300000 ms)**. Override
with the `MAINTAINER_POLL_INTERVAL_MS` env var at agent launch:

```bash
# 1-minute interval (high-traffic repo)
MAINTAINER_POLL_INTERVAL_MS=60000

# 15-minute interval (low-traffic repo)
MAINTAINER_POLL_INTERVAL_MS=900000
```

Bounds: floor **10 s** (10000 ms), ceiling **1 hour**
(3600000 ms). Values outside are clamped.

Compute once at the top of every patrol run:

```bash
POLL_MS="${MAINTAINER_POLL_INTERVAL_MS:-300000}"
[ "$POLL_MS" -lt 10000 ] && POLL_MS=10000
[ "$POLL_MS" -gt 3600000 ] && POLL_MS=3600000
POLL_SECONDS=$(( POLL_MS / 1000 ))
```

Use `$POLL_SECONDS` as the argument to every `sleep` in the loop.

## Ledger setup

```bash
REPO="<githubRepo from agent registry>"
AGENT_ID="<agentId>"
LEDGER_DIR="$HOME/.aimaestro/maintainer/$AGENT_ID"
LEDGER="$LEDGER_DIR/processed-issues.json"
mkdir -p "$LEDGER_DIR"
[ -f "$LEDGER" ] || echo '{"processed":{}}' > "$LEDGER"
```

The ledger persists across hibernation. On resume, replay it
against the current open-issue list to skip already-processed
entries.

## Per-cycle loop body

```bash
gh issue list --repo "$REPO" --state open --limit 50 \
  --json number,title,author,labels,createdAt,body > /tmp/issues-$$.json

# diff against ledger.processed; for each new issue:
#   dispatch maintainer-triage with (number, title, author,
#     labels, body); record returned disposition in ledger
sleep "$POLL_SECONDS"
```

Dispositions recorded in the ledger: `triaged`, `fixed`,
`rejected`, `duplicate`, `needs-info`, `manual`, `error`.

## Rate-limit handling

If the Bash tool prepends a **"GitHub API rate limit"** hint to
a `gh` call (Claude Code 2.1.116+), the loop:

1. Stops iterating on that repo for the current cycle.
2. `sleep "$POLL_SECONDS"` (do NOT retry immediately).
3. Does NOT mark the unprocessed issues in the ledger — they
   re-appear next cycle with a fresh API budget.

Tight retry loops only deepen GitHub's back-off.

## Stopping the patrol

The patrol loop runs until the session ends. To stop manually:

- The user says "stop patrol" or "pause monitoring".
- The session is terminated or hibernated.

The current ledger state is saved after each issue, so no
explicit shutdown procedure is needed.
