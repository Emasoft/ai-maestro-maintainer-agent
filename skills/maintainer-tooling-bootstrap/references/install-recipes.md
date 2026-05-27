# Install recipes — `maintainer-tooling-bootstrap`

Per-platform install commands for every tool the maintainer agent
(and its sister skills) may need. The skill picks the column that
matches the host and runs the cell verbatim; humans can copy the
same cell into a terminal.

## Table of Contents

- [Platform IDs](#platform-ids)
- [Mandatory tools](#mandatory-tools)
- [Optional tools](#optional-tools)
- [Verification snippets](#verification-snippets)
- [Direct-download fallback URLs](#direct-download-fallback-urls)

## Platform IDs

| ID         | Host                                    | Package manager  |
|------------|-----------------------------------------|------------------|
| `macos`    | macOS 12+ (Intel + Apple Silicon)       | `brew`           |
| `apt`      | Debian 11+, Ubuntu 22.04+               | `apt-get`        |
| `dnf`      | Fedora 38+, RHEL/Rocky/Alma 9+          | `dnf`            |
| `pacman`   | Arch, Manjaro                           | `pacman`         |
| `apk`      | Alpine 3.18+                            | `apk`            |
| `wsl2`     | Windows 10/11 with WSL2 + Linux distro  | (inner distro's) |

Unsupported (skill exits `3`): Windows native, Cygwin, MSYS2 without
WSL2, FreeBSD/OpenBSD, AIX, Solaris.

## Mandatory tools

These four must be present at the listed minimum before any other
maintainer skill will run.

### `gh` (≥ 2.40)

| Platform | Command |
|----------|---------|
| `macos`  | `brew install gh` |
| `apt`    | `type -p curl >/dev/null \|\| apt-get install -y curl; curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \| dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list && apt-get update && apt-get install -y gh` |
| `dnf`    | `dnf install -y dnf-plugins-core && dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo && dnf install -y gh` |
| `pacman` | `pacman -S --noconfirm github-cli` |
| `apk`    | `apk add --no-cache github-cli` |
| `wsl2`   | (use inner distro's row) |

### `git` (≥ 2.30)

| Platform | Command |
|----------|---------|
| `macos`  | `brew install git` |
| `apt`    | `apt-get install -y git` |
| `dnf`    | `dnf install -y git` |
| `pacman` | `pacman -S --noconfirm git` |
| `apk`    | `apk add --no-cache git` |

### `uv` (≥ 0.4)

| Platform | Command |
|----------|---------|
| `macos`  | `brew install uv` |
| `apt`    | `curl -LsSf https://astral.sh/uv/install.sh \| sh` (uv ships its own installer; not in Debian repos) |
| `dnf`    | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `pacman` | `pacman -S --noconfirm uv` |
| `apk`    | `apk add --no-cache curl && curl -LsSf https://astral.sh/uv/install.sh \| sh` |

### `bash` (≥ 4)

| Platform | Command |
|----------|---------|
| `macos`  | `brew install bash` (system `/bin/bash` is 3.2; the skill uses the Homebrew copy when present) |
| `apt`    | (already present at 5.x; no action needed) |
| `dnf`    | (already present at 5.x) |
| `pacman` | (already present at 5.x) |
| `apk`    | `apk add --no-cache bash` (Alpine ships only `ash` by default) |

## Optional tools

These are only required by some maintainer skills; see the per-skill
matrix at the end of this file.

### `actionlint` (≥ 1.6) — for `workflow-scan`, `workflow-fix-safe`

| Platform | Command |
|----------|---------|
| `macos`  | `brew install actionlint` |
| `apt`    | Download release binary from `https://github.com/rhysd/actionlint/releases/latest` (not packaged) |
| `dnf`    | Download release binary (not packaged) |
| `pacman` | `pacman -S --noconfirm actionlint` (in `extra/`) |
| `apk`    | Download release binary (not packaged) |

### `docker` (any modern) — for `maintainer-sandbox`

| Platform | Command |
|----------|---------|
| `macos`  | `brew install --cask docker` (Docker Desktop) or `brew install --cask orbstack` (lighter alternative) |
| `apt`    | `apt-get install -y docker.io` (or follow Docker's official engine repo) |
| `dnf`    | `dnf install -y docker` |
| `pacman` | `pacman -S --noconfirm docker` |
| `apk`    | `apk add --no-cache docker` |

After install: `systemctl enable --now docker` (Linux) or open the
Docker.app once (macOS). Add the user to the `docker` group on Linux
to avoid `sudo`: `usermod -aG docker $USER` (re-login required).

### `jq` (≥ 1.6) — for report-rendering helpers

| Platform | Command |
|----------|---------|
| `macos`  | `brew install jq` |
| `apt`    | `apt-get install -y jq` |
| `dnf`    | `dnf install -y jq` |
| `pacman` | `pacman -S --noconfirm jq` |
| `apk`    | `apk add --no-cache jq` |

### `yamllint` (≥ 1.32) — for `maintainer-config-lint`

Always invoke as `uvx yamllint <file>` so no install is needed; the
table below is for users who prefer a system-wide package.

| Platform | Command |
|----------|---------|
| `macos`  | `brew install yamllint` |
| `apt`    | `apt-get install -y yamllint` |
| `dnf`    | `dnf install -y yamllint` |
| `pacman` | `pacman -S --noconfirm yamllint` |
| `apk`    | `apk add --no-cache yamllint` |

### `hadolint` (≥ 2.12) — for `maintainer-config-lint` (Dockerfile)

| Platform | Command |
|----------|---------|
| `macos`  | `brew install hadolint` |
| `apt`    | Download release binary from `https://github.com/hadolint/hadolint/releases/latest` |
| `dnf`    | Download release binary |
| `pacman` | `pacman -S --noconfirm hadolint` (AUR via `yay`) |
| `apk`    | `apk add --no-cache hadolint` (community repo) |

### `plutil` — for `maintainer-config-lint` (Plist)

| Platform | Command |
|----------|---------|
| `macos`  | (ships with macOS — no install needed) |
| All Linux | Not available; the lint skill falls back to `xmllint --noout` |

### `trufflehog` (≥ 3.x) — optional for `maintainer-secrets-scan`

| Platform | Command |
|----------|---------|
| `macos`  | `brew install trufflehog` |
| `apt`    | `curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh \| sh -s -- -b /usr/local/bin` |
| `dnf`    | (same install.sh as apt) |
| `pacman` | AUR: `yay -S trufflehog` |
| `apk`    | (same install.sh as apt) |

### `gitleaks` (≥ 8.x) — optional fallback for `maintainer-secrets-scan`

| Platform | Command |
|----------|---------|
| `macos`  | `brew install gitleaks` |
| `apt`    | Download release binary from `https://github.com/gitleaks/gitleaks/releases/latest` |
| `dnf`    | Download release binary |
| `pacman` | AUR: `yay -S gitleaks` |
| `apk`    | Download release binary |

## Verification snippets

After every install, the skill runs the corresponding probe and
parses the version. Each probe MUST exit `0` for the install to be
considered successful.

```bash
gh --version          # "gh version 2.62.0 (2024-11-06)"
git --version         # "git version 2.45.0"
uv --version          # "uv 0.5.1 (a14e6c0d6 …)"
bash --version | head -n1  # "GNU bash, version 5.2.32(1)-release …"

actionlint -version   # "1.7.7" on stdout
docker version --format '{{.Server.Version}}'  # "27.3.1"
jq --version          # "jq-1.7.1"
yamllint --version    # "yamllint 1.35.1"
hadolint --version    # "Haskell Dockerfile Linter 2.12.0-no-git"
plutil -lint /dev/null 2>&1 | head -n1   # macOS: "/dev/null: OK"
trufflehog --version  # "trufflehog 3.85.1"
gitleaks version      # "v8.21.2"
```

Use `command -v <tool>` before the version probe — it returns `0` if
the binary is on `PATH` and `1` otherwise, without spawning a shell.

## Direct-download fallback URLs

For tools not in a host's package manager, download the latest
release tarball from these URLs (each is a GitHub `/releases/latest`
which serves the canonical version):

| Tool        | URL |
|-------------|-----|
| `actionlint`| <https://github.com/rhysd/actionlint/releases/latest> |
| `hadolint`  | <https://github.com/hadolint/hadolint/releases/latest> |
| `trufflehog`| <https://github.com/trufflesecurity/trufflehog/releases/latest> |
| `gitleaks`  | <https://github.com/gitleaks/gitleaks/releases/latest> |
| `gh`        | <https://github.com/cli/cli/releases/latest> |
| `uv`        | <https://github.com/astral-sh/uv/releases/latest> |

The skill never auto-downloads from these — too many archive-shape
variations across platforms. Instead it prints the URL and asks the
user to install manually.

## Per-skill required tool matrix

| Skill                       | Required tools (above mandatory)         |
|-----------------------------|------------------------------------------|
| `workflow-scan`             | `actionlint`, `jq`; `uvx zizmor` (no install) |
| `workflow-fix-safe`         | `actionlint`                             |
| `workflow-pin-actions`      | (mandatory only)                         |
| `workflow-protect-branch`   | (mandatory only)                         |
| `workflow-bootstrap`        | `actionlint`                             |
| `maintainer-sandbox`        | `docker`                                 |
| `maintainer-guardian`       | (mandatory only)                         |
| `maintainer-triage`         | (mandatory only)                         |
| `maintainer-config-lint`    | `yamllint`, `hadolint` (optional `plutil` on macOS) |
| `maintainer-secrets-scan`*  | `trufflehog` OR `gitleaks`               |

`*` = future skill; listed for completeness.
