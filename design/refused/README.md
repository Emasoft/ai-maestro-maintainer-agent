# `design/refused/` — proposals that were NEVER approved

A TRDD is `git mv`-ed here (never deleted — RULE 0) when a proposal in
`design/proposals/` is **declined at the approval gate**: the approver sets
`column: refused`, records the one-line reason in the TRDD body
`## Approval log`, and moves the file here as the audit record.

A refused proposal is **terminal** — re-attempting the idea means authoring a
**new** proposal (which may cite the refused one in `supersedes:` / the body).

The distinction from `design/archived/`: this folder holds **never-approved**
proposals; `design/archived/` holds **once-approved** TRDDs that later finished,
were cancelled, or were superseded. Lineage is the test: *was it ever
approved?* — no → `design/refused/`; yes → `design/archived/`.
