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

**Say WHY, in the same comment (R49 — an approver is a guide, not a
gate).** The bare token stays valid on its own and always will: it is
the abort path, and a gate that can jam because the parser disliked
your prose is worse than a terse rejection. But a refusal that names
nothing is malpractice *even when the ruling is correct*, because the
proposer cannot tell "wrong approach" from "right approach, wrong
moment" and simply re-proposes the same thing. So write the three
elements after the token, as free text:

```text
reject-protected-edit — the CI job id is wrong (`validate`, not
`Validate`), so the branch would seal on a context that never
reports. Re-propose once the id is read from the ruleset.
```

1. the **precise defect** — what is actually wrong, not that it is;
2. the **bar for acceptance** — what would make it approvable;
3. an **explicit invitation to re-propose**.

VERIFY still parses only the token, so this text is for the human on
the other side, not the matcher. And note what a bare "no" does *not*
authorize: abandoning the fix is the point of a rejection, but a
refusal that names no defect never licenses deleting or stripping
working code that merely depended on the proposal.

## Diff-fingerprint binding (D2 — replay prevention)

An approval is bound to the EXACT planned diff it approved, not to the
issue. Without this, an approval granted for one small protected-path
edit would stay valid for the lifetime of the issue — so if the fix is
later re-scoped to a larger or different protected-path change, the
stale approval would silently release the gate (approval replay).

The binding is a content fingerprint of the planned diff:

```bash
# Same diff basis as the name-only match below (tracked changes vs HEAD PLUS
# untracked new files), hashed over the patch CONTENT + each untracked file's
# path and blob hash, so any change to WHAT is edited — not just which files —
# yields a different fingerprint. (Untracked files are folded in because the fix
# flow has not yet staged them at gate time; see the CHECK commands below.)
FINGERPRINT="$( { git diff HEAD --; git ls-files --others --exclude-standard \
    | while IFS= read -r f; do printf '%s ' "$f"; git hash-object "$f"; done; } \
  | git hash-object --stdin | cut -c1-12)"
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

# Compute the planned diff. WHY the untracked union: `git diff HEAD` shows only
# TRACKED changes, but the fix flow stages files only at commit-time (fix-steps
# Step 6, AFTER this gate). A fix that ADDS a brand-new protected file (e.g. a
# new .github/workflows/evil.yml or agents/backdoor.md) is still untracked here,
# so a names-only `git diff HEAD` would MISS it and the gate would return noop —
# a fail-open the match-semantics section explicitly forbids ("adding a new file
# under a protected directory counts as a match"). Union in the untracked set.
PLANNED="$( { git diff --name-only HEAD --; git ls-files --others --exclude-standard; } | sort -u )"

# D2: fingerprint the planned change CONTENT (not just names) so the approval
# binds to exactly what is being changed — INCLUDING untracked new files, whose
# path + blob-hash are folded in via a portable while-read (no `xargs -r`, which
# is GNU-only and hangs BSD/macOS on empty input; no index mutation). CHECK and
# VERIFY MUST use this byte-identical basis or the gate can never release. For a
# modify-only fix (no untracked files) the while-loop emits nothing, so the
# fingerprint is unchanged from the historical `git diff HEAD` hash.
FINGERPRINT="$( { git diff HEAD --; git ls-files --others --exclude-standard \
    | while IFS= read -r f; do printf '%s ' "$f"; git hash-object "$f"; done; } \
  | git hash-object --stdin | cut -c1-12)"

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
<!-- maintainer:machine-comment -->
This fix would modify the following security-sensitive path(s):

\`\`\`
$HITS
\`\`\`

Planned-diff fingerprint: \`$FINGERPRINT\`

Per the maintainer's protected-paths policy, I will not commit this
edit without explicit approval from $AUTHORIZED_USER.

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
# gate ONLY if it carries THIS fingerprint (replay-proof). MUST be the exact
# same command as CHECK (untracked files folded in the identical way) or the
# live fingerprint never matches the published one and the gate never releases.
FINGERPRINT="$( { git diff HEAD --; git ls-files --others --exclude-standard \
    | while IFS= read -r f; do printf '%s ' "$f"; git hash-object "$f"; done; } \
  | git hash-object --stdin | cut -c1-12)"

COMMENTS="$(gh issue view "$ISSUE_NUM" --json comments --jq '.comments')"

# CRITICAL: every select EXCLUDES the gate's own machine-authored comments
# (`contains("maintainer:machine-comment") | not`). WHY: CHECK posts its
# approval-REQUEST comment with the same gh token that resolves $AUTHORIZED_USER
# (gh api user), so that comment's author.login == $AUTHORIZED_USER, and its
# body literally contains BOTH `approve-protected-edit <fp>` AND
# `reject-protected-edit` as instructions to the human. Without this exclusion
# the request comment self-satisfies these filters, so the gate returns a
# verdict derived from ITS OWN comment (rejected/ok) instead of the human's —
# a total defeat of the control (privilege/decision confusion). Genuine human
# approvals never carry the HTML sentinel, so excluding it removes exactly the
# machine comments and never a real approval.
REJECTED=$(echo "$COMMENTS" | jq --arg user "$AUTHORIZED_USER" '
  [.[] | select(.author.login == $user)
       | select(.body | contains("maintainer:machine-comment") | not)
       | select(.body | test("\\breject-protected-edit\\b"))]
  | length')

# Approval must contain the phrase AND the CURRENT fingerprint. Both values
# pass as NAMED args (--arg), never bash-interpolated into the filter — the
# jq --arg trap defence. contains($fp) is a literal substring test (no regex).
APPROVED=$(echo "$COMMENTS" | jq --arg user "$AUTHORIZED_USER" --arg fp "$FINGERPRINT" '
  [.[] | select(.author.login == $user)
       | select(.body | contains("maintainer:machine-comment") | not)
       | select(.body | test("\\bapprove-protected-edit\\b"))
       | select(.body | contains($fp))]
  | length')

# Phrase present but WITHOUT the current fingerprint = stale/unbound approval
# (the diff was re-scoped since it was approved, or the user omitted the fp).
APPROVED_ANY=$(echo "$COMMENTS" | jq --arg user "$AUTHORIZED_USER" '
  [.[] | select(.author.login == $user)
       | select(.body | contains("maintainer:machine-comment") | not)
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
