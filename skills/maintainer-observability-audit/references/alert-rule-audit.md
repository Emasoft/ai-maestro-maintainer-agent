# Alert- and recording-rule audit — the AR-xx catalogue

These checks run against every rule file found in the repo: plain
Prometheus rule files, `PrometheusRule` CRDs (after `.spec`
extraction), and Loki ruler rule files (language-neutral checks only).

The rule file's shape:

```yaml
groups:
  - name: api
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: sum by (job) (rate(http_requests_total{code=~"5.."}[5m])) > 0.05
        for: 10m
        labels:
          severity: critical
        annotations:
          summary: "5xx rate above 5% on {{ $labels.job }}"
      - record: job:http_requests:rate5m
        expr: sum by (job) (rate(http_requests_total[5m]))
```

## Table of Contents

- [Findings catalogue](#findings-catalogue)
- [Metric-type semantics — the table AR-04/AR-05/AR-06 are built on](#metric-type-semantics--the-table-ar-04ar-05ar-06-are-built-on)
- [Loki rule files (LogQL `expr`)](#loki-rule-files-logql-expr)
- [What is NOT a finding](#what-is-not-a-finding)

## Findings catalogue

| ID | Severity | Finding | Why it matters |
|----|----------|---------|----------------|
| AR-01 | MED | Alert has no `for:` | Fires on a single scrape. One flaky scrape or one GC pause pages the on-call. `for:` is what turns a spike into an incident |
| AR-02 | MED | Alert has no `severity` label | Alertmanager routes on labels. With no `severity` the alert lands on the catch-all receiver — usually nowhere anyone reads |
| AR-03 | HIGH | Alert `expr` has no comparison operator | `expr: rate(errors[5m])` returns a value for every series, always. The alert fires forever, and the team mutes it. Alert exprs must reduce to a boolean via `>`, `<`, `==`, `!=`, `>=`, `<=`, `absent()`, or `absent_over_time()` |
| AR-04 | HIGH | `rate()` or `increase()` applied to a gauge | Defined only for counters. On a gauge, a value that goes down reads as a counter reset and the result is garbage — a silently wrong alert |
| AR-05 | MED | Counter used raw (no `rate`/`increase`) in an alert expr | A counter's absolute value is "everything since process start". Comparing it to a threshold alerts on uptime, not on behaviour |
| AR-06 | MED | Averaging a pre-computed quantile | `avg(http_request_duration_seconds{quantile="0.95"})` is not the p95 of anything. Quantiles do not average. Compute from histogram buckets via `histogram_quantile` over `rate(..._bucket[5m])` |
| AR-07 | LOW | `irate()` over a range longer than ~5m | `irate` only looks at the last two samples in the range; the rest of the window is scanned and discarded. Either shrink the range or use `rate()` |
| AR-08 | LOW | Recording rule name breaks the `level:metric:operations` convention | The convention encodes the aggregation level, the source metric, and the operations applied (`job:http_requests:rate5m`). A recording rule named like a raw metric is indistinguishable from one, and the next person double-rates it |
| AR-09 | MED | Duplicate `alert:`/`record:` name inside one group | Both evaluate; the recording rule's later write wins non-deterministically. `promtool check rules --lint=all` also catches this |
| AR-10 | LOW | `for:` shorter than 2× the group's `interval:` (or the global evaluation interval) | The alert cannot survive its own pending period reliably — it will flap between pending and firing |
| AR-11 | LOW | Alert has no `summary`/`description` annotation | The page arrives with a rule name and nothing else. Cheap to fix, expensive at 3am |

## Metric-type semantics — the table AR-04/AR-05/AR-06 are built on

Type is inferred from the metric name suffix when no `/metrics`
fixture is available. State the inference in the finding so a reader
can overrule it.

| Suffix | Type | Correct handling | Wrong handling |
|--------|------|------------------|----------------|
| `_total`, `_count`, `_sum` | counter | `rate(m[5m])`, `increase(m[1h])` | raw value in a threshold |
| `_bucket` (with `le`) | histogram | `histogram_quantile(0.95, sum by (le) (rate(m_bucket[5m])))` | `avg(m_bucket)` |
| `{quantile="…"}` | summary | compare the quantile series directly, per-instance | `avg()` / `sum()` across the quantile |
| `_bytes`, `_ratio`, `_seconds` (no `_total`), `..._info`, everything else | gauge | raw value, `avg_over_time`, `max_over_time`, `delta` | `rate()`, `increase()` |

The inference is a heuristic and the corpus it came from says so. A
custom counter named `requests_handled` (no `_total`) will be read as a
gauge. When the metric type is not deducible, do **not** raise AR-04 —
raise `manual-review` and name the ambiguity.

## Loki rule files (LogQL `expr`)

Applicable: AR-01, AR-02, AR-03, AR-09, AR-10, AR-11 — they are about
the rule's *metadata*, not its query language.

Not applicable: AR-04..AR-08 — those are PromQL semantics. LogQL has
its own equivalents worth flagging when obvious from the text:

- A metric query in an alert with no aggregation grouping —
  `sum(rate({app="api"}[5m]))` collapses every stream into one number;
  the alert cannot say *which* app broke. Group with
  `sum by (namespace, app)`.
- A range vector over hours (`rate({app="api"}[24h])`) in a rule that
  is evaluated every 30s — each evaluation rescans a day of logs.
- `|~ "GET"` where `|= "GET"` would do: a regex line filter for a
  plain substring. Slower, and in a rule it runs on every evaluation.

Do not lint LogQL beyond these. There is no offline LogQL parser in
this skill's toolchain, and a heuristic "syntax error" would be a lie.

## What is NOT a finding

The maintainer audits what is committed. It does not design the
alerting strategy. None of these are findings:

- **A missing alert.** "There is no alert on disk usage" is a product
  decision the team owns. Do not open it.
- **A threshold you disagree with.** `> 0.05` vs `> 0.01` is not
  auditable from the repo.
- **An SLO or error-budget model.** Out of scope entirely.
- **A metric the rule references that you cannot verify exists.** The
  maintainer has no live TSDB. `pint`'s `promql/series` check does
  this properly *with* a Prometheus; without one, silence.
- **A dashboard.** Grafana JSON is not audited here.
- **A recording rule that looks expensive.** Without cardinality data
  it is speculation. If the team wants proof, hand them
  `promtool tsdb analyze` and let them run it against real data.
