# Full step-by-step — `workflow-scan`

## Table of Contents

- [Step 1: Resolve report path](#step-1-resolve-report-path)
- [Step 2: Run zizmor (JSON)](#step-2-run-zizmor-json)
- [Step 3: Run actionlint](#step-3-run-actionlint)
- [Step 4: Render markdown report](#step-4-render-markdown-report)
- [Step 5: Rate-limit handling](#step-5-rate-limit-handling)
- [Step 6: Optional issue comment](#step-6-optional-issue-comment)
- [Step 7: Return disposition](#step-7-return-disposition)

## Step 1: Resolve report path

```bash
MAIN_ROOT="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
DIR="$MAIN_ROOT/reports/workflow-scan"
mkdir -p "$DIR"
TS="$(date +%Y%m%d_%H%M%S%z)"
JSON="$DIR/$TS-scan.json"
MD="$DIR/$TS-scan.md"
```

`%Y%m%d_%H%M%S%z` is local time + GMT offset, filesystem-safe.

## Step 2: Run zizmor (JSON)

```bash
uvx zizmor --gh-token "$(gh auth token)" --format=json \
  .github/workflows/ > "$JSON"
ZEX=$?
```

Exit codes (zizmor v1.x contract):

- 0 = clean
- 1 = tool error
- 2 = bad CLI args
- 3 = no inputs collected
- 11 = highest finding informational
- 12 = highest finding low
- 13 = highest finding medium
- 14 = highest finding high

## Step 3: Run actionlint

```bash
ALINT_JSON="$DIR/$TS-actionlint.json"
ALINT_LOG="$DIR/$TS-actionlint.log"
: > "$ALINT_LOG"
ALINT_COUNT=0
for f in .github/workflows/*.y*ml; do
  [ -e "$f" ] || continue
  actionlint -format '{{json .}}' "$f" >> "$ALINT_JSON" 2>> "$ALINT_LOG" \
    || ALINT_COUNT=$((ALINT_COUNT + 1))
done
```

Each file is run separately so one bad file does not abort the rest.

`-format '{{json .}}'` yields structured findings — each carries
`message`, `filepath`, `line`, `column`, `kind` (the rule that fired),
and `snippet`. Group the report on `kind`, exactly as zizmor findings
group on `audit`. Do not line-scrape the human-readable format.

actionlint exit codes: `0` clean, `1` findings, `2` FATAL (unparseable
file / bad config). Exit 2 is a TOOL ERROR, not a dirty scan — surface
it as such; never report it as clean.

Two preconditions worth checking once, before the loop:

- `shellcheck` on PATH — actionlint shells out to it for every `run:`
  block. Absent, the highest-yield lint layer is silently off. Note the
  degradation in the report header.
- `.github/actionlint.yaml` present — if so, read it. A scan run under
  its `ignore:` list is not a clean scan and the report must say so.
  It is also the correct fix for a repo with self-hosted runners
  drowning in unknown-label findings.

See [engine-coverage.md](engine-coverage.md) for what each engine owns
and what it is blind to.

Then run the bundled Sentinel port (32 deterministic rules; covers
the structural classes zizmor does not):

```bash
SENTINEL_JSON="$DIR/$TS-sentinel.json"
uv run --with pyyaml "$MAIN_ROOT/scripts/sentinel_scan.py" scan \
  --format json --severity low . > "$SENTINEL_JSON"
SENTINEL_EX=$?   # 0 = no critical/high, 1 = critical/high present
```

## Step 4: Render markdown report

Parse `$JSON` (zizmor), `$ALINT_JSON` (actionlint) and `$SENTINEL_JSON`
(Sentinel) with `jq` and render per [report-layout.md](report-layout.md).
Group by severity descending, then audit/rule ID ascending. Include the
actionlint and Sentinel findings in their own sections.

Classify each finding — severity, auto-fixability, and which skill
remediates it — per [threat-classes.md](threat-classes.md). Two classes
in that table are **never auto-fixable** and must survive as findings
rather than be absorbed by a later hardening pass:
`pull_request_target` checking out PR head code, and any secret reaching
a log, URL, or artifact.

## Step 5: Rate-limit handling

If the Bash tool prepends a `GitHub API rate limit` hint to the
zizmor run, re-run with `--offline`:

```bash
uvx zizmor --offline --format=json .github/workflows/ > "$JSON"
```

Note `Mode: offline (rate-limit downgrade)` in the report header.
Do NOT retry online inside the same skill invocation.

## Step 6: Optional issue comment

When invoked from `maintainer-fix` with an issue number in
context:

```bash
gh label create workflow-security-review-needed --force \
  --color C5DEF5 \
  --description "zizmor or actionlint surfaced new high finding" \
  --repo "$REPO"

head -40 "$MD" | gh issue comment "$ISSUE" --body-file - \
  --repo "$REPO"

if [ "$NEW_HIGH" -gt 0 ]; then
  gh issue edit "$ISSUE" --add-label workflow-security-review-needed \
    --repo "$REPO"
fi
```

`gh label create --force` is idempotent (creates or updates).

## Step 7: Return disposition

```json
{
  "exit_code": 0,
  "highest_severity": "none",
  "total": 0,
  "actionlint": 0,
  "report_md": "/path/to/<ts>-scan.md",
  "report_json": "/path/to/<ts>-scan.json"
}
```
