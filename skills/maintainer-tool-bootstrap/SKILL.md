---
description: |
  Audit and install the maintainer CLI tools (gh, uv, actionlint,
  etc.) on a new host (macOS, Linux x86_64, Linux aarch64, WSL2).
  Refuses root unless --allow-root; refuses Windows native.
  Trigger with "bootstrap maintainer tools", "what's missing on
  this host", "install gh / uv / actionlint", "tool audit".
---

# maintainer-tool-bootstrap — cross-platform tool installer + auditor

## Overview

Every other skill in this plugin assumes a particular set of CLI
tools are on `PATH` at a minimum version. When they are not, the
caller hits a cryptic "command not found" instead of an actionable
error. This skill centralises detection, version-checking, and
guided installation across the four supported host shapes — macOS
(Homebrew), Debian/Ubuntu (`apt`), Fedora/RHEL/Rocky (`dnf`), Arch
(`pacman`), Alpine (`apk`), and WSL2 (uses the inner Linux distro
path). Windows-native hosts are explicitly unsupported.

The skill ships three modes — `audit`, `recipe`, `install` — and
writes a JSON report under `$MAIN_ROOT/reports/maintainer-tool-bootstrap/`
so callers downstream (CI, the patrol loop) can read the result
without re-running detection.

**Mandatory tools** for the maintainer core: `gh` (≥2.40),
`git` (≥2.30), `uv` (≥0.4), `bash` (≥4.0).

**Per-skill optional tools** are listed under
[references/install-recipes.md](references/install-recipes.md).

## Prerequisites

- `bash` ≥4 on `PATH` (every supported host ships with it; macOS
  default `/bin/bash` 3.2 is too old — the skill checks Homebrew's
  `bash` first, then falls back to `/bin/bash` and warns).
- `uname -s` and `/etc/os-release` (Linux) or `sw_vers` (macOS)
  resolve — used for platform detection.
- For `install` mode: the host package manager (`brew`, `apt-get`,
  `dnf`, `pacman`, `apk`) is on `PATH`. The skill never installs a
  package manager itself.

## Instructions

1. **Resolve report path** under `$MAIN_ROOT/reports/maintainer-tool-bootstrap/`
   with a `YYYYMMDD_HHMMSS±HHMM` local-time-plus-offset stamp.

2. **Detect platform**:
   - `uname -s == Darwin` → `macos` (pkg manager: `brew`).
   - `uname -s == Linux`:
     - If `uname -r` contains `microsoft` or `WSL2` → `wsl2`, then
       fall through to inner-distro detection.
     - Source `/etc/os-release` and read `ID` and `ID_LIKE`:
       - `debian`/`ubuntu` (or `ID_LIKE=debian`) → `apt`.
       - `fedora`/`rhel`/`rocky`/`almalinux` (or
         `ID_LIKE=rhel fedora`) → `dnf`.
       - `arch`/`manjaro` (or `ID_LIKE=arch`) → `pacman`.
       - `alpine` → `apk`.
   - Anything else (Cygwin/MSYS native, etc.) → hard fail with
     "this plugin requires macOS, Linux, or WSL2".

3. **Pick mode** based on caller args (`audit` is the default):

   - `audit` — for each required tool: run `command -v <tool>` and
     `<tool> --version` (or the tool's idiomatic version flag), parse
     out the version, compare against the minimum. Emit JSON per
     [references/audit-format.md](references/audit-format.md). Exit
     `0` only if every **mandatory** tool is present and meets its
     minimum; exit `1` if any mandatory is missing/too-old; exit `2`
     if a required *optional* tool is missing (caller decides).

   - `recipe` — print platform-specific install recipes for every
     missing tool to stdout. No installations performed. Exit `0`.

   - `install` — refuse if `EUID == 0` and `--allow-root` was not
     passed (running the package manager as root inside an agent is
     too easy a footgun). Then iterate missing tools and shell out
     to the platform PM. After each install, re-run `command -v` and
     `<tool> --version` to verify. If verification fails, surface a
     hard error with the recipe URL from the table.

4. **Emit report** — write the JSON output to the report path and
   echo the path to stdout. Stderr carries a human-readable summary
   table.

For the full per-platform install matrix and verification snippets,
see [references/install-recipes.md](references/install-recipes.md).
For the JSON schema, see
[references/audit-format.md](references/audit-format.md).

## Output

- A JSON file at `$MAIN_ROOT/reports/maintainer-tool-bootstrap/<ts>-bootstrap.json`
  with `platform`, `mode`, `tools[]` (each with `name`, `required`,
  `found`, `version`, `min_version`, `status`, `install_recipe`),
  and `disposition` (`ok | needs_install | unsupported_platform |
  install_failed`).
- On stdout: the absolute path to the report file (and nothing else
  in `install`/`audit` modes; `recipe` mode prints the recipes).
- On stderr: a colored summary table with one row per tool.

## Error Handling

| Error | Action |
|-------|--------|
| Windows native (not WSL2) | Stop, exit `3`, print "macOS / Linux / WSL2 required" |
| Unknown Linux distro | Stop, exit `4`, print supported list, point to recipes doc |
| `install` mode as root without `--allow-root` | Stop, exit `5`, print the safety reason |
| Package manager missing on host | Stop, exit `6`, print the recipe to install the PM itself |
| Post-install `command -v` still fails | Stop, exit `7`, surface raw stderr from the install command |
| Network unreachable during `install` | Retry the install command once with 30s sleep; on second failure exit `8` |

## Examples

Initial host check (audit):
```
User: "what's missing on this host?"
→ Detect: macos → brew
→ Probe: gh 2.62.0 OK, git 2.45.0 OK, uv 0.5.1 OK, bash /opt/homebrew/bin/bash 5.2.32 OK,
   actionlint MISSING, docker MISSING
→ Report: reports/maintainer-tool-bootstrap/<ts>-bootstrap.json
   { "disposition": "needs_install", "missing": ["actionlint", "docker"] }
→ Exit 0 (mandatory all present; optionals missing)
```

Print recipe (no install):
```
User: "show me how to install zizmor + actionlint on Ubuntu"
→ recipe mode → stdout:
   apt-get install -y actionlint  # NOTE: not in default repos; download release binary
   uvx zizmor --help               # zizmor is invoked via uvx; nothing to install
```

Guided install:
```
User: "install whatever's missing"
→ install mode → brew install actionlint
→ Verify: command -v actionlint ✓ ; actionlint -version → 1.7.7
→ Re-emit audit JSON with new versions
→ Exit 0
```

## Scope

- ONLY interacts with the host package manager and the per-tool
  installers documented in
  [references/install-recipes.md](references/install-recipes.md).
- Does NOT touch user shell rc files (`~/.bashrc`, `~/.zshrc`); the
  package managers handle their own PATH additions.
- Does NOT install language toolchains beyond what's in the table
  (no Python interpreter setup, no Node, no Rust toolchain — those
  belong to the entrusted repo's own setup, not the maintainer).
- Does NOT modify the entrusted repo at all; this is purely a
  host-level capability check.
- Refuses Windows-native hosts even with `--force` — users must
  switch to WSL2.

## Resources

- [references/install-recipes.md](references/install-recipes.md) —
  per-platform package names, install commands, and direct-download
  URLs for tools not in any PM:
  - Mandatory tools (gh, git, uv, bash)
  - Optional tools (actionlint, docker, jq, trufflehog, gitleaks, hadolint, yamllint, plutil)
  - Per-platform installation matrix
  - Verification snippets
- [references/audit-format.md](references/audit-format.md) — the
  JSON schema the skill emits in `audit` mode:
  - Top-level disposition fields
  - Per-tool fields and status enum
  - Reading the report from a downstream skill
- Companion skills: `maintainer-config-lint` (uses several optional
  tools listed here), `workflow-scan` (uses zizmor + actionlint).
