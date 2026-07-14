# Deep PromQL rule checks — the AR-12+ extension catalogue

`alert-rule-audit.md` holds AR-01..AR-11 (rule *metadata* + the
core metric-type mistakes). This file holds the deeper **PromQL
correctness, deprecation, and syntax** checks — the ones a real parser
(`pint`) catches and a metadata scan does not. Apply them to every
alerting and recording rule `expr:`. When `pint` is installed, prefer
its output; these heuristics are the fallback for a repo with no `pint`
on PATH.

Every ID continues the `AR-xx` sequence so a finding cites one scheme.
None of these need a live Prometheus.

## Table of Contents

- [Findings catalogue](#findings-catalogue)
- [Gauge-suffix inference — the full list](#gauge-suffix-inference--the-full-list)
- [Native histograms (Prometheus 2.40+/3.0)](#native-histograms-prometheus-240-30)
- [absent() — the silent-absence trap](#absent--the-silent-absence-trap)
- [Vector matching mistakes](#vector-matching-mistakes)
- [Range-window thresholds](#range-window-thresholds)
- [Deprecations and version gates](#deprecations-and-version-gates)
- [PromQL syntax errors that block load](#promql-syntax-errors-that-block-load)
- [What is NOT one of these findings](#what-is-not-one-of-these-findings)

## Findings catalogue

| ID | Severity | Finding | Why it matters |
|----|----------|---------|----------------|
| AR-12 | HIGH | A rate-family call (`rate`, `irate`, `increase`, `delta`, `idelta`) with no range vector `[…]` | Parse error: "expected type range vector … got instant vector". The rule file fails to load — the same class as an AR-03 dead alert but caught at parse time |
| AR-13 | HIGH | `histogram_quantile()` over a classic `_bucket` metric with no `rate()`/`increase()` inside | Feeds cumulative bucket *counts* since process start into the quantile — a value that only ever drifts up. The p95 is garbage |
| AR-14 | MED | Classic `histogram_quantile()` whose aggregation drops the `le` label | Without `le` in the `by(...)` set the buckets collapse and the quantile is undefined/empty. Keep `le`: `sum by (job, le) (rate(m_bucket[5m]))` |
| AR-15 | HIGH | `absent()` wrapping an aggregation, or `absent()` with a `by(...)` clause | `absent(sum(m))` returns empty whenever *any* series exists, so a "target is gone" alert silently never fires. `absent()` yields a single value and takes no `by`. For per-label absence use `group(present_over_time(m[range])) by (l) unless group(m) by (l)` |
| AR-16 | HIGH | `group_left`/`group_right` used with no `on(...)` or `ignoring(...)` | Parse error — the modifier needs a matching key. The rule will not load |
| AR-17 | MED | A binary op joins an `_info`/`_labels`-style metric with no `group_left(...)` | Many-to-one join fails at eval with "multiple matches for labels"; the alert produces no data. Bring the labels over: `m * on(job,instance) group_left(version) target_info` |
| AR-18 | MED | `rate()` range shorter than ~4× the scrape interval (roughly `< 2m`) | Too few samples in the window; the rate is noisy and, at the boundary, wrong. Rule of thumb: `rate_range >= 4 * scrape_interval` |
| AR-19 | LOW | A subquery `[range:res]` whose range is very long (beyond ~7d) in a rule evaluated every few seconds | Each evaluation rescans the whole window. Push the inner series into a recording rule and subquery *that* |
| AR-20 | MED | `predict_linear()` over a short range (roughly `< 10m`) | Extrapolation off two-or-three points is unstable — the "disk full in 4h" alert flaps. Give it `[1h]`-class history |
| AR-21 | LOW | A ratio `expr` divides by `rate()`/`increase()` of a counter with no zero guard | When the denominator is 0 the result is `NaN` and the sample *drops*, so a "error ratio > x" alert goes silent exactly when traffic stops. Guard with `… or vector(0)` or a `> 0` floor on the denominator |
| AR-22 | LOW | `changes()` / `resets()` used as the alert signal | Both only see values *at scrape points*; an event between scrapes is invisible. Acceptable for slow signals, misleading for fast ones — note it |
| AR-23 | MED | Different metric *types* combined by arithmetic (`counter × gauge`, `latency / memory`, …) | Each type has different semantics; the combination is usually meaningless. Exception: `_bucket` inside `histogram_quantile()` is the correct classic-histogram pattern, not a counter misuse |
| AR-24 | LOW | Dimensions baked into the metric *name* (`http_requests_GET_total`, `cpu_0_usage`, `..._500_...`) | Method, status class, or an index belongs in a label, not the name. A named-in dimension can't be aggregated and invites double-counting |
| AR-25 | LOW | A regex matcher `=~"literal"` where an equality `="literal"` would do | Exact matches hit the label index directly (roughly 5–10× faster); a regex with no metacharacter is pure overhead. Only flag when the value has **no** regex metacharacter (`. * + ? ^ $ [ ] ( ) \| \`) |
| AR-26 | HIGH | `holt_winters()` in an `expr` | Removed-and-renamed in Prometheus 3.0 to `double_exponential_smoothing()` (itself experimental, behind `--enable-feature=promql-experimental-functions`). On a 3.x server the rule fails to parse |
| AR-27 | LOW | A UTF-8 metric name written as a label (`{my.metric="x"}`) instead of the quoted form `{"my.metric"}` (Prometheus 3.0+) | The dotted token is being read as a label name, so the selector matches nothing. UTF-8 metric names go quoted, first inside the braces |
| AR-28 | HIGH | `offset` placed **before** the range vector (`m offset 1h [5m]`) | Invalid position — `offset` follows the selector, including the `[…]`. Parse error, file will not load |

## Gauge-suffix inference — the full list

AR-04 (rate on a gauge) and AR-05 (raw counter) both hinge on
inferring metric *type* from the name when no `/metrics` fixture is
present. The counter set is small and exact:

`_total` · `_count` · `_sum` · `_bucket` — **counter/histogram
component**, always wrapped in `rate()`/`increase()`.

Everything below reads as a **gauge** (raw value, `avg_over_time`,
`max_over_time`, `delta` — never `rate()`):

`_bytes` · `_ratio` · `_usage` · `_percent` · `_gauge` · `_celsius` ·
`_fahrenheit` · `_temperature` · `_info` · `_size` · `_current` ·
`_limit` · `_available` · `_free` · `_used` · `_utilization` ·
`_capacity` · `_level`

The inference is a heuristic — a custom counter named `requests_handled`
(no `_total`) reads as a gauge. When a name matches *neither* set,
do **not** raise AR-04/AR-05; raise `manual-review` and name the
ambiguity so a reader can overrule.

## Native histograms (Prometheus 2.40+/3.0)

Native histograms are a distinct data model and change what a correct
`expr` looks like. Do not apply the classic `_bucket`/`le` rules to
them:

- They carry **no `_bucket` suffix** and need **no `le` label** in the
  aggregation. Raising AR-14 ("missing le") against a native-histogram
  query is a false positive — gate AR-14 on the presence of a
  `_bucket` metric in the expression.
- They still need `rate()` for a meaningful result:
  `histogram_quantile(0.95, sum by (job) (rate(m[5m])))`.
- The native accessor calls — `histogram_avg`, `histogram_stddev`,
  `histogram_stdvar`, `histogram_count`, `histogram_sum`,
  `histogram_fraction` — should wrap `rate()` too
  (`histogram_count(rate(m[5m]))` gives observations per second). A bare
  accessor over raw samples is a LOW note, not a hard finding.

## absent() — the silent-absence trap

AR-15 is worth stating twice because it is the highest-value check in
this file: an absence alert that silently cannot fire is worse than no
alert. The single-value nature of `absent()` is the whole trap.

- `absent(up{job="api"})` — correct: fires 1 when *no* `up` series for
  that job exists.
- `absent(sum(up{job="api"}))` — broken: the aggregation always returns
  a series while *any* member exists, so `absent()` is 0 forever.
- `absent(up{job="api"}) by (instance)` — broken: `absent()` returns one
  scalar-ish value; `by()` has nothing to group.

Per-label "which instance vanished" is not `absent()`'s job. Use the
`group(present_over_time(m[range])) by (l) unless group(m) by (l)`
shape and note it as the fix.

## Vector matching mistakes

`on()`/`ignoring()` and `group_left()`/`group_right()` are where
correct-looking rules fail at evaluation, not at parse:

- **AR-16** — `group_left`/`group_right` with no `on()`/`ignoring()` is a
  hard parse error.
- **AR-17** — a many-to-one join (typically against an `_info` metric)
  with no `group_left` throws "multiple matches for labels" at eval and
  yields no data. The alert quietly stops working.
- **`on()` with empty parentheses** matches across *all* series — valid,
  but almost never intended in a rule. Flag as a LOW note.

## Range-window thresholds

Concrete numbers behind AR-07/AR-18/AR-19/AR-20, all read straight off
the `[…]` window:

| Call | Sane window | Finding when |
|------|-------------|--------------|
| `rate()` | `>= 4 × scrape_interval`, commonly `[2m]`–`[5m]` | shorter than ~2m ⇒ AR-18 |
| `irate()` | `[2m]`–`[5m]` (only the last two samples are used) | longer than ~5m ⇒ AR-07 |
| `predict_linear()` | `[1h]`-class history | shorter than ~10m ⇒ AR-20 |
| subquery `[range:res]` | range within a few days | beyond ~7d on a fast eval ⇒ AR-19 |

These are heuristics — the true `rate()` floor depends on the target's
scrape interval, which the repo may not state. When it is unknown, say
so in the finding rather than asserting a hard number.

## Deprecations and version gates

| Symbol | Status | Action |
|--------|--------|--------|
| `holt_winters()` | Removed/renamed in Prometheus 3.0 | AR-26 — replace with `double_exponential_smoothing()` (experimental feature flag) |
| `double_exponential_smoothing()`, `limitk`, `limit_ratio`, `ts_of_*_over_time`, `first_over_time` | Experimental | Need `--enable-feature=promql-experimental-functions`; a rule using them fails on a server without the flag — note the runtime dependency |
| UTF-8 quoted metric names `{"a.b"}` | Prometheus 3.0+ | AR-27 — on a 2.x server the quoted form does not parse; flag the version assumption |

Report a deprecation as the version boundary, not a value judgement:
"`holt_winters()` will not parse on Prometheus 3.x" is checkable;
"holt-winters is old" is not.

## PromQL syntax errors that block load

These are AR-12 / AR-28 plus the structural checks a hand parser can do
before `promtool` is even reached. Each is a rule file that fails
`promtool check rules` — quote promtool's own stderr when it is present,
and fall back to these when it is not:

- Unbalanced `()`, `[]`, `{}`, or an unclosed string.
- A rate-family call with no range vector (AR-12).
- `offset` before the range vector (AR-28).
- A duration token that is not `\d+(ms|s|m|h|d|w|y)` inside `[…]`.
- An unknown query token where a known operator/keyword was meant (a
  typo like `avgg(` / `rte(`) — cite it, suggest the near match.

## What is NOT one of these findings

The same restraint as `alert-rule-audit.md` applies. In particular:

- **A metric the `expr` references that you cannot confirm exists.** No
  live TSDB ⇒ no such finding; that is `pint`'s `promql/series` check
  *with* a Prometheus, silent without one.
- **A "this query is complex, add a recording rule" suggestion.** That is
  optimization advice about a system's query load, not repo hygiene.
  Mention it once at most as a LOW note; never as a HIGH.
- **A threshold or `[range]` value you merely disagree with** when it is
  inside the sane band above. The band flags the clearly-wrong, not the
  merely-different.
