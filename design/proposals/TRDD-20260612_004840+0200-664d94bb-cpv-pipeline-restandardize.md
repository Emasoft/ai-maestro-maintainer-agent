---
trdd-id: 664d94bb-2609-4789-a0c5-e22fa1f96c93
title: CPV canonical-pipeline re-standardization — clear RC-PIPELINE-DRIFT-001
column: proposal
created: 2026-06-12T00:48:40+0200
updated: 2026-06-13T11:39:31+0200
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
external-refs: ["github.com/Emasoft/ai-maestro-maintainer-agent/issues/10", "github.com/Emasoft/ai-maestro-janitor/issues/19", "github.com/Emasoft/ai-maestro-janitor/issues/26"]
---

# CPV canonical-pipeline re-standardization — clear RC-PIPELINE-DRIFT-001

## ⏵ STATE — READ THIS FIRST (authoritative; supersedes the body below) — 2026-06-13

**FINDING (2026-06-13): the premise was wrong — DO NOT migrate.** I extracted
canon's actual templates in an isolated worktree (`cpv-remote-validate
standardize . --fix --force-templates`) and diffed. The result: running
standardize would **REGRESS** the maintainer plugin across all three files —
it is NOT behind canon, it is strictly **AHEAD**:

- `release.yml`: standardize reverts SHA-pinned `actions/checkout@de0fac…#v6.0.2`
  → **unpinned `actions/checkout@v4`** (a supply-chain regression), removes
  `permissions: contents: read` + `persist-credentials: false`, and **deletes
  the post-hoc validate-tag CPV gate** to restore the old release-creating job.
- `notify-marketplace.yml`: removes the MARKETPLACE_PAT preflight, removes
  `permissions` + `timeout`, reverts the dispatch action to an older SHA, drops
  version-in-payload.
- `publish.py`: strips the `# type: ignore[no-redef,misc]` tuples the plugin's
  mypy gate needs.

Canon ships **none** of the actionlint / commitlint / macOS-matrix /
env-sanitization the RC-PIPELINE-DRIFT-001 remediation text advertises — its
templates are stale relative to its own advice.

**REVISED ACTION (replaces "Proposed change" below):**
1. **Do NOT run standardize. Do NOT ship a v1.5.1 for this.** Keep all three
   files as-is — the warnings are "plugin ahead of canon," documented intentional.
2. **UPSTREAM** the maintainer's pipeline improvements into the CPV canonical
   templates (file on `claude-plugins-validation`) so the drift resolves at the
   source.
3. **File a CPV bug**: RC-PIPELINE-DRIFT-001 (a) can't distinguish "ahead" from
   "behind" — it tells ahead-plugins to downgrade; (b) its remediation text
   claims SHA-pinned actions / actionlint / commitlint / macOS matrix that the
   shipped `--force-templates` output does not contain (it even emits unpinned
   `checkout@v4`).
4. **Warn the fleet**: the programmer-agent (janitor #19) was advised to run the
   same `--force-templates` — it would strip ITS SHA-pins too. Posted the
   correction on #19.

Evidence diffs preserved: `/tmp/canon-workflows.diff`, `/tmp/canon-publish.diff`.
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
