---
prrd-version: 2.0
updated: "2026-07-09T15:16:02+0200"
project: ai-maestro-maintainer-agent
project-id: ai-maestro-maintainer-agent
canonical-source: design/requirements/PRRD.md
mirrors: []
---

# Project Requirements & Rules — ai-maestro-maintainer-agent

MAINTAINER role plugin — host-level oversight, repo hardening, PR triage.

## §0. Canonical source + copies

| Path | Role | Update strategy |
|---|---|---|
| `design/requirements/PRRD.md` | **CANONICAL** for this project | Edit first. Bump `prrd-version:`. Update `updated:`. |

## §I. How to read this document

Rule citation form: `PRRD G<n>.<v>` (golden, user-set) or `PRRD S<n>.<v>`
(silver, manager-mutable). Rule numbers are globally unique across G/S;
promote/demote flips the letter without changing the number. The
`get-prrd.py <n>` script returns a rule's text by bare number. Full
spec: `~/.claude/rules/prrd-design-rules.md`.

## 🥇 GOLDEN — set by the USER (immutable to MANAGER)

- **G1.2** — Every agent that writes to GitHub (issue, issue comment, PR, PR comment, PR review, discussion, release note) MUST begin the body with a one-line self-identification of which agent/role/plugin authored it, because all AI Maestro agents share the single human-owner GitHub identity (the shared @owner gh CLI auth). The canonical leading line — mandated by the USER on 2026-06-09, superseding the earlier italic _Posted by the Claude developing …_ style — is: This is the Claude responsible for the <project> project. Commit messages SHOULD carry an `Agent: <plugin-slug>` trailer (the stable package slug, e.g. `Agent: ai-maestro-maintainer-agent`), greppable ecosystem-wide and rename-surviving.

## 🥈 SILVER — MANAGER-mutable (agents propose via COS)

- **S2.1** — Every push to this repo MUST go through `scripts/publish.py`; direct `git push` is refused by the process-ancestry pre-push hook (G0). No bypass env var exists; only the publish orchestrator may initiate a push.
- **S3.1** — `publish.py` G3 requires `cpv-remote-validate plugin . --strict` to exit 0 (zero CRITICAL/MAJOR/MINOR/NIT) before any release. Residual upstream-scanner false positives are cleared author-side by devitalization (provably-inert data), never by suppressing a rule or relaxing `--strict`.
- **S4.1** — This repo carries the ratified baseline GitHub rulesets as-is: `baseline-history-protect` (no bypass) + `baseline-pr-and-checks` (admin bypass for publish.py) + `baseline-tag-protect` (`refs/tags/v*.*.*`). Applying the ratified set as-is is Tier-0; ANY deviation (extra rule, new/removed bypass actor, downgraded check, enforcement change) is Tier-2 and needs MANAGER approval BEFORE it is applied.
- **S5.1** — Every skill, command, and hook ships at least one real test (no mocks, no conceptual tests); the test exercises the skill's documented recipe/helper against real filesystem/subprocess behaviour. `tests/run-all-tests.py` exits 0 on all-pass and non-zero on any-fail and is the `publish.py` G4 gate.
- **S6.1** — Every agent/skill/hook/script writes reports ONLY to `$MAIN_ROOT/reports/<component>/<TS±TZ>-<slug>.md` (main-repo root, resolved via `git worktree list | head -n1`), never a worktree-local or subsystem-private dir. Both `/reports/` and `/reports_dev/` stay gitignored.
- **S7.1** — No skill or agent frontmatter declares `allowed-tools`, `disallowed-tools`, or `tools:` (ADR-0002); the tool surface is managed dynamically by AI Maestro at dispatch time.
- **S8.1** — TRDDs use the v2 `column:` kanban schema (no v1 `status:` field) and the 4-zone design folders (`design/proposals|tasks|refused|archived`); the MAINTAINER, being a governance-layer peer, files Tier-2 proposals DIRECTLY to MANAGER (no CHIEF-OF-STAFF hop).
- **S9.1** — The MAINTAINER is the single authoritative writer of the **ruleset-config domain** (branch/tag protection rulesets) on every repo it is entrusted with; INTEGRATOR coordinates ruleset changes via MANAGER rather than writing them directly, and on a repo where both the janitor and the maintainer would apply the baseline the janitor's auto-enforcement yields to the maintainer's explicit `workflow-protect-branch` apply (both emit the byte-identical ratified set, so the result is identical regardless of who wins).
