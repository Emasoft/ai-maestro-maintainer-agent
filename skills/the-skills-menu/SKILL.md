---
name: the-skills-menu
description: 'Dynamic skill catalog for the ai-maestro-maintainer-agent plugin. Lists every operational skill the plugin ships, what each one does, and how to load it on demand with the Skill() tool. The main agent preloads ONLY this catalog in its skills: frontmatter and loads the rest on demand, so a session pays for the skills it actually uses instead of all 28. Use when an agent needs to pick a downstream skill at runtime.'
user-invocable: false
license: Apache-2.0
metadata:
  version: "1.0.0"
---

# the-skills-menu — the maintainer's skill catalog

## Overview

This skill is the **catalog** every ai-maestro-maintainer-agent agent consults to
discover its operational skills at runtime. The agent preloads only this catalog
in its `skills:` frontmatter; everything else loads on demand via the `Skill()`
tool.

**Why it exists:** preloading all 30 skills injects every one of them into the
agent's base context on every turn, and a long-running agent re-reads that base
on each turn. Preloading one catalog and loading the two or three skills a task
actually needs is the same capability at a fraction of the per-turn cost.

## Prerequisites

- The calling agent has `Skill` in its available tools.
- A clear task statement, so you can pick the right skill the first time.

## Instructions

1. Identify the task domain (issues? workflows? Docker? shell? secrets? docs?).
2. Find the matching row in **Plugin skills** below.
3. Load it: `Skill({skill: "ai-maestro-maintainer-agent:<name>"})` — the plugin
   namespace prefix is required.
4. Follow that skill's own checklist. Do **not** load a second skill until the
   first one returns.
5. Surface the loaded skill's summary to the caller.

Load the minimum number of skills the task needs. Loading a skill "just in case"
is exactly the cost this catalog exists to avoid.

## Plugin skills

| # | Skill | What it does |
|---|-------|--------------|
| 1 | `maintainer-approval-gate` | Halts a commit whose diff touches a protected path until the authorized user approves that exact diff fingerprint |
| 2 | `maintainer-ci-audit` | Audits and hardens non-GitHub CI — GitLab CI, Jenkins, Azure Pipelines |
| 3 | `maintainer-commit-msg-why` | Enforces conventional commits that record the WHY, not just the what |
| 4 | `maintainer-config-lint` | Lints config files (JSON, YAML, TOML, Plist, .cfg, .ini, .env, Dockerfile) for syntax and schema errors |
| 5 | `maintainer-detect-stack` | First-contact fingerprint of a freshly-entrusted repo — languages, frameworks, package managers, CI |
| 6 | `maintainer-dockerfile-audit` | Audits and hardens existing Dockerfiles — unpinned bases, root USER, baked secrets, missing HEALTHCHECK |
| 7 | `maintainer-fix` | Fixes a GitHub issue end-to-end: clone, branch, edit, test, audit, approval gate, commit, publish, close |
| 8 | `maintainer-generate-docs` | Scaffolds missing community files (CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, ACKNOWLEDGEMENTS) |
| 9 | `maintainer-guardian` | Proactive supply-chain threat scan of the repo — at session start, on patrol, and pre-merge |
| 10 | `maintainer-iac-audit` | Audits and hardens Terraform/OpenTofu and Terragrunt code |
| 11 | `maintainer-k8s-audit` | Audits and hardens Kubernetes manifests, Helm charts and Ansible playbooks |
| 12 | `maintainer-macos-notarize` | Audits or bootstraps Apple code-signing + notarization for a repo shipping macOS binaries |
| 13 | `maintainer-observability-audit` | Audits monitoring and logging config — Prometheus rules, Alertmanager routes, Loki, Fluent |
| 14 | `maintainer-patrol` | Polls the entrusted repo for new issues and dispatches `maintainer-triage` per issue |
| 15 | `maintainer-pr-review` | Deep review of a pull request once triage has cleared it |
| 16 | `maintainer-pr-triage` | Triages an incoming pull request and decides its disposition |
| 17 | `maintainer-prrd-trdd-kanban` | The MAINTAINER's role in the PRRD / TRDD / 17-column kanban workflow |
| 18 | `maintainer-redact` | Redacts private data before any public GitHub content is authored |
| 19 | `maintainer-sandbox` | Runs untrusted tools or packages in a throwaway container instead of on the host |
| 20 | `maintainer-secrets-scan` | Secret-scans the working tree and recent commits |
| 21 | `maintainer-shell-audit` | Audits and hardens shell scripts, git hooks and Makefiles (shellcheck, shfmt) |
| 22 | `maintainer-tooling-bootstrap` | Audits and installs the maintainer CLI tools (gh, uv, actionlint, ...) on a new host |
| 23 | `maintainer-trdd-adr` | Scaffolds or authors TRDDs and ADRs under `design/tasks/` and `design/adrs/` |
| 24 | `maintainer-triage` | Triages a new open issue and decides the action — fix, ask, close, or defer |
| 25 | `maintainer-worktree` | Creates, inspects, and destroys git worktrees for isolated work; the destroy path refuses to discard an agent's work |
| 26 | `workflow-bootstrap` | Creates the first `.github/workflows/` for a repo that has none |
| 27 | `workflow-fix-safe` | Applies ONLY the safe zizmor auto-fixes to the repo's workflows |
| 28 | `workflow-pin-actions` | SHA-pins every unpinned third-party action |
| 29 | `workflow-protect-branch` | Queries or applies the ratified default-branch and release-tag rulesets |
| 30 | `workflow-scan` | Read-only security audit of GitHub Actions workflows (zizmor + actionlint + the Sentinel rules) |

## Output

The catalog itself returns nothing — it documents how to invoke the other skills.
The skill you load produces the actual output.

## Scope

ONLY a catalog. It does not scan, fix, publish, or touch the repo. Every action
belongs to the skill you load from the table above.

## Resources

- Each skill's own `SKILL.md` under `skills/<name>/` — the authoritative
  instructions for that skill.
- Keep this table in sync when a skill is added or removed. Read each skill's
  `description:` with a YAML parser, not a line-oriented regex: most of this
  plugin's skills use the `description: |` block-scalar form, which a
  single-line regex silently reads as empty (see
  `claude-plugins-validation#165`).
