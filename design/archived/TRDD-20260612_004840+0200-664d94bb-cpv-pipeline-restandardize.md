---
trdd-id: 664d94bb-2609-4789-a0c5-e22fa1f96c93
title: CPV canonical-pipeline re-standardization — clear RC-PIPELINE-DRIFT-001
column: published
created: 2026-06-12T00:48:40+0200
updated: 2026-06-22T11:11:55+0200
current-owner: maintainer-agent
assignee: maintainer-agent
priority: 4
severity: LOW
effort: M
task-type: infra
approval-tier: 2
parent-trdd: null
npt: []
eht: []
blocked-by: []
relevant-rules: []
release-via: publish
delivery: direct-push
target-branch: main
impacts: [ci-pipeline]
test-requirements: [lint, typecheck, unit]
audit-requirements: []
review-requirements: [human-review]
runtime-targets: [macos, linux]
implementation-commits: [62e6eda, bb53c82, 8af1f41, 997099d]
published-version: 1.7.2
published-at: 2026-06-22T11:11:55+0200
external-refs: ["github.com/Emasoft/ai-maestro-maintainer-agent/issues/10", "github.com/Emasoft/ai-maestro-maintainer-agent/issues/17", "github.com/Emasoft/ai-maestro/issues/44", "github.com/Emasoft/claude-plugins-validation/issues/145", "github.com/Emasoft/ai-maestro-janitor/issues/19", "github.com/Emasoft/ai-maestro-janitor/issues/26", "github.com/Emasoft/claude-plugins-validation/issues/150", "github.com/Emasoft/claude-plugins-validation/issues/151"]
---

# CPV canonical-pipeline re-standardization — clear RC-PIPELINE-DRIFT-001

## ⏵ STATE — READ THIS FIRST (authoritative; supersedes the body below) — 2026-06-22 (11:11)

**✅ DONE (2026-06-22 11:11): PUBLISHED v1.7.2 — CI fully GREEN. column → published; archived.**
- Migration to CPV **v2.143.0** canon SHIPPED across two releases: **v1.7.1** (the migration) + **v1.7.2** (follow-on: enabling Checkov/Trivy surfaced Dockerfile-policy gaps in the maintainer-sandbox fixtures → pinned mitm's base tag + added a non-root USER; documented-suppressed the inapplicable HEALTHCHECK on the ephemeral run-once containers — scoped, gate intact).
- v1.7.2 CI all green: Lint · Validate (CPV --strict exit 0) · Test matrix macOS+ubuntu · workflow-security/zizmor · Release post-hoc gate.
- Implementation commits: 62e6eda (migration) · bb53c82 (publish.py mypy fix) · 8af1f41 (sandbox Checkov/Trivy fix) · 997099d (uv.lock). Auto-bumps: 31261f0 (1.7.1) · a670f7d (1.7.2).
- the-skills-menu EXCLUDED (broken canon feature → CPV #150); zizmor RE-ADDED (no security regression). CPV canon bugs reported: #150 + #151. GitHub #17 CLOSED with the full record.
- DEFERRED fast-follows (own TRDDs/tasks #116/#117): SBOM/provenance/SHA256SUMS into release.yml (fleet #44); the .githooks↔git-hooks hook-convention reconcile.

**UPDATE (2026-06-22 03:07): USER invoked /go-on-yourself → AUTHORIZED; column → planned; EXECUTING migration to LATEST canon v2.143.0.** [SUPERSEDED by the ✅ DONE entry above]
- Canon advanced to **v2.143.0** (v2.141 fixer CI-preflight; v2.142 validator spec-sync → CC 2.1.185; v2.143 plugin-creator preflight + the-skills-menu "conditional canon"). Re-verified force-templates in a fresh worktree @ v2.143.0 (report `reports/cpv-standardize/20260622_030242+0200-v2143-worktree-verify.txt`).
- PIPELINE invariants STILL hold @ v2.143.0: `release.yml` + `notify-marketplace.yml` SKIPPED (ahead-of-canon → post-hoc gate + PAT/marketplace target PRESERVED); `.markdownlint.json` KEEPS `MD025: front_matter_title`; `ci.yml` created; `publish.py` refreshed; new files `.jscpd.json` + `git-hooks/pre-push` + `scripts/cpv_network_resilience.py`.
- ⛔ NEW v2.143.0 REGRESSION — the-skills-menu conversion is BROKEN: force-templates (a) writes an EMPTY `skills/the-skills-menu/SKILL.md` ("this plugin has no operational skills yet" — but the plugin has 22 skills), and (b) STRIPS 11 core skills from the agent frontmatter, pointing it at that empty menu → the agent would LOSE access to maintainer-patrol/triage/fix/guardian/etc. The stub also carries `allowed-tools: Read` (violates the no-tool-frontmatter rule). Filed **CPV #150**. ⇒ EXCLUDE the-skills-menu from THIS migration (revert agent doc + rm the empty stub); adopt it PROPERLY in a separate TRDD (run `the-skills-menu-create` to populate + strip allowed-tools + verify dynamic loading & token savings).
- SCOPE = option B (per /go-on-yourself "integrate don't delete; never relax quality"): apply pipeline canon + manually MERGE canon's SBOM/build-provenance/per-asset-checksum into `release.yml` (honors fleet #44) + bump all 3 workflows' action pins to latest (folds in dependabot #14) + EXCLUDE the-skills-menu.
- NEXT ACTIONS (executing): (1) force-templates on main; (2) `git checkout` agent doc + `rm -rf skills/the-skills-menu`; (3) merge SBOM into release.yml; (4) bump pins checkout 6.0.3 / setup-uv 8.2.0 / codeql 4.36.2 across ci.yml+release.yml+notify; (5) cpv validate --strict clean; (6) docs/README/help; (7) commit; (8) publish.py; (9) CI watch → fleet #44, close #17, close #14. Release also carries 8631e60 + 3409c1c + 1d57d85 + uv.lock sync.

**UPDATE (2026-06-21 23:10): CPV #145 CLOSED → v2.140.0; dry-run done; AWAITING USER decision on scope.** [SUPERSEDED by the 2026-06-22 entry above — canon is now v2.143.0; A/B/C resolved → option B; the-skills-menu EXCLUDED]
- CPV #145 fixed in **v2.140.0** (ships MD025 in canon `.markdownlint.json`; profile-aware standardize; publish.py ruff/mypy clean). The unblock the USER waited for.
- Ran `cpv-standardize . --fix --force-templates --dry-run` via uvx@v2.140.0 — report `reports/cpv-standardize/20260621_231013+0200-v2140-dryrun.txt`. Findings:
  - ✓ Profile-awareness WORKS: it SKIPS `release.yml` + `notify-marketplace.yml` ("at/AHEAD of canon — would downgrade") → my post-hoc CPV gate + PAT preflight + marketplace target PRESERVED, zero regression.
  - ⚠ SBOM/build-provenance/per-asset-checksums NOT delivered: they live in canon's `release.yml`, which is SKIPPED. My release.yml is a MIXED file (ahead on the gate, behind on SBOM) and the per-file direction classifier resolved it "ahead" → skip. Adopting SBOM needs a MANUAL merge of canon's new release.yml steps into mine.
  - Migration WOULD overwrite `publish.py` (76KB) + `cpv_network_resilience.py` + `.markdownlint.json` + `.mega-linter.yml` + `cliff.toml`; and CREATE `ci.yml` + `git-hooks/pre-push` + `.jscpd.json` + a pyproject dev-extra (the jscpd copy-paste gate, issue #143).
- WORKTREE-VERIFIED (23:20) the REAL --fix (isolated worktree, main untouched): migration is SAFE — `release.yml` + `notify-marketplace.yml` PRESERVED (no regression); `publish.py` refresh keeps maintainer logic (the `ai-maestro-plugins` target + post-hoc gate live in the PRESERVED workflows, not publish.py) and GAINS the jscpd gate #143 + cpv_network_resilience integration; `validate.yml`→`ci.yml` is an UPGRADE (adds `lint`+`commitlint` jobs, keeps the remote-CPV `--strict` validate job); `.markdownlint.json` KEEPS `MD025: front_matter_title` (only relaxes MD024 siblings_only→false). New files: ci.yml, .jscpd.json, git-hooks/pre-push, scripts/cpv_network_resilience.py, pyproject dev-extra. ⇒ Option A is now LOW-RISK; only the SBOM/provenance gap remains (option B's manual release.yml merge).
- NEXT — USER decides scope: (A) proceed as-is (refresh publish.py/configs + add ci.yml/jscpd gate; clears drift; NO SBOM) → review the publish.py diff → publish; (B) ALSO manually merge SBOM/provenance/checksums into release.yml first (delivers what the fleet #44 row promised) → publish; (C) hold for USER review. **NOTHING written yet — dry-run only, tree clean.** Release also carries committed MD018 fix 8631e60 + #18 self-id fix 3409c1c + uv.lock sync 1d57d85.

**UPDATE (2026-06-21): canon caught up — migrate AFTER CPV #145, then publish.**
Re-extracted canon's templates against **CPV 2.137.0** (worktree + `git diff`).
Canon advanced a lot since the 2026-06-13 finding:

- The plugin passes `cpv-remote-validate plugin . --strict` **clean** (exit 0:
  CRITICAL=0 MAJOR=0 MINOR=0 NIT=0; 7 advisory RC-PIPELINE-DRIFT WARNINGs). The
  validator is now profile-aware and says "at or AHEAD of canon — do NOT
  --force-templates" for the by-design files.
- Canon 2.137.0 now **SHA-pins** actions (even bumps versions), **keeps**
  least-priv `permissions` + `persist-credentials: false`, and **ADDS** an SBOM,
  a build-provenance attestation (SLSA), per-asset SHA256SUMS, and idempotent
  release creation — genuine hardening the plugin LACKS and should adopt.
- But `standardize --force-templates` is still NOT profile-aware, so it would
  STILL regress the plugin (narrower than before): strips `.markdownlint.json`'s
  `MD025: front_matter_title` (→ breaks publish on the TRDD docs), overwrites the
  by-design files, and reformats `publish.py` (ruff E302 / mypy misc risk).

**NEXT ACTION (USER decision 2026-06-21):** do NOT hand-port, do NOT
force-templates now. Filed **CPV #145** asking canon to make the standardizer
profile-aware (ship the MD025 config; skip overwriting profile-recognized
by-design files; guarantee a templated publish.py passes ruff+mypy). **WAIT** for
CPV to ship #145, THEN migrate to the new canon (gaining SBOM/provenance, zero
regression) and **publish**. The committed MD018 lint fix `8631e60` rides that
release. Fleet status posted on this repo's #17 + ai-maestro#44 (DEFERRED
pending #145, not stalled).

**SUPERSEDED — do NOT carry forward:**
- ✗ "standardize reverts SHA-pinned `checkout` → unpinned `@v4`, removes
  permissions, deletes the post-hoc gate" (2026-06-13) — FALSE as of CPV 2.137.0
  (it SHA-pins + keeps permissions + adds SBOM/provenance). Residual regression
  is now only MD025-config-strip + by-design-overwrite + publish.py reformat.
- ✗ "Canon ships none of the SHA-pinning/actionlint it advertises" — FALSE now;
  canon SHA-pins and adds SLSA provenance.
- ✗ "File a CPV bug = #118" — DONE + CLOSED (validator half). The standardizer
  half is the new **CPV #145**.

Evidence: 2026-06-21 worktree diff analyzed in-session; the 2026-06-13 diffs
(`/tmp/canon-workflows.diff`, `/tmp/canon-publish.diff`) are now stale.
The "Proposed change" / "Acceptance criteria" sections below are **SUPERSEDED**
by this block.

## Why this is a PROPOSAL (not a planned task)

It edits `.github/workflows/*` + `scripts/publish.py` — a pipeline/workflow
change, which the approval-tier rule classes **Tier 2 (MANAGER approval)**. I
committed to authoring this TRDD + coordinating before applying, in the v1.5.0
closure on maintainer #10 and the JANITOR coordination at janitor #26. It stays
`column: proposal` until the MANAGER (and JANITOR, for fleet convergence)
approve.

## Symptom

v1.5.0's CPV `--strict` run is VALID (0 blocking) but emits **RC-PIPELINE-DRIFT-001**
(WARNING) against three files — they differ from the current canonical CPV
templates:

- `scripts/publish.py`
- `.github/workflows/release.yml`
- `.github/workflows/notify-marketplace.yml`

The canonical templates now bundle: idempotent publish.py, atomic push,
SHA-pinned actions, actionlint + commitlint gates, a macOS test matrix, and
env-sanitized `run:` blocks. The maintainer's copies predate some of these.

## Proposed change

Run `/cpv-upgrade-plugin` (≡ `uvx cpv-remote-validate standardize . --fix
--force-templates`), then reconcile the diff: KEEP the maintainer-specific
intent already layered on top (the post-hoc CPV gate in `release.yml`, the
MARKETPLACE_PAT preflight + `Emasoft/ai-maestro-plugins` target in
`notify-marketplace.yml`, the `cpv_network_resilience` retry shims in
`publish.py`), DROP only the genuine drift. Re-run CPV `--strict` to confirm the
three RC-PIPELINE-DRIFT-001 warnings clear with no new findings.

## Fleet coordination (REQUIRED before applying)

JANITOR is tracking the identical drift class for ai-maestro-programmer-agent
(janitor #19). Converge programmer #19 + this proposal onto ONE canonical
publish-pipeline target so every role plugin re-standardizes to the same
template revision rather than drifting independently. Confirm the target
template revision with JANITOR + MANAGER first.

## Related minor cleanups (fold into the same maintenance pass)

Both are non-blocking advisories from the same v1.5.0 CPV run:

1. Dead URL `https://cli.github.com/packages` (HTTP 404) in
   `skills/maintainer-tooling-bootstrap/references/install-recipes.md` —
   re-verify (may be a link-checker FP on a browser-valid URL) then update or
   document.
2. `agents/ai-maestro-maintainer-agent-main-agent.md` body is 3176 words
   (CPV recommends <2000) — trim / move detail into references.

## Acceptance criteria

- RC-PIPELINE-DRIFT-001 clears for all three files (CPV `--strict` re-run).
- No maintainer-specific pipeline behavior lost (post-hoc gate, PAT preflight,
  retry shims, marketplace target all preserved).
- Full suite + lint + typecheck stay green; a real publish round-trips.
- The two minor advisories addressed or explicitly justified.
- Canonical template revision agreed with JANITOR (#19) + MANAGER before merge.

## Approval log

- 2026-06-12T00:48:40+0200 — Authored as `proposal` (tier 2) by maintainer-agent.
  Awaiting MANAGER approval + JANITOR/#19 canonical-target convergence.
- 2026-06-13T11:39:31+0200 — Premise INVALIDATED by ground-truth extraction (see
  STATE block): standardize would REGRESS the plugin (strips SHA-pins + hardening).
  Migration cancelled. No v1.5.1. Revised to upstream-to-canon + file CPV bug +
  fleet warning (janitor #19). This proposal effectively becomes a do-not-migrate
  record; the upstream/CPV-bug actions are tracked in task #100.
- 2026-06-22T03:07:45+0200 — APPROVED by USER via /go-on-yourself (tier 2; USER
  outranks MANAGER). column proposal→planned; moved design/proposals→design/tasks.
  Scope = option B: pipeline canon @ v2.143.0 + SBOM merge + action-pin bumps (#14),
  EXCLUDING the broken the-skills-menu conversion (CPV #150). It is a plugin project
  → publish via publish.py is authorized.
