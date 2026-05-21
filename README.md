# ai-maestro-maintainer-agent

<!--BADGES-START-->
[![CI](https://github.com/Emasoft/ai-maestro-maintainer-agent/actions/workflows/validate.yml/badge.svg)](https://github.com/Emasoft/ai-maestro-maintainer-agent/actions/workflows/validate.yml)
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
| `workflow-bootstrap` | "set up workflows", "bootstrap CI", "configure github for this new repo" |
| `workflow-scan` | "scan workflows", "audit github actions", "zizmor scan" |
| `workflow-fix-safe` | "fix workflow security", "harden workflows" |
| `workflow-pin-actions` | "pin workflow actions", "SHA-pin actions" |
| `workflow-protect-branch` | SHOW: "show branch rules", "what branch rules are active", "refresh branch-rule cache" · APPLY: "protect main branch", "apply branch rules" |

## Governance Rules

- **R19.6**: Feature requests and change proposals are only accepted from
  the GitHub user authenticated with `gh` on the host. Bug reports are
  welcome from all users.
- **R19.7**: No force-push, no history rewrite, no tag/branch deletion
  without MANAGER approval.
- **R19.8**: All tests must pass before any push.

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
  effort-aware triage.
- `gh` CLI authenticated (`gh auth login`)
- `git` configured with user identity
- `uv` (for Python repos with `scripts/publish.py`, and for the
  workflow-* skills — `uvx zizmor` is fetched on demand, no host
  install required)
- SERENA MCP (optional, improves code search)
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
- **Tool surface is dynamic.** Skills and the agent in this plugin
  intentionally do NOT declare `allowed-tools` / `tools:` /
  `disallowedTools:` in their frontmatter. AI Maestro provisions the
  tool surface (built-in Claude Code tools + MCP servers + any
  ecosystem extensions) dynamically at agent-spawn time, so the
  available toolset can grow without per-skill edits. If you want
  to reduce permission prompts when running unattended, invoke the
  `/less-permission-prompts` skill (Claude Code ≥ 2.1.111) once at
  the start of the session — it scans your transcripts and adds the
  observed safe tool patterns to `.claude/settings.json` at the
  user or project scope.
- **Observability** (Claude Code ≥ 2.1.145). `claude agents --json` emits a
  machine-readable view of every running agent (including this one), and
  OTEL spans for agent activity expose `agent_id` / `parent_agent_id` so
  you can correlate patrol cycles in your observability backend.
- **GitHub Actions security.** Five focused skills wrap
  [zizmor](https://github.com/zizmorcore/zizmor) and `actionlint`
  (both via `uvx` / Homebrew — no manual install needed for
  zizmor; actionlint is a Homebrew formula):
    - `workflow-bootstrap` — first-time scaffold for a repo with no
      `.github/workflows/` yet. Detects language (Python / Node /
      Rust / Go / generic), writes a hardened CI workflow +
      `workflow-security` job from templates, drops a ruleset spec,
      chains pin-actions + scan to verify, commits on
      `chore/bootstrap-ci`. Refuses to overwrite existing workflows.
    - `workflow-scan` — read-only audit; JSON + markdown reports
      under `$MAIN_ROOT/reports/workflow-scan/`. Posts a summary on
      the linked issue when chained from `maintainer-fix`.
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
  `.github/workflows/validate.yml` runs zizmor on every push / PR and
  uploads SARIF to GitHub code-scanning, providing a post-push safety
  net. All third-party actions in this plugin's own workflows are
  SHA-pinned with version comments per zizmor's `unpinned-uses` policy.
  Required labels (`workflow-security-clean`,
  `workflow-security-review-needed`, `fix-failed`, `manual`,
  `verified`, `cannot-reproduce`) are auto-created on first use via
  `gh label create --force`.

## License

MIT — see [LICENSE](LICENSE) for details.
