---
description: |
  Use when the user wants to apply ONLY safe auto-fixes to the
  maintained repo's GitHub Actions workflows — never destructive,
  never unsafe. Runs zizmor in safe-fix mode (the conservative
  default, no human review needed), then layers idempotent
  hardening edits: top-level permissions: contents: read,
  concurrency: { group, cancel-in-progress }, timeout-minutes
  on every job, persist-credentials: false on every checkout.
  Commits the resulting diff DIRECTLY on the current git branch
  with a conventional message. NEVER force-pushes (governance
  R19.7). NEVER pushes — pushing is the caller's responsibility.
  NEVER uses --fix=all or --fix=unsafe-only (those need human
  review and a different skill). Assumes secrets and the gh auth
  token are exported by AI Maestro on the host; reads the token
  via $(gh auth token). Honours pre-commit hooks — if a hook
  fails the skill stops and surfaces the failure rather than
  bypassing with --no-verify. Skips silently when
  .github/workflows/ is missing or when the working tree is dirty
  with non-workflow changes (caller should commit those first).
  Do NOT trigger on read-only audit requests (use workflow-scan)
  or on SHA-pinning requests (use workflow-pin-actions). Trigger
  with phrases like "fix workflow security", "harden workflows",
  "apply safe workflow fixes", or "auto-fix workflow findings".
allowed-tools: "Bash(uvx:*), Bash(zizmor:*), Bash(actionlint:*), Bash(gh:*), Bash(git:*), Read, Write, Edit, Grep, Glob"
---

# workflow-fix-safe — apply only conservative auto-fixes

Pipeline: scan → `zizmor --fix=safe` → idempotent hardening
edits → stage by name → commit on current branch. Caller pushes.

## Prerequisites (all auto-checked)

- `uvx` on PATH; `gh auth token` returns a value; clone is a git
  repo with a clean working tree (or only `.github/workflows/`
  changes already staged).
- Current branch is a feature branch — never run on `main` /
  `master` / `release/*` without confirmation. Skill detects via
  `git rev-parse --abbrev-ref HEAD` and aborts if the branch
  matches the protected pattern.

## Workflow

1. Resolve the report-dir for the pre/post scans:
   ```bash
   MAIN_ROOT="$(git worktree list | head -n1 | awk '{print $1}')"
   DIR="$MAIN_ROOT/reports/workflow-fix-safe"
   mkdir -p "$DIR"
   ```
2. Pre-scan baseline: invoke **workflow-scan**, capture finding
   counts. If 0 findings AND every workflow already has top-level
   permissions + concurrency + timeout-minutes + persist-creds
   on every checkout, exit early with disposition `noop`.
3. Apply zizmor safe auto-fixes:
   ```bash
   uvx zizmor --gh-token "$(gh auth token)" --fix=safe \
     .github/workflows/ 2>&1 | tee "$DIR/zizmor-fix.log"
   ```
   Some findings will be "held back" — that's correct (they need
   `--fix=all` which this skill MUST NOT run). Record the held
   count in the report; never escalate.
4. Layer idempotent hardening edits on each workflow file:
   - Top-level `permissions: contents: read` if missing.
   - Top-level `concurrency: { group: "${{ github.workflow }}-${{ github.ref }}", cancel-in-progress: false }` if missing.
   - Per-job `timeout-minutes: 15` if missing.
   - Every `actions/checkout` step gets `with: persist-credentials: false`.
   Use the Read+Edit tools (yaml-aware, line-precise) — NEVER
   shell out to `sed`/`awk` for these edits (YAML round-trip is
   fragile; let the user see each diff via the tool surface).
5. Re-scan: run **workflow-scan** post-edit, compare against the
   baseline. If new findings appeared (unlikely but possible),
   STOP and surface them — do NOT commit a regression.
6. Stage and commit (NEVER `git add -A`):
   ```bash
   git add .github/workflows/<file1> .github/workflows/<file2> ...
   git commit -m "chore(ci): apply safe workflow hardening (zizmor --fix=safe)"
   ```
7. Return:
   ```json
   {
     "fixed_by_zizmor": <int>,
     "hardening_edits": <int>,
     "held_back": <int>,
     "commit": "<sha>",
     "report_md": "<path>"
   }
   ```

## Constraints

- NEVER `--fix=all` or `--fix=unsafe-only`.
- NEVER `git push` — caller pushes.
- NEVER force-push, `--no-verify`, `git add -A`, `git reset --hard`.
- NEVER edit workflows outside `.github/workflows/`.
- STOP on pre-commit hook failure; surface the failure.

## Resources

- zizmor fix modes: <https://docs.zizmor.sh/usage/#auto-fixing>
- Companion skills: `workflow-scan` (read-only), `workflow-pin-actions` (SHA pinning), `workflow-protect-branch` (branch ruleset).
