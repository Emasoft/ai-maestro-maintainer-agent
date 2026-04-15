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

## Governance Rules

- **R19.6**: Feature requests and change proposals are only accepted from
  the GitHub user authenticated with `gh` on the host. Bug reports are
  welcome from all users.
- **R19.7**: No force-push, no history rewrite, no tag/branch deletion
  without MANAGER approval.
- **R19.8**: All tests must pass before any push.

## Requirements

- `gh` CLI authenticated (`gh auth login`)
- `git` configured with user identity
- `uv` (for Python repos with `scripts/publish.py`)
- SERENA MCP (optional, improves code search)

## License

MIT — see [LICENSE](LICENSE) for details.
