---
name: maintainer-prrd-trdd-kanban
description: "MAINTAINER's role in the PRRD / TRDD / Kanban workflow. MAINTAINER is read-mostly: audits projects for PRRD compliance, surfaces drift signals, proposes PRRD changes when patterns emerge across multiple projects. Does NOT own kanban columns or mutate PRRDs directly."
metadata:
  author: "Emasoft"
  version: "1.0.0"
---

## Overview

MAINTAINER is the host-level, read-mostly oversight layer of the PRRD /
TRDD / Kanban model. It owns NO kanban columns and mutates NO TRDDs. It
audits projects for PRRD compliance, surfaces drift signals, and proposes
PRRD changes — but every change is filed as a non-binding proposal that
MANAGER must approve. MAINTAINER reaches MANAGER + HUMAN per R6; it never
reaches team agents directly. For the universal mechanics, see the
`prrd-trdd-kanban` skill in `ai-maestro-plugin`.

## Prerequisites

- The universal `prrd-trdd-kanban` skill (in `ai-maestro-plugin`) for the
  shared workflow mechanics and the exempt-operations rules.
- A PRRD plus a populated `design/tasks/` TRDD set in each audited project.
- Read access to the projects under audit (the audit is read-only).

## Instructions

1. Run `kanban.py --check-drift > /tmp/drift.txt` to capture every drift
   signal across the project (block-down, block-up, eht-gate, etc.).
2. Run `findtrdd.py --column blocked --sort updated --format table >
   /tmp/blocked.txt` to list blocked TRDDs, oldest first (stale blockers
   need MANAGER attention).
3. Run `findprrd.py --unused > /tmp/unused-rules.txt` to find PRRD rules
   nobody cites (candidates for revision or deletion).
4. Read the three outputs and classify the findings: drift, blocked-stale,
   and unused-rules.
5. Write an audit report to
   `$MAIN_ROOT/reports/maintainer-audit/<TS>-<project>.md` with TRDD counts
   per column, the drift summary, unused rules, long-stalled TRDDs, and a
   `proposes:` block per recommended PRRD change.
6. For patterns that recur across projects, file a PRRD proposal:
   `prrd-edit.py propose silver "<text>" --target <N or null> --proposed-by
   maintainer --routed-via null` (governance routes straight to MANAGER, no
   COS hop).
7. If findings are serious, notify MANAGER over AMP:
   `amp-send manager-<host> "Audit findings need attention — see <path>"`.

## Output

- An audit report file at
  `$MAIN_ROOT/reports/maintainer-audit/<TS>-<project>.md`.
- Zero or more PRRD proposals filed via `prrd-edit.py propose`.
- An AMP note to MANAGER (and HUMAN per R6) when action is needed, phrased
  as `recommend:` not `do:` — MAINTAINER recommends, MANAGER decides.

## Error Handling

- Never edit a TRDD `column:` (or any TRDD field) directly — that is the
  column owner's job; surface it to MANAGER instead.
- Never mutate the PRRD directly — always file a proposal. Proposals are
  exempt and non-binding; only MANAGER approval mutates the PRRD.
- Never bulk-fail abandoned TRDDs — propose the archive to MANAGER first.
- Never message team-internal agents (R6.2); route through MANAGER.

## Examples

Drift audit run for one project:

```bash
kanban.py --check-drift > /tmp/drift.txt
findtrdd.py --column blocked --sort updated --format table > /tmp/blocked.txt
findprrd.py --unused > /tmp/unused-rules.txt
# classify, then write $MAIN_ROOT/reports/maintainer-audit/<TS>-<project>.md
amp-send manager-host "Audit findings need attention — see <report-path>"
```

A recurring drift signal seen across several projects becomes a proposal:

```bash
prrd-edit.py propose silver "Require relevant-rules on every TRDD" \
            --target null --proposed-by maintainer --routed-via null
```

## Resources

See the universal `prrd-trdd-kanban` skill in `ai-maestro-plugin` for the
shared mechanics and its `exempt-operations.md` reference, which defines
why audits, status reports, and proposals are exempt. Companion MAINTAINER
skills cover patrol, PR triage, and config linting; the MAINTAINER persona
lives with the agent definition in this plugin.
