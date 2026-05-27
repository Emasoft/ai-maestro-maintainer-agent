---
description: Structured review of a PR's diff against the canonical 7-category checklist (workflow changes, protected paths, lifecycle scripts, lockfile growth, test changes, diff size, untrusted actions). Posts a single AI-assisted review comment.
argument-hint: "<pr-number>"
---

Structured review of PR #<pr-number> against the 7-category
checklist. Pair with `/maintainer-triage-pr` which decides
*whether* to review; this command performs the review.

Loads skill: **maintainer-pr-review**

Checklist (each category flags the PR if the criteria fires):

1. **Workflow changes** — if the PR touches `.github/workflows/`,
   fires `workflow-scan` on the new YAML; reports new HIGH
   zizmor / actionlint / Sentinel-port findings.

2. **Protected-path edits** — lists every protected path
   (`.github/**`, `scripts/publish.py`, `.gitignore`, `.npmrc`,
   etc.) the PR touches and prompts for `approve-protected-edit`
   from the authorized user.

3. **Lifecycle scripts** — flags any new `preinstall` /
   `postinstall` / `prepare` in `package.json`, any new
   `[build-system]` entries or script entry points in
   `pyproject.toml`.

4. **Lockfile growth** — flags lockfiles (`package-lock.json`,
   `uv.lock`, `Cargo.lock`, `go.sum`) that added new packages.
   Cross-references package release dates: a < 7-day-old new dep
   is auto-flagged (matches the article-recommended
   `min-release-age` posture).

5. **Test changes** — flags PRs adding production code without
   tests, and any PR DELETING tests.

6. **Diff size** — flags PRs > 500 lines with a
   "consider splitting" recommendation.

7. **Untrusted action additions** — flags any new
   `uses: <action>@<tag>` line in `.github/workflows/`.

Posts a SINGLE structured comment on the PR summarizing every
flag. The comment header explicitly states "this is an
AI-assisted review; final approval requires a human reviewer."

The review does NOT approve or reject the PR — that decision
remains with the human reviewer. The agent's role is to surface
the structured findings; the human decides.

Cross-reference: the seven categories live in
`skills/maintainer-pr-review/references/review-checklist.md` with
the exact `gh` / `git` / `grep` commands per category.
