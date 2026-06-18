---
trdd-id: dfd73e4e-d34f-4e81-b110-8ee960884be5
title: Propagate governance R26-R40 into maintainer persona + skills + docs + governance scenarios
column: dev
created: 2026-06-19T00:01:53+0200
updated: 2026-06-19T00:01:53+0200
current-owner: ai-maestro-maintainer-agent
assignee: ai-maestro-maintainer-agent
priority: 2
severity: MEDIUM
effort: M
labels: [governance, fleet-coordination, persona]
task-type: docs
parent-trdd: null
relevant-rules: []
release-via: publish
delivery: direct-push
target-branch: main
test-requirements: [lint]
review-requirements: [human-review]
impacts: []
external-refs: ["github.com/Emasoft/ai-maestro-maintainer-agent/issues/16", "github.com/Emasoft/ai-maestro/issues/38", "github.com/Emasoft/ai-maestro/issues/37"]
---

# TRDD-dfd73e4e — Propagate governance R26-R40 into maintainer persona + SCEN

## ⏵ STATE — READ THIS FIRST ON RESUME (authoritative) — 2026-06-19

**Why:** MANAGER coordination issue **#16** (filed 2026-06-18) directs every
role-plugin persona to internalize fleet governance **R26-R40**
(GOVERNANCE-RULES.md **v4.0.2**, landed via ai-maestro **#38** CLOSED; #37 is the
older R23-R25 decoupling issue the MANAGER cross-referenced loosely). AMAMA
**v2.12.0** is the reference implementation (persona + skills + docs +
`tests/scenarios/governance-scenarios.md`). USER `/goal` standing order covers
it ("complete all pending tasks; coordinate with the MAESTRO plugin's claude via
GitHub issues"); the MANAGER explicitly authorized the publish step.

**Audit finding (verify-before-act):** my plugin has **NO OLD-model statements to
reverse** — no agent sudo/governance-password (only a benign Docker
`usermod -aG docker` recipe), no "COS-assignment-USER-only / MANAGER-recommends-COS".
The MAINTAINER is a governance-layer non-team agent, so it never carried the OLD
team/sudo model. This is **additive internalization**, not reversal. Existing
R6/R19/R23 citations stay valid (R23 = decoupling, per the v3.11.0 renumber).

**Maintainer-relevant R26-R40 subset (from #16 emphasis + canonical doc):**
- R26 immutable identity — I never self-change TITLE/ROLE/NAME/AID (only USER/MANAGER; I have no COS).
- R27 self-install only via core `ai-maestro-plugin` skills + MANAGER approval + server CPV scan.
- R28 three-check authz (AID → TITLE → portfolio token); never assert my own title; server never trusts client-supplied id/title/scope.
- R29.3 the MANAGER creates/deletes MAINTAINER agents (me) on its own authority; R29-R31 team lifecycle = awareness only (I don't run teams).
- R32 (CRITICAL) NO agent sudo gates — AID+title+portfolio token IS my authorization; a sudo `--password` is a USER-via-UI residual I SURFACE to the MAESTRO, never perform.
- R33/R34 signed-ledger is the source of truth for my auth state (valid AID with no ledger history = refused).
- R35/R40 foreign-host agent/user needs MAESTRO approval (awareness).
- R36/R37 obey the MANAGER; the MANAGER obeys only the MAESTRO; one MAESTRO/host; single MAESTRO-DELEGATE.
- R38/R39 non-MAESTRO user restrictions + the new ASSISTANT agent (awareness; I don't interact with these).

**NEXT ACTION:** Phase 2 — add a "Governance core (R26-R40)" internalization
section to `agents/ai-maestro-maintainer-agent-main-agent.md`; add a README note;
create `tests/scenarios/governance-scenarios.md`; CPV `--strict` clean; publish
via publish.py; reply on #16 when done.

## Plan (phased)
1. ✅ Phase 0 — gather canonical sources (GOVERNANCE-RULES.md v4.0.2 R26-R40 + #16/#37/#38), audit plugin. DONE.
2. Phase 2 — persona internalization (additive R26-R40 section, maintainer subset). ≤1 file.
3. Phase 3 — README governance note + `tests/scenarios/governance-scenarios.md` (mirror AMAMA). ≤2 files.
4. Phase 4 — CPV `--strict` clean (respect `.markdownlint.json`; the MD025 fix is already in place).
5. Phase 5 — publish via publish.py (MANAGER-authorized); reply on #16; close TRDD → published.

## Acceptance criteria
- Persona carries an explicit R26-R40 internalization (maintainer subset), no OLD-model contradictions remain (verified: none existed).
- `tests/scenarios/governance-scenarios.md` exists with maintainer governance scenarios.
- CPV `--strict` clean.
- Shipped via publish.py; #16 replied/closed.

## Durable artifacts to read before acting
- Canonical rules: `/tmp/GOVERNANCE-RULES.md` (v4.0.2, R26-R40 at lines 1211-1364) — re-fetch from ai-maestro `governance-rules` branch if gone.
- MANAGER task: issue #16 (this repo). Governance landing: ai-maestro#38 (closed).
- Reference impl: ai-maestro-assistant-manager-agent v2.12.0 (persona + governance-scenarios.md).
