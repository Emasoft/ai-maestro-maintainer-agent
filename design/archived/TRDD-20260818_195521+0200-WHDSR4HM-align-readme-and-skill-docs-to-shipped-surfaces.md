---
trdd-id: WHDSR4HM
title: Align README and skill docs to the shipped surfaces (audit C1-1 C1-2 C1-3)
column: completed
created: 2026-08-18T19:55:21+0200
updated: 2026-08-18T20:02:00+0200
current-owner: maintainer-agent-session
task-type: docs
approval-tier: 0
created-by: TRDD-BRRJK57P phase-2 GO (hub 2026-08-18)
---

# Align README and skill docs to the shipped surfaces

Phase-2 remediation of three CONFIRMED Phase-1 audit findings
(`reports/plugin-self-audit/20260816_190656+0200-audit.md`, items C1-1..C1-3).
One atomic task: make the docs state only what the plugin actually ships.

## The three defects (each re-verified in Phase 1)

1. **C1-1** — `README.md:219` promises a bundled `/fewer-permission-prompts`
   skill that does not exist anywhere in the repo (only hit repo-wide; not a
   harness built-in; no skill provides it under another name). Remove the claim
   (or reword to reference the harness-level skill without claiming bundling).
2. **C1-2** — rule count overstated: README says 32 (`README.md:231`, `:305`);
   real count is 31 (runtime registry; 34 rule files − 3 infra; 33 `^class` − 2
   bases). Correct both sites. NOTE the falsifier's trap: a naive `(Rule)`
   substring grep undercounts to 28 because 3 subclasses use `(Rule, GuardPatterns)`.
3. **C1-3** — README + `skills/maintainer-patrol/SKILL.md:47-49` describe the
   SessionStart hook as "firing" a skill; `hooks/hooks.json` holds one
   `"type": "command"` entry (an `echo`) and a command hook cannot invoke a
   skill. Reword both sites to what the hook actually does.

## Acceptance

- [x] `grep -rn "fewer-permission-prompts" README.md` → no bundling claim
      (now "Claude Code's built-in … harness-provided, not bundled")
- [x] README rule count reads 31 at both former sites; count re-verified
      first-hand: 31 classes extend `Rule` in `scripts/sentinel/rules/`
      (4 via `(Rule, GuardPatterns)`)
- [x] README and maintainer-patrol SKILL.md describe the SessionStart hook as a
      command/echo nudge, not a skill invocation
- [x] full-repo sweep found TWO stale copies beyond the audit's sites —
      `agents/ai-maestro-maintainer-agent-main-agent.md:247` and
      `commands/maintainer-scan-workflows.md:9` (both said 32) — corrected

## Approval log

- 2026-08-18T20:02:00+0200 — COMPLETED by maintainer-agent-session under the
  hub's Phase-2 GO (Tier-0 docs remediation). All four acceptance checks
  verified by grep after edit.
