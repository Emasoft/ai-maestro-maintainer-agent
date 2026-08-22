---
name: maintainer-prrd-trdd-kanban
description: "MAINTAINER's role in the PRRD / TRDD / Kanban workflow. MAINTAINER is read-mostly: audits projects for PRRD compliance, surfaces drift signals, proposes PRRD changes when patterns emerge across multiple projects. Does NOT own kanban columns or mutate PRRDs directly."
metadata:
  author: "Emasoft"
  version: "1.1.0"
---

## Overview

MAINTAINER is the host-level, read-mostly oversight layer of the PRRD /
TRDD / Kanban model. It owns NO kanban columns and mutates NO TRDDs. It
audits projects for PRRD compliance, surfaces drift signals, and proposes
PRRD changes — but every change is filed as a non-binding proposal that
MANAGER must approve. MAINTAINER reaches MANAGER + HUMAN per R6; it never
reaches team agents directly. For the universal mechanics, use the granular
`ama-*` skills in `ai-maestro-plugin` — `ama-kanban-render`,
`ama-trdd-{find,write,update,transition}`, `ama-prrd-{get,find,edit,propose}`,
and `ama-proposal-approvals` — which replaced the retired monolithic
`prrd-trdd-kanban` skill. They own the `scripts/prrd-trdd/` governance
scripts; this wrapper never calls those scripts directly.

## Prerequisites

- The granular `ama-*` PRRD / TRDD / kanban skills (in `ai-maestro-plugin`)
  for the shared workflow mechanics and the exempt-operations rules —
  chiefly `ama-kanban-render`, `ama-trdd-find`, `ama-prrd-find`, and
  `ama-prrd-propose` (plus the write/edit/transition/approval variants).
- A PRRD plus a populated `design/tasks/` TRDD set in each audited project.
- Read access to the projects under audit (the audit is read-only).
- **Frozen CLI only (IRON RULE).** Every ai-maestro interaction goes through the
  frozen scripts and the `ama-*` skills — here, `aimaestro-message.sh send`
  (with `amp-send` as the explicit degrade path where the CLI is absent) and
  `aimaestro-trdd.sh`. Exit codes (3 transport / 4 not-found / 5 ambiguous /
  6 R6-refused — follow the hint on stderr verbatim / 7 auth), the
  recipient-resolve recipe, and the never-pass-`--from`-as-an-agent rule are
  owned by
  [approval-request.md](../maintainer-approval-gate/references/approval-request.md).
  NEVER call the ai-maestro server `/api/*` directly, not even as a fallback
  when a script is missing: degrade explicitly instead.
  (`gh` APIs are NOT covered — keep them.)

## Instructions

1. Invoke the `ama-kanban-render` skill in its drift view (`--check-drift`)
   to capture every drift signal across the project (block-down, block-up,
   eht-gate, stale `updated:`, etc.).
2. Invoke the `ama-trdd-find` skill (`--column blocked --sort updated
   --format table`) to list blocked TRDDs, oldest first (stale blockers
   need MANAGER attention).
3. Invoke the `ama-prrd-find` skill (`--unused`) to find PRRD rules nobody
   cites (candidates for revision or deletion).
4. Read the three outputs and classify the findings: drift, blocked-stale,
   and unused-rules.
5. Write an audit report to
   `$MAIN_ROOT/reports/maintainer-audit/<TS>-<project>.md` with TRDD counts
   per column, the drift summary, unused rules, long-stalled TRDDs, and a
   `proposes:` block per recommended PRRD change.
6. For patterns that recur across projects, file a PRRD proposal via the
   `ama-prrd-propose` skill (`silver "<text>" --target <N or null>
   --proposed-by maintainer --routed-via null` — governance routes straight
   to MANAGER, no COS hop). A proposal is non-binding and never mutates the
   PRRD directly.
7. If findings are serious, notify MANAGER over AMP:
   `aimaestro-message.sh send "$MANAGER" --subject "Audit findings need attention" --body "See <path> for details" --type alert`
   (fallback where the CLI is absent:
   `amp-send "$MANAGER" "Audit findings need attention" "See <path> for details" --type alert`).
   Resolve `$MANAGER` with the recipe in `approval-request.md` in the
   `maintainer-approval-gate` skill's references — never send to the
   `manager-<host>` placeholder.

## Output

- An audit report file at
  `$MAIN_ROOT/reports/maintainer-audit/<TS>-<project>.md`.
- Zero or more PRRD proposals filed via the `ama-prrd-propose` skill.
- An AMP note to MANAGER (and HUMAN per R6) when action is needed, phrased
  as `recommend:` not `do:` — MAINTAINER recommends, MANAGER decides.

## Error Handling

- Never edit a TRDD `column:` (or any TRDD field) directly — that is the
  column owner's job (via `ama-trdd-transition` / `ama-trdd-update`);
  surface it to MANAGER instead.
- Never mutate the PRRD directly — always file a proposal via
  `ama-prrd-propose`. Proposals are exempt and non-binding; only MANAGER
  approval (through `ama-prrd-edit` / `ama-proposal-approvals`) mutates the
  PRRD.
- Never bulk-fail abandoned TRDDs — propose the archive to MANAGER first.
- Never message team-internal agents (R6.2); route through MANAGER.

## Examples

Drift audit run for one project — invoke the read-only pillar skills, then
classify and report:

- `ama-kanban-render` (`--check-drift`) → drift signals.
- `ama-trdd-find` (`--column blocked --sort updated --format table`) →
  blocked TRDDs, oldest first.
- `ama-prrd-find` (`--unused`) → uncited PRRD rules.
- Classify the three outputs, then write
  `$MAIN_ROOT/reports/maintainer-audit/<TS>-<project>.md`.
- Notify MANAGER over AMP:
  `aimaestro-message.sh send "$MANAGER" --subject "Audit findings need attention" --body "See <report-path> for details" --type alert`
  (fallback where the CLI is absent: `amp-send "$MANAGER" "Audit findings need attention" "See <report-path> for details" --type alert`;
  `manager-host` is not a resolvable name — resolve `$MANAGER` per
  `approval-request.md` in the `maintainer-approval-gate` skill's references).

A recurring drift signal seen across several projects becomes a proposal —
invoke `ama-prrd-propose`:

`silver "Require relevant-rules on every TRDD" --target null --proposed-by maintainer --routed-via null`

## Resources

- [AMP approval-request template](../maintainer-approval-gate/references/approval-request.md)
  — owns the exit codes, the recipient-resolve recipe, and the
  never-pass-`--from`-as-an-agent rule this skill defers to:
  - When you send this
  - Resolve the recipient BEFORE composing
  - The message
  - Recording the answer
  - When the answer is "no"
  - The protected-edit variant (human, not AMP)

See the granular `ama-*` skills in `ai-maestro-plugin` for the shared
mechanics — each ships its own reference docs, and `ama-trdd-transition`'s
`exempt-operations.md` reference defines why audits, status reports, and
proposals are exempt. Companion MAINTAINER skills cover patrol, PR triage,
and config linting; the MAINTAINER persona lives with the agent definition
in this plugin.
