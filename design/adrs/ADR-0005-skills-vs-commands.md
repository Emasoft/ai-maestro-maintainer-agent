# ADR-0005 — Skills as primary surface; slash-commands as discoverability layer

Status: accepted
Date: 2026-05-27
Authors: Emasoft

## Context

Claude Code plugins expose three callable surfaces:

1. **Skills** (`skills/<name>/SKILL.md`) — invoked by the agent
   when the user's intent matches the skill's frontmatter. The
   agent reads SKILL.md, then executes the documented steps.
2. **Slash commands** (`commands/<name>.md`) — invoked explicitly
   by the user typing `/<name>`. The command file documents the
   command for the agent.
3. **Subagents** (`agents/<name>.md`) — invoked by the main agent
   via the Agent tool. Subagents have their own (isolated)
   context window.

Until now this plugin shipped 11 skills + 1 main agent + 0
commands + 0 subagents. The all-skill design has two known costs:

- **Discoverability.** A new user reading the README can see the
  skill names but cannot fire them with one keystroke. They must
  type a natural-language phrase the skill's `description: |`
  matches.
- **Documentation pressure.** Without slash commands, every skill's
  description must do double duty — both onboarding ("here is
  what this skill does") and intent matching ("trigger on these
  phrases"). The result is description bloat.

Audit A (the full plugin audit, 2026-05-27) flagged this as
F4 — "high-value flows lack slash commands; discoverability suffers"
— and recommended adding slash commands for the major user-invokable
flows.

The question is not "skills or commands" — both are useful — but
"which surface is **primary** for a given flow?"

## Decision

**Skills remain primary; slash commands are a discoverability
layer on top of skills.**

Concretely:

- Every user-facing operation is implemented as a skill. The skill
  is the source of truth.
- For each user-invokable operation (i.e. excluding internal-only
  skills like `maintainer-triage` that the agent calls
  reflexively), we add a thin slash command under `commands/`
  that the user can type to trigger the skill explicitly.
- A slash command file is at most ~40 lines: a description, an
  optional argument schema, and an "invoke the SKILL" body. It
  does NOT duplicate skill logic.

The mapping for this plugin (deferred to a follow-up commit
within Wave 1.F of TRDD-e1c2677a):

| Slash command | Skill it fires |
|---|---|
| `/maintainer-scan-workflows` | `workflow-scan` |
| `/maintainer-fix-safe` | `workflow-fix-safe` |
| `/maintainer-pin-actions` | `workflow-pin-actions` |
| `/maintainer-protect-branch` | `workflow-protect-branch` APPLY |
| `/maintainer-show-branch-rules` | `workflow-protect-branch` SHOW |
| `/maintainer-guardian-baseline` | `maintainer-guardian` BASELINE |
| `/maintainer-guardian-scan` | `maintainer-guardian` SCAN |
| `/maintainer-sandbox-preflight` | `maintainer-sandbox` (preflight) |
| `/maintainer-sandbox-precheck` | `maintainer-sandbox` (precheck) |
| `/maintainer-bootstrap-ci` | `workflow-bootstrap` |

Skills that are internal-only (the agent's own decision logic —
`maintainer-triage`, `maintainer-fix`, `maintainer-patrol`,
`maintainer-approval-gate`) do NOT get slash commands; they are
not user-invokable operations.

## Consequences

**Easier:**

- New users discover operations by typing `/` and reading the
  command list — standard Claude Code behaviour.
- Each skill's description can focus on intent-matching, leaving
  onboarding to the command files + README.
- A user who wants to fire a specific operation without crafting a
  natural-language phrase can type the slash command directly.

**More difficult:**

- We now maintain two surfaces per user-facing operation (the
  skill + the command). Mitigated by the command files being
  thin (one-screen documents that just point at the skill).
- A skill rename requires updating the corresponding command file.
  Mitigated by the small command-file size.

**Neutral:**

- We do not change skill behavior. The slash commands are pure
  discoverability — typing `/maintainer-scan-workflows` is
  equivalent to saying "scan workflows" in chat, both fire the
  same skill body.
- The mapping above is the *initial* set. Future operations get a
  slash command iff they are user-invokable; internal operations
  remain skill-only.

## References

- Audit A finding F4 — `reports/audit/20260527_131719+0200-audit-A-skills-agent.md`
- Claude Code commands documentation (as of v2.1.x).
- The TRDD this ADR supports: `design/tasks/TRDD-20260527_140000+0200-e1c2677a-full-plugin-audit-fix.md`
  Wave 1.F.
