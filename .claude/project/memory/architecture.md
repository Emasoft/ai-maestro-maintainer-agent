---
name: architecture
description: "how does ai-maestro-maintainer-agent work — overview, the main parts (guardian/patrol/workflow-* skills, the main agent, publish pipeline), where the key pieces live / how does the Sentinel scanning engine behind workflow-scan work and how do I add a rule to it / what severity should a new rule use"
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


^ATOM-23QN-F7D8 [desc:"Sentinel is the workflow-scan engine: scripts/sentinel/ + rules/ (34 auto-discovered files) — adding a rule is adding a file, there is no registry to edit", keywords: how_does_the_sentinel_scanner_work where_do_workflow_findings_come_from how_do_I_add_a_new_sentinel_rule workflow_scan_engine_layout 34_rule_files_under_scripts_sentinel_rules, ocd: 2026-08-06, lmd: 2026-08-06]

**Sentinel — the scanning engine behind `workflow-scan`,** and the largest
subsystem in the repo.

Layout (`scripts/sentinel/`): `rule_engine.py` holds one instance of every
registered rule, severity-ordered, and **auto-discovers them via the `rules`
package** — so adding a rule is adding a file under `scripts/sentinel/rules/`,
with no registry to edit. Supporting modules: `scanner.py`, `finding.py`,
`policy.py`, `workflow.py`, `sha_resolver.py`, `autofix.py`, `local_client.py`.
34 rule files ship today.

Tests live in `tests/test_sentinel_rules_{a..f}.py` plus `test_sentinel_core.py`
and `test_sentinel_autofix.py`; the `workflow-scan` skill owns the engine's
user-facing contract (severity classes, report layout).


^ATOM-HP0I-YJXV [desc:"Sentinel severity is a design decision: separate CAN-do from DOES-at-install from files-ARE-present, and justify the choice in the rule's own docstring", keywords: what_severity_should_a_new_sentinel_rule_use why_does_this_rule_fire_at_medium_not_critical capability_vs_execution_vs_presence detector_severity_convention why_not_report_an_opt_in_feature_as_critical, ocd: 2026-08-06, lmd: 2026-08-06]

**Choosing a Sentinel severity is a design decision, not a formality.** The
vocabulary is `critical | high | medium | low`, and the convention the shipped
rules follow is to keep three different states apart —
`generated_workflow_provenance.py` is the worked example:

    package CAN write agent-context files  -> informational (a dependency scan)
    package DOES at install time           -> critical
    the files are actually present         -> actionable  <- what that rule reports

That rule fires at `medium` deliberately. Reporting a documented opt-in feature
at critical is how a detector teaches its readers to discount it — so it is
already being ignored on the day a genuinely malicious package arrives. The same
reasoning says a remedy of "delete it" would be wrong here: a maintainer may have
adopted a generated workflow on purpose, so the fix text sends the reader to
`git log --follow` first.

A new rule carries that reasoning in **its own docstring**, as the shipped ones
do — the docstring is where the severity is justified and the first thing a
reviewer reads.

## Notes and lessons learned
