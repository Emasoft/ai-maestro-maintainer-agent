# Full step-by-step — `workflow-fix-safe`

## Table of Contents

- [Step 1: Protected-branch guard](#step-1-protected-branch-guard)
- [Step 2: Pre-scan baseline](#step-2-pre-scan-baseline)
- [Step 3: Run zizmor --fix=safe](#step-3-run-zizmor---fixsafe)
- [Step 4: Hardening edits](#step-4-hardening-edits)
- [Step 5: Post-scan regression guard](#step-5-post-scan-regression-guard)
- [Step 6: Stage by name and commit](#step-6-stage-by-name-and-commit)

## Step 1: Protected-branch guard

```bash
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
case "$BRANCH" in
  main|master|release/*)
    echo "ABORT: refuse to run on protected branch '$BRANCH'" >&2
    exit 64
    ;;
esac
```

## Step 2: Pre-scan baseline

Invoke the `workflow-scan` skill, capture finding counts in
`$BASELINE_JSON`. If baseline is 0 findings AND every workflow
already has top-level permissions, concurrency, timeout-minutes,
and persist-credentials, exit early with disposition `noop`.

## Step 3: Run zizmor --fix=safe

```bash
MAIN_ROOT="$(git worktree list | head -n1 | awk '{print $1}')"
DIR="$MAIN_ROOT/reports/workflow-fix-safe"
mkdir -p "$DIR"
TS="$(date +%Y%m%d_%H%M%S%z)"

# Redirect to the log (report evidence); do NOT `| tee` it — tee streams
# zizmor's full fix output into the agent's context. The next steps need
# only the held/fixed counts, so read an errors-only summary of the log,
# never the whole log. (Same file-redirect pattern as workflow-scan Step.)
uvx zizmor --gh-token "$(gh auth token)" --fix=safe \
  .github/workflows/ > "$DIR/$TS-zizmor-fix.log" 2>&1
grep -iE 'fixed|held back|no fixes|error|[0-9]+ finding' "$DIR/$TS-zizmor-fix.log" | tail -20
```

Some findings will be "held back" by safe mode (they need
`--fix=all` which this skill MUST NOT run). Record the held count
from the errors-only summary above — do not read the full log into context.

## Step 4: Hardening edits

For each `.github/workflows/*.y*ml`, add or update via Read+Edit
(yaml-aware, line-precise — never sed/awk):

### Top-level permissions block

Insert before `jobs:` if missing:

```yaml
permissions:
  contents: read
```

### Top-level concurrency block

Insert before `jobs:` if missing:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: false
```

`cancel-in-progress: false` so in-flight runs finish — safer for
release pipelines than cancelling mid-publish.

### Per-job timeout-minutes

For each job key under `jobs:`, add `timeout-minutes: 15` if
missing:

```yaml
jobs:
  validate:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      ...
```

### Per-checkout persist-credentials

For every `uses: actions/checkout@...` step, ensure the `with:`
block contains `persist-credentials: false`:

```yaml
- uses: actions/checkout@<sha>  # vX.Y.Z
  with:
    persist-credentials: false
```

### jq command-substitution audit (the `--arg` trap)

Documentation reference for the `--arg` hardening pattern. This
section is a tutorial walk-through with worked examples. Routing
`${{ }}` values through `env:` blocks defeats GitHub
expression injection. It does NOT defeat bash command
substitution. Example of the vulnerable shape (do NOT ship):

```yaml
# Example — VULNERABLE — looks safe but isn't
# This is documentation only — see "How to refactor" below.
env:
  PR_TITLE_PLACEHOLDER: YOUR_PR_TITLE_HERE
run: |
  PAYLOAD=$(jq -nc --arg text "New PR: ${PR_TITLE_PLACEHOLDER}" '{text: $text}')
```

Bash expands the placeholder inside the double-quoted string BEFORE
jq sees it. A PR title containing a bash command-substitution
literal (documented in the tutorial example above) executes via
bash command substitution.

How to detect: for every `run:` block in every workflow file,
scan for the pattern `jq[^|]*"[^"]*\$\{[A-Z_][A-Z0-9_]*\}` (a
documented usage of `${VAR}` inside double-quoted text on the
same line as a `jq` invocation). For every hit:

1. Step 1: read the line and the surrounding context (1-2 lines above
   and below).
2. Step 2: refactor so every shell variable enters `jq` via its own
   `--arg name "$VAR"` and is referenced as `$name` INSIDE the
   jq filter (jq parses `$name`, bash never sees it):

```yaml
# Example — HARDENED — tutorial usage
env:
  PR_TITLE_PLACEHOLDER: YOUR_PR_TITLE_HERE
run: |
  PAYLOAD=$(jq -nc \
    --arg title "$PR_TITLE_PLACEHOLDER" \
    '{text: ("New PR: " + $title)}')
```

3. Step 3: use `Read` + `Edit` (yaml-aware, line-precise) — NEVER
   `sed` or `awk` to rewrite YAML.
4. Step 4: if the surrounding shell builds a JSON payload (an
   example usage list: HTTP client, Slack webhook, generic
   webhook), apply the same `--arg` discipline to every
   interpolated value — partial coverage is no coverage.

If the regex pattern above returns zero hits, this Hardening
Edit is a no-op for that workflow.

## Step 5: Post-scan regression guard

Invoke `workflow-scan` again. If the post-scan reports MORE
findings than the baseline (any severity), STOP — do NOT commit:

```bash
if [ "$POST_HIGH" -gt "$BASELINE_HIGH" ] \
   || [ "$POST_MEDIUM" -gt "$BASELINE_MEDIUM" ]; then
  echo "REGRESSION: post-fix scan introduced new findings" >&2
  exit 65
fi
```

## Step 6: Stage by name and commit

```bash
CHANGED="$(git diff --name-only -- .github/workflows/)"
if [ -z "$CHANGED" ]; then
  echo "noop: no changes to commit"
  exit 0
fi

# Stage explicitly by name — NEVER `git add -A`
echo "$CHANGED" | xargs git add --

git commit -m "chore(ci): apply safe workflow hardening (zizmor --fix=safe)"
```

The commit lands on the current feature branch. Pushing is the
caller's responsibility — this skill stops here per R19.7.

If a pre-commit hook fails, surface the failure verbatim. Do NOT
use `--no-verify`.
