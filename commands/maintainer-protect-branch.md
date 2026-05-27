---
description: Apply the canonical branch protection ruleset to a repo's default branch — PR-required, force-push blocked, deletion blocked, linear history, signed commits, status checks required.
argument-hint: "<owner/repo>"
---

Apply (or refresh) the canonical branch-protection ruleset on the
default branch of `<owner/repo>`.

The applied ruleset requires:

- Pull requests (no direct push to default branch)
- Linear history (no merge commits unless squashed)
- Status checks: every job name visible in the most recent push of
  the validate / release workflows must pass
- Signed commits
- Force-push: BLOCKED
- Deletion: BLOCKED

Loads skill: **workflow-protect-branch** (mode=APPLY)

The skill is idempotent — running it on an already-protected
branch updates the status-checks list if any have changed, and
exits 0 with no diff otherwise. It uses
`gh api PUT repos/<owner>/<repo>/rulesets/<id>` (or POST if no
default-branch-ruleset exists yet), then re-fetches and caches the
result to `$AGENT_DIR/.aimaestro/state/branch-rules.json` so
downstream skills see the live state on the next push.

To preview the current ruleset without modifying it, use
`/maintainer-show-branch-rules`.

If the agent does NOT have admin permission on the target repo,
this command fails fast with a clear permission error (`gh api`
returns 403). It does NOT attempt to escalate.
