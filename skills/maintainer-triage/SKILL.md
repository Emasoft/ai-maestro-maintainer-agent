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

### Authorization Check (CRITICAL — R19.6)

Before processing any issue, determine the authorized user:

```bash
AUTHORIZED_USER=$(gh api user --jq .login)
```

This is the GitHub login of the host's authenticated `gh` user (typically
the repository owner / MAESTRO-privileged user).

### Classification Flowchart

```text
New Issue
  │
  ├─ Has label "bug" or title contains "bug"/"error"/"crash"/"fix"?
  │   YES → BUG PATH (any author)
  │
  ├─ Has label "feature"/"enhancement" or title contains "feature"/"add"/"request"?
  │   YES → FEATURE PATH (authorized user only)
  │
  ├─ Clearly a duplicate of an existing open issue?
  │   YES → DUPLICATE PATH
  │
  ├─ Spam, off-topic, or unintelligible?
  │   YES → INVALID PATH
  │
  └─ Ambiguous
      → Read the body carefully, classify as bug or feature based on content
```

### Bug Path (any author)

1. Read the issue body and any linked error logs
2. Search the repository for files related to the bug description:
   ```bash
   gh api repos/<owner>/<repo>/git/trees/HEAD?recursive=1 --jq '.tree[].path' | head -200
   ```
3. Attempt to verify the bug:
   - Does the described behavior match the code?
   - Is there a clear code path that causes the issue?
   - Are there related test failures?
4. Based on verification:

   **Verified bug:**
   ```bash
   gh issue edit <number> --repo <repo> --add-label "bug,verified"
   gh issue comment <number> --repo <repo> --body "Verified: <brief explanation of root cause>. Working on a fix."
   ```
   Return disposition `triaged` with `action: fix`

   **Cannot reproduce / insufficient info:**
   ```bash
   gh issue edit <number> --repo <repo> --add-label "bug,needs-info"
   gh issue comment <number> --repo <repo> --body "Thank you for reporting this. I was unable to reproduce the issue. Could you provide: (1) exact steps to reproduce, (2) expected vs actual behavior, (3) your environment (OS, version)?"
   ```
   Return disposition `needs-info`

### Feature Path (AUTHORIZED USER ONLY)

1. Get the issue author:
   ```bash
   AUTHOR=$(gh issue view <number> --repo <repo> --json author --jq .author.login)
   ```

2. Compare against the authorized user:
   ```bash
   if [ "$AUTHOR" != "$AUTHORIZED_USER" ]; then
     gh issue comment <number> --repo <repo> --body "Thank you for your suggestion! Feature requests and change proposals for this repository are only accepted from the repository maintainer (@$AUTHORIZED_USER). Bug reports are welcome from everyone — if this is a bug, please re-open with a bug report."
     gh issue edit <number> --repo <repo> --add-label "wontfix"
     gh issue close <number> --repo <repo>
   fi
   ```
   Return disposition `rejected` with reason `unauthorized-feature`

3. If author IS authorized:
   - Read the request carefully
   - Assess if it's feasible within the current codebase
   - Label `enhancement,accepted`
   - Comment acknowledging the request
   Return disposition `triaged` with `action: fix`

### Duplicate Path

1. Search existing open issues for similar titles/descriptions
2. If clearly a duplicate:
   ```bash
   gh issue comment <number> --repo <repo> --body "This appears to be a duplicate of #<original>. Closing in favor of the original issue."
   gh issue edit <number> --repo <repo> --add-label "duplicate"
   gh issue close <number> --repo <repo>
   ```
   Return disposition `duplicate`

### Invalid Path

```bash
gh issue edit <number> --repo <repo> --add-label "invalid"
gh issue close <number> --repo <repo>
```
Return disposition `invalid`

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
