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

## The finding this comes from (IN-SCOPE statement — see the SCOPE section below)

**`ai-maestro-plugins` — the marketplace every agent in the ecosystem installs from —
ships no push-policy gate.** It dispatches the global Git LFS shim, which gates only LFS
object upload: no branch rule, no publish gate, no secret scan. `AgentlensPro` is in the
same state. That is the highest-value target here, and it spent an afternoon buried under
dozens of rows about repos that were none of our business.

**`AI-MAESTRO-WEBDESIGN-AGENT` is the in-scope DECORATIVE case:** it ships
`.githooks/pre-push` while `core.hooksPath` names `git-hooks` — one character apart, two
directories, **the reviewed file is not the executed file**, and nothing reports it. The
guard is present, reviewed, committed, and inert.

**A second state, SHADOWED:** a repo with `core.hooksPath` set AND a leftover
`.git/hooks/pre-push`. Git runs the former and ignores the latter — harmless to
execution, **actively misleading to inspection**, because anyone opening
`.git/hooks/pre-push` to learn "what runs" reads the wrong file. Four sessions made
exactly that mistake in one day, on this very subject.

**This repo was measured LIVE and clean** (`core.hooksPath=.githooks`,
`.git/hooks/pre-push` absent, so git executes the tracked file), which is precisely why
the gap is invisible from inside it: **a healthy repo looks identical to a broken one
until you ask what git actually resolves.**

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

## ⛔ SCOPE — owner directive 2026-08-22, and it invalidated every census below

> **"stop messing with projects that are not ai-maestro plugins or dependency plugins
> (cpv, pss, llm-externalizer, etc.) or dependency tools (agentlenspro)"** — USER,
> relayed by the hub session.
>
> Every census recorded further down swept **~152 git repos under `~/Code`**, the owner's
> unrelated private projects included. Reads only, nothing modified — but the wrong
> population, widened four times in an hour, each widening chasing a measurement error
> and none of them pausing to ask whether the wider set was ours to audit.
> **Correcting an instrument is not a licence to enlarge its scope.**
>
> **WITHDRAWN — do not encode, do not cite:** the three "genuinely unprotected" repos,
> the 39/48 and 46/48 ratios, the 9-repo hook-type matrix, and the "five sixths of this
> machine" framing. The alarming half of that finding was about the owner's private work.

### What survives, re-scoped to the ecosystem

| state | count |
|---|---|
| own pre-push guard | 16 (ai-maestro, ai-maestro-plugin, the janitor, the 8 role-plugins, assistant-role, web-scenario-tester, WEBDESIGN, perfect-skill-suggester) |
| **inherits the LFS shim — NO push-policy gate** | **2** — **`ai-maestro-plugins` (the MARKETPLACE)** and `AgentlensPro` |
| not resolvable at a depth-3 path | 4 |

**THE FINDING WORTH THE WHOLE THREAD: `ai-maestro-plugins` — the marketplace every agent
installs from — has no push-policy gate.** It dispatches the global LFS shim. Highest-
value target in the ecosystem, and 46 irrelevant rows had buried it.

`AI-MAESTRO-WEBDESIGN-AGENT` remains the in-scope DECORATIVE case: ships
`.githooks/pre-push` while `hooksPath=git-hooks` — the reviewed file is not the executed
one.

### Scope rule for the implementation

Membership comes from the **SSOT** (`lib/ecosystem-constants.ts` + the CLAUDE.md repo
table + the named dependency tools), never from a directory glob. A guardian that walks
`~/Code/*` audits the owner's private work — that is the defect this directive names.

And `~/Code/*/` is **depth 1** while in-scope repos nest deeper (e.g.
`~/Code/EMASOFT-ASSISTANT-MANAGER/ai-maestro-assistant-manager-agent`), so the same
sweeps were **too wide and too narrow at once**. Resolve entrusted repos BY NAME from the
SSOT and `find` them at depth.

## Census — RETRACTED TWICE, kept only as a worked example of checks that measure nothing

**Every count in this section is out of scope per the directive above and must not be
cited.** It is retained solely for the classifier post-mortem, which is this card's
subject matter.

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
| ships a guard git never resolves — see the SPLIT below, do not cite as one number | 5 |

**DECORATIVE=5 IS A LOSSY HEADLINE; ENCODE THE SPLIT.** Counts get encoded, tables get
read, and folding these together files a protected repo beside unprotected ones:

| sub-state | count | meaning |
|---|---|---|
| genuinely unprotected | **3** | ships a guard, runs nothing that gates pushing |
| protected-but-unreviewable | **1** | runs a real 3285 B guard that is UNTRACKED — no PR can review it |
| reviewed-file-is-not-the-executed-file | **1** | ships `.githooks/pre-push`, `hooksPath=git-hooks` — two dirs, one reviewed, the other executed |

**46 of 48 repos execute a pre-push**, not the 6 the first table implied — anyone
reading "6 LIVE / 48" as coverage got the inverse of reality. The substantive point
survives all of it: for 39 of them the executed file is the stock LFS shim.

**Precise about what that shim does, because "gates nothing" was twice too strong.**
`git lfs pre-push` receives the ref range on stdin, uploads associated LFS objects, and
**ABORTS THE PUSH if that upload fails** — so it does gate pushing, on exactly one
condition. Correct form: **gates only LFS object upload; nothing about branch, ancestry,
or publish policy.** With nothing on this machine tracking LFS that condition cannot
arise, so the conclusion stands and only the absolute phrasing was wrong. Two rounds of
over-claiming here, both from reading the wrapper and not the wrappee.

**DECORATIVE rose to 5 only under PATH-AGNOSTIC discovery** (`git ls-files | grep -E
'(^|/)pre-push$'` instead of three assumed directory names). One repo ships at
`scripts/hooks/pre-push`; another ships `.githooks/pre-push` while `hooksPath=git-hooks`
— two directories, one reviewed, the other executed. **Any implementation here must
discover hook files, never assume where they live** — assuming the directory is how the
first count missed two.

**The states are NOT a partition.** A repo can be LIVE *and* SHADOWED at once, so report
per ARTIFACT and never classify a repo into one bucket.

## Fifth state — DEPRIVED. **SEVERITY WITHDRAWN. Do NOT ship this as breakage.**

> The hub withdrew the severity it attached to this state, and the settling measurement
> agrees: **all 9 repos with a local `core.hooksPath` track zero LFS content, and ZERO
> repos on this machine have a `filter=lfs` pattern at all.** The three "lost" hooks
> (`post-checkout`, `post-commit`, `post-merge`) are installed by `git lfs install` — they
> are plumbing that ships beside the `pre-push` shim, not anyone's policy. **No repo here
> lost anything.**
>
> The original claim measured *a file is not there now* and reported *"thereby REMOVED
> three hooks"* + *"silent breakage"* — causal claims about a transition nobody observed,
> carrying a harm nobody established. Shipped as a check, it would have flagged seven
> healthy repos forever, which is how a guardian gets muted.
>
> Also set aside on the way: `.git/lfs` EXISTS and even holds files in most repos —
> `cache`/`tmp` residue from `git lfs install`, not tracked content. **Directory existence
> is not usage**, the same proxy trap one more time.
>
> The state may stay in the model as an OBSERVATION. Its acceptance criterion is the
> matrix **AND** the usage signal, together, always.



`core.hooksPath` **replaces the entire hooks directory**; there is no per-hook fallback
to the global one. So a repo that sets it to ADD a push gate silently REMOVES every
other hook type the global dir was providing.

Measured here 2026-08-22:

```
.githooks/                -> pre-push                                    (1 file)
~/.config/git/hooks/      -> pre-push post-checkout post-commit post-merge
lost by overriding        -> post-checkout, post-commit, post-merge
```

**Benign in this repo, and that is MEASURED, not assumed** — zero `filter=lfs` patterns
in `.gitattributes` and zero `git lfs ls-files`, so the three lost hooks had nothing to
do. **Not benign in general**: an entrusted repo that DOES use LFS and sets a local
`hooksPath` loses checkout/commit/merge behaviour with no error and a `core.hooksPath`
that reads as correctly configured.

**A MISSING HOOK IS A LOSS ONLY WHERE THE HOOK HAD WORK.** This is the qualifier that
makes the state reportable rather than alarmist, and the hub's first DEPRIVED table
lacked it: it said 7 of 9 local-hooksPath repos "thereby REMOVED three unrelated hooks",
which imputes a regression nobody measured. What is actually established is only that
those repos **do not provide** the three non-push hooks the global dir provides — whether
any ever had or wanted them is unmeasured, and a repo that never touched LFS is missing
nothing. **The check must report the matrix AND the usage signal together**, or it files
a benign absence as breakage in every repo that never used the feature.

Two rows of that table were also wrong, from testing a hardcoded four-name list instead
of enumerating the directory: one repo reported as running "nothing" in fact runs a real
`pre-commit` (it has only `pre-push.sample`, which git never executes — "no push gate"
is the true finding, not "empty shell"), and another reported with two hooks actually
runs five.

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

- [ ] the repo set comes from the ECOSYSTEM SSOT, resolved BY NAME and found at depth —
      never `~/Code/*` or any directory glob. A glob is both too wide (it audits the
      owner's private projects, which the 2026-08-22 directive forbids) and too narrow
      (in-scope repos nest below depth 1)
- [ ] hook files are DISCOVERED (`git ls-files | grep -E '(^|/)pre-push$'`), never
      assumed to live in a known directory — assuming the dir is what undercounted
      DECORATIVE by two
- [ ] the resolved path comes from `git rev-parse --git-path hooks`, and the classifier
      NEVER string-concatenates it with the repo root (`core.hooksPath` is frequently
      absolute; concatenating yields a path that cannot exist, and every branch then
      reports "not live" for any input — the exact bug that produced the retracted table)
- [ ] the resolved hooks dir is ENUMERATED, never probed for a list of expected names:
      `find "$h" -maxdepth 1 -type f -perm -u+x ! -name '*.sample'`. Both filters are
      load-bearing and fail in OPPOSITE directions — a name list misses every hook
      outside it (two rows of the retracted table), while an unfiltered executable count
      over-reports by 14 on any repo using its default `.git/hooks`, which ships 14
      executable `.sample` files
- [ ] a missing hook is reported as a LOSS only alongside a usage signal that the hook
      had work (e.g. LFS hooks against `filter=lfs` patterns and `git lfs ls-files`) —
      otherwise it is a benign absence, and reporting it as breakage trains the reader
      to ignore the check
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
