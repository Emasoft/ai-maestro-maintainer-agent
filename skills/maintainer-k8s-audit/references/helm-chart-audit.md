# Helm chart audit

A chart is a program that emits manifests. Auditing the chart means
auditing the program's *structure* and then auditing its *output*
(the rendered manifests, per k8s-manifest-checks.md). `helm lint` does
only the first half.

## Table of Contents

- [The render-then-scan contract](#the-render-then-scan-contract)
- [Chart structure and dependency pinning](#chart-structure-and-dependency-pinning)
- [values.yaml and values.schema.json](#valuesyaml-and-valuesschemajson)
- [Templates, hooks, operators and checklist](#templates-hooks-operators-and-checklist)

## The render-then-scan contract

`helm lint` validates chart structure and Go-template syntax. It cannot
tell you whether the rendered Deployment has a `securityContext`,
because it never renders one path. So the audit is two passes:

```bash
helm lint ./chart --strict --with-subcharts
helm template audit ./chart -f ./chart/values.yaml --include-crds \
  --output-dir "$TMP/rendered"
# then run the k8s-manifest-checks.md catalogue over $TMP/rendered
```

- `--strict` — turns lint WARNINGs into failures. Use it in `gate` mode.
- `--with-subcharts` — lint the dependencies too; a wide-open subchart
  is your problem the moment you depend on it.
- Render ONCE PER VALUES FILE the repo ships (`values.yaml`,
  `values-prod.yaml`, `values-staging.yaml`). A chart hardened under the
  defaults and wide open under the production overlay is wide open. The
  overlay is where the real config lives.
- `helm template` fails while `helm lint` passed → the chart is broken
  along a path lint did not render. HIGH `chart-does-not-render`; name
  the values file that triggered it.
- The server-side dry-run, the extra `helm template` audit flags
  (`--validate`, `--kube-version`, `--show-only`, `--is-upgrade`) and
  `helm diff upgrade` are in
  [validation-and-dry-run.md](validation-and-dry-run.md) — run them when a
  cluster context is available for the checks a static render cannot make.
- **macOS gotcha:** `helm` reporting `Chart.yaml file is missing` when the
  file plainly exists is usually extended attributes
  (`com.apple.provenance` / `com.apple.quarantine`) on the chart files —
  diagnose with `xattr <file>` and clear with `xattr -cr <chart>`. It is an
  environment artefact, not a chart defect; do not report it as a finding.

## Chart structure and dependency pinning

### Chart structure and Chart.yaml

| Finding | Sev | Why |
|---|---|---|
| `Chart.yaml` `apiVersion: v1` | MEDIUM | v1 is the Helm 2 format; a current chart is `apiVersion: v2` (dependencies live in Chart.yaml, not requirements.yaml) |
| missing `Chart.yaml`, `values.yaml`, or `templates/` | HIGH | not a valid chart; `helm` will refuse it |
| `version` not SemVer | MEDIUM | `helm` and every repo index sort by SemVer; a non-SemVer version breaks upgrade ordering |
| `appVersion` unset | LOW | the deployed app version is untracked; NOTES and labels lose it |
| no `.helmignore` | MEDIUM | `helm package` sweeps `.git/`, `.env`, CI files, `*.md` into the tarball and the registry |

`version` is the CHART's version; `appVersion` is the version of the
APP the chart deploys. They move independently — bumping the app image
bumps `appVersion`, changing a template bumps `version`.

### Dependency pinning and Chart.lock

| Finding | Sev | Why |
|---|---|---|
| a dependency `version:` range (`^1.0.0`, `~2.3`, `>=1`) | HIGH | the resolved subchart changes under you; a compromised upstream release is pulled silently |
| `Chart.lock` missing while dependencies are declared | HIGH | nothing records which subchart versions were actually used — the build is not reproducible |
| a dependency `repository:` on plain `http://` | HIGH | the subchart is fetched over an unauthenticated channel |

```yaml
# Chart.yaml
dependencies:
- name: postgresql
  version: "15.5.38"                       # EXACT, not a range
  repository: "https://charts.example.com" # https, and ideally a checksum-verified OCI ref
```

Pin every dependency to an exact version and commit `Chart.lock`.
Pinning to the version `Chart.lock` already resolves is deploy-neutral
(the same bytes deploy) — that is the one dependency edit the audit may
auto-apply.

## values.yaml and values.schema.json

| Finding | Sev | Why |
|---|---|---|
| a credential default in `values.yaml` (`password:`, `token:`, `apiKey:`) | CRITICAL | ships in the packaged chart and every mirror; a default secret is a shipped secret |
| no `values.schema.json` | MEDIUM | a caller can pass a wrong-typed or missing value and get a broken-but-valid render, or a template panic at deploy time |
| a required value with no `required`/no default | MEDIUM | a missing value renders an empty string, producing a subtly wrong manifest instead of a clear failure |
| a Secret's `data:` populated from a `values.yaml` literal | CRITICAL | same as a committed Secret — the value is in the chart |

Constrain the security-relevant surface with a schema so a bad override
fails at lint time, not at deploy time:

```json
{
  "$schema": "https://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["image"],
  "properties": {
    "image": {
      "type": "object",
      "required": ["repository", "tag"],
      "properties": {
        "repository": {"type": "string"},
        "tag": {"type": "string", "pattern": "^sha256:[a-f0-9]{64}$|^v?[0-9]+\\.[0-9]+\\.[0-9]+"},
        "pullPolicy": {"enum": ["IfNotPresent", "Always", "Never"]}
      }
    }
  }
}
```

Adding a schema is deploy-neutral ONLY if `helm lint` still passes with
EVERY values file the repo ships — a schema that rejects an existing
overlay breaks the next release, so re-lint each overlay before shipping
it.

## Templates, hooks, operators and checklist

### Template pitfalls that become security bugs

| Pattern | Sev | Why |
|---|---|---|
| `image: {{ .Values.image.repository }}:{{ .Values.image.tag \| default "latest" }}` | HIGH | the tag DEFAULTS to a mutable tag when unset — the rendered manifest is unpinned |
| `image: ...:{{ .Chart.AppVersion }}` | MEDIUM | ties the image to a mutable semantic tag, never a digest |
| `{{ .Values.x \| nindent 4 }}` where `indent` was meant (or vice versa) | HIGH | `nindent` prepends a newline, `indent` does not; the wrong one corrupts the block — a mis-indented `securityContext` renders as a sibling, not a child, and applies nothing |
| an unquoted string value (`port: {{ .Values.port }}`) | MEDIUM | a numeric-looking value is emitted as an int where a string was required, or a `y`/`no` becomes a bool — YAML's type coercion bites at deploy time |
| `{{ toYaml .Values.resources }}` without `nindent` | HIGH | the block lands at column 0 and breaks the document |
| `lookup` used at template time | MEDIUM | it returns **nil** under `helm template` (it only resolves during a live install/upgrade), so an offline render is wrong; a chart that does `lookup` an existing Secret with a `randAlphaNum` fallback REGENERATES the credential on every apply — non-reproducible and churning |
| a non-deterministic generator — `randAlphaNum`, `uuidv4`, `now`, `randAscii` — inside a persisted Secret / ConfigMap / annotation | HIGH | the value changes on every render and upgrade — spurious diffs, credential churn, a Secret that never stabilises. Generate once and store, or delegate to an external-secrets operator |
| `tpl` applied to a caller-supplied value | HIGH | `tpl` renders its string argument AS a template, so an untrusted value flowing through it is a template-injection vector |
| `{{ if .Values.x \| quote }}` — a formatter piped inside an `if` | MEDIUM | `quote` yields a non-empty string that is ALWAYS truthy, so the condition never tests the real value; test the raw `.Values.x`, never pipe it through a formatter in a boolean context |
| `set` / `unset` used inside a template | MEDIUM | they mutate `.Values` IN PLACE — a hidden cross-template side effect that makes render order significant |
| a resource name from `{{ .Release.Name }}-{{ .Chart.Name }}-…` with no truncation | MEDIUM | a name over 63 chars fails DNS-1123 validation at apply time; truncate with `… \| trunc 63 \| trimSuffix "-"` |
| a rolling/version label (`app.kubernetes.io/version`) inside a Deployment `selector.matchLabels` | HIGH | the selector is immutable, so a version bump can never update it and rolling updates are blocked; keep `version` in `metadata.labels`, never the selector (see [workload-controllers.md](workload-controllers.md)) |

Quote string values, use `nindent` for injected blocks, and default the
image to a digest-or-nothing, never to `latest`:

```yaml
    image: "{{ .Values.image.repository }}@{{ required "image.digest is required" .Values.image.digest }}"
    {{- with .Values.securityContext }}
    securityContext:
      {{- toYaml . | nindent 6 }}
    {{- end }}
```

`required "msg" .Values.x` turns a missing critical value into a clear
render-time failure instead of an empty string. Prefer it over
`| default ""` for anything security-relevant. Two more render-time traps:
`{{ if .Values.optional }}` errors when the key is absent (guard with
`| default ""`), and comparing an integer value against a string with `eq`
silently never matches (coerce with `| toString` first).

**Config change that never rolls the pods.** A `ConfigMap`/`Secret` edit
does NOT restart the workloads that consume it — they keep the old mounted
copy until an unrelated rollout. The audit flags a security-relevant config
with no roll trigger; the remediation is a checksum annotation on the pod
template so any config change forces a rollout:

```yaml
  template:
    metadata:
      annotations:
        checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
```

### Hooks, CRDs and .helmignore

| Finding | Sev | Why |
|---|---|---|
| a `helm.sh/hook` with no `hook-delete-policy` | MEDIUM | the hook Job/Pod lingers after success, accumulating across upgrades |
| a pre-install hook running a privileged or `command`-style Job | HIGH | hooks run with the release's permissions before the workload is audited — a privileged hook is an unaudited privileged pod |
| CRDs placed in `templates/` instead of `crds/` | MEDIUM | CRDs in `templates/` are re-templated and can be deleted on `helm uninstall`; `crds/` are installed once and never upgraded/removed by Helm — know which behaviour the chart relies on |
| `.helmignore` missing or not excluding `.git/`, secrets | MEDIUM | packaging leaks repository internals into the tarball |

```
# .helmignore
.git/
.gitignore
.env
*.tmproj
.DS_Store
ci/
tests/
*.md
```

CRDs are a deliberate design choice, not a bug: `crds/` = install-once,
never touched again by Helm (safe for shared CRDs); `templates/` =
templated and lifecycle-managed (dangerous — an uninstall can take the
CRD and every custom resource with it). Flag the mismatch, name the
consequence, let the human choose.

### Helm audit checklist

- [ ] `Chart.yaml apiVersion: v2`, SemVer `version`, `appVersion` set
- [ ] `helm lint --strict --with-subcharts` passes for EVERY values file
- [ ] `helm template` renders cleanly for EVERY values file
- [ ] rendered manifests pass the k8s-manifest-checks.md catalogue
- [ ] every dependency pinned exact + `Chart.lock` committed
- [ ] no credential default in any `values.yaml`
- [ ] `values.schema.json` present and constrains the image/security surface
- [ ] no `image` tag defaulting to `latest` or a mutable semantic tag
- [ ] `nindent` (not `indent`) on every injected block; string values quoted
- [ ] hooks carry a `hook-delete-policy`; no privileged hook Jobs
- [ ] CRDs in the directory that matches the intended lifecycle
- [ ] `.helmignore` excludes `.git/`, secrets, CI, tests
- [ ] resource names truncated (`trunc 63 | trimSuffix "-"`); no random/time function inside a persisted Secret/ConfigMap
- [ ] operator CustomResources (ArgoCD/Istio/VPA/KEDA/Gateway) audited for wildcard grants and stale apiVersions

### Operator custom resources a chart ships

Many charts render more than built-in kinds — they ship Custom Resources
for operators the cluster runs. `kubeconform` has no schema for most of
these (a WARNING, not a pass — see
[validation-and-dry-run.md](validation-and-dry-run.md)), so their security
posture must be audited by hand. The recurring findings:

| Custom resource | Finding | Sev | Why |
|---|---|---|---|
| ArgoCD `AppProject` | `sourceRepos: ['*']` + `destinations` namespace `'*'` + a `clusterResourceWhitelist` of `{group: '*', kind: '*'}` | HIGH | cluster-wide blast radius — the wildcard-RBAC anti-pattern one layer up; scope the repos, destinations and resource kinds |
| ArgoCD `Application` | `finalizers: [resources-finalizer.argocd.argoproj.io]` | MEDIUM | deleting the Application CASCADES deletion to every resource it manages — confirm the cascade is intended |
| Gateway API `HTTPRoute` / `Gateway` | a cross-namespace backend or Secret reference with no `ReferenceGrant` in the target namespace | HIGH | the reference is silently DENIED — the route or TLS never works; the `ReferenceGrant` must live in the referenced namespace |
| VPA `VerticalPodAutoscaler` | `updateMode: Auto` or `Recreate` | MEDIUM | it EVICTS running pods to resize them; and a VPA plus an HPA on the same metric fight — pick one per metric |
| KEDA `ScaledObject` | `minReplicaCount: 0` / `idleReplicaCount: 0`; a secret inline in the trigger `metadata` | MEDIUM | scales the workload to zero (cold-start latency, dropped work if unintended); put credentials behind a `TriggerAuthentication` / `authenticationRef`, never inline |

**Stale operator CRD apiVersions.** Operator CRs move through their own
apiVersion deprecations, independent of the built-in ones in
k8s-manifest-checks.md. Flag a chart pinned to a superseded group/version
and check it against the operator's current CRD — common examples: Istio
`networking.istio.io/v1beta1` (VirtualService / Gateway / DestinationRule
now have a `v1`), External-Secrets `external-secrets.io/v1beta1` (now `v1`),
Sealed-Secrets `bitnami.com/v1alpha1`. A chart rendering an apiVersion the
target cluster's operator no longer serves fails at apply, exactly like a
removed built-in API.
