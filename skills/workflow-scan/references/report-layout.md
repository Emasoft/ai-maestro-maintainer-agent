# Report layout — `workflow-scan`

## Table of Contents

- [File header](#file-header)
- [Severity summary](#severity-summary)
- [Findings sections](#findings-sections)
- [Footer](#footer)
- [Markdown invariants](#markdown-invariants)

## File header

```markdown
# Workflow security audit — <repo>

**Date:** YYYY-MM-DD HH:MM:SS±HHMM (local time + GMT offset)
**zizmor version:** <output of `uvx zizmor --version`>
**actionlint version:** <output of `actionlint -version`>
**Mode:** online | offline (rate-limit downgrade)
**zizmor exit:** 0 | 11 | 12 | 13 | 14
**Highest severity:** none | informational | low | medium | high
**zizmor findings:** N (M suppressed)
**actionlint findings:** N
```

## Severity summary

```markdown
| Severity | zizmor | actionlint |
|----------|--------|------------|
| High     | <n>    | n/a        |
| Medium   | <n>    | n/a        |
| Low      | <n>    | n/a        |
| Info     | <n>    | n/a        |
| Lint     | n/a    | <n>        |
```

## Findings sections

One section per finding, severity-descending, audit-ID-ascending
within severity. Each entry is anchored:

````markdown
### `<audit-id>` — one-line description

- **File:** `<path>:<line>:<col>`
- **Severity:** high | medium | low | informational
- **Confidence:** low | medium | high
- **Auto-fixable:** yes (safe) | yes (unsafe) | no
- **Doc:** <https://docs.zizmor.sh/audits/#audit-id>

```yaml
<±2 lines of context from the workflow>
```

<one-sentence remediation note>
````

## Footer

```markdown
---

## Reproduce locally

```bash
uvx zizmor --gh-token "$(gh auth token)" .github/workflows/
actionlint .github/workflows/*.yml
```

## Suppress a finding

Add an entry under `rules.<id>.ignore` in `zizmor.yml` at the repo
root, citing a PR or issue number that justifies the exception:

```yaml
rules:
  unpinned-uses:
    ignore:
      - workflow.yml:24:15  # PR #N: third-party action requires @v4
```

Blanket ignores are a smell.
```

## Markdown invariants

- Paths in backticks; never bare.
- Severity names lowercase (`high`, `medium`, `low`, `informational`).
- Audit IDs in backticks.
- Exit codes as integers, never strings.
- Header date is local time + GMT offset (`%Y-%m-%d %H:%M:%S%z`).
- One blank line between sections; no trailing whitespace.
