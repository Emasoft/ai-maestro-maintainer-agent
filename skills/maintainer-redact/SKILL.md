---
description: |
  Use when the maintainer agent is about to author public GitHub
  content (issue comment, PR body, release notes, commit message)
  on an entrusted repo. Pipe the draft through scripts/redact.py
  to strip host-specific paths and mask any leftover secret tokens
  BEFORE the text leaves the agent. Closes audit MAJOR-2: no path
  redaction on agent-authored content.
  Trigger with phrases like "redact this", "sanitise before
  posting", "scrub paths from this draft", or "check for leaks
  before commit".
---

# maintainer-redact — sanitise agent-authored GitHub content

## Overview

The maintainer agent is the only voice the entrusted repo's
authorized user sees on issues, PRs, and releases. That means
every byte the agent emits is a leak surface — a raw absolute
path exposes the host layout, a leftover token compromises a
credential. This skill enforces a single chokepoint: every draft
the agent is about to publish on GitHub passes through
`scripts/redact.py`. The substitutions are idempotent so a
double-redaction is a no-op.

## Prerequisites

- `uv` on PATH (the script declares its inline deps via PEP 723;
  Python 3.11+ stdlib is sufficient — no third-party packages).
- The draft body exists as a shell variable, a stdin stream, or a
  file on disk.
- Optional env vars consumed by the script when set, ignored when
  not:
  - `MAINTAINER_REPO_PATH` — absolute path of the entrusted repo;
    rewritten to `$PROJECT_DIR`.
  - `MAINTAINER_AGENT_PATH` — absolute path of the agent's working
    dir; rewritten to `$AGENT_DIR`.

## Instructions

1. **When to invoke** — every code path that produces text headed
   for GitHub must redact first. The four canonical surfaces:

   | Surface | Command shape | Redact target |
   |---|---|---|
   | Issue comment | `gh issue comment N --body-file -` | the heredoc body |
   | PR description | `gh pr edit N --body "$BODY"` | `$BODY` |
   | Release notes | `gh release create v --notes-file -` | the notes body |
   | Commit message | `git commit -m "$MSG"` | `$MSG` |

2. **How to invoke** — stdin form (preferred when the body is in a
   shell variable):

   ```bash
   SANITISED=$(printf '%s' "$BODY" | uv run scripts/redact.py)
   ```

   File form (preferred when the body is being assembled across
   multiple steps):

   ```bash
   uv run scripts/redact.py --file path/to/draft.md > path/to/draft.sanitised.md
   ```

   Check-only (CI gate; exits 1 if any rule would fire, no
   output mutation):

   ```bash
   printf '%s' "$BODY" | uv run scripts/redact.py --check
   ```

3. **Always pipe through heredoc body files for gh** — never
   inline a sanitised body via `--body "$VAR"` if the body contains
   shell-metacharacter chars; pipe it through `--body-file -`
   instead. See [references/redaction-map.md](references/redaction-map.md):
   [Why heredoc body files](references/redaction-map.md#why-heredoc-body-files).

4. **Self-test (round-trip a fixture)** — verify the helper before
   trusting it in a release:

   ```bash
   cat <<'FIXTURE' | uv run scripts/redact.py | grep -q '\$HOME/code/foo' \
     && echo "redact.py OK"
   /Users/example-user/code/foo
   FIXTURE
   ```

Full substitution map + rationale + integration recipes:
[references/redaction-map.md](references/redaction-map.md):
- [Substitution rules](references/redaction-map.md#substitution-rules)
- [Why each rule exists](references/redaction-map.md#why-each-rule-exists)
- [Why heredoc body files](references/redaction-map.md#why-heredoc-body-files)
- [Integration recipes](references/redaction-map.md#integration-recipes)
- [False negatives & extending](references/redaction-map.md#false-negatives--extending)

## Output

The skill itself produces no report file. The wrapped script is a
pure stdin/stdout filter:

- **stdout**: redacted text (or original text when no rule fired —
  the substitutions are idempotent, so passing already-sanitised
  text through is a no-op).
- **stderr** (only with `--check`): one line listing the rule
  names that WOULD fire if `--check` were dropped.
- **Exit code**:
  - `0` — nothing fired, or output written successfully.
  - `1` — `--check` mode AND at least one rule would fire.
  - non-zero, non-1 — script error (bad args, file not readable).

When the maintainer agent invokes the script as part of a larger
audit cycle, it writes its OWN report to
`$MAIN_ROOT/reports/maintainer-redact/<TS>-<slug>.md` summarising
which surfaces were checked and which rules fired.

## Error Handling

| Error | Action |
|-------|--------|
| `uv` not on PATH | Stop, surface — the script is PEP 723 and needs `uv run` |
| `--file` path missing | Stop, surface stderr from Python |
| `--check` reports rules fired but caller already published | Stop the patrol cycle, alert authorized user, classify as MAJOR — the leak already shipped |
| Rule fires on legitimate content (e.g. an example user wrote `/Users/alice` in a tutorial) | Pre-process that content out of the sanitisation lane (don't post it through redact); or extend the rule with a negative match — see [references/redaction-map.md](references/redaction-map.md): [False negatives & extending](references/redaction-map.md#false-negatives--extending) |
| Tool produces output with mojibake / encoding error | Stop, the script reads UTF-8; re-encode the input first |

## Examples

```
Maintainer agent drafts a fix issue comment quoting a stack trace
that includes /Users/alice/code/repo/src/foo.py:42
→ redact pipe → "$HOME/code/repo/src/foo.py:42"
→ gh issue comment N --body-file -  (heredoc)
```

```
Pre-commit hook on the entrusted repo:
  printf '%s' "$COMMIT_MSG" | uv run scripts/redact.py --check
  → exit 1 because the message contains ghp_<36chars>
  → hook BLOCKS the commit; user re-runs after rotating the token
```

```
Release notes drafted by patrol from a CHANGELOG diff:
  uv run scripts/redact.py --file CHANGELOG.draft.md > CHANGELOG.sanitised.md
  → gh release create v1.4.0 --notes-file CHANGELOG.sanitised.md
```

## Scope

ONLY a string-level filter. Does NOT:

- Edit files in place. Always streams via stdin/stdout or `--file`
  → stdout; the caller decides what to do with the output.
- Run git, gh, docker, network. No side effects beyond stdout.
- Replace the secret-scan gate (`maintainer-secrets-scan`). That
  is the authoritative pre-publish gate; this skill is the
  last-mile scrub for *agent-authored prose*. Both layers must
  ship.

Per RULE 1.7 the subagent that invokes this skill MUST NOT commit,
push, or modify files outside its assigned scope — `scripts/redact.py`
is a pure filter and respects that constraint by construction.

## Resources

- [Substitution map + rationale](references/redaction-map.md):
  - [Substitution rules](references/redaction-map.md#substitution-rules)
  - [Why each rule exists](references/redaction-map.md#why-each-rule-exists)
  - [Why heredoc body files](references/redaction-map.md#why-heredoc-body-files)
  - [Integration recipes](references/redaction-map.md#integration-recipes)
  - [False negatives & extending](references/redaction-map.md#false-negatives--extending)
- Script source: `scripts/redact.py` (PEP 723 inline deps; stdlib only).
- Companion skills: `maintainer-secrets-scan` (pre-publish gate),
  `maintainer-approval-gate` (protected-paths gate),
  `maintainer-guardian` (T5 secret-leak detector).
- Audit finding: MAJOR-2, audit E (no path redaction on
  agent-authored GitHub content).
