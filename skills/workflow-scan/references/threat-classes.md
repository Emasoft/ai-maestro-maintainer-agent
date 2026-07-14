# Threat classes — triage catalogue

What a finding MEANS, how severe it is, and which skill remediates it.
`workflow-scan` never fixes; it classifies and routes.

## Table of Contents

- [Routing table](#routing-table)
- [Expression injection](#expression-injection)
- [Trigger hazards](#trigger-hazards)
- [Secret exposure](#secret-exposure)
- [Over-broad permissions](#over-broad-permissions)

## Routing table

| Class | Typical severity | Auto-fixable | Remediated by |
|---|---|---|---|
| Expression injection in `run:` | high | no — needs a human-reviewed rewrite | `workflow-fix-safe` (env indirection) |
| Unpinned third-party `uses:` | high | yes | `workflow-pin-actions` |
| `pull_request_target` + checkout of PR head | high | **no — never auto-fix** | human review; escalate |
| Credential persistence after checkout | medium | yes | `workflow-fix-safe` (`persist-credentials: false`) |
| Missing top-level `permissions:` | medium | yes | `workflow-fix-safe` |
| Missing `timeout-minutes` / `concurrency` | low | yes | `workflow-fix-safe` |
| Secret echoed into logs or a URL | high | no — needs a rewrite + likely a rotation | human review; escalate |
| `secrets: inherit` on a reusable-workflow call | medium | no | human review |

Anything in the "no" column stays a **finding**, not a fix. Report it,
route it, and do not let a hardening pass paper over it.

## Expression injection

The single most common exploitable defect in GitHub Actions. zizmor's
`template-injection` audit is the primary detector; the full taint list
and the remediation live in
`skills/workflow-fix-safe/references/injection-hardening.md`.

The shape, in one line: a `${{ ... }}` expression whose value an
outside party controls is interpolated **directly into a `run:` block**.
GitHub substitutes the raw text into the shell script before the shell
parses it, so the attacker is writing shell, not supplying a string.

```yaml
# VULNERABLE SHAPE — never ship
- run: echo "Title: ${{ github.event.pull_request.title }}"
```

Triage rules:

- The value's ORIGIN decides severity, not the sink. `github.sha` and
  `github.run_id` are GitHub-generated and safe; a PR title, issue body,
  branch name, or commit message is whatever a stranger typed.
- Interpolation into `with:` / `env:` / `if:` is not the same defect —
  those values are passed as data, not spliced into a shell script.
- A finding here is never "informational". If the workflow runs on a
  fork-reachable trigger, it is high.

## Trigger hazards

Which trigger a workflow uses decides whether attacker code meets your
secrets. This is a scan-time READ of the `on:` block, and no scanner
will make the judgement for you.

| Trigger | Code that runs | Secrets / token | Verdict |
|---|---|---|---|
| `pull_request` | the PR's code | none (read-only token, no secrets on fork PRs) | safe default |
| `pull_request_target` | the BASE branch's code | full write token + all secrets | high risk |
| `workflow_run` | the BASE branch's code | full write token + secrets | safe, if it does not check out PR code |
| `issue_comment` | the BASE branch's code | full write token + secrets | high risk — fires for ANY commenter (see below) |

`pull_request_target` exists so a workflow can comment on, or label, a
fork's PR — jobs that need a write token, which `pull_request` denies.
It runs the **base** branch's workflow definition, with full secrets, and
that is fine as long as it never runs the **fork's** code.

The catastrophic combination — flag it every time, at high severity:

```yaml
on: pull_request_target      # full secrets + write token
jobs:
  build:
    steps:
      # THE DEFECT: checks out the fork's code, then runs it (build,
      # test, install — any of them) with the base branch's secrets in
      # the environment. A fork PR that edits a build script owns the
      # token.
      - uses: actions/checkout@<sha>
        with:
          ref: ${{ github.event.pull_request.head.sha }}
```

Safe uses of `pull_request_target` do not check out the head ref at all
— they call the API with the token and touch none of the PR's files.
When a workflow genuinely must BUILD fork code and THEN use secrets,
the correct shape is two workflows: a `pull_request` job that builds
with no secrets, and a `workflow_run` job that consumes its result.

`workflow_run` is safe *by construction* (it runs base-branch code) but
inherits the same rule: do not check out the triggering PR's head, and
treat any artifact downloaded from the upstream run as untrusted data.

### Comment-triggered ChatOps (`issue_comment`)

`issue_comment` (and `issue_comment` on a PR) runs the base branch's
workflow with the full write token and all secrets — like
`pull_request_target` — but it fires on a comment posted by **anyone**,
including a drive-by account with `author_association: NONE`. A ChatOps
handler (`/deploy`, `/run-tests`) is therefore a privileged surface any
stranger can poke. Two things make it a high finding:

1. **No permission gate.** A safe handler gates the job on BOTH
   `github.event.issue.pull_request` (the comment is on a PR) AND an
   `author_association` allowlist. A handler with neither is exploitable.
2. **Checkout-and-run of PR head.** If the handler resolves the PR's head
   ref and checks it out, then builds/tests/installs it, an outside
   commenter's PR code runs with the base branch's secrets — the same
   catastrophic shape as the `pull_request_target` defect, reached via a
   comment instead of a push.

`author_association` values, most- to least-trusted: `OWNER`, `MEMBER`,
`COLLABORATOR`, `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, `FIRST_TIMER`,
`NONE`. A sound gate allows only `OWNER` / `MEMBER` / `COLLABORATOR`.

Gotcha worth calling out in the report: `author_association` alone is a
WEAK gate. `CONTRIBUTOR` is anyone who has ever had a PR merged, so an
allowlist that includes `CONTRIBUTOR` grants ChatOps to a large,
open-ended set. A robust gate checks team/role membership via the API,
not the association string. Flag an association-only gate that admits
`CONTRIBUTOR` (or wider) as a medium finding.

## Secret exposure

Report at high severity, and do not auto-fix — a leaked secret usually
needs rotation, which is a human decision:

- A secret interpolated into a URL (`https://<token>@github.com/...`)
  — it lands in the git remote and in every log line that prints it.
- A secret echoed, printed, or passed as a command-line argument
  (argv is visible to other processes on the runner).
- A secret written into an artifact, a step summary, or a cache.
- A value DERIVED from a secret (a signed URL, a decoded credential):
  GitHub masks the registered secret, not its derivatives. Masking a
  derivative requires an explicit `add-mask` workflow command — see the
  hardening reference.

## Over-broad permissions

`permissions: write-all`, or a top-level `contents: write`, hands every
job in the file a token that can push to the repository. The correct
shape is a read-only default at the top with per-job elevation — the
remediation lives in `workflow-fix-safe`. At scan time, record which
jobs actually needed the elevation; a job that writes nothing but holds
a write token is the finding.
