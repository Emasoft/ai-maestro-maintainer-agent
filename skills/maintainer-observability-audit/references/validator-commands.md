# Validator commands — the real tools, the real flags

Everything here is a first-party validator that runs **offline against
files in the repo**. Nothing here needs a live Prometheus or Loki
except where marked. Probe every binary before calling it; a missing
tool is a `notes[]` entry, never a crash.

## Table of Contents

- [Tool inventory and probe](#tool-inventory-and-probe)
- [promtool](#promtool)
- [PrometheusRule CRD extraction](#prometheusrule-crd-extraction)
- [pint — deeper PromQL rule lint](#pint--deeper-promql-rule-lint)
- [amtool — Alertmanager config and routes](#amtool--alertmanager-config-and-routes)
- [Loki](#loki)
- [Fluent Bit](#fluent-bit)
- [Degrade matrix](#degrade-matrix)

## Tool inventory and probe

```bash
for t in promtool pint amtool loki logcli fluent-bit; do
  if command -v "$t" >/dev/null 2>&1; then
    printf '%-12s %s\n' "$t" "$("$t" --version 2>&1 | head -n1)"
  else
    printf '%-12s missing\n' "$t"
  fi
done
```

Install via package manager or the vendor's release archive — never
pipe a remote script into a shell. `promtool` ships inside the
Prometheus tarball; `amtool` inside the Alertmanager tarball;
`fluent-bit` and `loki` are packaged by their vendors; `pint` is a
single Go binary from cloudflare/pint.

## promtool

`promtool` is the authoritative validator for Prometheus config and
rule files. It parses the same code path the server does, so a pass
here means the server will load the file.

```bash
# Server config. Also validates every rule file referenced by rule_files:.
promtool check config prometheus.yml

# Rule files directly (alerting + recording rules).
promtool check rules rules/*.yml

# Turn lint warnings into failures — the release-gate form.
promtool check rules --lint=all --lint-fatal rules/*.yml
promtool check config --lint=all --lint-fatal prometheus.yml

# Rule unit tests, if the repo ships any (a file with `rule_files:` +
# `tests:` — this is the only way to prove an alert actually fires).
promtool test rules tests/*.yml
```

Notes:

- `--lint` accepts `all`, `duplicate-rules`, or `none`; the default is
  `duplicate-rules`. `--lint-fatal` makes a lint finding a non-zero
  exit. Confirm the set your build supports with
  `promtool check rules --help` — flags vary across Prometheus majors.
- Exit non-zero ⇒ **HIGH**. Quote promtool's stderr verbatim in the
  report; it names the file, line, and the offending token.
- `promtool tsdb analyze <data-dir> --limit=20` reports the highest-
  cardinality metric names and label pairs. It needs a **TSDB data
  directory**, which a repo does not contain — mention it as an
  operator follow-up when a `CARD-xx` finding is theoretical and the
  team wants proof. Do not fabricate its output.
- `promtool check metrics` reads Prometheus exposition format on
  **stdin** and lints metric names/HELP. Only useful if the repo
  commits a fixture of scraped output.

## PrometheusRule CRD extraction

In a Kubernetes repo the rules usually do not live in a plain rule
file — they live inside a `kind: PrometheusRule` custom resource, with
the real rule groups under `.spec`. `promtool` cannot read that: it
expects the bare `groups:` document. Extract first.

```bash
# One CRD → a rule file promtool understands.
python3 - "$CRD" <<'PY' > /tmp/rules-from-crd.yaml
import sys, yaml
doc = yaml.safe_load(open(sys.argv[1]))
yaml.safe_dump(doc["spec"], sys.stdout, sort_keys=False)
PY
promtool check rules /tmp/rules-from-crd.yaml
```

A multi-document file (`---`-separated) needs `yaml.safe_load_all` and
one temp file per document. When reporting a finding, map the line
number back to the **CRD**, not the temp file — search the CRD for the
rule's `alert:`/`record:` name and cite that line, or cite the CRD
file with the rule name and no line if the mapping is ambiguous.

## pint — deeper PromQL rule lint

`pint` (cloudflare/pint) catches rule problems promtool does not:
comparison-free alert expressions, `rate()` on a gauge, a regex matcher
that should be an equality, aggregations that drop needed labels.

```bash
pint lint rules/            # lint a directory or explicit files
pint ci                     # lint only the rules changed on this branch
pint config                 # print the active check set
```

Its offline checks (no Prometheus needed) cover PromQL syntax, rate
usage, regex matchers, aggregation, vector matching, alert comparison
operators, `for` values, and duplicate rules. Checks whose names and
availability vary by version — run `pint config` and report what that
build actually runs rather than assuming a name. Checks in the
`promql/series` family need a live Prometheus configured in
`.pint.hcl`; skip them in a repo-only audit.

pint findings map to `AR-xx` in `alert-rule-audit.md`. When pint is
present, prefer its output over the hand-rolled heuristics — it has a
real PromQL parser.

## amtool — Alertmanager config and routes

```bash
amtool check-config alertmanager.yml

# Prove a labelled alert reaches the receiver the team thinks it does.
amtool config routes test --config.file=alertmanager.yml \
  severity=critical service=api
amtool config routes show --config.file=alertmanager.yml
```

`check-config` exit non-zero ⇒ HIGH. A route test that lands on the
default/catch-all receiver when the rule carries `severity: critical`
is worth a MED — the page will go nowhere useful.

## Loki

```bash
# Config validation. Exits non-zero and prints the offending key.
loki -config.file=loki-config.yaml -verify-config

# Same, without installing Loki on the host.
docker run --rm -v "$PWD:/etc/loki" grafana/loki:3 \
  -config.file=/etc/loki/loki-config.yaml -verify-config
```

**Do not run `promtool check rules` on a Loki ruler rule file.** The
file's shape (`groups: → rules: → expr:`) is identical, but `expr` is
**LogQL**, and promtool parses it as PromQL — you get a confident,
completely bogus syntax error. For Loki rule files:

1. Structural YAML check (groups/rules/expr/for/labels present).
2. Apply the `AR-xx` checks that are language-neutral (missing `for:`,
   missing `severity`, no comparison operator).
3. Prove the LogQL parses only against a live Loki, and only when the
   caller supplies one:

   ```bash
   LOKI_ADDR=https://loki.internal:3100 \
     logcli query '<expr>' --limit=1 --since=5m
   ```

   A parse error comes back from the server as a 400 with the position.
   This is **opt-in** — the default audit never reaches the network.

If `cortextool` (grafana/cortex-tools) is on the host it can lint Loki
rule files directly; confirm the flags on the installed build with
`cortextool rules lint --help` before relying on them.

## Fluent Bit

```bash
# Classic .conf and YAML (2.x+) both work. Exit non-zero = will not start.
fluent-bit -c fluent-bit.conf --dry-run
fluent-bit -c fluent-bit.yaml --dry-run
```

`--dry-run` loads every plugin, resolves `@INCLUDE`d files and the
parser database, and exits without shipping a byte. It is the single
highest-value check in this skill: a config that fails here is a
CrashLooping DaemonSet on the next rollout.

If the binary is absent, run the static audit (`SEC-xx`, `CARD-xx`)
and emit exactly one note: *dry-run skipped, fluent-bit not on PATH;
run it in CI or in the fluent/fluent-bit image*. Do not fail the audit
for the missing binary unless the caller passed `--require-tools`.

## Degrade matrix

| Constraint | Behaviour |
|---|---|
| `promtool` missing | Structural YAML check of rule files; all `AR-xx` heuristics still run; note the skip |
| `pint` missing | promtool + heuristics only; no note needed (pint is a bonus) |
| `fluent-bit` missing | Static section audit only; one note with the skip reason |
| `loki` missing | YAML + `limits_config`/`auth_enabled` key audit only; note the skip |
| No network / no live Loki | Skip `logcli`; LogQL exprs get structural checks only, marked `manual-review` |
| Config uses env interpolation the validator cannot resolve | Not a finding — record `unresolved-env-reference` and keep going |
| `--require-tools` passed | Every missing validator becomes a HIGH finding |
