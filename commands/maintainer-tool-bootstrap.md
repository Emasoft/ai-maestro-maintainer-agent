---
description: Audit, install, or print install-recipes for the maintainer agent's required tools (gh, git, uv, zizmor, actionlint, docker, trufflehog, gitleaks) — cross-platform (macOS / Linux / WSL2).
argument-hint: "[audit|install|recipe]"
---

Verify the host has every required tool the maintainer agent's
skills need. Three modes:

- `audit` (default) — read-only check. Lists each tool, its
  version (or "missing"), and the install-recipe URL for the
  current platform. Exits 0 if all mandatory tools are present.
- `install` — install missing tools via the platform PM. Refuses
  to run as root unless `--allow-root`. Verifies the install
  succeeded by re-running `command -v <tool>` after.
- `recipe` — print install recipes for the current platform
  WITHOUT doing anything; the user copy-pastes the commands.

Loads skill: **maintainer-tool-bootstrap**

Mandatory tools (agent will fail-fast without them):
- `gh` (≥ 2.4) — authentication + REST/GraphQL
- `git` (≥ 2.30)
- `uv` (≥ 0.4) — Python pkg / venv management
- `bash` (≥ 4)

Optional tools (per skill):
- `zizmor` — via `uvx` (no host install needed)
- `actionlint` — workflow YAML linter (Go binary)
- `jq` — JSON in shell
- `docker` — maintainer-sandbox harness
- `trufflehog` — maintainer-secrets-scan preferred backend
- `gitleaks` — maintainer-secrets-scan secondary backend

Platform detection:
- macOS (any arch) → `brew install <pkg>`
- Linux Debian/Ubuntu → `apt-get install <pkg>` (some require
  GH-releases download)
- Linux Fedora/RHEL → `dnf install <pkg>`
- Linux Arch → `pacman -S <pkg>`
- Linux Alpine → `apk add <pkg>`
- Windows-WSL2 → falls back to Linux distro path
- Windows native → hard fail; this plugin requires macOS / Linux
  / WSL2 (per Audit E MINOR-3)

Full per-platform install table:
`skills/maintainer-tool-bootstrap/references/install-recipes.md`

Output schema:
`skills/maintainer-tool-bootstrap/references/audit-format.md`
(JSON with `tools[].name`, `tools[].present`, `tools[].version`,
`tools[].install_command`).
