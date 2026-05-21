# Effort scaling — `maintainer-triage`

## Table of Contents

- [Triage depth tiers](#triage-depth-tiers)
- [Reading $CLAUDE_EFFORT](#reading-claude_effort)
- [Rate-limit handling](#rate-limit-handling)

## Triage depth tiers

| Depth | When applied | Behaviour |
|---|---|---|
| `medium` (floor) | Default and explicit `LOW`/`MEDIUM` | Title + labels + body match; grep the repo ONLY when classification is ambiguous after that |
| `high` | `$CLAUDE_EFFORT=HIGH` | Also grep the repo for referenced symbols/files before deciding, even when title/body looks unambiguous |
| `max` | `$CLAUDE_EFFORT=MAX` or `XHIGH` | Escalate to deep cross-file analysis (referenced symbols + their callers/imports) before deciding — for issues that span multiple modules or contradict their own labels |

`LOW` is intentionally promoted to `medium` because triage that
skips code verification is unsafe.

## Reading $CLAUDE_EFFORT

```bash
case "${CLAUDE_EFFORT:-medium}" in
  max|MAX|maximum|MAXIMUM)  TRIAGE_DEPTH=max ;;
  xhigh|XHIGH)              TRIAGE_DEPTH=max ;;
  high|HIGH)                TRIAGE_DEPTH=high ;;
  *)                        TRIAGE_DEPTH=medium ;;
esac
```

Pre-2.1.133 sessions (env var unset) get the `medium` branch —
the same conservative default the skill used before
`$CLAUDE_EFFORT` existed.

`xhigh` (Claude Code 2.1.111+) routes to the same MAX budget as
`max` — both express "give me the deepest available analysis".
Triage has no reason to distinguish them.

## Rate-limit handling

Every `gh` call in this skill can trip GitHub's REST or
search-API rate limit. When the Bash tool prepends a
**"GitHub API rate limit"** hint (Claude Code 2.1.116+):

1. STOP iterating on the current issue.
2. Return:
   ```json
   {"disposition": "needs-info", "action": "none", "reason": "rate-limit deferred"}
   ```
   so the patrol skill does NOT mark the issue processed.
3. Do NOT retry the same `gh` call inside this invocation — the
   next patrol cycle resumes with a fresh API budget.

Tight retry loops deepen the back-off. A deferred triage costs
one cycle (≤ `$POLL_SECONDS`); a hammered API costs minutes of
throttling across the whole patrol.
