---
trdd-id: OOG7QWVV
title: Ship a real worktree capability, and fix the MAIN_ROOT idiom that truncated paths with a space
column: dev
created: 2026-07-14T21:33:03+0200
updated: 2026-07-14T21:33:03+0200
current-owner: ai-maestro-maintainer-agent
task-type: feature
release-via: publish
relevant-rules: [1, 6]
---

# Ship a real worktree capability, and fix the MAIN_ROOT idiom

## Why

The user observed that the plugin "has a very poor handling of the worktrees."
It is worse than poor. Two findings, both verified, not inferred:

**1. There was no worktree capability at all.** No skill, no command, no script.
`ls skills/ commands/ | grep worktree` returned nothing.

**2. The only worktree code in the plugin was broken, in 16 files.** Every
report-writing skill resolved the main repo root with:

```bash
MAIN_ROOT="$(git worktree list | head -n1 | awk '{print $1}')"
```

`git worktree list` prints `<path> <sha> [<branch>]`, so `awk '{print $1}'`
splits on the **first space**. Proven in a real repo whose path contains one:

```text
raw:       [/…/scratchpad/my repo b766fc2 [master]]
awk idiom: [/…/scratchpad/my]          <-- TRUNCATED
porcelain: [/…/scratchpad/my repo]     <-- correct
```

A path with a space is routine on macOS — iCloud Drive, Google Drive, any folder
named in a GUI. On such a machine every report-writing skill would `mkdir -p` a
directory that does not exist and write the audit trail there, **reporting
success**. `scripts/sandbox/sandbox.py` carried the identical bug in Python
(`.split()[0]`).

The failure mode is the dangerous kind: nothing errors, nothing is red, and the
evidence simply goes to a place nobody looks.

**The bug's source was outside the plugin.** It is prescribed by the canonical
shell prologue in the user's global rule `~/.claude/rules/agent-reports-location.md`.
The plugin copied it faithfully 14×. The user approved fixing it at the source —
otherwise every future skill, agent, and plugin re-seeds it.

## Reference

`downloads_dev/parallel-code-main.zip` (johannesjo/parallel-code — an Electron
app that dispatches AI agents into isolated worktrees). Treated as **untrusted
data**: extracted to a scratchpad, read, never executed. Its `electron/ipc/git.ts`
is a catalogue of hard-won worktree edge cases covering the whole create→destroy
cycle. We took the **knowledge**, not the code (it is TypeScript; we are Python).

Reading its doc-comments — which the user insisted on — changed three things that
would otherwise have shipped wrong, one of them destructively. See "What the
reference's comments changed" below.

Its **security** posture, by contrast, was not worth taking: see EHT below.

## What was built

### `scripts/worktree.py` — the engine

One module, so the logic exists once instead of being copy-pasted into 16
documents. Each function carries an edge case mined from the reference:

| Function | The edge case it exists for |
|---|---|
| `main_root()` | Space-safe: `git worktree list --porcelain \| sed -n '1s/^worktree //p'`. Correct from the main checkout **and from inside a linked worktree**. |
| `list_worktrees()` | Parses `--porcelain` line-by-line, never by column. |
| `detect_main_branch()` | **Never hardcodes main/master.** `origin/HEAD` → verify the target still resolves (a symref goes STALE when the remote renames its default branch) → `git remote set-head --auto` → remote-tracking main/master → local → `init.defaultBranch`. |
| `create_worktree()` | Catches two failures git only explains cryptically: an **empty repo**, and a **branch-prefix collision** (git stores refs as FILES, so `fix` and `fix/a` cannot coexist). |
| `assert_safe_to_destroy()` | **The data-loss guard.** See below. |
| `remove_worktree()` | Guard → `worktree remove --force` → on failure `rmtree` **with backoff** (a sandbox may still be releasing a mount) → `prune` → `branch -D`. Idempotent. |
| `recover_stale()` | The crashed-session case. **Never deletes a branch** — it may hold the only copy of an interrupted session's commits. |
| `gitignored_dirs()` / `link_gitignored_dirs()` | A fresh worktree holds only TRACKED files — no `node_modules`, no `.venv`. An agent dropped into it cannot build or test: it is **born broken**. Symlink them in. Link names are validated to a single path component, so a crafted name cannot escape the worktree. |
| `ensure_symlink_excludes()` | The subtle half — see mechanic 2 below. |

### The destroy guard (the reason the destroy half can be trusted)

Before anything is deleted, the worktree must be on the branch we expect, on an
attached HEAD, with a clean tree. Otherwise `remove` REFUSES and says why.

Quoting the reference's own comment, which is what put this in scope:

> *AI agents sometimes check out a different branch (or detach HEAD), and merging
> the original branch would silently discard their work.*

Three shapes, so three guards and three tests: **wrong branch**, **detached
HEAD**, **dirty tree**. `force=True` is the explicit, auditable opt-out — and even
forced, it discards only *our* worktree and *our* branch: a branch the agent
created itself survives (asserted by `test_force_still_does_not_delete_someone_elses_branch`).

### What the reference's comments changed

Three findings that would have made the implementation wrong:

| Finding | Consequence had it been missed |
|---|---|
| **In a linked worktree, `.git` is a FILE, not a directory** (it holds `gitdir: …`). | The planned `<worktree>/.git/info/exclude` join names a path that cannot exist. The code would have written the exclusions nowhere, reported success, and the symlink noise would have stayed. Must resolve via `git rev-parse --git-common-dir`. |
| **Verify the worktree is still on its expected branch before destroying it.** | A destroy path without this deletes an agent's work with no error and no trace. This is the guard above. |
| **Git refuses to check out a branch that is live in another worktree.** | A naive `git checkout <branch>` in the main root fails. Operate INSIDE the worktree. |

Two smaller ones, kept: exclude patterns must be **root-anchored** (`/node_modules`,
not `node_modules`) so a legitimately-nested tracked dir of the same name is still
visible to git; and the exclude block uses a **header line as an idempotency
marker** so a second worktree does not duplicate it.

**Deliberately NOT ported:** the `.claude`-must-be-a-real-directory bwrap
workaround (specific to their Electron sandbox, which we do not run), and the
merge-base/cherry-pick diff-refinement machinery (`pickMergeBase`,
`refineDiffBaseWithCherryPick`) — that is a *diff-review* feature belonging to
their UI, not lifecycle. Shipping machinery we cannot exercise is how dead code
gets in.

### `skills/maintainer-worktree/` + `commands/maintainer-worktree.md`

Five verbs: `root`, `list`, `create`, `remove`, `recover`. Registered in
`the-skills-menu` (now 29 skills) and the README.

### The 16-file fix

```diff
- MAIN_ROOT="$(git worktree list | head -n1 | awk '{print $1}')"
+ MAIN_ROOT="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
```

13 shipped `.md` docs · `scripts/sandbox/sandbox.py` (the Python `.split()[0]`
twin) · `design/requirements/PRRD.md` (rule **S6.1 → S6.2**, which *prescribed*
the idiom) · `tests/test_workdir_containment.py` (which asserted on it, and now
enforces `--porcelain` instead).

### `~/.claude/rules/agent-reports-location.md` — fixed at the source

Corrected the canonical prologue and added the explanation. This is why the bug
reached 16 files, and why it would have reached the next 16.

### `.gitignore` += `.worktrees/`

**Load-bearing, not housekeeping.** `.worktrees/` was not ignored, so a worktree
created under the repo shows as untracked — and the release-staging guard shipped
in v1.7.15 (`_unmanaged_dirty_paths`) refuses to cut a release with unmanaged
dirty paths. Without this line, merely *creating* a worktree would have bricked
the next release.

## Tests — `tests/test_worktree.py` (41 new, real git repos, no mocks)

Suite: **594 → 635**, all green. CPV `--strict`: `CRITICAL=0 MAJOR=0 MINOR=0 NIT=0`.

Three of these deserve naming, because each exists to stop a test from being
decoration:

- `test_the_old_awk_idiom_is_genuinely_broken` — the **control**. It asserts the
  idiom we removed *does* truncate, and that the truncated path does not exist.
  Without it, the "new one works" test could pass for a trivial reason.
- `test_the_offender_detector_actually_detects_an_offender` — the regression guard
  is fed the real bug (both the shell and Python shapes) and the real fix, in both
  directions. Two earlier versions of that detector were wrong: one flagged skills
  that merely *mention* awk in prose, and — worse — any check keyed on the literal
  string `"worktree list"` **misses the Python form entirely**, because subprocess
  spells it `["git", "worktree", "list"]`. It would have certified the buggiest
  file in the repo as clean.
- `test_exclude_entries_are_root_anchored` — carries its own **counterfactual**:
  it appends the bare pattern an unanchored implementation would have written and
  asserts the nested tracked dir *does* vanish. A guard that cannot fail is worse
  than no guard.

## EHT — effects to handle

- **TRDD (new):** port the reference's `docker/Dockerfile` (agent CLIs in a
  container) into `scripts/sandbox/dockerfiles/`. **Security must be fixed on
  port** — the user's words: *"security was completely ignored by the
  parallel-code project."* It does `curl -fsSL … | bash` (this plugin ships
  `scripts/sentinel/rules/curl_pipe_shell.py`, which flags exactly that), runs as
  **root** (creates an `agent` user but never `USER agent`), and pins nothing
  (`FROM ubuntu:22.04`). CI runs Checkov/Trivy over that directory and would fail.
- **TRDD (new):** port the reference's Apple codesign + notarization workflow as a
  `maintainer-macos-notarize` skill. The ephemeral-keychain + App Store Connect
  API-key pattern and its `if: always()` cleanup are genuinely good. On port: add
  `timeout-minutes` (the reference has none → 6h default, violating the gh-actions
  rule), scope `permissions` per-job instead of repo-wide `contents: write`, and
  cover the non-electron-builder path (`xcrun notarytool submit --wait` +
  `stapler staple`).
- **Upstream (CPV):** `RC-DEP-TAG-PIPELINE` is a **false positive**. It claims
  `publish.py` never tags `{name}--v{version}`, but `scripts/publish.py:1698` builds
  `f"{get_plugin_name(root)}--v{new_ver}"` and pushes it atomically —
  `ai-maestro-maintainer-agent--v1.7.15` exists on the remote. CPV's scan greps for a
  literal plugin name and misses the computed f-string. File on
  `Emasoft/claude-plugins-validation`; do not patch CPV from this repo (cross-project rule).

## Bug autopsy

The idiom was not careless — it was *inherited*. It sat in a global rule that
every skill was told to paste verbatim, so it propagated by exactly the mechanism
that was supposed to guarantee consistency. Two guardrails now exist so it cannot
come back: the rule is fixed at the source, and
`test_no_shipped_file_still_uses_the_truncating_awk_idiom` fails the suite if any
tracked file invokes `git worktree list` without `--porcelain`.

The through-line with the last three findings holds: **the findings that matter
most are the ones nothing is failing on.** No test was red, no gate was failing,
and no report was missing — because on a path without a space the bug is
invisible, and every CI machine has a path without a space.
