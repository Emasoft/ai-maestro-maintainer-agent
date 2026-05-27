# PR Review Checklist — 7 Categories

Each category has the same shape:

- **Goal** — what we're looking for.
- **Detection** — exact shell commands.
- **Flag** — JSON object the skill appends to `flags[]`.
- **Notes** — why this category exists / known false positives.

The skill walks all 7 categories regardless of triage case
(A/B/C). The output is the union of every category's flags.

## Table of Contents

- [Cat 1 — Workflow changes](#cat-1--workflow-changes)
- [Cat 2 — Protected-path edits](#cat-2--protected-path-edits)
- [Cat 3 — Lifecycle-script additions](#cat-3--lifecycle-script-additions)
- [Cat 4 — Lockfile churn](#cat-4--lockfile-churn)
- [Cat 5 — Test/prod balance](#cat-5--testprod-balance)
- [Cat 6 — Diff size](#cat-6--diff-size)
- [Cat 7 — Untrusted-action additions](#cat-7--untrusted-action-additions)
- [Shared diff helpers](#shared-diff-helpers)

---

## Cat 1 — Workflow changes

**Goal:** detect new HIGH-severity zizmor / actionlint findings
introduced by the PR's workflow edits.

**Detection:**

```bash
# Only run if .github/workflows/ files are in the diff.
if jq -e '.[] | select(.filename | startswith(".github/workflows/"))' \
       /tmp/pr-$PR-files.json > /dev/null; then
  # Chain workflow-scan (read-only). Returns JSON with
  # exit_code, highest_severity, total, report_md, report_json.
  SCAN=$(uv run scripts/workflow_scan.py --pr "$PR" --json)
  HIGH_NEW=$(echo "$SCAN" | jq -r .highest_severity)
  if [ "$HIGH_NEW" = "high" ] || [ "$HIGH_NEW" = "error" ]; then
    flag 1 high "workflow.scan.new-high" \
      "workflow-scan surfaced new high-severity findings: $(echo "$SCAN" | jq -r .report_md)"
  fi
fi
```

**Flag:**

```json
{"category": 1, "severity": "high", "label": "workflow.scan.new-high", "detail": "<scan report path>"}
```

**Notes:** the actual zizmor / actionlint / Sentinel commands
live in `skills/workflow-scan/SKILL.md` — this skill never
duplicates them. The base case (no workflow changes) is silent —
no flag, no comment line.

## Cat 2 — Protected-path edits

**Goal:** list every protected path the PR touches, ONE flag per
hit, with a "why was this changed?" prompt.

**Detection:**

```bash
TOUCHED=$(jq -r '.[].filename' /tmp/pr-$PR-files.json)

PROTECTED_LIST="$SKILL_REFS/../../maintainer-approval-gate/references/protected-paths.md"
OVERRIDE_PATH=".aimaestro/protected-paths.txt"

HITS=$(python3 - "$PROTECTED_LIST" "$OVERRIDE_PATH" <<'PY' <<<"$TOUCHED"
import pathlib, sys
list_path, override_path = sys.argv[1], sys.argv[2]
patterns, in_code = [], False
for line in pathlib.Path(list_path).read_text().splitlines():
    if line.startswith("```"):
        in_code = not in_code; continue
    if in_code and line.strip() and not line.lstrip().startswith("#"):
        patterns.append(line.strip())
ov = pathlib.Path(override_path)
if ov.is_file():
    for line in ov.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
planned = sys.stdin.read().splitlines()
for p in planned:
    if p and any(pathlib.PurePath(p).match(g) for g in patterns):
        print(p)
PY
)

while IFS= read -r path; do
  [ -z "$path" ] && continue
  flag 2 high "protected-path.touched" \
    "Protected path \`$path\` modified — why?"
done <<< "$HITS"
```

**Flag (one per hit):**

```json
{"category": 2, "severity": "high", "label": "protected-path.touched", "detail": "<path>"}
```

**Notes:** the canonical list is a single source of truth shared
with `maintainer-approval-gate`. If the per-repo override
(`.aimaestro/protected-paths.txt`) malforms, fall back to the
canonical list and record one low-severity flag.

## Cat 3 — Lifecycle-script additions

**Goal:** flag any NEW lifecycle script that runs at install/
build time. Existing scripts that are unchanged are NOT flagged.

**Detection:**

```bash
# Pull patch hunks for package.json + pyproject.toml.
grep -nE '^(\+\+\+|\+).*(package\.json|pyproject\.toml)' /tmp/pr-$PR.diff > /tmp/lc-target.txt 2>/dev/null

# package.json additions inside "scripts" block
ADDED_NPM=$(awk '
  /^\+\+\+ .*package\.json$/ { inpkg=1; next }
  /^\+\+\+ / { inpkg=0 }
  inpkg && /^\+ *"(preinstall|postinstall|prepare|install|preuninstall|postuninstall)" *:/ { print }
' /tmp/pr-$PR.diff)

# pyproject.toml — new [build-system] requires, new
# [tool.poetry.scripts] entries, new [project.entry-points]
ADDED_PYPROJECT=$(awk '
  /^\+\+\+ .*pyproject\.toml$/ { inpy=1; next }
  /^\+\+\+ / { inpy=0 }
  inpy && /^\+ *(\[build-system\]|\[tool\.poetry\.scripts\]|\[project\.scripts\]|\[project\.entry-points)/ { print }
' /tmp/pr-$PR.diff)

if [ -n "$ADDED_NPM" ]; then
  flag 3 high "lifecycle.npm.added" "New npm lifecycle script(s): $ADDED_NPM"
fi
if [ -n "$ADDED_PYPROJECT" ]; then
  flag 3 high "lifecycle.pyproject.added" "New pyproject build-system / scripts section(s): $ADDED_PYPROJECT"
fi
```

**Flag:**

```json
{"category": 3, "severity": "high", "label": "lifecycle.npm.added|lifecycle.pyproject.added", "detail": "<added lines>"}
```

**Notes:** lifecycle scripts ARE legitimate in many real-world
PRs (build hooks, codegen). The flag prompts the reviewer to
read what the script does — it's not a refusal. The sandbox
precheck in `maintainer-pr-triage` ran with `--ignore-scripts`,
so the agent has NOT actually executed any of these scripts.

## Cat 4 — Lockfile churn

**Goal:** flag any new package version introduced by the PR
whose registry release date is < 7 days ago. Typo-squat and
account-takeover payloads tend to be published just before they
land in a PR.

**Detection:**

```bash
# Identify changed lockfiles.
LOCKFILES=$(jq -r '.[] | select(.filename | test("(^|/)(package-lock\\.json|pnpm-lock\\.yaml|uv\\.lock|Cargo\\.lock|go\\.sum)$")) | .filename' /tmp/pr-$PR-files.json)

# For each lockfile, extract "added" package@version lines from
# the patch (i.e. lines with leading "+" that contain a name +
# version pair). Each ecosystem has a different format — examples:
#
#   package-lock.json (npm):  +    "version": "1.2.3"   (per-package block)
#   pnpm-lock.yaml:           +/pkg@1.2.3:               or "+'<pkg>@<ver>':"
#   uv.lock:                  +name = "pkg"  + version = "1.2.3"
#   Cargo.lock:               +name = "pkg"  + version = "1.2.3"
#   go.sum:                   +<module> v1.2.3 h1:...
#
# Use the per-ecosystem extractor below; for each (name, version)
# query the registry's release-date API.

while IFS= read -r lock; do
  [ -z "$lock" ] && continue
  case "$lock" in
    *package-lock.json|*pnpm-lock.yaml)  ECO=npm    ;;
    *uv.lock)                            ECO=pypi   ;;
    *Cargo.lock)                         ECO=crates ;;
    *go.sum)                             ECO=gomod  ;;
    *)                                   continue   ;;
  esac

  # Extract new (name, version) tuples (per-ecosystem parser).
  ADDED_PKGS=$(scripts/pr_review_lockfile_added.py "$lock" "/tmp/pr-$PR.diff" "$ECO")

  while IFS=$'\t' read -r name ver; do
    [ -z "$name" ] && continue
    case "$ECO" in
      npm)
        REL=$(curl -s "https://registry.npmjs.org/$name" | jq -r ".time[\"$ver\"] // empty") ;;
      pypi)
        REL=$(curl -s "https://pypi.org/pypi/$name/$ver/json" | jq -r '.urls[0].upload_time // empty') ;;
      crates)
        REL=$(curl -s "https://crates.io/api/v1/crates/$name" | jq -r ".versions[] | select(.num == \"$ver\") | .created_at" | head -1) ;;
      gomod)
        # Go modules don't expose a per-version timestamp via a
        # stable API — skip the age check, record low-severity
        # flag noting the gap.
        flag 4 low "lockfile.gomod.no-age" "Cannot verify age of $name@$ver (go.sum)"
        continue ;;
    esac
    if [ -n "$REL" ]; then
      AGE_DAYS=$(python3 -c "from datetime import datetime,timezone; r=datetime.fromisoformat('$REL'.replace('Z','+00:00')); print((datetime.now(timezone.utc) - r).days)")
      if [ "$AGE_DAYS" -lt 7 ]; then
        flag 4 high "lockfile.young-package" "$ECO:$name@$ver released $AGE_DAYS day(s) ago"
      fi
    fi
  done <<< "$ADDED_PKGS"
done <<< "$LOCKFILES"
```

**Flag:**

```json
{"category": 4, "severity": "high|low", "label": "lockfile.young-package|lockfile.gomod.no-age", "detail": "<ecosystem>:<name>@<ver>"}
```

**Notes:** retry the registry calls inside the
github-timeouts retry loop (per `~/.claude/rules/github-timeouts.md`);
a single timeout should NOT cause an entire category to silently
pass.

## Cat 5 — Test/prod balance

**Goal:** flag PRs that add production code WITHOUT adding tests,
or PRs that delete tests.

**Detection:**

```bash
# Heuristic prod paths: every non-test source file under common roots.
PROD_ADDED=$(jq -r '
  [ .[]
    | select(.status != "removed")
    | select(.filename | test("^(src/|lib/|app/|packages/[^/]+/src/|scripts/|cmd/|internal/)"))
    | select(.filename | test("test|spec|fixture|__tests__") | not)
    | .additions ]
  | add // 0' /tmp/pr-$PR-files.json)

TEST_ADDED=$(jq -r '
  [ .[]
    | select(.status != "removed")
    | select(.filename | test("test|spec|__tests__|/tests?/"))
    | .additions ]
  | add // 0' /tmp/pr-$PR-files.json)

TEST_DELETED=$(jq -r '
  [ .[]
    | select(.status == "removed")
    | select(.filename | test("test|spec|__tests__|/tests?/"))
    | .filename ]
  | join(",")' /tmp/pr-$PR-files.json)

if [ "$PROD_ADDED" -gt 20 ] && [ "$TEST_ADDED" = "0" ]; then
  flag 5 medium "tests.prod-without-test" \
    "+$PROD_ADDED prod LOC, 0 test LOC added"
fi
if [ -n "$TEST_DELETED" ]; then
  flag 5 high "tests.deleted" "Test files removed: $TEST_DELETED"
fi
```

**Flag:**

```json
{"category": 5, "severity": "medium|high", "label": "tests.prod-without-test|tests.deleted", "detail": "<summary>"}
```

**Notes:** `> 20` LOC threshold avoids flagging trivial typo
fixes. The path patterns are deliberately conservative — false
positives are preferred to false negatives here.

## Cat 6 — Diff size

**Goal:** flag PRs over 500 added lines as harder-to-review-safely.

**Detection:**

```bash
ADDITIONS=$(jq -r '[ .[].additions ] | add // 0' /tmp/pr-$PR-files.json)
if [ "$ADDITIONS" -gt 500 ]; then
  flag 6 medium "size.over-500" "+$ADDITIONS lines — consider splitting into focused PRs"
fi
```

**Flag:**

```json
{"category": 6, "severity": "medium", "label": "size.over-500", "detail": "+<N> lines"}
```

**Notes:** the threshold is a soft signal, not a refusal — the
reviewer can still merge a 5,000-line PR if it's a refactor.

## Cat 7 — Untrusted-action additions

**Goal:** flag NEW `uses: …@…` lines in workflow YAML.
Dependabot tracks existing actions; new ones haven't been
reviewed by anyone yet.

**Detection:**

```bash
# Extract added `uses:` lines from workflow files in the patch.
ADDED_USES=$(awk '
  /^\+\+\+ .*\.github\/workflows\/.*\.ya?ml$/ { inwf=1; next }
  /^\+\+\+ / { inwf=0 }
  inwf && /^\+ *uses: *[^ ]+@[^ ]+/ { print }
' /tmp/pr-$PR.diff)

if [ -n "$ADDED_USES" ]; then
  # Filter: skip if the action is already pinned in main.
  EXISTING=$(git -C "$REPO_DIR" grep -h "^[[:space:]]*uses:" -- '.github/workflows/' 2>/dev/null || true)
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    ACTION=$(echo "$line" | sed -E 's/^.*uses: *([^ ]+).*$/\1/')
    if ! echo "$EXISTING" | grep -qF "uses: $ACTION"; then
      flag 7 medium "actions.new-untrusted" \
        "New workflow action introduced: \`$ACTION\` — verify the publisher + pin to a commit SHA"
    fi
  done <<< "$ADDED_USES"
fi
```

**Flag (one per new action):**

```json
{"category": 7, "severity": "medium", "label": "actions.new-untrusted", "detail": "<action>@<tag>"}
```

**Notes:** the comparison against `main` filters out "this
action is already in another workflow" false positives. The
flag specifically asks the reviewer to verify the publisher
(per `~/.claude/rules/gh-actions.md` — actions outside
`actions/` and `github/` should be pinned to a commit SHA).

## Shared diff helpers

`flag` is a tiny shell function the categories call:

```bash
flag() {
  local cat=$1 sev=$2 label=$3 detail=$4
  printf '%s\n' "$(jq -nc \
    --argjson c "$cat" --arg s "$sev" --arg l "$label" --arg d "$detail" \
    '{category:$c, severity:$s, label:$l, detail:$d}')" \
    >> /tmp/pr-$PR-flags.jsonl
}
```

At the end of the run, `cat /tmp/pr-$PR-flags.jsonl | jq -s .`
produces the `flags[]` array used by the comment template.
