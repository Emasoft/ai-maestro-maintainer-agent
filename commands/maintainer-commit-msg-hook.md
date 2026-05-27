---
description: Install / audit / uninstall the commit-msg hook that enforces conventional-commit subject lines plus a WHY paragraph in the body. Operates on the entrusted repo's .git/hooks/commit-msg.
argument-hint: "[install|audit|uninstall]"
---

Install (or audit / uninstall) the commit-msg hook on the
maintained repo. The hook:

- Validates subject line matches conventional-commits:
  `type(scope): subject` where `type` ∈ {feat, fix, docs, chore,
  refactor, test, perf, style, ci, build, revert} and the
  subject is ≤ 70 chars.
- Validates the body has ≥ 2 paragraphs.
- Validates one body paragraph contains a WHY marker
  (case-insensitive): "why" / "rationale" / "context" / "reason"
  / "because".
- On violation: exits non-zero with a clear error message; the
  commit is rejected.

Loads skill: **maintainer-commit-msg-why**

Three modes:

- `install` (default) — copy the canonical hook to the entrusted
  repo's `.git/hooks/commit-msg` + `chmod +x`. Refuses to
  overwrite an existing hook; backs it up to
  `.git/hooks/commit-msg.bak.<TS>` if one exists.
- `audit` — scan the last 50 commits, report which ones would
  have failed the validation. Prints a per-commit verdict
  (`pass` / `fail` / `fail+bypass-used`).
- `uninstall` — remove the hook; restores `.bak.<TS>` if one
  exists.

The hook respects `COMMIT_MSG_HOOK_BYPASS=1` for emergency
situations (e.g. mid-rebase). When the bypass is used, the hook
logs to stderr so audit mode can highlight bypassed commits.

The shipped hook is pure bash + grep — no external deps. Works on
any POSIX shell. Documented at
`skills/maintainer-commit-msg-why/references/hooks/commit-msg.sh`.

Why this matters: every commit body should explain the WHY of the
change so a future reader (or the agent on a later patrol) can
reconstruct the rationale. A subject line alone is not enough.
