---
trdd-id: 1LTGEA2H
title: Remove the abolished owner lockout from workflow-protect-branch and bootstrap templates (audit C2b-1 C2b-2)
column: todo
created: 2026-08-18T19:55:21+0200
updated: 2026-08-18T19:55:21+0200
current-owner: maintainer-agent-session
task-type: bugfix
approval-tier: 0
created-by: TRDD-BRRJK57P phase-2 GO (hub 2026-08-18)
relevant-rules: []
---

# Remove the abolished owner lockout from shipped surfaces

Phase-2 remediation of CONFIRMED audit findings C2b-1 + C2b-2
(`reports/plugin-self-audit/20260816_190656+0200-audit.md`; detail in
`reports/plugin-self-audit/candidates/axis2b-baseline-prose-drift.md`).
One root cause: shipped surfaces still carry the PRE-ratification baseline
shape (empty `bypass_actors`, 1 approval) that the USER's Tier-3 ruling
abolished. The code SSOT is the janitor's
`branch_protection_lib.baseline_ruleset_payloads` (v3.3.11 `scripts/lib/`:
admin bypass on history-protect at :226-232, approvals 0 at :303).

## The defects

1. **C2b-1** — `skills/workflow-protect-branch/references/instructions.md`
   - `:274` sends `"bypass_actors": []` on history-protect (wrong: admin bypass now)
   - `:295` sends `required_approving_review_count: 1` (wrong: 0 now)
   - `:478-479` ENFORCES `HIST_BYPASS = 0` — the verification fails precisely
     when a repo is CORRECTLY configured
   - **DISCRIMINATOR: `:523` (tag assertion) is CORRECT — do NOT sweep it.**
2. **C2b-2** — two `workflow-bootstrap` templates carry the same abolished pair:
   `ruleset-no-force-no-delete.json:15`, `ruleset-required-checks.json:15`.

## Constraints

- Build every payload from the SSOT shape (`baseline_ruleset_payloads`), never
  from prose (five prose sites fleet-wide still say otherwise).
- The CPV wrong-shape PUT (`setup_branch_rules.py:807`) is ANOTHER project —
  not touched from here. This card fixes only THIS plugin's surfaces; it does
  not depend on CPV, so it is not blocked-by.

## Acceptance

- [ ] instructions.md :274 region ships admin-bypass history-protect payload
- [ ] instructions.md :295 region ships approvals 0
- [ ] instructions.md :478-479 verification asserts the RATIFIED shape (admin
      bypass present, approvals 0) and reddens on the abolished one
- [ ] :523 tag assertion untouched
- [ ] both bootstrap template JSONs carry the ratified pair
- [ ] repo-wide grep finds no remaining `"bypass_actors": []` on a
      default-branch history-protect surface and no `review_count: 1` baseline
      claim (docs deliberately historical excepted)

## Approval log
