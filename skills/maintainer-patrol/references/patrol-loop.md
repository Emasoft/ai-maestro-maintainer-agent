# Patrol loop reference

## Table of Contents

- [Poll interval and bounds](#poll-interval-and-bounds)
- [Ledger setup](#ledger-setup)
- [Guardian pre/post hooks](#guardian-prepost-hooks)
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

All per-agent state lives **inside the agent's working directory**
— never under `$HOME` — so AI Maestro's backup snapshots capture
it and host-to-host migration (export from laptop, re-import on
desktop) carries the ledger with the agent.

The agent working directory is resolved via this fallback chain:

```bash
# 1. $AIMAESTRO_AGENT_DIR is the canonical AI Maestro env var
#    (preferred when AI Maestro is the runtime, see
#    https://github.com/Emasoft/ai-maestro/issues/32).
# 2. $CLAUDE_PROJECT_DIR is Claude Code's standard project dir
#    (current actual env var until AI Maestro ships its own).
# 3. $PWD is the last-resort fallback for unmanaged runs.
AGENT_DIR="${AIMAESTRO_AGENT_DIR:-${CLAUDE_PROJECT_DIR:-$PWD}}"
STATE_DIR="$AGENT_DIR/.aimaestro/state"
mkdir -p "$STATE_DIR"
```

Then:

```bash
REPO="<githubRepo from agent registry>"
LEDGER="$STATE_DIR/processed-issues.json"
[ -f "$LEDGER" ] || echo '{"processed":{}}' > "$LEDGER"
```

The ledger persists across hibernation. On resume, replay it
against the current open-issue list to skip already-processed
entries.

> **Never** write the ledger under `$HOME` (`~/.aimaestro/...`,
> `$HOME/agents/...`). Host-global paths are invisible to AI
> Maestro backups, which means after a restore the agent boots
> into a fresh ledger and re-processes already-handled issues.
> The same trap breaks agent migration between hosts.

## Guardian pre/post hooks

Each patrol cycle is bracketed by Guardian-Mode work that turns
the maintainer from a reactive issue-fixer into a proactive
guardian of the repo.

**Pre-cycle (before `gh issue list`):**

```bash
# 1. Backstop the SessionStart hook — make sure the baseline exists.
BASELINE="$STATE_DIR/guardian-baseline.json"
if [ ! -f "$BASELINE" ]; then
  # Invoke maintainer-guardian in baseline mode.
  # ...
fi

# 2. Run the per-cycle scan and read its disposition.
# Invoke maintainer-guardian in scan mode → ./guardian-state.json
# Disposition shape: {delta: {...}, routes: [...]}
```

If the scan returns a **T5 hit** (secret-leak marker in recent
commits) the loop STOPS and the authorized user is alerted — no
issue-loop work happens this cycle.

If the scan returns critical **T1/T2/T3/T4** deltas, the routed
work (auto-fix PR, tracking issue, alert) is launched and the
patrol SKIPS the issue loop this cycle to let the routed work
land first. The skip is recorded so the issue list is picked up
again next cycle without back-pressure on GitHub.

**Post-cycle (after the issue loop):**

```bash
# Refresh the branch-rules cache so the next Guardian scan diffs
# against the live state of the repo's ruleset.
# Invoke workflow-protect-branch in SHOW mode.
```

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
`rejected`, `duplicate`, `needs-info`, `manual`, `error`,
`guardian-skip` (cycle was pre-empted by a Guardian critical
finding).

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
