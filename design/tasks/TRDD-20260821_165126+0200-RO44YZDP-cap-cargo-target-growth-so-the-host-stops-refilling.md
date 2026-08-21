---
trdd-id: RO44YZDP
title: Cap cargo target growth so the host stops refilling to 99 percent
column: backburner
created: 2026-08-21T16:51:26+0200
updated: 2026-08-21T16:51:26+0200
current-owner: maintainer-agent-session
task-type: infra
min-approval-requirement: user
parent-trdd: DBT8UACO
---

# Cap cargo target growth so the host stops refilling to 99 percent

`cargo clean` RECLAIMS; it does not FIX. TRDD-DBT8UACO measured the mechanism and
this card owns the durable answer, so that closing DBT8UACO is never mistaken for
having solved the disk.

## Why this is a separate card

DBT8UACO's scope was *identify the writer*, and it did: cargo debug builds under
`~/Code`. The measurement that closed it is also the argument for this card —
`AgentlensPro/rust-core/target` went **49,032 MB → 79,859 MB in three days**
(2026-08-18 → 2026-08-21) while `SVG_PLAYER/target` sat unchanged at 45,296 MB.
One tree is built, one is not; only the built one grows.

On 2026-08-21 a `cargo clean` of SVG_PLAYER alone returned 49.4 GiB (212,146
files) and moved the host 99% → 97%. At the measured rate the built trees refill
that in roughly a week. A cleanup that must be repeated on a human's attention is
not a fix, it is a recurring chore with an outage at the end of every missed one.

## The measurement that scopes it

13 `target/` dirs under `~/Code`, ~115,722 MB before the SVG_PLAYER clean, all
regeneratable. The growth is concentrated: two repos held 123 GB of it.

## Candidate approaches (not yet chosen — this is the decision to make)

- **Shared `CARGO_TARGET_DIR`** — one build cache instead of 13, so shared deps
  are compiled and stored once. Biggest structural win; changes every repo's
  build layout, so it needs the USER's agreement per repo.
- **Scheduled prune** — `cargo-sweep`-style removal of artifacts not touched in
  N days, on the janitor's existing heartbeat. Keeps warm caches warm and only
  reaps cold ones. Least invasive; does not bound peak.
- **A disk-pressure trigger** — clean the coldest `target/` automatically when
  free space crosses a floor. Bounds the failure mode directly rather than
  guessing a schedule. Must never touch a tree with a live build (see the gotcha
  below).
- **Per-repo `[profile.dev]` limits** — `debug = "line-tables-only"`,
  `incremental = false` on the hot repos. Cheapest to try, smallest win.

These are not exclusive; the prune and the pressure trigger compose.

## Load-bearing gotcha — check liveness before cleaning ANY target dir

On 2026-08-21 the advice received was "clean AgentlensPro first, it is biggest".
A process-table snapshot taken first showed `cargo test --workspace` live in that
very tree (pid 52111), plus a 21-hour-old `./target/debug/alcore serve` (pid
75824) running FROM it. Cleaning it would have destroyed a running test run and a
live binary's on-disk image.

**Any automation this card produces MUST snapshot the process table to a file and
check it before removing a `target/` dir** — and must snapshot rather than
`pgrep -f` / `ps | grep`, which match their own search pattern in the scanning
shell's argv. Size is the wrong sort key; liveness is the right one.

## Acceptance

- [ ] an approach is chosen with the USER (all four touch repos this agent does
      not own, so this is theirs to decide, not a Tier-0 call)
- [ ] free space stays above an agreed floor for 14 consecutive days with no
      human intervention
- [ ] whatever runs proves it checked liveness before deleting, from a process
      snapshot taken before the check
- [ ] DBT8UACO's STATE block links here, so the mechanism and the fix stay joined

## Notes and lessons learned
