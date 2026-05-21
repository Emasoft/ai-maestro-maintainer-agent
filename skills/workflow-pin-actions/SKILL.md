---
description: |
  Use when the user wants to SHA-pin every unpinned third-party
  action reference in the maintained repo's workflows. Discovers
  every `uses: name@ref` under .github/workflows/ where `ref` is
  NOT a 40-char commit SHA (so `@v4`, `@v4.3.1`, `@main`, short
  SHAs all qualify); resolves `ref` to its current commit SHA via
  `gh api repos/OWNER/REPO/commits/REF --jq .sha`; replaces
  inline with the full 40-char SHA plus a trailing comment that
  carries the longest matching semver tag at that SHA. Local
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
---

# workflow-pin-actions — resolve unpinned actions to commit SHAs

Replaces every unpinned `uses: foo/bar@vN` with the full 40-char
commit SHA at the head of that ref, plus a trailing semver
comment. No major-version bumps.

## Overview

Discovers every `uses: name@ref` under `.github/workflows/` where
the ref is not already a 40-char commit SHA. For each, resolves
the current commit SHA via the GitHub API and rewrites inline
with the SHA plus a trailing semver comment. Commits on the
current branch. Never pushes. Never bumps majors.

## Prerequisites

- `gh auth token` returns a value.
- Working tree clean (or only `.github/workflows/` already
  staged).
- Current branch is NOT `main` / `master` / `release/*` (skill
  aborts otherwise — protected-branch guard).

## Instructions

1. Discover unpinned references with a tight regex over
   `.github/workflows/*.yml`. Skip `./`, `../`, and `docker://`
   refs.
2. For each unique `name@ref`, resolve the commit SHA via
   `gh api repos/{owner}/{repo}/commits/{ref} --jq .sha` and the
   longest matching semver tag at that SHA for the comment.
3. Rewrite inline with the full SHA plus a trailing semver
   comment. Use the Read+Edit tools per file.
4. Re-validate every edited file: `python3 -c "import yaml;
   yaml.safe_load(open(F))"` plus `actionlint F`.
5. Final sweep: invoke `workflow-scan`; zizmor must now report
   zero `unpinned-uses` findings.
6. Stage by name and commit
   `chore(ci): SHA-pin third-party actions`.

Full commands and the exact regex: see
[references/instructions.md](references/instructions.md).

## Output

A JSON object with `pinned`, `skipped_local`, `skipped_docker`,
`commit`, and `report_md` fields, plus a commit on the current
branch.

## Error Handling

| Error | Action |
|-------|--------|
| `gh api commits/{ref}` returns 404 | Stop, surface — do not skip silently |
| Rate-limit hint | Stop with partial-progress disposition |
| YAML parse fails after edit | Revert that file, stop, surface |
| actionlint fails after edit | Revert that file, stop, surface |
| `workflow-scan` post-sweep still finds unpinned | Stop, no commit |
| Protected branch | Stop, ask for a feature branch |

## Examples

```
User: "SHA-pin every action in the workflows"
→ Discover 5 unpinned refs (actions/checkout@v4, etc.)
→ Resolve each via gh api commits/v4 --jq .sha
→ Rewrite inline with 40-char SHA + semver comment
→ workflow-scan post-sweep — zero unpinned-uses findings
→ git add .github/workflows/*.yml
→ git commit -m "chore(ci): SHA-pin third-party actions"
→ Return: {pinned: 5, skipped_local: 0, commit: "abc1234", …}
```

## Resources

- zizmor unpinned-uses rule:
  <https://docs.zizmor.sh/audits/#unpinned-uses>
- GitHub Refs API:
  <https://docs.github.com/rest/git/refs>
- Companion skills: `workflow-scan`, `workflow-fix-safe`,
  `workflow-protect-branch`.
- [Full step-by-step instructions](references/instructions.md)
