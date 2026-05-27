---
description: Detect missing community files (CONTRIBUTING / SECURITY / CODE_OF_CONDUCT / ACKNOWLEDGMENTS / AUTHORS / ISSUE_TEMPLATE / PULL_REQUEST_TEMPLATE) on the maintained repo, then generate them from per-repo-customised templates. Never overwrites existing files.
argument-hint: "[audit|generate|diff|update-stale|validate]"
---

Detect which community files the maintained repo is missing,
which are stale, which exist. Generate the missing ones from
templates that substitute per-repo placeholders ($PROJECT_NAME,
$AUTHOR, $EMAIL, $REPO_URL, $CONTACT_EMAIL).

Loads skill: **maintainer-generate-docs**

Five modes:

- `audit` (default) — list which files exist, which are missing,
  which are stale (last touched > 365 days). Exit 0 if all
  present + fresh.
- `generate` — write the missing files using the templates.
  REFUSES to touch existing files. Each template uses
  `envsubst` for placeholder substitution; values come from the
  maintained repo's `pyproject.toml` / `package.json` /
  `git remote -v` / `git config user.*`.
- `diff` — show the diff between an existing file and what the
  template would produce. Read-only.
- `update-stale` — re-generate ONLY files that haven't been
  touched in > 365 days, after backing them up to
  `<file>.bak.<TS>`.
- `validate` — sanity-check existing files (does CONTRIBUTING
  mention the test command? Does SECURITY have a disclosure
  address?). Returns a list of failures.

Templates shipped under
`skills/maintainer-generate-docs/references/templates/`:

- CONTRIBUTING.md.template
- SECURITY.md.template
- CODE_OF_CONDUCT.md.template (references Contributor Covenant
  v2.1 by URL — does not inline the full text)
- ACKNOWLEDGMENTS.md.template
- AUTHORS.template (uses `git shortlog -sne` for the contributor list)
- .github-PULL_REQUEST_TEMPLATE.md.template
- .github-ISSUE_TEMPLATE-{bug_report,feature_request,config}.yml.template

Placeholder resolution:
`skills/maintainer-generate-docs/references/placeholder-map.md`.

Validation checks:
`skills/maintainer-generate-docs/references/validate-checks.md`.

Use case: a maintainer takes over a public repo with bare
`README.md` only. `/maintainer-generate-docs audit` reports the 9
missing files; `/maintainer-generate-docs generate` writes all 9
from templates substituting per-repo metadata; the maintainer
reviews and commits.
