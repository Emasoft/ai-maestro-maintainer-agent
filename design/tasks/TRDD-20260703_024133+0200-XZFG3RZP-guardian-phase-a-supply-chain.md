---
trdd-id: XZFG3RZP
title: Guardian Mode Phase A supply-chain hardening
column: dev
created: 2026-07-03T02:41:33+0200
updated: 2026-07-03T02:41:33+0200
current-owner: amama
task-type: security
release-via: publish
delivery: direct-push
target-branch: main
test-requirements: [lint, typecheck]
review-requirements: [code-review]
impacts: [ci-pipeline]
relevant-rules: []
---

# Guardian Mode Phase A — supply-chain hardening

## ⏵ STATE — READ THIS FIRST ON RESUME (authoritative; supersedes the body) — 2026-07-03

- **Scope.** Phase A ("mechanical fixes" A1/A2/A3) of the Guardian-Mode plan
  (`~/.claude/plans/rustling-sniffing-melody.md`). Phases B/C/D are OUT of scope.
- **Verified state — read the files, do NOT trust the plan's gap list.** On
  inspection all three "gaps" were already implemented and committed (v1.4.0 era,
  file dates 2026-05-21 .. 2026-06-10):
  - **A1 / GAP-1 — Dependabot for `github-actions`:** `.github/dependabot.yml`
    already present and a SUPERSET of the plan's minimal spec (adds `day: monday`,
    `include: scope`, `labels`, `open-pull-requests-limit`). No edit — overwriting
    with the minimal spec would REGRESS it.
  - **A2 / GAP-4 — bootstrap seeds supply-chain config:** the templates
    (`templates/dependabot.yml`, `templates/npmrc-hardened`) plus `SKILL.md` and
    `references/instructions.md` (Step 5) already seed `.github/dependabot.yml`
    (always) and `.npmrc` (Node). The ONE genuine residual gap: the seeded
    `.npmrc` template lacked `ignore-scripts=true` (the #1 npm install-time RCE
    vector — lifecycle scripts) and `save-exact=true` (no caret drift into a
    republished malicious patch). → **ADDED** (integrating; the existing 5-day
    quarantine / no-downgrade / block-exotic-subdeps / frozen-lockfile /
    audit-level=high defences are preserved untouched).
  - **A3 / GAP-2 — jq `--arg` trap detector:** already present in
    `workflow-fix-safe` `SKILL.md` (description + Step 3) and
    `references/instructions.md` (Step 4 "jq command-substitution audit"), with
    worked vulnerable/hardened examples and the detection regex. No edit.
- **NEXT ACTION.** None left for Phase A — the single code change (npmrc) is
  applied. Ship it bundled with the already-committed token-efficiency fix
  (`1726642`) as v1.7.5 via `uv run python scripts/publish.py --patch`.
- **Load-bearing facts / gotchas.** publish.py is the ONLY push path (pre-push
  ancestry hook refuses all other pushes). CPV `--strict` + zizmor gate the
  release. `.markdownlint.json` already sets `front_matter_title: ""`, so this
  TRDD's frontmatter `title:` does NOT collide with its body `# H1` under MD025.
  uv.lock self-version already synced to 1.7.4 (matches plugin.json) → no
  dirty-tree lag at the publish gate.
- **SUPERSEDED — do NOT carry forward.** The plan's claim that GAP-1 and GAP-2
  are "remaining" — VERIFIED false; both were closed in earlier work.
- **Durable artifacts.** Plan: `~/.claude/plans/rustling-sniffing-melody.md`.
  Report: `reports/maintainer-guardian-phase-a/`.

## Why

The article "Supply chain attacks are at an all-time high" (Atai Barkai,
2026-05-20) catalogues 8 OSS attack vectors. The maintainer's audit mapped three
of them onto Phase-A "mechanical" gaps:

- **GAP-1** — no Dependabot for the `github-actions` ecosystem, so SHA-pinned
  actions go silently stale and miss upstream security patches. Pinning is half
  the discipline; Dependabot is the other half.
- **GAP-2** — no detector for the jq `--arg` trap: a `${VAR}` interpolated into a
  double-quoted jq FILTER string is a bash-command-substitution / JSON-injection
  vector. It is distinct from `${{ }}` expression injection (which `env:` routing
  already defeats) — bash expands the value before jq ever parses it.
- **GAP-4** — `workflow-bootstrap` must seed the same Dependabot config + a
  hardened `.npmrc` into every newly-entrusted repo so the defence propagates,
  not just this plugin.

All three were found already implemented on inspection. The residual real gap was
the seeded `.npmrc` missing `ignore-scripts=true` / `save-exact=true`; those two
settings are added here without regressing the existing (richer) hardening. This
TRDD is the audit trail recording that Phase A is satisfied and shipped in v1.7.5.

## File manifest

| File | Change |
|---|---|
| `.github/dependabot.yml` | none — already present (verified superset of spec) |
| `skills/workflow-bootstrap/references/templates/dependabot.yml` | none — already present |
| `skills/workflow-bootstrap/references/templates/npmrc-hardened` | EDIT — add `ignore-scripts=true` + `save-exact=true` |
| `skills/workflow-bootstrap/SKILL.md` | none — already documents the seeding |
| `skills/workflow-bootstrap/references/instructions.md` | none — already documents Step 5 seeding |
| `skills/workflow-fix-safe/SKILL.md` | none — already lists the jq `--arg` trap audit |
| `skills/workflow-fix-safe/references/instructions.md` | none — already has the jq audit |

## Approval log

- 2026-07-03T02:41:33+0200 — APPROVED by go-on-yourself standing authorization (Tier-2 .github edit; solo dev, user is manager). Rationale: closes GAP-1/2/4 supply-chain hardening.

## Notes and lessons learned

- Verify the working tree before "implementing" a plan's steps: this plan's gap
  list was stale (GAP-1/GAP-2/GAP-4 already closed in earlier releases). Blindly
  executing the mechanical steps would have overwritten richer, already-shipped
  config with a weaker minimal spec — a security regression disguised as
  "following the plan". Read the files; trust the files over the description.
