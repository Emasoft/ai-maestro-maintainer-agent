# `design/archived/` — once-approved TRDDs that reached a terminal-DONE state

A TRDD is `git mv`-ed here (never deleted — RULE 0) when it was **approved**
(reached `design/tasks/`) and later reached a terminal-DONE state:

| State | `column:` | When |
|-------|-----------|------|
| **completed** | `completed` | work finished / shipped (its `release-via` terminal reached) |
| **cancelled** | `cancelled` | withdrawn — the work is no longer wanted |
| **superseded** | `superseded` | replaced by other TRDD(s) (recorded in `superseded-by:`) |

The dividing line vs `design/refused/` is *was it ever approved?* — a proposal
the approver **declined** never entered the pipeline and goes to
`design/refused/`; only once-approved TRDDs land here.

**`failed` is NOT archived.** `failed` is a *retryable* in-progress state that
stays in `design/tasks/`; giving up on it is an explicit `cancelled`
transition (→ here).

**Grandfathering:** terminal TRDDs authored before the 4-zone model existed
remain in `design/tasks/` as historical reference; they are not retroactively
moved here.
