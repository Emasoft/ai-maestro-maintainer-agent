# Triage Classification Paths — Detailed Commands

## Table of Contents

- [Bug Path (any author)](#bug-path-any-author)
- [Feature Path (authorized user only)](#feature-path-authorized-user-only)
- [Duplicate Path](#duplicate-path)
- [Invalid Path](#invalid-path)

## Bug Path (any author)

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

## Feature Path (AUTHORIZED USER ONLY)

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

## Duplicate Path

1. Search existing open issues for similar titles/descriptions
2. If clearly a duplicate:
   ```bash
   gh issue comment <number> --repo <repo> --body "This appears to be a duplicate of #<original>. Closing in favor of the original issue."
   gh issue edit <number> --repo <repo> --add-label "duplicate"
   gh issue close <number> --repo <repo>
   ```
   Return disposition `duplicate`

## Invalid Path

```bash
gh issue edit <number> --repo <repo> --add-label "invalid"
gh issue close <number> --repo <repo>
```
Return disposition `invalid`
