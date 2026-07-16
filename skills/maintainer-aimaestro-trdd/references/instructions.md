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

```bash
if ! command -v aimaestro-trdd.sh >/dev/null 2>&1; then
  echo "aimaestro-trdd.sh NOT AVAILABLE — the ai-maestro TRDD CLI is absent on this host."
  echo "Read design/ directly instead; approval tokens cannot be minted or verified here."
  exit 3
fi
```

**Why this is mandatory.** `install.sh` clones ai-maestro without `--branch`, so a
provisioned host tracks `main` — which ships only a subset of the scripts and none of
the governance docs. The full surface exists where the `governance-rules` tree is run
directly. So the manifest listing a script does **not** mean this host has it, and a
host's `~/.local/bin` is residue (the installer copies, never prunes) — a deleted
script lingers there and a fresh install simply lacks it.

Never gate on a version string. A version tells you what a tree *intends* to ship;
`command -v` tells you what is *here*.

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
aimaestro-trdd.sh verify 27IG72GX --json
case $? in
  0) echo "VERIFIED — the approval token holds" ;;
  2) echo "NOT VERIFIED — this card's approval does not hold (a FINDING, report it)" ;;
  1) echo "ERROR — could not evaluate; do not report a verdict" ;;
esac
```

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
