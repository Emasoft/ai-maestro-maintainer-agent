# Runner labels — the valid set, retirements, and the "clean scan, broken run" gap

`runs-on:` names a GitHub-hosted (or self-hosted) runner. actionlint
validates the label against its **bundled** list, so it catches a typo
(`ubuntu-lastest`) but can be blind to a label GitHub has since RETIRED —
that is the audit gap this file closes.

## Table of Contents

- [Why this matters to an audit](#why-this-matters-to-an-audit)
- [Valid GitHub-hosted labels (dated snapshot)](#valid-github-hosted-labels-dated-snapshot)
- [Retired and deprecated runners](#retired-and-deprecated-runners)
- [The gap: a retired label passes lint but fails the run](#the-gap-a-retired-label-passes-lint-but-fails-the-run)
- [Self-hosted labels and false positives](#self-hosted-labels-and-false-positives)

## Why this matters to an audit

Two distinct findings hide in `runs-on:`:

1. **Typo** — `ubuntu-lastest`. actionlint's `runner-label` rule catches
   this deterministically (`label "ubuntu-lastest" is unknown`). It is a
   correctness finding: the job never schedules and the run hangs queued.
2. **Retired label** — a label that WAS valid and is now removed
   (`macos-13`). Whether actionlint flags it depends on how current its
   bundled label list is; a lint run against an older actionlint can be
   green while the workflow is already dead on GitHub's side. Confirm the
   label against GitHub's live runner docs, not only against the linter.

Because runner labels move over time, treat the tables below as a
**dated snapshot** and re-verify against GitHub's runner documentation on
each audit — the durable facts are the *retirements* and the
architecture direction, not the exact version numbers.

## Valid GitHub-hosted labels (dated snapshot)

Snapshot as of the last update to this file; re-verify before asserting a
label is invalid.

| OS | Labels |
|---|---|
| Ubuntu | `ubuntu-latest` (tracks 24.04), `ubuntu-24.04`, `ubuntu-22.04` |
| Windows | `windows-latest` (tracks 2022), `windows-2025`, `windows-2022` |
| macOS (Apple Silicon) | `macos-latest` (tracks 15), `macos-15`, `macos-14`, `macos-26` (preview) |
| ARM64 (Linux/Win) | `ubuntu-latest-arm64`, `ubuntu-24.04-arm64`, `windows-latest-arm64` — free for PUBLIC repos; private needs an Enterprise plan |
| Larger macOS | `macos-15-xlarge`, `macos-14-xlarge` (M2 Pro, GPU) |
| GPU | `gpu-t4-4-core` (NVIDIA T4) — needs a Team/Enterprise plan |

`-latest` labels float: `ubuntu-latest` moving from 22.04 to 24.04 has
silently changed behaviour for many repos. A workflow that must be
reproducible should pin an explicit version label, not `-latest`.

## Retired and deprecated runners

Durable facts (these do NOT drift back):

| Label | Status | Why it is a finding |
|---|---|---|
| `macos-13` | RETIRED (Nov 14 2025), Intel x86_64 | job fails to schedule — hard error |
| `macos-12` | RETIRED, Intel x86_64 | same |
| `macos-15-intel`, `macos-14-large`, `macos-15-large` | Intel, long-term deprecated | Apple Silicon (ARM64) is required after Fall 2027 — plan migration |

Direction of travel: Intel macOS runners are being wound down; new macOS
work targets Apple Silicon (`macos-15` / `macos-latest`). Flag any Intel
macOS label as a currency finding even while it still runs.

## The gap: a retired label passes lint but fails the run

The load-bearing audit insight: **a syntactically-valid-but-retired label
is a real defect a lint-clean scan can miss.** actionlint answers "is this
a label I know about?", not "does GitHub still offer this runner today?".
When the report shows zero `runner-label` findings, that is NOT proof the
runners are current — cross-check any pinned OS version against the
retirement table above and GitHub's live docs. A job on `macos-13` is
broken regardless of what the linter said.

For multi-architecture builds the correct shape is a matrix over the
runner label (e.g. an `ubuntu-latest` row and an `ubuntu-latest-arm64`
row), with the architecture read from the matrix value — never a single
retired label.

## Self-hosted labels and false positives

A repo that self-hosts drowns in `runner-label` false positives unless
its custom labels are declared. The fix is the actionlint config, NOT
suppressing the rule (see
[engine-coverage.md — actionlint config](engine-coverage.md#actionlint-config--githubactionlintyaml)):

```yaml
# .github/actionlint.yaml
self-hosted-runner:
  labels:
    - gpu-runner
    - arm-runner
    - on-premises
```

If a scan produces a wall of unknown-label findings on a repo that is
known to self-host, read this config before reporting — an absent
`self-hosted-runner.labels` list is the cause, and the findings are
noise, not defects.
