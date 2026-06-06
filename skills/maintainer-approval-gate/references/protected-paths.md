# Protected paths — the canonical list + override mechanism

The approval-gate skill consults this list (plus an optional
per-repo override) on every `CHECK` invocation. If the maintainer
agent's planned diff touches any path matching the list, the fix
halts and the authorized user is asked for approval on the
originating issue.

## Table of Contents

- [Canonical protected-paths list](#canonical-protected-paths-list)
- [Per-repo override](#per-repo-override)
- [Approval-comment grammar](#approval-comment-grammar)
- [Diff-fingerprint binding (D2 — replay prevention)](#diff-fingerprint-binding-d2--replay-prevention)
- [Match semantics](#match-semantics)
- [CHECK commands](#check-commands)
- [VERIFY commands](#verify-commands)

---

## Canonical protected-paths list

```text
# CI / CD configuration — direct attack surface
.github/workflows/**
.github/actions/**
.github/dependabot.yml
.github/CODEOWNERS

# Release machinery — credential-handling
scripts/publish.py
scripts/setup_marketplace_pat.py

# Repo hygiene — supply-chain affecting
.gitignore
.gitattributes
.npmrc
.pnpmrc
.nvmrc
.python-version
.tool-versions

# Legal / governance
LICENSE
SECURITY.md
CODE_OF_CONDUCT.md

# Plugin-specific (Claude Code plugins)
.claude-plugin/plugin.json
.claude-plugin/marketplace.json
agents/**/*.md
hooks/**

# Tool configs that affect what runs in CI
pyproject.toml
package.json
package-lock.json
pnpm-lock.yaml
Cargo.toml
Cargo.lock
go.mod
go.sum
```

Globs are evaluated relative to the repo root. `**` matches any
number of path components.

## Per-repo override

If the maintained repo ships a `.aimaestro/protected-paths.txt`
file, the approval-gate loads ADDITIONAL paths from it. The
canonical list is always applied — the override only adds; it
cannot remove.

Override file format: one glob per line, `#` for comments.

```text
# .aimaestro/protected-paths.txt
src/auth/**
config/secrets-policy.yaml
```

## Approval-comment grammar

The authorized user releases a fix by posting a comment on the
issue whose body contains the exact lowercase phrase FOLLOWED BY the
12-char diff fingerprint that CHECK published in its approval-request
comment:

```text
approve-protected-edit <fingerprint>
```

e.g. `approve-protected-edit a1b2c3d4e5f6`. The phrase + fingerprint
must appear together (whitespace-separated). The comment can include
additional text — e.g. "approve-protected-edit a1b2c3d4e5f6 — yes, the
type-check removal is intentional, see #41". VERIFY matches the phrase
AND the CURRENT live fingerprint; explanation text is not parsed.

To explicitly reject:

```text
reject-protected-edit
```

A `reject-protected-edit` comment from the authorized user causes
the fix to be abandoned (the branch is left in place for manual
review; the issue gets label `fix-rejected`). Reject needs no
fingerprint — it abandons the fix regardless of diff.

## Diff-fingerprint binding (D2 — replay prevention)

An approval is bound to the EXACT planned diff it approved, not to the
issue. Without this, an approval granted for one small protected-path
edit would stay valid for the lifetime of the issue — so if the fix is
later re-scoped to a larger or different protected-path change, the
stale approval would silently release the gate (approval replay).

The binding is a content fingerprint of the planned diff:

```bash
# Same diff basis as the name-only match below (tracked changes vs HEAD),
# but hashed over the patch CONTENT so any change to WHAT is edited — not
# just which files — yields a different fingerprint.
FINGERPRINT="$(git diff HEAD -- | git hash-object --stdin | cut -c1-12)"
```

- CHECK publishes `$FINGERPRINT` in its approval-request comment and
  asks the user to echo it back in the approval.
- VERIFY recomputes the live `$FINGERPRINT` and releases ONLY when an
  approval comment carries the phrase AND that exact current
  fingerprint. Fail-closed: a bare `approve-protected-edit` with no
  fingerprint, or one carrying a STALE fingerprint (the diff changed
  since approval), returns `pending` — never `ok`. The user must
  re-approve the new fingerprint.

`git hash-object --stdin` is deterministic for identical content and is
always available (git is a hard dependency), so the same planned diff
always produces the same 12-char fingerprint on any host.

## Match semantics

- Glob matching uses `pathlib.PurePath.match` semantics: `**` is
  recursive, `*` is non-recursive within one component.
- A planned diff entry MATCHES the protected list if ANY glob
  matches.
- Adding a new file under a protected directory counts as a match
  (e.g. creating `.github/workflows/new.yml` matches
  `.github/workflows/**`).
- Renames are split — both the old path and the new path are
  checked.

## CHECK commands

```bash
PROTECTED_LIST="$SKILL_REFS/protected-paths.md"
OVERRIDE_PATH=".aimaestro/protected-paths.txt"

# Compute planned diff (caller is on the fix branch, not yet committed)
PLANNED="$(git diff --name-only HEAD --)"

# D2: fingerprint the planned diff CONTENT (not just names) so the approval
# binds to exactly what is being changed. Same diff basis as the name match.
FINGERPRINT="$(git diff HEAD -- | git hash-object --stdin | cut -c1-12)"

# Match each planned path against the glob set via a small python helper
HITS="$(python3 - <<'PY'
import pathlib, sys
patterns = [...]  # loaded from PROTECTED_LIST + OVERRIDE_PATH
planned = sys.stdin.read().splitlines()
hits = [p for p in planned if any(pathlib.PurePath(p).match(g) for g in patterns)]
print("\n".join(hits))
PY
<<< "$PLANNED")"

if [ -n "$HITS" ]; then
  # Post approval-request comment via heredoc body. The fingerprint is
  # published here and the user is asked to echo it back, binding the
  # approval to THIS diff (D2).
  gh issue comment "$ISSUE_NUM" --body-file - <<COMMENT
This fix would modify the following security-sensitive path(s):

\`\`\`
$HITS
\`\`\`

Planned-diff fingerprint: \`$FINGERPRINT\`

Per the maintainer's protected-paths policy, I will not commit this
edit without explicit approval from @$AUTHORIZED_USER.

To approve, reply to this issue with a comment containing the exact
phrase plus this fingerprint:

\`\`\`
approve-protected-edit $FINGERPRINT
\`\`\`

The approval is bound to this exact diff — if the fix is re-scoped, a
fresh fingerprint is published and re-approval is required.

To reject, reply with \`reject-protected-edit\` — the fix branch
will be left in place for manual review.
COMMENT

  gh issue edit "$ISSUE_NUM" --add-label awaiting-maintainer-approval
  echo "needs-approval fingerprint=$FINGERPRINT"
  exit 0
fi
```

## VERIFY commands

```bash
# D2: recompute the live planned-diff fingerprint; an approval releases the
# gate ONLY if it carries THIS fingerprint (replay-proof). Same diff basis
# as CHECK.
FINGERPRINT="$(git diff HEAD -- | git hash-object --stdin | cut -c1-12)"

COMMENTS="$(gh issue view "$ISSUE_NUM" --json comments --jq '.comments')"

REJECTED=$(echo "$COMMENTS" | jq --arg user "$AUTHORIZED_USER" '
  [.[] | select(.author.login == $user)
       | select(.body | test("\\breject-protected-edit\\b"))]
  | length')

# Approval must contain the phrase AND the CURRENT fingerprint. Both values
# pass as NAMED args (--arg), never bash-interpolated into the filter — the
# jq --arg trap defence. contains($fp) is a literal substring test (no regex).
APPROVED=$(echo "$COMMENTS" | jq --arg user "$AUTHORIZED_USER" --arg fp "$FINGERPRINT" '
  [.[] | select(.author.login == $user)
       | select(.body | test("\\bapprove-protected-edit\\b"))
       | select(.body | contains($fp))]
  | length')

# Phrase present but WITHOUT the current fingerprint = stale/unbound approval
# (the diff was re-scoped since it was approved, or the user omitted the fp).
APPROVED_ANY=$(echo "$COMMENTS" | jq --arg user "$AUTHORIZED_USER" '
  [.[] | select(.author.login == $user)
       | select(.body | test("\\bapprove-protected-edit\\b"))]
  | length')

if [ "$REJECTED" -gt 0 ]; then
  echo "rejected"
elif [ "$APPROVED" -gt 0 ]; then
  echo "ok fingerprint=$FINGERPRINT"
elif [ "$APPROVED_ANY" -gt 0 ]; then
  # Fail-closed: an approval exists but is bound to a DIFFERENT diff (or has
  # no fingerprint). Re-run CHECK to publish the fresh fingerprint and
  # re-request. NEVER auto-promote a stale approval to ok.
  echo "pending (stale approval: diff changed since approval)"
else
  echo "pending"
fi
```

Note the `jq --arg user "$AUTHORIZED_USER" --arg fp "$FINGERPRINT"` form —
this is the correct pattern that defeats the jq `--arg` trap from the
article: both the username and the fingerprint flow into jq as NAMED
ARGUMENTS, never as bash interpolation inside a double-quoted filter
string. `contains($fp)` is a literal substring match, so the hex
fingerprint is never treated as a regex.
