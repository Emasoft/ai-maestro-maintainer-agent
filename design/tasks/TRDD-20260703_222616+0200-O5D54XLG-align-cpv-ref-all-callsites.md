---
trdd-id: O5D54XLG
title: Align CPV validator ref to @v2.152.1 across all pipeline callsites
column: complete
created: 2026-07-03T22:26:16+0200
updated: 2026-07-03T22:26:16+0200
current-owner: ai-maestro-maintainer-agent
task-type: infra
release-via: publish
delivery: direct-push
target-branch: main
test-requirements: [lint, typecheck]
audit-requirements: []
review-requirements: []
relevant-rules: []
parent-trdd: TRDD-K9M2X7Q4
supersedes: []
impacts: [ci-pipeline]
implementation-commits: [4a01864]
published-version: null
published-at: null
external-refs: ["github.com/Emasoft/claude-plugins-validation/releases/tag/v2.152.1"]
---

# TRDD-O5D54XLG — Align CPV validator ref to @v2.152.1 across all pipeline callsites

## STATE — READ THIS FIRST ON RESUME (authoritative) — 2026-07-03T22:26:16+0200

**Current state: fix COMMITTED (4a01864), awaiting v1.7.8 publish. NEXT ACTION: `python3 scripts/publish.py --patch` then flip this TRDD to `published`.**

- Closes the CPV-ref version skew that TRDD-K9M2X7Q4 flagged as a deferred follow-up
  (its STATE note: "release.yml is @v2.152.1 while publish.py + ci.yml stay @v2.143.0;
  aligning all three is a future TRDD").
- ci.yml + publish.py bumped @v2.143.0 -> @v2.152.1; committed 4a01864. Tree clean.
- Publish (v1.7.8) pending — on success, set `column: published`, add the bump commit
  to `implementation-commits`, set `published-version: 1.7.8`.

## Problem

v1.7.7 pinned only `.github/workflows/release.yml`'s CPV validator ref to the
release tag `@v2.152.1`. Two other pipeline callsites still fetched the validator
at the older `@v2.143.0`:

| File:line | Invocation | Ref before |
|---|---|---|
| `.github/workflows/release.yml:50` | `cpv-remote-validate plugin . --strict` | @v2.152.1 (already pinned in v1.7.7) |
| `scripts/publish.py:586` | `cpv-setup-branch-rules <slug>` | @v2.143.0 |
| `scripts/publish.py:806` | `cpv-remote-validate plugin . --strict` | @v2.143.0 |
| `scripts/publish.py:1038` | (docstring reference) | @v2.143.0 |
| `scripts/publish.py:1053` | `cpv-remote-validate plugin . --strict` | @v2.143.0 |
| `.github/workflows/ci.yml:151` | `cpv-remote-validate plugin . --strict` | @v2.143.0 |

Version skew across callsites means the local pre-push gate, the CI `validate`
gate, and the post-hoc release gate could enforce **different** validator
rulesets — an incoherent supply-chain posture, and the exact drift-class this
plugin's own workflow-pin doctrine guards against.

## Change

Bumped every `@v2.143.0` -> `@v2.152.1` (5 occurrences: 4 in publish.py incl. the
docstring, 1 in ci.yml). All six CPV callsites now sit on the single pinned tag
`@v2.152.1`, matching release.yml. A `# WHY:` pin-rationale comment was added above
the ci.yml callsite (it previously lacked one; mirrors release.yml's doctrine).

## Compatibility verification (at tag v2.152.1, before editing)

Confirmed both entry points and their subcommands/flags exist and are unbroken at
the target tag (source fetched via `gh api ... ?ref=v2.152.1`):

- `pyproject.toml [project.scripts]`: `cpv-remote-validate = scripts.remote_validation:main`,
  `cpv-setup-branch-rules = scripts.setup_branch_rules:main` — both present.
- `remote_validation.py`: `plugin` is a valid command alias (-> `validate_plugin`);
  positional `script` + optional `target` are parsed; `--strict` is forwarded to the
  target via `parse_known_args()` -> `extra` -> `script_argv.extend(extra)`. So
  `cpv-remote-validate plugin . --strict` is valid.
- `setup_branch_rules.py`: positional `repo` arg present; publish.py passes only the
  positional `<slug>` (no extra flags). So `cpv-setup-branch-rules <slug>` is valid.

No invocation would break at @v2.152.1 — the bump is safe.

## Verification

- `grep` confirms zero `@v2.143.0` remain in `scripts/` + `.github/`; all six refs
  read `@v2.152.1`.
- `ci.yml` + `release.yml` parse as valid YAML; `publish.py` parses as valid Python.
- Delivery: publish.py cuts the release (direct-push via its own pipeline; the repo's
  pre-push hook refuses any other push path).

## Notes and lessons learned
