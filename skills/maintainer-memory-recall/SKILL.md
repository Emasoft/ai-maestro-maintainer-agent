---
description: |
  Use when the maintainer agent should recall durable project
  memories from a SYMPTOM before debugging, deciding, or acting on
  a recurring problem — especially a recurring GitHub alert/issue,
  a familiar CI failure, or a ruleset/publish question already
  settled in a past session. Searches the project's markdown
  memory notes with memgrep (degrading to plain grep when memgrep
  is absent), ranking notes by how well the symptom query hits
  each note's description/title/tags.
  Trigger with phrases like "have we hit this before", "recall
  memories about X", "did we already solve this", "search the
  memory notes", or "check what we learned about Y".
---

# maintainer-memory-recall — symptom-first recall of project memory notes

## Overview

Recall is the FIRST step before debugging a recurring problem, making a
design decision, or acting on a recurring GitHub alert — "have we hit
this before?". It searches the project's curated markdown memory notes
(the `memory/` dir the harness maintains) and returns the notes whose
`description`/`title`/`tags` best match the SYMPTOM. The answer is in
the matched note's body.

This is distinct from conversation/transcript search: it recalls
*curated, symptom-indexed notes*, not raw chat history.

**The one law:** query with the SYMPTOM — the user's words, the error
text, the alert text — NOT the answer's jargon. A note is findable from
the symptom because its author put symptom vocabulary in `description`.

## Prerequisites

- None hard. `memgrep` (a Rust binary from the `ai-maestro-janitor`
  repo's `tools/memgrep`) gives ranked recall when present; when it is
  absent the skill falls back to plain `grep` — recall degrades, never
  breaks. Install once with
  `cargo install --path <janitor-repo>/tools/memgrep`.

## Instructions

1. Resolve the project memory dir (the harness per-project notes dir):

   ```bash
   MEMDIR="$HOME/.claude/projects/$(pwd | sed 's#/#-#g')/memory"
   # If that path doesn't exist, fall back to a project-local memory/ dir:
   [ -d "$MEMDIR" ] || MEMDIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)/memory"
   ```

2. Build a SYMPTOM query from the user's words / the error / the alert
   (never the answer's jargon), then recall — memgrep if present, plain
   grep otherwise:

   ```bash
   SYMPTOM="the symptom in the user's / the error's words"
   if command -v memgrep >/dev/null 2>&1; then
     memgrep recall "$SYMPTOM" "$MEMDIR"        # ranked best-first: path — description
   else
     grep -rliE "$SYMPTOM" "$MEMDIR" 2>/dev/null # fallback: degrade, never break
   fi
   ```

3. Read the top 1-3 notes returned — the fact you need is in their
   bodies, and memgrep auto-appends each note's `[^N]` lessons (the WHY
   behind the facts; read those too). If recall returns nothing, the
   memory doesn't exist yet — solve the problem, then capture it with
   `maintainer-memory-recall`'s write counterpart
   (`maintainer-memory-write`).

4. Optional refinements when memgrep is present (verify with
   `memgrep recall --help`):

   ```bash
   memgrep recall "$SYMPTOM" "$MEMDIR" --sort lmd            # newest-modified first
   memgrep recall "$SYMPTOM" "$MEMDIR" --since 2026-06-01    # only recent notes
   memgrep find "+ruleset -tag" "$MEMDIR"                    # AND/exclude keyword search
   memgrep find "+publish" "$MEMDIR" --only-notes            # search ONLY the lessons
   ```

## Output

A short ranked list of `path — description` lines (memgrep) or matching
paths (grep fallback), best first. Read the top few; do NOT dump full
note bodies into the conversation — open the one you need.

## Error Handling

- `memgrep` missing → the `command -v` gate routes to the grep
  fallback automatically; report nothing, just degrade.
- `MEMDIR` missing/empty → report "no memory notes yet" and continue
  with the task; never block on an empty corpus.
- grep returning nothing on a real symptom → retry once with a shorter,
  more symptom-flavored query before concluding the memory is absent.

## Examples

```text
User: the publish push got rejected again with GH013
→ recall "publish push rejected GH013 branch protection" → surfaces the
  two-ruleset note; read it WHOLE (facts + lessons) before touching rulesets.

User: have we seen this tee/head truncation before?
User: recall what we decided about the baseline rulesets
User: check the memory notes about CPV false positives
```

## Scope

ONLY searches + surfaces existing memory notes (read-only). Does NOT
write notes (use `maintainer-memory-write`). Degrades to plain grep when
memgrep is absent; never blocks on a missing binary.

## Resources

- `rules/memory-protocol.md` — the MAINTAINER memory protocol (the law,
  the schema, the read-the-notes rule, the dual-test method).
- `maintainer-memory-write` — the WRITE side (authoring + the
  non-destructive correction protocol).
- The memgrep tool reference doc (SKILL.md under the janitor repo's
  memgrep tool dir) — the `ai-maestro-janitor` repo owns and
  distributes the binary.
