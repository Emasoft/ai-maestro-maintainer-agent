---
trdd-id: M9FXC82B
title: Align shipped surfaces to Claude Code 2.1.232 and ban gitleaks
column: published
created: 2026-08-15T00:35:55+0200
updated: 2026-08-15T00:45:00+0200
current-owner: maintainer-session
task-type: docs
release-via: publish
approval-tier: 0
relevant-rules: [3, 5, 7]
implementation-commits: [5ad8d2e]
---

# Align shipped surfaces to Claude Code 2.1.232 and ban gitleaks

USER handed the Claude Code 2.1.221→2.1.232 changelog and asked for alignment;
mid-plan the USER also banned gitleaks outright (2026-08-14: single-threaded,
single-process, file-count capped — too slow to be useful).

## What shipped (all verified by the suite before commit)

1. **Persona transport note corrected** (`agents/…-main-agent.md`): the
   "nothing polices it" claim scoped to *no R6 enforcement point* (upstream's
   auto-mode classifier 2.1.222 + `crossSessionInbound` 2.1.224/2.1.232 gate
   USER CONSENT, never the comm graph); reach widened to cross-machine
   (2.1.225); "nothing queues them" replaced with the parked/held reality;
   bare-name addressing (2.1.232); "sub-agents inherit nothing" scoped to
   fresh spawns (a `subagent_type: "fork"` inherits the full conversation).
2. **Guard tests moved in lockstep** (`tests/test_persona_governance.py`):
   the 403 test now pins the *scoped* claim (old absolute wording explicitly
   rejected), inbound-channel test asserts cross-machine reach + parking, new
   test pins the fork-qualified inheritance sentence.
3. **Worktree skill pin** 2.1.221 → 2.1.232 with the 2.1.222 fact (isolation
   now covers file edits + Bash in every session type) in SKILL.md and
   references/instructions.md.
4. **Surface-compliance re-measure + re-pin** (`tests/test_claude_code_surface_compliance.py`):
   header re-measured against live CLI 2.1.233; one-positional + `_VALUE_FLAGS`
   re-confirmed; new `/ultrareview` detector (bite proven on a deliberate
   violation, never matches bare `/review`); new gitleaks-ban detector (bit on
   9 real files before the sweep).
5. **GitLab token families**: `scripts/security_catalog.json` +10 families
   (glrt gloas glptt glagent glimt glsoat glcbt glft glffct gldt; glpat
   widened to `{20,}` for CRC suffixes); `scripts/redact.py` redacts the two
   routable ones (glpat/gldt), mirroring upstream's split; sentinel port
   deliberately untouched (Ruby-mirror contract, commented). Tests with inert
   fixtures + negative prose controls.
6. **publish.py marketplace gate** recognises `archive` (slug-match) and
   treats `npm`/`command` as registered-but-unverifiable; unknown forms still
   refuse. Direct unit tests on the pure function.
7. **gitleaks ban executed**: every reference removed from shipped surfaces +
   `.mega-linter.yml` (comment now attributes the TruffleHog coverage to CPV,
   correcting the false "publish.py's TruffleHog gate" claim); fallback chain
   is trufflehog → bundled `fast_security_scan.py`; USER-scope wikimem page
   `secret-scanner-selection` records the ban (memgrep-authored, validate+lint
   clean). `design/archived/` kept as historical record, per the compliance
   file's own scope rule.

## Pass criteria

- [x] Full suite green (`tests/run-all-tests.py` exit 0)
- [x] CPV `--strict` → CRITICAL=0 MAJOR=0 MINOR=0 NIT=0
- [x] Both new detectors proven to bite, then green after the fix
- [x] memgrep validate + lint clean on the new USER page

## Approval log

- 2026-08-15T00:45:00+0200 — PUBLISHED as v1.13.8 (release
  <https://github.com/Emasoft/ai-maestro-maintainer-agent/releases/tag/v1.13.8>,
  commit 5ad8d2e + publish bump 519f79e). Tier-0 work; the release itself was
  USER-approved this session ("Commit + publish a release"). Closed same-session
  per the drain rule.
