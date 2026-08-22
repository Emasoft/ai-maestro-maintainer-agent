---
trdd-id: G88RIN1C
title: Detect guards that are committed but never executed on entrusted repos
column: backburner
created: 2026-08-22T19:47:45+0200
updated: 2026-08-22T19:47:45+0200
current-owner: maintainer-agent-session
task-type: feature
approval-tier: 0
relevant-rules: [3]
created-by: fleet census by the ai-maestro hub session, relayed 2026-08-22
---

# Detect guards that are committed but never executed on entrusted repos

## The finding this comes from

A hub census of **15 repos shipping `.githooks/pre-push`** measured that **3 of them
never execute it**:

- 2 (`defuddle-skill`, `maestro-orchestrate`) have `core.hooksPath` pointing at a
  directory **outside the repo** (`~/.config/git/hooks`).
- 1 (`AI-MAESTRO-WEBDESIGN-AGENT`) ships `.githooks` (dot) while `core.hooksPath` names
  `git-hooks` (hyphen).

**One character is enough, and nothing reports it.** The push protection is present,
reviewed, committed — and decorative. This repo was measured CLEAN
(`core.hooksPath=.githooks`, `.git/hooks/pre-push` absent, so git executes the tracked
file directly), which is exactly why the gap is invisible from here: a healthy host
looks identical to a broken one until you ask what git actually resolves.

A second, subtler state from the same census: **4 repos** have `core.hooksPath=.githooks`
AND a leftover `.git/hooks/pre-push`. Git runs the former and ignores the latter —
harmless to execution, **actively misleading to inspection**, because anyone opening
`.git/hooks/pre-push` to learn "what runs" reads the wrong file. That is the exact
mistake four sessions made in one day on this very subject.

## Why this is the MAINTAINER's job

The plugin's scope is **entrusted downstream repos**, and audit findings become
capabilities applied on each of them (`maintainer-guardian` already owns T3 branch-rule
drift, which is the same shape one layer up: a protection that is configured wrong
rather than absent).

The class generalizes past hooks. A gate can be enabled and check nothing:
- a hook git never resolves (this finding),
- a required status check whose context name never reports (already burned this project
  once — a `validate` vs `Validate` mismatch left PRs unmergeable forever),
- a linter whose glob matches no files.

**Each fails silently in the same direction: nothing is red, because nothing ran.**
Those are the findings that matter most precisely because nothing is failing on them.

## Census — RETRACTED TWICE, and the retractions are the useful part

**Do not cite any count here as settled.** Two successive hub censuses were withdrawn,
the second because its classifier was broken in a way that made it right for the wrong
reason. That history is kept because this card's whole subject is checks that pass
without measuring anything — a census that did exactly that is the best worked example
available.

**The classifier bug (hub's own post-mortem).** The loop tested
`[ -x "$d/$hp/pre-push" ]`, but `$hp` is ABSOLUTE for most repos, so the concatenation
produced `/Users/…/Code/foo//Users/…/.config/git/hooks` — a path that cannot exist.
Every branch failed and those rows printed `live=no` **by construction, for any input**.
The `DECORATIVE` branch additionally required `-z "$hp"` while `core.hooksPath` is set
everywhere, so **it fired zero times**. And the loop computed `git rev-parse --git-path
hooks` — the correct instrument — into a variable it never used. It survived review
because `live=no` was a TRUE sentence about those repos, reached by a route that would
have printed it regardless.

**Corrected numbers (ask git what it resolves, then ask the filesystem):**

| | count |
|---|---|
| execute a pre-push resolved to the **global LFS shim** | 39 |
| execute a pre-push resolved **repo-locally** | 7 |
| execute **nothing** at the resolved path | 2 |
| DECORATIVE (ships a guard git never resolves) | **5**, was reported 3 |

**46 of 48 repos execute a pre-push**, not the 6 the first table implied — anyone
reading "6 LIVE / 48" as coverage got the inverse of reality. The substantive point
survives all of it: for 39 of them the executed file is the LFS shim that gates nothing.

**DECORATIVE rose to 5 only under PATH-AGNOSTIC discovery** (`git ls-files | grep -E
'(^|/)pre-push$'` instead of three assumed directory names). One repo ships at
`scripts/hooks/pre-push`; another ships `.githooks/pre-push` while `hooksPath=git-hooks`
— two directories, one reviewed, the other executed. **Any implementation here must
discover hook files, never assume where they live** — assuming the directory is how the
first count missed two.

**The states are NOT a partition.** A repo can be LIVE *and* SHADOWED at once, so report
per ARTIFACT and never classify a repo into one bucket.

## Fifth state — DEPRIVED, and THIS REPO IS IN IT

`core.hooksPath` **replaces the entire hooks directory**; there is no per-hook fallback
to the global one. So a repo that sets it to ADD a push gate silently REMOVES every
other hook type the global dir was providing.

Measured here 2026-08-22:

```
.githooks/                -> pre-push                                    (1 file)
~/.config/git/hooks/      -> pre-push post-checkout post-commit post-merge
lost by overriding        -> post-checkout, post-commit, post-merge
```

**Benign in this repo** — it tracks zero LFS patterns and zero LFS objects, so the three
lost hooks were Git LFS hooks with nothing to do. **Not benign in general**, and that is
exactly why it belongs in a downstream check: an entrusted repo that DOES use LFS and
sets a local `hooksPath` loses LFS checkout/commit/merge behaviour with no error, no
warning, and a `core.hooksPath` value that reads as correctly configured. Fleet-wide, 7
of 9 repos with a local hooksPath provide only `pre-push`; one points at a directory
containing nothing and therefore runs no hooks at all while appearing configured.

This makes the model a **per-hook-type matrix**, not a per-repo state: for each hook
type, what does git resolve, and does a file exist there?

## Caution carried from the hub's near-miss

They formed "384/388 bytes is LFS-shim-sized, classify on size" and were about to use
it. Reading refuted it: one 384 B hook delegates to `publish.py --gate`, one 388 B hook
runs ruff + mypy under `set -euo pipefail`. Both real guards, merely short. **Size is a
reason to OPEN a file, never a reason to classify it.** The read is what proved the LFS
finding; the size only prompted it.

**INHERITED is not "protected by an external file" — measured, it is protected by
nothing.** `~/.config/git/hooks/pre-push` on this machine is 388 bytes of **stock Git
LFS**: it checks `git-lfs` is on PATH (its only exit path) and calls `git lfs pre-push`.
No publish gate, no ancestry walk, no branch guard. For contrast this repo's
`.githooks/pre-push` is 3165 bytes of process-ancestry enforcement — the size gap is
what prompted reading the file rather than accepting the config value.

Consequence, and the reason this state matters most: **`core.hooksPath` REPLACES, it
does not fall back.** Any INHERITED repo that also ships its own `.githooks/pre-push`
has that guard shadowed by an LFS shim which gates nothing — so it is DECORATIVE, and
the DECORATIVE=3 figure is a FLOOR, not a total. Such a repo reads as correctly
configured to anyone who checks `core.hooksPath` and stops there: the
healthy-looks-identical-to-broken trap, now wearing a plausible config value.

Open census question this raises, worth answering before implementing: **of the 39
INHERITED repos, how many ship a push guard of their own?** Each one is a gate both
present and inert.

Remediation note: the fix is per-repo LOCAL `core.hooksPath`, never editing the global
file — that file is shared by all 48 and changing it would alter LFS behaviour
machine-wide. (Its `.bak-20260413_202201` siblings are backups of an LFS shim, not of a
security control.)

THIS REPO remains unaffected and LIVE: local `core.hooksPath=.githooks` overrides the
global, `.git/hooks/pre-push` absent, tracked 3165-byte guard executes.

## Proposed capability (NOT yet implemented — this card is intake only)

A `maintainer-guardian` threat class (or a sibling check) that, per entrusted repo,
answers *what actually executes* rather than *what exists*:

1. `git config --get core.hooksPath` — empty, in-repo, or elsewhere?
2. `git rev-parse --git-path hooks` — the path git actually resolves.
3. Compare against the hook files the repo SHIPS. Report:
   - **DECORATIVE** — a shipped hook that git will never run (the 3 above).
   - **SHADOWED** — a leftover `.git/hooks/<name>` that git ignores because
     `core.hooksPath` is set (the 4 above); misleads readers, does not misbehave.
   - **LIVE** — the shipped file is the resolved file (the healthy 12).

Report-only in the first cut. Repairing another repo's git config is a mutation on a
tree this agent does not own, and the cross-project rule routes that through an issue or
a PR, never a direct edit.

## Acceptance

- [ ] hook files are DISCOVERED (`git ls-files | grep -E '(^|/)pre-push$'`), never
      assumed to live in a known directory — assuming the dir is what undercounted
      DECORATIVE by two
- [ ] the resolved path comes from `git rev-parse --git-path hooks`, and the classifier
      NEVER string-concatenates it with the repo root (`core.hooksPath` is frequently
      absolute; concatenating yields a path that cannot exist, and every branch then
      reports "not live" for any input — the exact bug that produced the retracted table)
- [ ] reported per ARTIFACT and per HOOK TYPE, never as one state per repo
- [ ] the states above are distinguished by MEASUREMENT, never by the presence of a file
      and never by its SIZE
- [ ] a positive control proves the detector bites: a fixture whose `core.hooksPath`
      points somewhere else must be reported DECORATIVE, and a correctly-wired one must
      NOT be — a guard that reddens on correct configuration gets deleted
- [ ] report-only; no write to another repo's git config
- [ ] this repo's own state is asserted LIVE, so the detector is exercised on every run

## Notes

Not started, not authorized to implement. Filed so the finding does not evaporate with
the conversation that produced it — the whole point of the class is that nothing
complains, so nothing will re-surface it.
