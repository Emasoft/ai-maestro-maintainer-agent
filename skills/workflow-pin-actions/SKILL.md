---
description: |
  Use when the user wants to SHA-pin every unpinned third-party
  action reference in the maintained repo's workflows. Discovers
  every `uses: name@ref` under .github/workflows/ where `ref` is
  NOT a 40-char commit SHA (so `@v4`, `@v4.3.1`, `@main`, short
  SHAs all qualify); resolves `ref` to its current commit SHA via
  `gh api repos/OWNER/REPO/commits/REF --jq .sha`; replaces
  inline with `uses: name@<sha>  # vX.Y.Z` where the trailing
  comment is the longest matching semver tag at that SHA. Local
  refs (`./action`, `../action`) and Docker refs
  (`docker://image:tag`) are skipped — those have different
  pinning rules. Commits the diff DIRECTLY on the current branch
  with a conventional message. NEVER force-pushes (R19.7), NEVER
  pushes (caller's job), NEVER bumps major versions automatically
  — preserves the current major-line semantics, only pins to the
  latest commit on it. Assumes AI Maestro exports the gh auth
  token on the host; reads it via `$(gh auth token)`. Honours
  the 2.1.116 rate-limit hint — if a `gh api` call trips it the
  skill stops with a partial-progress disposition so the next
  session can resume. Do NOT trigger on requests to upgrade major
  versions or on read-only audit requests (use workflow-scan).
  Trigger with phrases like "pin workflow actions", "SHA-pin
  actions", or "harden action references".
allowed-tools: "Bash(gh:*), Bash(git:*), Bash(grep:*), Bash(awk:*), Read, Write, Edit, Grep, Glob"
---

# workflow-pin-actions — resolve unpinned actions to commit SHAs

Replaces every `uses: foo/bar@vN` (or any non-SHA ref) with the
full 40-char commit SHA at the head of that ref, plus a trailing
`# vX.Y.Z` comment for human readability. No major-version bumps.

## Prerequisites (auto-checked)

- `gh auth token` returns a value.
- Working tree clean (or only `.github/workflows/` already staged).
- Current branch is not `main` / `master` / `release/*` (skill
  aborts otherwise — protected branch).

## Workflow

1. Discover unpinned references with a tight regex:
   ```bash
   grep -REn '^\s*-?\s*uses:\s*[^@]+@[^[:space:]]+' .github/workflows/ \
     | grep -Ev 'uses:\s*\./|uses:\s*\.\./|uses:\s*docker://' \
     | grep -Ev 'uses:\s*[^@]+@[a-f0-9]{40}\b' \
     > /tmp/unpinned-uses-$$.txt
   ```
   Each line: `<file>:<lineno>: ...uses: foo/bar@ref`.
2. For each unique `foo/bar@ref`:
   ```bash
   SHA=$(gh api "repos/$REPO/commits/$REF" --jq '.sha')
   # Find the longest matching semver tag at that SHA:
   TAG=$(gh api "repos/$REPO/tags?per_page=100" \
     --jq "[.[] | select(.commit.sha==\"$SHA\") | .name] | sort_by(length) | reverse | .[0] // \"$REF\"")
   ```
   If `$REF` is already `vN`, prefer the most specific semver tag
   on that line (e.g. `v4` → `v4.3.1`). If the lookup fails (404,
   rate-limit), STOP and return a partial-progress disposition —
   do NOT skip silently and continue.
3. Replace inline using the Edit tool, one file at a time:
   `uses: foo/bar@vN` → `uses: foo/bar@<sha>  # vX.Y.Z`.
   Preserve indentation and any trailing comment-like text.
4. Re-validate after every file edit:
   - `python3 -c "import yaml; yaml.safe_load(open('<file>'))"` to
     confirm the YAML still parses.
   - `actionlint <file>` to confirm no syntactic regressions.
5. Run the **workflow-scan** skill once at the end: zizmor should
   now report zero `unpinned-uses` findings. If any remain, STOP
   and surface them — do not commit a partial pin.
6. Stage by name and commit:
   ```bash
   git add .github/workflows/<file1> .github/workflows/<file2> ...
   git commit -m "chore(ci): SHA-pin third-party actions"
   ```
7. Return:
   ```json
   {
     "pinned": <int>,
     "skipped_local": <int>,
     "skipped_docker": <int>,
     "commit": "<sha>",
     "report_md": "<path>"
   }
   ```

## Constraints

- NEVER bumps major versions automatically.
- NEVER force-pushes, never pushes.
- NEVER edits actions outside `.github/workflows/`.
- STOPs on rate-limit (partial progress, no commit).

## Resources

- zizmor `unpinned-uses` rule: <https://docs.zizmor.sh/audits/#unpinned-uses>
- GitHub Refs API: <https://docs.github.com/rest/git/refs>
- Companion skills: `workflow-scan`, `workflow-fix-safe`, `workflow-protect-branch`.
