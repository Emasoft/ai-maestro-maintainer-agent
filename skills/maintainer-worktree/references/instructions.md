# maintainer-worktree — runnable recipes

Everything here shells out to `scripts/worktree.py`. The engine is the single
source of truth; these are the recipes for driving it, plus the three mechanics
that are easy to get wrong and expensive to get wrong.

## Table of Contents

- [Step 1: Resolve the main repo root](#step-1-resolve-the-main-repo-root)
- [Step 2: Create an isolated worktree](#step-2-create-an-isolated-worktree)
- [Step 3: Work inside it](#step-3-work-inside-it)
- [Step 4: Destroy it](#step-4-destroy-it)
- [Step 5: Recover after a crash](#step-5-recover-after-a-crash)
- [The three mechanics that bite](#the-three-mechanics-that-bite)
- [Report](#report)

## Step 1: Resolve the main repo root

```bash
MAIN_ROOT="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
[ -n "$MAIN_ROOT" ] || MAIN_ROOT="$CLAUDE_PROJECT_DIR"   # not a git repo
```

`--porcelain` is mandatory. Plain `git worktree list` prints
`<path> <sha> [<branch>]`, so any column split truncates a path containing a
space and silently names a directory that does not exist.

## Step 2: Create an isolated worktree

```bash
uv run scripts/worktree.py create hotfix-auth
# -> created <repo>/.worktrees/hotfix-auth on branch wt/hotfix-auth
```

Options:

| Flag | Effect |
|---|---|
| `--branch <B>` | branch name (default `wt/<name>`) |
| `--base <REF>` | branch from `REF` (default: the repo's detected default branch) |
| `--no-link` | do NOT symlink the gitignored (local-scoped) paths into the worktree |

The default base is **detected**, never assumed: `origin/HEAD` first (re-pointed
with `git remote set-head --auto` if it has gone stale), then a remote-tracking
`main`/`master`, then a local one, then `init.defaultBranch`. A repo that was
cloned before its remote renamed `master` → `main` still carries a stale
`origin/HEAD`, and trusting it blindly branches from a ref that no longer exists.

## Step 3: Work inside it

The worktree is usable immediately. A worktree checks out only **git-TRACKED**
files, so everything **git-ignored** — the *local-scoped* half — has been
symlinked in:

```bash
cd "$(uv run scripts/worktree.py root)/.worktrees/hotfix-auth"
git status --porcelain      # clean — the symlinks are excluded (see below)

npm test                    # node_modules resolves to the main checkout's
ls .claude/skills/          # a locally-installed skill is present
memgrep recall "…" .claude/project/memory   # the INDEX resolves, so this finds things
```

**Check that last one.** `.claude/` is *partially* tracked: its project memory
(`.md` files) is committed and arrives for free, but the memgrep **index** at
`.claude/project/memory/.memgrep/` is gitignored. Without the symlink the agent
has the memory files and no index, and `memgrep recall` **returns nothing and
raises no error** — it reports an empty corpus rather than a missing index, so
the agent quietly proceeds as though there were nothing to remember. Same for a
local-only skill in `.claude/skills/` and for `settings.local.json`.

The links are **live, not copies**: local state is shared with the main checkout.
That is deliberate — a copy would drift, and a memory written inside the worktree
would be destroyed along with it.

Commit as normal. The branch is real; the objects are shared with the main repo.

## Step 4: Destroy it

```bash
uv run scripts/worktree.py remove hotfix-auth
```

### The destroy-guard decision table

`remove` inspects the worktree BEFORE deleting anything, and refuses when what
it finds is not what it left:

| State found | Action | Why |
|---|---|---|
| on `wt/<name>`, clean | remove + delete the branch | the expected case |
| on a **different branch** | **REFUSE** | an agent checked out its own branch; deleting now discards work we never made |
| **detached HEAD** | **REFUSE** | commits there are reachable from no branch at all |
| **dirty tree** | **REFUSE** | uncommitted work is reachable from nothing |
| any of the above, `--force` | remove | the explicit, auditable opt-out |

This is a **data-loss** guard, not a style preference. The failure it prevents
is silent: the orchestrator believes the worktree holds the branch it created,
removes the directory, deletes that branch — and the agent's actual work, on
some other ref, is gone with no error.

`--force` still does not delete a branch the agent created itself. It discards
the *worktree*, not work we never made.

`--keep-branch` removes the directory and preserves the branch for later.

## Step 5: Recover after a crash

```bash
uv run scripts/worktree.py recover --dry-run   # report only
uv run scripts/worktree.py recover             # clean
```

Handles two kinds of wreckage:

- a registration git still holds for a directory that is gone (`prunable`),
- a directory under `.worktrees/` that git never knew about (a `worktree add`
  that died halfway).

It deliberately **does not delete branches**. A stale worktree's branch may be
the only copy of an interrupted session's commits, and guessing wrong is
irreversible. An independent git repo cloned under `.worktrees/` (it has a `.git`
*directory*, not a `.git` *file*) is skipped and reported, never deleted.

## The three mechanics that bite

### 1. In a linked worktree, `.git` is a FILE

Not a directory. It contains a single line:

```text
gitdir: /path/to/repo/.git/worktrees/hotfix-auth
```

So `<worktree>/.git/info/exclude` **names a path that cannot exist**. Code that
joins that path writes the exclusions nowhere, reports success, and the
exclusions silently never take effect. Resolve it properly:

```bash
EXCLUDE="$(git rev-parse --git-common-dir)/info/exclude"
```

### 2. `.gitignore`'s `node_modules/` does NOT match a symlink

A trailing-slash pattern matches a **directory**. The symlink we create into the
worktree is not a directory, so it is *not* ignored: it shows up as untracked in
every `git status` the agent runs, and is one careless `git add` away from being
committed as a link into someone's home directory.

The fix is a pattern without the trailing slash, in `info/exclude`:

```text
/node_modules
```

**Root-anchored** (`/node_modules`), never bare (`node_modules`). A bare pattern
matches at every depth, which would also hide a legitimately tracked
`packages/foo/dist` in a monorepo — a silent, data-losing overreach. Anchor it to
the root so it hides exactly the one symlink we created.

### 3. Git refuses to check out a branch that is live in another worktree

```text
fatal: 'wt/hotfix-auth' is already used by worktree at '.../worktrees/hotfix-auth'
```

This is git protecting you, not an error to route around. Operate on the branch
**inside** its worktree (`git -C "$WT" …`), not from the main checkout.

`git -C` here assumes the MAIN session. Inside an `Agent(isolation: "worktree")`
subagent it does not reach `$WT`: Claude Code 2.1.210 / 2.1.216 redirect git into
that agent's own worktree and closed `git -C`, `--git-dir`, `GIT_DIR` and
`GIT_WORK_TREE` as escapes. So the fallback there is not a different flag — it is
that this skill does not belong in such an agent, which already has its own
isolation.

## Report

```bash
MAIN_ROOT="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
DIR="$MAIN_ROOT/reports/maintainer-worktree"
mkdir -p "$DIR"
REPORT="$DIR/$(date +%Y%m%d_%H%M%S%z)-worktree.md"
```
