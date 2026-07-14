# Log-pipeline secrets and PII — the SEC-xx catalogue

This is the gate that justifies the skill. A log backend is a
different security domain from the repo: broader read access, longer
retention, replicated to a SaaS, indexed and searchable. Anything the
pipeline *promotes into a field* or *ships as a raw line* is now in
that domain. A credential that leaks here is not "a logging bug" — it
is a credential disclosure, and rotating it is `maintainer-secrets-scan`'s
job once this gate finds it.

Two directions of leak, and the audit must check both:

1. **Credentials in the shipper/backend config itself** (SEC-01..03) —
   the config file is committed, so this overlaps with secret scanning
   but is missed by generic scanners that do not know `HTTP_Passwd` is
   a password field.
2. **Secrets and PII flowing *through* the pipeline into the backend**
   (SEC-04..08) — nothing is committed, so a secret scanner sees
   nothing. Only a config audit catches it.

**Report locations, never values.** Cite `file:line` and the key or
field *name*. Never echo the value, never paste a matched log line.

## Table of Contents

- [Findings catalogue](#findings-catalogue)
- [SEC-04 — over-broad tail paths, concretely](#sec-04--over-broad-tail-paths-concretely)
- [SEC-05 — the parser that promotes a header](#sec-05--the-parser-that-promotes-a-header)
- [The filter that should exist](#the-filter-that-should-exist)
- [Backend-side exposure (Loki)](#backend-side-exposure-loki)
- [Handoff](#handoff)

## Findings catalogue

| ID | Severity | Finding | Detection |
|----|----------|---------|-----------|
| SEC-01 | HIGH | Plaintext credential in a shipper/backend config | Any of `HTTP_User`, `HTTP_Passwd`, `Password`, `Secret`, `API_Key`, `Token`, `AWS_Access_Key`, `AWS_Secret_Key`, `access_key_id`, `secret_access_key`, `bearer_token`, `basic_auth.password` whose value is **not** an `${ENV_VAR}` reference, a `*_file` path, or an empty placeholder |
| SEC-02 | HIGH | `tls Off` / `tls false` on an OUTPUT that leaves the host | Log stream, including whatever SEC-04..08 let through, crosses the network in cleartext |
| SEC-03 | HIGH | `tls.verify Off` / `insecure_skip_verify: true` | TLS with no verification is a MITM waiting to happen; the shipper will happily hand its bearer token to anyone who answers |
| SEC-04 | HIGH | Over-broad `tail` `Path` | A glob wide enough to swallow a file that is not a log: `/app/**`, `/etc/**`, `*.env*`, `*.pem`, `*credential*`, `*.kubeconfig`, `id_rsa*`, `.git/**`. See below |
| SEC-05 | HIGH | Parser promotes an auth field with no redaction behind it | A JSON/regex parser whose captured keys include `authorization`, `cookie`, `set-cookie`, `password`, `token`, `api_key`, `secret`, `ssn`, `card`, `email` — and no downstream FILTER removes or masks them |
| SEC-06 | MED | No redaction stage at all on a pipeline that parses request/response bodies | Bodies carry whatever the app puts in them. A pipeline that parses them and ships them raw is a PII pump. See "the filter that should exist" |
| SEC-07 | MED | `Log_Level debug` / `trace` on a production path | Fluent Bit's own debug logging echoes record content, including the fields SEC-05 flagged, into the container's stdout — which is usually itself being tailed |
| SEC-08 | MED | High-cardinality identifiers promoted to **indexed labels** rather than kept in the line or in structured metadata | `user_id`, `email`, `session_id` as a Loki stream label is both a cardinality bomb (see `cardinality-and-limits.md`) and a PII index. Structured metadata is unindexed and the correct home |
| SEC-09 | LOW | Backend without `auth_enabled` / multi-tenancy in a shared deployment | Any tenant reads every tenant's logs |
| SEC-10 | LOW | No `retention_period` on the backend | Leaked PII lives forever; a retention policy bounds the blast radius of every finding above |

## SEC-04 — over-broad tail paths, concretely

The classic Fluent Bit tail input:

```ini
[INPUT]
    Name          tail
    Path          /var/log/containers/*.log
    Exclude_Path  /var/log/containers/*fluent-bit*.log
    Tag           kube.*
```

That is fine. These are not:

| Path | What it also swallows |
|------|-----------------------|
| `/app/**` or `/app/**/*` | `.env`, `config/secrets.yml`, `*.pem` — anything the app ships next to its logs |
| `/var/log/*` (no `Exclude_Path`) | Fluent Bit's **own** log, if it writes there → a feedback loop that amplifies until the buffer dies |
| `/etc/**` | Config, certs, kubeconfigs |
| `*.log*` with a rotation suffix glob | Rotated files re-read after every rotation without `DB` set → duplicate ingestion |

Two rules:

- The `Path` glob must be **rooted in a log directory**, not in an
  application or config root.
- A tail on `/var/log/containers/` or any path the shipper itself
  writes into **must** carry an `Exclude_Path` for the shipper's own
  log. Missing that is a log storm, not a leak — but it takes the
  backend down just as effectively.

## SEC-05 — the parser that promotes a header

```ini
[FILTER]
    Name    parser
    Match   app.*
    Key_Name log
    Parser  json
```

That flattens the whole JSON body into top-level record fields. If the
app logs its request context — and most structured loggers do — the
record now has `authorization`, `cookie`, and whatever the request
carried, as first-class fields. Elasticsearch/Loki index them or store
them; either way they are searchable by anyone with backend read.

The finding is **not** "you parsed JSON". The finding is "you parsed
JSON and there is no filter behind it that removes the sensitive keys".

## The filter that should exist

Any of these downstream of the parser clears SEC-05/SEC-06. The audit
looks for *one* of them matching the same tag:

```ini
# Drop the fields outright — the safest form.
[FILTER]
    Name    record_modifier
    Match   app.*
    Remove_key authorization
    Remove_key cookie
    Remove_key set_cookie
    Remove_key password
    Remove_key api_key

# Or mask them (Lua), when the field's presence is itself signal.
[FILTER]
    Name    lua
    Match   app.*
    script  redact.lua
    call    redact
```

Equivalent stages in the other shippers count too: a Promtail/Alloy
`replace` stage in the pipeline, a Vector `remap` transform, an
OpenTelemetry Collector `attributes` processor with `delete`/`hash`
actions. The audit is looking for *a redaction stage on the path*, in
whatever tool the repo uses — not for a specific plugin name.

If none exists **and** the pipeline parses structured bodies, raise
SEC-06 and name the tag that is unprotected.

## Backend-side exposure (Loki)

| Key | Finding |
|-----|---------|
| `auth_enabled: false` in a shared/multi-tenant deployment | SEC-09 — no tenant isolation |
| `server.http_tls_config` / `grpc_tls_config` absent on a networked deployment | SEC-02 class — inter-component traffic in cleartext |
| storage credentials inline (`access_key_id`, `secret_access_key`) | SEC-01 — should be an IAM role, a workload identity, a managed identity, or a secret mounted from the platform's secret store |
| `limits_config.retention_period` absent + `compactor.retention_enabled: false` | SEC-10 — nothing ages out |

## Handoff

A SEC-01 finding means a credential is **committed to the repo**. Stop
the pipeline audit's remediation at "found, here is the location" and
hand off:

1. `maintainer-secrets-scan` — confirm the value is live, plan the
   rotation and the git-history purge.
2. `maintainer-redact` — before any of this lands in a public issue or
   PR comment.

Never rotate, never rewrite history, and never paste the value from
here.
