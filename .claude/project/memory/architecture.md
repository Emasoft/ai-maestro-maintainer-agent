---
name: architecture
description: "how does ai-maestro-maintainer-agent work — overview, the main parts (guardian/patrol/workflow-* skills, the main agent, publish pipeline), where the key pieces live"
ocd: 2026-06-16
lmd: 2026-06-16
metadata:
  node_type: memory
  type: project
  tier: hub
  functionality: architecture
  globs: ["skills/**", "agents/**", "commands/**", "hooks/**", "scripts/**"]
---
ai-maestro-maintainer-agent — a Claude Code PLUGIN that acts as the fleet
**MAINTAINER**: it hardens entrusted GitHub repos (branch + tag rulesets,
SHA-pinned Actions, config lint, secret scans), runs CPV `--strict`
validation, patrols for threats as the repo **guardian**, and coordinates
the other ai-maestro plugins (MANAGER, JANITOR, role agents) via GitHub
issues. It is published via the CPV canonical pipeline (`scripts/publish.py`)
and is the single authoritative writer of the ruleset-config domain (PRRD S9).

## Parts map
- **Main agent** — `agents/ai-maestro-maintainer-agent-main-agent.md` (the
  orchestrator: triage → fix → guardian → coordinate).
- **Guardian/patrol skills** — `skills/maintainer-guardian` (threat classes
  T1–T5), `skills/maintainer-patrol`, `skills/maintainer-triage`,
  `skills/maintainer-fix`.
- **Workflow skills** — `skills/workflow-protect-branch` (the ratified
  3-ruleset baseline), `skills/workflow-pin-actions`, `skills/workflow-fix-safe`,
  `skills/workflow-bootstrap`, `skills/workflow-scan`.
- **Governance skills** — `skills/maintainer-prrd-trdd-kanban`,
  `skills/maintainer-detect-stack`.
- **Publish pipeline** — `scripts/publish.py` (CPV canonical; the ONLY push
  path — a pre-push hook refuses all other pushes), `.github/workflows/`
  (validate / release / notify-marketplace).

## Applies to
- (radiates down to component/aspect pages as they're written — wire the
  reciprocal `## Governed by` on each)

## See also
- (lateral links to other functionality hubs, once they exist)

## Notes and lessons learned
