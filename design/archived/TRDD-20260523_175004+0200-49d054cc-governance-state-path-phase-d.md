---
trdd-id: 49d054cc-042f-4c33-b2b3-b7947fd2a8d4
title: Governance state-path fix — relocate per-agent state from $HOME to AGENT_DIR (Phase D)
column: completed
created: 2026-05-23T17:50:04+0200
updated: 2026-08-07T12:08:37+0200
---

## TRDD-49d054cc — Governance state-path fix — relocate per-agent state from $HOME to AGENT_DIR (Phase D)

**Filename:** `design/tasks/TRDD-20260523_175004+0200-49d054cc-governance-state-path-phase-d.md`
**Tracked in:** this repo (design/tasks/ is git-tracked)

## Implementing commit

- 5995a26 — `fix(governance): relocate per-agent state from $HOME to AGENT_DIR (Phase D)`

## User request (verbatim, reconstructed from commit body + upstream issue)

> Resolves the upstream governance issue filed at
> https://github.com/Emasoft/ai-maestro/issues/32. Previously, all
> per-agent state — issue ledger, branch-rules cache, Guardian
> baseline and per-cycle state, per-session repo clone — was written
> under $HOME (~/.aimaestro/maintainer/<id>/ and $HOME/agents/<name>/).
> This is invisible to AI Maestro backups and does not survive
> host-to-host migration. The maintainer was breaking the two pillars
> AI Maestro sells: backup/recovery and agent portability.

This TRDD undoes a deliberate Phase B choice (TRDD-2a34e0cd) that
located the Guardian baseline under `~/.aimaestro/maintainer/<id>/`.
The Phase B choice was locally correct (per-session isolation, no
conflicts between agent instances) but breaks AI Maestro's two
load-bearing guarantees:

1. **Backup/recovery.** AI Maestro backs up the agent's working
   directory, not arbitrary subtrees of `$HOME`. State under
   `$HOME/.aimaestro/...` is invisible to backups.
2. **Agent portability.** Moving an agent between hosts (a routine
   AI Maestro flow) ships the working directory only. State under
   `$HOME` doesn't travel.

## Scope — five state paths, one resolution chain

All five state paths now resolve via the AGENT WORKING DIRECTORY:

```bash
AGENT_DIR="${AIMAESTRO_AGENT_DIR:-${CLAUDE_PROJECT_DIR:-$PWD}}"
```

| State file                                          | Purpose                                  | Regenerable? |
|-----------------------------------------------------|------------------------------------------|--------------|
| `$AGENT_DIR/.aimaestro/state/processed-issues.json` | Patrol ledger (issue de-dupe)            | No           |
| `$AGENT_DIR/.aimaestro/state/branch-rules.json`     | Protect-branch cache                     | Yes (refetch)|
| `$AGENT_DIR/.aimaestro/state/guardian-baseline.json`| Guardian baseline (T1–T5 snapshot)       | Yes (rescan) |
| `$AGENT_DIR/.aimaestro/state/guardian-state.json`   | Guardian per-cycle (delta tracking)      | Yes (rescan) |
| `$AGENT_DIR/.aimaestro/workspace[-<sid>]/`          | Fix-skill repo clone                     | Yes (reclone)|

The resolution chain prefers `AIMAESTRO_AGENT_DIR` (the env var
proposed in upstream ai-maestro#32), falls back to
`CLAUDE_PROJECT_DIR` (Claude Code's existing standard), and only
uses `$PWD` as a last resort. Skills work today with
`CLAUDE_PROJECT_DIR`; flipping AI Maestro to export
`AIMAESTRO_AGENT_DIR` is a single env-var change with no plugin
updates required.

## Design decisions

1. **One canonical resolution chain everywhere.** All five state
   paths use the EXACT same `AGENT_DIR` expression. No skill is
   allowed to invent its own resolution. Grep for the expression
   and you find every state read/write site.
2. **`.aimaestro/state/` is a single directory.** Everything
   non-regenerable (the ledger) and the small fast-rebuild caches
   live in one place. The fix-skill workspace clone lives at
   `.aimaestro/workspace[-<sid>]/` because it's large and
   per-session; bundling it with `state/` would mean copying
   gigabytes on every backup.
3. **Resolution chain prefers the new env var.** `AIMAESTRO_AGENT_DIR`
   first so future AI Maestro versions can set it explicitly.
   `CLAUDE_PROJECT_DIR` second so the agent works today inside
   Claude Code without AI Maestro changes. `$PWD` last because
   it's the only resolution that can be wrong (if the user
   `cd`'d before invoking the agent).
4. **The workspace clone is documented as regenerable.** First
   fix post-migration triggers a fresh clone. This means upgrading
   does NOT preserve any pending uncommitted work in the workspace
   — that work is by design transient (the fix skill always
   commits before reporting done).
5. **`.gitignore` adds `/.aimaestro/`.** State files are
   per-agent and per-host. They must not be committed. AI Maestro
   backups handle them; git stays clean.
6. **Two-pillar reasoning is documented in the main agent file.**
   The new "State paths (governance)" section at the top of
   `agents/ai-maestro-maintainer-agent-main-agent.md` lists every
   state file, the resolution chain, and the two load-bearing
   reasons (backup, migration). Future readers see the constraint
   without grepping the upstream issue.
7. **Never-write-under-$HOME warnings inline in every skill.**
   Each touched SKILL.md gets an explicit warning so future edits
   don't regress.

## Files touched (commit 5995a26)

```
.gitignore                                                       (MOD, +/.aimaestro/)
README.md                                                        (MOD, +Guardian Mode subsection)
agents/ai-maestro-maintainer-agent-main-agent.md                 (MOD, +State paths section)
ai-maestro-maintainer-agent.agent.toml                           (MOD, primary skill list)
hooks/hooks.json                                                 (MOD, AGENT_DIR-rooted reminder)
skills/maintainer-approval-gate/SKILL.md                         (MOD)
skills/maintainer-fix/SKILL.md                                   (MOD)
skills/maintainer-fix/references/fix-steps.md                    (MOD, workspace path)
skills/maintainer-guardian/SKILL.md                              (MOD)
skills/maintainer-guardian/references/threat-classes.md          (MOD, baseline + state paths)
skills/maintainer-patrol/SKILL.md                                (MOD, ledger path)
skills/maintainer-patrol/references/patrol-loop.md               (MOD)
skills/workflow-protect-branch/SKILL.md                          (MOD)
skills/workflow-protect-branch/references/instructions.md        (MOD, cache write snippet)
```

## Acceptance criteria (all met by 5995a26)

- [x] Every state path resolves via the `${AIMAESTRO_AGENT_DIR:-${CLAUDE_PROJECT_DIR:-$PWD}}`
      chain. Grep confirms no leftover `~/.aimaestro/...` or
      `$HOME/agents/...` writes.
- [x] `.gitignore` ignores `/.aimaestro/`.
- [x] Main agent file has a "State paths (governance)" section at
      the top.
- [x] Each touched SKILL.md has an explicit "never-write-under-$HOME"
      warning.
- [x] Workspace clone documented as regenerable; first fix
      post-migration re-clones.
- [x] `agent.toml` primary skills list adds `maintainer-guardian`
      and `maintainer-approval-gate`; `workflow-*` family moves
      to secondary.
- [x] README gains a "Guardian Mode" subsection naming the two
      new skills.

Verification (run at commit time):
- uvx zizmor: 0 findings on every workflow.
- CPV strict: CRITICAL=0, MAJOR=0.
- All ten SKILL.md files under 5000 chars.
- All "Use when" + "Trigger with" phrases present in every
  touched skill description.

## Post-mortem

**What worked:**
- The resolution-chain expression is short enough to memorize.
  Future skills (and future audits) can verify compliance with a
  single grep for the substring `AIMAESTRO_AGENT_DIR`.
- Putting the governance reasoning in the main agent file
  (top-of-file, not buried) makes the constraint discoverable for
  anyone editing the maintainer.
- Bundling the env-var fallback chain (AIMAESTRO_AGENT_DIR →
  CLAUDE_PROJECT_DIR → $PWD) means the migration to AI Maestro
  doesn't require coordinated releases — the plugin works in
  both worlds simultaneously.

**What was tricky:**
- The Phase B baseline path (`~/.aimaestro/maintainer/<id>/`) was
  the LOCALLY right answer (per-session isolation, no cross-agent
  collisions). It was the GLOBALLY wrong answer (breaks AI Maestro
  pillars). The lesson: design choices in a plugin must consider
  the upstream operating environment, not just the plugin's local
  guarantees.
- Several SKILL.md files cited the OLD path verbatim in their
  prose. A search-and-replace approach would have missed cases
  where the path was mentioned in passing without being a code
  block. Each file got a Read + Edit instead.
- The workspace clone's "regenerable" status means uncommitted
  work in the workspace is lost on migration. This is technically
  a regression from Phase B (where the clone lived under
  `$HOME/agents/<name>/` and survived) — but the fix skill never
  reports done with uncommitted work, so the regression is
  invisible in normal operation.

**Lessons for future work:**
- When a plugin runs inside a host platform (Claude Code,
  AI Maestro, etc.), every persistent state path must use the
  platform's blessed environment variable. `$HOME` is a code
  smell.
- The env-var fallback pattern (`${A:-${B:-$C}}`) is the
  load-bearing primitive for cross-platform agents. Document the
  expression once; reuse it everywhere.
- Cross-repo issues (upstream ai-maestro#32) drove this fix.
  Future TRDDs that respond to upstream issues should link the
  issue URL at the top of the file.
