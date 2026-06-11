---
trdd-id: 5307ae6c-9ef1-4d0e-aeb8-13dbef04cd5e
title: workflow-protect-branch must emit the two-ruleset split, not one bypass-less required-checks ruleset
column: complete
created: 2026-06-01T05:08:23+0200
updated: 2026-06-11T11:13:41+0200
---

<!-- markdownlint-disable MD025 -->

# TRDD-5307ae6c — workflow-protect-branch two-ruleset split

**Filename:** `design/tasks/TRDD-20260601_050823+0200-5307ae6c-protect-branch-two-ruleset.md`
**Tracked in:** this repo (design/tasks/ is git-tracked)

## Problem

`skills/workflow-protect-branch` (and the `workflow-bootstrap` template it
feeds) applies a SINGLE GitHub ruleset named `default-branch-ruleset` that
combines `required_status_checks` + `non_fast_forward` + `deletion` with
NO `bypass_actors`. On any repo that publishes via a **direct push to the
default branch** (the canonical publish.py model — Gate-0 pre-push hook,
no PR), this reproduces the `GH013` block: required checks can only go
green AFTER a push, so a direct push can never satisfy
"N of N required status checks are expected" → rejection.

This was hit live on 2026-05-29 during the v1.3.1 publish of THIS repo.
The fix that unblocked it (verified working, live as of this TRDD) was to
SPLIT the protection into two rulesets on `~DEFAULT_BRANCH`:

| Ruleset | rules | `bypass_actors` | Effect |
|---|---|---|---|
| `default-branch-no-force-no-delete` | `[non_fast_forward, deletion]` | `[]` | force-push + branch-deletion blocked for EVERYONE incl. admin |
| `default-branch-required-checks` | `[required_status_checks]` (strict) | `[{actor_id:5, actor_type:"RepositoryRole", bypass_mode:"always"}]` | admin (publish.py) bypasses ONLY the checks; outside-contributor PRs stay gated |

**Critical gotcha (root cause of why one ruleset can't work):** a ruleset's
`bypass_actors` applies to the ENTIRE ruleset, not per-rule. Putting an
admin bypass on the single combined ruleset would ALSO let admin
force-push and delete `main` — a wider hole than intended. The only way to
get "admin bypasses checks but NOBODY bypasses force-push/deletion" is two
rulesets.

The skill is the MAINTAINER agent's capability applied to every entrusted
downstream repo, so the bug ships to all of them. The bootstrap template
seeds the same broken JSON into every new repo.

See memory `branch-protection-required-checks-blocks-direct-push` and
`~/.claude/rules/...` (the original incident).

## Live reference bodies (mirror these exactly — idempotent target)

Ruleset A — `default-branch-no-force-no-delete`:
```json
{"name":"default-branch-no-force-no-delete","target":"branch","enforcement":"active",
 "conditions":{"ref_name":{"include":["~DEFAULT_BRANCH"],"exclude":[]}},
 "rules":[{"type":"non_fast_forward"},{"type":"deletion"}],
 "bypass_actors":[]}
```

Ruleset B — `default-branch-required-checks`:
```json
{"name":"default-branch-required-checks","target":"branch","enforcement":"active",
 "conditions":{"ref_name":{"include":["~DEFAULT_BRANCH"],"exclude":[]}},
 "rules":[{"type":"required_status_checks","parameters":{
   "strict_required_status_checks_policy":true,
   "required_status_checks":<CHECKS_JSON>}}],
 "bypass_actors":[{"actor_id":5,"actor_type":"RepositoryRole","bypass_mode":"always"}]}
```

`actor_id:5` = built-in **Admin** RepositoryRole (GitHub accepts it; verify
via readback). User repos have no OrganizationAdmin and no per-user bypass
actor, so RepositoryRole(Admin) is the correct actor.

## Phases (each ≤ 5 files, verify between)

### Phase 1 — the skill itself (AUTHORIZED, doing now)
- `skills/workflow-protect-branch/SKILL.md` — Overview/Instructions/Scope
  describe TWO rulesets; APPLY POST/PUTs both by name; SHOW caches the
  array (already does). Keep ≤ 5000 chars, all 6 Nixtla sections,
  flow-style, no `${{ }}`.
- `skills/workflow-protect-branch/references/instructions.md` — Step 3
  builds TWO JSON bodies; Step 4 discovers BOTH ids by name; Step 5
  POST/PUTs each; Step 6 verifies both present; dispositions list both
  ruleset ids. Add a "Why two rulesets" rationale box citing the
  whole-ruleset bypass_actors gotcha.

### Phase 2 (DERIVED) — bootstrap template + its instructions — DONE (commit pending)
- `skills/workflow-bootstrap/references/templates/ruleset.json` → split
  into `ruleset-no-force-no-delete.json` + `ruleset-required-checks.json`
  (or one file holding an array of two). Whichever shape, bootstrap's
  Step 5 + "Post-merge ruleset apply" must stash + POST BOTH.
- `skills/workflow-bootstrap/references/instructions.md` — template
  inventory row, Step 5 stash, post-merge apply prose.
- `skills/workflow-bootstrap/SKILL.md` — template-inventory mention.

### Phase 3 (DERIVED) — prose that names the single ruleset — DONE (commit pending)
- `commands/maintainer-protect-branch.md` — "default-branch-ruleset
  exists yet" → two-ruleset language.
- `commands/maintainer-detect-stack.md`, `commands/maintainer-guardian-baseline.md`
  — T3 "current default-branch-ruleset" → "current default-branch
  ruleset(s)".
- `skills/maintainer-guardian/references/threat-classes.md` — T3 baseline
  shape already says "ruleset(s)" in prose; confirm the JSON example
  doesn't hard-assume a single id (it uses `ruleset_id` singular — may
  widen to a list, or leave as illustrative).

### Phase 4 (DERIVED) — verify
- Frontmatter YAML parses; SKILL.md ≤ 5000 chars; "Trigger with" +
  "Use when"/triggers present; 6 sections; no `${{ }}` in snippets.
- `git grep "default-branch-ruleset"` returns ONLY intentional
  historical references (none should imply it's the live name).
- CPV strict on the plugin → CRITICAL=0 MAJOR=0.
- Idempotency check: the rewritten Step-3/4/5 against THIS repo's live
  topology is a no-op (both rulesets already exist with these exact
  bodies) — must not regress 17025842's bypass_actors or split.

## Acceptance criteria

- Running APPLY on a fresh direct-push repo produces BOTH rulesets and a
  subsequent `publish.py` direct push succeeds (admin bypasses checks,
  force-push/deletion stay blocked for all).
- Running APPLY on THIS repo is a verified no-op (converges to the live
  two-ruleset state).
- No tracked file implies `default-branch-ruleset` (singular combined) is
  the applied topology.

## Out of scope

- Changing publish.py / cpv-setup-branch-rules (that's CPV's surface; this
  TRDD is the maintainer plugin's own skill).
- Per-author bypass actors (covered by TRDD-d4112f1e).
- The CC-2.1.158 alignment pass (separate backlog item).
