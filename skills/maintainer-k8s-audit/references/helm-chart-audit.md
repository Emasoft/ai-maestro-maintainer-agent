# Helm chart audit

A chart is a program that emits manifests. Auditing the chart means
auditing the program's *structure* and then auditing its *output*
(the rendered manifests, per k8s-manifest-checks.md). `helm lint` does
only the first half.

## Table of Contents

- [The render-then-scan contract](#the-render-then-scan-contract)
- [Chart structure and dependency pinning](#chart-structure-and-dependency-pinning)
- [values.yaml and values.schema.json](#valuesyaml-and-valuesschemajson)
- [Template pitfalls, hooks and checklist](#template-pitfalls-hooks-and-checklist)

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

## Template pitfalls, hooks and checklist

### Template pitfalls that become security bugs

| Pattern | Sev | Why |
|---|---|---|
| `image: {{ .Values.image.repository }}:{{ .Values.image.tag \| default "latest" }}` | HIGH | the tag DEFAULTS to a mutable tag when unset — the rendered manifest is unpinned |
| `image: ...:{{ .Chart.AppVersion }}` | MEDIUM | ties the image to a mutable semantic tag, never a digest |
| `{{ .Values.x \| nindent 4 }}` where `indent` was meant (or vice versa) | HIGH | `nindent` prepends a newline, `indent` does not; the wrong one corrupts the block — a mis-indented `securityContext` renders as a sibling, not a child, and applies nothing |
| an unquoted string value (`port: {{ .Values.port }}`) | MEDIUM | a numeric-looking value is emitted as an int where a string was required, or a `y`/`no` becomes a bool — YAML's type coercion bites at deploy time |
| `{{ toYaml .Values.resources }}` without `nindent` | HIGH | the block lands at column 0 and breaks the document |
| `lookup` used at template time | MEDIUM | reads live cluster state during render — the chart is not reproducible and behaves differently in `--dry-run` |

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
`| default ""` for anything security-relevant.

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
