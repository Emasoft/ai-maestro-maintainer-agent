---
trdd-id: CLBRI62H
title: Backfill current-owner and task-type on the 10 TRDDs missing them (audit C2-1)
column: todo
created: 2026-08-18T19:55:21+0200
updated: 2026-08-18T19:55:21+0200
current-owner: maintainer-agent-session
task-type: docs
approval-tier: 0
created-by: TRDD-BRRJK57P phase-2 GO (hub 2026-08-18)
---

# Backfill current-owner and task-type on the 10 TRDDs missing them

Phase-2 remediation of CONFIRMED audit finding C2-1
(`reports/plugin-self-audit/20260816_190656+0200-audit.md`): 10 of 27 TRDDs
lack `current-owner:` and the SAME 10 lack `task-type:`. No grandfathering
clause exists; the v1→v2 migration section says the opposite (backfill them).
At least one affected card is OPEN (`column: backburner`).

## Task

Enumerate the 10 cards (`grep -L "^current-owner:" design/tasks/*.md
design/archived/*.md design/refused/*.md` — then Read each hit to confirm, per
claim-verification), add the two fields with values derived from each card's
own body/history. This is a MECHANICAL frontmatter repair that changes no
fact a card asserts: per TRDD rule 7, do NOT bump `updated:` (a repair bump
would reorder the whole board). Terminal-column cards: adding a missing
REQUIRED field is a machine-verifiable frontmatter completion, not a body edit.

## Acceptance

- [ ] every TRDD across design/tasks|archived|refused carries `current-owner:`
      and `task-type:`
- [ ] no `updated:` field changed on any repaired card
- [ ] values are per-card (owner from the card's history, task-type from its
      content), not one pasted constant

## Approval log
