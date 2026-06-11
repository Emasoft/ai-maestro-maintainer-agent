---
trdd-id: ea33f618-90ad-4bdc-840d-7f9baa747945
title: Evaluate Renovate as Dependabot replacement for github-actions
column: complete
created: 2026-05-23T17:30:00+0200
updated: 2026-06-11T11:13:41+0200
---

## TRDD-ea33f618 — Evaluate Renovate as Dependabot replacement for github-actions

**Filename:** `design/tasks/TRDD-20260523_173000+0200-ea33f618-renovate-vs-dependabot-eval.md`
**Tracked in:** this repo (design/tasks/ is git-tracked)
**Companion research notes:** `reports/renovate-eval/20260523_175306+0200-notes.md` (gitignored, contains the full citation list)

---

## 1. Verbatim user prompt that motivated this work

> (From the v1.1.0 conversation, 2026-05-23) The user surfaced Atai Barkai's
> 2026-05-20 supply-chain article and asked whether this plugin should
> migrate from GitHub-native Dependabot to Renovate. The article called out
> a known Dependabot grouping bug (#14202) that floods repos with PRs and
> recommended Renovate for:
>
> - One PR per repo for all updates (vs Dependabot's per-package fan-out)
> - Built-in auto-merge after CI
> - `helpers:pinGitHubActionDigests` preset that auto-pins actions to SHAs
> - Central config across all repos via shared base config
> - Free for public AND private repos

This TRDD is the decision document for whether to act on that
recommendation.

---

## 2. Context

The plugin currently uses GitHub-native Dependabot:

- `.github/dependabot.yml` — committed, weekly schedule, one `github-actions`
  ecosystem block, `actions-minor-and-patch` group covering `minor` + `patch`,
  major bumps as separate PRs, `open-pull-requests-limit: 5`.
- `skills/workflow-bootstrap/references/templates/dependabot.yml` — identical
  seed copy that workflow-bootstrap stamps into downstream plugins, then
  appends a second ecosystem block (`pip` / `npm` / `cargo` / `gomod`) per
  detected language.

Actual SHA-pinned-action surface today:

- 3 workflows (`release.yml`, `validate.yml`, `notify-marketplace.yml`)
- ~7 unique pinned actions (`actions/checkout`, `actions/setup-python`,
  `astral-sh/setup-uv`, `actions/upload-artifact`,
  `github/codeql-action/upload-sarif`, `peter-evans/repository-dispatch`)
- All already SHA-pinned with `# vX.Y.Z` trailing comments via the
  `workflow-pin-actions` skill

---

## 3. Article-claim verification (one-line summary per claim, full evidence in companion notes)

| Article claim | Verdict | Note |
|---|---|---|
| Dependabot has a known grouping bug (#14202) that floods PRs | PARTIAL | #14202 is Maven-specific and the symptom is **suppression** not **flooding**. Article overstates applicability to github-actions. |
| Renovate auto-pins actions via `helpers:pinGitHubActionDigests` | TRUE | But the preset is a no-op on this repo since `workflow-pin-actions` already SHA-pins everything. |
| Renovate consolidates updates into one PR per repo | PARTIAL | Renovate's real win is **in-place PR updates** (force-push on new version); Dependabot now also supports grouping, which this plugin already uses. |
| Renovate has built-in auto-merge | TRUE-with-sharp-edges | `platformAutomerge: true` silently ignores `automergeStrategy`, ignores `automergeSchedule`, and (without required-status-checks) can auto-merge failing PRs. |
| Central config across all repos via shared preset | TRUE | Renovate `extends: github>org/repo`. Dependabot has no equivalent. Decisive ONLY for multi-repo orgs. |
| Free for public AND private repos | TRUE | Cost parity with Dependabot. |

Full citations, exact upstream-issue numbers, and discussion-thread links
in `reports/renovate-eval/20260523_175306+0200-notes.md`.

---

## 4. Comparison matrix (this plugin's actual use case)

Scope: one repo, one ecosystem (`github-actions`), ~7 pinned actions, weekly
cadence, no automerge currently configured.

| Dimension | Dependabot (current) | Renovate (proposed) | Winner |
|---|---|---|---|
| SHA pinning | Honors already-pinned actions; updates SHA + comment | Same, via `helpers:pinGitHubActionDigests` | TIE |
| PR volume | Grouped minor+patch in 1 PR, major separate (current config) | Grouped via presets; in-place PR updates | Renovate (marginal) |
| Auto-merge | Requires ~40-line workflow + `dependabot/fetch-metadata` | `platformAutomerge: true` (but documented bugs) | TIE |
| Config sharing across repos | None | `extends: github>org/repo` | Renovate (irrelevant for single-repo plugin) |
| Private-repo cost | Free | Free | TIE |
| Setup time | Zero (already shipped) | Install GitHub App + author renovate.json + onboarding PR + branch-protection wiring | Dependabot |
| Maintenance burden | Low — config is 30 lines; bugs are upstream | Medium — more knobs, more documented bugs to track | Dependabot |
| Bus factor / vendor lock-in | GitHub-only, owned by GitHub | 5 platforms, owned by Mend.io | Renovate (theoretical) |
| Supply-chain story | Surfaces upstream patches as PRs | Same | TIE |
| Known bugs as of 2026-05 | Group-pattern + update-types in Maven (#14202); fanout edge cases (#13919) | `platformAutomerge` ignores `automergeStrategy`, ignores `automergeSchedule`; bare-SHA actions disabled by default | TIE |

**Decisive factors for THIS plugin:**

1. The plugin's surface is **1 repo, 7 actions, 3 workflows**. Renovate's killer features (multi-repo shared config, in-place updates on high-churn deps, regex managers for non-standard files) provide near-zero value at this size.
2. The Dependabot config we ship is **already** the well-grouped pattern that sidesteps #14202's frame — `update-types: [minor, patch]` in a group, majors separate.
3. Migration touches **two files in this repo** plus **every downstream plugin** that consumed the workflow-bootstrap template. Non-trivial blast radius for marginal benefit.
4. Renovate's "built-in auto-merge" pitch is partially defeated by the documented `platformAutomerge` bugs; we'd need to handle them ourselves.

---

## 5. Test plan (for the decision itself, not for an unimplemented migration)

The recommendation here is "keep status quo" — so the test plan is the set
of signals that would falsify it and force re-opening the evaluation.

### How would we know the current setup is working?

- `gh pr list --repo Emasoft/ai-maestro-maintainer-agent --label dependencies` lists at most ~1 grouped minor/patch PR per Monday, plus occasional major-bump PRs.
- Pinned-action SHAs do get bumped — no action has been stuck on a stale SHA for >30 days when an upstream patch is available.
- No silent suppression of major bumps observed in PR history.

### How would we know the current setup is broken?

- Dependabot stops opening PRs for >2 weeks even though upstream actions have shipped new versions (silent suppression — would trigger Issue #14202 concern).
- Dependabot opens N separate PRs for what should be one grouped PR (fanout — would trigger Issue #13919 concern).
- A supply-chain incident lands a malicious version of an upstream action and Dependabot's open-new-close-old behavior delays our awareness vs Renovate's in-place update would have caught it.

### Rollback path (if the recommendation is wrong)

Since the recommendation is "keep Dependabot," the "rollback" is just
re-opening this TRDD's question by authoring a **new** TRDD that supersedes
this one. No code rollback is needed because nothing changed.

---

## 6. Decision

**KEEP Dependabot. Do not migrate to Renovate at this time.**

### Rationale (one paragraph)

The plugin's current Dependabot config already implements the grouped,
SHA-aware, weekly-cadence pattern that Renovate is being recommended for.
Renovate's three strongest advantages (multi-repo shared presets, in-place
PR updates on high-churn deps, broader platform coverage) all have
near-zero value on a single-repo plugin with 7 pinned actions across 3
workflows. The two specific bugs the article cites against Dependabot are
narrower than they appear (#14202 is Maven-specific; the github-actions
grouping path is a different code path that has not exhibited this
behavior in our PR history). Migrating would touch two files in this repo
plus every downstream plugin that consumed the workflow-bootstrap template
— a non-trivial blast radius for marginal benefit. The Renovate
`platformAutomerge` story also has its own documented sharp edges (ignored
merge strategy, ignored schedule, auto-merge of failing PRs without status
checks) that would need to be carefully configured around. Net: status quo
is the higher-EV choice.

### Revisit-criteria (when to author a new TRDD that supersedes this one)

Open a successor TRDD if any of these become true:

1. The maintainer-agent owner ends up managing **5+ repos** that all want
   identical update policy — shared presets become decisive.
2. Dependabot github-actions grouping breaks materially in this repo
   (silent suppression of majors, or stale-PR explosion) and the upstream
   bugs aren't being fixed.
3. A supply-chain incident shows that **in-place PR updates** (Renovate's
   key behavioral difference) would have caught a malicious version sooner
   than Dependabot's open-new-PR-close-old approach.
4. The user wants auto-merge across many ecosystems and prefers the
   one-config-many-tools angle.
5. The `workflow-bootstrap` skill grows to seed many downstream plugins
   and the user wants one place to update update-policy.

---

## 7. File list — what WOULD need to change if we ever migrate

This section is **forward-looking notes for the successor TRDD**, not a
to-do list for this session.

### Files to add (in a future migration)
- `renovate.json` (root) extending `config:best-practices` + `helpers:pinGitHubActionDigests`, with `packageRules` to group minor+patch, separate majors, and `platformAutomerge: true` on minor/patch only

### Files to remove (in a future migration)
- `.github/dependabot.yml` (after Renovate onboarding PR lands and is verified)

### Files to update in this plugin (in a future migration)
- `skills/workflow-bootstrap/SKILL.md` and references — switch the seed from `dependabot.yml` to `renovate.json` (or seed both during a deprecation window)
- `skills/workflow-bootstrap/references/templates/dependabot.yml` — archive or replace with `renovate.json` template
- The language-aware ecosystem-block logic (`pip` / `npm` / `cargo` / `gomod`) becomes a `packageRules` matrix — different shape, similar intent

### Branch-protection setup (in a future migration)
- Enable "Allow auto-merge" in repo settings
- Configure required status checks (at minimum: `validate` workflow)
- Add Renovate to "Allow specified actors to bypass required pull requests"
  if PR-review enforcement is on

### Downstream impact (in a future migration)
- Every plugin that ran `workflow-bootstrap` before the migration is still
  on Dependabot and will stay on Dependabot until it re-runs bootstrap.
  Decide whether the bootstrap skill should detect existing
  `dependabot.yml` and migrate, or only seed `renovate.json` for fresh
  plugins. This is a design decision the successor TRDD has to make.

---

## 8. Acceptance criteria (for this TRDD only)

This TRDD's acceptance criteria are met when:

- [x] The current Dependabot config has been read and characterized
- [x] The article's six specific claims have each been independently verified against current upstream docs and trackers
- [x] A comparison matrix specific to this plugin's surface (1 repo, 7 actions, 3 workflows) has been written
- [x] A decision has been recorded with rationale
- [x] Revisit-criteria are documented so a future session can re-open the question on objective signals rather than re-doing the research from scratch
- [x] The file list for a future migration is sketched (forward-looking, not actioned)
- [x] No source code in this plugin has been modified

Status set to `completed` because the recommendation is status-quo — no
implementation work follows from this TRDD. If a successor TRDD is later
opened per the revisit-criteria above, it will be a new TRDD with its own
UUID, not an edit of this one.
