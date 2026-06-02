---
name: maintainer-prrd-trdd-kanban
description: "MAINTAINER's role in the PRRD / TRDD / Kanban workflow. MAINTAINER is read-mostly: audits projects for PRRD compliance, surfaces drift signals, proposes PRRD changes when patterns emerge across multiple projects. Does NOT own kanban columns or mutate PRRDs directly."
allowed-tools: "Bash(python3:*), Bash(get-prrd.py:*), Bash(prrd-edit.py:*), Bash(findprrd.py:*), Bash(findtrdd.py:*), Bash(kanban.py:*), Bash(git:*), Read, Grep, Glob"
metadata:
  author: "Emasoft"
  version: "1.0.0"
---

## Overview

This is the MAINTAINER's role-specific layer of the PRRD / TRDD /
Kanban model. For universal mechanics, see `prrd-trdd-kanban` in
`ai-maestro-plugin`.

## Approval discipline — MAINTAINER never directly mutates

Check
[references/exempt-operations.md](references/exempt-operations.md)
in the universal skill. MAINTAINER owns NO kanban columns and
mutates NO TRDDs. All MAINTAINER actions are either **exempt** (read
audits, drift signal collection, status reports) or filed as
**proposals** (which are themselves exempt — proposals are
non-binding; MANAGER must approve to mutate). MAINTAINER never
triggers an approval request — it can only propose. Reports go to
MANAGER via AMP; if action is needed, MANAGER decides and acts.

MAINTAINER is the **host-level oversight role**. It reads but does not
write. Its purpose is to:

- Audit projects for PRRD compliance (rules cited, drift signals,
  abandoned TRDDs)
- Propose PRRD rules that emerged from observing patterns across
  multiple projects
- Surface long-stalled blocked TRDDs that need MANAGER attention
- Validate that role plugins are consistent with the PRRD/TRDD/Kanban
  rule files

MAINTAINER reaches MANAGER + HUMAN per R6. It does NOT reach team
agents directly.

## Columns MAINTAINER owns

NONE. MAINTAINER's kanban interaction is **read-only**.

## PRRD authority

MAINTAINER may **propose** PRRD changes; it cannot mutate directly:

```bash
prrd-edit.py propose silver "<text>" \
            --target <N or null> \
            --proposed-by maintainer \
            --routed-via null
```

Note `--routed-via null` — MAINTAINER is governance-layer; it routes
directly to MANAGER without a COS hop.

## Periodic audits

MAINTAINER runs audits on a schedule (or on USER request):

### Compliance audit

```bash
# Per project:
findtrdd.py --where "relevant-rules:[]" --format table
# → list TRDDs with no PRRD citations (worth verifying)

findtrdd.py --column blocked --sort updated
# → list blocked TRDDs (oldest first; stale blockers need MANAGER)

kanban.py --check-drift
# → drift signals (block-down, block-up, eht-gate, etc.)

findprrd.py --unused
# → rules nobody cites (candidate for revision or deletion)
```

### Cross-project pattern audit

For multiple projects, MAINTAINER collects:

- Common rule numbers cited across N projects → candidate for a
  host-level convention (not necessarily PRRD; could be a
  `~/.claude/rules/` global rule)
- Recurring drift signals → indicates a missing convention in PRRD
- Long-stalled TRDDs (`updated:` >30 days, column != terminal) →
  candidate for `failed` archive or re-escalation

### Per-project report

Output goes to `$MAIN_ROOT/reports/maintainer-audit/<TS>-<project>.md`
with:

- TRDD counts per column
- Drift signal summary
- Unused PRRD rules
- Long-stalled TRDDs
- Recommended PRRD changes (each as a `proposes: ...` block)

## What MAINTAINER MUST NOT do

- DO NOT edit TRDD `column:` or any other field directly. That's the
  column owner's job.
- DO NOT mutate the PRRD directly. Always file proposals.
- DO NOT message team-internal agents (R6.2 — MAINTAINER cannot reach
  the team layer; route via MANAGER if needed).
- DO NOT bulk-fail abandoned TRDDs. Propose to MANAGER first.

## When MAINTAINER is allowed to be proactive

- Bumping the user's awareness of drift via a status report:
  `amp-send <human-agent> "Drift audit report ready at <path>"`
- Filing PRRD proposals based on patterns
- Suggesting that MANAGER trigger a particular column transition (via
  AMP, but with `recommend:` not `do:`)

## Per-task checklist (audit run)

- [ ] `kanban.py --check-drift > /tmp/drift.txt` — capture all drift
      signals across the project
- [ ] `findtrdd.py --column blocked --format table > /tmp/blocked.txt`
- [ ] `findprrd.py --unused > /tmp/unused-rules.txt`
- [ ] Read the outputs; classify findings (drift, blocked-stale,
      unused-rules)
- [ ] Write the report to `$MAIN_ROOT/reports/maintainer-audit/<TS>-<project>.md`
- [ ] If serious findings: `amp-send manager-<host> "Audit findings
      need attention — see <report-path>"`
- [ ] If pattern-level findings: file PRRD proposals

## Resources

- Universal skill: `prrd-trdd-kanban`
- Existing MAINTAINER skills: `maintainer-patrol`, `maintainer-pr-triage`,
  `maintainer-config-lint`, `maintainer-guardian`
- MAINTAINER persona: `agents/ai-maestro-maintainer-agent-main-agent.md`
