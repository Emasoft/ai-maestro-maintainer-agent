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
