---
description: >
  Fix a triaged GitHub issue by cloning the repository, creating a feature
  branch, making code changes, running tests, and publishing via the strict
  publish pipeline. Use when the maintainer-triage skill returns action=fix,
  or when the user says "fix issue #N", "implement the fix for #N", or
  "work on issue #N".
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Agent
---

# Maintainer Fix — Clone, Branch, Fix, Test, Publish

Fix a triaged issue in the maintained repository. The full workflow is:
clone → branch → understand → edit → test → commit → publish → close.

## Prerequisites

- Issue has been triaged with `action: fix` by the maintainer-triage skill
- `gh` CLI authenticated
- `git` configured with user identity
- The repo's `scripts/publish.py` exists and follows the strict pipeline

## Step 1: Prepare the Workspace

If the repo is not already cloned locally:

```bash
REPO="<githubRepo>"
AGENT_NAME="<agent name>"
WORKSPACE="$HOME/agents/$AGENT_NAME/workspace"
mkdir -p "$WORKSPACE"
cd "$WORKSPACE"
if [ ! -d ".git" ]; then
  gh repo clone "$REPO" . -- --depth=50
fi
git fetch origin
git checkout main
git pull origin main
```

If the repo is already cloned, ensure it's up-to-date with origin.

## Step 2: Create a Feature Branch

```bash
ISSUE_NUM=<number>
SLUG=$(echo "<short issue description>" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-' | head -c 40)
BRANCH="fix/${ISSUE_NUM}-${SLUG}"
git checkout -b "$BRANCH"
```

## Step 3: Understand the Issue

1. Read the issue description:
   ```bash
   gh issue view $ISSUE_NUM --repo "$REPO" --json title,body,labels,comments
   ```

2. Study the relevant code:
   - Use `grep` or SERENA MCP to find related files
   - Read the files to understand the current behavior
   - Identify the root cause (for bugs) or the implementation point (for features)

3. Plan the fix before writing any code. Consider:
   - What files need to change?
   - Are there tests to update?
   - Could this break other functionality?

## Step 4: Make the Code Changes

- Edit the minimum number of files needed to fix the issue
- Follow the repo's existing code style and conventions
- Do NOT add unrelated changes (no cleanup, no refactoring beyond the fix)
- If the repo has type checking (TypeScript, mypy), verify types after editing

## Step 5: Run Tests (MANDATORY — R19.8)

The test suite MUST pass before any commit. Detect and run the appropriate
test framework:

```bash
# Python
[ -d tests ] && uv run --with pytest pytest tests/ -x -q

# Node.js
[ -f package.json ] && ([ -f yarn.lock ] && yarn test || npm test)

# Rust
[ -f Cargo.toml ] && cargo test

# Go
[ -f go.mod ] && go test ./...
```

If tests fail:
1. Read the failure output
2. Fix the test or the code
3. Re-run until all pass
4. If unable to fix after 3 attempts, comment on the issue:
   ```bash
   gh issue comment $ISSUE_NUM --repo "$REPO" \
     --body "Fix attempt failed: tests are not passing after the change. Manual review needed. Branch: \`$BRANCH\`"
   gh issue edit $ISSUE_NUM --repo "$REPO" --add-label "fix-failed"
   ```
   Return disposition `fix-failed` to the patrol.

## Step 6: Commit

Use a conventional commit message that references the issue:

```bash
git add <specific files>
git commit -m "fix: <description> (closes #$ISSUE_NUM)"
```

For feature implementations:

```bash
git commit -m "feat: <description> (closes #$ISSUE_NUM)"
```

## Step 7: Publish (MANDATORY — R19.8)

Use the strict publish pipeline if available:

```bash
uv run python scripts/publish.py --patch
```

If `scripts/publish.py` is not present in the target repo, use the repo's
own publish mechanism. If no publish mechanism exists, push the branch and
create a PR:

```bash
git push origin "$BRANCH"
gh pr create --repo "$REPO" \
  --title "fix: <description> (closes #$ISSUE_NUM)" \
  --body "Fixes #$ISSUE_NUM"
```

## Step 8: Close the Issue

After successful publish or PR creation:

```bash
gh issue comment $ISSUE_NUM --repo "$REPO" \
  --body "Fixed in <commit-hash> (v<new-version>). The fix is published and available."
gh issue close $ISSUE_NUM --repo "$REPO"
```

## Step 9: Return to Patrol

After closing the issue, return to the workspace root and switch back to
main:

```bash
git checkout main
git pull origin main
```

Report the result to the patrol skill:

```json
{
  "issue": 42,
  "disposition": "fixed",
  "commit": "<hash>",
  "version": "<new-version>",
  "branch": "fix/42-short-slug"
}
```

## Constraints (R19.7, R19.8)

- **No force-push** — ever. If the push is rejected, investigate why.
- **No history rewrite** — no rebase --force, no amend of pushed commits.
- **No tag/branch deletion** — leave cleanup to the repo owner.
- **Always test before push** — zero exceptions.
- **Honor pre-push hooks** — if the repo has a pre-push hook, it must pass.
- **One fix per issue** — don't bundle multiple issue fixes in one commit.
