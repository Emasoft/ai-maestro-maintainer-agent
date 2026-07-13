# Optional supply-chain hardening add-ons

Two security controls the base CI baseline does NOT ship by default,
because they only apply to a subset of repos. Offer them when the repo
fits; do not add them unprompted to every bootstrap.

All action refs below are shown as `@vN` for readability. Just like the
CI templates, `workflow-pin-actions` converts each to a 40-char SHA
plus a trailing `# vX.Y.Z` comment on the first run — never ship these
unpinned.

## Table of Contents

- [Dependency-review PR gate](#dependency-review-pr-gate)
- [Build attestation via OIDC (keyless)](#build-attestation-via-oidc-keyless)
- [When NOT to add these](#when-not-to-add-these)

## Dependency-review PR gate

`actions/dependency-review-action` blocks a PR that adds a vulnerable or
badly-licensed dependency. It reads the PR's dependency DELTA (via
GitHub's dependency graph) and fails on policy violations before the
code merges. Offer it on any repo with a lockfile GitHub understands
(npm, pip, cargo, go, maven, …).

```yaml
name: Dependency Review

on:
  pull_request:
    branches: [main, master]

permissions:
  contents: read

jobs:
  dependency-review:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - uses: actions/dependency-review-action@v4
        with:
          fail-on-severity: high
          deny-licenses: GPL-3.0, AGPL-3.0
          comment-summary-in-pr: on-failure
```

- `fail-on-severity` — `low` / `moderate` / `high` / `critical`. `high`
  is the sensible default gate; `critical` is minimal.
- `allow-licenses` / `deny-licenses` — pick ONE, not both (they are
  mutually exclusive). `deny-licenses` is the lighter policy for most
  repos.
- It runs on `pull_request` (not `_target`) — no secrets, no write
  token, only the read-only dependency graph. Keep it that way.

## Build attestation via OIDC (keyless)

For a repo that PUBLISHES an artifact or container image, attestation
makes the artifact verifiable and removes long-lived registry secrets.
Two pieces, both keyed on OIDC:

**OIDC for cloud/registry auth.** Instead of storing a long-lived cloud
key as a repo secret, request a short-lived token per run:

```yaml
permissions:
  id-token: write     # REQUIRED to mint the OIDC token
  contents: read

jobs:
  deploy:
    steps:
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::<acct>:role/<role>
          aws-region: us-east-1
```

The cloud side trusts `token.actions.githubusercontent.com` scoped to
`repo:<org>/<repo>:ref:refs/heads/main` (a `sub` claim condition), so a
fork or a non-main ref cannot assume the role. No secret is stored, so
none can leak.

**SBOM + build provenance.** For a published image, generate an SBOM and
attach signed provenance:

```yaml
permissions:
  id-token: write
  attestations: write     # REQUIRED to write the attestation
  contents: read
  packages: write         # only if pushing to GHCR

steps:
  - uses: actions/attest-build-provenance@v2
    with:
      subject-name: ghcr.io/<org>/<image>
      subject-digest: ${{ steps.build.outputs.digest }}
      push-to-registry: true
```

`attestations: write` and `id-token: write` are the two non-obvious
permissions; without them the attest step 403s. Keep the top-level
default `contents: read` and grant these ONLY on the publishing job.

## When NOT to add these

- The repo publishes nothing → skip the attestation block entirely.
- The repo has no dependency lockfile GitHub can read → dependency-review
  has nothing to review; skip it.
- Never widen the top-level `permissions:` to fit these. `id-token`,
  `attestations`, and `packages` are per-JOB grants on the one job that
  needs them — the top-level default stays `contents: read`.
- These are CI *security* controls, in scope for a hardening bootstrap.
  Feature-authoring conveniences (reusable-workflow scaffolding,
  composite actions, container-job service matrices, job-summary
  dashboards) are NOT — leave those to whoever authors the repo's
  application CI.
