# Cardinality and limits — the CARD-xx catalogue

A cardinality explosion is a self-inflicted denial of service on the
monitoring backend, committed to the repo as a one-word label. It is a
maintainer finding for the same reason an unbounded query in a hot path
is: the config in *this* repo takes down a shared system.

Prometheus: every unique label-value combination is a time series, held
in RAM by the ingester. Loki: every unique **stream-selector** label
combination is a stream, indexed and chunked. Both grow
multiplicatively.

## Table of Contents

- [Findings catalogue](#findings-catalogue)
- [CARD-01 — the unbounded label names](#card-01--the-unbounded-label-names)
- [CARD-02 — aggregation without grouping](#card-02--aggregation-without-grouping)
- [Loki limits that must be present](#loki-limits-that-must-be-present)
- [Loki limits_config — the exact defaults](#loki-limits_config--the-exact-defaults)
- [The retention two-key gotcha](#the-retention-two-key-gotcha)
- [Fluent Bit backpressure and restart re-ingest](#fluent-bit-backpressure-and-restart-re-ingest)
- [Proving a cardinality finding](#proving-a-cardinality-finding)

## Findings catalogue

| ID | Severity | Finding | Where |
|----|----------|---------|-------|
| CARD-01 | MED | Unbounded label name in a `by`/`without` clause, a rule's output labels, or a Loki stream selector | Prometheus rules, Loki rules, shipper label config |
| CARD-02 | MED | Aggregation with no `by`/`without` in an alert | `sum(rate({app="api"}[5m]))` collapses every dimension — the alert cannot say what broke |
| CARD-03 | MED | Loki `limits_config` absent, or `max_streams_per_user: 0` (unlimited) | Loki config |
| CARD-04 | MED | Loki `limits_config` with no `ingestion_rate_mb` / `ingestion_burst_size_mb` / `max_line_size` | Loki config |
| CARD-05 | MED | Fluent Bit `tail` INPUT with no `Mem_Buf_Limit` | Fluent Bit config |
| CARD-06 | HIGH | Fluent Bit `tail` INPUT with no `DB` | On restart the file is re-read **from the beginning** — the whole log re-ingested, every time the pod restarts. A crashloop becomes an ingestion flood |
| CARD-07 | LOW | Fluent Bit OUTPUT with no `storage.total_limit_size` | An unreachable backend backs up into unbounded buffering |
| CARD-08 | LOW | Very long range vector in a frequently-evaluated rule (`[24h]` on a 30s interval) | Each evaluation rescans the whole window |

## CARD-01 — the unbounded label names

Flag a label whose value space is not a small closed set. The names
below are the ones that show up in real incidents; match on the name,
case-insensitively, and on obvious variants:

**Never a label** — unbounded, one series per value:

`user_id` · `userid` · `customer_id` · `account_id` · `request_id` ·
`trace_id` · `span_id` · `session_id` · `correlation_id` · `uuid` ·
`email` · `ip` / `remote_addr` (individual addresses) · `url` / `path`
with IDs embedded (`/users/8123/orders/55`) · `timestamp` ·
`container_id` (the full hash) · `pod_ip` · full `message` /
`error_message` text

**Bounded, fine as a label:**

`job` · `service` · `namespace` · `cluster` · `environment` · `region` ·
`app` · `level` (`error|warn|info`) · `status_code` (or better,
`status_class`) · `method` (a closed HTTP verb set) · `route`
*template* (`/users/:id`, not `/users/8123`) · `pod` and `instance`
*in moderation* (they churn on every deploy)

Where the high-cardinality value genuinely needs to be queryable:

- **Prometheus:** it does not belong in a metric. It belongs in a log
  or a trace. There is no safe way to put a `user_id` in a label.
- **Loki:** keep it **out of the stream selector**. Put it in the log
  line and filter at query time (`{app="api"} | json | user_id="…"`),
  or attach it as **structured metadata**, which Loki 3.x stores
  unindexed. Both avoid a new stream per value. (This overlaps SEC-08:
  a `user_id` label is also a PII index.)

## CARD-02 — aggregation without grouping

```promql
# Finding: one number for the whole fleet; the alert names no culprit.
sum(rate(http_requests_total{code=~"5.."}[5m])) > 10

# Clear: the page arrives with the job attached.
sum by (job) (rate(http_requests_total{code=~"5.."}[5m])) > 10
```

Same in LogQL: `sum by (namespace, app) (rate({app="api"}[5m]))`.

This is MED, not HIGH: the alert *works*, it is just useless at 3am.

## Loki limits that must be present

An absent `limits_config` means the defaults, and the defaults do not
know how much this repo's pipeline is about to send. The audit checks
for presence and for the explicit-unlimited footgun:

```yaml
limits_config:
  ingestion_rate_mb: 50           # CARD-04 if absent
  ingestion_burst_size_mb: 100    # ~2x the rate
  max_line_size: 256KB            # CARD-04 if absent
  max_line_size_truncate: true
  max_streams_per_user: 10000     # CARD-03 if absent or 0
  max_global_streams_per_user: 100000
  retention_period: 30d           # also SEC-10
```

`max_streams_per_user: 0` means *unlimited* — that is a CARD-03 HIGH-
adjacent finding written as an explicit choice. Report the line and say
so; do not assume it was a typo.

Do **not** audit Loki's deployment topology, storage backend,
replication factor, memcached, or resource requests. Those are
operator decisions about a running system, not repo hygiene, and the
maintainer has no basis to second-guess them.

## Loki limits_config — the exact defaults

An absent key means Loki's built-in default, which is often *not* what
the repo's traffic needs. Cite the default when you flag an absent key
so the reader sees the delta. Verified against the Loki config schema:

| Key | Default | Audit note |
|-----|---------|------------|
| `ingestion_rate_mb` | `4` | Low; a busy stream trips the per-tenant rate limit and drops lines (CARD-04) |
| `ingestion_burst_size_mb` | — | Pair with the rate, ~2× |
| `max_line_size` | `256KB` | With `max_line_size_truncate: false` an over-size line is *dropped*, not cut |
| `max_line_size_truncate` | `false` | Set `true` to keep truncated lines instead of losing them |
| `max_streams_per_user` | `10000` | Per-tenant stream cap; `0` = unlimited (CARD-03) |
| `max_global_streams_per_user` | `5000` | Global cap — note it can read *lower* than the per-tenant one |
| `max_label_names_per_series` | `15` | A stream with more labels is rejected — a cardinality guardrail |
| `max_label_name_length` | `1024` | — |
| `max_label_value_length` | `2048` | — |
| `max_entries_limit_per_query` | `5000` | — |
| `max_query_length` | `721h` | — |
| `max_query_series` | `500` | — |
| `retention_period` | `0` | **`0` = keep forever** (SEC-10). See the gotcha below |

## The retention two-key gotcha

Setting `limits_config.retention_period` **alone changes nothing** —
Loki only deletes when the compactor is *also* told to enforce
retention, and that is off by default:

```yaml
compactor:
  retention_enabled: true      # default false — WITHOUT this, nothing ages out
  retention_delete_delay: 2h
limits_config:
  retention_period: 30d        # default 0 (forever); ignored unless the compactor enforces
```

So a repo that "has a retention period" but left `retention_enabled`
absent/`false` is retaining forever regardless — a SEC-10 finding even
though `retention_period` is set. Check both keys together, not either
alone. (Do not audit the compactor's topology beyond these two keys.)

The **OTLP index-label rule** (Loki 3.0+ native ingestion) is the same
CARD-01 principle at the ingestion layer: promote only low-cardinality
resource attributes to index labels. High-cardinality ones such as the
pod name or the service-instance id belong in **structured metadata**
(unindexed), never in `index_label` — indexing them is a stream-per-value
bomb identical to a `user_id` label.

## Fluent Bit backpressure and restart re-ingest

```ini
[INPUT]
    Name           tail
    Path           /var/log/containers/*.log
    DB             /var/log/flb_kube.db    # CARD-06 if absent
    Mem_Buf_Limit  50MB                    # CARD-05 if absent
    Skip_Long_Lines On

[OUTPUT]
    Name                     loki
    Match                    kube.*
    storage.total_limit_size 5G            # CARD-07 if absent
    Retry_Limit              5
```

- **`DB`** is the offset database. Without it, restart = re-read the
  file from byte zero. This is CARD-06 (HIGH) because it compounds:
  the flood causes backpressure, backpressure causes an OOM kill, the
  OOM kill causes a restart, the restart causes the flood.
- **`Mem_Buf_Limit`** bounds the in-memory buffer per input. Sane band:
  roughly 10MB–500MB. Below the band, the input pauses under normal
  load (backpressure); above it, the shipper's own memory becomes the
  incident. Outside the band ⇒ CARD-05.
- **`storage.total_limit_size`** bounds the filesystem buffer when the
  destination is unreachable. Absent ⇒ the buffer grows until the disk
  is full and *everything* on the node fails, not just logging.

## Proving a cardinality finding

Every CARD-xx above is a **static** finding — read off the config, no
live system needed. That is deliberate: the maintainer audits the repo.

If the team disputes a finding, the proof lives in their running
system, not in this skill:

- Prometheus: `promtool tsdb analyze <data-dir> --limit=20` prints the
  highest-cardinality metric names and label pairs from a real TSDB.
- Loki: the per-tenant stream count in the backend's own metrics.

Hand them the command. Do not run it against production, and never
fabricate its output to strengthen a report.
