# Scanner toolchain — Kubernetes, Helm, Ansible

## Table of Contents

- [Tool status — what is alive, what is archived](#tool-status--what-is-alive-what-is-archived)
- [kubeconform — schema validation](#kubeconform--schema-validation)
- [Workload scorers — kube-score, kubesec, polaris, kube-linter](#workload-scorers--kube-score-kubesec-polaris-kube-linter)
- [Rendering a chart before scanning it](#rendering-a-chart-before-scanning-it)
- [Documented suppression — the only permitted escape hatch](#documented-suppression--the-only-permitted-escape-hatch)
- [Exit codes](#exit-codes)

## Tool status — what is alive, what is archived

| Tool | Status | Verdict |
|---|---|---|
| `kubeconform` | actively maintained (yannh/kubeconform) | **the** schema validator. Fast, parallel, CRD-aware, self-updating schema fork |
| `kubeval` | **ARCHIVED** upstream (instrumenta/kubeval); schemas many Kubernetes versions behind | Do NOT introduce it. If an entrusted repo's CI already pins it, report a MEDIUM `archived-validator` finding and propose the drop-in swap to `kubeconform` — same schema model, same UX, maintained |
| `kube-score` | actively maintained | opinionated workload scoring; the highest signal-per-second tool here |
| `kubesec` | actively maintained (controlplaneio) | numeric pod-security risk score; complements kube-score |
| `polaris` | actively maintained (FairwindsOps) | policy audit with configurable severities; good CI gate |
| `kube-linter` | actively maintained (StackRox) | static lint, SARIF out, easy to wire into a PR |
| `datree` | **DISCONTINUED** (service shut down) | Do not use. Its CRD schema *catalogue* (`datreeio/CRDs-catalog`) lives on and is still the schema source kubeconform points at |
| `conftest` / OPA Rego | actively maintained | only when the repo already ships Rego policies — do not introduce a policy language into a repo that has none |
| `checkov`, `trivy` | actively maintained | the two this repo's CI already runs |

Install through the host package manager — `brew install kubeconform
kube-score kubesec polaris kube-linter helm yamllint trivy`, `pipx
install checkov ansible-lint` (or `uvx checkov`). Never install a
security tool by downloading a script from a URL and executing it
unreviewed; that is the exact supply-chain shape this skill exists to
find.

### What this repo's CI already runs

`.mega-linter.yml` enables `REPOSITORY_CHECKOV` and `REPOSITORY_TRIVY`.
Both understand Kubernetes manifests and Ansible:

```bash
checkov -d manifests/ --framework kubernetes --output sarif
checkov -d . --framework helm --output sarif        # renders the chart, then scans
checkov -d playbooks/ --framework ansible --output sarif
trivy config manifests/                             # misconfiguration scan
```

So a manifest committed to a repo on this pipeline is **already** gated
in CI. Running them locally is about seeing the finding before the PR
does — not about adding a new gate. In `gate` mode a missing `checkov`
or `trivy` is a HARD FAIL: CI will run them regardless, so a local green
without them proves nothing.

Checkov's Ansible rule IDs are stable and worth knowing by sight:
`CKV_ANSIBLE_1`..`CKV_ANSIBLE_4` (certificate validation disabled on
`uri` / `get_url` / `yum`), `CKV2_ANSIBLE_1`/`CKV2_ANSIBLE_2` (plain
HTTP instead of HTTPS), `CKV_ANSIBLE_5`/`CKV_ANSIBLE_6` (packages
installed without GPG signature verification, or with `force`).

## kubeconform — schema validation

```bash
kubeconform \
  -strict \
  -summary \
  -verbose \
  -ignore-missing-schemas \
  -kubernetes-version 1.31.0 \
  -schema-location default \
  -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' \
  -output json \
  manifests/
```

- `-strict` — **the flag that matters.** It rejects unknown fields. The
  API server silently *drops* a field it does not recognise, so a typo
  like `readOnlyRootFileSystem` (capital S) or `livenessprobe`
  (lowercase p) applies cleanly and hardens nothing. Without `-strict`
  the manifest validates and the container still runs writable. Always
  `-strict`.
- `-ignore-missing-schemas` — needed for CRDs whose schema is not in the
  catalogue. It downgrades "no schema" from an error to a skip. Record
  every skipped kind in the report: an unvalidated CRD is a **coverage
  gap**, not a pass.
- `-schema-location` — repeatable, evaluated in order. `default` is the
  upstream Kubernetes schema set; the second entry above resolves
  community CRDs from the CRDs-catalogue. For an in-house CRD, point a
  third `-schema-location` at the repo's own converted schema rather
  than accepting the skip.
- `-kubernetes-version` — pin it to the version the cluster actually
  runs. Validating against a newer version hides a field that does not
  exist yet on the target cluster.

**Line numbers.** kubeconform does not report file-absolute lines.

- *Parse errors* (`error converting YAML to JSON: yaml: line N`) — `N`
  is relative to the DOCUMENT, not the file. Convert:
  `file_line = doc_start_line + N - 1`.
- *Schema errors* — a JSON path only, no line at all (e.g. `at
  '/spec/template/spec/containers/0/ports/0/containerPort': got string,
  want integer`). Locate the field by name within that document.

Always present file-absolute line numbers in the report. A reviewer who
has to count documents to find the error will not fix it.

Schema validation is static — it grades the manifest in isolation. The
server-side dry-run that ALSO sees admission webhooks, a policy engine,
quotas and missing references is in
[validation-and-dry-run.md](validation-and-dry-run.md); run it read-only
whenever a cluster context is available.

## Workload scorers — kube-score, kubesec, polaris, kube-linter

### kube-score — workload scoring

```bash
kube-score score --output-format ci manifests/*.yaml
kube-score score --output-format json manifests/*.yaml > kube-score.json
kube-score score --kubernetes-version v1.31 --exit-one-on-warning manifests/
kube-score list                        # every check id, for building an ignore list
```

- `--output-format ci` — one grep-able line per finding; `human` for
  reading, `json` for the report, `sarif` for a PR annotation.
- `--exit-one-on-warning` — turns WARNING into a non-zero exit. Correct
  for `gate` mode; too loud for `scan`.
- `--ignore-test <id>` — the ONLY sanctioned suppression, and only with
  a WHY comment beside it in the calling script or config.

The checks worth knowing by name, because they are the ones that fire:
`container-security-context-user-group-id`,
`container-security-context-readonlyrootfilesystem`,
`container-security-context-privileged`, `container-resources`,
`container-image-tag` (mutable tag), `container-image-pull-policy`,
`pod-probes`, `deployment-has-poddisruptionbudget`,
`deployment-replicas`, `pod-networkpolicy`, `stable-version`
(deprecated apiVersion).

### kubesec — pod-security risk score

```bash
kubesec scan manifests/deployment.yaml
```

Emits JSON: a numeric `score`, plus `advise` (what would raise it) and
`critical` (what dragged it down). It is a *score*, so read the direction
and the drivers, not the absolute number:

- Big negatives: `privileged: true`, `hostNetwork`, `hostPID`,
  `hostIPC`, a `hostPath` volume, `capabilities.add: [SYS_ADMIN]`.
- Positives: `runAsNonRoot: true`, `readOnlyRootFilesystem: true`,
  `capabilities.drop: [ALL]`, `resources.limits.memory`, a
  `seccompProfile`, a non-default `serviceAccountName`.

A negative score on a workload manifest is always at least a HIGH
finding. kubesec takes ONE resource per invocation cleanly — split a
multi-document file before feeding it in.

### polaris — policy audit

```bash
polaris audit --audit-path manifests/ --format pretty
polaris audit --audit-path manifests/ --format json > polaris.json
polaris audit --audit-path manifests/ --set-exit-code-on-danger
polaris audit --audit-path manifests/ --set-exit-code-below-score 90
polaris audit --audit-path manifests/ --config polaris.yaml   # per-repo severities
```

Groups findings into security / efficiency / reliability. Use
`--set-exit-code-on-danger` in `gate` mode. `--set-exit-code-below-score
N` is a blunt instrument — a repo can pass it while carrying one
CRITICAL, so never make it the only gate.

### kube-linter — static lint

```bash
kube-linter lint manifests/ --format json
kube-linter lint manifests/ --format sarif > kube-linter.sarif
kube-linter lint ./chart                      # understands Helm charts directly
kube-linter checks list                       # every check + its description
```

Configure per-repo with `.kube-linter.yaml`. Its highest-value checks
overlap kube-score deliberately — agreement between two independent
tools is what lets you report a finding as certain: `latest-tag`,
`no-read-only-root-fs`, `run-as-non-root`, `privileged-container`,
`unset-cpu-requirements`, `unset-memory-requirements`,
`drop-net-raw-capability`, `dangling-service` (a Service whose selector
matches no pod — an outage waiting to happen), `no-anti-affinity`.

## Rendering a chart before scanning it

None of the scanners above can read a Go template. `{{ .Values.image }}`
is not YAML. A chart MUST be rendered first:

```bash
helm template audit ./chart -f ./chart/values.yaml --include-crds \
  --output-dir "$TMP/rendered"
kube-score score --output-format ci "$TMP"/rendered/**/*.yaml
```

Render once per values file the repo ships. A finding that appears only
under `values-prod.yaml` is the finding that matters.

## Documented suppression — the only permitted escape hatch

A check that genuinely does not apply is suppressed by ID, in the repo's
own config, with a comment saying WHY. Never by disabling the linter,
never by lowering a severity floor, never with `--soft-fail`.

```yaml
# .kube-linter.yaml
checks:
  exclude:
    # WHY: this DaemonSet is the node-exporter; reading the host /proc is
    # its entire purpose. Scoped to this one check, reviewed 2026-07-13.
    - "privileged-container"
```

```yaml
# .ansible-lint
skip_list:
  # WHY: the vendor installer is a signed binary blob with no module
  # equivalent; guarded by `creates:` so it stays idempotent.
  - command-instead-of-module
```

An undocumented suppression is itself a finding (`undocumented-suppression`),
and `gate` mode fails on it.

## Exit codes

| Tool | 0 | non-zero |
|---|---|---|
| `kubeconform` | all resources valid | any invalid resource, or a parse error |
| `kube-score` | no CRITICAL | CRITICAL present (WARNING too, with `--exit-one-on-warning`) |
| `polaris audit` | no danger (with `--set-exit-code-on-danger`) | danger present |
| `kube-linter lint` | no findings | any finding |
| `helm lint` | chart passes | any ERROR (a WARNING alone still exits 0 — unless `--strict`) |
| `ansible-lint` | no violation | `2` = violations found; `1` = ansible-lint itself failed. Do not conflate them: a `1` means the audit did not run, not that the code is clean |
| `yamllint` | clean | `1` = error, `2` = warning (with `-s`) |
