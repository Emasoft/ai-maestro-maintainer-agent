---
description: |
  Drive the ai-maestro TRDD CLI (aimaestro-trdd.sh) — the 3-pillars task
  SSOT — to search, read, verify, edit, approve, refuse, promote, and
  archive TRDD cards. Use for "verify this approval", "is this card's
  approval real", "approve/refuse a proposal", "promote a TRDD",
  "archive a completed TRDD", "search the board". ALWAYS probes for the
  script first and degrades explicitly when absent — an install.sh host
  does not ship it. Verify answers from a signed token, never prose.
---

# maintainer-aimaestro-trdd — the ai-maestro TRDD CLI, probed before use

## Overview

`aimaestro-trdd.sh` is ai-maestro's **task SSOT**: one frozen (Tier-A) CLI over the
TRDD corpus — the same cards this plugin's `maintainer-trdd-adr` skill authors. Its
write verbs (`edit`, `approve`, `refuse`, `promote`, `archive`) used to reject every
agent with `agent_policy_undefined`; since `d7531e53` (TRDD-K2WJH7RF) they are
governed by the `manage-trdd` AuthAction and are usable by agents within their
authority.

**Why this skill exists at all:** `docs/SCRIPT-MANIFEST.md` §5.3 records that
`aimaestro-trdd.sh` is Tier-A and **zero plugins reference it** — "a capability
nobody knows about is not a capability" — and §5.4 assigns adoption to each
role-plugin repo, this one included.

## Prerequisites — PROBE, never assume

**The script may not exist on this host, and that is normal.** `install.sh` clones
ai-maestro with no `--branch`, so a provisioned host tracks `main`, which ships a
subset of the scripts; the full surface exists only where the `governance-rules`
tree runs directly. The manifest is a **contract, not a presence guarantee**, and a
host's `~/.local/bin` is deployment residue (the installer copies and never prunes),
never a source of truth.

**Probe the VERB, not just the script.** `command -v` alone is not enough — and this
is not hypothetical: as of 2026-07-16 the copy deployed to `~/.local/bin` is **330
lines and dispatches 7 verbs**, while `governance-rules` is **387 lines and dispatches
8**. The missing one is `verify`. So `command -v` succeeds, the agent calls `verify`
in good faith, and it fails. Ask the script itself what it can do:

```bash
# Ask THIS host's script what it actually implements. Its own --help is the only
# source that reflects this host — not the manifest, not a version, not a doc.
aimaestro_trdd_has () {   # $1 = verb
  command -v aimaestro-trdd.sh >/dev/null 2>&1 || return 1
  aimaestro-trdd.sh --help 2>/dev/null | grep -qE "^[[:space:]]+$1\b"
}

if ! command -v aimaestro-trdd.sh >/dev/null 2>&1; then
  echo "aimaestro-trdd.sh NOT AVAILABLE on this host — the ai-maestro TRDD CLI is absent."
  echo "Falling back to reading design/ directly; approvals cannot be minted or verified here."
  exit 3
fi

if ! aimaestro_trdd_has verify; then
  echo "aimaestro-trdd.sh is present but does NOT implement 'verify' on this host."
  echo "Approval authenticity CANNOT be checked here. Do NOT infer it from the card's prose."
  exit 3
fi
```

Never gate on a version string, and never infer a verb from
`docs/SCRIPT-MANIFEST.md` — the manifest is generated from `scripts/` on the
`governance-rules` tree and documents `verify`, which the deployed script does not
have. **A skill teaching a verb the shipped CLI lacks is exactly as broken as a
manifest promising one `main` does not ship.**

## Instructions

Full recipes: [Full step-by-step instructions](references/instructions.md):

- Step 1: Probe for the CLI
- Step 2: Search and read the board
- Step 3: Verify an approval (the token check)
- Step 4: Edit, promote, approve, refuse
- Step 5: Archive
- The authority model
- What verify does NOT prove
- Report

### The verbs

| Subcommand | Deployed? | Flags |
|---|---|---|
| `search` | ✅ | `--column C` `--id I` `--keyword K` `--zone proposals\|tasks\|archived\|refused` |
| `read <id>` | ✅ | — |
| `verify <id>` | ⚠️ **NOT on the deployed script — probe first** | exit `0` verified · **`2` NOT verified** · `1` error. **Flags UNSETTLED** — see below |
| `edit <id>` | ✅ | `--set k=v` (repeatable) — frontmatter in place, no folder move |
| `approve <id>` | ✅ | `--approver W` `--tier N` `--rationale R` — proposal → planned, `git mv` |
| `refuse <id>` | ✅ | `--approver W` `--tier N` `--reason R` — → `refused/` |
| `promote <id> --column C` | ✅ | `--note N` `--approver W` — advance in place |
| `archive <id> --state S` | ✅ | `--reason R` `--superseded-by ID` `--approver W` |

**The `verify` row is the reason this skill probes per-verb.** It is implemented on
`governance-rules` (`cmd_verify`, dispatched) and documented in the manifest, but the
copy deployed to `~/.local/bin` does not dispatch it (verified 2026-07-16; tracked in
ai-maestro#69). Treat it as *available only where the probe says so*. **`--tier` is a
CLAIM the server must validate against the caller's real title — never a grant**
(ai-maestro#69 §2).

> **`verify`'s FLAGS are not frozen yet — do not hardcode them** (ai-maestro-plugin#29,
> open as of 2026-07-16). The exit-code contract IS settled (`0` / `2` / `1`, mirroring
> `aimaestro-portfolio.sh verify`), and so is the token-not-prose property. But the
> posted frozen shape reads `verify <id> [--agent A]` with the verdict fields
> (`verified · token_id · issuer_agent_id · issuer_title · min_approval_requirement ·
> authority_sufficient · reasons[]`) on STDOUT, and whether **`--json`** survives is an
> open question CORE has asked and ai-maestro has not yet answered. So: rely on the
> **exit code**, read flags from the host's own `--help` at call time, and do not teach
> `--json` as given. Teaching an unsettled flag is the same error as teaching an
> undeployed verb.
>
> **A `min-approval-requirement: none` card verifies TRUE — that is correct, not a
> forgery.** Tier-0 work is legitimately unapproved-by-design. A verifier that cried
> forgery on routine `none` cards would be one people learn to ignore, which would cost
> more than it saves.

Global `--agent <uuid|name>` targets that agent's `<workdir>/design` corpus.
**Nothing is committed for you** — stage and commit the result yourself, by name.

`archive --state` accepts `completed`, `cancelled`, `superseded` and **refuses
`failed`**: a failed TRDD is retryable and stays open in `design/tasks/`; giving up
is an explicit `cancel`.

### The authority model

Approval authority is read from the card's own `min-approval-requirement:`
(`none < orchestrator < chief-of-staff < manager < user`). Two hard limits:

- **No agent may approve a `user`-tier card.** `user` is the top rung and is not an
  agent.
- **No one may approve their own proposal — MANAGER included.**

This MAINTAINER is a governance-layer peer: it self-authorizes floor-`none` work and
files manager-floor proposals directly to MANAGER.

### Verify reads a TOKEN, not prose

`approve` MINTS a host-signed, ledger-anchored `approval-token:` into the card's
frontmatter. `verify` answers **from that token** — it checks the signature, the R34
ledger anchor, that the issuer still holds its title, and that the issuer's authority
meets the card's `min-approval-requirement:`. It deliberately ignores
`approval-judge:` and the `## Approval log` prose, because prose is exactly what a
forger rewrites.

**Exit `2` is a real answer, not an error.** `0` verified · `2` NOT verified · `1`
error. Treat `2` as "this approval does not hold" and report it; do not retry it away.

**What verify does NOT prove — say this accurately.** The token binds an approval to
the card's **identity, not its content**. Anyone with repo write can edit the body
after approval and `verify` will still report the approval authentic — because it is.
Freezing content needs a card digest inside the token (`attestation_ref`, reserved).
**Never describe a verified approval as vouching for the card's body.**

## Output

One line per action, plus the verb's own exit code. A probe miss prints the explicit
degrade and exits `3`. A `verify` disagreement exits `2` and is reported as a
finding, not a failure to retry.

## Done when (terminating conditions)

- [ ] **Probe missing** — the CLI is absent: the degrade line was printed and exit
  `3` returned. This is a COMPLETE, correct outcome on an `install.sh` host — do not
  work around it by calling the server API or by reading `~/.local/bin`.
- [ ] **`search` / `read`** — the result is printed. Read-only; nothing to verify.
- [ ] **`verify`** — an exit code was obtained and reported: `0` verified, `2` NOT
  verified (a finding — report which card and that the approval does not hold), `1`
  error (investigate; do not report a verdict).
- [ ] **`edit` / `promote` / `approve` / `refuse` / `archive`** — the verb exited `0`
  AND the resulting change was staged and committed **by name** (the CLI commits
  nothing for you). An uncommitted mutation is not done.
- [ ] **Refusal is terminal too** — an authority refusal (own-proposal, `user`-tier)
  means the answer is "not permitted here"; escalate per the ladder, do not retry.

## Boundaries

- Does **not** author TRDDs — that is `maintainer-trdd-adr`.
- Does **not** commit. Stage by name; never `git add -A`.
- Does **not** call the ai-maestro server `/api/*` — the frozen CLI only.
- Does **not** modify another agent's corpus without an explicit `--agent` target.

## Resources

- [Full step-by-step instructions](references/instructions.md) — the runnable recipes.
- `docs/SCRIPT-MANIFEST.md` (ai-maestro, `governance-rules`) — the frozen contract;
  §5.3/§5.4 are why this skill exists.
- `aimaestro-trdd-approval.md` (ai-maestro, `governance-rules`, in rules/aimaestro/) — the
  canonical approval/mandate model.
