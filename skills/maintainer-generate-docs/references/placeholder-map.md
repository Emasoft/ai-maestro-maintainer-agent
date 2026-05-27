# Placeholder source map — `maintainer-generate-docs`

Each `$VAR` in the templates resolves from one of the entrusted
repo's own metadata sources, in the order listed. First match
wins. If every source is empty, the skill writes the literal
string `<unset>` into the file and emits a `placeholder_warning`
in the JSON disposition — the caller MUST fix those before
publishing the docs.

## Table of contents

- [Placeholder reference](#placeholder-reference)
- [Resolution helpers (shell)](#resolution-helpers-shell)
- [Normalisation rules](#normalisation-rules)
- [Examples](#examples)
- [Caller overrides](#caller-overrides)

## Placeholder reference

| Placeholder | Description | Source order (first non-empty wins) |
|---|---|---|
| `$PROJECT_NAME` | Display name of the project | (1) `pyproject.toml` `[project].name` → (2) `package.json` `.name` → (3) `Cargo.toml` `[package].name` → (4) `go.mod` first `module` path's last segment → (5) `basename $(git rev-parse --show-toplevel)` |
| `$AUTHOR` | Primary author / current maintainer | (1) `pyproject.toml` `[project].authors[0].name` → (2) `package.json` `.author` (string or `.author.name`) → (3) `Cargo.toml` `[package].authors[0]` (split on `<`) → (4) `git config user.name` |
| `$EMAIL` | Author contact email | (1) `pyproject.toml` `[project].authors[0].email` → (2) `package.json` `.author.email` → (3) `Cargo.toml` `[package].authors[0]` (extract between `<>`) → (4) `git config user.email` |
| `$REPO_URL` | Canonical HTTPS URL of the repo | (1) `git remote get-url origin` (normalised — see below) → (2) `pyproject.toml` `[project.urls].Homepage` → (3) `package.json` `.repository.url` → (4) `<unset>` |
| `$REPO_OWNER` | Owner segment of the GitHub URL | Parsed from `$REPO_URL` (`https://github.com/OWNER/REPO` → `OWNER`); `<unset>` if URL is non-GitHub |
| `$REPO_NAME` | Repo segment of the GitHub URL | Parsed from `$REPO_URL` (`https://github.com/OWNER/REPO` → `REPO`); `<unset>` if URL is non-GitHub |
| `$CONTACT_EMAIL` | Code of conduct + SECURITY contact | (1) `--contact-email` CLI flag → (2) `$EMAIL` |
| `$LICENSE_SPDX` | SPDX identifier of the project's license | (1) `pyproject.toml` `[project].license.text` → (2) `package.json` `.license` → (3) `LICENSE` file first-line heuristic → (4) `MIT` (default) |
| `$YEAR` | Current year (for copyright lines) | `date +%Y` |
| `$DEFAULT_BRANCH` | Default branch of the repo | (1) `git symbolic-ref refs/remotes/origin/HEAD` → (2) `git config init.defaultBranch` → (3) `main` |
| `$TEST_COMMAND` | One-liner the contributor runs to verify the test suite | (1) `pyproject.toml` `[tool.pytest.ini_options]` present → `uv run pytest tests/ -v` → (2) `package.json` `.scripts.test` → `npm test` → (3) `Cargo.toml` present → `cargo test` → (4) `go.mod` present → `go test ./...` → (5) `make test` (if `Makefile` defines a `test` target) → (6) `<unset>` |

## Resolution helpers (shell)

```bash
# Project name
get_project_name() {
  if [ -f pyproject.toml ]; then
    python3 -c "import tomllib,sys; d=tomllib.load(open('pyproject.toml','rb')); print(d.get('project',{}).get('name',''))"
  elif [ -f package.json ]; then
    node -p "require('./package.json').name || ''" 2>/dev/null
  elif [ -f Cargo.toml ]; then
    python3 -c "import tomllib; d=tomllib.load(open('Cargo.toml','rb')); print(d.get('package',{}).get('name',''))"
  elif [ -f go.mod ]; then
    awk '/^module / {n=split($2,a,"/"); print a[n]; exit}' go.mod
  else
    basename "$(git rev-parse --show-toplevel)"
  fi
}

# Repo URL (HTTPS-normalised)
get_repo_url() {
  RAW="$(git remote get-url origin 2>/dev/null || true)"
  case "$RAW" in
    git@github.com:*)
      # git@github.com:owner/repo(.git) → https://github.com/owner/repo
      echo "https://github.com/${RAW#git@github.com:}" | sed 's/\.git$//'
      ;;
    https://*)
      echo "${RAW%.git}"
      ;;
    *)
      echo ""
      ;;
  esac
}
```

`pyproject.toml` parsing uses Python's built-in `tomllib`
(Python ≥3.11); avoid external deps so the skill is portable.

## Normalisation rules

- `$REPO_URL`: always normalised to `https://github.com/OWNER/REPO`
  (no trailing `.git`, no SSH form). If the remote is not GitHub
  (gitlab.com, bitbucket.org, self-hosted), the URL is kept
  verbatim and `$REPO_OWNER` / `$REPO_NAME` resolve to `<unset>`.
- `$AUTHOR`: if `git config user.name` contains an `<email>`
  segment by accident, strip it; emails go to `$EMAIL`.
- `$EMAIL`: noreply addresses (`*@users.noreply.github.com`) are
  considered VALID — they are GitHub's recommended privacy
  default. Do NOT warn about them.
- `$CONTACT_EMAIL`: the skill never invents an email — if `$EMAIL`
  is `<unset>` and the caller didn't pass `--contact-email`, the
  `CODE_OF_CONDUCT.md` and `SECURITY.md` outputs contain `<unset>`
  and the disposition flags a `placeholder_warning`.

## Examples

### Python project

```
pyproject.toml:
  [project]
  name = "my-django-app"
  authors = [{ name = "Jane Doe", email = "jane@example.com" }]

git remote get-url origin:
  git@github.com:janedoe/my-django-app.git

→ $PROJECT_NAME   = "my-django-app"
→ $AUTHOR         = "Jane Doe"
→ $EMAIL          = "jane@example.com"
→ $REPO_URL       = "https://github.com/janedoe/my-django-app"
→ $REPO_OWNER     = "janedoe"
→ $REPO_NAME      = "my-django-app"
→ $CONTACT_EMAIL  = "jane@example.com"
→ $TEST_COMMAND   = "uv run pytest tests/ -v"
```

### Node project with no author field

```
package.json:
  { "name": "my-cli", "scripts": { "test": "vitest" } }

git config user.name:   "Acme Bot"
git config user.email:  "bot@acme.io"

→ $PROJECT_NAME   = "my-cli"
→ $AUTHOR         = "Acme Bot"
→ $EMAIL          = "bot@acme.io"
→ $TEST_COMMAND   = "npm test"   # resolves to vitest under the hood
```

### Bare repo (no manifest, no remote)

```
→ All sources empty
→ $PROJECT_NAME   = basename(repo-root)
→ $AUTHOR         = git config user.name (or "<unset>")
→ $EMAIL          = git config user.email (or "<unset>")
→ $REPO_URL       = "<unset>"  (placeholder_warning)
→ $TEST_COMMAND   = "<unset>"  (placeholder_warning)
```

## Caller overrides

The caller may pass any of these CLI flags to force a value:

```
--project-name <name>
--author <name>
--email <addr>
--repo-url <url>
--contact-email <addr>
--license <spdx>
--test-command <cmd>
```

A flag value always wins over autodetected values. Flags are how
the caller resolves `<unset>` warnings without editing the
generated files by hand.
