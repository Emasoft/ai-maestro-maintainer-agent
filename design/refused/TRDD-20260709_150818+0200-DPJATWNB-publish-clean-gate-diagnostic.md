---
trdd-id: DPJATWNB
title: Diagnose stray runtime artifacts in the publish.py clean-tree gate
column: proposal
approval-tier: 2
created: 2026-07-09T15:08:18+0200
updated: 2026-07-09T15:08:18+0200
current-owner: ai-maestro-maintainer-agent
task-type: infra
priority: 5
severity: LOW
effort: S
labels: [publish, fleet-readiness, diagnostics]
release-via: publish
delivery: direct-push
target-branch: main
test-requirements: [lint, typecheck]
audit-requirements: []
review-requirements: []
relevant-rules: []
parent-trdd: null
supersedes: []
impacts: [ci-pipeline]
implementation-commits: []
published-version: null
published-at: null
external-refs: ["github.com/Emasoft/ai-maestro-maintainer-agent/issues/26"]
---

# TRDD-DPJATWNB — Diagnose stray runtime artifacts in the publish.py clean-tree gate

## STATE — READ THIS FIRST ON RESUME (authoritative) — 2026-07-09T15:08:18+0200

**Current state: PROPOSAL, awaiting Tier-2 (MANAGER/USER) approval. Nothing implemented.
NEXT ACTION: approver decides; on approval `git mv` this file to `design/tasks/`, set
`column: planned`, then implement the diagnostic in `scripts/publish.py::stage_check_clean`.**

- This is a **latent** risk, not an active bug. Verified 2026-07-09: today's `.gitignore`
  covers every path the persona/skills declare they write, so the gate does not misfire.
- `scripts/publish.py` is a **protected path** (`maintainer-approval-gate`
  `references/protected-paths.md`), which is why this is `approval-tier: 2` and lives in
  `design/proposals/` rather than being edited directly.
- **Do NOT weaken the gate.** The fail-fast behaviour is correct and must be preserved.
  This proposal only makes the failure *diagnosable*. See "Non-goals".

## Problem

`scripts/publish.py::stage_check_clean` (lines 887-895) is step `[1/11]` of the publish
pipeline:

```python
def stage_check_clean(root: Path) -> None:
    """Step 1: Working tree must be clean."""
    r = run(["git", "status", "--porcelain"], cwd=root, capture=True)
    if r.stdout.strip():
        cprint(f"  {RED}Working tree is dirty. Commit or stash changes first.{NC}")
        sys.exit(1)
```

It is an unconditional hard-fail on ANY non-ignored dirty or untracked path, with **no
distinction and no diagnostic** between:

1. a stray tracked-file edit the developer forgot to commit (the intended catch), and
2. an **AI-Maestro runtime artifact that landed outside every ignored path**.

The message prints no paths, so the operator sees only `Working tree is dirty` with no clue
which file caused it.

## Why it matters (the fleet-self-maintenance angle)

Issue #26 imports this repo as a **fleet agent** whose workdir root IS this repo's own git
root. On import and on every wake, AI Maestro seeds runtime files into the workdir
(`.claude/settings.local.json`, `.claude/rules/aimaestro-*.md`, plus `.janitor/`,
`reports*/`, `*_dev/`). Today all of those are ignored (`.gitignore` verified path-by-path,
plus a managed `.git/info/exclude` block on import), so `git status --porcelain` stays empty
and the gate passes.

But this repo's own `publish.py` is exactly what the agent (or a human) invokes to release
this plugin. If **any future** AI-Maestro runtime artifact is ever written to a path not
covered by the ignore set — a session marker, a lock file, tmux state — then
`stage_check_clean` will **silently block every future publish of this repo**, self-publish
included, with a message that names no file. The failure mode is high-friction and the
diagnosis is manual.

## Evidence / provenance

- Surfaced by the #26 B2 fleet-readiness audit, ITEM 2 (verdict **PASS**, with this recorded
  as the single residual CONCERN). Audit report:
  `reports/maintainer-fleet-readiness/20260709_015409+0200-b2-audit.md` (gitignored).
- Related shipped work: commit `56de645` (#26 G1/G2 — in-place self-maintenance topology +
  flag-don't-self-publish). That commit is what makes this repo self-maintaining, and hence
  what makes this latent risk worth tracking.
- Packaging itself was audited clean: publish is git-native (`gh release create` on the
  pushed tag, no filesystem-walking bundler), so there is **no** exclusion list to fix — the
  single source of truth is `.gitignore`. Only the *gate's diagnostic* is at issue.

## Proposed change

In `stage_check_clean`, keep the hard-fail, but make it explain itself:

1. Capture the porcelain output and **print the offending paths** (capped, e.g. first 20)
   instead of a bare message.
2. Classify each offending path against a known **AI-Maestro runtime-artifact prefix list**
   (`.claude/`, `.aimaestro/`, `.janitor/`, `reports/`, `reports_dev/`, `*_dev/`,
   `.trashcan/`, `.serena/`, `.rechecker/`, `llm_externalizer_output/`).
3. When a path matches a runtime prefix but is **not** ignored, emit an explicit,
   actionable hint: this is an un-ignored AI-Maestro runtime artifact — add it to
   `.gitignore` (a deliberate, reviewed edit) — rather than leaving the operator to guess.
4. When a path does not match, keep today's message ("commit or stash").
5. Exit non-zero in **both** cases. Unchanged.

## Non-goals (explicit — do not do these)

- **Never auto-add anything to `.gitignore`.** `.gitignore` is a protected path; widening
  the ignore set is a reviewed human decision, never a publish-time side effect.
- **Never auto-stash, auto-commit, auto-clean, or `--force` past the gate.** No workaround,
  no bypass, no fallback. The gate either passes or the publish exits non-zero.
- **Never downgrade the exit code** or make the gate skippable via an env var.
- Do not touch the packaging step; it is already git-native and correct.

## Acceptance criteria

- [ ] `stage_check_clean` prints every offending path (capped) on failure.
- [ ] A path under a known runtime prefix that is not ignored produces the distinct
      "un-ignored AI-Maestro runtime artifact" hint naming that path.
- [ ] Any other dirty path produces the existing "commit or stash" message.
- [ ] Exit code is `1` in both cases (unchanged); a clean tree still exits `0` and proceeds
      to step `[2/11]`.
- [ ] No change to `.gitignore`, to the packaging step, or to any other pipeline stage.
- [ ] `ruff` + `mypy` clean; CPV validate gate green.

## Verification

1. Clean tree → `publish.py` proceeds past `[1/11]` (regression check).
2. `touch .claude/UNIGNORED_MARKER` after temporarily un-ignoring it → gate exits `1` and
   the output names `.claude/UNIGNORED_MARKER` with the runtime-artifact hint.
3. Edit a tracked source file → gate exits `1` with the "commit or stash" message naming
   that file.
4. Confirm exit codes with `echo $?` in all three cases.

## Approval log

<!-- Approver appends: "- <ISO> — APPROVED|REFUSED by <approver> (tier 2). <rationale>." -->
