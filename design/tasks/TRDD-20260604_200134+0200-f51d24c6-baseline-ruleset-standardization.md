---
trdd-id: f51d24c6-d541-4e45-97b4-ebea95904853
title: Migrate maintainer branch-ruleset source to the ratified baseline-* pair
column: testing
created: 2026-06-04T20:01:34+0200
updated: 2026-06-06T00:12:50+0200
current-owner: ai-maestro-maintainer-agent
assignee: ai-maestro-maintainer-agent
priority: 2
severity: MEDIUM
effort: M
labels: [branch-protection, baseline, governance, supply-chain]
task-type: refactor
parent-trdd: null
supersedes: []
relevant-rules: [1]
release-via: publish
delivery: pull-request
target-branch: main
feature-branch: feat/baseline-ruleset-standardization
must-pass-tests-before-merge: true
test-requirements: [lint, typecheck]
audit-requirements: []
review-requirements: [human-review]
runtime-targets: [macos, linux]
impacts: [ci-pipeline]
attempts: 1
last-test-result: pass
last-test-at: 2026-06-04T20:24:03+0200
implementation-commits: [c8fe5ce, 089c979, 31fe57f, cde65eb, 138dfdd]
external-refs: ["github.com/Emasoft/ai-maestro-maintainer-agent/issues/7", "github.com/Emasoft/ai-maestro-janitor/issues/14"]
---

# Migrate maintainer branch-ruleset source to the ratified `baseline-*` pair

## ⏵ STATE — READ THIS FIRST ON RESUME (authoritative) — 2026-06-04

**Current state:** Migration IMPLEMENTED + locally verified on branch
`feat/baseline-ruleset-standardization` (2 commits: `c8fe5ce` core
baseline-* rename + `required_linear_history` + `pull_request` +
orphan-delete; `089c979` `.yml`/`.yaml` glob sweep). 467 tests pass;
CPV `--strict` reports ZERO findings in the touched files (the 18
remaining are pre-existing upstream FPs, CPV #68). Source now emits the
ratified `baseline-history-protect` + `baseline-pr-and-checks` pair.
NOT yet pushed; live repo rulesets NOT yet re-applied.

**NEXT ACTION (awaiting repo-owner go):** push the branch + open the PR
against `main`; post the two commit SHAs on issue #7 for the manager to
verify. After merge, optionally re-apply the live rulesets on this repo
via `workflow-protect-branch` APPLY (which now also orphan-deletes the
old `default-branch-*` pair).

**Load-bearing facts:**
- Ratified baseline agreed BYTE-IDENTICAL by both plugins (manager #7,
  janitor #14). The janitor reference impl is
  `ai-maestro-janitor/0.5.1/scripts/lib/branch_protection_lib.py`.
- `bypass_actors` is whole-ruleset, never per-rule → the two-ruleset
  split MUST be preserved. `pull_request` goes in the BYPASSED ruleset
  (`baseline-pr-and-checks`) so `publish.py` (admin) direct-pushes;
  `required_linear_history` goes in the NO-bypass ruleset
  (`baseline-history-protect`) and a linear fast-forward push satisfies
  it, so it does not block publish.py.
- Applying the ratified baseline as-is is EXEMPT (manager-approval
  §F). This migration applies it as-is — no deviation.

**SUPERSEDED — do NOT carry forward:**
- ✗ "the rulesets are named `default-branch-*`" — renamed to `baseline-*`.
- ✗ "history-protect has only `[non_fast_forward, deletion]`" — now
  `[deletion, non_fast_forward, required_linear_history]`.
- ✗ "checks ruleset has only `required_status_checks`" — now
  `[pull_request, required_status_checks]`.

**Durable artifacts to read before acting:**
- `~/.claude/.../memory/project_ratified_baseline_rulesets.md` — ratified spec.
- Prior split design: `design/tasks/TRDD-20260601_050823+0200-5307ae6c-protect-branch-two-ruleset.md`.

## Background

Issue #7 (companion janitor #14) ratified a unified two-ruleset baseline
that all AI Maestro agents align to as the default branch protection. The
maintainer Claude owns the maintainer-source migration (cross-project
rule: each plugin migrates its own source). Both peers converged
byte-identical and gave the go-ahead; the repo owner authorized the
standardization.

## Target state (the ratified `baseline-*` pair)

Both `target: branch`, `enforcement: active`, condition
`ref_name.include: ["~DEFAULT_BRANCH"]`.

- **`baseline-history-protect`** — `bypass_actors: []` (nobody, incl.
  admin). Rules: `deletion`, `non_fast_forward`, `required_linear_history`.
- **`baseline-pr-and-checks`** — `bypass_actors:
  [{actor_id:5, actor_type:RepositoryRole, bypass_mode:always}]`. Rules:
  - `pull_request` (`required_approving_review_count:1`,
    `dismiss_stale_reviews_on_push:true`, `require_code_owner_review:false`,
    `require_last_push_approval:false`,
    `required_review_thread_resolution:true`)
  - `required_status_checks` (`strict_required_status_checks_policy:true`,
    CI job ids auto-detected at apply time).

Re-applying the `baseline-*` pair deletes the orphaned legacy rulesets by
name (`default-branch-no-force-no-delete`,
`default-branch-required-checks`, the older single `default-branch-ruleset`,
and `janitor-baseline`).

## Phased edits

**Phase 1 — canonical payload templates (2 files):**
- `skills/workflow-bootstrap/references/templates/ruleset-no-force-no-delete.json`
- `skills/workflow-bootstrap/references/templates/ruleset-required-checks.json`

**Phase 2 — the core payload-builder (1 file):**
- `skills/workflow-protect-branch/references/instructions.md` — rename in
  the two heredocs + table + discover/verify/cache/disposition; add
  `required_linear_history` + `pull_request`; widen CI-detection glob to
  `*.y*ml`; add orphan-delete of the legacy names after verify.

**Phase 3 — prose + downstream references (3 files):**
- `skills/workflow-protect-branch/SKILL.md`
- `commands/maintainer-protect-branch.md`
- `skills/maintainer-guardian/references/threat-classes.md` (T3 baseline).

**Phase 4 — `.yml`/`.yaml` glob sweep in sibling skills (committed to the
janitor on #14):** `workflow-scan`, `workflow-pin-actions`,
`workflow-fix-safe`. Separate commit.

## Verification

- `python3 -c "import yaml; ..."` frontmatter parse on every touched SKILL.
- Every SKILL.md ≤ 5000 chars.
- JSON templates parse (`python3 -m json.tool`).
- `uvx zizmor` unaffected (no workflow files touched).
- CPV `--strict` CRITICAL=0 MAJOR=0.

## Shared follow-ups (post-SHA-exchange)

Two refinements surfaced during cross-plugin review on janitor #14,
agreed by both plugins + MANAGER to land byte-identical AFTER the SHA
exchange (not before — avoids diverging mid-reconcile):

1. **Job-level `if: github.event_name == 'push'` filter.** The PR-trigger
   filter (commit `cde65eb`) checks the WORKFLOW's `on:`, but a job inside
   a PR-triggered workflow can itself be gated push-only via a job-level
   `if: github.event_name == 'push'`. Such a job passes the workflow-level
   filter yet never reports on a PR → still deadlocks a non-admin PR.
   Refine the detection to also skip job-level push-only guards.

2. **gh-stub tightening to real-API semantics.** Both the PATCH-vs-PUT
   and push-only-context bugs stayed latent because the test GitHub-API
   stub answers any method / any path with success. Tighten both plugins'
   stubs: method→status (`PATCH /rulesets/{id}`→404, `PUT`→200,
   `POST /rulesets`→201), unknown-path→404, and a check-runs fixture where
   a push-only job never reports on a `pull_request` event — so the whole
   class is caught in-suite, not on live GitHub.

Both are tracked on janitor #14; land them paired so the two plugins stay
byte-identical.

3. **`baseline-tag-protect` — third ratified ruleset (TAG protection).**
   Surfaced by the 2026-06-05 security audit (no ruleset protects `v*`
   release tags → a moved/deleted published tag re-points installers at
   arbitrary code; a post-hoc CI gate can't catch a tag moved onto a
   commit that itself passes CI). **Tri-party converged byte-identical**
   (maintainer #7 + janitor + MANAGER on janitor #14, 2026-06-05). Spec:
   ```
   name: baseline-tag-protect
   target: tag
   enforcement: active
   conditions.ref_name.include: ["refs/tags/v*.*.*"]  # lock exact spelling at apply time via readback
   conditions.ref_name.exclude: []
   bypass_actors: []
   rules: [deletion, update]
   ```
   **Rule = `[deletion, update]` (NOT `non_fast_forward`).** `update`
   ("restrict updates") blocks EVERY move of an existing tag; bare
   `non_fast_forward` only blocks the non-fast-forward path, so a tag
   *fast-forward-moved* onto a descendant commit (append a malicious
   commit on top of the tagged one, move the tag forward) would slip
   through — `update` closes that edge and is the complete immutability
   statement. `non_fast_forward` is redundant under `update`. Creation
   stays unrestricted → publish.py still cuts each `vX.Y.Z`, no bypass
   actor needed.
   **Scope = `refs/tags/v*.*.*`** (full-semver release tags only): the
   invariant is *immutable published version tags*; `~ALL`/`v*` would
   freeze a future movable alias (`v1`/`latest`/`nightly`) for zero gain.
   Maintainer fact: `git tag -l` here = only `v1.0.1 … v1.3.1`, zero
   movable aliases (janitor same) — nothing in flight conflicts.
   **Open detail:** the exact GitHub-accepted `ref_name.include` literal
   for a `target: tag` ruleset — verify via readback on first apply and
   pin what GitHub echoes (same discipline as `actor_id:5`). Both
   verify-blocks assert `rules == [deletion, update]` (echoed form) +
   `bypass_actors == []`.
   **Governance = Tier-3 / USER** (MANAGER escalated — touches
   published-release integrity). All three plugins endorse the same
   byte-identical spec; awaiting the USER's ratify. Maintainer lands it
   as a 3rd payload in `workflow-protect-branch` (+ orphan-cleanup name
   awareness) folded into the same CPV-G3-cleared publish so it ships
   WITH the migration; janitor mirrors it in `branch_protection_lib.py`.
   Janitor TRDD: `TRDD-8546a187`.

## Audit-discovered maintainer-internal hardening (no baseline change)

Found by the 2026-06-05 security audit (full report:
`reports/workflow-protect-branch/20260605_*-baseline-ruleset-security-audit.md`).
All Tier-0 (no ratified-baseline change) → land via publish.py after the
CPV-G3 unblock; no cross-plugin re-ratification needed:

- **C2** bootstrap `ruleset-required-checks.json` literal-apply footgun —
  hardcoded `ci` context + the raw `gh api --input` follow-up deadlock
  any PR on a repo whose CI job ≠ `ci`. Blank the template's checks
  array; drop the raw-apply follow-up (protect-branch auto-detects).
- **C3** Step-6 verify never asserts `required_status_checks` contexts
  are non-empty → an empty auto-detection yields a hollow checks rule
  that still "passes". Guard Step-2 (`[]`→warn/abort) + Step-6 readback.
- **C4** bypass verify checks actor_TYPE not actor_ID → a `Maintain`
  (id 4) bypass passes the `RepositoryRole` assertion. Pin `actor_id==5`.
- **C5** no retry loop on `gh api` net calls; orphan-delete swallows
  DELETE failures silently. Wrap mutating calls in the retry loop.
- **C6** Step-2 `yaml.safe_load` has no try/except → one malformed
  workflow aborts the whole apply. Skip-with-warning per file.
- **D1** guardian T3 diffs branch rules only vs the session-start
  snapshot → a repo already off-baseline at startup is never flagged.
  Also compare the snapshot against the ratified spec.
- **D2** approval-gate `approve-protected-edit` is permanent-per-issue,
  not bound to a diff/SHA → replayable within an issue. Bind approval to
  a planned-diff fingerprint.

## Approval log

- 2026-06-04 — Repo owner authorized the baseline standardization once both
  peers agreed (janitor #14 converged byte-identical; manager #7 approved
  Path 1). Applying the ratified baseline as-is is EXEMPT (manager-approval
  §F). No deviation from the ratified spec.
