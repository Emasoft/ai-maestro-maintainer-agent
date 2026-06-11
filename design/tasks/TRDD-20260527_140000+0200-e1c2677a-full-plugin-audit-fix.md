---
trdd-id: e1c2677a-3ac2-4f0c-8958-1e8d0eb663e4
title: Full plugin audit + remediation pass (single sweep)
column: complete
created: 2026-05-27T14:00:00+0200
updated: 2026-06-11T11:13:41+0200
---

<!-- markdownlint-disable MD025 MD004 -->

# TRDD-e1c2677a — Full plugin audit + remediation pass

**Filename:** `design/tasks/TRDD-20260527_140000+0200-e1c2677a-full-plugin-audit-fix.md`
**Tracked in:** this repo (design/tasks/ is git-tracked)

## ⏵ STATE — READ THIS FIRST ON RESUME (authoritative) — 2026-06-11

**COMPLETED 2026-06-11.** This was the umbrella audit-sweep; its work was
decomposed into 5 child TRDDs (all now `completed`) plus the Guardian /
approval-gate / baseline-ruleset / memory work that SHIPPED in **v1.4.0**
(2026-06-10). Disposition verified item-by-item before closing (not a
drift-detector rubber-stamp):

- **Phase 1 (audit)** — the 5 audit reports exist under `reports/audit/`
  (gitignored); findings were decomposed into the children below.
- **Phase 2-4 deliverables — VERIFIED PRESENT:** all 6 new skills ship
  (`maintainer-guardian`, `maintainer-pr-triage`, `maintainer-detect-stack`,
  `maintainer-redact`, `maintainer-secrets-scan`, `maintainer-tooling-bootstrap`),
  zizmor in `validate.yml`, `.github/dependabot.yml` present (5 Dependabot
  PRs merged 2026-06-10), trufflehog/gitleaks/bundled secret-scan gate.
- **Phase 5 (real-repo sandbox e2e)** — covered by `tests/test_real_repos.py`
  + `tests/test_sandbox.py` in the 476-passing suite (Docker harness,
  `--network=none`/`--read-only`/`--cap-drop=ALL`), not a separate ad-hoc
  3-repo run.
- **Phase 6 / acceptance** — pytest 476/476, CPV `--strict` exit 0,
  zizmor+actionlint green in CI, `.gitignore` covers `reports/` +
  `reports_dev/`, the once-"Outstanding" branch-protection item APPLIED
  LIVE (3 ratified rulesets) and shipped in v1.4.0.

**Children (all `completed`):** `TRDD-c0734bde`, `TRDD-2a34e0cd`,
`TRDD-2700e67d`, `TRDD-49d054cc` (A-D), `TRDD-e5816c13` (sentinel port).
Terminal — do not edit the body further; new audit work = a new TRDD.

## Context

User instruction (verbatim, on 2026-05-27): "audit the whole plugin for
errors, missing things, inconsistencies, safety issues, wrong paths,
broken references, conflicting skills instructions, missing helper
scripts, workflows holes, main agent flaws, flawed procedures, cross
platform incompatibilities, local deployment issues, safety issues,
security issues, poor handling of edge cases, parsing errors, false
positives, missing tests, missing checklists, incomplete tools and
package managers support, incorrect handling of github configurations,
outdated code, outdated github rules, outdated github actions, missing
quality gates, missing security gates, missing diagnostics skills,
wrong design choices, poor readme maintainance, lack of detection of a
project configuration, poor heuristic for autoconfigure build and
publishing pipeline, incomplete subagents, incomplete skills, subagents
not doing what were supposed to do, skills not delivering what they
were supposed to deliver, non-conformance to anthropic specs,
insufficient debug messages, main agent or subagents writing outside of
the project folder and /tmp dir, lack of protocols to handle project
contributions safely, lack of protocols for PR reviews handling from
untrusted users, local testing in sandboxes via docker, protocols for
testing and reviewing feature branches safely, incomplete review and
merge checklists, lack of detailed commit messages with the WHYs of
every change, lack of handling protocols for TRDD and ADR .md files,
outdated frontmatter handling for TRDD files, automatic gitignoring of
reports folder, subagents writing reports outside the reports
subfolders, worktrees agents not writing the reports on the main
project root reports subfolders but inside the worktree (causing the
loss of them when merging), inefficient use of tokens, subagents
reading the same file twice due to poor coordination, lack of
fix-as-you-check method to avoid wasting tokens reading the same code
twice, lack of precise checklists for readme completeness and project
environment configuration, incongruent protocols locally vs on github
ci, missing linting for json/yaml/toml/cfg/plist/etc. files, lack of
templates to generate missing text info files for the project (CONTRIB,
SECURITY, CHANGELOG, CODE OF CONDUCT, ACKNOWLEDGMENTS, etc.), lack of
secrets scanning gates with trufflehog, missing rules for redacting
private details and paths when posting or answering issues on github
or when writing commits messages, lack of skills to ensure crossplatform
protocols and scripts, lack of skills to ensure automatic install and
configuration of the required tools and stack for dev ops in a safe
way, lack of defences from prompt injections and malicious inputs,
lack of input sanitization before it reaches the main agent or the
subagents, and potential issues. Fix all issues and do the necessary
improvements. Test your rules on random github repos, cloning them
locally in a sandbox and in a docker container, and simulate and
verify the correct working of all the plugin maintainance procedures."

## Scope (audit domains)

The audit is split across 5 parallel sonnet-level subagents to fit
each into its own ~167K-token context window. Every agent writes its
detailed report to `$MAIN_ROOT/reports/audit/<TS>-audit-<X>-<slug>.md`
and returns only the report path.

| Domain | What it covers |
|--------|---------------|
| **A — Skills & main agent** | 11 skills + 1 main agent. Frontmatter (Nixtla-strict), token budgets, "Use when"/"Trigger with", cross-skill consistency, broken references, missing tool/PM coverage (pnpm/yarn/cargo/go-mod/composer/gem/brew), conflicting instructions, anthropic spec conformance, prompt-injection defences. Commands & hooks dirs (`commands/` empty, `hooks/hooks.json` only). |
| **B — Helper scripts + tests** | `scripts/sentinel/*` (32 rules + 6 fixers), `scripts/sandbox/*` (Docker harness), Python correctness (ruff + pyright), cross-platform (Linux/macOS/Windows), fail-fast adherence, subprocess safety, secret handling. `tests/*` coverage matrix vs skills/scripts; missing tests; mocked vs real tests. |
| **C — GitHub Actions + CI/CD** | `.github/workflows/{validate,release,notify-marketplace}.yml` + `.bak` cleanups; SHA-pinning, permissions least-privilege, zizmor + actionlint; Dependabot for actions; action version freshness (`gh api repos/X/Y/releases/latest`); local-vs-CI lint parity; quality gates + security gates + diagnostics. |
| **D — Repo hygiene + docs** | `.gitignore` (CRITICAL: `/reports/` + `/reports_dev/` missing); top-level missing files (CONTRIBUTING / SECURITY / CODE_OF_CONDUCT / ACKNOWLEDGMENTS / AUTHORS / `.github/ISSUE_TEMPLATE/*` / `.github/PULL_REQUEST_TEMPLATE.md` / FUNDING.yml); README completeness checklist; CHANGELOG generation; TRDD frontmatter compliance with `~/.claude/rules/trdd-design-tasks.md`; ADR support; project configuration detection heuristic; auto-bootstrap publishing pipeline. |
| **E — Cross-cutting security + safety** | Reports-location compliance ($MAIN_ROOT vs worktree, gitignored); prompt-injection defences in main agent + maintainer-triage; input sanitization; TruffleHog secret-scan gate; redaction rules for PR body / commit messages / issue replies (no host paths, no tokens); sandbox security invariants (network=none, --cap-drop=ALL, --read-only, orphan reap, no Docker-socket-mount, no --privileged); contribution / PR-from-untrusted-user protocol; review/merge checklists; commit-message-with-WHY convention; install/bootstrap-stack-safely. |

## Out of scope (deliberate)

- Renaming the plugin or shifting marketplace registration.
- Multi-repo Guardian fleet (one Guardian per plugin per repo by design).
- Production-grade telemetry (metrics, traces) — local agent, not a SaaS.
- Sentinel Ruby CLI integration (zizmor + actionlint already cover the
  surface; recorded earlier).

## Deliverables (sequential)

1. **Phase 1 — Audit** (5 parallel agents) → 5 report files under
   `reports/audit/`. Aggregate into one consolidated findings list.
2. **Phase 2 — Fix wave A: mechanical** (per ≤5-files rule, ≤5 commits)
   — `.gitignore` patch; remove `.bak` files; cleanup `__pycache__`
   tracking; missing top-level docs from templates; etc.
3. **Phase 3 — Fix wave B: skills + agent + scripts** (≤5 files /
   commit) — frontmatter normalisation, broken-reference fixes, new
   skills (prompt-injection-defense, contribution-handler,
   project-detection, redaction, secret-scan, cross-platform-stack-install).
4. **Phase 4 — Fix wave C: GitHub Actions hardening + Dependabot + new
   workflows** (security-gate.yml with trufflehog + zizmor + actionlint
   + ruff + pyright).
5. **Phase 5 — Sandbox integration tests** — clone 3 random GitHub
   repos (varied stacks) inside the existing `scripts/sandbox/` Docker
   harness, simulate Guardian patrol + maintainer-fix flow end-to-end,
   verify no host-side writes outside `$MAIN_ROOT/reports/` and `/tmp/`.
6. **Phase 6 — Final verification** — re-run all pytest tests +
   `uvx zizmor` + `uvx actionlint` + CPV strict; commit; report to user.

## Acceptance criteria

- All 5 audit reports written and consolidated.
- Every issue flagged in any audit report has either a fix or an
  explicit deferred-with-reason note.
- Phase 5 sandbox tests on 3 real GitHub repos pass end-to-end.
- `.gitignore` covers `/reports/` and `/reports_dev/` (RULE 0 / report-
  location rule).
- All new skills pass Nixtla-strict + token budget.
- All workflows pass zizmor + actionlint.
- pytest test suite still 100% pass (any new test count > current).
- TruffleHog gate added to validate.yml or a new security workflow.
- No subagent writes outside `$MAIN_ROOT/reports/<component>/` or `/tmp/`.

## Risks + mitigation

- **Token exhaustion if I try to do everything in one turn** →
  Phase-gated. Phase 1 finishes → present consolidated findings + fix
  plan to user → user picks scope of phases 2–6.
- **Breaking existing skills with frontmatter "fixes"** → Every skill
  re-validated by re-reading after edit + running test_*.py against it.
- **Sandbox tests slow** → Already integrated `scripts/sandbox/`
  harness; tests skip cleanly if Docker unreachable.

## Verification commands

```bash
# All-skill frontmatter validity
python3 -c "import yaml; [yaml.safe_load(open(p).read().split('---')[1]) for p in $(find skills -name SKILL.md)]"

# zizmor + actionlint
uvx zizmor --gh-token "$(gh auth token)" .github/workflows/
uvx actionlint .github/workflows/

# Python correctness
uv run ruff check scripts/ tests/
uv run mypy scripts/

# pytest
uv run pytest tests/ -v

# Reports-location compliance (no rogue report dirs)
find . -name "*.md" -path "*/report*" | grep -v "$(git rev-parse --show-toplevel)/reports/" | grep -v node_modules || echo OK

# TruffleHog (once added)
docker run --rm -v "$(pwd):/repo" trufflesecurity/trufflehog filesystem /repo
```

## Cross-references

- Earlier TRDDs: A/B/C/D (`TRDD-c0734bde`, `TRDD-2a34e0cd`,
  `TRDD-2700e67d`, `TRDD-49d054cc`).
- Sentinel: `TRDD-e5816c13` (Python port).
- Outstanding: branch protection on `Emasoft/ai-maestro-maintainer-agent`
  main — user has not yet authorised running `workflow-protect-branch`.
