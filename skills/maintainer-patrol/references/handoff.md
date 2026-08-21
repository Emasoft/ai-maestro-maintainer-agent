# AMP message template — patrol handoff (R15.7)

Sent when patrol state must survive the session that produced it: hibernation,
host migration, or handing the repo to a successor session. The sibling template
is
[approval-request.md](../../maintainer-approval-gate/references/approval-request.md).

A handoff is a **status report about durable state**, not a work order. It names
where the state lives so the successor reads the files rather than trusting a
summary of them.

## Contents

- [What the successor actually needs](#what-the-successor-actually-needs)
- [The message](#the-message)
- [Degrade](#degrade)

## What the successor actually needs

Most patrol state is already on disk under the agent working directory — that is
deliberate, so AI Maestro's backups and host-to-host migration carry it (see
[patrol-loop.md](patrol-loop.md) for the ledger and baseline paths). The
handoff points at that state and adds only what a file cannot say: what is
half-done, and what is waiting on a human.

The three that bite if omitted:

- **An open approval gate.** A fix halted at `needs-approval` is invisible in the
  ledger's disposition alone — say which issue, and which fingerprint was
  published, or the successor re-runs CHECK and republishes a second one.
- **A T5 stop.** A suspected secret leak stops the loop by design. If the alert
  was raised and not yet acknowledged, the successor must not "resume patrol"
  and quietly clear it.
- **A guardian-skip streak.** Repeated pre-emption means routed work is not
  landing; the successor should look at why before adding another cycle.

## The message

Body opens with the self-id line, same as every AMP message and every GitHub
write.

```bash
aimaestro-message.sh send "$RECIPIENT" \
  --subject "HANDOFF — <repo> patrol state" --body - --priority normal <<'EOF'
This is the Claude responsible for the ai-maestro-maintainer-agent project.

Repo: <owner/repo>
State dir: $AGENT_DIR/.aimaestro/state/   (ledger + guardian baseline; read these)
Last cycle: <ISO> — disposition <triaged|fixed|guardian-skip|...>

Open gates: <issue #N awaiting approve-protected-edit <fingerprint>, or: none>
T5 outstanding: <yes — alert raised <ISO>, unacknowledged | no>
In flight: <what was mid-fix and where it stopped, or: nothing>
Next action: <the one concrete step the successor should take first>
EOF
```

Where the CLI is absent, the degrade path is the legacy
`amp-send "$RECIPIENT" "HANDOFF — <repo> patrol state" "<the same body>" --priority normal`.

`Next action` is one runnable step, not a plan. If you cannot name one, the
handoff is not ready to send.

## Degrade

No fleet session, no AMP: NEITHER `aimaestro-message.sh` nor `amp-send` on PATH
(or the CLI exits 3, transport unavailable) → write the same content
to the patrol report under `$MAIN_ROOT/reports/maintainer-patrol/` and say so.
The state on disk is what makes the handoff recoverable; the message is only the
pointer to it.
