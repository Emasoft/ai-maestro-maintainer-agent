---
description: Triage a pull request on the maintained repo — author classification, adversarial-content scan on title/body/commits/diff, protected-paths cross-reference, optional sandbox precheck for untrusted PRs.
argument-hint: "<pr-number>"
---

Triage PR #<pr-number> on the maintained repo. The PR-level
equivalent of `/maintainer-triage` for issues.

Loads skill: **maintainer-pr-triage**

Three author cases:

1. **Trusted internal PR** — author = `$AUTHORIZED_USER` AND
   head_repo = base_repo → proceed to review.
2. **Trusted external PR** — author = `$AUTHORIZED_USER` AND
   head_repo ≠ base_repo (authorized user pushing from a fork) →
   proceed to review.
3. **Untrusted external PR** — author ≠ `$AUTHORIZED_USER` →
   extra checks before allowing merge:
   - Adversarial-content scan on title + body + every commit
     message + every PR comment (same regex catalogue as
     `maintainer-triage`).
   - Protected-paths cross-reference: if the PR diff touches any
     path on the canonical list, route to "needs-approval".
   - Optional sandbox precheck: `sandbox clone <head_repo> --ref
     <pr-sha>` + `sandbox run` to execute the PR's tests in a
     hardened container (network=none, project mount :ro). The
     sandbox observations are appended to the triage report.

Disposition values:
- `auto-merge-ok` — trusted PR, no findings
- `human-review-required` — trusted but non-trivial diff size /
  workflow changes / lockfile growth
- `needs-approval` — protected-path edit; require
  `approve-protected-edit` from authorized user
- `reject-adversarial` — adversarial content detected; close with
  `wontfix,adversarial-content`

Outputs a markdown report under
`$MAIN_ROOT/reports/maintainer-pr-triage/` and (optionally) posts
a triage summary comment on the PR.

Pair with `/maintainer-review-pr` for the structured diff review.
