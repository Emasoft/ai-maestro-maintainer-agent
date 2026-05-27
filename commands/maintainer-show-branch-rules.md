---
description: Read-only fetch of the default-branch ruleset on the maintained repo. Caches the result for downstream skills.
argument-hint: "[<owner/repo>]"
---

Fetch the current branch-protection ruleset on the default branch
of `<owner/repo>` (defaults to the maintained repo if omitted) and
print a human-readable summary.

Loads skill: **workflow-protect-branch** (mode=SHOW)

This is a read-only operation. It uses
`gh api repos/<owner>/<repo>/rulesets` (NOT the older
`gh ruleset list` subcommand, which requires `gh ≥ 2.44`).

The result is cached to `$AGENT_DIR/.aimaestro/state/branch-rules.json`
for downstream skills (workflow-fix-safe, maintainer-fix, etc.)
that need to know what status checks must pass before a push will
succeed. Refresh the cache before any push:

```bash
# Refresh, then check
/maintainer-show-branch-rules
git push origin main
```

To apply or update protection (rather than just observe it), use
`/maintainer-protect-branch`.

To clear the cache and force a re-fetch on the next read, delete
`$AGENT_DIR/.aimaestro/state/branch-rules.json` — the next SHOW
call will recreate it.
