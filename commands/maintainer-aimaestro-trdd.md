---
description: Drive the ai-maestro TRDD CLI (aimaestro-trdd.sh) — search, read, verify, edit, approve, refuse, promote, archive. Probes for the script first and degrades explicitly when absent; verify answers from a signed token, never prose.
argument-hint: "[search|read <id>|verify <id>|edit <id>|approve <id>|refuse <id>|promote <id>|archive <id>]"
---

Drive `aimaestro-trdd.sh` — ai-maestro's Tier-A **task SSOT** over the TRDD corpus.
Its write verbs became agent-usable in `d7531e53` (TRDD-K2WJH7RF), governed by the
`manage-trdd` AuthAction.

Loads skill: **maintainer-aimaestro-trdd**

**Probe first, always.** The CLI may be absent and that is normal: `install.sh` clones
ai-maestro with no `--branch`, so a provisioned host tracks `main`, which ships only a
subset of the scripts. `command -v aimaestro-trdd.sh` — on a miss, print the degrade
and exit `3`. Never gate on a version string; never treat `~/.local/bin` as truth (the
installer copies and never prunes, so it is residue).

Eight verbs:

- `search` — `--column C` `--id I` `--keyword K` `--zone proposals|tasks|archived|refused`
- `read <id>` — the card
- `verify <id>` — **is this approval REAL?** `--json`; exit `0` verified · **`2` NOT
  verified** · `1` error. Exit `2` is an answer — a finding to report, not to retry.
- `edit <id>` — `--set k=v` (repeatable); frontmatter in place, no folder move
- `approve <id>` — `--approver W` `--tier N` `--rationale R`; proposal → planned,
  `git mv`, and **MINTS** the signed `approval-token:`
- `refuse <id>` — `--approver W` `--tier N` `--reason R`; → `refused/`
- `promote <id> --column C` — `--note N` `--approver W`; advance in place
- `archive <id> --state S` — `completed|cancelled|superseded`; **refuses `failed`**
  (failed is retryable and stays open — giving up is an explicit `cancel`)

`--agent <uuid|name>` targets that agent's corpus. **Nothing is committed for you** —
stage by name and commit with the TRDD id in the subject.

**Authority** comes from the card's `min-approval-requirement:`
(`none < orchestrator < chief-of-staff < manager < user`). No agent may approve a
`user`-floor card; **no one may approve their own proposal**, MANAGER included.

**Why `verify` ignores the prose:** it answers from the host-signed, ledger-anchored
token — checking the signature, the R34 anchor, that the issuer still holds its title,
and that its authority meets the card's floor. `approval-judge:` and the
`## Approval log` line are exactly what a forger rewrites.

**What it does NOT prove:** the token binds the approval to the card's *identity, not
its content*. A body edited after approval still verifies — because the approval is
authentic. Never call a verified approval a vouch for the body.
