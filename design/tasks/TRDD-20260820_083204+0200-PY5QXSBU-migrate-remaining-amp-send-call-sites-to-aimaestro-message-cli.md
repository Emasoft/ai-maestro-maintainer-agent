---
trdd-id: PY5QXSBU
title: Migrate the 5 remaining amp-send call sites to the aimaestro-message CLI
column: ai_review
created: 2026-08-20T08:32:04+0200
updated: 2026-08-21T22:26:38+0200
current-owner: maintainer-agent-session
task-type: docs
min-approval-requirement: none
---

# Migrate the 5 remaining amp-send call sites to the aimaestro-message CLI

`aimaestro-message.sh` v1.0.0 shipped (hub TRDD-0AB76JG3, 2026-08-20) to the
maintainer's exact contract; `approval-request.md` already migrated (00a4499).
Hub-agreed plan: fold the rest into the next release cycle, keeping the
CLI-primary / `amp-send`-fallback pattern so the shipped prose is correct on
hosts in EITHER deploy state (future hosts install the plugin before the
server's CLI layer necessarily lands).

## Call sites (grep-verified 2026-08-20)

- `skills/maintainer-guardian/SKILL.md:31,33,103` (T5 escalation)
- `skills/maintainer-guardian/references/threat-classes.md:300,315`
- `skills/maintainer-prrd-trdd-kanban/SKILL.md:32,59,95`

## Acceptance

- [x] every site names `aimaestro-message.sh send` as primary (exit codes: 3
      transport / 4 not-found / 5 ambiguous / 6 R6-refused-follow-hint / 7 auth;
      never `--from` as an agent) with `amp-send` as the explicit degrade path
- [x] `grep -rn 'amp-send' skills/ agents/` shows only fallback-labelled uses
- [ ] rides a release (publish.py) — **DEFERRED, not forgotten.** Two reasons,
      both external to this card: (a) publish is NON-EXEMPT and needs the USER,
      and the peer hub explicitly has no governance title over this repo to grant
      it; (b) the host is at **99% disk / 25 GB free** (measured 2026-08-21
      16:41) and a build+test+publish there risks a corrupt release and a
      half-written index. Land the release on the next cycle, after the disk is
      reclaimed.

Pattern to copy: `skills/maintainer-approval-gate/references/approval-request.md`.

## Scope correction (2026-08-21)

The card listed 3 files / 8 sites, but **acceptance box 2 is a whole-tree grep**,
and 4 more files named `amp-send` as the sole, unlabelled transport. Patching only
the listed 3 would have left every sibling caller wrong while the grep still
passed by accident. Also migrated: `skills/maintainer-patrol/SKILL.md`,
`skills/maintainer-patrol/references/handoff.md`,
`skills/maintainer-approval-gate/SKILL.md`,
`agents/ai-maestro-maintainer-agent-main-agent.md` (2 sites, ordering only).
Final state: 17/17 `amp-send` occurrences are fallback-labelled.

The exit-code contract is stated ONCE per file and otherwise linked to
`approval-request.md`, which owns it — 8 verbatim copies of a 5-line table is 8
things to drift.

## AI review — 2026-08-21

**VERDICT: PASS.** Both work boxes verified independently; the release box is
genuinely outstanding, not a hidden completion.

| Box | Evidence checked | Result |
|---|---|---|
| every site names the CLI as primary, `amp-send` as explicit degrade | re-grepped the whole tree, not the 3 files the card originally listed | ok |
| `grep -rn 'amp-send' skills/ agents/` shows only fallback-labelled uses | **17 hits, 17 labelled, 0 bare** — matches the card's claim exactly | ok |
| rides a release (publish.py) | untickable here — NON-EXEMPT, needs the USER | correctly left unticked |

**A false positive worth recording, because it is this card's own subject matter.**
A first pass filtering hits by "does the line contain fallback/legacy/degrade" flagged
**7 of 17 as unlabelled**. All 7 were wrong: the label sits on the *preceding* line,
because the sentence wraps —

```
   (fallback where the CLI is absent:
   `amp-send "$MANAGER" ... --type alert`).
```

A line-scoped filter cannot see a line-wrapped label, so it reports the documentation
*about* the fallback as an unlabelled use of it. Same class as the detector-validity
lesson: a keyword needle cannot tell USE from MENTION, and reading the context — not
tightening the pattern — is what resolved it. Recorded here so the next reviewer of
this card does not re-derive the same 7 ghosts.

**Scope correction upheld.** Patching only the 3 originally-listed files would have
left 4 sibling callers wrong while box 2's whole-tree grep passed by accident. The
widened fix is the correct one.
