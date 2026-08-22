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

## Census corrected 2026-08-22 — 48 repos, and a fourth state

The hub re-ran over the whole machine (48 repos, not the ~15 fleet repos). Two
structural corrections and one new state:

| state | count |
|---|---|
| LIVE (own tracked hook executes) | 6 |
| DECORATIVE (ships a hook git never resolves) | **3** — the only figure stable across both populations |
| SHADOWED (stale ignored `.git/hooks/pre-push`) | 9 (was 4) |
| INHERITED (no local `core.hooksPath`; takes the machine default) | **39** |

**The states are NOT a partition.** Two repos are LIVE *and* SHADOWED at once, so the
check must report each state per ARTIFACT and never classify a repo into one bucket.

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

- [ ] the three states above are distinguished by MEASUREMENT (both commands), never by
      the presence of a file
- [ ] a positive control proves the detector bites: a fixture whose `core.hooksPath`
      points somewhere else must be reported DECORATIVE, and a correctly-wired one must
      NOT be — a guard that reddens on correct configuration gets deleted
- [ ] report-only; no write to another repo's git config
- [ ] this repo's own state is asserted LIVE, so the detector is exercised on every run

## Notes

Not started, not authorized to implement. Filed so the finding does not evaporate with
the conversation that produced it — the whole point of the class is that nothing
complains, so nothing will re-surface it.
