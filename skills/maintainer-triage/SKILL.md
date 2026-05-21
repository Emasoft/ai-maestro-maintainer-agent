---
description: |
  Use when maintainer-patrol surfaces a new open issue or the user
  wants to triage, classify, or decide what to do with a specific
  issue on the maintained repo. Classifies a GitHub issue against
  a flowchart (bug, feature or enhancement, duplicate, invalid or
  spam, needs-info) and returns a structured disposition the
  patrol skill records in the ledger. Enforces governance rule
  R19.6: feature requests and change proposals are accepted ONLY
  from the GitHub user authenticated with gh on the host (the
  authorized MAESTRO user); bug reports are welcomed from any
  author. Reads CLAUDE_EFFORT (Claude Code 2.1.133+) to scale
  verification depth — MEDIUM is the floor (LOW is intentionally
  promoted to MEDIUM because triage that skips code verification
  is unsafe), HIGH adds proactive grep before deciding, and MAX
  or XHIGH escalate to cross-file analysis for cross-module or
  self-contradicting issues. Honours the 2.1.116 rate-limit hint:
  if any gh call trips the rate-limit warning, returns a
  needs-info disposition with reason "rate-limit deferred" so the
  patrol skill does NOT mark the issue processed and re-picks it
  up next cycle with a fresh budget. Do NOT trigger on read-only
  "show me issue N" queries — those go straight to gh issue view.
  Trigger with phrases like "triage issue #N", "classify issue
  #N", or "decide what to do with issue #N".
---

# maintainer-triage — gatekeeper classification

## Overview

Evaluates each new GitHub issue against a classification
flowchart, enforces the authorized-user rule for feature
requests (R19.6), and returns a structured disposition with the
recommended action. Bugs from any author are welcomed; feature
requests are accepted only from the repository owner.

## Prerequisites

- `gh auth status` succeeds.
- `githubRepo` set on the calling agent.
- Issue number + basic metadata available (typically passed by
  `maintainer-patrol`).

Copy this checklist and track your progress (per-issue):

- [ ] Authorized user identified via `gh api user`
- [ ] Issue body read and classified
- [ ] Action determined (`fix` / `none`)
- [ ] GitHub labels updated
- [ ] Disposition returned to patrol

## Instructions

1. `AUTHORIZED_USER=$(gh api user --jq .login)` — the
   MAESTRO-privileged GitHub login (R19.6).
2. Set `$TRIAGE_DEPTH` from `$CLAUDE_EFFORT` (floor = `medium`,
   `MAX`/`XHIGH` → `max`). See
   [effort-scaling.md](references/effort-scaling.md).
3. Fetch metadata: `gh issue view <N> --repo <repo> --json
   title,body,author,labels`.
4. Classify against the flowchart. Verification depth scales:
   - `medium` — title + labels + body match; grep only if
     ambiguous.
   - `high` — also grep referenced symbols / files before
     deciding.
   - `max` — deep cross-file analysis (referenced symbols + their
     callers / imports) before deciding.
5. **Bug** (label `bug`, or title matches
   `bug`/`error`/`crash`/`fix`): verify, label, return
   `action: fix` or `needs-info`.
6. **Feature / change** (label `feature`/`enhancement`, or title
   matches `feature`/`add`/`request`): check author against
   `$AUTHORIZED_USER`. Reject if mismatch (R19.6); accept if
   match.
7. **Duplicate**: link the original, label `duplicate`, close.
8. **Invalid / spam**: label `invalid`, close.
9. **Ambiguous**: read body carefully; at `high` or `max` depth,
   grep the codebase before deciding.
10. Return the structured disposition to the patrol skill.

Path-specific `gh` commands:
[classification-paths.md](references/classification-paths.md).

## Output

```json
{
  "issue": 42,
  "disposition": "triaged|rejected|duplicate|invalid|needs-info",
  "action": "fix|none",
  "reason": "<brief explanation>"
}
```

The patrol skill records this in the ledger. If `action: fix`,
patrol invokes **maintainer-fix** next.

## Error Handling

| Error | Action |
|-------|--------|
| `gh api user` fails | Stop, report auth failure |
| Issue not found | Return disposition `invalid`, log error |
| Cannot read repo tree | Skip code verification, triage on text only |
| Duplicate search fails | Skip duplicate check, continue |
| GitHub rate-limit hint | Return `needs-info / rate-limit deferred`, do NOT retry |

## Examples

Bug from any user:

```
Issue #42: "NullPointerException in auth module"
→ Bug; verify in code → label bug,verified
→ {disposition: "triaged", action: "fix"}
```

More examples (rejected feature, duplicate, invalid) and the
per-path `gh` commands:
[classification-paths.md](references/classification-paths.md).

## Resources

- [Classification paths](references/classification-paths.md):
  - Bug Path (any author)
  - Feature Path (AUTHORIZED USER ONLY)
  - Duplicate Path
  - Invalid Path
- [Effort scaling](references/effort-scaling.md):
  - Triage depth tiers
  - Reading $CLAUDE_EFFORT
  - Rate-limit handling
- GitHub CLI: <https://cli.github.com/manual/>
