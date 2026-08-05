---
description: Drive the ai-maestro TRDD CLI (aimaestro-trdd.sh) — search, read, verify, edit, approve, refuse, promote, archive. Probes for the script first and degrades explicitly when absent; verify answers from a signed token, never prose.
argument-hint: "[search|read <id>|verify <id>|edit <id>|approve <id>|refuse <id>|promote <id>|archive <id>]"
---

Drive `aimaestro-trdd.sh` — ai-maestro's Tier-A **task SSOT** over the TRDD corpus.
Its write verbs became agent-usable in `d7531e53` (TRDD-K2WJH7RF), governed by the
`manage-trdd` AuthAction.

Loads skill: **maintainer-aimaestro-trdd**

**Frozen CLI only (IRON RULE).** Every one of these verbs reaches the server through
`aimaestro-trdd.sh`. NEVER reach past it to the server's `/api/*` — not when a verb is
missing, not when the script is absent, not for a read that merely looks harmless, and
not to "just check" a token. When the frozen path cannot do it, **the capability does
not exist here**: degrade explicitly (below) and report the gap upstream. This binds
this command file itself, because a command runs with **no skill loaded** — the
prohibition has to be at the surface where the decision is actually made, not one hop
away in a skill nobody consulted. (`gh` and package-registry APIs are NOT covered.)

**Probe first — and probe the VERB, not just the script.** The CLI may be absent, and
even when present it may lack the verb: verified 2026-07-16, the deployed copy is 330
lines / 7 verbs while `governance-rules` is 387 / 8 — the missing one is **`verify`**
(ai-maestro#69). So `command -v aimaestro-trdd.sh` for the script, then
`aimaestro-trdd.sh --help | grep -qE "^[[:space:]]+<verb>\b"` for the verb; on either
miss, print the degrade and exit `3`. Never gate on a version string; never infer a
verb from `docs/SCRIPT-MANIFEST.md` (it documents `verify`, which the deployed script
lacks); never treat `~/.local/bin` as truth (the installer copies and never prunes, so
it is residue). **A skill teaching a verb the shipped CLI lacks is as broken as a
manifest promising one `main` doesn't ship.**

Eight verbs:

- `search` — `--column C` `--id I` `--keyword K` `--zone proposals|tasks|archived|refused`
- `read <id>` — the card
- `verify <id>` — **is this approval REAL?** `--json`; exit `0` verified · **`2` NOT
  verified** · `1` error. Exit `2` is an answer — a finding to report, not to retry.
  ⚠️ **Not on the deployed script — probe before calling** (ai-maestro#69). Where it is
  absent, approval authenticity CANNOT be checked: say so, and never substitute the
  card's `approval-judge:`/`## Approval log` prose for a real check.
  `--tier` is a CLAIM the server must validate against the caller's real title by AID —
  never a grant to trust (ai-maestro#69 §2).
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
