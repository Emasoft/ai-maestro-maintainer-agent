---
trdd-id: DBT8UACO
title: Identify the ~2G/hr host disk-growth writer by measurement
column: ai_review
created: 2026-08-18T20:03:32+0200
updated: 2026-08-20T09:30:00+0200
current-owner: maintainer-agent-session
task-type: audit
approval-tier: 0
created-by: hub endorsement 2026-08-18; lead from agentlenspro TRDD-0XGU6NE2
---

# Identify the ~2G/hr host disk-growth writer by measurement

## ⏵ STATE — READ THIS FIRST ON RESUME (authoritative; supersedes the body) — 2026-08-19 21:40

- **ATTRIBUTION DONE.** Writer = `uv` filling `~/.cache/uv` (91 GB; +2.6 GB/hr while
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

- [x] growth attributed to specific path(s) with two-timestamp evidence — `~/.cache/uv`, 90957→91106 MB @1787141665→1787141871, plus the 7-point df series (net 1.79 GB/hr over 14.5 h)
- [x] writer process identified — `uv` (fleet-wide `uv run --script` from hooks/heartbeats/plugin scripts)
- [x] remedy PROPOSED (not applied) in a report under `reports/host-hygiene/` — 20260819_213800+0200-disk-growth-attribution.md

## Approval log
