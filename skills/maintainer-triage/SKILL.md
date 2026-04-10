---
description: >
  Use when maintainer-patrol detects a new issue or user says "triage
  issue #N". Classifies GitHub issues as bug, feature, duplicate, or
  invalid. Enforces authorized-user rule (R19.6) for feature requests.
  Trigger with "triage issue #N".
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
2. Fetch the issue metadata: `gh issue view <number> --repo <repo> --json title,body,author,labels`.
3. Classify the issue by scanning the title, labels, and body against the flowchart below.
4. If **bug** (label "bug" or title matches "bug"/"error"/"crash"/"fix"): follow the Bug Path — verify, label, return `action: fix` or `needs-info`.
5. If **feature/change** (label "feature"/"enhancement" or title matches "feature"/"add"/"request"): check author against `$AUTHORIZED_USER`. Reject if mismatch (R19.6). Accept if match.
6. If **duplicate**: link the original issue, label `duplicate`, close.
7. If **invalid/spam**: label `invalid`, close.
8. If **ambiguous**: read the body carefully, classify as bug or feature based on content.
9. Return the structured disposition to the patrol skill.

For detailed `gh` commands for each path, see [Classification Paths Reference](references/classification-paths.md):
  - Bug Path (any author)
  - Feature Path (authorized user only)
  - Duplicate Path
  - Invalid Path

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
