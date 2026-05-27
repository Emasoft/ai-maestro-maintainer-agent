---
description: Resolve every `uses: owner/action@vTAG` to its 40-char commit SHA via gh api, with the original tag preserved as a trailing comment.
argument-hint: "[--dry-run]"
---

Discover every `uses: owner/action@vTAG` in `.github/workflows/`
on the maintained repo, resolve each tag to its 40-char commit SHA
via `gh api repos/<owner>/<action>/commits/<tag>`, then rewrite
the workflow:

```yaml
# before
- uses: actions/checkout@v4

# after
- uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5  # v4.3.1
```

Loads skill: **workflow-pin-actions**

The original semver tag is preserved as a trailing inline comment
so a reviewer can see at a glance what each SHA corresponds to.
This is the canonical Dependabot-compatible format — Dependabot
will keep the SHA + comment in sync on future updates.

`--dry-run` prints the planned rewrite without modifying files
(useful inside a sandbox or before committing).

This command does NOT verify the resolved SHA against the action's
upstream signing key — if the SHA you trust is the SHA Dependabot
will resolve for the same tag, you trust the action.
