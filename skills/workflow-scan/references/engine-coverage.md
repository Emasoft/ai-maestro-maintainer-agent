<!-- cspell:ignore biuld lastest -->
<!-- `biuld` and `lastest` are DELIBERATE misspellings — they are the sample
     broken workflows this page teaches you to recognize. Correcting them would
     destroy the lesson, so they are ignored here rather than in the global
     dictionary: a real `biuld` typo anywhere else must still fail the build. -->

# Engine coverage — who catches what

## Table of Contents

- [Division of labour](#division-of-labour)
- [What actionlint alone catches](#what-actionlint-alone-catches)
- [actionlint rule kinds — the `kind` field](#actionlint-rule-kinds--the-kind-field)
- [Beyond the workflows directory: composite actions](#beyond-the-workflows-directory-composite-actions)
- [Machine-readable actionlint output](#machine-readable-actionlint-output)
- [actionlint exit codes](#actionlint-exit-codes)
- [actionlint config — `.github/actionlint.yaml`](#actionlint-config--githubactionlintyaml)
- [`act` — parse-only, never execute](#act--parse-only-never-execute)

## Division of labour

Three engines run in `workflow-scan`. They overlap very little, so a
finding missing from one is NOT evidence the workflow is clean —
always read all three sections of the report.

| Engine | Owns | Blind to |
|---|---|---|
| **zizmor** | Security audits: `template-injection`, `unpinned-uses`, `excessive-permissions`, `artipacked` (credential persistence), `dangerous-triggers` | YAML schema errors, typos, dead `needs:` edges, shell bugs |
| **actionlint** | Schema + correctness: runner labels, cron, `needs:` graph, expression types, action inputs, shell bugs via shellcheck | Supply-chain posture; it does not care that an action is unpinned |
| **Sentinel** (`scripts/sentinel_scan.py`) | Structural classes the other two skip: build/publish credential exposure, IDE-config injection (32 rules) | Everything the other two own |

Practical consequence: a workflow can be **zizmor-clean and still
broken** (bad cron, undefined `needs:` target, unquoted shell var), and
**actionlint-clean and still unsafe** (unpinned third-party action,
injectable `run:` block).

## What actionlint alone catches

These classes are actionlint's, and are worth calling out explicitly in
the report because neither zizmor nor Sentinel will surface them:

| Class | Example defect | Why it bites |
|---|---|---|
| Runner label | `runs-on: ubuntu-lastest` | Job never gets scheduled; the run hangs as queued |
| Cron syntax | `cron: '0 0 * * 8'` (weekday 8) | Schedule silently never fires |
| `needs:` graph | `needs: biuld`, or a cycle between two jobs | Workflow refuses to start |
| Expression type | `if: ${{ 'true' }}` — a *string*, which is truthy always | Condition is always taken; the guard is decorative |
| Action inputs | Unknown or missing required `with:` key | Step fails at runtime, after the job has burned minutes |
| Shell (shellcheck) | `run: echo $VAR` — unquoted, word-splits | Silent wrong behaviour on values with spaces |
| Glob patterns | `paths: ['**.js']` | Accepted, but `'**/*.js'` is the explicit conventional form |

Enable the shell layer — it is the highest-yield of the set. actionlint
shells out to `shellcheck` for every `run:` block when `shellcheck` is
on PATH (Homebrew formula `shellcheck`), and to `pyflakes` for
`shell: python` blocks.

## actionlint rule kinds — the `kind` field

Each JSON finding carries a `kind` — the name of the actionlint rule that
fired — and that is the field to group the report on (the analogue of
zizmor's `audit`). The rule names actionlint reports include:

| `kind` | What it flags |
|---|---|
| `syntax-check` | YAML schema errors — unexpected/missing keys, bad nesting, wrong types |
| `expression` | `${{ }}` type errors, unknown context access, bad function calls |
| `events` | trigger/`on:` mistakes, invalid cron |
| `glob` | malformed `paths:` / `paths-ignore:` patterns |
| `runner-label` | unknown `runs-on:` label (typo or unrecognised) |
| `job-needs` | undefined `needs:` target, cyclic `needs:` graph |
| `action` | unknown action input, missing required `with:` key |
| `shellcheck` | shell bugs in `run:` blocks (delegated to shellcheck) |
| `pyflakes` | Python bugs in `shell: python` blocks |
| `credentials` | hardcoded credentials in `container`/`services` blocks |
| `permissions` | invalid `permissions:` scope name or value |
| `workflow-call` | reusable-workflow input/secret/output mismatches |
| `deprecated-commands` | deprecated workflow commands (e.g. `set-output`) |

This is not the exhaustive set — actionlint's Checks page is the
authoritative list — but these are the kinds a workflow audit meets most.
Group the report on `kind` and cite it in each finding, never line-scrape
the human-readable format.

## Beyond the workflows directory: composite actions

`workflow-scan` scopes to `.github/workflows/`, but a repo's own
**composite actions** (`.github/actions/<name>/action.yml` with
`runs.using: composite`) carry `run:` steps that have the *same*
expression-injection exposure as a workflow — and they live OUTSIDE the
scanned directory, so a workflows-only scan is blind to them. zizmor and
actionlint can both audit an `action.yml` when pointed at it directly.
When a repo defines local composite (or Docker/JS) actions, note in the
report that they are an un-scanned injection + supply-chain surface and,
if the caller wants them covered, run the engines against
`.github/actions/**/action.yml` as a follow-up. Do not silently imply the
`.github/workflows/`-only scan cleared the whole repo.

## Machine-readable actionlint output

Prefer structured output over the human-readable default — it merges
into the report cleanly and does not need line-scraping:

```bash
actionlint -format '{{json .}}' .github/workflows/ci.yml
```

Each element carries `message`, `filepath`, `line`, `column`,
`kind` (the rule that fired), and a `snippet`. `kind` is the field to
group on in the report, exactly as `audit` is for zizmor.

SARIF is also available for GitHub code-scanning upload:

```bash
actionlint -format sarif .github/workflows/ci.yml
```

Use SARIF only when the caller explicitly wants a code-scanning upload;
`workflow-scan` itself is read-only and does not upload.

## actionlint exit codes

| Code | Meaning |
|---|---|
| 0 | Clean — no findings |
| 1 | Findings present |
| 2 | Fatal — unparseable file, bad config, bad CLI args |

Exit 2 is NOT "the workflow has problems" — it means actionlint could
not run. Surface it as a tool error, never as a clean scan.

## actionlint config — `.github/actionlint.yaml`

Optional, and absent on most repos. It matters in exactly three cases:

```yaml
# .github/actionlint.yaml
self-hosted-runner:
  labels:
    - gpu-runner
    - my-custom-runner

shellcheck:
  enable: true
  shell: bash

pyflakes:
  enable: true
```

1. **Self-hosted runners.** Without the `self-hosted-runner.labels`
   list, actionlint reports every custom label as an unknown runner —
   a wall of false positives. If the scan produces unknown-label
   findings on a repo that self-hosts, the fix is this config file, NOT
   suppressing the rule.
2. **Shell linting.** Explicitly enable/disable the shellcheck layer,
   and pin the shell dialect.
3. **Rule ignores.** An `ignore:` list exists. Treat it as a smell —
   the same discipline as `zizmor.yml` suppression: every entry cites a
   PR or issue number that justifies it, and blanket ignores are never
   acceptable.

Read the config if present, and say so in the report header — a scan
run under an `ignore:` list is not a clean scan, and the report must
not imply that it is.

## `act` — parse-only, never execute

`act` (nektos/act) runs workflows locally in Docker. Two of its modes
are safe on an entrusted repo, and the rest are not:

```bash
act -l          # list jobs/events — parses every workflow, executes nothing
act -n          # dry run — parse + plan, executes nothing (alias: --dryrun)
```

**Never run bare `act`, `act push`, `act pull_request`, or `act -j
<job>` on an entrusted repo.** Those EXECUTE the repository's own
workflow code — third-party actions, `run:` blocks, and all — on the
maintainer's machine, inside a container with the local Docker socket
in reach. The repo is exactly the artifact under audit; running it is
the one thing an auditor must not do. A workflow that a scan flagged as
injectable is a workflow you have just volunteered to execute.

`act -n` earns its keep as a cheap third parser: it fails on structural
errors that a plain YAML load accepts. It requires Docker running, so
treat it as optional — if Docker is absent, skip it and note the skip.
It never replaces zizmor or actionlint.
