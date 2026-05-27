---
description: Lint every JSON / YAML / TOML / Plist / CFG / INI / .env / Dockerfile in the maintained repo. Severity-aware (HIGH = syntax errors block publish; LOW = style nits).
argument-hint: "[scan|fix-style|audit-installed]"
---

Walk the maintained repo's tree, run the appropriate linter per
file extension, emit a SARIF-style report under
`$MAIN_ROOT/reports/maintainer-config-lint/`. Honours
`.gitignore` (via `git check-ignore`) — never scans ignored files.

Loads skill: **maintainer-config-lint**

Three modes:

- `scan` (default) — full scan. Exits 0 if no HIGH severity
  findings; exits 1 otherwise.
- `fix-style` — auto-fix NITs only (add trailing newline,
  normalize whitespace, sort YAML keys where idempotent). NEVER
  auto-fixes syntax errors or schema violations.
- `audit-installed` — confirm which linters are installed
  (yamllint, hadolint, plutil, jsonschema). Suggest installs for
  missing tools (via `/maintainer-tooling-bootstrap recipe`).

Per-format linter chain:
- **JSON** — `python3 -m json.tool` (built-in syntax check) +
  optional `jsonschema` validation against repo-provided schemas
- **YAML** — `uvx yamllint` with relaxed defaults (line-length
  max 320 to match this plugin's convention)
- **TOML** — `python3 -c "import tomllib"` for syntax
- **Plist** — `plutil -lint` (macOS) or `xmllint --noout`
  (Linux)
- **CFG / INI** — `python3 -c "import configparser; ..."`
- **.env** — syntax-only (line shape `KEY=VALUE`, no value
  content scan — would echo secrets)
- **Dockerfile** — `hadolint` if available

Severity:
- **HIGH** — syntax error (file unusable)
- **MEDIUM** — schema violation (file parses but fails schema)
- **LOW** — style nit (trailing whitespace, no trailing newline)

A clean run prints "0 HIGH / 0 MEDIUM / N LOW (informational)"
and exits 0.

Output schema:
`skills/maintainer-config-lint/references/sarif-output.md`
— SARIF 2.1.0 compatible; consumable by GitHub code-scanning if
uploaded as an artifact.
