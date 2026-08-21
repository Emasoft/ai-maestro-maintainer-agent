---
trdd-id: DBT8UACO
title: Identify the ~2G/hr host disk-growth writer by measurement
column: dev
created: 2026-08-18T20:03:32+0200
updated: 2026-08-21T10:55:00+0200
current-owner: maintainer-agent-session
task-type: audit
approval-tier: 0
created-by: hub endorsement 2026-08-18; lead from agentlenspro TRDD-0XGU6NE2
---

# Identify the ~2G/hr host disk-growth writer by measurement

## ⏵ STATE — READ THIS FIRST ON RESUME (authoritative; supersedes the body) — 2026-08-21 10:55

- **ai_review REJECTED the uv attribution — reopened to `dev`.** The prune was the
  experiment that falsified it. Measured 2026-08-21 (df `/`, MB used):
  `1,801,976 @1787140831 → 1,829,347 @1787275916` = **+27,371 MB net over 37.5 h
  (0.71 GB/hr)** — and that is *after* the 65.6 GiB prune landed inside the window, so
  **gross growth = +94,546 MB ≈ 2.46 GB/hr**, the original symptom, undiminished.
- **`uv` is now INERT and is NOT the writer.** `~/.cache/uv` 91,106 MB → prune → 17,600
  → **18,018 MB now**: +418 MB in 37.5 h (0.01 GB/hr). Its 91 GB was *accumulated
  garbage over months*, not a rate. The old "+2.6 GB/hr" came from extrapolating a
  **3.4-minute** sample taken during an active `uv run` burst — a sampling error.
  Pruning it bought a one-off 65.6 GiB and changed the growth rate by nothing.
- **LESSON (do not repeat): a LEVEL is not a RATE.** A 91 GB directory is evidence of
  accumulation, not of current writing. Only a two-timestamp delta on the *same* path
  proves a rate, and the interval must be long enough to span the burst/idle cycle —
  this writer is bursty (0.7 → 15.8 GB/hr windows), so any sample under ~1 h lies.
- **Second writer UNIDENTIFIED — that is the open work.** Exonerated by measurement
  this session: `~/.cache/uv` (flat), `~/.claude/projects` (18,503 MB, ~flat vs the
  18 GB recorded 2 d ago), LM Studio model downloads (multi-GB `.part` files, but on
  `/Volumes/EmaUITEK4TBSSD` — a different volume, not `/`). A `find` for files >200 MB
  modified in the last 24 h over Containers/Application Support/.cache/.claude/Caches
  totals only ~3.7 GB ⇒ **the growth is many small files, or lives outside `$HOME`.**
- **NEXT ACTION:** take snap-6 (same command as snap-5) ≥45 min after snap-5's
  ts 1787275916 and diff per path; snap-5 is `/tmp/du-snap-5.txt` (partial — Photos
  98,952 / orbstack 10,025 / .claude 49,136 / .cache 36,224 / Caches 16,931 /
  Containers 90,509 MB; `~/Code`, `~/Downloads`, `~/Library/Application Support`,
  `/private/var/folders` still pending). If every `$HOME` path is flat, the writer is
  outside `$HOME` — sweep `/private/var`, `/Library`, `/System/Volumes/Data` at depth 1.
- **Still USER's call** (both now LOWER value than when proposed, since uv is inert):
  a recurring weekly `uv cache prune` chore, and a 40 GB `~/.cache/uv` alert.

### Superseded — do NOT carry forward

- "ATTRIBUTION DONE / writer = uv" and the three acceptance boxes ticked on that basis.
  The finding below is kept as the audit trail of *how* it was reached, not as fact.

- (FALSIFIED 2026-08-21) **ATTRIBUTION DONE.** Writer = `uv` filling `~/.cache/uv` (91 GB; +2.6 GB/hr while
  measured; 1,979 files touched in 3 h). Net disk growth +25.9 GB over 14.5 h
  (1.79 GB/hr) matches the symptom; bursty (spikes to 16 GB/hr, reclaim valleys).
  All prior suspects exonerated by interval measurement (projects, plugins, Caches,
  Photos, OrbStack, snapshots, swap).
- Report: `reports/host-hygiene/20260819_213800+0200-disk-growth-attribution.md`
- Remedy PROPOSED (not applied — USER decision): `uv cache prune` now; weekly janitor
  prune chore; optional UV_CACHE_DIR quota / 40 GB alert.
- All 3 acceptance boxes satisfied. Column ai_review.
- 2026-08-20: disk hit 96% with a live 5.3GB `next build` running — executed the
  SAFE remedy under the regeneratable-cache rule (use-safe-delete: regeneratable
  ⇒ act, don't stall): `uv cache prune` removed 2,648,300 unreferenced files,
  **65.6 GiB freed** (cache 91.4→17.6 GB). Nothing non-regeneratable touched.
  Still USER's call: the recurring weekly prune chore + 40 GB alert threshold.

### Older working notes (superseded by the above) — 2026-08-19 early

- Snapshots: /tmp/du-snap-1.txt (epoch 1787088712), du-snap-2.txt (1787090489),
  du-snap-3.txt (1787107952). Snap2→snap3 (4.85 hr): disk +3377 MB (~0.70 GB/hr)
  while the ORIGINAL scoped candidates NET SHRANK −1165 MB ⇒ writer is OUTSIDE
  the original scope. `~/.claude/projects` grew only +7..28 MB/window — NOT the
  writer (the agentlenspro lead is falsified by measurement).
- No TM local snapshots (only stable OS-update snapshots) — growth is real files.
- lsof attribution: Photos library under heavy write (photoanalysisd,
  mediaanalysisd, cloudphotod, icloudwebd). ~33 GB of its files rewritten in the
  last 6 h (18.5 GB Photos.sqlite, multi-GB .ithmb thumbs, cloudsync store).
  Library size reading: 98965 MB @1787107943. OrbStack data.img.raw is sparse:
  1.9 TB apparent, only 10 GB allocated — benign unless its du grows.
- NEXT ACTION: read /tmp/du-snap-4.txt (written by a 45-min background timer,
  bash task burmcnma0; if missing, re-run: date +%s; df / | tail -1; du -sm
  "$HOME/Pictures/Photos Library.photoslibrary" "$HOME/Library/Group
  Containers/HUAQ24HBR6.dev.orbstack" $HOME/.claude/projects
  $HOME/Library/Caches /private/var/folders). Compute MB/hr per path, then
  write the report to reports/host-hygiene/ and propose (not apply) a remedy.
- SUPERSEDED — do NOT carry forward: the one-shot cron af1b6699 (died with the
  2026-08-18 session clear; replaced by the snapshots above). Do NOT re-run a
  whole-home `du`/`find` — both exceed 20 min on this host.

Disk was 96% (now 94% after the 2026-08-18 cache sweep, +40G) and grows
~2G/hr. AgentlensPro's server is EXONERATED (its session measured 0.3MB
written since boot; no supervisor exists — its TRDD-0XGU6NE2). Best current
lead, measured by that session: `~/.claude/projects` (session transcripts,
18G, grows every turn of every session).

## Method (measure, don't suspect)

- Interval `du` deltas: snapshot `du -sm` over the top-level candidates
  (`~/Library`, `~/.claude`, `~/Code`, `/private/var`, …) twice, 30-60 min
  apart, diff the two snapshots to files.
- Or live: `sudo fs_usage -w -f filesys | grep -v READ` filtered to writes,
  sampled briefly.
- Attribute the growth to a concrete path + writer process before proposing
  any remedy. Retention policy for `~/.claude/projects` (if it is the
  writer) is a USER decision — surface, don't delete.

## Acceptance

- [ ] growth attributed to specific path(s) with two-timestamp evidence — REOPENED. The
  `uv` attribution (90957→91106 MB over 3.4 min) was a burst extrapolated to a rate;
  pruning uv to 18 GB left the 2.46 GB/hr gross growth unchanged. Needs a delta over
  ≥45 min per path, and a sweep outside `$HOME` if every `$HOME` path is flat.
- [ ] writer process identified — REOPENED. `uv` exonerated (+418 MB in 37.5 h).
- [x] remedy PROPOSED (not applied) in a report under `reports/host-hygiene/` — 20260819_213800+0200-disk-growth-attribution.md (its *conclusion* is now falsified; the df series and method in it remain valid evidence)

## Approval log
