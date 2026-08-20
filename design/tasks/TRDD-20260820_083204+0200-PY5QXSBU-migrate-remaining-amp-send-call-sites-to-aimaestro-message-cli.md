---
trdd-id: PY5QXSBU
title: Migrate the 5 remaining amp-send call sites to the aimaestro-message CLI
column: todo
created: 2026-08-20T08:32:04+0200
updated: 2026-08-20T08:32:04+0200
current-owner: maintainer-agent-session
task-type: docs
min-approval-requirement: none
---

# Migrate the 5 remaining amp-send call sites to the aimaestro-message CLI

`aimaestro-message.sh` v1.0.0 shipped (hub TRDD-0AB76JG3, 2026-08-20) to the
maintainer's exact contract; `approval-request.md` already migrated (00a4499).
Hub-agreed plan: fold the rest into the next release cycle, keeping the
CLI-primary / `amp-send`-fallback pattern so the shipped prose is correct on
hosts in EITHER deploy state (future hosts install the plugin before the
server's CLI layer necessarily lands).

## Call sites (grep-verified 2026-08-20)

- `skills/maintainer-guardian/SKILL.md:31,33,103` (T5 escalation)
- `skills/maintainer-guardian/references/threat-classes.md:300,315`
- `skills/maintainer-prrd-trdd-kanban/SKILL.md:32,59,95`

## Acceptance

- [ ] every site names `aimaestro-message.sh send` as primary (exit codes: 3
      transport / 4 not-found / 5 ambiguous / 6 R6-refused-follow-hint / 7 auth;
      never `--from` as an agent) with `amp-send` as the explicit degrade path
- [ ] `grep -rn 'amp-send' skills/ agents/` shows only fallback-labelled uses
- [ ] rides a release (publish.py)

Pattern to copy: `skills/maintainer-approval-gate/references/approval-request.md`.
