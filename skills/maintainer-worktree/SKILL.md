---
description: |
  Create, inspect, and destroy git worktrees for isolated work in the
  entrusted repo — a risky refactor, a dependency bump, or an agent
  session that must not touch the main checkout. Five verbs: root,
  list, create, remove, recover. The destroy path REFUSES to discard
  work (wrong branch / detached HEAD / dirty tree) unless forced.
  Also the canonical way to resolve $MAIN_ROOT for a report path.
  Trigger with "make a worktree", "work in isolation", "clean up
  worktrees", "remove the worktree", "where is the main repo root".
---

# maintainer-worktree — isolated worktrees, created and destroyed safely

## Overview

A git worktree is a second checkout of the same repository on a different
branch, sharing one object store. It is the cheapest isolation the maintainer
has: a risky edit, a dependency bump, or a whole agent session can happen in
`.worktrees/<name>` and be thrown away without the main checkout ever having
been dirty.

The engine is `scripts/worktree.py`. Everything below shells out to it — the
logic lives in ONE place because the last time worktree handling was
copy-pasted into many documents, a single bug spread to sixteen files.

**The bug, for context, because it explains the whole design.** `git worktree
list` prints `<path> <sha> [<branch>]`. Parsing that by column
(`awk '{print $1}'`, `cut -d' ' -f1`, Python's `.split()[0]`) truncates any path
containing a **space** — routine on macOS. A skill that resolved its report
directory that way would `mkdir -p` a path that does not exist and write its
audit trail there, reporting success. Always `--porcelain`.

## Prerequisites

- `git` ≥ 2.17 on PATH (`worktree list --porcelain`, `worktree remove`).
- The entrusted repo has at least one commit (`worktree add` needs a base).
- `.worktrees/` is gitignored in the target repo. **This is load-bearing**: an
  unignored worktree is an untracked path, and a release-staging guard that
  refuses to publish a dirty tree will block the next release.

## Instructions

Run the engine from anywhere inside the repo. It resolves the main checkout
itself, so it behaves the same from the main root or from inside a worktree.

### 1. Resolve the main repo root (`root`)

The canonical `$MAIN_ROOT` for any report path. Correct from a linked worktree,
and correct when the path contains a space:

```bash
MAIN_ROOT="$(uv run scripts/worktree.py root)"
```

The pure-shell equivalent, when the engine is not on hand:

```bash
MAIN_ROOT="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
```

### 2. Inspect (`list`)

```bash
uv run scripts/worktree.py list          # human-readable
uv run scripts/worktree.py list --json   # path, branch, head, detached, prunable
```

### 3. Create (`create`)

```bash
uv run scripts/worktree.py create <name> [--branch B] [--base REF] [--no-link]
```

Creates `.worktrees/<name>` on a new branch (default `wt/<name>`), branched from
the repo's **detected** default branch — `origin/HEAD`, repaired if stale, never
a hardcoded `main`.

It then **symlinks every gitignored path** — files and directories, at **any
depth** — from the main checkout into the worktree, and hides them via
`.git/info/exclude`. Pass `--no-link` to skip it.

**Why this is not optional.** A worktree checks out only **git-TRACKED** files.
Restated in scope terms:

| scope | | reaches the worktree by |
|---|---|---|
| **project-scoped** = git-tracked | committed, shared | **git checks it out.** Free. |
| **local-scoped** = git-ignored | machine-private | **nothing** — it is simply ABSENT. |

The obvious half is `node_modules` / `.venv`: without them the agent cannot
install, build, or test, and the worktree is born broken. At least that one fails
loudly.

**The dangerous half is `.claude/`, because it is PARTIALLY tracked and its
failure is SILENT.** `.claude/project/memory/*.md` is tracked and arrives; but a
locally-installed skill in `.claude/skills/`, `settings.local.json`,
`.claude/janitor/`, and — three levels down, *inside a tracked directory* —
`.claude/project/memory/.memgrep/`, **the memgrep INDEX**, are all ignored. Miss
them and the agent has the memory files but no index, so **`memgrep recall`
returns nothing and raises no error**: it reports an empty corpus rather than a
missing index, and the agent proceeds as if there were nothing to remember.

The links are **live, not copies** — deliberately. A copy would drift, and a
memory the agent wrote inside the worktree would die with it.

Two failures are caught up front, because git's own messages for them are
opaque:

- **an empty repo** — `worktree add` has no commit to branch from;
- **a branch-prefix collision** — branch `fix` exists, so `fix/a` is impossible,
  because git stores refs as *files* on disk and `fix` cannot be both a file and
  a directory.

### 4. Destroy (`remove`)

```bash
uv run scripts/worktree.py remove <name> [--force] [--keep-branch]
```

**The guard is the point.** Before anything is deleted, the worktree must be on
the branch we expect, on an attached HEAD, with a clean tree. If it is not,
`remove` REFUSES and says why.

That is not defensiveness for its own sake. An agent working inside a worktree
can check out a different branch or detach HEAD. Removing that worktree — while
still believing it holds the branch we created — deletes the agent's work with
no error and no trace. `--force` is the explicit opt-out, and even then it
discards only *our* worktree and *our* branch: a branch the agent created itself
survives.

`--keep-branch` removes the directory and leaves the branch for later.

### 5. Recover (`recover`)

```bash
uv run scripts/worktree.py recover [--dry-run]
```

Cleans up after a crashed session: registrations git still holds for directories
that are gone, and directories under `.worktrees/` git never knew about.

It **never deletes a branch** — a stale worktree's branch may hold the only copy
of an interrupted session's commits. Branch deletion belongs to `remove`, which
checks first. An independent git repo someone cloned under `.worktrees/` is
skipped, not deleted.

### 6. Report

Reports go to `$MAIN_ROOT/reports/maintainer-worktree/` with a local-time +
GMT-offset stamp:

```bash
MAIN_ROOT="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
DIR="$MAIN_ROOT/reports/maintainer-worktree"
mkdir -p "$DIR"
REPORT="$DIR/$(date +%Y%m%d_%H%M%S%z)-worktree.md"
```

## Output

One line per action (`created … on branch …`, `removed …`, `cleaned: …`), and a
non-zero exit with an actionable message on refusal. A refusal is a normal,
expected outcome — it means the guard did its job.

## Boundaries

- Does **not** merge, rebase, or cherry-pick. Creating and destroying isolation
  is the scope; integrating the result is the caller's decision.
- Does **not** dispatch agents into worktrees. Claude Code already ships
  `Agent(isolation: "worktree")`; a second orchestration surface would compete
  with it.
- Does **not** touch a worktree it did not create, beyond listing it.

## Two harness behaviours this skill has to live with (Claude Code 2.1.232)

Neither is a defect here, and neither is worked around — both are places where
the harness will refuse or redirect something these instructions ask for, and a
silent redirect is worse than a known one.

- **Run this skill from the MAIN session, not from inside a worktree-isolated
  agent or session.** A worktree-isolated context has git redirected into its
  OWN worktree: 2.1.210 / 2.1.216 closed the escapes — `git -C`, `--git-dir`,
  `GIT_DIR`, `GIT_WORK_TREE` — and 2.1.222 extended the containment to file
  edits and Bash in EVERY session type (not only `Agent(isolation: "worktree")`
  subagents; worktree-isolated sessions and their subagents could previously
  still run destructive git against the main checkout). Every `git -C "$WT" …`
  below is written for the main checkout and will not reach the path it names
  from inside one. That containment is correct; it just means this skill is the
  wrong tool there, since such a context already has the isolation this skill
  exists to create.
- **`.worktrees/` is deliberately NOT `.claude/worktrees/`.** Since 2.1.206 the
  `EnterWorktree` tool asks for confirmation before entering a worktree outside
  `.claude/worktrees/`, so pointing it at ours prompts. Keep them separate
  anyway: `.claude/worktrees/` is the harness's own managed area, and putting
  ours there would let two lifecycles create and delete in the same directory.
  Drive ours with the verbs below, not with `EnterWorktree`.

## Done when (terminating conditions)

The task is complete when the verb you ran reached one of its terminal states:

- [ ] **`root` / `list`** — the value is printed. Read-only; there is nothing to
  undo and nothing to verify.
- [ ] **`create`** — `.worktrees/<name>` exists, is on the new branch, and
  `git -C .worktrees/<name> status --porcelain` is **empty**. A non-empty status
  means the gitignored-dir symlinks were not excluded, and the worktree will
  pollute every status the agent runs. Investigate before handing it over.
- [ ] **`remove`** — the directory is gone and `list` no longer shows it. **A
  REFUSAL IS ALSO A TERMINAL STATE**: if the guard refused (wrong branch,
  detached HEAD, dirty tree), the task is *done* and the answer is "not safe to
  remove". Report the reason to the caller. Do **not** reflexively re-run with
  `--force` — that is a decision for whoever owns the work being discarded.
- [ ] **`recover`** — `list` shows no prunable entries and `.worktrees/` holds no
  orphan directories. Anything reported as `SKIPPED` is intentional and stays.

## Resources

- `scripts/worktree.py` — the engine (also importable: `main_root()`,
  `list_worktrees()`, `create_worktree()`, `remove_worktree()`, …).
- [Full step-by-step instructions](references/instructions.md):
  - Step 1: Resolve the main repo root
  - Step 2: Create an isolated worktree
  - Step 3: Work inside it
  - Step 4: Destroy it
  - Step 5: Recover after a crash
  - The three mechanics that bite
  - Report
- `tests/test_worktree.py` — real-git-repo tests, including the
  path-with-a-space regression and all three destroy-guard refusals.
