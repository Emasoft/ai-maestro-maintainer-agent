---
description: |
  Use when the maintainer agent should capture a durable, reusable
  fact as a markdown memory note so a future session recalls it
  from the SYMPTOM — after solving a non-trivial bug (bug-autopsy
  gotcha), fixing a CVE or ruleset-drift incident, learning a repo
  constraint not derivable from code, a confirmed user preference,
  or any "we should remember this" moment. Writes a schema-valid
  note (name/description/metadata + body) with the description
  indexed by question/symptom vocabulary, and appends the
  MEMORY.md index line.
  Trigger with phrases like "remember this", "save a memory",
  "capture this gotcha", or "note that for next time".
---

# maintainer-memory-write — capture one durable fact, symptom-indexed

## Overview

Capture one durable fact as a memory note so a future session — which
will have the SYMPTOM, not the answer — can recall it. The load-bearing
decision is the `description`: it MUST carry the words the problem will
present with (the user's words, the error, the alert), because recall
ranks on `description` (+ `title` + `tags`). Put the symptom in
`description`; put the answer in the body.

Only capture what is NON-OBVIOUS and reusable: operational gotchas (CVE
handling, ruleset-drift fixes, publish-gate quirks), constraints not in
the code, confirmed preferences, hard-won debugging facts. Do NOT
capture what the repo already records (code structure, git history,
CLAUDE.md) or what only matters to the current conversation.

## Prerequisites

- None hard. `memgrep` improves the duplicate-check (step 3); without
  it the grep fallback applies. Writing itself needs no binary.

## Instructions

1. Resolve the memory dir (same as recall):

   ```bash
   MEMDIR="$HOME/.claude/projects/$(pwd | sed 's#/#-#g')/memory"
   [ -d "$MEMDIR" ] || MEMDIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)/memory"
   mkdir -p "$MEMDIR"
   ```

2. Choose `type` ∈ `user | feedback | project | reference` and a kebab
   slug (prefix the slug with the type, e.g. `feedback_…`,
   `reference_…`).

3. Check for an existing note that already covers this (update it
   rather than duplicate):

   ```bash
   if command -v memgrep >/dev/null 2>&1; then
     memgrep recall "<symptom>" "$MEMDIR"
   else
     grep -rliE "<symptom>" "$MEMDIR" 2>/dev/null
   fi
   ```

4. Author the note file inside `$MEMDIR` — filename is the step-2 slug
   plus the markdown extension — with the Write tool (NOT echo), schema:

   ```yaml
   ---
   name: <type>_<slug>
   description: "<the SYMPTOM in the user's / the error's words — the words a future session will search with, NOT the answer's jargon>"
   metadata:
     node_type: memory
     type: <user|feedback|project|reference>
   ---
   <the one fact. For feedback/project, follow with **Why:** and **How to apply:** lines.
   Link related notes with [[their-name]].>
   ```

5. Append a one-line pointer to `"$MEMDIR/MEMORY.md"` (create if
   missing): a list item that links the note Title to the note's
   filename, then an em-dash and a one-line hook.

6. Sanity-check: would a future session, having only the SYMPTOM, find
   this note by searching `description`? If the description reads like
   the *answer*, rewrite it to read like the *question*.

### Correcting a memory — the 2-step non-destructive protocol

When a new discovery CONTRADICTS an existing memory:

1. **Clean the fact in place.** Replace the wrong statement in the body
   with the correct one — the body is always the current truth, with no
   "we used to think X" clutter inline.
2. **Demote the error to a lesson — the WHY is the point.** Record the
   error as a numbered `[^N]:` entry under a bottom `## Notes and
   lessons learned` section, connected to the corrected fact with a
   standard-markdown footnote `[^N]`, with a leading
   `[ocd:YYYY-MM-DD lmd:YYYY-MM-DD]` date prefix. The load-bearing
   content is *why* the previous statement was wrong (root cause), not
   merely "this was wrong" — a lesson without a WHY cannot stop the
   next repeat.

The fact is corrected; the error is never deleted — it is demoted to a
linked lesson so future readers don't repeat it.

## Output

One note file + one MEMORY.md index line. Report the note path and the
one-line description; do NOT echo the whole note back into the
conversation.

## Error Handling

- Duplicate found in step 3 → update that note (correction protocol if
  contradicting) instead of creating a sibling.
- `MEMDIR` not writable → report the path and stop; never write notes
  into the repo working tree as a workaround.
- Description reads like the answer → rewrite before saving (step 6 is
  mandatory, not advisory).

## Examples

```text
After fixing a publish-gate failure caused by upstream scanner FPs:
  description: "publish blocked / CPV strict exit 3 but the findings look wrong"
  body: explains the upstream-FP mechanism + where the suppression decision lives.

User: remember that the baseline rulesets are applied as-is, Tier 0
  → type: project; description carries "can I apply the branch rulesets
    without asking / what approval does baseline hardening need".
```

A corrected note (fact cleaned in body, error demoted to a dated lesson):

```markdown
---
name: reference_tag_protect_rules
description: "which rules does the tag ruleset enforce / can publish.py still create tags"
metadata:
  node_type: memory
  type: reference
---
`baseline-tag-protect` enforces `[deletion, update]` on `refs/tags/v*.*.*`.[^1]
New-tag creation is unrestricted, so `publish.py` is unaffected.

## Notes and lessons learned
[^1]: [ocd:2026-06-09 lmd:2026-06-09] earlier this page said the rules were
  `[deletion, non_fast_forward]` — wrong; that was the pre-ratification draft.
  The error: quoting a mid-thread proposal instead of the USER-ratified final
  spec. Lesson: pin facts to the ratification comment, not the negotiation.
```

## Scope

ONLY authors/updates memory notes + the MEMORY.md index. Does NOT recall
(use `maintainer-memory-recall`). One fact per note. Symptom-indexed
description is mandatory — it is what makes the note recallable.

## Resources

- `rules/memory-protocol.md` — the MAINTAINER memory protocol (the law,
  schema, lessons-learned conventions, dual-test method).
- The harness `# Memory` directive — the authoring source-of-truth this
  skill follows.
- `maintainer-memory-recall` — the RECALL side (find a note before you
  duplicate or correct it; lessons come back appended).
