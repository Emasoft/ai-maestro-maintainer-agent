---
trdd-id: HDO00XSF
title: This repo ships the 17-column kanban vocabulary that 3-pillars 3.0.0 replaced with 22
column: backburner
created: 2026-08-23T16:29:29+0200
updated: 2026-08-23T16:29:29+0200
current-owner: ai-maestro-maintainer-agent
task-type: docs
approval-tier: 2
scope: project
---

# This repo ships the 17-column kanban vocabulary that 3-pillars 3.0.0 replaced with 22

## Why this is intake only

A peer session (`ai-maestro-b9`) notified this session on 2026-08-23 that the USER
ratified **3-pillars spec 3.0.0**, widening the kanban vocabulary from 17 to 22
board columns. The peer was explicit that the artifacts live in
**Emasoft/ai-maestro, branch `governance-rules`**, and that 3.0.0 binds this repo
only once it arrives here as a real artifact. It has not.

So this card records a **measured drift**, not an authorized edit. A peer cannot
authorize a governance change (approval-tier 2: this repo's shipped persona is the
governance text every entrusted downstream repo inherits). Do not act on it until
the spec lands here or the USER says so.

## What was measured (this repo, 2026-08-23)

`grep` for the vocabulary across live artifacts — archived TRDDs excluded, they are
frozen historical record and correctly still say 17:

| file | sites | what it is |
|---|---|---|
| `tests/test_persona_governance.py` | 7 | the parametrized gate that asserts the 17 columns one-per-column |
| `agents/ai-maestro-maintainer-agent-main-agent.md` | 5 | the SHIPPED persona — `### The board: exactly 17 columns` at :469 |
| `skills/maintainer-trdd-adr/references/trdd-template.md` | 3 | lifecycle order handed to every authored TRDD |
| `skills/maintainer-trdd-adr/references/seed-readmes.md` | 3 | lifecycle order seeded into new repos' `design/` READMEs |
| `design/tasks/README.md` | 3 | this repo's own board legend |
| `skills/the-skills-menu/SKILL.md` | 1 | menu row 17 names "17-column kanban" |

## The claimed 3.0.0 vocabulary (peer's words, NOT verified against an artifact)

```
backburner, approval, design, design_ai_review, design_human_review, todo,
verify_assumptions, plan, dispatch, dev, testing, ai_review, human_review,
complete, publish, published, deploy, live, live_auditing
+ blocked, failed, superseded
```

Five new; `design` MOVED to before `todo`; nothing removed; snake_case. Legal
`column:` set claimed to be 27 — the 5 bracket values (`proposal`, `planned`,
`refused`, `completed`, `cancelled`) unchanged and outside the board.

**Verify this list against the real artifact before writing a single character of
it into this repo.** It is currently hearsay relayed through a socket.

## The one genuinely reassuring finding

`tests/test_persona_governance.py` is a REAL gate, not a decorative one. It names
each column individually, so the day 3.0.0 lands here the test fails loudly rather
than letting the persona drift silently. That is the opposite of the usual
stale-prose hazard the peer warned about — here the prose IS covered.

The uncovered sites are the three skill/reference files and the two READMEs.

## Do NOT

- Edit `~/.claude/rules/universal-kanban.md`. It is janitor-shipped, still says 17,
  and the peer flagged it as stale-not-authoritative. It is not this repo's to fix.
- Touch the ratified GitHub branch-ruleset baseline. The peer confirmed 3.0.0 does
  not change `baseline-history-protect` / `baseline-pr-and-checks` /
  `baseline-tag-protect`, and this repo's memory already records that slice as done.
- Re-evaluate non-archived cards. The USER's mandate to do that was issued about
  ai-maestro's corpus and does not cross the repo boundary.

## Next action when authorized

1. Read the real 3.0.0 artifact from `Emasoft/ai-maestro@governance-rules` — do not
   trust the list above.
2. Update the 6 live files in one batch, persona first.
3. Update `tests/test_persona_governance.py` in the SAME change — a vocabulary edit
   that leaves the test on 17 is a red suite, and a test edit that lands without the
   persona edit is a gate pointed at nothing.
4. Delivery requires a `publish.py` release (the pre-push hook refuses every other
   push), which is NON-EXEMPT and needs USER authorization separately.

## Approval log
