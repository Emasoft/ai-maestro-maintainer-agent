# Redaction map — full substitution table + rationale

Every rule in `scripts/redact.py` is documented here. The script is
the runtime source of truth — when a rule changes, this file MUST
be updated in the same commit.

## Table of Contents

- [Substitution rules](#substitution-rules)
- [Why each rule exists](#why-each-rule-exists)
- [Why heredoc body files](#why-heredoc-body-files)
- [Integration recipes](#integration-recipes)
- [False negatives & extending](#false-negatives--extending)

---

## Substitution rules

The rules apply in this order. Every rule is **idempotent**:
applying the same rule twice on the same input produces the same
output as applying it once. The script asserts this via the
`--check` mode (running `--check` on an already-sanitised body
returns exit 0).

| Order | Rule name | Pattern | Replacement |
|---|---|---|---|
| 1 | `agent-dir` (env-gated) | `<exact $MAINTAINER_AGENT_PATH>/<rest>` | `$AGENT_DIR/<rest>` |
| 2 | `project-dir` (env-gated) | `<exact $MAINTAINER_REPO_PATH>/<rest>` | `$PROJECT_DIR/<rest>` |
| 3 | `home-mac` | `/Users/<anyone>/<rest>` | `$HOME/<rest>` |
| 4 | `home-linux` | `/home/<anyone>/<rest>` | `$HOME/<rest>` |
| 5 | `home-volumes` | `/Volumes/<anyone>/<rest>` | `$HOME/<rest>` |
| 6 | `home-windows` | `C:\Users\<anyone>\<rest>` (case-insensitive) | `%USERPROFILE%\<rest>` |
| 7 | `anthropic-api-key` | `\bsk-ant-api03-[A-Za-z0-9_-]+` | `sk-ant-api03-<REDACTED>` |
| 8 | `openai-project-key` | `\bsk-proj-[A-Za-z0-9_-]+` | `sk-proj-<REDACTED>` |
| 9 | `aws-access-key-id` | `\bAKIA[0-9A-Z]{16}\b` | `AKIA<REDACTED>` |
| 10 | `github-pat` | `\bghp_[A-Za-z0-9]{36}\b` | `ghp_<REDACTED>` |
| 11 | `github-oauth` | `\bgho_[A-Za-z0-9]{36}\b` | `gho_<REDACTED>` |
| 12 | `github-server-token` | `\bghs_[A-Za-z0-9]{36}\b` | `ghs_<REDACTED>` |
| 13 | `github-user-token` | `\bghu_[A-Za-z0-9]{36}\b` | `ghu_<REDACTED>` |
| 14 | `github-refresh-token` | `\bghr_[A-Za-z0-9]{36}\b` | `ghr_<REDACTED>` |
| 15 | `gitlab-pat` | `\bglpat-[A-Za-z0-9_-]{20,}\b` | `glpat-<REDACTED>` |
| 16 | `gitlab-deploy-token` | `\bgldt-[A-Za-z0-9_-]{20,}\b` | `gldt-<REDACTED>` |
| 17 | `slack-bot-token` | `\bxoxb-[0-9-]+-[A-Za-z0-9]+\b` | `xoxb-<REDACTED>` |
| 18 | `slack-user-token` | `\bxoxp-[0-9-]+-[A-Za-z0-9]+\b` | `xoxp-<REDACTED>` |
| 19 | `pem-private-key` | `-----BEGIN <KIND> PRIVATE KEY-----...-----END <KIND> PRIVATE KEY-----` (DOTALL) | `-----BEGIN <KIND> PRIVATE KEY----- <REDACTED> -----END <KIND> PRIVATE KEY-----` |

The two GitLab families are the ROUTABLE ones (a bare `glpat-`/`gldt-` value
grants API or repo access from anywhere) — mirroring Claude Code 2.1.232's own
redaction split. The other nine `gl*-` families are detection-only, carried by
`scripts/security_catalog.json`. The suffix is `{20,}`, not exactly `{20}`:
newer GitLab tokens append a CRC tail, and an exact-20 rule would leave the
tail of a longer token visible after redaction.

Get the live list (the order may shift as new patterns land):

```bash
uv run scripts/redact.py --list-rules
```

## Why each rule exists

### Path rules (1–6)

- **Rules 1–2 — env-gated repo/agent paths.** When the maintainer
  agent is operating on an entrusted repo, the absolute path of
  that repo is highly identifying (it usually contains the
  organisation name, the dev box hostname, the user shortname,
  and the project name). Replacing it with the abstract token
  `$PROJECT_DIR` makes the same comment usable across any
  reviewer's local checkout. Same for `$AGENT_DIR`.

- **Rules 3–5 — POSIX home-style paths.** A path that starts
  with `/Users/<name>/` (macOS), `/home/<name>/` (Linux), or
  `/Volumes/<name>/` (macOS external mounts) leaks the host's
  username and FS layout. `$HOME` is the portable substitute
  every shell already understands.

- **Rule 6 — Windows home-style paths.** Same problem, different
  shell; `%USERPROFILE%` is the equivalent cmd/PowerShell variable.
  Case-insensitive because Windows is case-insensitive on its
  drive letters AND the username segment.

### Credential rules (7–17)

These are belt-and-braces. The pre-publish gate
(`maintainer-secrets-scan`) should have caught any committed
credential and refused to publish; this skill is the LAST stop
before a credential ends up in agent-authored prose
(stack-trace excerpts, JSON dumps, accidental copy-paste from a
shell history). Every rule masks the secret body and keeps the
prefix so a security reviewer can still triage the leak class.

- **Rules 7–8 — Anthropic / OpenAI keys.** Variable-length
  suffix, so we match `[A-Za-z0-9_-]+` (one-or-more chars). NOT
  bounded with a `{20,}` floor — Anthropic has shipped keys of
  varying lengths and we cannot bake that schedule into the
  scanner.
- **Rule 9 — AWS access-key ID.** Exactly 16 chars of uppercase
  alphanum after the `AKIA` prefix. Schema-rigid.
- **Rules 10–14 — GitHub token family.** Each variant has a
  fixed 36-char suffix; only the 4-char prefix differs (`ghp_`,
  `gho_`, `ghs_`, `ghu_`, `ghr_`). We ship a rule per variant
  so the redacted output preserves the leak class (the reviewer
  knows whether to rotate a PAT, OAuth, server, user, or refresh
  token).
- **Rules 15–16 — Slack tokens.** Per the upstream schema, both
  bot and user tokens are shaped
  `xox[bp]-<digits-and-hyphens>-<alphanum>` — the digit section
  may itself contain internal hyphens. Our character class
  `[0-9-]+` accepts that without requiring a fixed segment count.
- **Rule 17 — PEM private keys.** Matches the full
  `BEGIN…END` envelope (DOTALL is essential — keys span lines)
  and keeps the BEGIN/END markers so the reader sees the leak
  class. We non-greedily match the body so a document with TWO
  consecutive keys redacts each independently.

## Why heredoc body files

The maintainer agent must always pipe authored content to `gh`
via a body file (`--body-file -` plus a heredoc), never via
`--body "$VAR"`:

```bash
gh issue comment "$N" --body-file - <<COMMENT
$SANITISED_BODY
COMMENT
```

vs the WRONG shape:

```bash
gh issue comment "$N" --body "$SANITISED_BODY"   # DO NOT — see below
```

Reasons:

1. **Shell expansion in the wrong form.** `--body "$VAR"` exposes
   the body to one extra round of shell quoting. If `$VAR`
   contains a backtick or `$()`, command substitution fires
   silently. The heredoc body is a single argument and a closed
   text region — bash never re-parses it.
2. **Length limits.** macOS argv length is bounded
   (`getconf ARG_MAX` ≈ 1 MiB). A long PR body fits comfortably
   on stdin (no limit) but can clip on a long `--body` argument.
3. **Newlines and CR/LF.** `--body` collapses newline handling
   in some shells; heredoc keeps every byte verbatim.

The heredoc TAG must be `COMMENT` (or any UPPER-CASE marker the
body itself doesn't contain). Always quote the tag — `<<'COMMENT'`
— to disable parameter expansion inside the body. (`$SANITISED_BODY`
in the example is expanded BEFORE the heredoc is fed to gh, which
is what we want; the leading `<<COMMENT` form is intentional.)

## Integration recipes

### Recipe 1 — Sanitise + post issue comment

```bash
BODY="$(printf '%s' "$RAW_BODY" | uv run scripts/redact.py)"
gh issue comment "$ISSUE_NUM" --body-file - <<COMMENT
$BODY
COMMENT
```

### Recipe 2 — Sanitise + edit PR description

```bash
BODY="$(printf '%s' "$RAW_DESCRIPTION" | uv run scripts/redact.py)"
gh pr edit "$PR_NUM" --body "$BODY"
# (--body is acceptable here only because we re-quoted; for
# bodies >>1 KiB, prefer the body-file form via gh pr edit's
# --body-file flag.)
```

### Recipe 3 — Sanitise + create release notes

```bash
uv run scripts/redact.py --file CHANGELOG.draft.md > CHANGELOG.sanitised.md
gh release create "$TAG" --notes-file CHANGELOG.sanitised.md
```

### Recipe 4 — Pre-commit hook (sanitise commit messages)

```bash
# .git/hooks/commit-msg
MSG_FILE="$1"
if ! uv run scripts/redact.py --check < "$MSG_FILE"; then
  echo "Commit msg contains host paths or secret-like tokens — rewriting." >&2
  uv run scripts/redact.py < "$MSG_FILE" > "$MSG_FILE.sanitised"
  mv "$MSG_FILE.sanitised" "$MSG_FILE"
fi
```

(Note: in-place rewrite of the commit message; the user sees
the sanitised version in the next prompt.)

### Recipe 5 — CI gate (block any agent-authored content that leaks)

```bash
# In a workflow job that uploads agent prose as an artefact:
uv run scripts/redact.py --check < artefact.md \
  || { echo "Leak detected — refusing to publish" >&2; exit 1; }
```

## False negatives & extending

### When a rule legitimately should NOT fire

- A tutorial that intentionally documents the shape of a
  GitHub PAT: route the prose AROUND the redact pipe (write it
  to a docs file directly, not via the maintainer agent's
  sanitisation lane). The agent-authored-content gate is for
  prose the agent wrote; documentation that quotes shapes
  on purpose is human-authored.

- A path that mentions `/Users/foo` in a code comment of a test
  fixture: same — don't pipe test fixtures through redact.

### Adding a new rule

1. Add a `Rule(name=..., pattern=..., replacement=..., flags=...)`
   to `_path_rules()` or `_secret_rules()` in `scripts/redact.py`.
2. Add a row to the table at the top of this file.
3. Add a "Why this rule exists" paragraph below.
4. Write a self-test: pass a fixture that contains exactly the
   leak the new rule targets, assert the output doesn't contain
   the original text.

Rule names are alphabetical within each group (path rules vs
credential rules) — keep that ordering when inserting.

### Idempotence requirement

Every new rule MUST satisfy:

```python
text2, _ = redact(text1, [rule])
text3, _ = redact(text2, [rule])
assert text2 == text3   # rule is idempotent
```

The replacement MUST NOT contain a substring that the same rule's
pattern would match. Concretely: a rule that masks
`ghp_<36chars>` to `ghp_<REDACTED>` is idempotent because
`<REDACTED>` is not 36 chars of `[A-Za-z0-9]`. If your replacement
WOULD re-match the pattern, anchor it differently (e.g. wrap with
backticks or angle brackets).
