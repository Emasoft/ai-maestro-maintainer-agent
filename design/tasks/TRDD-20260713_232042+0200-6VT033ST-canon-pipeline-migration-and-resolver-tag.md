---
trdd-id: 6VT033ST
title: Canon pipeline migration (ai-maestro #44) plus the plugin-dependency resolver tag
column: dev
created: 2026-07-13T23:20:42+0200
updated: 2026-07-13T23:20:42+0200
current-owner: ai-maestro-maintainer-agent
task-type: infra
release-via: publish
relevant-rules: [1]
---

# Canon pipeline migration (ai-maestro #44) plus the plugin-dependency resolver tag

## ⏵ STATE — READ THIS FIRST ON RESUME (authoritative; supersedes the body) — 2026-07-13

**Where it stands:** code COMPLETE and locally verified. NOT pushed. NOT released.

| Component | State |
|---|---|
| `scripts/publish.py` | DONE — `get_plugin_name()` + resolver tag; both tags in ONE `--atomic` push |
| `tests/test_publish_resolver_tag.py` | DONE — 10 real tests, all passing (no mocks) |
| `skills/the-skills-menu/SKILL.md` | DONE — hand-written (canon's generated one is broken); 0 lint errors |
| `agents/…-main-agent.md` | DONE — preloads only the catalog; 28 skills now load on demand |
| `.commitlintrc.json` | DONE — adopted (inert: commitlint is not in `ENABLE_LINTERS`) |
| Canon regressions | REJECTED (4) — see the table below |
| CPV coordination | DONE — `claude-plugins-validation#165` (3 asks + upstream offer) |

**NEXT ACTION:** run the full gate — `uv run tests/run-all-tests.py`, then the EXACT CI
command (below), then `publish.py --patch --dry-run`. Then commit locally and **STOP**.

**Do NOT push.** Pushing *is* a release here (the process-ancestry pre-push hook permits no
other path), and release authorization is a **separate, still-pending** USER decision.

**SUPERSEDED — do NOT carry forward:**

- The 2026-07-10 canon diff in `[[project_cpv_pipeline_drift_do_not_standardize]]` (it
  predicted `publish.py` would gain G2c/G2d gates). **Wrong now.** Canon v2.157.2 leaves
  `publish.py` entirely alone — CPV #145's profile-awareness works.
- The ai-maestro #44 thread's "apply these 4 canon-CI fixes by hand" recipe. **All four are
  fixed** (CPV #142 CLOSED 2026-06-21). Verified, not assumed.

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
