---
name: maintainer-dockerfile-audit
description: 'Audit and harden Dockerfiles that ALREADY EXIST in an entrusted repo — unpinned base images, root USER, missing HEALTHCHECK, secrets baked into layers, single-stage bloat, layer-cache misses, build-context leaks. Runs hadolint, Checkov, Trivy and dive, classifies every finding as fix-or-documented-suppress, then re-scans to prove green. Trigger with "audit the Dockerfile", "harden this container image", "Checkov is failing CI", "Trivy flagged our Dockerfile", "why does CKV_DOCKER_2 fire", "lint our Dockerfiles", or "is this image running as root".'
license: Apache-2.0
metadata:
  version: "1.0.0"
---

# maintainer-dockerfile-audit — audit and harden existing Dockerfiles

## Overview

The maintainer inherits Dockerfiles it did not write. This skill is an
AUDIT, not an authoring tool: it reads container images that already
exist in an entrusted repo, finds what is wrong, and fixes it. Authoring
recipes appear only as *remediation templates* — the target is always an
existing file.

Two rules carry the whole skill:

1. **Applicability before severity.** A finding is only a finding if the
   check applies to *this* image. An ephemeral run-once tool container
   and a long-running shipped service fail the same rule for completely
   different reasons. Read the Dockerfile and learn what it IS before
   you rank what is wrong with it.
2. **Fix, or suppress with a documented rationale — never suppress to go
   green.** Silencing a rule you do not understand converts a security
   finding into a lie. See
   [suppression-policy](references/suppression-policy.md).

This repo is its own worked example: `scripts/sandbox/dockerfiles/*.Dockerfile`
failed CI on Checkov + Trivy, and the fix was to genuinely harden two
policies (pinned base tag, non-root `USER`) while suppressing exactly one
inapplicable policy (`HEALTHCHECK`) with the reason written into BOTH
`.mega-linter.yml` and `.trivyignore`.

## Prerequisites

- `docker` — **the only hard requirement**. Every scanner below runs as a
  container, so no host installs and no version drift with CI.
- `git` — to enumerate tracked Dockerfiles.
- Host binaries (`hadolint`, `checkov`, `trivy`, `dive`) are OPTIONAL. If
  one is on PATH, prefer it for speed; otherwise use the container form.
  Never make the audit depend on a host install.

## Instructions

1. **Discover the targets.** Dockerfiles hide under many names:

   ```bash
   git ls-files | grep -iE '(^|/)(Dockerfile|Containerfile)([.-].*)?$|\.Dockerfile$'
   ```

2. **Read each Dockerfile end-to-end before scanning it.** Classify it —
   this decides which findings are even applicable:

   | Image kind | Lives how long | HEALTHCHECK applies | Non-root applies |
   |---|---|---|---|
   | Shipped long-running service | Indefinitely, takes traffic | YES | YES |
   | Ephemeral run-once tool container | Runs one command, exits | NO | YES |
   | Build/CI stage (multi-stage builder) | Discarded at build end | NO | Often NO |
   | Throwaway sidecar (proxy, capture) | Torn down with the harness | NO | YES |

   Non-root and pinned-base apply almost everywhere. HEALTHCHECK is the
   check most often *inapplicable* — and the one most often wrongly
   silenced.

3. **Run the scanner matrix.** Four tools, four non-overlapping jobs. Full
   invocations, exit codes and the complete verified check-ID catalogue
   are in [scanner-matrix](references/scanner-matrix.md).

   | Tool | Answers | Typical IDs |
   |---|---|---|
   | hadolint | Is the Dockerfile well-written? | `DL3008`, `DL3016` |
   | Checkov | Does it violate container policy? | `CKV_DOCKER_*` |
   | Trivy (`config`) | Same policy, second opinion | `DS-0001`, `DS-0002` |
   | dive | Where is the image wasting space? | efficiency score |

   hadolint and Checkov/Trivy disagree by design — hadolint lints the
   *source*, Checkov and Trivy assert *policy*. Run both; a clean hadolint
   run says nothing about whether the image runs as root.

4. **Classify every finding** against
   [audit-checklist](references/audit-checklist.md), which is organised as
   *what to check → what is wrong → how to fix*:

   | Severity | Class |
   |---|---|
   | CRITICAL | Secret baked into a layer; credential in `ENV`/`ARG` |
   | HIGH | Runs as root; unpinned or `:latest` base; disabled TLS verification |
   | MEDIUM | Missing HEALTHCHECK *on a service*; unpinned packages; no multi-stage on a bloated image |
   | LOW | Layer-cache misses; `ADD` where `COPY` belongs; missing `LABEL` metadata |

5. **Decide fix vs suppress for each finding.** The decision procedure and
   the documented-suppression recipe are in
   [suppression-policy](references/suppression-policy.md). Before
   suppressing anything, check it against
   [false-positives](references/false-positives.md) — several findings in
   this class are scanner parser artefacts, not defects.

6. **Remediate.** Apply the smallest change that removes the finding at
   its root; copy-paste fixes are in
   [remediation-templates](references/remediation-templates.md). Never
   "fix" a finding by deleting the instruction that triggered it, and
   never weaken a scanner to make a build pass.

7. **Re-scan to prove green.** A fix is not done until the same scanner
   that failed now passes. Re-run the exact command from step 3 and paste
   the clean output into the report. If the finding was suppressed rather
   than fixed, prove the suppression actually takes effect — an ignore
   entry that silently fails to match is worse than no entry at all.

8. **Report** to `$MAIN_ROOT/reports/maintainer-dockerfile-audit/`:

   ```bash
   MAIN_ROOT="$(git worktree list | head -n1 | awk '{print $1}')"
   DIR="$MAIN_ROOT/reports/maintainer-dockerfile-audit"
   mkdir -p "$DIR"
   REPORT="$DIR/$(date +%Y%m%d_%H%M%S%z)-dockerfile-audit.md"
   ```

## The audit checklist

Nine classes. Each maps to a section of
[audit-checklist](references/audit-checklist.md).

| # | Class | The question it answers |
|---|---|---|
| 1 | Base image | Pinned to a tag? To a digest? Official? Minimal? |
| 2 | Runtime user | Is the LAST `USER` non-root? Does that user own its files? |
| 3 | Secrets in layers | Any credential in `ENV`, `ARG`, or a deleted-later file? |
| 4 | HEALTHCHECK | Present — or provably inapplicable and documented? |
| 5 | Multi-stage | Do build tools ship in the runtime image? |
| 6 | Layer + cache | Are layers ordered least-to-most volatile? Cache cleaned in-layer? |
| 7 | Build context | Is a `.dockerignore` needed, or is the context already narrow? |
| 8 | Instruction hygiene | `COPY` over `ADD`, exec-form `CMD`, absolute `WORKDIR`, PID-1 init |
| 9 | Obsolete patterns | Anything the ecosystem has since removed or deprecated |

Class 7 has a trap worth stating once: a missing `.dockerignore` is only
a finding **if the build context is wide**. This repo builds with the
context scoped to `scripts/sandbox/dockerfiles/` — a directory holding
nothing but Dockerfiles — so there is no context to leak and no
`.dockerignore` to add. Check the actual `docker build` invocation before
raising this finding.

## Fix vs suppress

The one rule that must never bend:

> A suppression is a claim that the check does not apply. It is never a
> claim that the finding is inconvenient.

A suppression is legitimate only when ALL of these hold:

- The check genuinely cannot apply to this image kind (see step 2).
- The rationale is written where the next reader will look — in the
  config that performs the suppression, not in a commit message.
- The suppression names ONE check. Blanket-disabling a scanner, lowering
  a severity threshold, or excluding the file from linting are all
  forbidden.
- The neighbouring checks stay ENFORCED. Suppressing HEALTHCHECK must not
  quietly take non-root and pinned-base down with it.

Anything else is a fix. Full procedure, and this repo's worked example, in
[suppression-policy](references/suppression-policy.md).

## Output

- `$MAIN_ROOT/reports/maintainer-dockerfile-audit/<ts>-dockerfile-audit.md`
  — one section per Dockerfile: image kind, findings by severity, the
  fix-or-suppress decision with its rationale, and the re-scan proof.
- stdout: the report's absolute path.
- stderr: one summary line —
  `N dockerfiles, C critical, H high, M medium, L low, S suppressed`.
- Exit `1` if any CRITICAL or HIGH finding remains unfixed; else `0`.

## Error Handling

| Error | Action |
|-------|--------|
| `docker` not reachable | Stop. Every scanner is a container; there is no degraded mode worth trusting. Report the daemon error verbatim. |
| Scanner image pull fails (offline) | Fall back to a READ-ONLY review against the audit checklist; mark the report `PARTIAL` and name every scanner skipped. Never report PASS from a partial run. |
| hadolint cannot parse the file | Almost always a heredoc. See [false-positives](references/false-positives.md); do NOT rewrite the Dockerfile to appease the parser. |
| Checkov reports `unsupported instruction` | Same heredoc cause. The instructions listed are heredoc *body* lines, not real ones. |
| A finding fires on a fixture / intentionally-bad example | Fixtures are excluded from lint by design. Confirm the path is fixture-scoped, then leave it alone. |
| Suppression added but the finding still fires | The ignore ID did not match. Prove suppression with a control run before believing it. |
| Fix requires changing a shipped service's runtime user | This can break volume permissions at runtime. Flag it; do not silently apply. |

## Examples

Audit every Dockerfile in an entrusted repo:

```
User: "audit our Dockerfiles"
→ 5 found, all ephemeral tool containers
→ hadolint: 3× DL3008 (unpinned apt), 1× DL3016 (unpinned npm -g)
→ Checkov: 298 passed, 5 failed — all CKV_DOCKER_2 (HEALTHCHECK)
→ Trivy:   DS-0026 (HEALTHCHECK, LOW) ×5
→ Decision: HEALTHCHECK inapplicable (run-once containers) → documented
  suppress in .mega-linter.yml + .trivyignore; non-root + pinned-base
  stay ENFORCED. DL3016 → fix (pin the global install).
→ Re-scan: Checkov 0 failed. Exit 0.
```

CI is red and the cause is unclear:

```
User: "Checkov is failing CI on our Dockerfile"
→ Reproduce locally with the exact CI check-id set
→ CKV_DOCKER_3 (no user created) → REAL. Fix: add a non-root USER.
→ Never add it to --skip-check; that is the finding, not the noise.
```

Image is far larger than expected:

```
User: "our image is 1.2 GB, why"
→ dive --ci → efficiency 41%, build toolchain present in final layer
→ Single-stage build shipping compilers → multi-stage remediation
→ 1.2 GB → 48 MB
```

## Scope

- ONLY reads and edits Dockerfiles, `.dockerignore`, and the scanner
  config that governs them (`.mega-linter.yml`, `.trivyignore`,
  `.hadolint.yaml`). Does not build, push, tag, run, or publish images.
- Does NOT run the containers it audits. To execute anything in
  isolation, that is `maintainer-sandbox` — it owns the Docker harness,
  including these very Dockerfiles.
- Does NOT lint non-Dockerfile config. `maintainer-config-lint` owns
  JSON/YAML/TOML/`.env` (and invokes hadolint as one of its many
  linters). This skill is the DEEP pass on container images specifically:
  policy, layers, and the fix-vs-suppress decision that config-lint does
  not make.
- Does NOT scan for secrets in git history — that is
  `maintainer-secrets-scan`. This skill only catches a credential
  *baked into an image layer*.
- Never weakens a scanner to make a build pass.

## Resources

Each reference lists its full section outline (its Table of Contents) so
you can jump straight to the part you need.

- [scanner-matrix](references/scanner-matrix.md) — the four tools, real
  invocations, exit codes, CI wiring, and the complete verified check-ID
  catalogue (Checkov `CKV_DOCKER_*`/`CKV2_DOCKER_*`, Trivy `DS-*`,
  hadolint `DL*`).
  - Why four tools
  - Prefer the container form
  - Verified flags
  - Exit codes
  - Checkov Dockerfile catalogue (complete, from `checkov -l`)
  - Trivy Dockerfile IDs
  - hadolint rules seen most often
  - CI wiring in this repo
- [audit-checklist](references/audit-checklist.md) — the nine classes as
  check → defect → fix, including the obsolete-pattern sweep.
  - 1. Base image
  - 2. Runtime user
  - 3. Secrets in layers
  - 4. HEALTHCHECK
  - 5. Multi-stage
  - 6. Layers and cache
  - 7. Build context
  - 8. Instruction hygiene
  - 9. Obsolete patterns — remove on sight
- [remediation-templates](references/remediation-templates.md) —
  copy-paste fixes: multi-stage per language, non-root user creation,
  build secrets, `.dockerignore`, HEALTHCHECK forms, PID-1 init.
  - Non-root user
  - Pinned base image
  - HEALTHCHECK (services only)
  - Multi-stage — strip build tooling from the runtime
  - Single-stage that cannot be split — drop the build deps
  - Layer cache — order least-to-most volatile
  - Package install hygiene
  - Secrets — never bake, always mount
  - Installing a third-party tool safely
  - PID-1 init — reap zombies, forward signals
  - `.dockerignore`
  - Instruction hygiene
  - Hardening a shipped image further
- [suppression-policy](references/suppression-policy.md) — when a finding
  is genuinely inapplicable, how to document it, and this repo's worked
  example.
  - The decision procedure
  - Forbidden, always
  - How to document a suppression
  - Worked example — this repo
  - Prove the suppression actually works
  - Review a suppression when the image changes
- [false-positives](references/false-positives.md) — verified scanner
  artefacts: heredoc parse breakage, ARG-interpolated version pins, and
  the Trivy check-ID prefix change.
  - Heredoc breaks BOTH hadolint and Checkov parsers
  - hadolint DL3013 misfires on an ARG-interpolated version pin
  - Trivy check-ID prefix changed — and the old one still works
  - `trivy config` has no `--no-progress` flag
  - The general rule
- Companion skills: `maintainer-sandbox` (owns the Docker harness and
  these Dockerfiles), `maintainer-config-lint` (broad multi-format config
  lint), `maintainer-secrets-scan` (secrets in history),
  `maintainer-fix` (lands the remediation).
