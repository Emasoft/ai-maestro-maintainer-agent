---
trdd-id: DBT8UACO
title: Identify the ~2G/hr host disk-growth writer by measurement
column: ai_review
created: 2026-08-18T20:03:32+0200
updated: 2026-08-21T16:41:00+0200
current-owner: maintainer-agent-session
task-type: audit
approval-tier: 0
created-by: hub endorsement 2026-08-18; lead from agentlenspro TRDD-0XGU6NE2
---

# Identify the ~2G/hr host disk-growth writer by measurement

## ⏵ STATE — READ THIS FIRST ON RESUME (authoritative; supersedes the body) — 2026-08-21 16:41

- **ATTRIBUTED, with a bracketed measurement. The writer is `cargo` debug builds under
  `~/Code`** — principally `~/Code/AgentlensPro/rust-core/target` (49,032 MB, of which
  `debug/` is 47,363 MB). Not uv, not the model stores, not the plugin marketplaces.
- **The evidence (one 59.4-min window that BRACKETS a captured burst):**
  `du` depth-1 over `$HOME/*` + `$HOME/.[!.]*` + `/Applications /Library /opt /usr/local
  /private/var`, A@1787276905 → B@1787280471. `df /` +1,270 MB; the per-path deltas
  account for +1,243 MB of it (98%):
  `~/Code +811` · `~/Downloads +380` · `~/Library +30` · `/private/var +19` ·
  `~/Pictures +6` · `/Library −3` MB.
  Birth-time scoped to that window (`find -newerBt A ! -newerBt B`) names the files:
  **4,683 MB across 7,833 NEW files, all `AgentlensPro/rust-core/target/debug/`** —
  `deps/*` 127-168 MB apiece, `libagentlens_core.rlib` 85 MB, `incremental/*/dep-graph.bin`
  54 MB, `query-cache.bin` 38 MB.
- **Why net (+811 MB) ≪ created (4,683 MB): a rebuild REPLACES most artifacts.** That is
  also why the growth is bursty with reclaim valleys, and why the long-run average
  (0.71 GB/hr net) is far below the in-burst rate (2.4-3.1 GB/hr measured live).
- **The burst, captured end to end** (first time): +857 MB over 1,167 s at ~2.5 GB/hr,
  then decay 0.86 → 0.19 → −0.17 GB/hr. Duration ~20 min, not hours. No `cargo`/`rustc`
  alive afterwards (ps snapshotted to a file first — never `pgrep -f`).
- **Accumulation, the real reason the disk is at 97%:** 13 `target/` dirs under `~/Code`
  total **115,722 MB (113 GB)**, all regeneratable. Top: AgentlensPro 49,032 ·
  SVG_PLAYER 45,296 · ANIME2SVG/vectorizer 10,257 · gpui-video-player 4,529 ·
  perfect-skill-suggester 3,919 MB.
- **RE-MEASURED 2026-08-21 16:41 — the attribution now has a third, independent
  corroboration, and it is a GROWTH one.** `du -sm`: AgentlensPro/rust-core/target
  **79,859 MB** (was 49,032 on 08-18 → **+30,827 MB in 3 days**), SVG_PLAYER/target
  45,296 MB (unchanged). `df /`: 25 GB free, **99%**. The one tree named as the writer
  is the one tree that grew; the tree that is not being built did not move. Quote
  78 GB / 45 GB, not the stale 49 GB.
- **NOT deleting them.** Regeneratable, so RULE 0 permits it — but the card's scope is
  *identify the writer*, and 113 GB of warm build caches across 13 of the USER's projects
  costs hours of rebuild time to reinstate. `cargo clean` per project is the USER's call.
- **`cargo clean` RECLAIMS, it does not FIX.** These trees rebuild; a clean at 99% buys
  days, not a solution. The durable fix (a CARGO_TARGET_DIR budget, a scheduled prune, or
  `--profile dev` artifact limits on the two hot repos) belongs to a NEW card — it is not
  this one's scope, and closing this one must not read as closing that.
- **Three falsifications this session, all the same error in different costumes** —
  see the LESSON below; it is the transferable part.
- **CORROBORATED 07:30 by a second, larger episode.** A `[system-daemon-runaway]` alert
  on `python` pid 53857 (7.1 GB RSS) was a FALSE POSITIVE — `mtplx.server.openai` holding
  a 27B model; RSS moved **+16 KB across 90 s**, CPU 0.2-0.8% (the detector made the same
  level-vs-rate error as everything else in this hunt). But the disk had fallen to
  **48 GB free (97.5%)**: `df` used 1,830,895 → 1,854,686 over 9,667 s = **8.9 GB/hr**,
  attributed to **`~/.mtplx/models/…Qwen3.8-27B-…` +19,745 MB** (absent from the
  dot-tree top-25 at 1787278202, so <594 MB then — a 27B model landed whole) plus
  `~/Code` +1,138 MB (cargo again), ~2,900 MB unattributed. Both went FLAT afterwards.
  **23.8 GB in 2.7 h from exactly two activity-driven sources, then quiet — there is no
  daemon to find.** Also surfaced, not touched (cross-project rule): `alcore serve`
  (pid 75824, `AgentlensPro/rust-core/target/debug/alcore`) at **98.2% CPU for 12 h 29 m**.
- **NEXT ACTION:** none required; card is at `ai_review`. If asked to reclaim, run
  `cargo clean` per project (USER-selected), not a blanket sweep.

### LESSON — a LEVEL is not a RATE, and WRITE ACTIVITY is not GROWTH

Three candidates were named and falsified today; each was measured with the wrong
instrument, and the right instrument was always a two-timestamp delta on the same path.

1. **`uv` (level mistaken for rate).** 91 GB of cache + `+149 MB` over a **3.4-minute**
   window spanning an active `uv run` = "+2.6 GB/hr". The prune falsified it: 65.6 GiB
   freed, rate unchanged, `~/.cache/uv` then +418 MB in 37.5 h.
2. **The six model stores (level, no rate at all).** 255,984 MB across `.mlxstudio`,
   `.hfd`, `.magnitude`, `.ollama`, `.lmstudio`, `.transformerlab` — and **zero files
   modified in 120 min**. Pure accumulation.
3. **`~/.claude/plugins/marketplaces` (write activity mistaken for growth).** A
   birth-time scan showed **2.61 GB across 35,805 files created** in the burst window,
   including a single 850 MB git pack — yet `~/.claude` grew **+2 MB**. A `git fetch`
   rewrites packs: every byte gets a fresh mtime and birth time, net size barely moves.

`find -mmin`/`-newerBt` measures what was WRITTEN; only a delta measures what was KEPT.
Use birth-time to NAME files inside a window you have already bracketed with a delta —
never as the attribution itself.

Two traps that cost real time here: **`$HOME/*` does not glob dotfiles** (~395 GB
invisible; use `$HOME/.[!.]*` too), and **`find -size +200M` cannot see a many-small-files
writer** (7,833 files did this).

### Superseded — do NOT carry forward

- The uv attribution, and the reopening note that said the writer was still unidentified.

- (SUPERSEDED 2026-08-21 05:10) ai_review REJECTED the uv attribution — reopened to `dev`. The prune was the
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

- [x] growth attributed to specific path(s) with two-timestamp evidence — `~/Code` **+811 MB** of a **+1,270 MB** `df` delta over one 59.4-min window bracketing a live burst (A@1787276905 → B@1787280471); per-path deltas account for 98% of it. Narrowed by birth time to `~/Code/AgentlensPro/rust-core/target/debug/` — 4,683 MB / 7,833 new files.
- [x] writer process identified — **`cargo` debug builds** (Rust incremental compilation). Exonerated by rate, not level: `uv` (+418 MB/37.5 h), the six model stores (0 files in 120 min), `~/.claude/plugins/marketplaces` (2.61 GB created but `~/.claude` +2 MB — pack rewrites), Docker.raw, OrbStack, Photos.sqlite, `~/.claude/projects`, `Library/Caches`, `var/folders`.
- [x] remedy PROPOSED (not applied) in a report under `reports/host-hygiene/` — 20260819_213800+0200 (conclusion falsified; df series still valid) superseded by **20260821_042713+0200-disk-growth-reattribution.md**. Remedy: `cargo clean` per USER-selected project — 13 `target/` dirs hold **115,722 MB**, all regeneratable. Deliberately NOT applied.

## Approval log
