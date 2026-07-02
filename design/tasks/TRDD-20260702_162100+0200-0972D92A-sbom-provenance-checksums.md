---
trdd-id: 0972D92A
title: Attach SBOM, build-provenance attestation, and SHA256SUMS to every release
column: backburner
created: 2026-07-02T16:21:00+0200
updated: 2026-07-02T16:27:17+0200
current-owner: maintainer
assignee: maintainer
priority: 4
severity: MEDIUM
effort: M
labels: [supply-chain, security, ci, release, sbom, provenance]
task-type: security
artifact-kinds: []
parent-trdd: null
npt: []
eht: []
blocked-by: []
supersedes: []
superseded-by: []
pre-block-column: null
relevant-rules: []
release-via: publish
delivery: direct-push
target-branch: main
feature-branch: null
merge-strategy: squash
must-pass-tests-before-merge: true
publish-target: null
publish-channel: stable
deploy-target: null
soak-duration: null
test-requirements: [lint, e2e]
audit-requirements: [security-scan]
review-requirements: [human-review, code-review]
fixtures: []
required-credentials: []
runtime-targets: [linux]
docker-image: null
impacts: [ci-pipeline]
migration-direction: null
attempts: 0
test-failures: 0
last-test-result: not-run
last-test-at: null
implementation-commits: []
pr-url: null
ci-runs: []
published-version: null
published-at: null
live-since: null
audit-trigger: null
audit-target: null
audit-evidence: []
audit-conclusion: null
external-refs: ["github.com/Emasoft/ai-maestro-maintainer-agent/issues/17 — NOT this deliverable; title says [fleet #44] but is about CPV canonical-pipeline migration, CLOSED"]
---

# Attach SBOM, build-provenance attestation, and SHA256SUMS to every release

## STATE — READ THIS FIRST ON RESUME (authoritative; supersedes the body) — 2026-07-02T16:21+0200

- **Current state:** DESIGN ONLY. Nothing implemented. `.github/workflows/release.yml`
  is untouched. This TRDD is parked at `column: backburner` per an explicit
  design-only sub-task; it has NOT been through ARCHITECT design-column
  review and has NOT been approved for implementation.
- **NEXT ACTION:** before any code lands, this TRDD must go through the
  `design` column and be classified under
  `~/.claude/rules/trdd-approval-tiers.md`. It touches `.github/workflows/`,
  which is an **objective Tier-2 (MANAGER approval) floor** per that rule's
  Part B / D3 table ("`.github/` workflows or rulesets" → Tier 2). **Do NOT
  self-approve this into `dev` — author a proposal (`design/proposals/`,
  `approval-tier: 2`) and route it to MANAGER before editing the workflow.**
  This is true even though the *design* of this TRDD (this file) was itself
  a Tier-0 TRDD-authoring operation (exempt per
  `manager-approval-defaults.md` Category B) — parking an idea needs no
  approval, but *applying* the `.github/` diff does.
- **Load-bearing facts (verified this session, see `## Evidence` below for
  exact commands):**
  - `scripts/publish.py::stage_gh_release` (≈line 1625-1676) creates every
    release via `gh release create <tag> --title <tag>` with **zero asset
    uploads**. Today's GitHub releases carry **no binary assets at all** —
    only the tag + release notes. So SBOM/provenance/checksums will be the
    **first assets ever attached** to a release of this plugin. There is no
    pre-existing build artifact (wheel/zip/tarball) to reuse — this design
    creates a source tarball as the checksummed/attested subject.
  - `.github/workflows/release.yml` is a **post-hoc safety-net gate**
    (`validate-tag` job) that runs on `push: tags: v*.*.*` **after**
    `publish.py` already created the release locally. It re-runs CPV
    `--strict` and fails the workflow (does not delete the release) if the
    tagged state is broken. Workflow-level `permissions: contents: read`.
    Existing SHA-pins: `actions/checkout@df4cb1c0…` (v6.0.3),
    `actions/setup-python@a309ff8b…` (v6.2.0),
    `astral-sh/setup-uv@fac544c0…` (v8.2.0).
  - The repo is **public** (`gh api repos/.../` → `"visibility":"public"`,
    `"private":false`), so `attestations: write` (GitHub Artifact
    Attestations) works on any plan — no Enterprise/Team requirement, no
    billing gate. Re-verify this if the repo is ever made private.
  - Neither **GitHub issue #44** nor **#116** exists in this repo. The
    closest hit is issue **#17**, titled `[fleet #44] Upgrade this plugin's
    publish pipeline to the CPV canonical standard` (CLOSED) — `"#44"`
    there is an **AI-Maestro fleet tracking id embedded in the title**, not
    a GitHub issue number, and the issue is about CPV pipeline migration,
    unrelated to SBOM/provenance/checksums. No open issue in this repo
    currently tracks this deliverable — this TRDD is the first tracked
    record of it.
  - Latest action releases resolved via `gh api repos/<o>/<r>/releases/latest`
    (2026-07-02): `anchore/sbom-action` → `v0.24.0`
    (`e22c389904149dbc22b58101806040fa8d37a610`);
    `actions/attest-build-provenance` → `v4.1.1`
    (`0f67c3f4856b2e3261c31976d6725780e5e4c373`). SHA-pins resolved via
    `gh api repos/<o>/<r>/commits/<tag>`. **Re-resolve both at
    implementation time — pins go stale.**
- **REVIEWER GOTCHA (found in review 2026-07-02, fix at implementation):** the
  diff's `sha256sum -- * > SHA256SUMS` has a glob-race — the shell truncates the
  empty `SHA256SUMS` (the `>` redirect) BEFORE expanding `*`, so `*` includes
  that now-empty file and sha256sum hashes its own output (circular; breaks
  `sha256sum -c`). Fix at implementation: list explicit patterns
  (`sha256sum -- *.tar.gz *.spdx.json > SHA256SUMS`), or write to a temp name
  outside the glob then `mv` it into place.
- **SUPERSEDED — do NOT carry forward:** nothing yet (first version of this
  TRDD).
- **Durable artifacts to read before acting:** the fuller design report at
  `reports/maintainer-release-supplychain/` (see the report filename in the
  commit/session notes — same session, same timestamp prefix) has the full
  rationale, alternatives considered, and permission-model walkthrough this
  STATE block only summarizes.

## Goal

Every tagged release of this plugin currently ships as bare source (tag +
notes, no assets). Add three supply-chain deliverables, generated in CI and
attached to **every** release, at zero new secrets and least-privilege
permissions:

1. **SBOM** (Software Bill of Materials, SPDX JSON) — enumerates every
   dependency declared in the shipped tree (`uv.lock`, `pyproject.toml`,
   etc.) via `anchore/sbom-action` (syft under the hood).
2. **Build-provenance attestation** — a Sigstore-signed, GitHub-hosted
   attestation binding the release artifacts to this exact workflow run,
   commit, and repo, via `actions/attest-build-provenance`. Verifiable by
   any consumer with `gh attestation verify <file> --owner Emasoft`.
3. **`SHA256SUMS`** — a checksum manifest over the other release assets, so
   a consumer can verify integrity even without the attestation tooling.

## Why extend `release.yml`, not `publish.py`

`actions/attest-build-provenance` mints its signature from a GitHub
Actions-issued OIDC token (`id-token: write`) — this is what makes the
attestation independently verifiable (it cryptographically ties the
artifact to "this repo, this workflow, this commit ran in GitHub's trusted
runners"). That trust anchor **only exists inside a GitHub Actions run** —
it cannot be reproduced by `publish.py` running locally on a maintainer's
machine. So provenance generation is necessarily a CI-side concern. Given
that, doing SBOM + checksum generation in the *same* CI job keeps all three
supply-chain artifacts co-located, generated from the same trusted
checkout, and attested together as one `subject-path` set — instead of
splitting responsibility awkwardly between local `publish.py` and CI.

`release.yml` already runs post-hoc, after the tag is pushed and the
release already exists (created by `publish.py`) — exactly the right place
to *enrich* that existing release with additional assets via
`gh release upload`.

## Design

Add a **second job** to `.github/workflows/release.yml`, gated on the
existing `validate-tag` job succeeding (`needs: validate-tag`) — if the CPV
strict gate fails (signal of a possible publish.py-bypass), do **not**
attach supply-chain artifacts to a release that already failed its safety
check.

The new job gets its **own** `permissions:` block (job-level permissions
override the workflow-level `contents: read` default) — the existing
`validate-tag` job is untouched and stays read-only:

| Permission | Why |
|---|---|
| `contents: write` | `gh release upload` attaches assets to the existing release (also covers the read access `actions/checkout` needs — write is a superset of read on the same resource, no separate `contents: read` line needed) |
| `id-token: write` | OIDC token so Sigstore can sign the build-provenance attestation |
| `attestations: write` | publishes the attestation to this repo's GitHub-hosted attestation store |

No new secrets. `GH_TOKEN: ${{ github.token }}` (the workflow-run token,
already scoped by the `permissions:` block above) is sufficient for
`gh release upload`.

Step order matters — each artifact must exist on disk before the next step
that depends on it:

1. Checkout the tagged commit (`persist-credentials: false`, matching the
   existing job's hardening).
2. `git archive --format=tar.gz HEAD` → the source tarball (the "build
   artifact" for a source-only plugin — there is no compiled binary).
3. `anchore/sbom-action` scans `path: .` (the full checked-out tree, so it
   picks up `uv.lock` / `pyproject.toml` / any other manifests) →
   `*.spdx.json`.
4. `sha256sum -- * > SHA256SUMS` inside the output dir, over exactly the
   tarball + SBOM (a SHA256SUMS file never lists its own hash — standard
   convention).
5. `actions/attest-build-provenance` with `subject-path: dist/*` — by this
   point `dist/` holds all three files, so the attestation covers the
   tarball, the SBOM, **and** the checksum manifest itself.
6. `gh release upload "$GITHUB_REF_NAME" dist/* --clobber` — attach all
   three to the release `publish.py` already created. `--clobber` makes
   the step idempotent on workflow re-runs.

## Exact `release.yml` diff (SKETCH ONLY — NOT APPLIED)

```diff
--- a/.github/workflows/release.yml
+++ b/.github/workflows/release.yml
@@ jobs:
   validate-tag:
     runs-on: ubuntu-latest
     timeout-minutes: 15
     steps:
       - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10  # v6.0.3
         with:
           fetch-depth: 0
           persist-credentials: false
       ...
       - name: CPV strict validation gate (post-hoc safety net)
         run: |
           ...
+
+  supply-chain-artifacts:
+    name: Attach SBOM, provenance attestation, and checksums to the release
+    needs: validate-tag
+    runs-on: ubuntu-latest
+    # Same reasoning as validate-tag: hard cap, no concurrency group (tags
+    # are sequential releases, never concurrent in practice).
+    timeout-minutes: 15
+    # Job-level permissions OVERRIDE the workflow-level `contents: read`
+    # default above. Only THIS job gets write scopes — validate-tag stays
+    # read-only. Least-privilege: exactly the 3 scopes the steps use.
+    permissions:
+      contents: write        # gh release upload attaches assets to the
+                              # release publish.py already created (also
+                              # covers checkout's read access — write is a
+                              # superset of read on the same resource)
+      id-token: write        # OIDC token so Sigstore can sign the
+                              # build-provenance attestation
+      attestations: write    # publish the attestation to this repo's
+                              # GitHub-hosted attestation store
+    steps:
+      - uses: actions/checkout@df4cb1c069e1874edd31b4311f1884172cec0e10  # v6.0.3
+        with:
+          persist-credentials: false
+
+      - name: Build reproducible source archive
+        run: |
+          mkdir -p dist
+          git archive --format=tar.gz \
+            --output "dist/ai-maestro-maintainer-agent-${GITHUB_REF_NAME}.tar.gz" \
+            HEAD
+
+      - name: Generate SBOM (SPDX JSON)
+        uses: anchore/sbom-action@e22c389904149dbc22b58101806040fa8d37a610  # v0.24.0
+        with:
+          path: .
+          format: spdx-json
+          output-file: dist/ai-maestro-maintainer-agent-${{ github.ref_name }}.spdx.json
+          upload-artifact: false   # we upload to the release ourselves below;
+                                   # don't also create a duplicate 90-day
+                                   # workflow-run artifact
+
+      - name: Compute SHA256SUMS
+        working-directory: dist
+        run: sha256sum -- * > SHA256SUMS
+
+      - name: Generate build provenance attestation
+        uses: actions/attest-build-provenance@0f67c3f4856b2e3261c31976d6725780e5e4c373  # v4.1.1
+        with:
+          subject-path: dist/*
+
+      - name: Upload release assets
+        env:
+          GH_TOKEN: ${{ github.token }}
+        run: |
+          gh release upload "$GITHUB_REF_NAME" dist/* \
+            --clobber --repo "${{ github.repository }}"
```

## Alternatives considered (and rejected / deferred)

- **CycloneDX instead of SPDX.** Both are valid, widely-consumed SBOM
  formats. SPDX chosen as the default because it's the ISO/IEC 5962:2021
  standard and what most downstream SBOM consumers (NIST, in-toto,
  Sigstore ecosystem) expect first. Not mutually exclusive — a follow-up
  EHT could add a second `format: cyclonedx-json` output if a consumer
  asks for it.
- **Doing this in `publish.py` instead of CI.** Rejected for provenance
  (needs the CI-issued OIDC token to be meaningful) and, for consistency,
  extended the same reasoning to SBOM + checksums so all three are
  generated from one trusted, reproducible checkout rather than split
  across local + CI.
- **Relying on `anchore/sbom-action`'s built-in `upload-release-assets`.**
  That input auto-attaches only when `github.event_name == 'release'`; this
  workflow triggers on `push: tags`, so it would silently no-op. Explicit
  `gh release upload` is used instead — works regardless of trigger event.

## Plan (steps for the `dev` column, once Tier-2 approved)

1. File a Tier-2 proposal in `design/proposals/` (per
   `trdd-approval-tiers.md`) citing this TRDD, route to MANAGER.
2. On approval: `git mv` this TRDD proto into the normal flow (`design` →
   `dispatch` → `dev`), re-resolve the two action SHA-pins (they may have
   moved since 2026-07-02), and apply the diff above verbatim (or as
   refined during ARCHITECT design review).
3. Add a `yamllint`/`actionlint` pass on the new job (test-requirements:
   `lint`).
4. `e2e` test: push a real tag (or a throwaway tag on a fork/test repo) and
   verify: (a) `validate-tag` still passes unmodified, (b) the new job
   produces exactly 3 files in the release, (c) `sha256sum -c SHA256SUMS`
   validates against the downloaded tarball + SBOM, (d)
   `gh attestation verify <tarball> --owner Emasoft` succeeds.
5. Security review (audit-requirements: `security-scan` — zizmor or
   equivalent) on the new job's permission block before merge, given it
   introduces `contents: write` / `id-token: write` / `attestations: write`
   to this workflow for the first time.
6. Update `README.md` / release docs to mention the new assets so
   consumers know to look for them.

## Evidence (commands run this session, 2026-07-02)

```
grep -n "release\|asset\|tarball\|\.zip\|gh release\|upload" scripts/publish.py
  → line 1648: gh release create tag --title tag  (no asset args anywhere in stage_gh_release)

gh issue view 44 --repo Emasoft/ai-maestro-maintainer-agent   → GraphQL: could not resolve issue #44
gh issue view 116 --repo Emasoft/ai-maestro-maintainer-agent  → GraphQL: could not resolve issue #116
gh issue list --repo Emasoft/ai-maestro-maintainer-agent --state all --limit 200
  → #17 CLOSED "[fleet #44] Upgrade this plugin's publish pipeline to the CPV canonical standard"
  → no issue mentions sbom/provenance/checksum/SHA256SUMS

gh api repos/anchore/sbom-action/releases/latest --jq '.tag_name'                → v0.24.0
gh api repos/anchore/sbom-action/commits/v0.24.0 --jq '.sha'                     → e22c389904149dbc22b58101806040fa8d37a610
gh api repos/actions/attest-build-provenance/releases/latest --jq '.tag_name'    → v4.1.1
gh api repos/actions/attest-build-provenance/commits/v4.1.1 --jq '.sha'          → 0f67c3f4856b2e3261c31976d6725780e5e4c373

gh api repos/Emasoft/ai-maestro-maintainer-agent --jq '.visibility, .private'    → public / false
```

## Approval log

(empty — this TRDD has not yet been submitted for approval; see STATE block
NEXT ACTION.)
