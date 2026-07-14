# CI gate integrity — a check that cannot fail is not a gate

The most common way a security or test gate is silently defeated is not
by removing it — it is by leaving it in place but making it *unable to
fail the pipeline*. A scanner that runs, finds a critical vulnerability,
prints it, and lets the pipeline go green is worse than no scanner: it
manufactures false assurance. This concern is identical across GitLab CI,
Jenkins, and Azure Pipelines; only the keyword that swallows the failure
changes. Audit every test/lint/scan/audit step for it.

## Table of Contents

- [The anti-pattern in three syntaxes](#the-anti-pattern-in-three-syntaxes)
- [What to look for](#what-to-look-for)
- [The fix — propagate the failure](#the-fix--propagate-the-failure)
- [Included-but-toothless scanners](#included-but-toothless-scanners)

## The anti-pattern in three syntaxes

| System | The failure-swallowing shape | Effect |
|---|---|---|
| GitLab CI | `allow_failure: true` on a test/scan job | job may fail, pipeline stays green |
| Azure Pipelines | `continueOnError: true` on a step; `failOnStderr: false`; `failTaskOnFailedTests: false` on `PublishTestResults@2` | step/tests may fail, stage continues |
| Jenkins | a `catch` that does not re-`throw` and never sets `currentBuild.result = 'FAILURE'`; `sh(script: …, returnStatus: true)` whose non-zero return is ignored | build reports SUCCESS despite the failure |

Each is a legitimate feature in the right place (a genuinely advisory
lint, a best-effort notification), which is exactly why it slips past
review on a *security* step where it must not appear.

## What to look for

- A dependency-audit, SAST, secret-scan, container-scan, or required
  test step carrying `allow_failure: true` (GitLab) / `continueOnError:
  true` (Azure) — the finding never blocks the merge or release.
- An Azure `condition: always()` on a *downstream* step that lets the
  pipeline proceed to deploy regardless of an upstream scan's result.
- A Jenkins `try { … } catch (e) { echo e.message }` around a build or
  test step with no re-throw and no `currentBuild.result` change — the
  exception is eaten and the stage is marked green.
- A Jenkins `sh(returnStatus: true)` whose captured exit code is never
  compared to `0` (so a non-zero exit is discarded).

## The fix — propagate the failure

Make the security-relevant step able to fail the pipeline, and let it:

- **GitLab** — remove `allow_failure: true` from the gate job (or set it
  explicitly `allow_failure: false`), so a scan finding fails the
  pipeline.
- **Azure** — drop `continueOnError: true` from the scan/test step; on
  `PublishTestResults@2` set `failTaskOnFailedTests: true` so failing
  tests fail the task.
- **Jenkins** — either let the exception propagate (do not catch it), or,
  if you must catch to run cleanup, re-`throw` after recording state; for
  a captured exit code, `error "…"` when it is non-zero.

Keep advisory-only steps advisory *deliberately and visibly* — an
informational lint may keep `allow_failure`/`continueOnError`, but a
comment must state that it is advisory so the next auditor does not read
a defeated gate as a working one. A gate with no such note and a
failure-swallowing flag is a finding (`non-blocking-security-gate`,
MEDIUM→HIGH by what it fails to catch).

## Included-but-toothless scanners

Adding a scanner is only half the control. GitLab's stock
`Security/*.gitlab-ci.yml` templates (see
[gitlab-ci-audit](gitlab-ci-audit.md) §8), an Azure security-scan task,
or a Jenkins scan stage all default to *reporting*, not *gating* —
whether they block depends on the same failure-propagation rules above.
When you confirm a repo includes a scanner, verify in the same pass that
its job/step is not simultaneously marked non-blocking; report a scanner
that runs but cannot fail as the same `non-blocking-security-gate`
finding.
