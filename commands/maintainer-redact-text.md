---
description: Redact host paths and any leftover secrets from text the agent is about to author into a GitHub comment / PR description / commit message / release notes.
argument-hint: "[--file <path>] [--check]"
---

Read text from stdin (or `--file <path>`), apply the canonical
redaction map (host-path → `$HOME`/`$PROJECT_DIR`; tokens →
`<REDACTED>`), and write the cleaned text to stdout.

Loads skill: **maintainer-redact**

Underlying CLI: `uv run scripts/redact.py [--file <path>] [--check]`

`--check` mode exits non-zero if any substitution would fire,
without printing the cleaned text. Useful in pre-commit / pre-push
hooks to refuse commits whose message would leak host paths.

Pipe pattern (use before every `gh` write that includes user-data):

```bash
echo "$BODY" | /maintainer-redact-text | gh issue comment N --body-file -
```

Idempotent: running redaction twice produces the same output as
running it once. Safe to chain.

Patterns covered:
- `/Users/<name>/<rest>` → `$HOME/<rest>`
- `/home/<name>/<rest>` → `$HOME/<rest>`
- `C:\Users\<name>\<rest>` → `%USERPROFILE%\<rest>`
- `<absolute path to maintained repo>` → `$PROJECT_DIR/<rest>`
- `<absolute path to plugin repo>` → `$AGENT_DIR/<rest>`
- 36-char GitHub PAT prefixes (`ghp_…`) → `ghp_<REDACTED>`
- Anthropic API keys (`sk-ant-api03-…`, `sk-proj-…`) → `<REDACTED>`
- AWS access key IDs (`AKIA…`) → `AKIA<REDACTED>`
- Slack tokens (`xoxb-…` / `xoxp-…`) → `<REDACTED>`
- PEM private key blocks → `<REDACTED>`

This is defense in depth — the canonical guard against secret
leakage is to NOT have secrets in the agent's context in the
first place. Use this command after the fact, never as a
substitute for proper secret handling.
