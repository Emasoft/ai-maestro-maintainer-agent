# Audit output format — `maintainer-tooling-bootstrap`

The skill emits a JSON file under
`$MAIN_ROOT/reports/maintainer-tooling-bootstrap/<ts>-bootstrap.json`.
This is the contract any downstream skill / CI step / hook reads.

## Table of Contents

- [Top-level fields](#top-level-fields)
- [Tool entry](#tool-entry)
- [Disposition enum](#disposition-enum)
- [Status enum](#status-enum)
- [Worked example](#worked-example)
- [Reading the report from another skill](#reading-the-report-from-another-skill)

## Top-level fields

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-27T17:42:18+0200",
  "platform": {
    "id": "macos",
    "os": "Darwin",
    "kernel": "24.6.0",
    "arch": "arm64",
    "distro": null,
    "package_manager": "brew",
    "is_wsl2": false
  },
  "mode": "audit",
  "mandatory_ok": true,
  "tools": [ /* one entry per probed tool */ ],
  "disposition": "ok",
  "missing_mandatory": [],
  "missing_optional": ["actionlint"],
  "install_failed": [],
  "notes": []
}
```

Field meanings:

| Field | Type | Meaning |
|-------|------|---------|
| `schema_version` | int | Bump if the schema changes; downstream readers gate on this. Current: `1`. |
| `generated_at` | string | ISO 8601 with local-time + GMT offset (`%Y-%m-%dT%H:%M:%S%z`). |
| `platform.id` | string | One of `macos | apt | dnf | pacman | apk | wsl2` (the inner Linux distro of WSL2 sets `is_wsl2: true` and `id` to the inner row). |
| `platform.distro` | string?| For Linux: the `ID` from `/etc/os-release` (`ubuntu`, `fedora`, …). `null` on macOS. |
| `platform.is_wsl2` | bool | True if running under WSL2 (detected via `uname -r` substring). |
| `mode` | string | `audit | recipe | install`. |
| `mandatory_ok` | bool | True iff every tool with `required: true` has `status: ok`. |
| `tools` | array | One entry per tool probed (see [Tool entry](#tool-entry)). |
| `disposition` | string | See [Disposition enum](#disposition-enum). |
| `missing_mandatory` | array | Tool names with `required: true` and `status != ok`. |
| `missing_optional` | array | Tool names with `required: false` and `status != ok`. |
| `install_failed` | array | Tool names whose `install` step ran but post-install verification failed. |
| `notes` | array | Free-text strings (e.g. "macOS /bin/bash 3.2 detected; Homebrew bash absent — install with `brew install bash`"). |

## Tool entry

```json
{
  "name": "gh",
  "required": true,
  "found": true,
  "path": "/opt/homebrew/bin/gh",
  "version": "2.62.0",
  "min_version": "2.40.0",
  "status": "ok",
  "install_recipe": "brew install gh",
  "install_docs_url": "https://github.com/cli/cli#installation",
  "skill_consumers": ["workflow-scan", "workflow-pin-actions", "maintainer-triage"]
}
```

Field meanings:

| Field | Type | Meaning |
|-------|------|---------|
| `name` | string | Lower-case canonical binary name. |
| `required` | bool | True iff in the mandatory set for the maintainer core. |
| `found` | bool | True iff `command -v <name>` exited `0`. |
| `path` | string?| Absolute path from `command -v`; `null` if not found. |
| `version` | string?| Parsed version string (e.g. `"2.62.0"`); `null` if not found or parse failed. |
| `min_version` | string | Minimum required version (semver-ish, see comparison rules below). |
| `status` | string | See [Status enum](#status-enum). |
| `install_recipe` | string | The exact shell command for the host's package manager. |
| `install_docs_url` | string | Canonical upstream install docs (for the `recipe` mode output). |
| `skill_consumers` | array | Names of the maintainer skills that need this tool — purely informational, to help users decide whether to install. |

## Disposition enum

| Value | Meaning |
|-------|---------|
| `ok` | All mandatory present at required versions; optional may be missing. Exit `0`. |
| `needs_install` | Some optional tool missing; mandatory all OK. Exit `0` for `audit`, `1` if a caller needed an optional. |
| `mandatory_missing` | At least one mandatory tool missing or below `min_version`. Exit `1`. |
| `unsupported_platform` | Windows native, BSD, etc. Exit `3`. |
| `install_failed` | `install` mode ran the package manager but post-install verification failed. Exit `7`. |
| `permission_denied` | `install` mode refused (root without `--allow-root`, or no write to package DB). Exit `5`. |

## Status enum

Per-tool `status`:

| Value | Meaning |
|-------|---------|
| `ok` | Found on PATH and version ≥ `min_version`. |
| `missing` | `command -v` returned non-zero. |
| `outdated` | Found but parsed version < `min_version`. |
| `unparseable` | Found but version string did not parse (e.g. tool printed a banner without a version number). Treated as needing reinstall. |
| `unsupported_on_platform` | Tool is intentionally absent on this platform (e.g. `plutil` on Linux). Excluded from `missing_mandatory`/`missing_optional`. |

## Version comparison rules

Versions are split on `.`, `-`, and `+`; each chunk is compared
numerically if both sides parse as int, lexically otherwise. Build
metadata (`+abc`) is ignored. Pre-releases (`-rc1`, `-beta`) compare
*less than* the same version without the suffix.

```
2.62.0          vs  2.40.0      → ok (greater)
2.30.0-rc1      vs  2.30.0      → outdated (rc < release)
1.7.7           vs  1.6         → ok
24.0.0+build123 vs  20.0.0      → ok (build metadata ignored)
```

## Worked example

```json
{
  "schema_version": 1,
  "generated_at": "2026-05-27T17:42:18+0200",
  "platform": {
    "id": "apt",
    "os": "Linux",
    "kernel": "6.8.0-45-generic",
    "arch": "x86_64",
    "distro": "ubuntu",
    "package_manager": "apt",
    "is_wsl2": false
  },
  "mode": "audit",
  "mandatory_ok": false,
  "tools": [
    {
      "name": "gh",
      "required": true,
      "found": true,
      "path": "/usr/bin/gh",
      "version": "2.4.0",
      "min_version": "2.40.0",
      "status": "outdated",
      "install_recipe": "(see install-recipes.md / apt row for gh)",
      "install_docs_url": "https://github.com/cli/cli#installation",
      "skill_consumers": ["workflow-scan", "workflow-pin-actions"]
    },
    {
      "name": "actionlint",
      "required": false,
      "found": false,
      "path": null,
      "version": null,
      "min_version": "1.6.0",
      "status": "missing",
      "install_recipe": "(download release binary)",
      "install_docs_url": "https://github.com/rhysd/actionlint/releases/latest",
      "skill_consumers": ["workflow-scan", "workflow-fix-safe"]
    }
  ],
  "disposition": "mandatory_missing",
  "missing_mandatory": ["gh"],
  "missing_optional": ["actionlint"],
  "install_failed": [],
  "notes": [
    "gh present but at 2.4.0 — too old. Upgrade via the apt repo recipe."
  ]
}
```

## Reading the report from another skill

```bash
REPORT="$(uv run scripts/tool_bootstrap.py audit --json-path-only)"
DISPOSITION="$(jq -r .disposition "$REPORT")"

case "$DISPOSITION" in
  ok)                  echo "host ready"; ;;
  needs_install)       echo "optional missing: $(jq -r '.missing_optional | join(\", \")' "$REPORT")"; ;;
  mandatory_missing)   echo "FAIL: $(jq -r '.missing_mandatory | join(\", \")' "$REPORT")"; exit 1; ;;
  unsupported_platform) echo "FAIL: platform unsupported"; exit 3; ;;
  *) echo "unknown disposition: $DISPOSITION"; exit 99; ;;
esac
```

Downstream skills should NOT shell out to `command -v` themselves —
they read the most recent bootstrap report and trust the JSON.
