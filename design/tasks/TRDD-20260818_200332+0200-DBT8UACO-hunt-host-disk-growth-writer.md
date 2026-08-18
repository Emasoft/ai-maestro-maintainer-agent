---
trdd-id: DBT8UACO
title: Identify the ~2G/hr host disk-growth writer by measurement
column: todo
created: 2026-08-18T20:03:32+0200
updated: 2026-08-18T20:03:32+0200
current-owner: maintainer-agent-session
task-type: audit
approval-tier: 0
created-by: hub endorsement 2026-08-18; lead from agentlenspro TRDD-0XGU6NE2
---

# Identify the ~2G/hr host disk-growth writer by measurement

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
