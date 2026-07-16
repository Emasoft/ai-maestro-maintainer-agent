---
trdd-id: 27IG72GX
title: Align plugin skills and docs with the ai-maestro governance and script-surface deltas from the issue 67 briefing
column: planned
created: 2026-07-16T15:43:43+0200
updated: 2026-07-16T15:43:43+0200
current-owner: ai-maestro-maintainer-agent
created-by: ai-maestro-maintainer-agent
task-type: feature
release-via: publish
min-approval-requirement: manager
mandate: true
mandated-by: user
approved: true
approval-judge: user
approval-datetime: 2026-07-16T15:43:43+0200
npt: []
eht: []
---

# Align plugin skills and docs with the ai-maestro governance and script-surface deltas (issue 67 briefing)

## ⏵ STATE — READ THIS FIRST ON RESUME (authoritative; supersedes the body) — 2026-07-16

- **NEXT ACTION:** execute Phase 1 (5-file edit set below), verify, commit, then Phase 2.
- Briefing source: the ai-maestro Claude's reply on <https://github.com/Emasoft/ai-maestro/issues/67>
  (fetched 2026-07-16; canonical overlay text re-fetched from
  `rules/aimaestro/aimaestro-trdd-approval.md` @ `governance-rules` — NEVER port from the
  issue prose alone).
- Load-bearing facts: top approval rung is `user` (`maestro` = deprecated read-alias,
  normalize on read, never write); `approval-tier:` decode is ON-NEXT-TOUCH only (no mass
  rewrite; absent/unknown ⇒ `manager`); R43–R48 are SPEC-ONLY (unenforced — do NOT port);
  downstream hosts provisioned by `install.sh` get `main` = ZERO governance docs and 12/75
  scripts ⇒ every skill must PROBE CAPABILITY (`command -v`, `--help`), never version.
- SUPERSEDED — do NOT carry forward: `approval-tier: N` as a field to write; the skill name
  `amama-proposal-approvals` (never shipped — real name `amama-approval-workflows`; this
  plugin verified clean of it 2026-07-16).

## Context

Issue #67 asked the ai-maestro Claude for the governance + script-surface deltas since the
R26–R40 propagation. The reply (2026-07-16) identified deltas this plugin's v1.7.19 copy
predates. Verified footprint in THIS plugin (greps, 2026-07-16): `approval-tier` appears in
3 shipped files + 2 board READMEs; the new frontmatter fields appear nowhere; 3
`aimaestro-*.sh` scripts are cited whose manifest tier is unverified.

## Scope

Update the plugin's own skills/agent docs/board seeds to the current overlay semantics, and
verify the cited script surface against the frozen contract. NOT in scope: porting R43–R48
(spec-only), mass-rewriting archived TRDDs (frozen + on-next-touch policy), issue #27 (joint
testing plan — its own thread), any change to ai-maestro's repo (cross-project; issues only).

## Implementation order

- **Phase 1 (≤5 files)** — `min-approval-requirement:` migration + new-field documentation:
  1. `skills/maintainer-trdd-adr/references/trdd-template.md` — replace the `approval-tier:`
     field mention; add the approval/mandate/derived/judgment field set, the depth-1 rule,
     and the completion gate (NPT gates `dev`, EHT gates `complete`).
  2. `skills/maintainer-trdd-adr/references/seed-readmes.md` — seeded README text names the
     floor field + deprecation.
  3. `design/proposals/README.md` — field usage + tier naming.
  4. `agents/ai-maestro-maintainer-agent-main-agent.md` — ladder text names the field.
  5. (this TRDD — dogfoods the schema.)
- **Phase 2** — fetch `docs/SCRIPT-MANIFEST.md` §2 (`governance-rules` branch); verify the
  tiers of the 3 cited scripts (`aimaestro-agent.sh`, `aimaestro-governance.sh`,
  `aimaestro-teams.sh`); fix any Tier-D (dead) caller; bake the capability-probe rule into
  the skills that touch the ai-maestro surface.
- **Phase 3** — adopt `aimaestro-trdd.sh` (SCRIPT-MANIFEST §5.4 assigns adoption to this
  repo): a capability-probed skill covering the write verbs + token-based `verify`
  (exit 0 verified / 2 NOT verified / 1 error; `archive --state` refuses `failed`).
  Then tests, CPV `--strict` clean, release via `publish.py`.

## Verification

- `grep -rn "approval-tier" skills/ commands/ agents/` → only decode-context mentions
  (deprecation notes), zero prescriptive uses.
- `uv run tests/run-all-tests.py` green; CPV remote-validate `--strict` → 0/0/0/0.
- Phase 2: each cited script's tier documented in this TRDD; no Tier-D caller remains.

## Out of scope (deferred)

R43–R48 (unenforced spec); archived/refused TRDDs carrying `approval-tier:` (frozen;
on-next-touch policy applies if ever touched); `aimaestro-session.sh` / `aimaestro-panel.sh`
adoption (candidates for a follow-up TRDD after `aimaestro-trdd.sh` proves the pattern).

## Approval log

- 2026-07-16T15:43:43+0200 — MANDATE issued by USER (min-approval-requirement: manager).
  Pre-approved: issuer authority >= required approver. No approval request was sent.
  Instruction (session, 2026-07-16): "be sure to align with ai-maestro claude" — work scoped
  by the ai-maestro reply to Emasoft/ai-maestro#67.
