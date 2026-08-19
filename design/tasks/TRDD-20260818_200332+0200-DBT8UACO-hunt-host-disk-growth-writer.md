---
trdd-id: DBT8UACO
title: Identify the ~2G/hr host disk-growth writer by measurement
column: dev
created: 2026-08-18T20:03:32+0200
updated: 2026-08-19T03:35:00+0200
current-owner: maintainer-agent-session
task-type: audit
approval-tier: 0
created-by: hub endorsement 2026-08-18; lead from agentlenspro TRDD-0XGU6NE2
---

# Identify the ~2G/hr host disk-growth writer by measurement

## ⏵ STATE — READ THIS FIRST ON RESUME (authoritative; supersedes the body) — 2026-08-19

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

- [ ] growth attributed to specific path(s) with two-timestamp evidence
- [ ] writer process identified
- [ ] remedy PROPOSED (not applied) in a report under `reports/host-hygiene/`

## Approval log
