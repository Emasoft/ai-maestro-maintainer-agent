---
trdd-id: f6a48a71-1259-471e-9517-ca25105c0138
title: Migrate to janitor-hosted global 3-scope markdown memory system
column: dev
created: 2026-06-16T01:28:16+0200
updated: 2026-06-16T01:28:16+0200
current-owner: ai-maestro-maintainer-agent
assignee: ai-maestro-maintainer-agent
priority: 3
severity: MEDIUM
effort: M
labels: [memory, migration, fleet-coordination]
task-type: refactor
parent-trdd: null
relevant-rules: []
release-via: publish
delivery: direct-push
target-branch: main
test-requirements: [lint]
review-requirements: [human-review]
impacts: [config-schema]
external-refs: ["github.com/Emasoft/ai-maestro-maintainer-agent/issues/12", "github.com/Emasoft/ai-maestro-assistant-manager-agent/issues/15"]
---

# TRDD-f6a48a71 — Migrate to janitor-hosted global 3-scope markdown memory

## ⏵ STATE — READ THIS FIRST ON RESUME (authoritative) — 2026-06-16

**Why:** JANITOR spec (issue #12) — the fleet adopts ONE shared markdown
wiki-memory system, **janitor-hosted and global**. Role plugins must NOT
ship their own memory skills. The USER authorized execution (2026-06-16
`/goal`: "complete all your pending tasks").

**Gate status: CLEARED.** janitor **0.8.10** ships the global
`janitor-memory-{bootstrap,recall,update,write}` skills (verified
2026-06-16). The migration is now unblocked.

**Current plugin state (verified 2026-06-16):**
- Still ships: `skills/maintainer-memory-recall`, `skills/maintainer-memory-write`,
  `rules/memory-protocol.md` (6627 B). All THREE must be removed.
- `.claude/project/memory/` NOT bootstrapped yet. `.claude/` is gitignored
  (`.gitignore:47`) with no exception.
- No plugin-root `CLAUDE.md` exists (target for folding plugin-UNIQUE content).
- Main agent: `agents/ai-maestro-maintainer-agent-main-agent.md`.

**NEXT ACTION:** Phase 1 — run `/janitor-memory-bootstrap` (additive).

**Plan (phased — destructive removal is LAST):**
1. **Bootstrap (additive):** `/janitor-memory-bootstrap` → creates
   `.claude/project/memory/` + the gitignore exception
   (`!.claude/project/` + `!.claude/project/memory/**`) + starter hub +
   `MEMORY.md`.
2. **Proactive contract (additive):** add the PROACTIVE MEMORY CONTRACT to
   the main agent doc AND propagate it into every skill that spawns
   sub-agents (sub-agents inherit nothing). Contract = recall-before-acting ·
   write/update-after-solving · maintain-the-wikimem · scope-routing
   (private→LOCAL, project-shared→PROJECT, cross-project→USER; unsure→LOCAL).
   Use the FIXED **array-form** recall (`ROOTS=(); … ROOTS+=("$d"); memgrep
   recall "$SYMPTOM" "${ROOTS[@]}"`) — the zsh word-split fix (janitor df2e563).
3. **Fold unique content:** read `rules/memory-protocol.md` +
   `maintainer-memory-{recall,write}/SKILL.md`; preserve any plugin-UNIQUE
   guidance (NOT already in the global skills/rule) into the main-agent doc
   or a new plugin `CLAUDE.md` BEFORE removal.
4. **Remove (destructive — commit first per RULE 0):** delete
   `skills/maintainer-memory-recall`, `skills/maintainer-memory-write`,
   `rules/memory-protocol.md`. Update README skills table (−2 rows).
5. **Verify + release:** CPV `--strict` clean; bundle into the next
   publish.py release (this repo pushes only via publish.py).

**SEQUENCING (open):** asked JANITOR/MANAGER on #12 whether removal should be
fleet-gated. Decision: land additive parts (1+2+3) immediately; the removal
(4) can proceed since the global skills are confirmed present — a role
plugin removing its local copy while the global skills exist leaves NO gap.

**SUPERSEDED — do NOT carry forward:**
- ✗ Old PROJECT scope `<git-root>/memory/` → now `<repo>/.claude/project/memory/`.
- ✗ Old space-joined `ROOTS` recall form (zsh silent-fail) → array form.

## Acceptance criteria
- `.claude/project/memory/` bootstrapped + gitignore exception present.
- Main agent + sub-agent-spawning skills carry the proactive contract.
- The 3 per-plugin memory artifacts removed; no dangling references
  (grep `maintainer-memory` / `memory-protocol` → only historical/TRDD hits).
- CPV `--strict` clean.

## Durable artifacts to read before acting
- JANITOR spec: issue #12 (the design spec).
- MANAGER sequencing: ai-maestro-assistant-manager-agent#15.
- `~/.claude/rules/markdown-memory-recall.md` (the recall protocol + scopes).
