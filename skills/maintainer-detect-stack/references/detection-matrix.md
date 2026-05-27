# Detection matrix — 10 dimensions

This is the canonical table the maintainer-detect-stack skill walks
each cycle. Each dimension has (a) a signal (the file or shell
test), (b) a value extraction, (c) which downstream skill consumes
the answer. Every detection is filesystem-driven — no LLM
judgement, no network calls.

## Table of Contents

- [1. Primary language](#1-primary-language)
- [2. Package manager / sub-detect](#2-package-manager--sub-detect)
- [3. Tool-versions manager](#3-tool-versions-manager)
- [4. CI presence](#4-ci-presence)
- [5. Dependabot](#5-dependabot)
- [6. Branch rules](#6-branch-rules)
- [7. Hooks present](#7-hooks-present)
- [8. Test framework](#8-test-framework)
- [9. Lint setup](#9-lint-setup)
- [10. Docs + TRDD/ADR](#10-docs--trddadr)
- [Suggestion-build rules](#suggestion-build-rules)
- [Worked example](#worked-example)

---

## 1. Primary language

| Signal (in priority order)   | Value           | Consumes               |
|------------------------------|-----------------|------------------------|
| `pyproject.toml` exists      | `python`        | workflow-bootstrap, maintainer-fix |
| `package.json` exists        | `node`          | workflow-bootstrap, T6 (Guardian) |
| `Cargo.toml` exists          | `rust`          | workflow-bootstrap     |
| `go.mod` exists              | `go`            | workflow-bootstrap     |
| `Gemfile` exists             | `ruby`          | workflow-bootstrap (generic template + note) |
| `composer.json` exists       | `php`           | workflow-bootstrap (generic + note) |
| `mix.exs` exists             | `elixir`        | workflow-bootstrap (generic + note) |
| `pubspec.yaml` exists        | `dart`          | workflow-bootstrap (generic + note) |
| none of the above            | `generic`       | workflow-bootstrap generic template |

When ≥ 2 markers are present (e.g. a Python repo with a small Node
frontend), pick the language whose source directory is deepest /
largest by file count and record the conflict in
`notes[]`. Same rule as `workflow-bootstrap`'s language detection.

```bash
PRIMARY="generic"
[ -f pyproject.toml ]   && PRIMARY="python"
[ -f package.json ]     && PRIMARY="${PRIMARY:-node}"
# (continue down the table…)
```

## 2. Package manager / sub-detect

| Primary | Signal                          | Value        |
|---------|---------------------------------|--------------|
| python  | `uv.lock` present               | `uv`         |
| python  | `pyproject.toml` has `[tool.poetry]` | `poetry` |
| python  | otherwise                       | `setuptools` |
| node    | `pnpm-lock.yaml` present        | `pnpm`       |
| node    | `yarn.lock` present             | `yarn`       |
| node    | otherwise                       | `npm`        |
| rust    | `Cargo.lock` present            | `cargo`      |
| go      | `go.sum` present                | `gomod`      |
| ruby    | `Gemfile.lock` present          | `bundler`    |
| else    | n/a                             | `none`       |

```bash
case "$PRIMARY" in
    python)
        if [ -f uv.lock ]; then PM=uv
        elif grep -q '^\[tool.poetry\]' pyproject.toml 2>/dev/null; then PM=poetry
        else PM=setuptools; fi ;;
    node)
        if [ -f pnpm-lock.yaml ]; then PM=pnpm
        elif [ -f yarn.lock ]; then PM=yarn
        else PM=npm; fi ;;
    rust) PM=cargo ;;
    go)   PM=gomod ;;
    ruby) PM=bundler ;;
    *)    PM=none ;;
esac
```

## 3. Tool-versions manager

| Signal             | Value     | Consumes |
|--------------------|-----------|----------|
| `.tool-versions`   | `asdf`    | workflow-bootstrap (pin setup-<lang> version) |
| `mise.toml` OR `.mise.toml` | `mise` | workflow-bootstrap |
| none               | `none`    | (default version) |

If both files exist, record both and prefer `mise.toml` (mise is
the actively-maintained successor to asdf). Note the conflict.

## 4. CI presence

| Signal                          | Value              |
|---------------------------------|--------------------|
| `.github/workflows/*.y[a]ml` matches | `present` + file list |
| empty or absent                 | `absent`           |

```bash
if compgen -G ".github/workflows/*.y*ml" > /dev/null; then
    CI_PRESENT=true
    CI_FILES="$(ls .github/workflows/*.y*ml 2>/dev/null)"
else
    CI_PRESENT=false
fi
```

Consumes: `workflow-bootstrap` (only runs if absent); `workflow-scan`
(only runs if present).

## 5. Dependabot

| Signal                              | Value      |
|-------------------------------------|------------|
| `.github/dependabot.yml` OR `.yaml` | `present` + ecosystems list |
| absent                              | `absent`   |

```bash
DEPENDABOT_FILE=""
for f in .github/dependabot.yml .github/dependabot.yaml; do
    [ -f "$f" ] && DEPENDABOT_FILE="$f" && break
done
if [ -n "$DEPENDABOT_FILE" ]; then
    ECOSYSTEMS="$(grep -E '^\s*package-ecosystem:' "$DEPENDABOT_FILE" \
                  | awk '{print $2}' | tr -d '"' | sort -u | paste -sd, -)"
fi
```

Consumes: `workflow-bootstrap` (seeds `dependabot.yml` if absent);
`maintainer-guardian` T2.

## 6. Branch rules

Chain `workflow-protect-branch SHOW`. If the chain succeeds, parse
the result from `$AGENT_DIR/.aimaestro/state/branch-rules.json`:

| Outcome                   | Value             |
|---------------------------|-------------------|
| ≥ 1 ruleset with `enforcement: active` | `active` |
| empty rulesets array      | `absent`          |
| chain failed (no auth, no admin) | `unknown`  |

Consumes: `maintainer-guardian` T3; `workflow-protect-branch APPLY`.

## 7. Hooks present

| Signal                                | Value       |
|---------------------------------------|-------------|
| `.git/hooks/pre-commit` is executable | + `pre-commit` |
| `.git/hooks/pre-push` is executable   | + `pre-push` |
| `.git/hooks/commit-msg` is executable | + `commit-msg` |
| `.githooks/` dir present              | + `githooks-dir` |
| `.pre-commit-config.yaml` present     | + `pre-commit-fwk` |
| `package.json` has `husky` dependency | + `husky` |

```bash
HOOKS=()
for h in pre-commit pre-push commit-msg; do
    [ -x ".git/hooks/$h" ] && HOOKS+=("$h")
done
[ -d ".githooks" ] && HOOKS+=("githooks-dir")
[ -f ".pre-commit-config.yaml" ] && HOOKS+=("pre-commit-fwk")
if [ -f package.json ] && grep -q '"husky"' package.json; then
    HOOKS+=("husky")
fi
```

Consumes: `maintainer-commit-msg-why` (suggests install if
`commit-msg` is absent).

## 8. Test framework

| Primary | Signal                                  | Value        |
|---------|-----------------------------------------|--------------|
| python  | `tests/` OR `test_*.py` files OR `[tool.pytest.ini_options]` | `pytest` |
| node    | `package.json` has `"jest"` dep         | `jest`       |
| node    | `package.json` has `"vitest"` dep       | `vitest`     |
| node    | `package.json` has `"mocha"` dep        | `mocha`      |
| rust    | always                                  | `cargotest`  |
| go      | `*_test.go` files exist                 | `gotest`     |
| ruby    | `spec/` dir                             | `rspec`      |
| else    | nothing matched                         | `none`       |

Consumes: `maintainer-fix` (Step 5 picks the right runner).

## 9. Lint setup

A list, not a single value — append every present signal:

| Signal                                  | Value            |
|-----------------------------------------|------------------|
| `ruff.toml` OR `[tool.ruff]` in `pyproject.toml` | `ruff`   |
| `mypy.ini` OR `[tool.mypy]`             | `mypy`           |
| `.eslintrc*`                            | `eslint`         |
| `.prettierrc*`                          | `prettier`       |
| `clippy.toml` OR clippy in `Cargo.toml` | `clippy`         |
| `.golangci.yml`                         | `golangci-lint`  |
| `.rubocop.yml`                          | `rubocop`        |

Consumes: `maintainer-fix` (Step 4 honors the repo's lint).

## 10. Docs + TRDD/ADR

Present-vs-missing inventory:

| File                       | Bucket            |
|----------------------------|-------------------|
| `README.md`                | docs              |
| `CHANGELOG.md`             | docs              |
| `CONTRIBUTING.md`          | docs              |
| `SECURITY.md`              | docs              |
| `CODE_OF_CONDUCT.md`       | docs              |
| `LICENSE` (or `LICENSE.md`/`.txt`) | docs       |
| `design/tasks/` directory  | `trdd_support.design_tasks` |
| `design/adrs/` directory   | `trdd_support.design_adrs`  |

```bash
DOCS_PRESENT=(); DOCS_MISSING=()
for f in README.md CHANGELOG.md CONTRIBUTING.md SECURITY.md \
         CODE_OF_CONDUCT.md LICENSE; do
    if [ -f "$f" ] || [ -f "$f.md" ] || [ -f "$f.txt" ]; then
        DOCS_PRESENT+=("$f")
    else
        DOCS_MISSING+=("$f")
    fi
done
TRDD_TASKS=false; TRDD_ADRS=false
[ -d "design/tasks" ] && TRDD_TASKS=true
[ -d "design/adrs" ]  && TRDD_ADRS=true
```

Consumes: future `maintainer-generate-docs` (when it exists);
this skill's `suggestions[]`.

---

## Suggestion-build rules

The suggestions list is the actionable output downstream skills
look at first.

| Condition                                              | Suggestion                                          |
|--------------------------------------------------------|-----------------------------------------------------|
| `ci_present == false`                                  | `{skill:"workflow-bootstrap"}`                      |
| `ci_present == true` AND `dependabot_present == false` | `{skill:"workflow-bootstrap", mode:"seed-dependabot"}` |
| `branch_rules == "unknown"` (auth ok, admin)           | `{skill:"workflow-protect-branch", mode:"APPLY"}`   |
| `commit-msg` not in `hooks_present` AND lang != generic | `{skill:"maintainer-commit-msg-why", mode:"install"}` |
| `README.md` in `docs_missing`                          | `{skill:"maintainer-generate-docs", file:"README.md"}` (not impl yet — record gap) |
| `is_node_repo == true` AND T6 baseline shows missing knobs | (Guardian already files the issue; do not duplicate) |

## Worked example

A Python project on uv with no CI:

```json
{
  "primary_language": "python",
  "package_manager": "uv",
  "tool_versions_manager": "none",
  "ci_present": false,
  "dependabot_present": false,
  "branch_rules": "absent",
  "hooks_present": ["pre-commit"],
  "test_framework": "pytest",
  "lint_setup": ["ruff", "mypy"],
  "docs_present": ["README.md", "LICENSE"],
  "docs_missing": ["CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md",
                   "CODE_OF_CONDUCT.md"],
  "trdd_support": {"design_tasks": false, "design_adrs": false},
  "suggestions": [
    {"skill": "workflow-bootstrap",
     "reason": "no .github/workflows/ files"},
    {"skill": "maintainer-commit-msg-why", "mode": "install",
     "reason": "no commit-msg hook present"}
  ],
  "notes": []
}
```
