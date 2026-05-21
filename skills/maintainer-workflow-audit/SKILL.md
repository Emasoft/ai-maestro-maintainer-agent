---
description: >
  Use when the user asks to "scan workflows", "audit github actions",
  "audit workflow security", "zizmor scan", "zizmor audit", "fix
  workflow security", "check workflow security", "harden workflows",
  "check actions for vulnerabilities", or any phrasing that targets
  GitHub Actions workflow security. Wraps `uvx zizmor` (zizmorcore/
  zizmor v1.x — no host install required, uvx fetches it) to run a
  static-analysis scan over `.github/workflows/` in the current clone,
  classify findings by zizmor's exit-code contract (0 clean, 11-14
  by severity: info/low/medium/high), and optionally apply
  `--fix=safe` for auto-fixable findings. Three modes: `scan-only`
  (just report), `scan-and-fix` (apply safe fixes, commit DIRECTLY
  to the current branch — never force-push, R19.7), and
  `audit-and-comment` (scan + comment summary on the linked GitHub
  issue). Writes a detailed markdown report to
  `$MAIN_ROOT/reports/workflow-audit/<ts>-zizmor.md`. Honours the
  v2.1.116 GitHub rate-limit hint on every `gh` call. Can be chained
  from `maintainer-fix` as a non-blocking pre-publish audit step, or
  invoked manually by the user. Do NOT trigger on unrelated mentions
  of "audit" or "scan" that don't target workflows or GitHub Actions
  — those go to other skills. Do NOT trigger on read-only "show me
  the workflows" queries — those go to `gh workflow list` directly.
allowed-tools: "Bash(uvx:*), Bash(gh:*), Bash(git:*), Read, Write, Edit, Grep, Glob"
---

# Maintainer Workflow Audit — zizmor-powered GitHub Actions security

Statically analyse the repo's `.github/workflows/` directory for
security issues using zizmor, optionally auto-fix the safe findings,
and report the results.

## Overview

zizmor (`zizmorcore/zizmor`) is a Rust-based static-analysis tool
for GitHub Actions. It flags template-injection bugs, credential
persistence, excessive permissions, unpinned action references,
known-vulnerable actions, impostor commits, and ~30 other classes
of CI/CD security smells. This skill wraps zizmor with the
maintainer agent's reporting conventions and (optionally) commits
auto-fixable findings to the current branch.

## Prerequisites

- `uvx` available on PATH (provided by `uv`, already required by
  the maintainer agent for the publish pipeline).
- `gh` CLI authenticated (`gh auth status`). zizmor uses
  `--gh-token "$(gh auth token)"` for online audits (vulnerable-
  action lookups, impostor-commit checks).
- The clone of the maintained repo is the current working directory
  (or pass an absolute path as the first argument).

Copy this checklist and track your progress:
- [ ] Mode chosen (scan-only / scan-and-fix / audit-and-comment)
- [ ] zizmor scan completed
- [ ] Report written to `$MAIN_ROOT/reports/workflow-audit/`
- [ ] Fixes committed (if scan-and-fix mode)
- [ ] Issue commented (if audit-and-comment mode)

## Output location

Write the report to:
`$MAIN_ROOT/reports/workflow-audit/<YYYYMMDD_HHMMSS±HHMM>-zizmor.md`

Resolve the path with:

```bash
MAIN_ROOT="$(git worktree list | head -n1 | awk '{print $1}')"
REPORT_DIR="$MAIN_ROOT/reports/workflow-audit"
mkdir -p "$REPORT_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S%z)"   # local time + GMT offset
REPORT_FILE="$REPORT_DIR/$TIMESTAMP-zizmor.md"
```

Do NOT write to `reports_dev/`, `.claude/`, or any per-worktree
subtree. Both `/reports/` and `/reports_dev/` must already be in
the maintained repo's `.gitignore`; if not, add them (atomic
append) before writing the first report.

## Instructions

1. **Resolve mode.** Defaults: `scan-only` for read-only triggers
   ("scan", "audit", "check"); `scan-and-fix` when the user
   explicitly says "fix", "harden", or "apply fixes";
   `audit-and-comment` when invoked from the `maintainer-fix` flow
   with an issue number in context.

2. **Verify `.github/workflows/` exists** in the current directory
   (or the argument path). If missing, return:
   `{disposition: "skipped", reason: "no workflows directory"}`.

3. **Run the scan.** Always pass an explicit `--gh-token` so online
   audits resolve correctly:

   ```bash
   GH_TOKEN="$(gh auth token)"
   uvx zizmor --gh-token "$GH_TOKEN" --format=json \
     .github/workflows/ > /tmp/zizmor-$$.json
   EXIT_CODE=$?
   ```

   Exit-code map (per zizmor docs):
   - 0 = clean (or SARIF mode suppressed exit codes)
   - 1 = tool error (bug in zizmor or invalid YAML)
   - 2 = bad CLI args
   - 3 = no inputs collected
   - 11 = highest finding is informational
   - 12 = highest finding is low severity
   - 13 = highest finding is medium severity
   - 14 = highest finding is high severity

4. **Build the report.** Render the JSON output as a markdown
   table grouped by severity, with file:line anchors and links to
   the audit documentation. Include the full exit code + finding
   count line as the report header. See [Report layout
   reference](references/report-layout.md) for the exact template.

5. **Apply fixes (mode = scan-and-fix only).** Run a second pass
   in fix mode:

   ```bash
   uvx zizmor --gh-token "$GH_TOKEN" --fix=safe \
     .github/workflows/ 2>&1 | tee -a "$REPORT_FILE"
   ```

   Important: `--fix=safe` is conservative — many "fixable"
   findings actually require `--fix=all` (which includes unsafe
   fixes). Never use `--fix=all` without explicit user
   authorisation — surface "N held back by fix mode" in the report
   instead and recommend manual review.

6. **Commit fixes (mode = scan-and-fix only).** If `git status`
   shows any modified file under `.github/workflows/`, stage those
   files BY NAME (never `git add -A`) and commit:

   ```bash
   git add .github/workflows/<file-1> [.github/workflows/<file-2> ...]
   git commit -m "chore(ci): apply zizmor safe auto-fixes"
   ```

   Honour R19.7: NEVER force-push, NEVER rewrite history. Pushing
   is the caller's responsibility — the skill stops after the
   commit lands locally. Honour R19.8: if a pre-commit hook fails,
   STOP and surface the failure; do NOT bypass with `--no-verify`.

7. **Comment on the issue (mode = audit-and-comment only).** If
   invoked from `maintainer-fix` with an issue number in context:

   ```bash
   gh issue comment "$ISSUE" --repo "$REPO" --body-file /tmp/zizmor-comment-$$.md
   ```

   Comment body: the report's first ~40 lines (header + severity
   summary table). Honour the v2.1.116 rate-limit hint — if the
   Bash tool prepends "GitHub API rate limit", skip the comment
   step rather than retrying inside this invocation.

8. **Return the disposition** to the caller:

   ```json
   {
     "exit_code": <0|11|12|13|14>,
     "highest_severity": "none|info|low|medium|high",
     "total_findings": <int>,
     "fixed": <int>,
     "remaining_high": <int>,
     "report_path": "<absolute path>"
   }
   ```

For detailed report layout, severity-tier handling, and the
recommended `zizmor.yml` ignore config, see [References](references/report-layout.md).

## Rate-limit awareness

Online audits (`archived-uses`, `known-vulnerable-actions`,
`impostor-commit`, `typosquat-uses`, `ref-confusion`) call the
GitHub API. From Claude Code 2.1.116 onward the Bash tool prepends
a **"GitHub API rate limit"** hint when the limit is close. On
seeing the hint:

1. Switch to offline mode for the remainder of the scan
   (`--offline` or `--no-online-audits`) — partial results are
   better than no results.
2. Note "scan completed offline due to rate-limit" in the report
   header.
3. Do NOT retry online audits within the same skill invocation.

## Error Handling

| Error | Action |
|-------|--------|
| `uvx` not on PATH | Stop, report to caller, do NOT attempt manual install |
| `gh` not authenticated | Run offline scan; note in report header |
| `.github/workflows/` missing | Return `{disposition: "skipped"}` immediately |
| zizmor exit 1 (tool error) | Capture stderr in report, return `{disposition: "error"}` |
| Pre-commit hook fails | STOP. Surface failure. Do NOT use `--no-verify` |
| Issue comment hits rate limit | Skip step, keep local report, return success |

## Output

A timestamped markdown report under
`$MAIN_ROOT/reports/workflow-audit/`, optionally a commit on the
current branch applying safe auto-fixes, optionally a comment on
the linked GitHub issue. The caller decides whether to push.

## Examples

**Manual scan from the user:**
```
User: "scan workflows for security issues"
→ Mode: scan-only
→ uvx zizmor --gh-token ... --format=json .github/workflows/
→ Write report to reports/workflow-audit/20260521_*-zizmor.md
→ Return: {exit_code: 14, highest_severity: "high", total: 12, ...}
```

**Auto-fix + commit:**
```
User: "fix the safe zizmor findings"
→ Mode: scan-and-fix
→ Scan + uvx zizmor --fix=safe
→ git add .github/workflows/validate.yml .github/workflows/release.yml
→ git commit -m "chore(ci): apply zizmor safe auto-fixes"
→ Return: {exit_code: 0, fixed: 3, remaining_high: 0, ...}
```

**Chained from maintainer-fix:**
```
maintainer-fix step 5.5 (pre-publish audit):
→ Mode: audit-and-comment
→ Scan + comment summary on the issue being fixed
→ Tag issue with workflow-security-clean OR workflow-security-regression
→ Continue maintainer-fix flow (non-blocking)
```

## Resources

- zizmor docs: https://docs.zizmor.sh/
- zizmor audits catalogue: https://docs.zizmor.sh/audits/
- zizmor source: https://github.com/zizmorcore/zizmor
- [Report layout reference](references/report-layout.md)

## Constraints

- No force-push — ever (R19.7).
- All tests must pass before any push (R19.8) — but pushing is the
  caller's responsibility; this skill never pushes on its own.
- Never run `--fix=all` without explicit user authorisation.
- Never use `git add -A` — stage workflow files by name.
- Never use `--no-verify` to bypass pre-commit hooks.
- Report file goes under `$MAIN_ROOT/reports/workflow-audit/`,
  filename ends with `-zizmor.md`, timestamp is local + GMT offset.
