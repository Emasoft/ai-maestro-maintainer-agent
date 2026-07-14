---
description: Create, inspect, and destroy git worktrees for isolated work in the entrusted repo. The destroy path refuses to discard an agent's work (wrong branch / detached HEAD / dirty tree) unless forced.
argument-hint: "[root|list|create <name>|remove <name>|recover]"
---

Manage `.worktrees/<name>` in the entrusted repo — a second checkout on its own
branch, sharing one object store. The cheapest isolation the maintainer has: a
risky refactor, a dependency bump, or a whole agent session happens there and is
thrown away without the main checkout ever having been dirty.

Loads skill: **maintainer-worktree**

Engine: `scripts/worktree.py` (importable, and the single source of truth).

Five verbs:

- `root` — print the MAIN checkout's root. Correct from inside a worktree, and
  correct when the path contains a space. This is the canonical `$MAIN_ROOT` for
  any report path.
- `list` — the worktrees, their branches, and whether any is detached or
  prunable. `--json` for structured output.
- `create <name>` — `.worktrees/<name>` on a new branch (default `wt/<name>`),
  branched from the repo's **detected** default branch, never a hardcoded
  `main`. Symlinks the gitignored dirs (`node_modules`, `.venv`, …) in so the
  worktree is usable immediately; `--no-link` to skip.
- `remove <name>` — destroy it. **Guarded**: refuses when the worktree is on a
  different branch, on a detached HEAD, or dirty — because removing it then would
  silently delete an agent's work. `--force` is the explicit opt-out;
  `--keep-branch` keeps the branch.
- `recover` — clean up after a crashed session (stale registrations, orphan
  directories). Never deletes a branch: it may hold the only copy of an
  interrupted session's commits. `--dry-run` to preview.

Why `--porcelain` appears everywhere: plain `git worktree list` prints
`<path> <sha> [<branch>]`, so splitting it by column truncates any path
containing a space — routine on macOS — and the caller then writes to a directory
that does not exist while reporting success.

Requires `.worktrees/` to be gitignored in the target repo. That is load-bearing,
not housekeeping: an unignored worktree is an untracked path, and a release gate
that refuses to publish a dirty tree will block the next release.
