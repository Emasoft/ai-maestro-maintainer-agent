# Expression-injection hardening

The rewrite that turns an injectable `run:` block into a safe one. This
is the remediation side of zizmor's `template-injection` audit and
actionlint's script-injection warning. Detection lives in
`workflow-scan`; this file is HOW to fix.

## Table of Contents

- [The defect, in one sentence](#the-defect-in-one-sentence)
- [Attacker-controllable context fields](#attacker-controllable-context-fields)
- [The fix — env-var indirection](#the-fix--env-var-indirection)
- [Why `env:` works and quoting does not](#why-env-works-and-quoting-does-not)
- [What env-var indirection does NOT fix](#what-env-var-indirection-does-not-fix)
- [Workflow-command injection — a second channel](#workflow-command-injection--a-second-channel)
- [The rewrite procedure](#the-rewrite-procedure)

## The defect, in one sentence

GitHub substitutes a `${{ ... }}` expression's raw text into the shell
script BEFORE the shell parses it — so a `${{ ... }}` whose value an
outsider controls, placed inside a `run:` block, lets that outsider
write shell code, not merely supply a string.

```yaml
# VULNERABLE SHAPE — documentation only, never ship
- run: echo "PR title: ${{ github.event.pull_request.title }}"
```

If the title is ordinary text this echoes it. If the title is crafted
to close the string and open a command substitution, the substituted
text becomes part of the command line and runs on the runner. We do not
reproduce a working payload here; the shape above is enough to
recognise and fix.

## Attacker-controllable context fields

Severity is decided by the value's ORIGIN, not the sink. These fields
are, or can carry, text a stranger typed — treat every one as hostile
when it lands in a `run:` block:

| Context field | Who controls it |
|---|---|
| `github.event.pull_request.title` / `.body` | PR author (incl. forks) |
| `github.event.issue.title` / `.body` | issue author |
| `github.event.comment.body` | any commenter |
| `github.event.review.body` / `review_comment.body` | reviewer |
| `github.event.pull_request.head.ref` (branch name) | PR author |
| `github.event.pull_request.head.label` | PR author |
| `github.head_ref` | PR author |
| `github.event.head_commit.message` | any committer |
| `github.event.commits.*.message` / `.author.*` | any committer |
| `github.event.discussion.title` / `.body` | discussion author |
| `github.event.inputs.*` (`workflow_dispatch`) | whoever dispatched |
| `github.event.client_payload.*` (`repository_dispatch`) | the API caller |

GitHub-generated fields are safe: `github.sha`, `github.ref`,
`github.run_id`, `github.run_number`, `github.run_attempt`,
`github.actor`, `github.triggering_actor`, `github.job`,
`github.repository`, `github.event_name`. They cannot carry
attacker-authored shell (`actor` / `triggering_actor` are usernames,
restricted to GitHub-legal characters).

**Watch the whole-context dump.** `${{ toJSON(github) }}` (or
`toJSON(github.event)`) spliced inline into a `run:` block is the same
defect wearing a debug hat — the serialized object contains every
attacker-controllable field above, so an inline dump is injectable even
though it looks like harmless diagnostics:

```yaml
# VULNERABLE SHAPE — documentation only, never ship
- run: echo '${{ toJSON(github) }}'
```

The fix is the same env-var indirection: bind the dump to an `env:` entry
and echo the shell variable.

```yaml
# HARDENED SHAPE
- name: Dump context
  env:
    GITHUB_CONTEXT: ${{ toJSON(github) }}
  run: echo "$GITHUB_CONTEXT"
```

## The fix — env-var indirection

Bind the expression to an `env:` variable on the step, then reference
the **shell** variable (`$NAME`) inside `run:`. The expansion happens in
the environment, never in the script text:

```yaml
# HARDENED SHAPE
- name: Print PR title
  env:
    PR_TITLE: ${{ github.event.pull_request.title }}
  run: echo "PR title: $PR_TITLE"
```

For a value used as data by a program that must not misparse it, quote
the shell reference (`"$PR_TITLE"`) and, where the tool supports it,
pass it through the tool's own data channel rather than string
concatenation. The canonical case — building JSON with `jq` — has its
own worked walk-through in the Hardening-edits step of
[instructions.md](instructions.md) (the `--arg` trap).

Validating an untrusted input before use composes with indirection:

```yaml
- name: Build image
  env:
    IMAGE_NAME: ${{ github.event.inputs.image-name }}
  run: |
    case "$IMAGE_NAME" in
      *[!a-z0-9-]*) echo "::error::invalid image name"; exit 1 ;;
    esac
    docker build -t "$IMAGE_NAME" .
```

## Why `env:` works and quoting does not

Adding quotes around the `${{ ... }}` in the `run:` block is NOT a fix.
GitHub interpolates the raw value first; a value that itself contains a
matching quote closes the string the author added and the rest is shell
again. `env:` breaks the chain because the value never enters the script
source — the shell reads it from the process environment at run time,
where it is inert data. This is the single load-bearing reason the
rewrite targets `env:` and not "better quoting".

## What env-var indirection does NOT fix

Indirection defeats GitHub expression injection. It does NOT defeat a
second-stage shell expansion of the same variable. If the hardened
`run:` block later interpolates `$NAME` into another shell string that
is then re-evaluated (`eval`, a `jq` filter built by concatenation, a
`bash -c "$NAME"`), the danger is back. The `jq --arg` walk-through in
[instructions.md](instructions.md) is exactly this second-stage case,
and its rule generalises: every untrusted value enters each tool
through that tool's own data channel, never by string-splicing.

## Workflow-command injection — a second channel

Even with env-var indirection closing the shell channel, there is a
SECOND, independent injection channel: the Actions **runner** parses every
line a step writes to stdout for workflow commands of the form
`::name::value` (`::error::`, `::add-mask::`, `::set-output::`,
`::stop-commands::`, …). So a step that echoes untrusted text — a PR
title, an issue body — hands the *runner* whatever `::...::` lines that
text contains. The attacker is no longer writing shell; they are writing
workflow commands: forging an output another step trusts, hiding a real
value from the masking, or emitting `::stop-commands::` to switch command
parsing off entirely.

This bites precisely when a step must legitimately print untrusted
content (echo a PR title into a log, `cat` an untrusted file into
`$GITHUB_STEP_SUMMARY`). Env-var indirection does not help here — the
danger is the *printing itself*, not the interpolation.

The fix is a `stop-commands` fence with an unguessable token around the
untrusted echo, so any `::...::` in the content is treated as literal
text, then re-enable command processing:

```yaml
# HARDENED SHAPE — fence untrusted output so :: lines are inert
- name: Echo untrusted title
  env:
    PR_TITLE: ${{ github.event.pull_request.title }}
  run: |
    TOKEN="$(uuidgen)"
    echo "::stop-commands::$TOKEN"   # command parsing OFF
    echo "$PR_TITLE"                  # any ::...:: inside is now literal
    echo "::$TOKEN::"                 # command parsing back ON
```

Prefer, where possible, NOT echoing untrusted data at all — write it to a
file and reference the path. Flag any step that prints an
attacker-controllable value to stdout or to `$GITHUB_STEP_SUMMARY`
without a fence; route the rewrite the same way as a shell-injection
rewrite (perform it, but STOP and escalate if the fence would change the
step's meaning).

## The rewrite procedure

For each injectable `run:` block the scan flagged:

1. Read the block and 1-2 lines of surrounding context (Read + Edit —
   never sed/awk on YAML).
2. Add or extend the step's `env:` block, one entry per untrusted
   `${{ ... }}` value, with an UPPER_SNAKE name.
3. Replace every `${{ ... }}` occurrence inside `run:` with the shell
   reference `"$NAME"`.
4. If the value flows into a JSON builder / HTTP client / webhook, apply
   the tool's data-channel discipline to EVERY interpolated value —
   partial coverage is no coverage.
5. Re-validate: `python3 -c "import yaml; yaml.safe_load(open(F))"`,
   then `actionlint F`, then the `workflow-scan` post-sweep. zizmor must
   report zero `template-injection` findings for the block.

This is a security rewrite of shell logic, so it is a hardening edit
`workflow-fix-safe` performs — but never one it applies blindly. If the
rewrite changes the program's meaning (a value that was genuinely meant
to be a shell fragment), STOP and route it to human review rather than
guess.
