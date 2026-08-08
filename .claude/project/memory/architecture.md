---
name: architecture
description: "how does ai-maestro-maintainer-agent work — overview, the main parts (guardian/patrol/workflow-* skills, the main agent, publish pipeline), where the key pieces live / how does the Sentinel scanning engine behind workflow-scan work and how do I add a rule to it / what severity should a new rule use / I edited the main agent persona and the test suite went red — what pins the kanban columns and the frozen-CLI prohibition / the test table shows no docstring on every row"
ocd: 2026-06-16
lmd: 2026-08-06
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


^ATOM-23QN-F7D8 [desc:"Sentinel is the workflow-scan engine: scripts/sentinel/ + rules/ — adding a rule is adding a FILE, there is no registry to edit; DERIVE the rule count, never quote one (three defensible numbers exist)", keywords: how_does_the_sentinel_scanner_work where_do_workflow_findings_come_from how_do_I_add_a_new_sentinel_rule workflow_scan_engine_layout how_many_sentinel_rules_are_there_right_now, ocd: 2026-08-06, lmd: 2026-08-08]

**Sentinel — the scanning engine behind `workflow-scan`,** and the largest
subsystem in the repo.

Layout (`scripts/sentinel/`): `rule_engine.py` holds one instance of every
registered rule, severity-ordered, and **auto-discovers them via the `rules`
package** — so adding a rule is adding a file under `scripts/sentinel/rules/`,
with no registry to edit. Supporting modules: `scanner.py`, `finding.py`,
`policy.py`, `workflow.py`, `sha_resolver.py`, `autofix.py`, `local_client.py`.
Do NOT quote a rule COUNT: three defensible numbers drift apart (2026-08-08 —
34 files, 33 excluding `__init__.py`, 28 `Rule` subclasses). Derive the one you
mean: `grep -rhoE "^class [A-Za-z_]+\(Rule\)" scripts/sentinel/rules/*.py | wc -l`.

**The CLI entry point is `scripts/sentinel_scan.py` — one level ABOVE the package,
not inside it.** Worth stating because the natural guess is wrong: everything else
is under `scripts/sentinel/`, so a reader looking for "how do I run a scan" searches
the package, finds only library modules, and concludes there is no entry point. It
is an ordinary `argparse` CLI.

Tests live in `tests/test_sentinel_rules_{a..f}.py` plus `test_sentinel_core.py`
and `test_sentinel_autofix.py`, and the whole suite runs through
`uv run tests/run-all-tests.py` (a runner, not plain pytest: it renders the
per-test result table and is what the publish gate invokes). The `workflow-scan`
skill owns the engine's user-facing contract (severity classes, report layout). [^1]


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


^ATOM-MYHQ-9JC0 [desc:"the main agent's governance sections are a TESTED contract — three test files pin the 17 kanban columns, the seeded-rules precedence row and the frozen-CLI prohibition, so editing the persona is a red", keywords: I_edited_the_main_agent_persona_and_the_test_suite_went_red why_does_a_test_assert_the_kanban_column_names where_is_the_frozen_CLI_prohibition_enforced can_I_reword_the_maintainer_persona_governance_section what_pins_the_17_column_board, type: project, ocd: 2026-08-06, lmd: 2026-08-06]

**The main agent's governance prose is executable contract, not documentation.**
`agents/ai-maestro-maintainer-agent-main-agent.md` rides every turn, so a quiet
edit to it silently changes how this plugin governs itself. Three suites pin it:

- `tests/test_persona_governance.py` — the board vocabulary, asserted **one test
  per column** (14 lifecycle + 3 exception) so a partial regression names WHICH
  columns went missing instead of failing as one opaque row. The expected tuple
  is written longhand on purpose: a test that derives its expectation from the
  file under test proves nothing.
- `tests/test_frozen_cli_prohibition.py` — the IRON RULE that the ai-maestro
  server's `/api/*` is never called directly, checked at every decision surface
  that could invoke it (persona, command, skill, hooks). It distinguishes
  *executable* positions (a fenced block, a line start, a `command -v` probe)
  from prose that merely names a verb — prose instructs nothing.
- `tests/test_command_contracts.py` — every `commands/*.md` has frontmatter, a
  description, no tool-grant keys, and a `Loads skill:` that resolves to a
  shipping skill.

So a red suite after touching the persona is the contract working. Re-read what
the failing test asserts before "fixing" either side — the assertion is usually
the thing you meant to keep.


^ATOM-C0K0-QYLH [desc:"A second tested-contract class: tests pinning EXTERNAL upstream surfaces (Claude Code CLI, the CPV pin, cited governance), because a fact verified in another repo rots with this suite green.", keywords: why_does_this_repo_test_things_it_does_not_own upstream_surface_compliance_tests a_deprecated_Claude_Code_feature_slipped_into_a_skill detector_must_be_self-checked_in_both_directions borrowed_upstream_fact_went_stale_unnoticed test_claude_code_surface_compliance, type: project, ocd: 2026-08-07, lmd: 2026-08-07]

Beyond the persona contract, this suite pins a second class: EXTERNAL surfaces
this plugin depends on but does not own.

* `tests/test_claude_code_surface_compliance.py` — removed/deprecated Claude Code
  features, `claude plugin <verb>` taking ONE positional, agent names without
  `:`, permission-rule spellings that warn, hook `if:` glob semantics.
* `tests/test_cpv_pin_alignment.py` — the validator pin is defined once and the
  workflows match it.
* `tests/test_r42_no_agent_drive.py` — a governance prohibition this plugin
  answered publicly.

WHY they exist: a fact verified against another project keeps living there. This
tree's checks stop at its own boundary while the upstream surface keeps moving,
so a doc that was right when written rots with the suite green and nothing on
either side can span the gap. Both halves happened here in one day — an
unratified rule shipped as settled governance, and a validator pin 50 releases
stale that was withholding the very fix needed to unblock a release.

THE INVARIANT, and it is not optional: every detector is self-checked in BOTH
directions — it must bite a real violation AND stay quiet on correct writing. A
guard that cannot fail reports a compliance it never checked; one that reddens on
correct code gets deleted. Both failure modes have occurred in this repo, so both
are pinned as tests rather than trusted as discipline.


^ATOM-YFJ6-OFHC [desc:"scripts/governance_drift.py watches 6 hub artifacts by BLOB sha (never branch sha) — exit 0 clean / 3 drift / 4 cannot-determine.", keywords: how_do_I_know_when_the_hub_governance_rules_changed did_GOVERNANCE-RULES.md_move governance_drift_detector why_blob_sha_and_not_branch_sha the_overlays_have_no_version_field, type: project, ocd: 2026-08-08, lmd: 2026-08-08]

`scripts/governance_drift.py` detects change in the hub governance artifacts this
plugin is bound by. Baseline in `design/governance-baseline.json`; refresh with
`--update`.

WATCHES SIX, not one: `docs/GOVERNANCE-RULES.md` plus the five `rules/aimaestro/`
DEP overlays. The catalog carries a `spec-version`, but the overlays carry NO
version field, so an overlay-only edit moves no number anywhere and a
version-based check would miss it in silence.

BY BLOB SHA, NEVER THE BRANCH SHA. The hub's `3-pillars-spec.md` clause
`3P-VER-05` forbids the branch commit sha as a change signal: it moves on every
unrelated commit, so a consumer polls, sees movement, refetches a byte-identical
document and records "checked, current" — manufacturing confidence instead of
information. A blob sha changes iff those bytes change.

EXIT CODES ARE THE INTERFACE: `0` clean · `3` drift · `4` cannot-determine. The
4 is deliberate and load-bearing — reporting "clean" from a failed fetch is the
false negative the tool exists to prevent.

Only the pure `compare()` is tested; the fetch half shells out to `gh`, and a
mocked hub would only assert that the fake returns what it was told. Shipped
v1.13.0 after three sessions in one day each cited a governance rule that had
moved underneath them.

## Notes and lessons learned

[^1]: [id:ATOM-8Q1B-MSF4, status:valid, desc:"the runner's per-test table rendered 310 blank descriptions while every docstring existed — the lookup key was wrong, not the tests", keywords:"the_test_result_table_shows_no_docstring_on_every_row parametrized_tests_have_no_description_in_the_table should_I_add_docstrings_to_these_test_functions run-all-tests_renders_blank_descriptions", ocd:2026-08-06, lmd:2026-08-06] DO NOT start adding docstrings when `run-all-tests.py`'s table renders "(no docstring)" across many rows, BECAUSE a parametrized test's pytest nodeid carries a `[params]` suffix the docstring map is not keyed on — 310 rows read blank while every docstring was already there. DO read the lookup (`tests/run-all-tests.py:198`) and strip the bracket suffix before the fallback: a table-wide blank is a key bug, a scattered one is a real missing docstring.
