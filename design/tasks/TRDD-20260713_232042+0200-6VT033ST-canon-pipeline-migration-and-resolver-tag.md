---
trdd-id: 6VT033ST
title: Canon pipeline migration (ai-maestro #44) plus the plugin-dependency resolver tag
column: published
created: 2026-07-13T23:20:42+0200
updated: 2026-07-14T17:42:00+0200
current-owner: ai-maestro-maintainer-agent
task-type: infra
release-via: publish
relevant-rules: [1]
implementation-commits: [42a27ba, fd5882f, dac01f8, 5a25695]
released-version: 1.7.10
---

# Canon pipeline migration (ai-maestro #44) plus the plugin-dependency resolver tag

## ⏵ STATE — READ THIS FIRST ON RESUME (authoritative; supersedes the body) — 2026-07-14

**Where it stands: SHIPPED. `v1.7.10`, commit `5a25695`, released 2026-07-14 (USER-authorized).**
All three workflows green (CI · Release · Notify Marketplace). This TRDD is `published` — do not
edit the body; new work = new TRDD.

| Component | State |
|---|---|
| `scripts/publish.py` | SHIPPED — `get_plugin_name()` (`:289`) + resolver tag (`:1627`); both tags in ONE `--atomic` push (`:1656`) |
| `tests/test_publish_resolver_tag.py` | SHIPPED — 10 real tests (no mocks); suite 568/568 |
| `skills/the-skills-menu/SKILL.md` | SHIPPED — hand-written (canon's generated one is broken); 0 lint errors |
| `agents/…-main-agent.md` | SHIPPED — preloads only the catalog; 28 skills now load on demand |
| `.commitlintrc.json` | SHIPPED — adopted (inert: commitlint is not in `ENABLE_LINTERS`) |
| Canon regressions | REJECTED (4) — see the table below |
| Both tags on `origin` | `v1.7.10` and `ai-maestro-maintainer-agent--v1.7.10` → same commit `5a25695` |
| GitHub writes | DONE — ai-maestro **#44** fleet row · this repo's **#28** (answered + CLOSED) · **#29-Q1** |

**OPEN FOLLOW-UP (the only one) — CPV is now AHEAD of our pin.** CPV **v2.158.0** shipped in
response to our `claude-plugins-validation#165`: `standardize --fix` now injects the
resolver-tag stage into an EXISTING `publish.py`, and `--force-templates` now MERGES config
files instead of clobbering them. **Our CI still pins `v2.152.1`**
(`.github/workflows/ci.yml:154`, `release.yml:50`). Next step, as its own TRDD: bump the pin and
re-run `standardize --fix` against v2.158.0 to confirm its migration is a **no-op** against our
hand-rolled stage rather than a duplicate. Two of the four rejections below may become adoptable
once merge-not-replace is real — **re-extract before believing that.**

**SUPERSEDED — do NOT carry forward:**

- "Committed, not released / do NOT push." **Released** 2026-07-14 with explicit USER
  authorization. `main` is level with `origin/main`.
- The 2026-07-10 canon diff in `[[project_cpv_pipeline_drift_do_not_standardize]]` (it
  predicted `publish.py` would gain G2c/G2d gates). **Wrong.** Canon v2.157.2 left
  `publish.py` entirely alone — CPV #145's profile-awareness works.
- The ai-maestro #44 thread's "apply these 4 canon-CI fixes by hand" recipe. **All four are
  fixed** (CPV #142 CLOSED 2026-06-21). Verified, not assumed.
- The framing that plugins simply "forgot" the resolver-tag stage. CPV confirmed the real
  cause: `standardize` REFUSED to touch an existing `publish.py`, so every plugin that had one
  was standardized without ever gaining the stage — and was told it succeeded.

## Why

ai-maestro **#44** carries a USER→MANAGER directive (2026-06-20): *"Make sure you make all
plugins update their publish pipeline using the CPV upgrade agent."* This plugin's fleet row
(2026-06-21) DEFERRED pending CPV #145.

**The deferral condition is met.** #118 closed 2026-06-16; #145 closed 2026-06-21 (v2.140.0).
Both were re-verified by `gh issue view`, not from memory — the failure mode this TRDD exists
to avoid is precisely a deferral that silently expired.

Bundled by USER decision: **#28 / #29-Q1 (TRDD-JT3U4ZVM)** — the `{name}--v{version}` resolver
tag. It touches the same file and is owed.

## What was actually done

### The extraction (never trust a stale diff)

`git archive HEAD` → throwaway copy → `cpv-remote-validate standardize . --fix
--force-templates` **inside the throwaway only** → `diff -ru` vs a pristine HEAD export. The
live tree was never touched by canon. This is the discipline `[^1]` of the memory note.

### ADOPTED

| Item | Note |
|---|---|
| `skills/the-skills-menu/` | Hand-written. Canon's **generated** one is broken — 21/28 rows had empty descriptions and were malformed 4-cell rows in a 3-column table → **21× MD056**, which would have blocked our own `--strict`. |
| main-agent persona | Preload only the catalog. 28 skills × every turn → 1 catalog. Dropping a skill from `skills:` makes it **lazy, not unavailable**. |
| `.commitlintrc.json` | Safe: `ENABLE_LINTERS` is an explicit allowlist and contains no commitlint. |
| **Resolver tag** (not from canon — canon lacks it) | `{plugin-name}--v{version}`, pushed in the SAME `--atomic` transaction as `v{version}`. |

### REJECTED — every one of these regresses a currently-green build

| Canon change | Why rejected |
|---|---|
| `.markdownlint.json` | Strips `MD010: {code_blocks: false}` → the `maintainer-shell-audit` skill's **Makefile** examples (which require literal tabs) fail lint. |
| `.mega-linter.yml` | Strips `CKV_DOCKER_2` **and its 8-line rationale** → CI Lint fails on `scripts/sandbox/dockerfiles/*`. Shipped deliberately in v1.7.2. |
| `.cspell.json` | Canon ships it with **no project dictionary**: 527 unknown words repo-wide (incl. security-test fixtures like `AKIAEXAMPLEKEY`). `SPELL_CSPELL` is live in our MegaLinter → instant red CI. |
| `git-hooks/pre-push` | Strips the TRDD-b8f4a7c2 NOTE. The file is **inactive** anyway — `core.hooksPath=.githooks`, and the ACTIVE `.githooks/pre-push` was **untouched** by canon. |

### Untouched by canon (confirmed, not assumed)

`scripts/publish.py` · `.githooks/pre-push` (the ACTIVE guard) · `.github/**`. The whole
`.github/**` protected path is therefore out of the blast radius.

## The resolver tag — why it is not optional

Since Claude Code **2.1.110**, a version-constrained plugin dependency resolves **only**
against tags named `{plugin-name}--v{version}`. A repo tagged only `v{version}` looks to the
resolver like a repo with **no tags at all** — every constrained dependency fails with "no git
tag satisfying `<range>`" while `git ls-remote --tags` plainly lists them. This grounded the
entire ai-maestro fleet for a day.

Both tags ship, and they are not redundant:

- `v{version}` → GitHub Releases + the marketplace notify chain
- `{plugin-name}--v{version}` → the **only** tag the dependency resolver reads

They are created together and pushed in **one** `--atomic` transaction, so a release can never
land half-tagged.

`claude plugin tag <name>` is **not** usable: its positional arg is a **PATH**, not a tag name
— called that way it silently creates nothing.

## Verification (the gate that actually predicts CI)

A green local dry-run does **not** predict green CI. Run the exact CI command:

```
CLAUDE_PRIVATE_USERNAMES=runner uvx --from git+https://github.com/Emasoft/claude-plugins-validation@v2.152.1 --with pyyaml cpv-remote-validate plugin . --strict
```

Require `CRITICAL=0 MAJOR=0 MINOR=0 NIT=0`. Plus: full test suite, `publish.py --patch
--dry-run`, and assert `.githooks/pre-push` is byte-identical to HEAD (the push-path invariant
must not move).

## Open follow-ups (NOT part of this TRDD's code)

1. **Backfill.** Existing releases have no resolver tag; only future ones will. A one-off
   backfill of the current version may be wanted so this plugin is resolvable *now* — that is
   a tag push, so it needs release authorization.
2. **Persona behaviour change** — lazy skill loading should be exercised when the MAINTAINER
   agent is actually stood up (ai-maestro #27's B1/B2 rows).
3. **CPV #165** — if CPV ships the resolver tag in canon, our hand-rolled step converges with
   it; if CPV makes suppressions MERGE-not-REPLACE, the 4 rejections above become adoptable.
4. **#44 fleet row + #28/#29 replies** — GitHub writes, only after a release lands.

## Notes and lessons learned

[^1]: [ocd:2026-07-13 lmd:2026-07-13] The memory note's own `[^3]` lesson said a deferral on an
  external condition ("wait for issue #N") is a time-bomb that silently expires. It was right:
  the 2026-07-10 diff it recorded was *already stale* three days later — canon had moved and no
  longer touched `publish.py` at all. Lesson: a canon/tool diff is evidence with a **shelf
  life**. Re-extract it against the live tool version at the moment you act; never plan from a
  recorded diff, however recently it was taken.

[^2]: [ocd:2026-07-13 lmd:2026-07-13] Canon's own `standardize` output **fails canon's own
  `--strict` gate** (21× MD056 from the generated `the-skills-menu`). Lesson: a generator's
  output is not pre-validated just because the generator is canonical. Lint anything a tool
  writes into your tree before you commit it — *especially* when the tool and the gate ship
  from the same vendor, because that is exactly the case where you assume it must already pass.

[^3]: [ocd:2026-07-13 lmd:2026-07-13] The root cause of the broken generator is a
  single-line regex on `description:` where a YAML parse was needed: 21 of our skills use the
  `description: |` block-scalar form and all 21 came out empty. Lesson: never regex a line out
  of YAML. Reported as `claude-plugins-validation#165`.

[^4]: [ocd:2026-07-14 lmd:2026-07-14] PARTIAL CORRECTION of my own `#165` Ask 2. I reported
  "canon's `publish.py` never creates the `{name}--v{version}` resolver tag". CPV's maintainer
  corrected it, and the true shape is **narrower and worse**: the *generator* had minted the tag
  correctly since v2.156.0 — but `standardize` is profile-aware and **deliberately refuses to
  overwrite an existing `publish.py`**, so every plugin that already had one (i.e. all of them)
  was standardized **without ever gaining the stage**, and was reported as succeeding. Fixed in
  v2.158.0 by a surgical injection under a plain `--fix`.
  **Lesson: I diagnosed from the ARTIFACT I could see (the template) instead of the CODE PATH
  that produces it.** Reading canon's generated `publish.py` template shows the tag missing —
  true, but it is not why *my* file lacked it, and the difference decides who is affected. "The
  template lacks X" and "the tool never gives you X" are different claims; only the second was
  actionable, and I could only have distinguished them by reading the standardizer's
  refuse-to-overwrite branch. When reporting a tool bug, trace the path from tool to *your*
  file — never infer the mechanism from the output alone. The over-broad report still got the
  fix shipped, but a fleet reading it would have concluded "canon can't do this" when the truth
  was "canon silently skipped you", which is the more urgent alarm.
