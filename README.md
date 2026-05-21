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
| `maintainer-workflow-audit` | "scan workflows", "audit github actions", "zizmor scan", "fix workflow security" |

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
  workflow-audit skill — `uvx zizmor` is fetched on demand,
  no host install required)
- SERENA MCP (optional, improves code search)

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
- **Permission prompts.** If you are running the agent unattended and want
  to reduce permission prompts (e.g. for the `Bash(git:*)`, `Bash(gh:*)`,
  `Bash(uv:*)` patterns this plugin uses), invoke the
  `/less-permission-prompts` skill (Claude Code ≥ 2.1.111) once at the
  start of the session. It walks you through trusting the allow-list
  declared in each skill's frontmatter — the lists in this plugin are
  already scoped to the exact subcommands the workflow needs.
- **Observability** (Claude Code ≥ 2.1.145). `claude agents --json` emits a
  machine-readable view of every running agent (including this one), and
  OTEL spans for agent activity expose `agent_id` / `parent_agent_id` so
  you can correlate patrol cycles in your observability backend.
- **GitHub Actions security.** The `maintainer-workflow-audit` skill
  wraps [zizmor](https://github.com/zizmorcore/zizmor) (`uvx zizmor` —
  no host install needed) for static analysis of `.github/workflows/`.
  It catches template injection, credential persistence, excessive
  permissions, unpinned action refs, known-vulnerable actions, and
  ~30 other CI/CD smells. Three modes: `scan-only`, `scan-and-fix`
  (commits `--fix=safe` directly to the current branch — never
  force-push), and `audit-and-comment` (chained from `maintainer-fix`
  when a bug-fix touches `.github/workflows/`). A companion job in
  `.github/workflows/validate.yml` runs zizmor on every push / PR and
  uploads SARIF to GitHub code-scanning, providing a post-push safety
  net. All third-party actions in this plugin's own workflows are
  SHA-pinned with version comments per zizmor's `unpinned-uses`
  policy.

## License

MIT — see [LICENSE](LICENSE) for details.
