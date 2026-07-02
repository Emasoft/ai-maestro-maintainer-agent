---
trdd-id: b8f4a7c2
title: Reconcile .githooks vs git-hooks push-protection convention — keep .githooks, fix install_hook
column: planned
created: 2026-07-02T11:33:28+0200
updated: 2026-07-02T11:33:28+0200
current-owner: maintainer-agent
assignee: maintainer-agent
priority: 4
severity: MEDIUM
effort: S
labels: [security, git-hooks, publish, ahead-of-canon]
task-type: security
parent-trdd: null
relevant-rules: []
release-via: publish
delivery: direct-push
target-branch: main
merge-strategy: squash
must-pass-tests-before-merge: true
test-requirements: [lint, typecheck]
audit-requirements: []
review-requirements: [human-review]
runtime-targets: [macos, linux]
impacts: [ci-pipeline]
external-refs: ["github.com/Emasoft/claude-plugins-validation/issues/118"]
implementation-commits: []
---

# Reconcile .githooks vs git-hooks push-protection convention

## ⏵ STATE — READ THIS FIRST ON RESUME (authoritative; supersedes the body) — 2026-07-02 (11:33)

**DECISION MADE (option B): KEEP `.githooks/pre-push` as the active, canonical push-protection hook; do NOT regress to canon's `git-hooks/`.** The only code change is making `publish.py --install-hook` install `.githooks/` (not `git-hooks/`) so fresh clones use the SAME proven hook. Investigation was read-only; NO code changed yet.

- **NEXT ACTION (implementation phase — do in a LEAN context, my own Edit, then test):**
  1. Edit `scripts/publish.py` `install_hook()` (≈L504-525): set `core.hooksPath=.githooks` and copy `.githooks/pre-push` into `.git/hooks/` (currently it installs `git-hooks/`). This is the load-bearing fix — it makes clones consistent with this machine.
  2. Dispose of `git-hooks/pre-push`: remove it (it becomes fully unused once install_hook points at `.githooks`) OR keep it with a one-line header comment `# INERT — canon-compat stub; the active hook is .githooks/pre-push (see TRDD-b8f4a7c2)`. Lean toward REMOVE to kill the "which hook is real?" ambiguity; note that a future CPV force-templates run may re-add it (documented drift, per RC-PIPELINE-DRIFT-001 — do not chase canon).
  3. Add a WHY comment at the `install_hook()` change site (Bug-Autopsy): "install the lean self-contained ancestry hook (.githooks), NOT canon's --gate-delegating hook, to avoid a redundant full-suite+network-CPV double-run at every publish's push step; canon's G0 ancestry check is equivalent security, so this is a cost fix not a security relaxation."
- **VERIFICATION (mandatory before considering done):** confirm a NON-publish.py `git push` is STILL REFUSED after the change. Test locally by invoking the hook path directly (a real push attempt to a throwaway ref, or run `.githooks/pre-push` with a simulated stdin ref-line and confirm exit 1 when no publish.py ancestor). Then a real `publish.py` run must still succeed (its push passes the ancestry check).
- **LOAD-BEARING FACTS (from the investigation, verified consistent):**
  - `.githooks/pre-push` (2688 B) = self-contained process-ancestry walk of parent PIDs (depth 15) matching `*python*scripts/publish.py*`; no ancestor → `exit 1`. Ancestry-only (no lint/tests). Currently ACTIVE (`core.hooksPath=.githooks`).
  - `git-hooks/pre-push` (384 B, canon) = delegates to `uv run python scripts/publish.py --gate`; INERT (hooksPath points at `.githooks`).
  - `publish.py --gate` → `run_gate` (≈L668+): G0 = `_called_by_publish_orchestrator` (≈L642-665) is the SAME ancestry walk (depth 30), THEN G1-G4 lint/jscpd/remote-CPV/tests. So canon's hook IS equivalent-or-stronger security, but double-runs the gates at push time (the orchestrator already ran lint/tests/validate non-skippably at ≈L1762-64).
  - `core.hooksPath` is LOCAL git config (NOT cloned) → a fresh clone has ZERO push protection until `publish.py --install-hook` runs; today `--install-hook` installs canon (`git-hooks`), silently diverging from this machine's `.githooks`. THIS is the inconsistency #117 reconciles.
- **DURABLE ARTIFACT (read before implementing):** `reports/maintainer-hooks/20260702_112937+0200-117-hook-convention-analysis.md` — full side-by-side, both scripts quoted, publish.py excerpts with line numbers.
- **SHIP:** via the next `publish.py` release (push-only-via-publish.py; a commit to main rides the next release). Authorized under the standing `/go-on-yourself` grant (plugin project → publish.py authorized). Does NOT relax security (keeps the proven hook + extends it to clones).

## Background

The repo carries TWO pre-push hooks — the ahead-of-canon self-contained ancestry guard `.githooks/pre-push` (what this dev machine actually runs) and canon's `git-hooks/pre-push` (what `publish.py --install-hook` installs). They diverge: a fresh clone gets canon, this machine runs the lean hook, and `core.hooksPath` (local-only) means clones are unprotected until `--install-hook`. #117 is to reconcile the two into one coherent convention.

## Investigation (read-only, agent-run 2026-07-02)

See the STATE block's LOAD-BEARING FACTS and the cited report. Bottom line: canon's hook is security-equivalent (same non-spoofable ancestry check via `--gate` G0) but costs a redundant lint/tests/network-CPV double-run at every publish's push step; the lean `.githooks/` hook runs the suite once.

## Decision — Option B: keep `.githooks/`, make it the one convention

Chosen over Option A (adopt canon `git-hooks/`, remove `.githooks/`) because:
- **Zero security gain from canon** — its G0 is the identical process-ancestry guard.
- **Concrete cost from canon** — a full-suite + network-CPV double-run on every publish.
- **Fits the documented ahead-of-canon posture** (RC-PIPELINE-DRIFT-001; the plugin deliberately stays ahead of canon and documents WHY rather than regressing — see memory `project_cpv_pipeline_drift_do_not_standardize`).
- **Safe-by-construction** — keeps the proven, battle-tested `.githooks/pre-push` UNCHANGED; the only edit makes `install_hook` install THAT same hook for clones, strengthening consistency without touching the security logic.

## Effects-handling / follow-ups

- The `install_hook()` edit is the substantive change; verify the ancestry refusal still holds (see VERIFICATION).
- If `git-hooks/` is removed, a future CPV `force-templates` migration may re-introduce it — that is expected documented drift; do not treat a re-added inert `git-hooks/pre-push` as a regression, just re-apply this reconcile (or leave it inert since install_hook no longer references it).

## Approval / authorization

Solo-dev context: the USER is the manager (per prrd-design-rules "operating outside AI Maestro"). Authorized under the standing `/go-on-yourself` grant; ships via `publish.py` (the only permitted push path). The change preserves security strictness (does not relax any gate).
