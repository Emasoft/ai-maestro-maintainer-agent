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
issue whose body contains the exact lowercase phrase:

```text
approve-protected-edit
```

The phrase must appear on its own line (or surrounded by
whitespace / punctuation). The comment can include additional text
— e.g. "approve-protected-edit — yes, the type-check removal is
intentional, see #41". The Guardian's VERIFY step matches the
phrase only; explanation text is not parsed.

To explicitly reject:

```text
reject-protected-edit
```

A `reject-protected-edit` comment from the authorized user causes
the fix to be abandoned (the branch is left in place for manual
review; the issue gets label `fix-rejected`).

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
  # Post approval-request comment via heredoc body
  gh issue comment "$ISSUE_NUM" --body-file - <<COMMENT
This fix would modify the following security-sensitive path(s):

\`\`\`
$HITS
\`\`\`

Per the maintainer's protected-paths policy, I will not commit this
edit without explicit approval from @$AUTHORIZED_USER.

To approve, reply to this issue with a comment containing the exact
phrase \`approve-protected-edit\` (no other action required).

To reject, reply with \`reject-protected-edit\` — the fix branch
will be left in place for manual review.
COMMENT

  gh issue edit "$ISSUE_NUM" --add-label awaiting-maintainer-approval
  echo "needs-approval"
  exit 0
fi
```

## VERIFY commands

```bash
COMMENTS="$(gh issue view "$ISSUE_NUM" --json comments --jq '.comments')"

APPROVED=$(echo "$COMMENTS" | jq --arg user "$AUTHORIZED_USER" '
  [.[] | select(.author.login == $user)
       | select(.body | test("\\bapprove-protected-edit\\b"))]
  | length')

REJECTED=$(echo "$COMMENTS" | jq --arg user "$AUTHORIZED_USER" '
  [.[] | select(.author.login == $user)
       | select(.body | test("\\breject-protected-edit\\b"))]
  | length')

if [ "$REJECTED" -gt 0 ]; then
  echo "rejected"
elif [ "$APPROVED" -gt 0 ]; then
  echo "ok"
else
  echo "pending"
fi
```

Note the `jq --arg user "$AUTHORIZED_USER"` form — this is the
correct pattern that defeats the jq `--arg` trap from the article:
the username flows into jq as a NAMED ARGUMENT, never as bash
interpolation inside a double-quoted filter string.
