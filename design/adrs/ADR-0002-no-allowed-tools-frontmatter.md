# ADR-0002 — No `allowed-tools` frontmatter; dynamic tool surface

Status: accepted
Date: 2026-05-27
Authors: Emasoft

## Context

Claude Code skills can optionally declare an `allowed-tools:` field in
their YAML frontmatter, restricting which tools the agent may invoke
while that skill is loaded. Conventional wisdom in the Claude Code
plugin ecosystem (as of v2.1.x) sits on a spectrum:

- **Restrictive**: list every tool explicitly. Pros: smallest blast
  radius if the skill is buggy or hijacked. Cons: the skill breaks
  the moment a tool is renamed, the agent needs a tool not on the
  list, or a new MCP server is added.
- **Permissive / absent**: omit the frontmatter; the agent inherits
  the full tool surface from its top-level definition. Pros: skills
  compose freely; new tools work without per-skill maintenance. Cons:
  a buggy skill can use any tool.

Our skill set (`maintainer-*`, `workflow-*`) tends to:

1. Invoke `gh`, `git`, `uv`, `uvx`, `bash`, `python3` via the Bash
   tool — across many different command shapes.
2. Read / edit / write files via Read / Edit / Write.
3. Spawn sub-agents via Agent (currently no skill does this, but the
   main agent does).
4. Call MCP tools opportunistically (SERENA for symbol search,
   `llm-externalizer` for cost-effective batch analysis).

The set of `Bash` command shapes is open-ended (every detector,
fixer, gh API call, git command, sandbox driver). Enumerating them
in `allowed-tools:` produces brittle skills that break every time we
add a new gh subcommand or a new utility.

Furthermore, the agent's primary safety mechanism is NOT a
per-skill tool allow-list — it is:

- The **approval-gate skill** that refuses to commit any diff
  touching a protected path without `approve-protected-edit` from
  `$AUTHORIZED_USER`.
- The **adversarial-content scan** in maintainer-triage that
  refuses to treat issue bodies as instruction sets.
- The **sandbox harness** that runs untrusted code in
  `--cap-drop=ALL --read-only --network none` containers.

These three are far stronger than any per-skill tool allow-list
could be, because they operate at the action layer (where the
mutation actually happens), not the tool layer (where mere invocation
is gated).

## Decision

We do NOT declare `allowed-tools:` in any SKILL.md frontmatter. Every
skill inherits the full tool surface of the agent that loads it.

Safety is enforced at three layers:

1. **maintainer-approval-gate** — runs CHECK mode before every
   commit; HALTS on protected-path edits.
2. **maintainer-triage adversarial-content scan** — refuses to treat
   imperative-mood text in untrusted inputs as instructions.
3. **maintainer-sandbox harness** — runs anything that takes
   untrusted code in a hardened Docker container with no network /
   no caps / read-only rootfs / project mount `:ro`.

A new skill in this plugin inherits the same safety story
automatically as long as it invokes the gate before any commit that
might touch a protected path.

## Consequences

**Easier:**

- New skills work immediately. No per-skill frontmatter audit needed
  when adding a tool or upgrading Claude Code.
- The agent composes skills freely. A skill that ships its own
  detection logic can also invoke `gh`, `git`, `uv` without a
  frontmatter dance.
- Reviewers focus on the three real gates (approval, triage,
  sandbox) rather than chasing every `Bash`-tool incantation.

**More difficult:**

- A buggy skill *could* in principle invoke any tool. We accept
  this risk because the three action-layer gates above are
  stronger guarantees than a tool-name allow-list.
- A skill that intentionally needs a NEW tool category (e.g.
  network access from the main agent's WebFetch) gets it
  automatically. Reviewers must spot this in PR review, not in a
  static frontmatter check.

**Neutral:**

- This decision is reviewable: if a future incident demonstrates
  that the three action-layer gates are insufficient, ship a
  superseding ADR and add `allowed-tools:` to the skills that
  introduced the risk.

## References

- Claude Code skill frontmatter docs (as of v2.1.x).
- `skills/maintainer-approval-gate/references/protected-paths.md`
  — the canonical protected-paths list.
- `skills/maintainer-triage/references/classification-paths.md`
  — adversarial-content detection patterns.
- `scripts/sandbox/sandbox.py` lines 333-358 — Docker harness safety
  invariants.
