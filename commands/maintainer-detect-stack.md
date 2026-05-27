---
description: Detect the maintained repo's language, package manager, CI presence, branch-rule state, test framework, lint setup, missing docs. Writes a fingerprint JSON for downstream skills to self-configure.
argument-hint: "[--refresh] [--json]"
---

Fingerprint the maintained repo across 10 dimensions and write
the result to `$AGENT_DIR/.aimaestro/state/stack-fingerprint.json`.

Loads skill: **maintainer-detect-stack**

Dimensions captured:

1. **Primary language** — Python / Node / Rust / Go / Ruby / PHP
   / Elixir / Dart / generic. Sub-detection: pnpm vs yarn vs npm
   for Node; poetry vs uv vs setuptools for Python.
2. **Tool-versions manager** — `.tool-versions` (asdf) or
   `mise.toml`.
3. **CI presence** — `.github/workflows/` files.
4. **Dependabot** — `.github/dependabot.yml` ecosystems.
5. **Branch-rule state** — current `default-branch-ruleset` via
   `workflow-protect-branch SHOW`.
6. **Pre-commit / pre-push hooks** — `.githooks/`,
   `.pre-commit-config.yaml`, Husky.
7. **Test framework** — pytest / jest / vitest / go test / cargo
   test / rspec.
8. **Lint setup** — ruff / mypy / eslint / prettier / clippy /
   golangci-lint config files.
9. **Existing docs** — README / CHANGELOG / CONTRIBUTING /
   SECURITY / CODE_OF_CONDUCT — which exist, which are missing.
10. **TRDD / ADR support** — `design/tasks/`? `design/adrs/`?

The output JSON also includes a `suggestions` array:
`workflow-bootstrap can scaffold CI`, `maintainer-generate-docs
can fill missing docs`, `maintainer-commit-msg-why can install
the commit hook`, etc.

Downstream skills (workflow-bootstrap, maintainer-fix,
maintainer-secrets-scan) read this fingerprint to self-configure
per-cycle defaults — no need to re-detect on every invocation.

The fingerprint is regenerated cheaply on each patrol cycle, so
changes (e.g. user adds a `.tool-versions`) are picked up.

Schema: see
`skills/maintainer-detect-stack/references/fingerprint-schema.json`
— JSON Schema 2020-12 compatible.
