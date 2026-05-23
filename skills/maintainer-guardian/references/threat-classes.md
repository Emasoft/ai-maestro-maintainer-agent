# Guardian threat classes — T1 through T5

The Guardian skill detects 5 classes of supply-chain threat. Each
class has a detector (read-only), a delta-vs-baseline check, and a
route (what the Guardian does when a delta is positive).

## Table of Contents

- [T1 — Workflow drift](#t1--workflow-drift)
- [T2 — Stale SHA pins](#t2--stale-sha-pins)
- [T3 — Branch-rule drift](#t3--branch-rule-drift)
- [T4 — Protected-path activity](#t4--protected-path-activity)
- [T5 — Secret-leak markers](#t5--secret-leak-markers)
- [Routing table](#routing-table)
- [Atomic write pattern](#atomic-write-pattern)

---

## T1 — Workflow drift

**Detection.** Chain the `workflow-scan` skill (read-only). It runs
`uvx zizmor` + `actionlint` on `.github/workflows/` and writes
report under `$MAIN_ROOT/reports/workflow-scan/`. Parse the report
into a per-severity finding count `{critical, high, medium, low}`.

**Baseline shape:**

```json
{
  "t1": {
    "zizmor": {"critical": 0, "high": 0, "medium": 0, "low": 0},
    "actionlint": {"errors": 0}
  }
}
```

**Delta.** Any positive delta on `critical` or `high` is a hit.
Medium/low deltas accumulate but do not trigger a route on their own.

**Route.** If the new finding is in zizmor's safe-fix set, propose
an auto-fix PR via `workflow-fix-safe` on a new branch
`chore/guardian-T1-<ts>`. Otherwise file a tracking issue with the
zizmor finding ID and link to the report.

---

## T2 — Stale SHA pins

**Detection.** `gh api repos/$REPO/dependabot/alerts --jq '[.[] |
select(.state=="open" and .dependency.package.ecosystem=="actions")]
| length'`. Falls back to checking the latest release SHA for every
SHA-pinned action in `.github/workflows/*.yml` if Dependabot is not
enabled.

**Baseline shape:**

```json
{
  "t2": {
    "stale_pins": 0,
    "dependabot_open_prs": 0
  }
}
```

**Delta.** Any new stale pin OR any new open Dependabot PR is a hit.

**Route.** File a tracking issue `chore: stale SHA pin in
<workflow>` with the Dependabot PR link. The issue carries the
`dependencies` + `github-actions` labels Dependabot itself uses, so
the Guardian-filed issue and Dependabot's own PR are linkable.

---

## T3 — Branch-rule drift

**Detection.** Chain `workflow-protect-branch` SHOW. Compare the
returned ruleset(s) against the previously-cached
`branch-rules.json`. A delta is any change in `enforcement`,
`required_status_checks`, `non_fast_forward`, `deletion`, or the
list of rule types.

**Baseline shape:**

```json
{
  "t3": {
    "ruleset_id": 12345,
    "enforcement": "active",
    "required_checks": ["validate", "workflow-security"],
    "non_fast_forward": true,
    "deletion": true
  }
}
```

**Delta.** ANY difference is a hit — branch rules don't drift by
accident; if they changed, someone took action and Guardian wants
the authorized user to know.

**Route.** Alert the authorized user via direct message (R6
governance edge). Do NOT auto-revert — the user may have made the
change intentionally. Guardian's job is observability, not policy
enforcement.

---

## T4 — Protected-path activity

**Detection.** The canonical protected-paths list lives in
`maintainer-approval-gate/references/protected-paths.md`. For each
path, capture `git log --format=%H -1 -- <path>` (latest commit
touching that path).

**Baseline shape:**

```json
{
  "t4": {
    "paths": {
      ".github/workflows/validate.yml": "abc123...",
      "scripts/publish.py": "def456...",
      ".gitignore": "ghi789..."
    }
  }
}
```

**Delta.** Any path whose latest-commit SHA changed between
baseline and scan is a hit.

**Route.** Alert the authorized user with the protected-path
that moved + the commit URL. The agent does NOT block the change
retroactively (the commit already landed); it just surfaces.

For PROSPECTIVE protected-path edits (i.e. ones the agent itself
is about to make as part of fixing an issue), the
`maintainer-approval-gate` skill is the relevant defense — it
catches the edit BEFORE commit, not after.

---

## T5 — Secret-leak markers

**Detection.** A basic regex sweep on the last 50 commits looking
for the patterns: `AKIA[0-9A-Z]{16}` (AWS), `ghp_[0-9a-zA-Z]{36}`
(GitHub PAT), `glpat-[0-9a-zA-Z\-_]{20}` (GitLab PAT), `xox[baprs]-`
(Slack token), `ya29\.[0-9A-Za-z\-_]+` (Google OAuth),
`sk-[a-zA-Z0-9]{32,}` (OpenAI / Anthropic API key shape).

```bash
git log --all --since="48 hours ago" -p \
  | grep -nE 'AKIA[0-9A-Z]{16}|ghp_[0-9a-zA-Z]{36}|...' \
  || true
```

**Baseline shape:**

```json
{
  "t5": {
    "matches": 0,
    "last_scanned_sha": "abc123..."
  }
}
```

**Delta.** Any non-zero match count is a hit — secrets in commit
history are CRITICAL by definition; baseline is always 0.

**Route.** STOP the patrol cycle. Alert the authorized user with
the matching commit SHA + the suspected secret kind. Do NOT echo
the secret value back in the message. Do NOT proceed with any
other patrol task until the user acknowledges.

---

## Routing table

| Class | Delta | Route |
|---|---|---|
| T1 critical/high | +N | safe-fix PR via workflow-fix-safe OR tracking issue |
| T1 medium/low | +N | accumulate only; weekly digest issue |
| T2 | +N | tracking issue with Dependabot link |
| T3 | any change | alert authorized user (R6 direct edge) |
| T4 | any path moved | alert authorized user (post-hoc, observability) |
| T5 | +N | STOP CYCLE + alert (secret in history is critical) |

## Atomic write pattern

Both `guardian-baseline.json` and `guardian-state.json` are written
atomically — same pattern as `branch-rules.json`. State files MUST
live inside the AGENT WORKING DIRECTORY (never under `$HOME`) so
AI Maestro backups and host migration capture them:

```bash
# Resolve the agent working dir:
#   1. $AIMAESTRO_AGENT_DIR (preferred — AI Maestro env var, see
#      https://github.com/Emasoft/ai-maestro/issues/32)
#   2. $CLAUDE_PROJECT_DIR  (Claude Code project dir)
#   3. $PWD                 (last-resort fallback)
AGENT_DIR="${AIMAESTRO_AGENT_DIR:-${CLAUDE_PROJECT_DIR:-$PWD}}"
STATE_DIR="$AGENT_DIR/.aimaestro/state"
mkdir -p "$STATE_DIR"

TMP="$STATE_DIR/guardian-baseline.json.tmp.$$"
# ...build JSON into $TMP...
mv -f "$TMP" "$STATE_DIR/guardian-baseline.json"
```

`mv -f` is atomic on POSIX filesystems, so a crash mid-scan leaves
the previous baseline intact rather than truncating it.

> **Never** write to `$HOME/.aimaestro/...` or `$HOME/agents/...`.
> Host-global paths are invisible to AI Maestro backups, which
> means after a restore the Guardian starts from a clean baseline
> and re-flags every drift the user already vetted. The same trap
> breaks agent migration between hosts.
