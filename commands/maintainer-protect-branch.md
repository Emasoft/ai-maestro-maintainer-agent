---
description: Apply the canonical two-ruleset baseline branch protection to a repo's default branch — force-push, deletion, and non-linear history blocked, PR review + status checks required (admin RepositoryRole bypasses the PR + checks so the canonical direct-push publish still works).
argument-hint: "<owner/repo>"
---

Apply (or refresh) the canonical two-ruleset branch protection on
the default branch of `<owner/repo>`.

Two rulesets are applied (see **workflow-protect-branch** for why a
single combined ruleset cannot work on a direct-push repo):

- `baseline-history-protect` — `deletion` + `non_fast_forward` +
  `required_linear_history`, no bypass → force-push, deletion, and
  non-linear (merge-commit) history blocked for EVERYONE, including
  admin.
- `baseline-pr-and-checks` — `pull_request` (1 approval) +
  `required_status_checks` (strict; every job name in the validate /
  release workflows must pass), with an admin RepositoryRole `always`
  bypass → the canonical `publish.py` direct push to the default branch
  succeeds (a fast-forward is not a force-push and adds no merge
  commit), while outside-contributor PRs are still gated by review +
  checks.

Loads skill: **workflow-protect-branch** (mode=APPLY)

The skill is idempotent — running it on an already-protected branch
updates each ruleset's status-checks list if any have changed, and
exits 0 with no diff otherwise. For each ruleset it uses
`gh api PUT repos/<owner>/<repo>/rulesets/<id>` (or POST if that
ruleset does not exist yet), then re-fetches and caches the result
to `$AGENT_DIR/.aimaestro/state/branch-rules.json` so downstream
skills see the live state on the next push.

To preview the current ruleset without modifying it, use
`/maintainer-show-branch-rules`.

If the agent does NOT have admin permission on the target repo,
this command fails fast with a clear permission error (`gh api`
returns 403). It does NOT attempt to escalate.
