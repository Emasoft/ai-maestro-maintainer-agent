# ai-maestro-maintainer-agent

<!--BADGES-START-->
[![CI](https://github.com/Emasoft/ai-maestro-maintainer-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Emasoft/ai-maestro-maintainer-agent/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-1.13.7-blue)](https://github.com/Emasoft/ai-maestro-maintainer-agent/releases)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
<!--BADGES-END-->

An AI Maestro role-plugin for the **MAINTAINER** governance title. Polls a
GitHub repository for new issues, triages bugs autonomously, accepts feature
requests only from the authorized GitHub user, and fixes valid issues via a
clone-branch-test-publish workflow.

## Installation

```bash
claude plugin install ai-maestro-maintainer-agent@ai-maestro-plugins
```

## Configuration

The agent requires the `githubRepo` attribute set on creation:

```bash
aimaestro-agent.sh create --name my-maintainer --role ai-maestro-maintainer-agent \
  --githubRepo Emasoft/my-project
```

The `gh` CLI must be authenticated on the host:

```bash
gh auth login
gh auth status
```

### Patrol interval

The patrol skill polls the repository every **5 minutes** by default. Override
with the `MAINTAINER_POLL_INTERVAL_MS` environment variable at agent launch:

```bash
# 1-minute interval for a high-traffic repo
MAINTAINER_POLL_INTERVAL_MS=60000 claude --agent ai-maestro-maintainer-agent-main-agent

# 15-minute interval for a low-traffic repo
MAINTAINER_POLL_INTERVAL_MS=900000 claude --agent ai-maestro-maintainer-agent-main-agent
```

Bounds are **10 s floor** and **1 h ceiling** — values outside the range are
clamped. Unit is milliseconds to match the rest of the AI Maestro ecosystem
(`MESSAGE_POLL_INTERVAL_MS`, `HOST_POLL_INTERVAL_MS`, etc.).

## Usage

Once the agent session is running:

- **Start patrol**: "start patrol" or "begin maintenance loop"
- **Triage an issue manually**: "triage issue #42"
- **Fix an issue manually**: "fix issue #42"
- **Stop patrol**: "stop patrol"

## Skills

| Skill | Trigger |
|-------|---------|
| `maintainer-patrol` | "start patrol", "begin maintenance loop" |
| `maintainer-triage` | "triage issue #N", "classify issue #N" |
| `maintainer-fix` | "fix issue #N", "work on issue #N" |
| `maintainer-guardian` | BASELINE: "guardian baseline", "capture security baseline" · SCAN: "guardian scan", "scan for threats", "check for supply-chain drift" |
| `maintainer-approval-gate` | CHECK: "approval gate check", "guard protected paths" · VERIFY: "verify protected-edit approval" |
| `workflow-bootstrap` | "set up workflows", "bootstrap CI", "configure github for this new repo" |
| `workflow-scan` | "scan workflows", "audit github actions", "zizmor scan" |
| `workflow-fix-safe` | "fix workflow security", "harden workflows" |
| `workflow-pin-actions` | "pin workflow actions", "SHA-pin actions" |
| `workflow-protect-branch` | SHOW: "show branch rules", "what branch rules are active", "refresh branch-rule cache" · APPLY: "protect main branch", "apply branch rules" |
| `maintainer-sandbox` | "sandbox this", "run in a sandbox", "test this package without installing", "shootout these two tools", "reproduce in a clean container", "verify before recommending" |

### Entrusted-repo capability skills (applied on every downstream repo the agent guards)

| Skill | Trigger |
|-------|---------|
| `maintainer-redact` | "redact host paths", "sanitize agent output", "strip secrets from this text" |
| `maintainer-secrets-scan` | "scan for secrets", "trufflehog this repo", "gitleaks audit", "pre-publish secret gate" |
| `maintainer-pr-triage` | "triage PR #N", "classify pull request", "review fork PR" |
| `maintainer-pr-review` | "review PR #N", "check this diff", "audit PR for protected paths" |
| `maintainer-commit-msg-why` | "install commit-msg WHY hook", "audit commit messages", "enforce WHY paragraphs" |
| `maintainer-detect-stack` | "detect repo stack", "fingerprint this project", "what language is this", "refresh stack snapshot" |
| `maintainer-tooling-bootstrap` | "install required tools", "bootstrap toolchain", "audit installed tools" |
| `maintainer-config-lint` | "lint config files", "validate JSON/YAML/TOML", "audit repo config files" |
| `maintainer-generate-docs` | "generate community files", "scaffold CONTRIBUTING", "audit missing docs" |
| `maintainer-trdd-adr` | "bootstrap TRDDs", "set up ADRs", "scaffold a TRDD", "author an ADR", "validate design docs" |
| `maintainer-worktree` | "make a worktree", "work in isolation", "remove the worktree", "clean up worktrees", "where is the main repo root" |
| `maintainer-macos-notarize` | "notarize the mac build", "set up code signing", "why does Gatekeeper block my app", "audit macOS signing" |

## Governance Rules

The agent operates under the AI Maestro governance layer (R19) and this
project's own PRRD (`design/requirements/PRRD.md`).

### Ecosystem rules (R19)

- **R19.6**: Feature requests and change proposals are only accepted from
  the GitHub user authenticated with `gh` on the host. Bug reports are
  welcome from all users.
- **R19.7**: No force-push, no history rewrite, no tag/branch deletion
  without MANAGER approval (a Tier-2 gate — see *Approval tiers* below).
- **R19.8**: All tests must pass before any push.
- **R6 (v3)**: The MAINTAINER is a governance-layer peer with a direct edge
  to MANAGER and HUMAN; every other title is reachable only via MANAGER.
  There is **no CHIEF-OF-STAFF hop** — Tier-2 proposals go directly to MANAGER.
- **G1.1 (self-id)**: Every GitHub post AND every AMP message body begins with
  the self-id line identifying which Claude authored it (all agents share the
  one human-owner identity).

### Security-core governance (R26-R40)

The agent internalizes the fleet's security-first governance core
(GOVERNANCE-RULES.md v4.x, USER-set 2026-06-18; landed via ai-maestro#38). The
maintainer-relevant subset: **immutable identity** — it never self-changes its
TITLE / ROLE / NAME / AID (R26); **self-installs only via the core
`ai-maestro-plugin` skills** with MANAGER approval + a server CPV scan (R27);
authenticates every server call by the **three-check AID → TITLE →
portfolio-token** model and **never faces a sudo gate** — a sudo password is
USER-via-UI only, surfaced to the MAESTRO, never performed (R28 / R32); trusts
the **signed ledger** as the source of truth (R33 / R34); and obeys the
**MANAGER → MAESTRO** chain (R36 / R37). It is aware of the team-lifecycle
(R29-R31) and the non-MAESTRO-user + ASSISTANT model (R38 / R39) but runs no
teams. Full text in the agent persona's *Governance core (R26-R40)* section.

### Project rules (PRRD)

The PRRD carries 1 GOLDEN rule (G1.1, USER-set, immutable to MANAGER) and 8
SILVER rules (S2–S9, MANAGER-mutable) covering: publish-only-via-`publish.py`
(S2), the CPV `--strict` exit-0 publish gate (S3), the ratified baseline
rulesets + the Tier-0-apply / Tier-2-deviate line (S4), real-tests-no-mocks
(S5), the reports-location rule (S6), no tool-grant frontmatter / ADR-0002
(S7), the v2 TRDD `column:` schema + 4-zone design folders (S8), and the
ruleset-config single-writer domain (S9). Query with `get-prrd.py <n>`.

### Approval tiers

Work is gated by the ladder **Tier 0 → MANAGER → USER** (the COS rung is
skipped for this governance-layer peer). Tier 0 (own in-scope DERIVED tasks;
applying the ratified baseline as-is) needs no approval; baseline *deviations*,
governance changes, and release-pipeline entry are Tier 2 (MANAGER); GOLDEN-rule
and owner-identity changes are Tier 3 (USER). TRDDs flow through the 4-zone
design folders (`design/proposals|tasks|refused|archived`). Full model:
`~/.claude/rules/trdd-approval-tiers.md`.

## Requirements

- Claude Code **≥ 2.1.133** — the triage skill reads `$CLAUDE_EFFORT` (added
  2.1.133) to scale verification depth, and the fix skill reads
  `$CLAUDE_CODE_SESSION_ID` (added 2.1.132) for per-session workspace
  isolation. MEDIUM is the effort floor: `$CLAUDE_EFFORT=LOW` is intentionally
  promoted to MEDIUM because triage that skips code verification is unsafe;
  set `$CLAUDE_EFFORT=MAX` (or `XHIGH`, added 2.1.111) for difficult issues
  that need cross-file analysis. Earlier Claude Code versions still work —
  both env vars degrade gracefully to the historical single-workspace,
  ambiguity-only-grep defaults — but you lose concurrency safety and
  effort-aware triage. The agent's `model: inherit` frontmatter means it picks up whichever model
  the session runs — since **Claude Code ≥ 2.1.197** that defaults to **Sonnet 5**
  (native 1M-token context), or **Opus 4.8** / whatever AI Maestro provisions when
  selected — with no per-skill change. On **Opus 4.8** (Claude Code ≥ 2.1.154) the
  session effort defaults to **HIGH**, so triage runs at `high` depth out of the box.
- `gh` CLI authenticated (`gh auth login`)
- `git` configured with user identity
- `uv` (for Python repos with `scripts/publish.py`, and for the
  workflow-* skills — `uvx zizmor` is fetched on demand, no host
  install required)
- SERENA MCP (optional, improves code search)
- **`ai-maestro-plugin`** (declared in `plugin.json` `dependencies`) — install
  it from the `Emasoft/ai-maestro-plugins` marketplace alongside this plugin.
  It provides the granular `ama-*` PRRD/TRDD/kanban governance skills
  (`ama-kanban-render`, `ama-trdd-*`, `ama-prrd-*`, `ama-proposal-approvals`)
  that the `maintainer-prrd-trdd-kanban` wrapper builds on — they own the
  `scripts/prrd-trdd/` governance scripts (`get-prrd.py`, `prrd-edit.py`,
  `findprrd.py`, `findtrdd.py`, `kanban.py`).
  Without it those commands fail silently at runtime. As of Claude Code
  ≥ 2.1.143 this declared dependency is **enforced**: `claude plugin enable`
  force-enables it (and its transitive deps), and
  `claude plugin disable ai-maestro-plugin` refuses while this plugin is
  enabled, printing a copy-pasteable disable-chain hint.
- `$MARKETPLACE_PAT` exported in your shell (or a .env outside the
  repo) for the one-time setup of the `notify-marketplace` workflow.
  Run `uv run scripts/setup_marketplace_pat.py` to push the secret
  to both the plugin repo and the marketplace hub — the script
  always uses `gh secret set NAME -b "$VALUE"` (the only reliable
  form; stdin pipes silently produce broken secrets).

## Behaviour notes

- **GitHub rate-limit awareness** (Claude Code ≥ 2.1.116). The Bash tool
  prepends a `GitHub API rate limit` hint to `gh` output when the REST or
  search-API limit is close. Both the patrol and triage skills honour this
  hint: patrol sleeps for `$POLL_SECONDS` instead of retrying inside the
  same cycle, and triage returns a `needs-info / rate-limit deferred`
  disposition so the issue is **not** marked processed in the ledger and is
  re-picked-up on the next cycle with a fresh budget. Tight retry loops
  only deepen GitHub's back-off — the skills will never retry the same
  `gh` call inside one invocation.
- **Model-overload resilience** (Claude Code ≥ 2.1.166). For unattended,
  heartbeat-driven operation, set the `fallbackModel` session setting (up to
  three models, tried in order when the primary is overloaded or
  unavailable). It complements the GitHub rate-limit handling above —
  `fallbackModel` guards against model-side throttling, the rate-limit hint
  against GitHub-side throttling — so a transient overload degrades to a
  fallback model instead of ending the turn. The agent's `model: inherit`
  frontmatter means it rides whatever the session (or its fallback) resolves
  to, with no per-skill change.
- **Tool surface is dynamic.** Skills and the agent in this plugin
  intentionally do NOT declare `allowed-tools`, `disallowed-tools`
  (a skill/slash-command frontmatter field added in Claude Code
  2.1.152), or an agent `tools:` list in their frontmatter. AI Maestro
  provisions the tool surface (built-in Claude Code tools, MCP servers,
  and any ecosystem extensions) dynamically at agent-spawn time, so the
  available toolset can grow without per-skill edits (see
  `design/adrs/ADR-0002`). If you want to reduce permission prompts when
  running unattended, invoke the bundled `/fewer-permission-prompts`
  skill once at the start of the session — it scans your transcripts and
  adds the observed safe tool patterns to `.claude/settings.json` at the
  user or project scope.
- **Observability** (Claude Code ≥ 2.1.145). `claude agents --json` emits a
  machine-readable view of every running agent (including this one), and
  OTEL spans for agent activity expose `agent_id` / `parent_agent_id` so
  you can correlate patrol cycles in your observability backend.
- **Guardian Mode.** The maintainer is the **guardian of the repo**,
  not merely a reactive issue-fixer. At session start, the SessionStart
  hook fires the `maintainer-guardian` skill in BASELINE mode to
  snapshot **six** threat classes — T1 zizmor/actionlint **plus the
  bundled Sentinel port (`scripts/sentinel_scan.py`, 32 deterministic
  rules)** findings, T2 stale SHA pins, T3 branch-rule state, T4
  protected-path activity, T5 secret-leak markers in recent commits,
  T6 package-manager safety-config drift (`.npmrc` / `pnpm-workspace.yaml` /
  `pyproject.toml [tool.uv]` knobs — `min-release-age`, `trust-policy`,
  `frozen-lockfile`, `blockExoticSubdeps`) — to
  `$AGENT_DIR/.aimaestro/state/guardian-baseline.json` (where
  `$AGENT_DIR = ${AGENT_WORK_DIR:-${CLAUDE_PROJECT_DIR:-$PWD}}`,
  per the post-v1.1.0 governance fix that relocated state into
  the agent's working directory so AI Maestro backups + host
  migration capture it). At
  every patrol cycle, SCAN mode diffs against baseline and routes
  critical deltas: safe-fixable zizmor findings auto-PR via
  `workflow-fix-safe`, stale pins auto-file a tracking issue,
  protected-path changes alert the authorized user, and any T5 hit
  STOPS the cycle. The `maintainer-approval-gate` skill refuses
  to commit any fix whose planned diff touches a security-sensitive
  path (`.github/**`, `scripts/publish.py`, `.gitignore`, `.npmrc`,
  `LICENSE`, `.claude-plugin/**`, etc.) without an
  `approve-protected-edit` reply from the authorized maintainer on
  the originating issue — defeating the "malicious bug report
  requesting CI edit" supply-chain pattern documented in Atai
  Barkai's 2026-05-20 article.

  **Guardian flow at a glance.**

  ```text
  Session start (SessionStart hook)
        │
        v
  maintainer-guardian  mode=BASELINE ──> guardian-baseline.json
  snapshot T1..T5                        ($AGENT_DIR/.aimaestro/state/)
        │
        v
  Patrol cycle (default 5 min) <─────────────────────────────┐
        │ pre-cycle SCAN                                     │
        v                                                    │
  maintainer-guardian  mode=SCAN                             │
  re-run T1..T5, diff vs baseline → delta per class          │
        │                                                    │
        v                                                    │
  Routing decision:                                          │
    T1 critical/high → safe-fixable? yes→ workflow-fix-safe PR
                                     no → tracking issue     │
    T2 stale pin     → tracking issue (Dependabot link)      │
    T3 rule drift    → alert authorized user (R6 direct)     │
    T4 path moved    → alert authorized user (post-hoc)      │
    T5 secret-leak   → STOP CYCLE + alert (HALT until ack)   │
        │                                                    │
        │ T5 hit? → HALT ; else proceed to triage / fix      │
        v                                                    │
  maintainer-fix  (planned diff on disk, before git commit)  │
        │                                                    │
        v                                                    │
  maintainer-approval-gate  mode=CHECK                       │
  diff ∩ protected-paths (.github/, scripts/publish.py,      │
     .gitignore, .npmrc, LICENSE, .claude-plugin/, ...) ?    │
        │                                                    │
        ├── no hit ──> commit + publish ─────────────────────┤
        │                                                    │
        └── hit ─> post approve-protected-edit on issue,     │
                   label awaiting-maintainer-approval, HALT  │
                        │                                    │
                        │ next patrol cycle                  │
                        v                                    │
                   maintainer-approval-gate  mode=VERIFY     │
                   ok → resume ; pending → wait ; rejected → abort
  ────────────────────────────────────────────────────────────┘
  ```

- **GitHub Actions security.** Six focused skills wrap
  [zizmor](https://github.com/zizmorcore/zizmor), `actionlint`, and
  the bundled **Sentinel port** (`scripts/sentinel_scan.py` — a
  faithful Python port of [jpr5/sentinel](https://sentinel.copilotkit.dev),
  32 deterministic rules with 6 mechanical auto-fixers; pure stdlib +
  PyYAML, run via `uv run`). zizmor + actionlint come via `uvx` /
  Homebrew — no manual install needed:
    - `workflow-bootstrap` — first-time scaffold for a repo with no
      `.github/workflows/` yet. Detects language (Python / Node /
      Rust / Go / generic), writes a hardened CI workflow +
      `workflow-security` job from templates, drops a ruleset spec,
      chains pin-actions + scan to verify, commits on
      `chore/bootstrap-ci`. Refuses to overwrite existing workflows.
    - `workflow-scan` — read-only audit running all three engines
      (zizmor + actionlint + Sentinel); JSON + markdown reports
      under `$MAIN_ROOT/reports/workflow-scan/`. Posts a summary on
      the linked issue when chained from `maintainer-fix`. Sentinel
      adds the structural classes zizmor misses — `build-publish-same-job`,
      `credential-window`, `ide-config-injection`,
      `missing-frozen-lockfile`, and more.
    - `workflow-fix-safe` — runs `zizmor --fix=safe` and adds
      missing hardening (`permissions: contents: read`,
      `concurrency:`, `timeout-minutes:`). Commits on the current
      branch — never force-push (R19.7).
    - `workflow-pin-actions` — resolves every unpinned
      `uses: name@vN` to a 40-char commit SHA via `gh api` and
      rewrites inline with the SHA plus a trailing semver comment.
    - `workflow-protect-branch` — idempotent
      `gh api POST /repos/.../rulesets` that requires the
      auto-detected status checks, blocks non-fast-forward pushes,
      and blocks branch deletion.
  A companion `workflow-security` job in
  `.github/workflows/ci.yml` runs zizmor on every push / PR and
  uploads SARIF to GitHub code-scanning, providing a post-push safety
  net. All third-party actions in this plugin's own workflows are
  SHA-pinned with version comments per zizmor's `unpinned-uses` policy.
  Required labels (`workflow-security-clean`,
  `workflow-security-review-needed`, `fix-failed`, `manual`,
  `verified`, `cannot-reproduce`) are auto-created on first use via
  `gh label create --force`.

## License

MIT — see [LICENSE](LICENSE) for details.
