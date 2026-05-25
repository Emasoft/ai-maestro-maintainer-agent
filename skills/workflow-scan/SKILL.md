---
description: |
  Use when the user wants a read-only security audit of GitHub
  Actions workflows in the maintained repo, or when chained from
  maintainer-fix after a fix touches .github/workflows/. Runs
  zizmor + actionlint + the bundled Sentinel rule engine via uvx,
  writes JSON + markdown report to
  $MAIN_ROOT/reports/workflow-scan/, optionally posts an issue
  summary comment. No mutations; no commits.
  Trigger with phrases like "scan workflows", "audit github
  actions", "zizmor scan", or "check workflow security".
---

# workflow-scan — read-only GitHub Actions audit

Three-engine static analysis of `.github/workflows/`. Zero side
effects beyond writing a report file (and optionally posting an
issue comment).

## Overview

Wraps `uvx zizmor` (zizmorcore/zizmor), `actionlint`, and the
bundled `scripts/sentinel_scan.py` (a Python port of the Sentinel
scanner — 32 deterministic rules covering the structural classes
zizmor does not, such as build/publish credential exposure and
IDE-config injection) for a read-only audit of every workflow under
`.github/workflows/`. Writes JSON + markdown reports under
`$MAIN_ROOT/reports/workflow-scan/`. Optionally posts a summary
on a linked GitHub issue. No file mutations, no commits, no push.

## Prerequisites

- `uvx` on PATH (provided by `uv`).
- `actionlint` on PATH (Homebrew formula `actionlint`).
- `gh auth token` resolves to a valid token (AI Maestro
  guarantees this on the host).
- `.github/workflows/` exists; if not, the skill returns
  `{disposition: "skipped", reason: "no workflows"}`.

## Instructions

1. Resolve report path under `$MAIN_ROOT/reports/workflow-scan/`
   with a `YYYYMMDD_HHMMSS±HHMM` local-time-plus-offset stamp.
2. Run `uvx zizmor --gh-token "$(gh auth token)" --format=json
   .github/workflows/` and capture exit code.
3. Run `actionlint <file>` for every `*.yml`, then run
   `uv run --with pyyaml scripts/sentinel_scan.py scan --format json .`
   and merge all three engines' findings.
4. Render the markdown report per
   [references/report-layout.md](references/report-layout.md).
5. On rate-limit hint: re-run with `--offline`, note in header.
6. If an issue number is in context, post the report's first 40
   lines as a comment; auto-create the label
   `workflow-security-review-needed` via `gh label create --force`.
7. Return a structured disposition (see Output).

For step-by-step commands see
[references/instructions.md](references/instructions.md).

## Output

A JSON object with `exit_code`, `highest_severity`,
`total`, `actionlint`, `report_md`, and `report_json` fields,
plus the two report files on disk.

## Error Handling

| Error | Action |
|-------|--------|
| `uvx` not on PATH | Stop, surface to caller |
| `gh auth token` empty | Stop, surface to caller |
| `.github/workflows/` missing | Return `{disposition: "skipped"}` |
| zizmor exit 1 (tool error) | Capture stderr in report, return error disposition |
| Rate-limit hint | Re-run `--offline`, note in report header |

## Examples

Manual scan:
```
User: "scan workflows for security issues"
→ uvx zizmor … --format=json .github/workflows/
→ actionlint .github/workflows/*.yml
→ Write report to reports/workflow-scan/<ts>-scan.md
→ Return: {exit_code: 14, highest_severity: "high", total: 12, …}
```

Chained from maintainer-fix:
```
maintainer-fix step 6 (workflow touched):
→ Run workflow-scan in audit mode with the issue number in context
→ Post summary as issue comment
→ Tag workflow-security-review-needed if new highs vs base
```

## Resources

- zizmor docs: <https://docs.zizmor.sh/>
- actionlint docs: <https://github.com/rhysd/actionlint>
- Sentinel port: `scripts/sentinel_scan.py` (32 deterministic
  rules; `scan` + `fix` subcommands)
- [Report layout](references/report-layout.md):
  - File header
  - Severity summary
  - Findings sections
  - Footer
  - Reproduce locally
  - Suppress a finding
  - Markdown invariants
- [Full step-by-step instructions](references/instructions.md):
  - Step 1: Resolve report path
  - Step 2: Run zizmor (JSON)
  - Step 3: Run actionlint
  - Step 4: Render markdown report
  - Step 5: Rate-limit handling
  - Step 6: Optional issue comment
  - Step 7: Return disposition
