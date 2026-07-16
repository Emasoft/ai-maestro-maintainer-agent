# `design/proposals/` — TRDDs awaiting approval

A TRDD lives here while it is a **request, not a commitment**: authored with
`column: proposal` in its frontmatter, awaiting the approval its
`min-approval-requirement:` names (`orchestrator`/`chief-of-staff` · `manager`
· `user`). The legacy `approval-tier: N` field is deprecated — decode-only
(`1 → chief-of-staff`/`orchestrator`, `2 → manager`, `3 → user`), migrated on
next touch, never written on a new TRDD. Nobody is expected to execute a TRDD
while it sits in this folder.

On approval the approver sets `column: planned`, records the decision in the
TRDD body `## Approval log`, and `git mv`s the file into `design/tasks/`
(preserving history). On refusal the approver sets `column: refused` and
`git mv`s it into `design/refused/`.

**The MAINTAINER is a governance-layer peer (R19) — it has NO CHIEF-OF-STAFF
and files manager-floor proposals (`min-approval-requirement: manager`)
DIRECTLY to MANAGER** (see the persona's *Approval Tiers* section and
`~/.claude/rules/trdd-approval-tiers.md`).

Tier-0 work (the agent's own in-scope DERIVED tasks — NPT/EHT — and applying
the ratified baseline as-is) skips this folder entirely: author directly in
`design/tasks/` as `column: planned`.
