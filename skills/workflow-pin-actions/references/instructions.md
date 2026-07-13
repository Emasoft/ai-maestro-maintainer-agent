# Full step-by-step — `workflow-pin-actions`

## Table of Contents

- [Step 1: Protected-branch guard](#step-1-protected-branch-guard)
- [Step 2: Discover unpinned refs](#step-2-discover-unpinned-refs)
- [Step 3: Resolve SHA + semver tag](#step-3-resolve-sha--semver-tag)
- [Step 4: Rewrite inline](#step-4-rewrite-inline)
- [Step 5: Per-file safety net](#step-5-per-file-safety-net)
- [Step 6: Final sweep](#step-6-final-sweep)
- [Step 7: Stage by name and commit](#step-7-stage-by-name-and-commit)

## Step 1: Protected-branch guard

Same as `workflow-fix-safe`: aborts on `main` / `master` /
`release/*`.

## Step 2: Discover unpinned refs

```bash
grep -REn '^\s*-?\s*uses:\s*[^@[:space:]]+@[^[:space:]]+' \
  .github/workflows/ \
  | grep -Ev 'uses:\s*\./|uses:\s*\.\./|uses:\s*docker://' \
  | grep -Ev 'uses:\s*[^@]+@[a-f0-9]{40}\b' \
  > /tmp/unpinned-uses-$$.txt
```

Each line is `<file>:<lineno>: ...uses: foo/bar@ref`. The third
grep filters out refs that are already 40-char SHAs.

Parse each line to extract `(file, lineno, repo, ref)`. Deduplicate
by `(repo, ref)`.

## Step 3: Resolve SHA + semver tag

For each unique `(repo, ref)`:

```bash
SHA="$(gh api "repos/$repo/commits/$ref" --jq '.sha')"

# Find the longest matching semver tag at that SHA. Prefer the
# most specific (v4.3.1 over v4).
TAG="$(gh api "repos/$repo/tags?per_page=100" \
  --jq "[.[] | select(.commit.sha==\"$SHA\") | .name] | sort_by(length) | reverse | .[0] // \"$ref\"")"
```

Fallback: if no tag matches the SHA exactly, use `$ref` as the
comment (this is acceptable for branch-name refs like `@main`).

If `gh api` returns 404 (deleted repo / private fork), STOP and
surface — do not skip silently and rewrite half of the workflow.

If the Bash tool emits the `GitHub API rate limit` hint, first try the
**unauthenticated** resolver, which does not spend REST quota:

```bash
# git ls-remote hits the git protocol, not the REST API — no rate
# budget consumed. It resolves a tag/branch ref to its SHA directly.
SHA="$(git ls-remote "https://github.com/$repo" "$ref" | awk '{print $1}' | head -n1)"
```

`git ls-remote` gives the SHA but NOT the semver-tag lookup (the trailing
`# vX.Y.Z` comment) — with the REST tags endpoint rate-limited, fall
back to using `$ref` verbatim as the comment. If `git ls-remote` also
fails or returns empty, THEN STOP and return
`{disposition: "partial", pinned_so_far: N}`; the next session resumes
from a fresh budget. Never leave a workflow half-pinned.

## Step 4: Rewrite inline

Use the Edit tool, one file at a time:

`uses: foo/bar@vN` → `uses: foo/bar@<sha>  # vX.Y.Z`

Preserve the original indentation. Preserve any trailing
comment-like text that wasn't a version pin.

## Step 5: Per-file safety net

After every file edit:

```bash
python3 -c "import yaml; yaml.safe_load(open('$file'))"
actionlint "$file"
```

If either fails, revert the file via `git checkout -- "$file"` and
STOP — do not continue and create a half-broken commit.

## Step 6: Final sweep

```bash
uvx zizmor --gh-token "$(gh auth token)" .github/workflows/
```

Output MUST report zero `unpinned-uses` findings. If any remain,
STOP — there is a bug in the discovery regex or a ref the tool
could not resolve. Surface the remaining unpinned refs.

## Step 7: Stage by name and commit

```bash
CHANGED="$(git diff --name-only -- .github/workflows/)"
echo "$CHANGED" | xargs git add --

git commit -m "chore(ci): SHA-pin third-party actions"
```

Caller pushes. R19.7 — never force-push, never `--no-verify`.
