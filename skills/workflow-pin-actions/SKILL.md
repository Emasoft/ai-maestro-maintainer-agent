---
description: |
  Use when the user wants to SHA-pin every unpinned third-party
  action in the maintained repo's workflows. Resolves each
  `uses: name@ref` (where ref isn't a 40-char SHA) to its commit
  SHA via `gh api`, replaces inline with the SHA + trailing
  `# vX.Y.Z` comment. Commits on the current branch. NEVER
  force-push or bump majors.
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

## Scope

ONLY resolves unpinned `uses: name@ref` references to 40-char SHAs
+ trailing semver comment. Does NOT:

- Bump major versions — preserves the existing `vN` constraint.
- Pin first-party `actions/*` / `github/*` references — those are
  excluded by convention (use the canonical owner-maintained refs).
- Run on protected branches (`main`, `master`, `release/*`).
- Force-push or push at all — caller pushes.
- Modify YAML other than the `uses:` field (no formatting, no
  reflow, no comment removal).

Idempotent — re-running on an already-pinned workflow is a no-op.

## Resources

- zizmor unpinned-uses rule:
  <https://docs.zizmor.sh/audits/#unpinned-uses>
- GitHub Refs API:
  <https://docs.github.com/rest/git/refs>
- Companion skills: `workflow-scan`, `workflow-fix-safe`,
  `workflow-protect-branch`.
- [Full step-by-step instructions](references/instructions.md):
  - Step 1: Protected-branch guard
  - Step 2: Discover unpinned refs
  - Step 3: Resolve SHA + semver tag
  - Step 4: Rewrite inline
  - Step 5: Per-file safety net
  - Step 6: Final sweep
  - Step 7: Stage by name and commit
