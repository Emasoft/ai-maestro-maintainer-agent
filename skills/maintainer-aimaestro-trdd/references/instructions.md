# maintainer-aimaestro-trdd — runnable recipes

Everything here drives `aimaestro-trdd.sh`, ai-maestro's Tier-A TRDD CLI. The CLI is
the single source of truth for what a card says; these are the recipes for driving it
safely, plus the two things that are easy to get wrong and expensive to get wrong (the
probe, and what `verify` actually proves).

## Table of Contents

- [Step 1: Probe for the CLI](#step-1-probe-for-the-cli)
- [Step 2: Search and read the board](#step-2-search-and-read-the-board)
- [Step 3: Verify an approval (the token check)](#step-3-verify-an-approval-the-token-check)
- [Step 4: Edit, promote, approve, refuse](#step-4-edit-promote-approve-refuse)
- [Step 5: Archive](#step-5-archive)
- [The authority model](#the-authority-model)
- [What verify does NOT prove](#what-verify-does-not-prove)
- [Report](#report)

## Step 1: Probe for the CLI

Two probes, because the script existing does not mean the verb exists:

```bash
# (a) is the CLI here at all?
if ! command -v aimaestro-trdd.sh >/dev/null 2>&1; then
  echo "aimaestro-trdd.sh NOT AVAILABLE — the ai-maestro TRDD CLI is absent on this host."
  echo "Read design/ directly instead; approvals cannot be minted or verified here."
  exit 3
fi

# (b) does THIS host's copy implement the verb I am about to call?
#     Its own --help is the only source that describes THIS host.
aimaestro_trdd_has () {   # $1 = verb
  aimaestro-trdd.sh --help 2>/dev/null | grep -qE "^[[:space:]]+$1\b"
}
```

**Why the second probe is not paranoia — the deployed copy MOVES, silently, in both
directions.** Two measurements of the same path, five weeks apart:

| measured | `~/.local/bin/aimaestro-trdd.sh` | lines | verbs dispatched |
|---|---|---|---|
| 2026-07-16 | deployed | 330 | search read edit approve refuse promote archive — **7** (no `verify`) |
| 2026-07-16 | `scripts/…` @ `governance-rules` | 387 | the same **+ `verify`** — **8** |
| **2026-08-21** | **deployed** | **627** | **+ `create` and `verify`** — **9** |

On 2026-07-16 `command -v` passed and `verify` still failed (ai-maestro#69). By
2026-08-21 the deployed copy had gained it — no announcement, no version bump, and
nothing in the repo said so. **A skill teaching a verb the shipped CLI lacks is exactly
as broken as a manifest promising one `main` does not ship — and a skill still denying
a verb the CLI has since gained is that same defect wearing the other face.** Neither
row above is the answer; the host you are on is. So probe the verb at call time, and
degrade explicitly when it is absent:

```bash
if aimaestro_trdd_has verify; then
  aimaestro-trdd.sh verify "$ID" --json
else
  echo "verify is NOT implemented on this host — approval authenticity cannot be checked."
  echo "Do NOT substitute the card's approval-judge:/Approval log prose for a real check."
  exit 3
fi
```

**Why any of this is mandatory.** `install.sh` clones ai-maestro without `--branch`,
so a provisioned host tracks `main` — which ships only a subset of the scripts and
none of the governance docs. The full surface exists where the `governance-rules` tree
runs directly. So the manifest listing a script (or a verb) does **not** mean this host
has it, and a host's `~/.local/bin` is residue (the installer copies, never prunes) —
a deleted script lingers there and a fresh install simply lacks it.

Never gate on a version string. A version tells you what a tree *intends* to ship;
the script's own `--help` tells you what is *here*.

## Step 2: Search and read the board

```bash
aimaestro-trdd.sh search --column dev
aimaestro-trdd.sh search --zone proposals
aimaestro-trdd.sh search --keyword worktree
aimaestro-trdd.sh read 27IG72GX
```

`--agent <uuid|name>` targets another agent's `<workdir>/design` corpus; omit it for
this workdir.

## Step 3: Verify an approval (the token check)

```bash
# Rely on the EXIT CODE — it is the settled half of the contract.
# Read the flags from the host's own --help at call time; do NOT hardcode --json
# (see "verify's flags are not frozen" below).
aimaestro-trdd.sh verify 27IG72GX
case $? in
  0) echo "VERIFIED — the approval token holds" ;;
  2) echo "NOT VERIFIED — this card's approval does not hold (a FINDING, report it)" ;;
  1) echo "ERROR — could not evaluate; do not report a verdict" ;;
esac
```

**`verify`'s flags are not frozen yet** (ai-maestro-plugin#29, open 2026-07-16). Settled:
the exit codes (`0`/`2`/`1`, mirroring `aimaestro-portfolio.sh verify`) and the
token-not-prose property. Unsettled: the posted frozen shape reads
`verify <id> [--agent A]` and emits the verdict fields (`verified · token_id ·
issuer_agent_id · issuer_title · min_approval_requirement · authority_sufficient ·
reasons[]`) on STDOUT — whether **`--json`** survives is an open question CORE asked and
ai-maestro has not answered. Teaching an unsettled flag is the same error as teaching an
undeployed verb, so branch on the exit code and discover flags from `--help`.

**A `min-approval-requirement: none` card verifies TRUE.** That is correct, not a
forgery: Tier-0 work is unapproved by design. A verifier that cried forgery on routine
`none` cards is one people learn to ignore — and an ignored verifier protects nothing.

**Exit `2` is an answer, not a failure.** It means the approval does not hold. Report
which card and stop — do not retry it away, and do not fall back to believing the
card's prose.

`verify` reads the `approval-token:` minted by `approve`: a host-signed,
ledger-anchored token pinned to that card. It checks the signature, the R34 ledger
anchor, that the issuer **still** holds its title, and that the issuer's authority
meets the card's `min-approval-requirement:`. It ignores `approval-judge:` and the
`## Approval log` line entirely — prose is exactly what a forger rewrites, so the only
thing taken from the file is the token id.

Consequences worth internalising: a COS-issued token cannot satisfy a manager-floor
card, and no agent token can ever satisfy a `user`-floor one.

## Step 4: Edit, promote, approve, refuse

**Every verb in this step is a STRICT route — mint `AID_AUTH` first.** They 401/403
without it; `search`/`read`/`verify` do not. This plugin is an AGENT caller, so the
agent half of the R32 dual path applies (a USER caller would use `AIMAESTRO_SUDO_TOKEN`
instead). The script's own `--help` calls `AID_AUTH` **"REQUIRED — no localhost
exemption"**:

```bash
export AID_AUTH="$(aid-auth.sh)"   # once, before any write verb below
```

A 401/403 is an authority answer, not a transport error: report it and stop. Do not
retry it, and do not read it as "the CLI is broken". Note the deployed header still
opens *"the local owner needs none"* two lines above the strict-route rule that
contradicts it (ai-maestro#149, fixed upstream, not yet redeployed) — believe `--help`
and the exit code.

```bash
# frontmatter in place, no folder move
aimaestro-trdd.sh edit 27IG72GX --set priority=high --set assignee=ai-maestro-maintainer-agent

# advance a column in place
aimaestro-trdd.sh promote 27IG72GX --column dev --note "phase 1 landed" --approver ai-maestro-maintainer-agent

# proposal -> planned, git mv proposals/ -> tasks/, MINTS the approval token
aimaestro-trdd.sh approve <id> --approver <who> --tier <N> --rationale "<why>"

# -> refused/
aimaestro-trdd.sh refuse <id> --approver <who> --tier <N> --reason "<why>"
```

**Nothing is committed for you.** After any write verb, stage the changed paths **by
name** and commit with the TRDD id in the subject:

```bash
git add design/tasks/TRDD-...-27IG72GX-....md
git commit -m "chore(trdd): promote TRDD-27IG72GX to dev"
```

Never `git add -A` — it stages whatever else happens to be untracked.

## Step 5: Archive

```bash
aimaestro-trdd.sh archive <id> --state completed  --reason "shipped in v1.8.0"
aimaestro-trdd.sh archive <id> --state cancelled  --reason "no longer wanted"
aimaestro-trdd.sh archive <id> --state superseded --superseded-by <newer-id>
```

`--state` accepts `completed`, `cancelled`, `superseded` — and **refuses `failed`**.
That refusal is correct and load-bearing: a failed TRDD is *retryable* and stays open
in `design/tasks/`; there is no "archive as failed". Deciding to give up is an
explicit `cancel`, which is a different, deliberate act — and the refusal is what
stops a bad day from being silently filed away as a conclusion.

## The authority model

Approval authority is read from the card's own `min-approval-requirement:`, on one
ladder:

```text
none < orchestrator < chief-of-staff < manager < user
```

Two hard limits the CLI enforces:

- **No agent may approve a `user`-floor card** — `user` is above the whole ladder and
  is not an agent.
- **No one may approve their own proposal** — MANAGER included.

A refusal on either ground is a terminal, correct answer: escalate per the ladder,
do not retry.

## What verify does NOT prove

The token binds an approval to the card's **identity, not its content**. Anyone with
repo write can edit the body *after* approval and `verify` will still report the
approval authentic — because it is: the approval genuinely happened, for that card.
Freezing content would need a card digest inside the token (`attestation_ref`,
reserved, not implemented).

**So never describe a verified approval as vouching for the card's body.** Saying
"verify passed, therefore this plan is approved as written" is a false claim, and it
is the exact claim someone editing a body post-approval would want you to make.

## Report

```bash
MAIN_ROOT="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
DIR="$MAIN_ROOT/reports/maintainer-aimaestro-trdd"
mkdir -p "$DIR"
REPORT="$DIR/$(date +%Y%m%d_%H%M%S%z)-trdd-cli.md"
```

`--porcelain` is mandatory: plain `git worktree list` prints `<path> <sha> [<branch>]`,
so any column split truncates a path containing a space and silently names a directory
that does not exist.
