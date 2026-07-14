# Fluent Bit config audit — structure, routing, plugins, OTel (FB-xx)

`--dry-run` (see [validator-commands](validator-commands.md)) is the
authoritative "does it start?" check. When the binary is absent, or as
a static pass that runs regardless, these `FB-xx` checks catch the
config faults `--dry-run` would have caught plus two it does not: a
**dead tag route** (a config that loads but silently ships nothing) and
plugin-level **required-parameter** gaps. They complement the
`SEC-xx` (secrets) and `CARD-xx` (backpressure) catalogues, which own
the leak and resource findings; this file owns *load, route, and
plugin-shape*.

Classic `.conf` (INI) shape assumed. YAML (2.x) carries the same
sections under different syntax; `--dry-run` handles both, the static
parser branches on the extension.

## Table of Contents

- [Findings catalogue](#findings-catalogue)
- [Structure and loading](#structure-and-loading)
- [Required-parameter matrix](#required-parameter-matrix)
- [Valid plugin names](#valid-plugin-names)
- [Tag routing — the dead-route check](#tag-routing--the-dead-route-check)
- [Service and resource thresholds](#service-and-resource-thresholds)
- [Plugin-level security](#plugin-level-security)
- [OpenTelemetry output (2.x+)](#opentelemetry-output-2x)
- [Kubernetes tail specifics](#kubernetes-tail-specifics)

## Findings catalogue

| ID | Severity | Finding | Detection |
|----|----------|---------|-----------|
| FB-01 | HIGH | No `[INPUT]` section | Required — nothing to read; the config will not start |
| FB-02 | HIGH | No `[OUTPUT]` section | Required — nothing to ship; will not start |
| FB-03 | MED | No `[SERVICE]` section | Recommended; without it flush/log-level/parsers-file defaults apply unstated |
| FB-04 | HIGH | Malformed `[section]` header, empty `[]`, or a parameter line outside any section | INI parse failure — pod will not boot |
| FB-05 | LOW | Mixed tabs and spaces in one indent | Fragile; some parsers mis-split the key/value |
| FB-06 | note | An `@INCLUDE`d file is **not** statically validated | Validate each included file separately; `--dry-run` resolves them, the static parser does not |
| FB-07 | HIGH | A plugin section missing a required parameter | Per the matrix below |
| FB-08 | LOW | Unknown plugin `Name` in an INPUT/FILTER/OUTPUT | Typo, or a plugin newer than the known set — plugin-specific checks are skipped, so state that |
| FB-09 | MED | A FILTER/OUTPUT `Match`/`Match_Regex` that matches **no** produced tag | Dead route — the stage silently processes/ships nothing. See below |
| FB-10 | MED | `[SERVICE] Flush` `< 1` (CPU burn) or `> 10` seconds (latency) | Out of the sane 1–10s band |
| FB-11 | MED | An `[OUTPUT]` with no `Retry_Limit` | Infinite retries against a dead backend feed the backpressure loop |
| FB-12 | HIGH | `[SERVICE] HTTP_Server On` with `HTTP_Listen 0.0.0.0` | The metrics/health API is exposed on every interface |
| FB-13 | MED | `forward` OUTPUT with `Require_ack_response On` but no `Shared_Key` | Acked forward with no authentication key |
| FB-14 | HIGH | `opentelemetry` OUTPUT `Header` carrying a literal `Bearer …` token (no `${ENV}`) | SEC-01 class — a credential committed to the repo |
| FB-15 | HIGH | `opentelemetry` OUTPUT `Port` outside 1–65535 | Invalid port; will not start |

FB-14/FB-12/FB-13 are security findings — hand them off exactly like the
`SEC-xx` catalogue says (report location + key name, never the value).

## Structure and loading

The parser reads top-to-bottom, tracking the current section:

- A line starting `[` must end `]` and name a non-empty section
  (`SERVICE`, `INPUT`, `FILTER`, `OUTPUT`, `PARSER`, `MULTILINE_PARSER`).
  Anything else is FB-04.
- A `key value` (whitespace-delimited) or `key = value` line before any
  section header is FB-04 (parameter outside a section).
- Lines starting `#` are comments; `@INCLUDE <file>` and `@SET k=v` are
  preprocessor directives. An unknown `@`-directive is a warning; an
  `@INCLUDE` is FB-06 (validate the target separately).
- Keys are case-insensitive; normalise before matching (`Mem_Buf_Limit`
  == `mem_buf_limit`).

## Required-parameter matrix

FB-07 fires when a required key is absent. Verified against the
Fluent Bit classic schema:

| Section / plugin | Required | Recommended (else a note) |
|------------------|----------|---------------------------|
| Any `[INPUT]` | `Name` | `Tag` (except `forward`, which sets tags dynamically) |
| `[INPUT tail]` | `Name`, `Path` | `Mem_Buf_Limit` (CARD-05), `DB` (CARD-06), `Skip_Long_Lines` |
| Any `[FILTER]` | `Name`, and `Match` **or** `Match_Regex` | — |
| `[FILTER parser]` | `Key_Name`, `Parser` | `Reserve_Data On` |
| `[FILTER nest]` | `Operation` (`nest`\|`lift`), `Nested_under` | — |
| `[FILTER rewrite_tag]` | `Rule` | — |
| `[FILTER throttle]` | `Rate` | — |
| `[FILTER multiline]` | `multiline.parser` | — |
| Any `[OUTPUT]` | `Name`, and `Match` **or** `Match_Regex` | `Retry_Limit` (FB-11) |
| `[OUTPUT es]`/`elasticsearch` | `Host` | `Logstash_Format` or `Index`; `tls` in prod |
| `[OUTPUT kafka]` | `Brokers`, `Topics` | `Format` |
| `[OUTPUT loki]` | `Host` | `labels` or `auto_kubernetes_labels On` |
| `[OUTPUT s3]` | `bucket`, `region` | `compression`, `s3_key_format` |
| `[OUTPUT cloudwatch_logs]` | `region`, `log_group_name` | `auto_create_group` |
| `[OUTPUT http]` | `Host` | `URI`, `Format`, `Compress` |
| `[OUTPUT forward]` | `Host` | `Shared_Key` when acked (FB-13) |
| `[OUTPUT file]` | `Path` | — |
| `[OUTPUT opentelemetry]` | `Host` | `Port`, a `*_uri`, `Header` auth, `add_label` |
| `[PARSER]` | `Name`, `Format` (`json`\|`regex`\|`ltsv`\|`logfmt`) | `Regex` when `Format regex`; `Time_Format` when `Time_Key` is set |
| `[MULTILINE_PARSER]` | `Name`, `Type` (`regex`), at least one `rule` | `flush_timeout` |

## Valid plugin names

FB-08 checks the `Name` against the known set. A miss is a typo or a
newer plugin — not automatically wrong, but plugin-specific checks stop:

- **INPUT:** tail, systemd, tcp, udp, forward, http, syslog, docker,
  kubernetes, dummy, and the process-spawning exec input.
- **FILTER:** grep, kubernetes, parser, modify, nest, rewrite_tag,
  throttle, multiline, record_modifier, lua, geoip2, expect,
  type_converter, stdout, log_to_metrics, wasm.
- **OUTPUT:** es/elasticsearch, kafka, loki, s3, cloudwatch_logs, http,
  forward, stdout, file, opentelemetry, null, influxdb, datadog, splunk,
  stackdriver, azure, tcp, udp, nats, firehose, kinesis_streams, gelf,
  pgsql.

## Tag routing — the dead-route check

FB-09 is the check `--dry-run` does not do: a config can be perfectly
valid and still route nothing, because a `Match` pattern lines up with
no tag any INPUT (or `rewrite_tag` FILTER) actually emits. That OUTPUT
loads clean and ships zero records forever.

The audit simulates the tag flow:

1. Collect every `Tag` from the INPUT sections — the initial produced
   set.
2. Walk FILTERs in order. A `rewrite_tag` FILTER's `Rule` emits a new
   tag (`$KEY REGEX NEW_TAG KEEP` — field 3 is the new tag, `*` if it
   interpolates a record key); add those to the produced set.
3. For every FILTER and OUTPUT, its `Match` (glob, `*` = all) or
   `Match_Regex` must overlap at least one produced tag. No overlap ⇒
   FB-09, naming the pattern and the line.

A `Match_Regex` whose overlap with a wildcard tag can't be decided
statically is reported as ambiguous (verify with `--dry-run`), not as a
hard miss.

## Service and resource thresholds

| Key | Sane band | Finding |
|-----|-----------|---------|
| `[SERVICE] Flush` | 1–10 s | `<1s` CPU burn / `>10s` latency ⇒ FB-10 |
| `[INPUT tail] Mem_Buf_Limit` | ~10MB–500MB | outside ⇒ CARD-05 |
| `[INPUT tail] DB` | present | absent ⇒ CARD-06 (restart re-ingests from byte 0) |
| `[OUTPUT] Retry_Limit` | set | absent ⇒ FB-11 (infinite retries) |
| `[OUTPUT] storage.total_limit_size` | set | absent ⇒ CARD-07 |

`Log_Level` must be one of `off`, `error`, `warn`, `info`, `debug`,
`trace`; `debug`/`trace` on a production path is SEC-07 (the shipper
echoes record content into its own stdout).

## Plugin-level security

These overlap the `SEC-xx` catalogue but are Fluent-Bit-plugin-specific,
so the values-vs-locations rule applies — report `file:line` + the key
name, never the secret:

- **Hardcoded credential.** Any of `HTTP_User`, `HTTP_Passwd`,
  `Password`, `AWS_Access_Key`, `AWS_Secret_Key`, `Secret`, `API_Key`,
  `Token` whose value does **not** begin `${` (an env reference) is
  SEC-01.
- **`tls Off` / `tls.verify Off`** on an OUTPUT that leaves the host —
  SEC-02 / SEC-03.
- **`HTTP_Server On` + `HTTP_Listen 0.0.0.0`** — FB-12, the built-in
  metrics/health endpoint on every interface. A network INPUT (http,
  tcp, udp, forward, syslog) bound to `0.0.0.0` is the SEC-side twin.
- **`forward` OUTPUT acked without `Shared_Key`** — FB-13.

## OpenTelemetry output (2.x+)

The `opentelemetry` OUTPUT is the modern shipper and has its own shape:

- `Host` required (FB-07); `Port`, if given, must be 1–65535 (FB-15) —
  the default is 4317 (gRPC) / 4318 (HTTP).
- A `Header` carrying a literal `Bearer …` with no `${ENV}` is FB-14 (a
  committed token). The safe form reads the token from the environment,
  e.g. `Header Authorization Bearer ${OTEL_TOKEN}`.
- `tls Off` / `tls.verify Off` here is SEC-02 / SEC-03 exactly as for any
  other networked OUTPUT.
- Missing `metrics_uri`/`logs_uri`/`traces_uri`, missing auth `Header`,
  or no `add_label` for resource attributes are notes, not findings.

## Kubernetes tail specifics

When a `tail` `Path` is under the container-log tree (or the path
mentions kube), two K8s-only checks apply:

- **FB-17** (MED, also SEC-04) — no `Exclude_Path` for the shipper's own
  log. Fluent Bit tailing its own output is a feedback loop that
  amplifies until the buffer dies. The classic guard:
  `Exclude_Path /var/log/containers/*fluent-bit*.log`.
- **FB-18** (LOW) — a K8s setup with no `kubernetes` FILTER gets no pod
  metadata enrichment. A recommendation, not a defect. `Buffer_Size 0`
  on that filter is the documented performance setting.
