---
description: Apply the canonical three-ruleset baseline (branch + release-tag) protection — force-push, deletion, and non-linear history blocked on the default branch, PR review + status checks required (admin RepositoryRole bypasses PR + checks so the canonical direct-push publish still works), and published v*.*.* tags made immutable (no move or delete; tag creation stays open).
argument-hint: "<owner/repo>"
---

Apply (or refresh) the canonical three-ruleset baseline (branch +
release-tag) protection on `<owner/repo>`.

Three rulesets are applied (see **workflow-protect-branch** for why the
two branch rulesets must be split on a direct-push repo):

- `baseline-history-protect` — `deletion` + `non_fast_forward` +
  `required_linear_history`, no bypass → force-push, deletion, and
  non-linear (merge-commit) history blocked for EVERYONE, including
  admin.
- `baseline-pr-and-checks` — `pull_request` (1 approval) +
  `required_status_checks` (strict; every PR-applicable CI job name
  must pass — push-only jobs like release/notify are excluded so they
  can't deadlock a PR), with an admin RepositoryRole `always` bypass →
  the canonical `publish.py` direct push to the default branch succeeds
  (a fast-forward is not a force-push and adds no merge commit), while
  outside-contributor PRs are still gated by review + checks.
- `baseline-tag-protect` — `deletion` + `update` on `refs/tags/v*.*.*`,
  no bypass → published version tags are immutable (cannot be moved or
  deleted, so installers pinned to a tag can't be silently re-pointed),
  while tag *creation* stays open so `publish.py` still cuts each new
  release. The exact `ref_name.include` literal is readback-pinned on
  first apply.

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
