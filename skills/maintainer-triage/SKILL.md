---
description: |
  Use when maintainer-patrol surfaces a new open issue or the user
  wants to triage, classify, or decide what to do with a specific
  issue on the maintained repo. Classifies a GitHub issue against
  a flowchart (bug, feature or enhancement, duplicate, invalid or
  spam, needs-info) and returns a structured disposition the
  patrol skill records in the ledger. Enforces governance rule
  R19.6: feature requests and change proposals are accepted ONLY
  from the GitHub user authenticated with gh on the host (the
  authorized MAESTRO user); bug reports are welcomed from any
  author. Reads CLAUDE_EFFORT (Claude Code 2.1.133+) to scale
  verification depth — MEDIUM is the floor (LOW is intentionally
  promoted to MEDIUM because triage that skips code verification
  is unsafe), HIGH adds proactive grep before deciding, and MAX
  or XHIGH escalate to cross-file analysis for cross-module or
  self-contradicting issues. Honours the 2.1.116 rate-limit hint:
  if any gh call trips the rate-limit warning, returns a
  needs-info disposition with reason "rate-limit deferred" so the
  patrol skill does NOT mark the issue processed and re-picks it
  up next cycle with a fresh budget. Do NOT trigger on read-only
  "show me issue N" queries — those go straight to gh issue view.
  Trigger with phrases like "triage issue #N", "classify issue
  #N", or "decide what to do with issue #N".
allowed-tools: "Bash(gh:*), Bash(git:*), Read, Write, Grep, Glob, Agent"
---

# Maintainer Triage — Issue Classification

Classify a GitHub issue and determine the appropriate action. This is
the gatekeeper: only verified bugs and authorized feature requests pass
through to the fix workflow.

## Overview

This skill evaluates each new GitHub issue against a classification flowchart,
enforces the authorized-user rule for feature requests (R19.6), and returns a
structured disposition with the recommended action. Bugs from any author are
welcomed; feature requests are accepted only from the repository owner.

## Prerequisites

- `gh` CLI authenticated (`gh auth status`)
- `githubRepo` set on the calling agent
- Issue number and basic metadata available (from maintainer-patrol ledger)

Copy this checklist and track your progress:
- [ ] Authorized user identified via gh api user
- [ ] Issue body read and classified
- [ ] Action determined (fix / none)
- [ ] GitHub labels updated
- [ ] Disposition returned to patrol

## Instructions

1. Determine the authorized user: `AUTHORIZED_USER=$(gh api user --jq .login)`. This is the MAESTRO-privileged GitHub login (R19.6).
2. Read the effort level from the environment to scale verification depth (Claude Code ≥ 2.1.133 exports `$CLAUDE_EFFORT`). MEDIUM is the floor — LOW is intentionally promoted to MEDIUM because triage that skips code verification is unsafe:

   ```bash
   # Floor is MEDIUM. LOW is too shallow for triage — promote to MEDIUM.
   # MAX is reserved for difficult/ambiguous issues that need cross-file analysis.
   # XHIGH (added in Claude Code 2.1.111) is treated as MAX — same deep cross-file budget.
   case "${CLAUDE_EFFORT:-medium}" in
     max|MAX|maximum|MAXIMUM)  TRIAGE_DEPTH=max ;;     # deep grep + cross-file
     xhigh|XHIGH)              TRIAGE_DEPTH=max ;;     # 2.1.111 tier, route to MAX budget
     high|HIGH)                TRIAGE_DEPTH=high ;;    # proactive grep before classifying
     *)                        TRIAGE_DEPTH=medium ;;  # default: grep only when title+body ambiguous
   esac
   ```

   Pre-2.1.133 sessions (env var unset) get the `medium` branch — same conservative default the skill used before. The `xhigh` tier (2.1.111+) maps to `max` because both represent "the user explicitly asked for the deepest available analysis"; triage has no reason to distinguish them.
3. Fetch the issue metadata: `gh issue view <number> --repo <repo> --json title,body,author,labels`.
4. Classify the issue by scanning the title, labels, and body against the flowchart below. Verification depth scales with `$TRIAGE_DEPTH`:
   - `medium` — title + labels + body match; grep the repo only when classification is ambiguous after that.
   - `high` — also grep the repo for referenced symbols/files before deciding, even when title/body looks unambiguous.
   - `max` — escalate to deep cross-file analysis (referenced symbols + their callers/imports) before deciding. Use for issues that span multiple modules or contradict their own labels.
5. If **bug** (label "bug" or title matches "bug"/"error"/"crash"/"fix"): follow the Bug Path — verify, label, return `action: fix` or `needs-info`.
6. If **feature/change** (label "feature"/"enhancement" or title matches "feature"/"add"/"request"): check author against `$AUTHORIZED_USER`. Reject if mismatch (R19.6). Accept if match.
7. If **duplicate**: link the original issue, label `duplicate`, close.
8. If **invalid/spam**: label `invalid`, close.
9. If **ambiguous**: read the body carefully, classify as bug or feature based on content. When `$TRIAGE_DEPTH` is `high` or `max`, grep the codebase (and for `max`, trace cross-file references) before deciding.
10. Return the structured disposition to the patrol skill.

For detailed `gh` commands for each path, see [Classification Paths Reference](references/classification-paths.md):
  - Bug Path (any author)
  - Feature Path (authorized user only)
  - Duplicate Path
  - Invalid Path

## Rate-limit awareness

Every `gh` call in this skill (`gh api user`, `gh issue view`, `gh issue
comment`, `gh issue edit --add-label`, `gh issue close`, `gh search issues`)
can trip GitHub's REST or search-API rate limit. From Claude Code 2.1.116
onward the Bash tool prepends a **"GitHub API rate limit"** hint to the
tool output when the limit is close. If you see that hint:

1. Stop iterating on the current issue.
2. Return the partial disposition `{disposition: "needs-info", action:
   "none", reason: "rate-limit deferred"}` to the patrol skill so the
   issue is **not** marked processed in the ledger.
3. Do NOT retry the same `gh` call inside this triage invocation — the
   next patrol cycle will pick the issue up with a fresh rate-limit
   budget (see `maintainer-patrol`'s own back-off rule).

Tight retry loops only deepen the back-off. A deferred triage costs one
cycle (≤ `$POLL_SECONDS`); a hammered API costs minutes of throttling
across the whole patrol.

## Output

A structured result returned to the patrol skill:

```json
{
  "issue": 42,
  "disposition": "triaged|rejected|duplicate|invalid|needs-info",
  "action": "fix|none",
  "reason": "<brief explanation>"
}
```

The patrol skill records this in the ledger. If `action: fix`, the patrol
skill invokes the **maintainer-fix** skill next.

## Error Handling

| Error | Action |
|-------|--------|
| `gh api user` fails | Stop, report auth failure to main agent |
| Issue not found | Return disposition `invalid`, log error |
| Cannot read repo tree | Skip code verification, triage based on text only |
| Duplicate search fails | Skip duplicate check, proceed to classification |

## Examples

**Bug from any user:**
```
Issue #42: "NullPointerException in auth module"
→ Identified as bug (title contains "exception")
→ Search code for auth module
→ Found root cause in auth.py:87
→ Label: bug,verified
→ Return: {disposition: "triaged", action: "fix"}
```

**Feature from unauthorized user:**
```
Issue #43: "Add dark mode support"
→ Identified as feature request
→ Author: randomuser ≠ AUTHORIZED_USER
→ Comment politely, label wontfix, close
→ Return: {disposition: "rejected", action: "none"}
```

**Feature from authorized user:**
```
Issue #44: "Increase poll interval to 10 minutes"
→ Identified as feature request
→ Author: Emasoft == AUTHORIZED_USER
→ Label: enhancement,accepted
→ Return: {disposition: "triaged", action: "fix"}
```

## Resources

- GitHub CLI issue commands: https://cli.github.com/manual/gh_issue
- Conventional labels: bug, feature, duplicate, invalid, needs-info, wontfix, enhancement
