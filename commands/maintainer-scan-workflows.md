---
description: Read-only audit of .github/workflows/ via zizmor + actionlint + the bundled Sentinel port. Writes a markdown report under $MAIN_ROOT/reports/workflow-scan/.
argument-hint: "[--issue <issue-number>]"
---

Run a read-only security audit of every workflow under
`.github/workflows/` on the maintained repo. Loads the
`workflow-scan` skill, which runs the three engines (zizmor +
actionlint + `scripts/sentinel_scan.py` — 32 deterministic rules)
and merges the findings into a per-severity report.

The optional `--issue <N>` argument posts the report as a comment
on issue #N when finished. Without it the report only lands on
disk.

Loads skill: **workflow-scan**

Read the skill's frontmatter for the full command surface,
exit-code semantics, and rate-limit handling. The report path is
printed on stdout.

This command does **not** modify any file. For automatic fixes
use `/maintainer-fix-safe`. For SHA pin updates use
`/maintainer-pin-actions`.
