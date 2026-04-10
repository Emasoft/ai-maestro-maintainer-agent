# Maintainer Fix — Step-by-Step Reference

## Table of Contents

- [Step 1: Prepare the Workspace](#step-1-prepare-the-workspace)
- [Step 2: Create a Feature Branch](#step-2-create-a-feature-branch)
- [Step 3: Understand the Issue](#step-3-understand-the-issue)
- [Step 4: Make the Code Changes](#step-4-make-the-code-changes)
- [Step 5: Run Tests](#step-5-run-tests)
- [Step 6: Commit](#step-6-commit)
- [Step 7: Publish](#step-7-publish)
- [Step 8: Close the Issue](#step-8-close-the-issue)
- [Step 9: Return to Patrol](#step-9-return-to-patrol)

---

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

---

## Step 2: Create a Feature Branch

```bash
ISSUE_NUM=<number>
SLUG=$(echo "<short issue description>" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-' | head -c 40)
BRANCH="fix/${ISSUE_NUM}-${SLUG}"
git checkout -b "$BRANCH"
```

---

## Step 3: Understand the Issue

1. Read the issue description:
   ```bash
   gh issue view $ISSUE_NUM --repo "$REPO" --json title,body,labels,comments
   ```
2. Search the codebase for related files using grep or SERENA MCP.
3. Identify the root cause (bugs) or implementation point (features).
4. Plan the fix before writing any code.

---

## Step 4: Make the Code Changes

- Edit the minimum number of files needed to fix the issue.
- Follow the repo's existing code style and conventions.
- Do NOT add unrelated changes (no cleanup, no refactoring beyond the fix).
- If the repo has type checking (TypeScript, mypy), verify types after editing.

---

## Step 5: Run Tests

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

If tests fail after 3 attempts, comment on the issue and label `fix-failed`.

---

## Step 6: Commit

```bash
git add <specific files>
git commit -m "fix: <description> (closes #$ISSUE_NUM)"
```

For feature implementations: `feat: <description> (closes #$ISSUE_NUM)`

---

## Step 7: Publish

Use the strict publish pipeline if available:

```bash
uv run python scripts/publish.py --patch
```

If not available, push the branch and create a PR:

```bash
git push origin "$BRANCH"
gh pr create --repo "$REPO" \
  --title "fix: <description> (closes #$ISSUE_NUM)" \
  --body "Fixes #$ISSUE_NUM"
```

---

## Step 8: Close the Issue

```bash
gh issue comment $ISSUE_NUM --repo "$REPO" \
  --body "Fixed in <commit-hash> (v<new-version>). The fix is published and available."
gh issue close $ISSUE_NUM --repo "$REPO"
```

---

## Step 9: Return to Patrol

```bash
git checkout main
git pull origin main
```

Return structured result to patrol:

```json
{
  "issue": 42,
  "disposition": "fixed",
  "commit": "<hash>",
  "version": "<new-version>",
  "branch": "fix/42-short-slug"
}
```
