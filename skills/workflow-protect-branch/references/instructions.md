# Full step-by-step — `workflow-protect-branch`

## Table of Contents

- [Step 0: Decide mode (SHOW vs APPLY)](#step-0-decide-mode-show-vs-apply)
- [Step 1: Verify admin permission (APPLY only)](#step-1-verify-admin-permission-apply-only)
- [Step 2: Auto-detect required checks (APPLY only)](#step-2-auto-detect-required-checks-apply-only)
- [Step 3: Build the ruleset JSON (APPLY only)](#step-3-build-the-ruleset-json-apply-only)
- [Step 4: Discover existing ruleset](#step-4-discover-existing-ruleset)
- [Step 5: POST or PUT (APPLY only)](#step-5-post-or-put-apply-only)
- [Step 6: Verify post-apply](#step-6-verify-post-apply)
- [Step 7: Write report + refresh agent cache](#step-7-write-report--refresh-agent-cache)

## Step 0: Decide mode (SHOW vs APPLY)

Match the user's trigger phrase:

| Phrases | Mode |
|---|---|
| "show branch rules", "what branch rules are active", "fetch the ruleset", "refresh branch-rule cache" | **SHOW** |
| "protect main branch", "apply branch rules", "set up branch protection", "harden default branch" | **APPLY** |

SHOW skips steps 1–3 and 5 (no admin check needed, no JSON build,
no write). Both modes converge on steps 4, 6, 7.

The main agent invokes SHOW automatically at session startup
(per `agents/ai-maestro-maintainer-agent-main-agent.md`) so the
cache at `$AGENT_DIR/.aimaestro/state/branch-rules.json`
is fresh before any other skill runs.

## Step 1: Verify admin permission (APPLY only)

```bash
REPO="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"

IS_ADMIN="$(gh api "repos/$REPO" --jq '.permissions.admin')"
if [ "$IS_ADMIN" != "true" ]; then
  echo "ABORT: authenticated user lacks admin on $REPO" >&2
  exit 64
fi
```

## Step 2: Auto-detect required checks (APPLY only)

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

## Step 3: Build the ruleset JSON (APPLY only)

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

## Step 5: POST or PUT (APPLY only)

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
# Use the REST API directly — `gh ruleset list` requires gh ≥ 2.44 and is
# absent on older hosts. The REST endpoint has been stable since gh 2.4.
NEW_ID="$(gh api "repos/$REPO/rulesets" \
  --jq '[.[] | select(.name=="default-branch-ruleset")] | .[0].id')"

if [ -z "$NEW_ID" ] || [ "$NEW_ID" = "null" ]; then
  echo "VERIFY FAIL: ruleset not present post-apply" >&2
  exit 65
fi
```

## Step 7: Write report + refresh agent cache

```bash
MAIN_ROOT="$(git worktree list | head -n1 | awk '{print $1}')"
DIR="$MAIN_ROOT/reports/workflow-protect-branch"
mkdir -p "$DIR"
TS="$(date +%Y%m%d_%H%M%S%z)"
REPORT="$DIR/$TS-ruleset.json"

# APPLY mode: fetch the post-apply state. SHOW mode: same call, just no
# preceding POST/PUT.
gh api "repos/$REPO/rulesets" > "$REPORT"

# Refresh the per-agent cache so the main agent + downstream skills
# stay aware of the live rule state across the session.
#
# State MUST live inside the AGENT WORKING DIRECTORY (never $HOME)
# so AI Maestro backups and host-to-host migration capture it.
# Resolution order:
#   1. $AIMAESTRO_AGENT_DIR — proposed AI Maestro env var
#      (https://github.com/Emasoft/ai-maestro/issues/32)
#   2. $CLAUDE_PROJECT_DIR  — Claude Code project dir
#   3. $PWD                 — last-resort fallback
AGENT_DIR="${AIMAESTRO_AGENT_DIR:-${CLAUDE_PROJECT_DIR:-$PWD}}"
CACHE_DIR="$AGENT_DIR/.aimaestro/state"
mkdir -p "$CACHE_DIR"
CACHE_TMP="$CACHE_DIR/branch-rules.json.tmp.$$"
gh api "repos/$REPO/rulesets" --jq '.' > "$CACHE_TMP"
mv -f "$CACHE_TMP" "$CACHE_DIR/branch-rules.json"
```

Cache schema (each entry of the top-level array):

```json
{
  "id": 12345,
  "name": "default-branch-ruleset",
  "target": "branch",
  "enforcement": "active",
  "conditions": {...},
  "rules": [
    {"type": "required_status_checks", "parameters": {...}},
    {"type": "non_fast_forward"},
    {"type": "deletion"}
  ]
}
```

Return the disposition:

```json
{
  "mode": "apply",
  "action": "created",
  "ruleset_id": 12345,
  "required_checks": ["validate", "workflow-security"],
  "report": "/path/to/<ts>-ruleset.json",
  "cache_path": "/Users/.../branch-rules.json"
}
```

For SHOW mode the disposition is:

```json
{
  "mode": "show",
  "ruleset_count": 1,
  "default_branch_ruleset": {
    "id": 12345,
    "required_checks": ["validate", "workflow-security"],
    "enforcement": "active",
    "non_fast_forward": true,
    "deletion": true
  },
  "cache_path": "/Users/.../branch-rules.json"
}
```

Cleanup (APPLY only):

```bash
rm -f "$TMPJSON"
```
