# AMP message template — approval request (R15.7)

The MAINTAINER has no CHIEF-OF-STAFF, so every approval it cannot
self-authorize goes **directly to MANAGER** (R6/R19). This is the shape of
that message. The sibling template is
[handoff.md](../../maintainer-patrol/references/handoff.md).

## Contents

- [When you send this](#when-you-send-this)
- [Resolve the recipient BEFORE composing](#resolve-the-recipient-before-composing)
- [The message](#the-message)
- [Recording the answer](#recording-the-answer)
- [When the answer is "no"](#when-the-answer-is-no)
- [The protected-edit variant (human, not AMP)](#the-protected-edit-variant-human-not-amp)

## When you send this

| Trigger | Floor |
|---|---|
| Destructive git — force-push, history rewrite, tag/branch deletion (R19.7) | `manager` |
| Deviating from the ratified baseline rulesets (adding a bypass actor, loosening a rule, disabling a check) | `manager` |
| Entering the release pipeline on a TRDD you own | `manager` |
| Anything golden / owner-identity — MANAGER forwards it to USER | `user` |

Applying the baseline **as-is** is Tier 0 — no message, just do it. Sending an
approval request for exempt work trains the reader to skim the ones that matter.

## Resolve the recipient BEFORE composing

**Primary path — `aimaestro-message.sh` (spec'd CLI, TRDD-0AB76JG3, v1.0.0+):**
a thin transport over the same AMP pipeline (R6 gate, AID, log all apply), with
DISTINGUISHABLE failures. `manager-<host>` is a placeholder, not a name —
sending to it fails at the moment you most need it to work.

```bash
if command -v aimaestro-message.sh >/dev/null 2>&1; then
  MANAGER=$(aimaestro-message.sh resolve manager | cut -f1)
  case $? in
    0) : ;;            # exactly one match — proceed
    4|5) : ;;          # ZERO or AMBIGUOUS → ask the authorized user which
                       # MANAGER to address. Never guess a recipient for a
                       # destructive-op approval.
    3) : ;;            # transport/registry unavailable → not a fleet session;
                       # degrade with ONE loud warning, continue patrol
    7) : ;;            # AID_AUTH missing/invalid → real fleet misconfig; warn
                       # ONCE loudly (a mandate may rot behind it), continue
  esac
fi
```

**Fallback — `amp-send` (same pipeline), only when the CLI is absent** on a
host whose deploy predates it:

```bash
command -v amp-send >/dev/null 2>&1 || exit 0   # neither CLI: not a fleet session
MANAGER=$(jq -r 'keys[] | select(test("manager"))' \
  ~/.agent-messaging/agents/.index.json 2>/dev/null | head -1)
# jq fallback cannot distinguish "no registry" from "no match" — treat any
# empty result as ask-the-user, never as "nobody to notify".
```

Fall back to `--id <uuid>` when the name is ambiguous.

## The message

Body **must** open with the self-id line — all AI Maestro agents share the one
human-owner identity, so the recipient cannot otherwise tell which Claude wrote
this (PRRD G1.1, and R22 for the GitHub equivalent).

```bash
aimaestro-message.sh send "$MANAGER" \
  --subject "APPROVAL REQUEST — TRDD-<id8> <one-line summary>" \
  --body - --priority normal <<'EOF'
This is the Claude responsible for the ai-maestro-maintainer-agent project.

TRDD: design/tasks/TRDD-<...>.md
min-approval-requirement: manager
Requested: <column> → <column>   (or: the exact operation, for a non-TRDD ask)
Rationale: <why this, why now — one line>
Impact: <what changes the moment it is approved>
Reversible: <yes | no | compensable-by: ...>
Blocked-on-this: <what is stalled until you answer, if anything>
EOF
```

On exit 0 the CLI prints the **message-id** — record it in the TRDD's
`## Approval log`. Non-zero always carries a stderr reason: 3 transport, 4
recipient not found, **6 = R6 REFUSED with the server's routing hint verbatim
on stderr — follow the hint**, 7 auth. Never pass `--from` from an agent (the
server overrides the sender with the AID-verified identity; the flag is the
human-owner path only); `--type` defaults to `notification` and is fine as-is.
With the legacy `amp-send` fallback the invocation is
`amp-send "$MANAGER" "<subject>" "<body>" --priority normal`.

Use `--priority high` only when something is genuinely blocked on the answer.

`min-approval-requirement:` names the TITLE that must approve —
`none | orchestrator | chief-of-staff | manager | user`. **`approval-tier: N` is
retired**: never write it, decode it only when reading a legacy card
(`0→none, 1→chief-of-staff, 2→manager, 3→user`). Field semantics are defined
once, in
[trdd-template.md](../../maintainer-trdd-adr/references/trdd-template.md) —
this template does not restate them.

## Checking for the answer

Poll `aimaestro-message.sh replies <message-id> [--limit N]` with the id the
send printed — TSV rows of inbox messages replying to it. Exit 0 = rows (read
them), 4 = none yet (keep working, re-check on a later wake — never spin-wait),
3 = transport unavailable, 7 = auth. This replaces scanning the whole
`amp-inbox` for the MANAGER's reply; the inbox drain on wake still happens
regardless (a MANAGER may answer with a fresh message instead of a reply).

## Recording the answer

The decision goes in the TRDD's `## Approval log`, in this exact line shape:

```
- <ISO> — APPROVED|REFUSED by <approver> (min-approval-requirement: <title>). <reason>
```

Archiving must never overwrite the original approver, and a supersede records
`approved: false` while STRIPPING the judge/datetime — attributing a decision to
someone who never made one is a lie that every later grep repeats.

## When the answer is "no"

A refusal is a **design review, not a prohibition**. Do not abandon the need,
and do not delete or strip working code that depended on the proposal on a bare
"no" — that binds from draft time, so never pre-concede destruction in the ask
itself. Read the stated defect and the bar for acceptance, then re-propose.

## The protected-edit variant (human, not AMP)

A protected-path edit is approved by `$AUTHORIZED_USER` **on the GitHub issue**,
not over AMP — that flow, its `approve-protected-edit <fingerprint>` grammar and
the replay-proof diff binding live in
[protected-paths.md](protected-paths.md). Same self-id rule applies to the
comment body.
