# Memory protocol — recall + write for the MAINTAINER role

The harness `# Memory` directive (injected each session) tells the agent how to
**WRITE** memories. This rule is the missing half for the **MAINTAINER**: how to
**RECALL** them, the **discipline** that makes recall work, and the **tool**
(`memgrep`) that powers it. Together they are "the memory system": authoring
(directive + `maintainer-memory-write`) + recall (this rule +
`maintainer-memory-recall`) + the search tool (memgrep) + the note corpus.

This recalls *curated, symptom-indexed markdown notes* in the project's
`memory/` dir — NOT conversation/transcript history. The two are different
corpora; transcript search cannot replace this and vice versa.

## The one law that makes memory work: index by the QUESTION, not the answer

A memory is found from the SYMPTOM, not the solution. When you write a note,
its `description:` (and `title`/`tags`) MUST carry the words a future session
will have when the problem RECURS — the user's words, the error text, the
GitHub-alert text, the symptom — NOT the jargon of the fix.

- WRONG `description`: "ruleset payload needs bypass_actors split across two
  rulesets". (Findable only if you already know the answer.)
- RIGHT `description`: "publish.py push rejected GH013 after enabling branch
  protection — why is the push blocked" + the two-ruleset fact in the BODY.

Two-hop recall: a symptom query lands you on the note; the note's BODY gives
the answer. The `description` is the load-bearing surface — `memgrep recall`
ranks on `description + title + tags` ONLY (the `metadata.type` taxonomy does
NOT affect ranking). Put symptom vocabulary in `description`; put the answer in
the body.

## Recall BEFORE acting (the protocol)

Before debugging a recurring problem, making a design decision, triaging a
**recurring GitHub alert/issue**, or re-deriving the entrusted repo's
architecture or gotchas, RECALL first — "have we hit this before?". Cheap, and
it is the whole point of having a memory. Concretely for the MAINTAINER:

- a Dependabot/CodeQL/secret-scanning alert that looks familiar → recall it;
- a CI failure with an error you half-remember → recall it;
- a ruleset-drift or publish-pipeline question already settled → recall it;
- about to re-investigate why a gate/hook behaves oddly → recall it.

```bash
# memdir is the harness per-project memory dir:
MEMDIR="$HOME/.claude/projects/<project-slug>/memory"   # slug = project path, dashed
SYMPTOM="the user's words / the error / the symptom"     # NOT the answer's jargon

if command -v memgrep >/dev/null 2>&1; then
  memgrep recall "$SYMPTOM" "$MEMDIR"      # notes ranked best-first as: path — description
else
  grep -rliE "$SYMPTOM" "$MEMDIR"          # fallback: plain grep, degrade-not-break
fi
```

Read the top 1-3 notes the recall returns; the answer is in their bodies. If
recall returns nothing, the memory doesn't exist yet — solve the problem, then
capture it with `maintainer-memory-write`.

## memgrep — the recall engine (with mandatory fallback)

`memgrep` is `rg` for markdown (gitignore-aware tree walk, markdown-structural
filters, and the memory subcommands `recall`/`find`/`index`). Its teaching doc
is `tools/memgrep/SKILL.md` in the `ai-maestro-janitor` repo, which owns and
distributes the binary.

- **Availability:** memgrep is a Rust binary. If `command -v memgrep` is
  empty, install it once: `cargo install --path
  <…>/ai-maestro-janitor/tools/memgrep` (puts it on `~/.cargo/bin`). Until
  then, the plain-`grep` fallback above works on note frontmatter + bodies —
  **recall degrades, never breaks**. Every Maintainer surface that recalls
  MUST gate on `command -v memgrep` and fall back to `grep -rliE`.
- **recall** `memgrep recall "SYMPTOM" <memdir>` — symptom-ranked notes,
  precision-first, printed `path — description`, best first. Useful flags:
  `--sort score|ocd|lmd`, `--since/--until`, `--top N`.
- **find** `memgrep find "+TERM -TERM" <memdir>` — note-level keyword search
  (`+` mandatory, `-` exclude, `"phrase"` verbatim, `*` wildcard);
  `--only-notes` searches the resolved `[^N]` lessons instead of pages.

## Read-the-notes rule — a memory's lessons are part of the memory

When you read ANY memory, read **all the lessons attached to it** — every
`[^N]` footnote and the `## Notes and lessons learned` entries they point to.
The lessons are *why* the facts are the way they are and *what errors not to
repeat*. memgrep auto-appends each returned note's resolved lessons on
`recall`/`find` (suppress with `--no-notes`; restore lesson metadata with
`--full-notes`), so one call yields the facts AND every linked WHY.

## The note format (recall-relevant fields)

The `# Memory` harness directive is the authoring source-of-truth. On disk:

```yaml
---
name: <kebab-slug>                 # == filename stem
description: "<symptom surface — the load-bearing recall field>"
metadata:
  node_type: memory
  type: user | feedback | project | reference
---
<body: the one fact; for feedback/project add **Why:** and **How to apply:**>
```

`MEMORY.md` is the human index (`- [Title](file.md) — hook`, one line per
note) loaded each session. Recall does not need the index — it scans the notes
directly.

## Correcting a memory — non-destructive, two steps

When a discovery CONTRADICTS an existing note: (1) **clean the fact in place**
(the body is always the current truth); (2) **demote the error to a lesson** —
a numbered `[^N]:` entry under `## Notes and lessons learned` carrying the WHY
(root cause), with `[ocd:… lmd:…]` dates. The fact is corrected; the error is
never deleted — it becomes the guardrail against the next repeat. Full
procedure: `maintainer-memory-write`.

## Evaluating recall: the dual-test method

- **Test A — cold-recall:** query ONLY from the symptom/user's words, never
  the answer's jargon. Tests "is the right note findable from the symptom?".
- **Test B — write-then-recall:** author a note, then retrieve it. Tests the
  round-trip. Contamination warning: after writing a note you are biased
  toward its wording — have the cold symptom come from the user verbatim.

## Why this rule exists

Without a standing rule + skills, a fresh MAINTAINER session is blind to the
note corpus even when the answer was written down last week, and re-derives
the same facts (entrusted-repo architecture, publish-gate gotchas, ruleset
decisions) every time. This rule makes "recall before acting" and "index by
symptom" a standing discipline, with a tool command that degrades to grep when
the binary is absent.
