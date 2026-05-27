# Per-format linters — `maintainer-config-lint`

The exact command the skill runs for each config format, the
severity it assigns to each failure mode, and the rule IDs that
appear in the SARIF output.

## Table of Contents

- [File extension to format map](#file-extension-to-format-map)
- [JSON](#json)
- [YAML](#yaml)
- [TOML](#toml)
- [Plist](#plist)
- [CFG / INI](#cfg--ini)
- [.env](#env)
- [Dockerfile](#dockerfile)
- [Generic fallthrough](#generic-fallthrough)
- [Severity scheme](#severity-scheme)

## File extension to format map

| Extensions | Format | Linter |
|------------|--------|--------|
| `.json`, `.jsonc`*, `.json5`* | JSON | `python3 -m json.tool` (+ schema if known) |
| `.yml`, `.yaml` | YAML | `uvx yamllint` |
| `.toml` | TOML | `python3 -c "import tomllib; tomllib.load(open(...,'rb'))"` |
| `.plist` | Plist | `plutil -lint` (macOS) / `xmllint --noout` (Linux) |
| `.cfg`, `.ini`, `.conf` | CFG/INI | `python3 -m configparser` |
| `.env`, `.env.*` | DotEnv | bundled `_lint_dotenv()` (no value logging) |
| `Dockerfile`, `*.dockerfile`, `Containerfile` | Dockerfile | `hadolint` if present |
| anything else with `#!/usr/bin/env …` shebang | Generic | skip (not a config) |

`*` JSONC and JSON5 are NOT strict JSON; `json.tool` will reject
trailing commas / comments. The skill detects these by extension
and (a) tries strict parse first, (b) if that fails and the
extension is `.jsonc`/`.json5`, retries with a permissive parser
(`jsonc-parser` via `uvx`), (c) emits a LOW note if the file would
fail strict-JSON parse — useful when the file gets piped through
non-permissive consumers in CI.

## JSON

### Syntax check (always)

```bash
python3 -m json.tool --no-ensure-ascii < "$FILE" > /dev/null 2>&1
```

- Exit `0` → syntax OK.
- Exit `1` → emit HIGH finding `json-syntax-error`; parse the
  stderr (`line N column M`) for location.

### Schema validation (when applicable)

If the file has a known schema, validate with `jsonschema` via
`uvx`. Mapping of well-known files:

| File | Schema URL |
|------|------------|
| `package.json` | <https://json.schemastore.org/package> |
| `tsconfig.json` | <https://json.schemastore.org/tsconfig> |
| `composer.json` | <https://getcomposer.org/schema.json> |
| `.eslintrc.json` | <https://json.schemastore.org/eslintrc> |
| `pyrightconfig.json` | <https://json.schemastore.org/pyrightconfig> |
| `.prettierrc.json` | <https://json.schemastore.org/prettierrc> |
| `renovate.json` | <https://docs.renovatebot.com/renovate-schema.json> |

```bash
uvx --with jsonschema --with requests python3 -c "
import json, sys, jsonschema, requests
schema = requests.get('$SCHEMA_URL', timeout=10).json()
doc = json.load(open('$FILE'))
jsonschema.validate(instance=doc, schema=schema)
"
```

- Validation error → MEDIUM finding `json-schema-violation`.
- Schema fetch failure (network) → add `notes[]` entry, do NOT
  block; schema validation is best-effort.

## YAML

```bash
uvx yamllint \
  -d "{extends: relaxed, rules: {line-length: {max: 320}, trailing-spaces: enable, new-line-at-end-of-file: enable}}" \
  -f parsable "$FILE"
```

Parse the parsable output: `path:line:col: [level] message (rule)`.

- `[error]` → HIGH `yaml-error-<rule>`.
- `[warning]` → MEDIUM `yaml-warning-<rule>`.
- Style rules (`trailing-spaces`, `new-line-at-end-of-file`) → LOW
  `style-nit` (the `fix-style` mode rewrites these).

SKIP `.github/workflows/*.yml` here — those are linted by
`actionlint` inside `workflow-scan`, and re-linting with yamllint
would double-report.

## TOML

```bash
python3 -c "
import sys, tomllib
try:
    with open(sys.argv[1], 'rb') as f:
        tomllib.load(f)
except tomllib.TOMLDecodeError as e:
    print(f'TOML_ERR: {e}', file=sys.stderr)
    sys.exit(1)
" "$FILE"
```

- Exit `1` → HIGH `toml-syntax-error`. Parse the error message —
  `tomllib` produces "Expected X (at line N, column M)".
- Exit `0` → no finding.

Style-only checks (key sorting, duplicate-key tolerance, etc.) are
NOT performed; `tomllib` is strict by spec.

## Plist

### macOS

```bash
plutil -lint "$FILE"
```

- "OK" on stdout → no finding.
- Any other output → HIGH `plist-syntax-error`. The error is
  prefixed by the file path; strip it.

### Linux (fallback)

```bash
xmllint --noout "$FILE" 2>&1
```

`plist` files are XML, so `xmllint --noout` catches XML-level
syntax errors. Plist-semantic checks (key/value type pairs) are
NOT enforced on Linux. Emit a LOW `plist-semantic-skipped` note.

## CFG / INI

```bash
python3 -c "
import configparser, sys
cp = configparser.ConfigParser(strict=True)
try:
    cp.read(sys.argv[1])
except configparser.Error as e:
    print(f'INI_ERR: {e}', file=sys.stderr); sys.exit(1)
" "$FILE"
```

- Exit `1` → HIGH `ini-syntax-error`.
- A duplicate-section warning (strict=True raises) → HIGH `ini-duplicate-section`.

## .env

**No external linter.** The skill ships a small `_lint_dotenv()`
Python helper because every existing tool either echoes values
(`dotenv-linter` did historically) or pulls in heavy deps.

Rules:

| Rule | Severity | Trigger | Logged? |
|------|----------|---------|---------|
| `env-bad-shape` | HIGH | line is non-empty, non-comment, and does not match `^[A-Za-z_][A-Za-z0-9_]*=.*$` | file:line, no value |
| `env-unquoted-value` | LOW | RHS contains a space but is not wrapped in `'…'` or `"…"` | file:line, no value |
| `env-trailing-whitespace` | LOW | line ends with whitespace then newline | file:line |
| `env-crlf-line-ending` | LOW | line ends with `\r\n` and the file is in a unix-only repo (heuristic: any other file has LF only) | file:line |
| `env-duplicate-key` | MEDIUM | the same `KEY=` appears twice (silently the second wins) | file:line of dupe, no value |

The implementation:

```python
import re
KEY_LINE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=')

def _lint_dotenv(path):
    findings = []
    keys = {}
    with open(path, 'r', encoding='utf-8', newline='') as f:
        for i, raw in enumerate(f, start=1):
            line = raw.rstrip('\n').rstrip('\r')
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            if not KEY_LINE.match(line):
                findings.append((i, 'env-bad-shape', 'HIGH'))
                continue
            key, _, value = line.partition('=')
            # space in unquoted value
            if ' ' in value and not (value.startswith('"') or value.startswith("'")):
                findings.append((i, 'env-unquoted-value', 'LOW'))
            if raw.rstrip('\n').endswith(' ') or raw.rstrip('\n').endswith('\t'):
                findings.append((i, 'env-trailing-whitespace', 'LOW'))
            if raw.endswith('\r\n'):
                findings.append((i, 'env-crlf-line-ending', 'LOW'))
            if key in keys:
                findings.append((i, 'env-duplicate-key', 'MEDIUM'))
            keys[key] = i
    return findings
```

The `value` variable is computed but NEVER logged. The report only
records `file:line` and the rule ID.

## Dockerfile

```bash
if command -v hadolint >/dev/null 2>&1; then
    hadolint --format json "$FILE"
else
    echo "hadolint-missing" >&2
fi
```

`hadolint` JSON output: `{file, line, column, level, code, message}`.

- `level: error` → HIGH `hadolint-<code>`.
- `level: warning` → MEDIUM `hadolint-<code>`.
- `level: info`/`style` → LOW `hadolint-<code>`.

If `hadolint` is missing, add a single `notes[]` entry per scan
suggesting the install recipe; do NOT skip silently.

## Generic fallthrough

Any file matched by the walker but not by the extension table is
SKIPPED, not reported. The skill never tries to lint binary files
or source code.

## Severity scheme

Findings are mapped onto a 3-level scale that maps directly to
SARIF `level`:

| Internal | SARIF `level` | Meaning | Auto-fixable in `fix-style`? |
|----------|---------------|---------|------------------------------|
| HIGH | `error` | Syntax error, merge-conflict marker, oversized config rejected, env-bad-shape | NO |
| MEDIUM | `warning` | Schema violation, yamllint warning, ini-duplicate-section, env-duplicate-key | NO |
| LOW | `note` | Style nit, trailing whitespace, missing final newline, env-unquoted-value | YES (only `style-nit` class) |
