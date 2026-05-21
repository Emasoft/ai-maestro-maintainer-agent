---
description: |
  Use when the user wants a read-only security audit of GitHub
  Actions workflows in the maintained repo, or when chained from
  maintainer-fix after a fix touches .github/workflows/. Runs two
  static analysers — zizmor (zizmorcore/zizmor, fetched on demand
  via uvx) and actionlint (Homebrew) — over .github/workflows/,
  writes a structured JSON report plus a markdown summary under
  $MAIN_ROOT/reports/workflow-scan/, and optionally posts a
  summary comment on a linked GitHub issue when an issue number
  is supplied. No file mutations beyond report writes; no commits;
  no force-push. Auto-creates the label
  workflow-security-review-needed via gh label create --force if
  needed when commenting on an issue (idempotent — safe to re-run).
  Assumes the gh CLI is already authenticated by the host (AI
  Maestro guarantees this) and reads the API token from
  $(gh auth token). Honours the Claude Code 2.1.116 GitHub
  rate-limit hint: switches to --offline on the hint, notes the
  downgrade in the report header, never retries inside one call.
  Do NOT trigger on commands that should mutate workflows
  (use workflow-fix-safe / workflow-pin-actions for that), and do
  NOT trigger on "show me the workflows" — that's gh workflow list.
  Trigger with phrases like "scan workflows", "audit github
  actions", "audit workflow security", "zizmor scan", or
  "check workflow security".
allowed-tools: "Bash(uvx:*), Bash(zizmor:*), Bash(actionlint:*), Bash(gh:*), Bash(git:*), Read, Write, Grep, Glob"
---

# workflow-scan — read-only GitHub Actions audit

Two-tool static analysis of `.github/workflows/`. Zero side
effects beyond writing a report file (and optionally posting an
issue comment).

## Prerequisites (all auto-verified, no human input)

- `uvx` on PATH (provided by `uv`, already required by publish.py).
- `actionlint` on PATH (Homebrew formula `actionlint`).
- `gh auth token` resolves to a valid token (already true on AI
  Maestro hosts — never run `gh auth login` from this skill).
- `.github/workflows/` exists in the current clone; if not, the
  skill returns `{disposition: "skipped", reason: "no workflows"}`.

## Workflow

1. Resolve report path:
   ```bash
   MAIN_ROOT="$(git worktree list | head -n1 | awk '{print $1}')"
   DIR="$MAIN_ROOT/reports/workflow-scan"
   mkdir -p "$DIR"
   TS="$(date +%Y%m%d_%H%M%S%z)"
   JSON="$DIR/$TS-scan.json"
   MD="$DIR/$TS-scan.md"
   ```
2. Run zizmor (JSON for tooling, parses into the markdown):
   ```bash
   uvx zizmor --gh-token "$(gh auth token)" --format=json \
     .github/workflows/ > "$JSON"
   ZEX=$?  # 0 clean | 11..14 by severity | 1 error
   ```
   If the Bash tool prepends "GitHub API rate limit", re-run with
   `--offline` and note "scanned offline (rate-limit)" in the
   report header. Never retry the online run inside this skill.
3. Run actionlint per file (concatenate findings):
   ```bash
   for f in .github/workflows/*.yml; do actionlint "$f"; done
   ```
4. Render `$MD` per
   [references/report-layout.md](references/report-layout.md):
   header (exit code, severity, mode), severity-summary table,
   per-finding sections (file:line:col + audit ID + doc link).
5. If an issue number is supplied in context, post the top of `$MD`
   (header + summary table) as a comment:
   ```bash
   gh label create workflow-security-review-needed --force \
     --color C5DEF5 \
     --description "zizmor or actionlint surfaced new high finding"
   gh issue comment "$ISSUE" --body-file <(head -40 "$MD")
   # Only tag when NEW HIGH findings vs main:
   if [ "$NEW_HIGH" -gt 0 ]; then
     gh issue edit "$ISSUE" --add-label workflow-security-review-needed
   fi
   ```
6. Return:
   ```json
   {
     "exit_code": <0|11|12|13|14>,
     "highest_severity": "none|info|low|medium|high",
     "total": <int>,
     "actionlint": <int>,
     "report_md": "<absolute path>",
     "report_json": "<absolute path>"
   }
   ```

## Constraints

- No commits, no pushes, no `git add` of any kind.
- No `--fix` invocations — that's `workflow-fix-safe`'s job.
- No `--no-verify`, no `-f`, no destructive operations.
- Never run `gh auth login` — fail-fast if `gh auth token` is empty.

## Resources

- zizmor docs: <https://docs.zizmor.sh/>
- actionlint docs: <https://github.com/rhysd/actionlint>
- [Report layout](references/report-layout.md)
