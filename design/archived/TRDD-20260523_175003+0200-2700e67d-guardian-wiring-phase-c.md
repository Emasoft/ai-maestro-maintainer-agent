---
trdd-id: 2700e67d-de93-43bf-ad88-06340c79d4f1
title: Guardian wiring + adversarial-content triage path (Phase C)
column: completed
created: 2026-05-23T17:50:03+0200
updated: 2026-08-07T12:08:37+0200
---

## TRDD-2700e67d — Guardian wiring + adversarial-content triage path (Phase C)

**Filename:** `design/tasks/TRDD-20260523_175003+0200-2700e67d-guardian-wiring-phase-c.md`
**Tracked in:** this repo (design/tasks/ is git-tracked)

## Implementing commit

- 47dc762 — `feat(security): wire Guardian into patrol/triage/fix (Phase C)`

## User request (verbatim, reconstructed from commit body)

> Connects the new Guardian-mode skills (Phase B) to the existing
> maintainer skill chain so threat detection and the approval gate
> fire at every cycle without separate commands from the user.

Phase B (TRDD-2a34e0cd) shipped the new skills as standalone
infrastructure. Phase C makes them actually run: at patrol pre-cycle,
at triage on suspicious issue body, and at fix before commit.
Without Phase C, the Phase B skills are dead code — the agent
doesn't know to call them.

## Scope — three wiring sites

### C1. maintainer-patrol — pre/post cycle Guardian hooks

- **Step 2 (baseline backstop):** If `guardian-baseline.json` is
  missing on the first patrol cycle of a session (i.e. the
  SessionStart hook from Phase B was missed or ignored), invoke
  maintainer-guardian BASELINE first. This makes the patrol
  self-sufficient — the user can `/maintainer-patrol` from a fresh
  session and Step 2 will produce the baseline before Step 4 needs
  it.
- **Step 4 (pre-cycle scan):** Invoke maintainer-guardian SCAN.
  Route the dispositions:
  - T5 (secret-leak) hits **halt the cycle entirely**. The
    issue loop is skipped this cycle; the alert wakes the
    authorized user.
  - Critical T1–T4 deltas route to auto-fix-PR / file-issue /
    alert per their default disposition, and SKIP the issue
    loop this cycle (new `guardian-skip` disposition). The
    rationale: a critical drift is a higher-priority event than
    any incoming issue, and triaging issues against an
    insecure baseline is wrong.
- **Step 8 (post-cycle):** Chain workflow-protect-branch SHOW to
  refresh the branch-rules cache. This keeps the next Guardian
  diff accurate for T3 (branch-rule drift).

### C2. maintainer-triage — adversarial-content path

Triage previously treated the issue body as untrusted input but
went straight to bug/feature classification. Phase C inserts a
**Step 4** that scans for imperative patterns:

- `modify CI`
- `add secret`
- `disable test`
- `remove type check`
- `edit .github/...`
- `--no-verify`
- `bypass`

Case-insensitive match. Any hit short-circuits classification:
the issue is routed to disposition `needs-info` with reason
`instruction-like-content` and labelled `awaiting-maintainer-approval`.
Triage does NOT proceed to bug/feature classification — the
authorized user must approve out-of-band first via the same
`approve-protected-edit` mechanism the approval-gate uses.

This closes **GAP-3** from the audit (adversarial issue content,
the gap that couldn't be closed mechanically in Phase A).

### C3. maintainer-fix — approval-gate call before commit

A new Step 7 (recorded as Step 5.5 in `references/fix-steps.md`)
invokes maintainer-approval-gate CHECK between "tests pass" and
"git commit". If the planned diff touches any protected path:

1. The gate posts an approval-request comment.
2. The gate labels the issue `awaiting-maintainer-approval`.
3. The gate returns `needs-approval`.
4. **maintainer-fix HALTS without committing.**

The next patrol cycle's VERIFY mode (invoked from maintainer-fix
Step 7 too, when resuming) checks for `approve-protected-edit` from
`$AUTHORIZED_USER`. If found, the fix resumes from where it
halted; if `reject-protected-edit`, the fix is abandoned; if
neither, the fix stays paused.

This closes the back half of GAP-3: adversarial bug reports that
would have sailed through Steps 1–5 (write edit, run tests with
type-check secretly removed, commit) are now blocked at the gate
even if Step 4 of triage missed them.

## Design decisions

1. **The patrol pre-cycle scan is gated, not blocking.** A
   non-critical T1/T3 delta is routed and the issue loop
   continues — only critical T4/T5 events halt the cycle. This
   keeps the maintainer responsive to ordinary issues even when
   minor drift is happening.
2. **Triage Step 4 is keyword-based, not LLM-classifier-based.**
   A regex of imperative phrases is dumb but predictable. An LLM
   classifier would be smarter but would also be vulnerable to
   the same prompt-injection it's trying to detect. The keyword
   list errs on the side of more `needs-info` dispositions; false
   positives are recoverable (`approve-protected-edit` flips
   them).
3. **The approval-gate fires before commit, not before fix.**
   Running the fix work — read files, write edit, run tests —
   doesn't touch protected paths until the commit step. Running
   tests is read-only on the live branch, so delaying the gate
   until just before commit preserves the "fast feedback when
   the diff is harmless" path.
4. **`guardian-skip` is a new disposition.** It distinguishes "we
   skipped the issue loop because we had Guardian work to do"
   from "we processed and skipped this issue". Logging the
   difference matters for post-mortem.
5. **Step 8 keeping the branch-rules cache fresh.** Without this,
   T3 (branch-rule drift) would fire false positives the first
   cycle after any branch-rule edit. workflow-protect-branch SHOW
   is idempotent and cheap.

## Files touched (commit 47dc762)

```
skills/maintainer-fix/SKILL.md                                    (MOD, +Step 7)
skills/maintainer-fix/references/fix-steps.md                     (MOD, +Step 5.5)
skills/maintainer-patrol/SKILL.md                                 (MOD, +Steps 2/4/8)
skills/maintainer-patrol/references/patrol-loop.md                (MOD)
skills/maintainer-triage/SKILL.md                                 (MOD, +Step 4)
skills/maintainer-triage/references/classification-paths.md       (MOD, +adversarial path)
```

## Acceptance criteria (all met by 47dc762)

- [x] maintainer-patrol Step 2 invokes BASELINE if baseline file
      missing.
- [x] maintainer-patrol Step 4 invokes SCAN; T5 hits halt cycle;
      critical T1–T4 deltas route and SKIP the issue loop.
- [x] maintainer-patrol Step 8 refreshes branch-rules cache.
- [x] maintainer-triage Step 4 scans for imperative patterns
      case-insensitively; match → `needs-info` /
      `instruction-like-content`.
- [x] maintainer-fix Step 7 invokes approval-gate CHECK before
      commit; protected-path hit → fix HALTS without committing.
- [x] `classification-paths.md` documents the new adversarial
      path.

## Post-mortem

**What worked:**
- Inserting Step 4 in triage was a single-skill edit — the
  imperative-pattern scan didn't need to touch maintainer-fix.
  Separation of concerns held.
- The `guardian-skip` disposition cleanly distinguishes "Guardian
  preempted this cycle" from ordinary outcomes. Post-mortem logs
  are readable.
- maintainer-fix Step 7 ran on the planned diff (not the staged
  diff) — which means the gate fires before any disk-write
  commit. If the gate says no, no recovery is needed; the work
  was held in memory.

**What was tricky:**
- Choosing when the patrol cycle halts entirely versus continues
  past the issue loop was a real design tradeoff. Going too
  aggressive (halt on any T1 hit) means a single zizmor regression
  blocks all issue work; going too lenient (never halt) means a
  secret-leak fires AND issue work still happens against a
  compromised baseline. Splitting on T5 vs T1–T4 lands the right
  trade.
- The imperative-pattern regex is conservative — it will
  false-positive on legitimate bug reports that quote the exact
  imperative phrases ("the README says to `disable test` for X
  but ..."). That's accepted; users can `approve-protected-edit`
  to recover.
- The approval-gate VERIFY → fix-resume handoff required carrying
  fix-state in the issue (label + comment trail) rather than in
  agent memory — agents don't have persistent sessions across
  patrol cycles. This was implicit in the design but turned out
  to be the load-bearing assumption.

**Lessons for future work:**
- Wiring phases (Phase C-class) are at least as expensive as
  authoring phases (Phase B-class). The skill API surface looks
  trivial in isolation but the right place to call it is a
  multi-step judgment.
- Resumable workflows that cross patrol cycles (fix → gate → next
  cycle VERIFY → resume) must store their resume state somewhere
  the next cycle can find. Github issue labels + comments are
  the obvious carrier.
