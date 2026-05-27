# SARIF output — `maintainer-config-lint`

The skill emits a SARIF 2.1.0 JSON document so the findings can be
consumed by VS Code, GitHub Code Scanning, and any other off-the-shelf
SARIF reader. A human-readable markdown summary accompanies it.

## Table of Contents

- [Why SARIF](#why-sarif)
- [Top-level structure](#top-level-structure)
- [`tool.driver` per linter](#tooldriver-per-linter)
- [`results[]` shape](#results-shape)
- [Severity mapping](#severity-mapping)
- [Suppressions](#suppressions)
- [Markdown summary layout](#markdown-summary-layout)
- [Reading the report](#reading-the-report)
- [Privacy invariants](#privacy-invariants)

## Why SARIF

GitHub's Advanced Security tab and most IDE-side problem panels
already speak SARIF 2.1.0. Emitting it means a finding from this
skill can land in the same UI a developer already uses for
zizmor/CodeQL/etc., without a custom plugin. The SARIF schema is
public:
<https://docs.oasis-open.org/sarif/sarif/v2.1.0/cs01/sarif-v2.1.0-cs01.html>.

## Top-level structure

```json
{
  "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    { /* one run per linter that produced findings; see below */ }
  ]
}
```

Each linter the skill invoked produces one `runs[]` entry — even
if that run had zero findings (so consumers can confirm the linter
actually ran). A linter that was *missing* on the host is reported
in `runs[0].invocations[0].toolExecutionNotifications[]` rather
than as its own run.

## `tool.driver` per linter

Each `run` carries the linter identity:

```json
{
  "tool": {
    "driver": {
      "name": "yamllint",
      "version": "1.35.1",
      "informationUri": "https://yamllint.readthedocs.io/",
      "rules": [
        {
          "id": "yaml-warning-line-length",
          "name": "line-length",
          "shortDescription": { "text": "Line is too long" },
          "defaultConfiguration": { "level": "warning" },
          "helpUri": "https://yamllint.readthedocs.io/en/stable/rules.html#module-yamllint.rules.line_length"
        }
      ]
    }
  },
  "invocations": [
    {
      "executionSuccessful": true,
      "exitCode": 0,
      "commandLine": "uvx yamllint -d ... -f parsable ...",
      "startTimeUtc": "2026-05-27T15:42:18Z",
      "endTimeUtc":   "2026-05-27T15:42:19Z"
    }
  ],
  "results": [ /* findings; see next section */ ]
}
```

Drivers per format:

| Format | `tool.driver.name` |
|--------|--------------------|
| JSON syntax | `python-json` |
| JSON schema | `jsonschema` |
| YAML | `yamllint` |
| TOML | `python-tomllib` |
| Plist (macOS) | `plutil` |
| Plist (Linux) | `xmllint` |
| CFG/INI | `python-configparser` |
| .env | `maintainer-config-lint-dotenv` |
| Dockerfile | `hadolint` |

## `results[]` shape

```json
{
  "ruleId": "json-syntax-error",
  "level": "error",
  "message": { "text": "Expecting ',' delimiter at line 14 column 5" },
  "locations": [
    {
      "physicalLocation": {
        "artifactLocation": {
          "uri": "package.json",
          "uriBaseId": "%SRCROOT%"
        },
        "region": {
          "startLine": 14,
          "startColumn": 5
        }
      }
    }
  ],
  "properties": {
    "internal_severity": "HIGH",
    "fixable_in_fix_style_mode": false,
    "format": "json"
  }
}
```

Required fields per SARIF spec: `ruleId`, `message`, `locations`.

`uri` is always relative to the entrusted repo root. The
`%SRCROOT%` base ID is defined in
`run.originalUriBaseIds.%SRCROOT%` so GitHub's Code Scanning UI can
link findings to the file on the default branch.

## Severity mapping

The internal 3-level scale (HIGH / MEDIUM / LOW) maps to SARIF
`level` exactly:

| Internal | SARIF `level` |
|----------|---------------|
| HIGH | `error` |
| MEDIUM | `warning` |
| LOW | `note` |

The original internal label is also preserved in
`result.properties.internal_severity` for tools that prefer it.

The skill's exit code follows internal severity, not SARIF `level`:

| Highest seen | Exit code |
|--------------|-----------|
| (no findings) | `0` |
| LOW only | `0` |
| MEDIUM (no HIGH) | `0` |
| HIGH (any) | `1` |

This intentionally diverges from "any SARIF `error` = fail" — a
caller running this in `patrol` mode wants the report regardless;
a caller running it as a pre-merge gate gets the right signal
because HIGH always corresponds to a parse failure.

## Suppressions

A finding can be suppressed via a `.config-lint.yml` at the
repo root:

```yaml
# .config-lint.yml
suppress:
  - rule: yaml-warning-line-length
    file: docs/sample-long-yaml.yml
    note: "intentional long line in test fixture; tracked by issue #42"
  - rule: env-unquoted-value
    file: .env.example
    note: "documentation file; intentional whitespace"
```

Suppressed findings still appear in the SARIF output but with
`suppressions[]` populated per the SARIF spec:

```json
{
  "ruleId": "yaml-warning-line-length",
  "suppressions": [
    {
      "kind": "external",
      "justification": "intentional long line in test fixture; tracked by issue #42"
    }
  ]
}
```

They do NOT count toward the exit-code threshold.

## Markdown summary layout

Sits alongside the SARIF file at
`<ts>-config-lint.md`:

```markdown
# Config lint — <repo>

**Date:** YYYY-MM-DD HH:MM:SS±HHMM
**Files scanned:** N
**Total findings:** H high, M medium, L low
**Linters run:** <comma-separated list of `tool.driver.name`>
**Linters missing:** <list with install-recipe links>

## Summary by file

| File | Format | HIGH | MED | LOW |
|------|--------|------|-----|-----|
| `package.json` | json | 0 | 1 | 0 |
| `pyproject.toml` | toml | 1 | 0 | 0 |

## HIGH findings

### `package.json:14:5` — json-syntax-error
> Expecting ',' delimiter at line 14 column 5

(no code excerpt — files may contain secrets)

## MEDIUM findings

…

## LOW findings (aggregated)

- `style-nit` (12 occurrences across 8 files)
- `env-unquoted-value` (3 occurrences in `.env.example`)

## Linters missing

- `hadolint` not on PATH → install: `brew install hadolint` or
  see `references/install-recipes.md` in maintainer-tooling-bootstrap
```

The summary NEVER includes the contents of `.env` files. Even for
non-env files, code excerpts are intentionally omitted — the
SARIF file carries the precise location and an off-line consumer
can open the file.

## Reading the report

```bash
SARIF="$(uv run scripts/config_lint.py scan --json-path-only)"

HIGH="$(jq '[.runs[].results[] | select(.level=="error" and (.suppressions // [] | length == 0))] | length' "$SARIF")"
if [ "$HIGH" -gt 0 ]; then
    echo "FAIL: $HIGH HIGH findings"
    exit 1
fi
```

For VS Code: install the *Sarif Viewer* extension, open the SARIF
file. For GitHub Code Scanning: upload via the `github/codeql-action/upload-sarif`
action (the workflow-bootstrap skill knows how to wire this).

## Privacy invariants

These are hard rules the skill MUST uphold:

1. **No `.env` file contents in any output.** Not in SARIF
   `message`, not in markdown excerpts, not in stdout, not in
   stderr.
2. **No raw file content beyond what's needed.** SARIF
   `region.snippet` is intentionally NOT populated — the file path
   + line/column is enough. The skill emits a `note` in the
   markdown clarifying this is by design.
3. **No file contents in error messages from spawned linters.**
   The skill captures stderr from `yamllint`, `hadolint`, etc.;
   if any line contains `=` and looks like it could be a `.env`
   value (line came from a `.env` file), the value side of the
   `=` is replaced with `<redacted>` before inclusion in the
   report.

Violation of any of these is a HIGH-severity bug; treat them with
the same seriousness as a secret leak.
