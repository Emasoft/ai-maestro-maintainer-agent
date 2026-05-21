# Full step-by-step — `workflow-protect-branch`

## Table of Contents

- [Step 1: Verify admin permission](#step-1-verify-admin-permission)
- [Step 2: Auto-detect required checks](#step-2-auto-detect-required-checks)
- [Step 3: Build the ruleset JSON](#step-3-build-the-ruleset-json)
- [Step 4: Discover existing ruleset](#step-4-discover-existing-ruleset)
- [Step 5: POST or PUT](#step-5-post-or-put)
- [Step 6: Verify post-apply](#step-6-verify-post-apply)
- [Step 7: Write report](#step-7-write-report)

## Step 1: Verify admin permission

```bash
REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"

IS_ADMIN="$(gh api "repos/$REPO" --jq '.permissions.admin')"
if [ "$IS_ADMIN" != "true" ]; then
  echo "ABORT: authenticated user lacks admin on $REPO" >&2
  exit 64
fi
```

## Step 2: Auto-detect required checks

```bash
CHECKS_JSON="$(grep -REn '^[[:space:]]{2}[a-z0-9_-]+:' \
  .github/workflows/*.yml \
  | awk -F: '{print $NF}' \
  | tr -d ' ' \
  | sort -u \
  | jq -R . | jq -s 'map({context: .})')"
```

For this plugin that yields:

```json
[
  { "context": "validate" },
  { "context": "workflow-security" }
]
```

## Step 3: Build the ruleset JSON

Write to a tmpfile — never inline with `${{ }}` interpolation
in the shell:

```bash
TMPJSON="$(mktemp -t ruleset.XXXXXX.json)"
cat > "$TMPJSON" <<JSON
{
  "name": "default-branch-ruleset",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["~DEFAULT_BRANCH"],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": $CHECKS_JSON
      }
    },
    { "type": "non_fast_forward" },
    { "type": "deletion" }
  ]
}
JSON
```

The `~DEFAULT_BRANCH` magic ref resolves to whatever branch the
repo declares as its default at apply time — so the same ruleset
JSON is portable across repos that use `main`, `master`, or a
custom default.

`strict_required_status_checks_policy: true` means the head of
the PR must be up to date with the base branch (the default-merge
checkbox).

## Step 4: Discover existing ruleset

```bash
RULESET_ID="$(gh api "repos/$REPO/rulesets" \
  --jq '[.[] | select(.name=="default-branch-ruleset")] | .[0].id // empty')"
```

`// empty` keeps the result empty when no ruleset matches (yields
empty string rather than `null`).

## Step 5: POST or PUT

```bash
if [ -z "$RULESET_ID" ]; then
  RESPONSE="$(gh api -X POST "repos/$REPO/rulesets" --input "$TMPJSON")"
  ACTION="created"
else
  RESPONSE="$(gh api -X PUT "repos/$REPO/rulesets/$RULESET_ID" --input "$TMPJSON")"
  ACTION="updated"
fi
```

If `gh api -X PUT` returns 404 (ruleset deleted concurrently
between our list and our write), retry as POST.

If any 4xx response other than 404, STOP — capture the response
body in the report and surface to the caller.

## Step 6: Verify post-apply

```bash
gh ruleset list --repo "$REPO" \
  | grep default-branch-ruleset \
  || { echo "VERIFY FAIL: ruleset not present post-apply" >&2; exit 65; }

NEW_ID="$(gh api "repos/$REPO/rulesets" \
  --jq '[.[] | select(.name=="default-branch-ruleset")] | .[0].id')"
```

## Step 7: Write report

```bash
MAIN_ROOT="$(git worktree list | head -n1 | awk '{print $1}')"
DIR="$MAIN_ROOT/reports/workflow-protect-branch"
mkdir -p "$DIR"
TS="$(date +%Y%m%d_%H%M%S%z)"
REPORT="$DIR/$TS-ruleset.json"

gh api "repos/$REPO/rulesets/$NEW_ID" > "$REPORT"
```

Return the disposition:

```json
{
  "action": "created",
  "ruleset_id": 12345,
  "required_checks": ["validate", "workflow-security"],
  "report": "/path/to/<ts>-ruleset.json"
}
```

Cleanup:

```bash
rm -f "$TMPJSON"
```
