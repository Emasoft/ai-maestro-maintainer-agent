# `design/proposals/` — TRDDs awaiting approval

A TRDD lives here while it is a **request, not a commitment**: authored with
`column: proposal` in its frontmatter, awaiting the approval its
`approval-tier:` requires (Tier 1 COS · Tier 2 MANAGER · Tier 3 USER). Nobody
is expected to execute a TRDD while it sits in this folder.

On approval the approver sets `column: planned`, records the decision in the
TRDD body `## Approval log`, and `git mv`s the file into `design/tasks/`
(preserving history). On refusal the approver sets `column: refused` and
`git mv`s it into `design/refused/`.

**The MAINTAINER is a governance-layer peer (R19) — it has NO CHIEF-OF-STAFF
and files Tier-2 proposals DIRECTLY to MANAGER** (see the persona's
*Approval Tiers* section and `~/.claude/rules/trdd-approval-tiers.md`).

Tier-0 work (the agent's own in-scope DERIVED tasks — NPT/EHT — and applying
the ratified baseline as-is) skips this folder entirely: author directly in
`design/tasks/` as `column: planned`.
