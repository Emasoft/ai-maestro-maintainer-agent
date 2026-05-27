# ADR-0003 — Per-agent state under `$AGENT_DIR/.aimaestro/state/`, not `$HOME`

Status: accepted
Date: 2026-05-27
Authors: Emasoft

## Context

The maintainer agent writes several long-lived state files:

| File | Purpose |
|---|---|
| `processed-issues.json` | Issue ledger — which #N have already been triaged this session |
| `branch-rules.json` | Cached branch-protection ruleset, refreshed pre-push |
| `guardian-baseline.json` | Clean snapshot of T1-T6 threat state captured at session start |
| `guardian-state.json` | Per-cycle Guardian deltas + open approval requests |
| `workspace-<sid>/` | Per-session clone of the maintained repo, used for fix branches |

Versions of this plugin earlier than v1.1.0 wrote these under
`$HOME/.aimaestro/state/`. That choice was simple — `$HOME` is
guaranteed to exist on every POSIX system. But it had three real
problems:

1. **AI Maestro backups missed it.** The AI Maestro orchestrator
   takes snapshots of each running agent's working directory so
   that the agent can be exported / imported between hosts. A
   restored agent starts with the working dir intact but
   `$HOME/.aimaestro/state/` gone, so the ledger is empty, the
   Guardian baseline is missing, and the agent re-processes
   already-handled issues.
2. **Host-to-host migration loses state.** Same root cause: the
   migration tool ships the agent working dir, not `$HOME`.
3. **Multiple agents on the same host collide.** Two MAINTAINER
   agents on the same host (one per repo) both write to
   `$HOME/.aimaestro/state/<basename>.json` and step on each
   other.

The v1.1.0 Phase-D work (TRDD-49d054cc) relocated state into the
agent's working directory.

## Decision

Every persistent file the agent writes lives under the **agent
working directory**, not `$HOME`. The agent working directory is
resolved with this priority:

```bash
AGENT_DIR="${AIMAESTRO_AGENT_DIR:-${CLAUDE_PROJECT_DIR:-$PWD}}"
```

1. **`$AIMAESTRO_AGENT_DIR`** — the canonical AI Maestro env var.
   When AI Maestro exports it (proposed in
   <https://github.com/Emasoft/ai-maestro/issues/32>), every skill
   uses it as the root.
2. **`$CLAUDE_PROJECT_DIR`** — Claude Code's standard project dir
   env var. Current actual production value.
3. **`$PWD`** — last-resort fallback for unmanaged runs.

State paths (per the main agent's frontmatter section "State paths"):

```
$AGENT_DIR/.aimaestro/state/processed-issues.json
$AGENT_DIR/.aimaestro/state/branch-rules.json
$AGENT_DIR/.aimaestro/state/guardian-baseline.json
$AGENT_DIR/.aimaestro/state/guardian-state.json
$AGENT_DIR/.aimaestro/workspace-<sid>/
```

`.aimaestro/` is added to `.gitignore` so the state never lands in
git.

## Consequences

**Easier:**

- AI Maestro backups + host migration capture the agent's full
  state automatically.
- Multiple MAINTAINER agents on the same host never collide —
  each has its own `$AGENT_DIR/.aimaestro/state/`.
- The agent's persistence is co-located with its code; an
  operator browsing the working dir sees the ledger right next to
  the agent's frontmatter.

**More difficult:**

- An agent whose `$AIMAESTRO_AGENT_DIR` / `$CLAUDE_PROJECT_DIR` is
  unset (truly unmanaged) writes to `$PWD/.aimaestro/state/` —
  which migrates with the working dir but may surprise an
  operator who expected `$HOME`. Mitigated by the main-agent
  frontmatter explicitly documenting the resolution priority.
- The repo's own `.gitignore` must list `.aimaestro/`. Confirmed
  present at the time of this ADR.

**Migration:**

- Existing agents with state under `$HOME/.aimaestro/state/`
  receive a one-time migration step in publish.py (also already
  shipped in v1.1.0). The shim is kept in place until v2.0 — at
  that point the legacy path becomes a fail-fast (no automatic
  migration).

## References

- Implementing TRDD: `design/tasks/TRDD-20260523_175004+0200-49d054cc-governance-state-path-phase-d.md`
- Main agent reference section: `agents/ai-maestro-maintainer-agent-main-agent.md` "State paths"
- AI Maestro env var proposal: <https://github.com/Emasoft/ai-maestro/issues/32>
- Default `.gitignore` covers `.aimaestro/`: confirmed
  in `.gitignore:75`.
