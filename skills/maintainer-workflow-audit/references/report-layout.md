# Workflow audit report layout

The SKILL.md writes its findings to
`$MAIN_ROOT/reports/workflow-audit/<ts>-zizmor.md`. This reference
defines the exact markdown structure so reports are scannable and
diff-friendly across runs.

## File header (always)

```markdown
# Workflow security audit — <repo>

**Date:** <YYYY-MM-DD HH:MM:SS±HHMM>
**zizmor version:** <output of `uvx zizmor --version`>
**Mode:** scan-only | scan-and-fix | audit-and-comment
**Online audits:** enabled | offline (rate-limited)
**Exit code:** <0|11|12|13|14>
**Highest severity:** none | informational | low | medium | high
**Total findings:** <n>
**Fixed this run:** <n>
**Suppressed:** <n>
```

## Severity summary table (always)

```markdown
| Severity | Count | Fixable |
|----------|-------|---------|
| High     | <n>   | <n>     |
| Medium   | <n>   | <n>     |
| Low      | <n>   | <n>     |
| Info     | <n>   | <n>     |
```

## Findings sections (one per severity, descending)

For each finding produced by `zizmor --format=json`:

```markdown
### <audit-id> — <one-line description>

- **File:** `<path>:<line>:<col>`
- **Severity:** <high|medium|low|informational>
- **Confidence:** <low|medium|high>
- **Auto-fixable:** yes (safe) | yes (unsafe) | no
- **Doc:** https://docs.zizmor.sh/audits/#<audit-id>

```yaml
<2-3 line code excerpt from the workflow>
```

<short remediation note>
```

Group by severity (High first), then by audit ID alphabetically
within each severity. Limit the code excerpt to ±2 lines around
the finding's line number.

## Fix-mode footer (only when mode = scan-and-fix)

```markdown
## Fixes applied this run

- `<file>:<line>` — <audit-id> — safe auto-fix applied
- `<file>:<line>` — <audit-id> — safe auto-fix applied

## Fixes held back

The following findings were flagged as auto-fixable but require
`--fix=all` (unsafe mode) which is NOT applied by this skill:

- `<file>:<line>` — <audit-id> — held back: <reason>
- ...

Review each manually before applying.
```

## Footer (always)

```markdown
---

## Reproduce this scan

```bash
uvx zizmor --gh-token "$(gh auth token)" .github/workflows/
```

## Suppress a finding (use sparingly)

Edit `zizmor.yml` at the repo root. Example:

```yaml
rules:
  unpinned-uses:
    ignore:
      - workflow.yml:24:15  # justification: see PR #N
```

Each ignore MUST cite a PR or issue explaining WHY. Blanket ignores
are a smell.
```

## Markdown invariants

- Filenames in backticks; never bare paths.
- All severity names lowercase (`high`, `medium`, `low`, `informational`).
- All audit IDs in backticks (`unpinned-uses`, `template-injection`).
- Exit codes as integers, never strings.
- Local time + GMT offset in the header date.
- One blank line between sections; no trailing whitespace.
