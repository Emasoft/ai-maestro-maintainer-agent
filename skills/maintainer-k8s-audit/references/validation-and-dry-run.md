# Dynamic validation — server-side dry-run and change detection

The static scanners in [scanner-toolchain.md](scanner-toolchain.md) grade
a manifest in isolation. They cannot see the cluster's admission
controllers, its quotas, its policy engine (OPA/Gatekeeper, Kyverno), or
whether a referenced ConfigMap actually exists. A server-side dry-run can.
This is the validation stage that runs against a real API server WITHOUT
mutating it — the audit's most thorough check when a cluster context is
available, and strictly read-only.

## Table of Contents

- [Server-side dry-run — the admission and policy gate](#server-side-dry-run--the-admission-and-policy-gate)
- [Client dry-run, kubectl diff and cluster-unreachable handling](#client-dry-run-kubectl-diff-and-cluster-unreachable-handling)
- [The dry-run failure taxonomy](#the-dry-run-failure-taxonomy)
- [Helm dry-run and change detection](#helm-dry-run-and-change-detection)
- [kubeconform chart rubric and CRD schema introspection](#kubeconform-chart-rubric-and-crd-schema-introspection)

## Server-side dry-run — the admission and policy gate

```bash
kubectl apply --dry-run=server -f manifests/
```

`--dry-run=server` sends the object through the full admission chain and
returns what WOULD happen, persisting nothing. It is the only check that
sees:

- admission webhooks (mutating and validating),
- a policy engine — OPA/Gatekeeper, Kyverno, or a Pod Security admission
  level — rejecting the pod,
- a `ResourceQuota` or `LimitRange` that the request violates,
- a missing target namespace,
- a `ConfigMap`/`Secret`/`ServiceAccount` reference that does not resolve,
- server-side field validation the static schema cannot express.

Run it in `gate` mode when a cluster context is present; it catches the
class of failure that passes every static scanner and then fails at
`kubectl apply` time. It mutates nothing, so it stays within triage's
read-only contract.

## Client dry-run, kubectl diff and cluster-unreachable handling

Validating a change without a full server round-trip, and what each of
these modes can and cannot see.

### Client dry-run and its blind spot

```bash
kubectl apply --dry-run=client -f manifests/          # local only, no API server
kubectl apply --dry-run=client --validate=false -f m  # parse-only — DANGEROUS as a gate
```

`--dry-run=client` renders and validates locally without contacting the
cluster — useful when offline, but it sees none of the admission/policy/
quota surface above. `--validate=false` goes further and **disables schema,
type, and required-field checking entirely** — it reduces the command to a
YAML parse. Treat a green `--dry-run=client --validate=false` as proof of
nothing; never let it stand in for `kubeconform -strict` or a server-side
dry-run. If a repo's CI uses it as its only "validation", that is itself a
MEDIUM finding.

### kubectl diff — auditing a change to a live resource

```bash
kubectl diff -f manifests/deployment.yaml
```

When the audit target is an UPDATE to an already-applied resource,
`kubectl diff` shows exactly what the apply would change — surfacing an
unintended field removal, a defaulted value being overwritten, or a
narrowing that would restart pods. Read-only; it is the change-review
companion to the dry-run.

### Cluster unreachable — skip, do not fail

A dry-run needs a reachable API server. When there is none, the audit must
distinguish "cannot reach the cluster" (skip this stage, note it) from "the
manifest is invalid" (a real finding). The connection-error signatures that
mean *skip, not fail*:

```text
connection refused
no such host
i/o timeout
tls handshake timeout
unable to connect to the server
no configuration has been provided
the server doesn't have a resource type
```

Match these and downgrade the dry-run to a recorded coverage gap — the same
discipline as a `kubeconform` missing schema. A dry-run stage that fails the
audit merely because no cluster is wired up is a false positive.

## The dry-run failure taxonomy

Not every dry-run error means the manifest is wrong. Classify the output
into four buckets before reporting:

| Class | Signature | Action |
|---|---|---|
| connection error | the skip-set above | skip the stage, note the coverage gap — NOT a finding |
| discovery / OpenAPI error | `couldn't get resource list`, `error getting OpenAPI` | skip; the cluster's discovery is incomplete, not the manifest |
| validation error | admission/quota/policy rejection, invalid field | RECORD — this is the real finding |
| parse error | `error converting YAML`, `error parsing` | the YAML is broken; fix syntax FIRST. A client-side fallback repeats the identical parse error — do not retry it |

The parse-error rule is load-bearing: a YAML syntax error blocks the
dry-run entirely, and re-running client-side produces the same error, so
never "retry client-side" on a parse failure — locate and fix the syntax,
then re-run.

## Helm dry-run and change detection

A chart has its own server-side dry-run, on top of the render-then-scan
pass in [helm-chart-audit.md](helm-chart-audit.md):

```bash
helm upgrade --install rel ./chart --dry-run=server --debug     # full admission, no mutation
helm diff upgrade rel ./chart                                    # helm-diff plugin — what changes
```

`--dry-run=server` runs the rendered manifests through admission exactly as
`kubectl apply --dry-run=server` does; older Helm only supports the
client-side `--dry-run`, which shares the client blind spot above. `helm
diff upgrade` (the `helm-diff` plugin) is the chart-level `kubectl diff` —
it shows what an upgrade would change against the live release, catching an
overwrite or a surprise deletion before it ships. Both are read-only; the
skill never runs a mutating `helm upgrade`.

Extra `helm template` audit flags worth knowing:

```bash
helm template rel ./chart --validate --include-crds --kube-version 1.28.0 \
  --show-only templates/deployment.yaml --is-upgrade
```

- `--validate` checks the rendered output against the cluster's OpenAPI
  (needs a context; a stronger check than an offline render).
- `--kube-version 1.28.0` renders the chart's version-gated logic as the
  TARGET cluster would — a chart that emits a removed apiVersion only under
  a specific `.Capabilities.KubeVersion` is caught here.
- `--show-only templates/deployment.yaml` isolates one template when a
  render error needs pinning down.
- `--is-upgrade` exercises the upgrade-only branches (`.Release.IsUpgrade`).

## kubeconform chart rubric and CRD schema introspection

The pass/warn/fail rubric for a chart's rendered output, and how to read a
CRD's schema when the catalog lacks it.

### kubeconform chart pass / warn / fail rubric

When `kubeconform` runs over a rendered chart, its verdicts need triage —
a CRD with no schema is expected, a core-type error is not:

| kubeconform result | Verdict |
|---|---|
| `no schema found` on a **CRD** kind | WARNING — acceptable IF the CRD's `spec` was verified against the operator's published docs; record the coverage gap |
| `no schema found` on a **built-in** kind | should never happen — investigate the schema-location config |
| schema / type / required-field error on any kind | FAIL — a real finding |
| parse error | FAIL — fix syntax first (see the taxonomy above) |

### CRD schema introspection

When a CRD has no catalogue schema, validate its `spec` by hand against the
cluster's own definition, read-only:

```bash
kubectl explain <kind>.spec                       # the live schema, field by field
kubectl explain <kind>.spec.<nestedField>         # drill into a nested field
kubectl get crd <name> -o yaml                     # the full CRD, incl. its openAPIV3Schema
kubectl api-versions                               # every served apiVersion on this cluster
```

`kubectl explain` reads the CRD's own OpenAPI schema off the cluster, so it
is the authoritative field reference for an in-house CRD that no public
catalogue covers. `kubectl api-versions` confirms whether a manifest's
apiVersion is actually served by the target cluster — the runtime check
behind the deprecation findings in
[workload-controllers.md](workload-controllers.md).
