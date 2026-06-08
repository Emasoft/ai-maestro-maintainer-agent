---
trdd-id: f51d24c6-d541-4e45-97b4-ebea95904853
title: Migrate maintainer branch-ruleset source to the ratified baseline-* pair
column: testing
created: 2026-06-04T20:01:34+0200
updated: 2026-06-08T18:05:11+0200
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
implementation-commits: [c8fe5ce, 089c979, 31fe57f, cde65eb, 138dfdd, b71a1ff, fde5e59, 99c3f9e, 976d311, 58e3234, b02b24c]
external-refs: ["github.com/Emasoft/ai-maestro-maintainer-agent/issues/7", "github.com/Emasoft/ai-maestro-janitor/issues/14"]
---

# Migrate maintainer branch-ruleset source to the ratified `baseline-*` pair

## ⏵ STATE — READ THIS FIRST ON RESUME (authoritative) — 2026-06-04

**Current state (2026-06-06):** The full THREE-ruleset baseline is
IMPLEMENTED + verified on branch `feat/baseline-ruleset-standardization`.
The pair migration (`c8fe5ce`, `089c979`) PLUS `baseline-tag-protect`
(USER-ratified Tier-3; commit `b71a1ff` — Body C build/apply/verify in
workflow-protect-branch, the ruleset-tag-protect.json template, bootstrap
stash+prose, guardian T3, command; audit-finding C2 folded in). PLUS the
full Tier-0 audit-hardening batch landed this session: C3-C6 (`fde5e59`),
D1 (`99c3f9e`), D2 (Phase 3) — all maintainer-internal, no baseline-shape
change. PLUS the 4 sentinel Pyright nits (our-side CPV-G3 portion) FIXED
this session (`b02b24c`). 471/471 tests pass; pyright 0/0/0 across
`scripts/`; CPV `--strict` clean on every touched file.
NOT yet pushed; live repo rulesets NOT yet re-applied.

**THE ONE BLOCKER — CPV-G3 (publish gate), now purely UPSTREAM:**
publish.py requires CPV `--strict` exit 0. The MINOR=4 sentinel Pyright
nits (OURS) are FIXED this session — `b02b24c`: positional-only `_Client`
protocol (the 3 fetch_* methods are always called positionally, so
`LocalClient`'s intentionally-unused `_repo` slot no longer needs to
name-match) + single-eval narrowing in missing_persist_creds /
unscoped_app_token (evaluate `step.get("with")` once so isinstance narrows
the assigned value). Remaining: NIT=14 (CPV #68 supply-chain FPs in
classification-paths / install-recipes / protocols docs — UPSTREAM, do
NOT edit our docs). `--strict` blocks on exit 1-4, so the NIT FPs alone
still block → need a CPV suppression/allowlist or a newer CPV release
(cross-project: a CPV fork+PR for #65/#68 is the repo-owner's call).

**NEXT ACTIONS:** (a) ✅ ALL Tier-0 audit hardening LANDED this session —
C3-C6 (Phase 1, `fde5e59`), D1 (Phase 2, `99c3f9e`), D2 (Phase 3) — see
the audit-hardening section. Nothing from the audit remains. (b) The 4
sentinel Pyright nits are FIXED (`b02b24c`). CPV-G3 unblock is now the
SOLE remaining gate to shipping, and its ONLY residual sub-blocker is the
#68 NIT FPs (CPV suppression / newer-CPV / upstream). This is the repo
owner's call (cross-project: it may need a CPV fix). Once CPV-G3 clears:
run publish.py (ships pair +
tag-protect + ALL the Tier-0 hardening together), re-apply live rulesets
via `workflow-protect-branch` APPLY, post SHAs on #7; janitor mirrors
byte-identical + first-apply readback-pins the tag `ref_name.include`.
ALL the C3-C6/D1/D2 hardening is maintainer-internal (Tier 0, no
baseline-shape change) → NO cross-plugin re-ratification needed; the
ratified `baseline-*` JSON shape stays byte-identical, only the
build/verify *procedure* + guardian/approval-gate logic got stricter.

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
- ✗ "the baseline is a PAIR (two rulesets)" — now THREE: the pair PLUS
  `baseline-tag-protect` (target tag, `refs/tags/v*.*.*`,
  `[deletion, update]`, no bypass), USER-ratified + implemented `b71a1ff`.

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
   **Governance = Tier-3 / USER → RATIFIED 2026-06-06** (USER approved
   directly + MANAGER relayed on #7/#14, recommendation=approve).
   **IMPLEMENTED in maintainer source — commit `b71a1ff`** (the 3rd
   payload in `workflow-protect-branch` instructions+SKILL: Body C build
   / discover / apply / verify / disposition / Why-subsection / TOC;
   `workflow-bootstrap` ruleset-tag-protect.json template + stash +
   post-merge prose; guardian T3 baseline snapshot; command). 467 tests
   pass; CPV `--strict` clean on all touched files. Still ships in the
   same CPV-G3-cleared publish as the pair (not yet pushed). Janitor
   mirrors it in `branch_protection_lib.py` (TRDD-8546a187); first-apply
   readback-pins the `ref_name.include` literal, byte-identical.

## Audit-discovered maintainer-internal hardening (no baseline change)

Found by the 2026-06-05 security audit (full report:
`reports/workflow-protect-branch/20260605_*-baseline-ruleset-security-audit.md`).
All Tier-0 (no ratified-baseline change) → land via publish.py after the
CPV-G3 unblock; no cross-plugin re-ratification needed:

- **C2** ✅ ADDRESSED in `b71a1ff` — bootstrap literal-apply footgun:
  the raw `gh api --input` follow-up was replaced with skill-only
  guidance (the post-merge prose now explicitly warns the
  required-checks template's `ci` context is a PLACEHOLDER and a
  verbatim POST deadlocks PRs on repos whose CI job ≠ `ci`; the skill
  rebuilds the context list by auto-detect). Template's `ci` left as a
  documented placeholder rather than blanked, since the skill always
  overrides it — net effect: no one is told to apply it raw anymore.
- **C3** ✅ ADDRESSED (Phase 1) — Step-2 now aborts (exit 64) when
  auto-detection yields `[]`/empty (no hollow checks rule can be built),
  AND Step-6 readback asserts the landed `required_status_checks` list
  length ≥ 1 (exit 67 on a hollow gate).
- **C4** ✅ ADDRESSED (Phase 1) — Step-6 now reads `actor_id` and asserts
  `CHECKS_BYPASS_ID == 5` (Admin), so a weaker `Maintain` (id 4) bypass
  no longer passes the `RepositoryRole`-only check (exit 66).
- **C5** ✅ ADDRESSED (Phase 1) — added `gh_api_retry()` (transient-only,
  fail-fast on 4xx per github-timeouts.md; bounded 30×6s) wrapping the
  POST/PUT in `apply_ruleset` and the Step-6.5 DELETE; a persistent
  DELETE failure is recorded in `ORPHAN_FAILED` → surfaced in the Step-7
  disposition `failed_legacy_deletes` (no longer swallowed).
- **C6** ✅ ADDRESSED (Phase 1) — Step-2 per-file `yaml.safe_load` is now
  wrapped in try/except `yaml.YAMLError`: one malformed workflow is
  skipped-with-warning to stderr; the C3 guard re-asserts the result is
  non-empty so a swallowed parse cannot silently yield `[]`.
- **D1** ✅ ADDRESSED (Phase 2) — guardian T3 now runs TWO checks:
  **T3-absolute** (compares the session-start snapshot against the
  ratified three-ruleset spec → flags a repo ALREADY off-baseline at
  startup, standing finding like T6 mode 3) + **T3-relative** (the
  existing drift-vs-snapshot). Added `baseline_compliance` to the
  baseline shape, a spec table, split routing (non-compliance →
  recommend APPLY/EXEMPT; drift → alert), and fixed the stale
  "T1 through T5" doc title → T6. Anchor `#t3--branch-rule-drift`
  preserved so the TOC/SKILL refs stay valid.
- **D2** ✅ ADDRESSED (Phase 3) — approval is now bound to a 12-char
  planned-diff fingerprint (`git diff HEAD -- | git hash-object --stdin
  | cut -c1-12`). CHECK publishes the fingerprint + asks the user to echo
  `approve-protected-edit <fp>`; VERIFY recomputes the LIVE fingerprint
  and releases ONLY on an exact match — a stale (re-scoped-diff) or bare
  (no-fp) approval is fail-closed to `pending`, never `ok`. Updated both
  SKILL.md + protected-paths.md (new "Diff-fingerprint binding" section +
  TOC, both embedded SKILL TOCs synced) AND the test model:
  `skill_helpers.classify_approval` now takes `fingerprint` + a new
  `diff_fingerprint` helper (faithful to git's blob-hash formula);
  test_approval_gate.py gained 4 tests incl. a REAL `git hash-object`
  cross-check (no mock). Also fixed a pre-existing Pyright nit in
  `resolve_agent_dir` surfaced in the same file. 471/471 pass.

## Approval log

- 2026-06-04 — Repo owner authorized the baseline standardization once both
  peers agreed (janitor #14 converged byte-identical; manager #7 approved
  Path 1). Applying the ratified baseline as-is is EXEMPT (manager-approval
  §F). No deviation from the ratified spec.
- 2026-06-05 — `baseline-tag-protect` (follow-up #3): tri-party consensus
  CLOSED. All three plugins hold the byte-identical spec
  `target: tag` / `refs/tags/v*.*.*` / `[deletion, update]` / no bypass.
  MANAGER self-corrected (`update` > `non_fast_forward`, owning the ff-move
  edge), confirmed on janitor #14, and escalated to USER for Tier-3 ratify
  with recommendation = APPROVE. Maintainer relayed the closed spec on #7.
  **Status: awaiting USER ratify** — the only remaining gate for the tag
  ruleset; lands byte-identical in the same CPV-G3-cleared publish as the
  pair. Nothing else open between the three plugins.
