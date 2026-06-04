# Full step-by-step — `workflow-protect-branch`

## Table of Contents

- [Why two rulesets, not one](#why-two-rulesets-not-one)
- [Step 0: Decide mode (SHOW vs APPLY)](#step-0-decide-mode-show-vs-apply)
- [Step 1: Verify admin permission (APPLY only)](#step-1-verify-admin-permission-apply-only)
- [Step 2: Auto-detect required checks (APPLY only)](#step-2-auto-detect-required-checks-apply-only)
- [Step 3: Build the two ruleset JSON bodies (APPLY only)](#step-3-build-the-two-ruleset-json-bodies-apply-only)
- [Step 4: Discover both existing rulesets](#step-4-discover-both-existing-rulesets)
- [Step 5: POST or PUT each ruleset (APPLY only)](#step-5-post-or-put-each-ruleset-apply-only)
- [Step 6: Verify both present post-apply](#step-6-verify-both-present-post-apply)
- [Step 6.5: Delete orphaned legacy rulesets (APPLY only)](#step-65-delete-orphaned-legacy-rulesets-apply-only)
- [Step 7: Write report + refresh agent cache](#step-7-write-report--refresh-agent-cache)

## Why two rulesets, not one

A GitHub ruleset's `bypass_actors` applies to the **entire ruleset**,
never per-rule. The canonical `publish.py` model pushes **directly to
the default branch** (Gate-0 pre-push hook — only publish.py may push,
no PR). But a `required_status_checks` rule blocks every direct push:
required checks only go green AFTER a push (CI / tag-triggered
workflows), so a direct push can never satisfy "N of N required status
checks are expected" → `GH013` rejection.

The fix is NOT to bypass the whole ruleset for admin — that would also
let admin force-push and delete the branch, a far wider hole. Instead,
SPLIT the protection into two rulesets on `~DEFAULT_BRANCH`:

| Ruleset | rules | `bypass_actors` | Effect |
|---|---|---|---|
| `baseline-history-protect` | `[deletion, non_fast_forward, required_linear_history]` | `[]` | force-push, branch-deletion, and non-linear (merge-commit) history blocked for EVERYONE incl. admin. A normal fast-forward push is NOT a force-push and adds no merge commit, so it is not blocked. |
| `baseline-pr-and-checks` | `[pull_request, required_status_checks]` (strict, the CI job ids) | `[{actor_id:5, actor_type:"RepositoryRole", bypass_mode:"always"}]` | admin (publish.py) direct-push bypasses BOTH the PR requirement and the checks; outside-contributor PRs are still gated by review + checks. |

Result: publish.py's normal push succeeds (admin bypasses checks; a
fast-forward isn't a force-push), force-push/deletion stay blocked for
all, PR flow stays gated. The push log shows
`remote: Bypassed rule violations ...` on success.

`actor_id:5` = the built-in **Admin** RepositoryRole (GitHub accepts
it; verify via readback). User repos have no OrganizationAdmin and no
per-user bypass actor, so RepositoryRole(Admin) is the right actor.
Do NOT put `required_status_checks` and history-protection in ONE
bypassed ruleset — verified live 2026-05-29 on
`Emasoft/ai-maestro-maintainer-agent` (the v1.3.1 publish that surfaced
this).

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

Use a real YAML parser. A shell `grep` over 2-space-indented keys
over-matches: it pulls in `concurrency.group` values, boolean leafs
(`read`, `true`), `runs-on:` targets, etc., and the resulting
`required_status_checks` POST fails with HTTP 422 *"Expected context
to be present"*. Verified empirically on 2026-05-27 when an earlier
shell-grep recipe produced the wrong context list.

```bash
CHECKS_JSON="$(python3 -c "
import yaml, json, glob
checks=[]
for f in sorted(glob.glob('.github/workflows/*.yml') + glob.glob('.github/workflows/*.yaml')):
    with open(f) as fh: wf = yaml.safe_load(fh) or {}
    for job_id in (wf.get('jobs') or {}):
        checks.append({'context': job_id})
print(json.dumps(checks))
")"
```

For this plugin that yields the four actual job ids:

```json
[
  { "context": "notify" },
  { "context": "validate-tag" },
  { "context": "validate" },
  { "context": "workflow-security" }
]
```

If a workflow declares jobs that are NOT meant to be required checks
(e.g. an opt-in deployment job, a chronologically-later release job),
filter `CHECKS_JSON` post-hoc — never silently drop them by hand-
maintaining a separate list.

## Step 3: Build the two ruleset JSON bodies (APPLY only)

Write each to its own tmpfile — never inline with `${{ }}`
interpolation in the shell.

**Body A — history-protect, NO bypass:**

```bash
TMP_HIST="$(mktemp -t ruleset-hist.XXXXXX.json)"
cat > "$TMP_HIST" <<JSON
{
  "name": "baseline-history-protect",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] }
  },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "required_linear_history" }
  ],
  "bypass_actors": []
}
JSON
```

**Body B — required-checks, admin bypass:**

```bash
TMP_CHECKS="$(mktemp -t ruleset-checks.XXXXXX.json)"
cat > "$TMP_CHECKS" <<JSON
{
  "name": "baseline-pr-and-checks",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] }
  },
  "rules": [
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_review_thread_resolution": true
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": $CHECKS_JSON
      }
    }
  ],
  "bypass_actors": [
    { "actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always" }
  ]
}
JSON
```

The `~DEFAULT_BRANCH` magic ref resolves to whatever branch the repo
declares as its default at apply time — portable across repos that
use `main`, `master`, or a custom default.

`strict_required_status_checks_policy: true` means a PR head must be
up to date with the base branch (the default-merge checkbox). Neither
the `pull_request` rule nor the checks block admin's direct push,
because `bypass_actors` exempts the admin RepositoryRole from this
entire (PR-and-checks) ruleset — that is exactly what lets `publish.py`
push straight to the default branch.

The admin bypass lives ONLY on Body B. Body A's `bypass_actors` is
`[]` so force-push, deletion, and non-linear (merge-commit) history
stay blocked for everyone, including admin — a linear fast-forward push
(what publish.py does) adds no merge commit, so it satisfies
`required_linear_history`. See [Why two rulesets](#why-two-rulesets-not-one).

## Step 4: Discover both existing rulesets

```bash
HIST_ID="$(gh api "repos/$REPO/rulesets" \
  --jq '[.[] | select(.name=="baseline-history-protect")] | .[0].id // empty')"
CHECKS_ID="$(gh api "repos/$REPO/rulesets" \
  --jq '[.[] | select(.name=="baseline-pr-and-checks")] | .[0].id // empty')"
```

`// empty` yields an empty string (not `null`) when a name has no
match, so the Step-5 `-z` test routes a missing ruleset to POST.

## Step 5: POST or PUT each ruleset (APPLY only)

Apply BOTH. A helper keeps the create-or-update logic in one place:

```bash
# Extract the .id from a ruleset response body. python3 is already a hard
# dependency (Step 2 uses it) — do NOT pipe into `gh api --jq`, which makes
# an HTTP request and cannot filter piped stdin.
ruleset_id_from() { python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])'; }

apply_ruleset() {  # $1=existing-id (may be empty)  $2=tmpfile  → echoes "id<TAB>action"
  local id="$1" body="$2" resp action
  if [ -z "$id" ]; then
    resp="$(gh api -X POST "repos/$REPO/rulesets" --input "$body")"
    action="created"
  else
    # If PUT 404s (ruleset deleted between our list and our write), retry as POST.
    resp="$(gh api -X PUT "repos/$REPO/rulesets/$id" --input "$body" 2>/dev/null)" \
      && action="updated" \
      || { resp="$(gh api -X POST "repos/$REPO/rulesets" --input "$body")"; action="created"; }
  fi
  printf '%s\t%s\n' "$(printf '%s' "$resp" | ruleset_id_from)" "$action"
}

read HIST_NEW_ID   HIST_ACTION   < <(apply_ruleset "$HIST_ID"   "$TMP_HIST")
read CHECKS_NEW_ID CHECKS_ACTION < <(apply_ruleset "$CHECKS_ID" "$TMP_CHECKS")
```

These snippets are bash (process substitution `< <(...)` and `local`).
If any 4xx response other than 404, STOP — capture the response body in
the report and surface to the caller. Apply order does not matter; the
two rulesets are independent.

## Step 6: Verify both present post-apply

```bash
# Use the REST API directly — `gh ruleset list` requires gh ≥ 2.44 and is
# absent on older hosts. The REST endpoint has been stable since gh 2.4.
NAMES="$(gh api "repos/$REPO/rulesets" --jq '.[].name')"
for want in baseline-history-protect baseline-pr-and-checks; do
  printf '%s\n' "$NAMES" | grep -qx "$want" || {
    echo "VERIFY FAIL: ruleset '$want' not present post-apply" >&2
    exit 65
  }
done

# Defence-in-depth: confirm the checks ruleset kept its admin bypass and
# the history ruleset stayed bypass-less — a wrong shape silently reopens
# the GH013 block (or the force-push hole).
CHECKS_BYPASS="$(gh api "repos/$REPO/rulesets/$CHECKS_NEW_ID" \
  --jq '[.bypass_actors[].actor_type] | join(",")')"
HIST_BYPASS="$(gh api "repos/$REPO/rulesets/$HIST_NEW_ID" \
  --jq '(.bypass_actors // []) | length')"
[ "$CHECKS_BYPASS" = "RepositoryRole" ] || {
  echo "VERIFY FAIL: checks ruleset lost its admin bypass ($CHECKS_BYPASS)" >&2
  exit 66
}
[ "$HIST_BYPASS" = "0" ] || {
  echo "VERIFY FAIL: history ruleset has $HIST_BYPASS bypass actor(s), want 0" >&2
  exit 66
}

# Confirm the ratified rule set actually landed — a partial apply can
# leave a ruleset present-by-name but missing required_linear_history or
# the pull_request rule, silently weakening the baseline.
HIST_RULES="$(gh api "repos/$REPO/rulesets/$HIST_NEW_ID" \
  --jq '[.rules[].type] | sort | join(",")')"
CHECKS_RULES="$(gh api "repos/$REPO/rulesets/$CHECKS_NEW_ID" \
  --jq '[.rules[].type] | sort | join(",")')"
[ "$HIST_RULES" = "deletion,non_fast_forward,required_linear_history" ] || {
  echo "VERIFY FAIL: history rules = [$HIST_RULES], want deletion,non_fast_forward,required_linear_history" >&2
  exit 67
}
[ "$CHECKS_RULES" = "pull_request,required_status_checks" ] || {
  echo "VERIFY FAIL: pr-and-checks rules = [$CHECKS_RULES], want pull_request,required_status_checks" >&2
  exit 67
}
```

## Step 6.5: Delete orphaned legacy rulesets (APPLY only)

Re-applying the ratified `baseline-*` pair supersedes the
pre-ratification rulesets. Once BOTH new rulesets verify present and
correctly-shaped (Step 6), delete any orphaned legacy ruleset BY NAME —
never a blanket "delete every ruleset", only the documented superseded
names. Order matters: new applied + verified FIRST, legacy removed
SECOND, so a crash in between still leaves the branch protected by the
new pair.

```bash
DELETED_LEGACY=()
for name in default-branch-no-force-no-delete \
            default-branch-required-checks \
            default-branch-ruleset \
            janitor-baseline \
            main-hardening \
            main-ci-gate; do
  OLD_ID="$(gh api "repos/$REPO/rulesets" \
    --jq "[.[] | select(.name==\"$name\")] | .[0].id // empty")"
  [ -z "$OLD_ID" ] && continue
  gh api -X DELETE "repos/$REPO/rulesets/$OLD_ID" \
    && DELETED_LEGACY+=("$name") \
    && echo "deleted orphaned legacy ruleset: $name ($OLD_ID)"
done
```

The six names are the full pre-ratification superseded set agreed on
issue #7 / janitor #14 (the union across both plugins): the maintainer's
old pair (`default-branch-no-force-no-delete`,
`default-branch-required-checks`), the even-older single
`default-branch-ruleset`, and the janitor's lineage — `janitor-baseline`
(v0.5.x) plus its v0.6.x split pair `main-hardening` / `main-ci-gate`.
Including the janitor's names matters because this agent guards
downstream repos the janitor may have hardened earlier; cleaning the
union lets whichever plugin applies last fully converge the repo to the
`baseline-*` pair. Deleting only these named rulesets — and only after
the new pair verifies — is the ratified convergence behavior, and is
EXEMPT (apply-baseline-as-is) per the governance exempt-operations list.
SHOW mode never reaches this step.

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

The cache is the full ruleset **array** (`gh api .../rulesets`
returns every ruleset), so it already holds BOTH entries with no
schema change. The two relevant entries look like:

```json
[
  {
    "id": 16946501,
    "name": "baseline-history-protect",
    "target": "branch",
    "enforcement": "active",
    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
    "rules": [{"type": "deletion"}, {"type": "non_fast_forward"}, {"type": "required_linear_history"}],
    "bypass_actors": []
  },
  {
    "id": 17025842,
    "name": "baseline-pr-and-checks",
    "target": "branch",
    "enforcement": "active",
    "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
    "rules": [{"type": "pull_request", "parameters": {...}}, {"type": "required_status_checks", "parameters": {...}}],
    "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]
  }
]
```

Return the APPLY disposition (both rulesets):

```json
{
  "mode": "apply",
  "history_ruleset": {"id": 16946501, "action": "updated"},
  "checks_ruleset": {"id": 17025842, "action": "updated"},
  "required_checks": ["validate", "workflow-security"],
  "deleted_legacy": ["default-branch-no-force-no-delete", "default-branch-required-checks"],
  "report": "/path/to/<ts>-ruleset.json",
  "cache_path": "/Users/.../branch-rules.json"
}
```

For SHOW mode the disposition lists both:

```json
{
  "mode": "show",
  "ruleset_count": 2,
  "rulesets": {
    "baseline-history-protect": {
      "id": 16946501, "enforcement": "active",
      "deletion": true, "non_fast_forward": true,
      "required_linear_history": true, "bypass_actors": 0
    },
    "baseline-pr-and-checks": {
      "id": 17025842, "enforcement": "active",
      "pull_request": true,
      "required_checks": ["validate", "workflow-security"],
      "admin_bypass": true
    }
  },
  "cache_path": "/Users/.../branch-rules.json"
}
```

APPLY removes the superseded legacy rulesets automatically in Step 6.5
and reports them in the disposition's `deleted_legacy` array (empty when
the repo was already clean). SHOW mode never deletes — it only reads and
caches.

Cleanup (APPLY only):

```bash
rm -f "$TMP_HIST" "$TMP_CHECKS"
```
