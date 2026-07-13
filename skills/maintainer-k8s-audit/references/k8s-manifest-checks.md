# Kubernetes manifest audit — finding catalogue

Every entry: the shape that is wrong, why it is dangerous, and the
hardened form. The hardened YAML is a remediation template, not
something the audit applies on its own — anything that changes cluster
behaviour is a patch for human approval (see the deploy-neutrality rule
in SKILL.md).

## Table of Contents

- [Severity model](#severity-model)
- [Workload security — securityContext, resources, probes](#workload-security--securitycontext-resources-probes)
- [Image references — tags, digests, pull policy](#image-references--tags-digests-pull-policy)
- [Secrets in manifests](#secrets-in-manifests)
- [Cluster access — RBAC, NetworkPolicy, PodSecurity, ServiceAccount](#cluster-access--rbac-networkpolicy-podsecurity-serviceaccount)
- [API deprecations and remediation templates](#api-deprecations-and-remediation-templates)

## Severity model

| Severity | Meaning |
|---|---|
| CRITICAL | direct path to compromise or data loss — root+privileged, a committed Secret, `verbs:["*"]` cluster-wide |
| HIGH | removes a security boundary or makes the deploy unknowable — no securityContext, a mutable image tag, wide RBAC |
| MEDIUM | weakens defence-in-depth — no NetworkPolicy, token automounted where unused, no PodDisruptionBudget |
| LOW | hygiene — missing recommended labels, no replica count set |

## Workload security — securityContext, resources, probes

### Pod and container securityContext

The single highest-value block, and the one most often absent. Two
levels — pod (`spec.template.spec.securityContext`) and container
(`...containers[*].securityContext`); the container level wins on
conflict.

| Finding | Sev | Why |
|---|---|---|
| no `securityContext` at all | HIGH | container runs as root (UID 0) with the default capability set and a writable root filesystem |
| `runAsNonRoot` unset or `false` | HIGH | a compromised process is UID 0 inside the container, one escape from UID 0 on the node |
| `allowPrivilegeEscalation` unset or `true` | HIGH | a setuid binary can gain more privilege than the parent — defeats a dropped-capability set |
| `readOnlyRootFilesystem` unset or `false` | MEDIUM | an attacker can write a payload to the container FS and persist across a probe restart |
| `capabilities.drop` does not include `ALL` | HIGH | the container keeps the ~14 default Linux capabilities (`NET_RAW`, `CHOWN`, `SETUID`, …) it almost never needs |
| `privileged: true` | CRITICAL | full access to every device on the node — effectively root on the host |
| `seccompProfile` unset | MEDIUM | no syscall filtering; `RuntimeDefault` blocks a large class of exploits at near-zero cost |

Hardened pair (pod + container):

```yaml
spec:
  securityContext:                 # pod level
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 2000
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: app
    securityContext:               # container level
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: [ALL]
        add: [NET_BIND_SERVICE]    # ONLY if it binds a port < 1024; else omit
```

`readOnlyRootFilesystem: true` breaks anything that writes to `/`. If
the app needs scratch space, mount an `emptyDir` at the write path
rather than dropping the setting:

```yaml
    volumeMounts:
    - {name: tmp, mountPath: /tmp}
  volumes:
  - {name: tmp, emptyDir: {}}
```

### Resource requests and limits

| Finding | Sev | Why |
|---|---|---|
| no `resources` block | HIGH | the pod can starve its neighbours (no limit) and the scheduler cannot place it well (no request); an OOM elsewhere on the node can evict it |
| `requests` set, `limits.memory` unset | HIGH | a memory leak grows unbounded until the node OOM-kills something — often another tenant |
| `limits.cpu` set very low | MEDIUM | CPU is throttled, not killed; a too-low limit causes latency, not a crash — check against `kubectl top` before "fixing" |
| `requests` == `limits` for memory | INFO | this is *Guaranteed* QoS, the most protected class — a deliberate choice, not a defect |

```yaml
    resources:
      requests: {cpu: "100m", memory: "128Mi"}
      limits:   {cpu: "500m", memory: "256Mi"}
```

Memory limit missing is the direct cause of the OOMKilled runtime
symptom (see cluster-triage.md). Set memory `requests == limits`;
leave a CPU limit generous or unset (CPU throttles, memory kills).

### Probes

| Finding | Sev | Why |
|---|---|---|
| no `readinessProbe` | HIGH | traffic reaches the pod before it is ready — 502s during every rollout |
| no `livenessProbe` | MEDIUM | a wedged process is never restarted; it stays Ready and black-holes traffic |
| `livenessProbe` == `readinessProbe` (same path, aggressive timing) | MEDIUM | a slow-start app fails liveness during boot and enters CrashLoopBackOff — a self-inflicted outage |
| slow-starting app, no `startupProbe` | MEDIUM | liveness kills the app mid-boot; a startupProbe gives it a grace window |

```yaml
    readinessProbe: {httpGet: {path: /readyz, port: http}, initialDelaySeconds: 5, periodSeconds: 10}
    livenessProbe:  {httpGet: {path: /healthz, port: http}, initialDelaySeconds: 15, periodSeconds: 20, failureThreshold: 3}
    startupProbe:   {httpGet: {path: /healthz, port: http}, failureThreshold: 30, periodSeconds: 10}   # 300s to boot
```

Keep liveness and readiness on *different* endpoints, and make liveness
the more forgiving of the two — an aggressive liveness probe is the
manifest cause of a probe-induced CrashLoopBackOff.

## Image references — tags, digests, pull policy

| Finding | Sev | Why |
|---|---|---|
| `image: app:latest` or no tag | HIGH | the deployed bits are unknowable and change under you; a rollback restores the tag, not the image |
| a mutable tag (`app:v1`, `app:stable`) | MEDIUM | better than latest, still repointable at the registry — not reproducible |
| pinned by digest | GOOD | `app@sha256:…` is immutable and verifiable — the audit target |
| `imagePullPolicy: Always` with a digest | LOW | redundant; a digest is already immutable |
| `imagePullPolicy: IfNotPresent` on a mutable tag | MEDIUM | nodes cache stale content under a moving tag |

```yaml
    image: registry.example.com/app@sha256:9b2c...e1   # immutable, verifiable
    imagePullPolicy: IfNotPresent
```

Pin by digest, not just by semantic tag. A `:v1.2.3` tag can be
force-pushed; a `@sha256:…` cannot. Digest pinning changes what deploys,
so it is a proposed patch, never an auto-fix.

## Secrets in manifests

| Finding | Sev | Why |
|---|---|---|
| a `kind: Secret` with populated `data:`/`stringData:` in git | CRITICAL | base64 is encoding, not encryption — the value is in every clone, fork and CI cache |
| a password/token literal in a ConfigMap or an env `value:` | CRITICAL | plaintext credential in the repo |
| a Secret consumed via `envFrom`/`valueFrom.secretKeyRef` (Secret created out-of-band) | GOOD | the reference is safe; the value is not in the repo |

The reference pattern is fine to keep; the committed *value* is the
finding. Rotate first (it is already leaked), then remove from history —
`maintainer-secrets-scan` owns that. Prefer a sealed-secrets / external
secrets operator, or a Secret created by the deploy pipeline, over any
Secret value in git.

## Cluster access — RBAC, NetworkPolicy, PodSecurity, ServiceAccount

### RBAC least privilege

| Finding | Sev | Why |
|---|---|---|
| `verbs: ["*"]` | HIGH | grants create/delete/update where read was needed |
| `resources: ["*"]` or `apiGroups: ["*"]` | HIGH | grants access to Secrets, Nodes, everything |
| a ClusterRoleBinding to the built-in `cluster-admin` | CRITICAL | full control of the cluster from one ServiceAccount |
| `verbs` include `escalate` or `bind` | CRITICAL | the subject can grant itself any permission — an RBAC bypass |
| `verbs` include `impersonate` | CRITICAL | the subject can act as any user or group |
| a Role granting `get`/`list`/`watch` on `secrets` cluster-wide | HIGH | one compromised pod reads every Secret in the cluster |

```yaml
kind: Role                          # namespaced, not ClusterRole, unless truly cluster-scoped
rules:
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["only-this-secret"]   # scope to the exact object where possible
  verbs: ["get"]                         # only the verbs actually used
```

Prefer `Role` over `ClusterRole`; name the exact `resourceNames`; list
only the verbs the workload calls. Narrowing RBAC can break a running
controller, so it is a proposed patch.

### NetworkPolicy

| Finding | Sev | Why |
|---|---|---|
| namespace has NO NetworkPolicy | MEDIUM | Kubernetes default is allow-all — any pod can reach any other pod, cluster-wide |
| a default-deny exists but no matching allow rules | MEDIUM (config) | the workload is isolated but may be unable to reach DNS — check before "fixing" |
| egress open to `0.0.0.0/0` | MEDIUM | a compromised pod has unrestricted outbound access to any external host |

Apply a default-deny per namespace, then add explicit allows. Always
allow DNS egress (port 53 UDP+TCP) or every in-cluster name lookup
fails.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata: {name: default-deny-all, namespace: app}
spec:
  podSelector: {}
  policyTypes: [Ingress, Egress]
```

In `from`/`to`, list items are ORed; within one item,
`namespaceSelector` + `podSelector` are ANDed — a frequent source of
"why can nothing reach this pod" and of over-broad allows.

### PodSecurity admission

The successor to the removed PodSecurityPolicy — namespace labels, not a
cluster object.

| Finding | Sev | Why |
|---|---|---|
| namespace has no `pod-security.kubernetes.io/*` label | MEDIUM | no baseline is enforced; a privileged pod is admitted silently |
| `enforce: privileged` | HIGH | the most permissive level — effectively no policy |

```yaml
metadata:
  labels:
    pod-security.kubernetes.io/enforce: restricted   # reject non-conforming pods
    pod-security.kubernetes.io/warn: restricted      # advisory
    pod-security.kubernetes.io/audit: restricted     # log to the audit trail
```

`warn` and `audit` are advisory and safe to add (deploy-neutral).
`enforce: restricted` REJECTS non-conforming pods, so it can fail the
next deploy of a workload that is not yet hardened — a proposed patch,
applied only after the workloads in the namespace already pass.

### ServiceAccount tokens and host namespaces

| Finding | Sev | Why |
|---|---|---|
| `automountServiceAccountToken` unset on a workload that never calls the API | MEDIUM | a stealable API token is mounted at `/var/run/secrets/...` for no reason |
| pod uses the `default` ServiceAccount | LOW | no per-workload identity; audit and RBAC scoping become impossible |
| `hostNetwork: true` | HIGH | the pod shares the node's network namespace — sees and binds host ports |
| `hostPID: true` / `hostIPC: true` | HIGH | the pod can see and signal every process on the node |
| a `hostPath` volume | HIGH | mounts a node directory into the pod — a path to node compromise (`/`, `/var/run/docker.sock`) |

```yaml
apiVersion: v1
kind: ServiceAccount
metadata: {name: app}
automountServiceAccountToken: false   # keep true ONLY for controllers/operators that call the API
```

Keep the token automounted only for operators, controllers, and
anything using `rest.InClusterConfig()`; disable it for stateless web
apps and batch jobs.

## API deprecations and remediation templates

### API deprecations

| Finding | Sev | Why |
|---|---|---|
| `extensions/v1beta1`, `apps/v1beta1/2` for Deployment/DaemonSet/etc. | HIGH | removed since 1.16 — will not apply on a current cluster |
| `networking.k8s.io/v1beta1` Ingress | HIGH | removed since 1.22 |
| `policy/v1beta1` PodDisruptionBudget | MEDIUM | removed since 1.25 — use `policy/v1` |
| `batch/v1beta1` CronJob | MEDIUM | removed since 1.25 — use `batch/v1` |

`kube-score`'s `stable-version` check and `kubeconform
-kubernetes-version` (pinned to the target cluster) both catch these.
Bumping an apiVersion is usually mechanical but can change defaults —
verify with `helm template`/`kubeconform` after the bump.

### Remediation templates

Complete hardened Deployment pod spec — the target state, applied only
via an approved patch:

```yaml
spec:
  serviceAccountName: app
  automountServiceAccountToken: false
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 2000
    seccompProfile: {type: RuntimeDefault}
  containers:
  - name: app
    image: registry.example.com/app@sha256:9b2c...e1
    imagePullPolicy: IfNotPresent
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities: {drop: [ALL]}
    resources:
      requests: {cpu: "100m", memory: "128Mi"}
      limits:   {cpu: "500m", memory: "256Mi"}
    readinessProbe: {httpGet: {path: /readyz, port: http}, initialDelaySeconds: 5}
    livenessProbe:  {httpGet: {path: /healthz, port: http}, initialDelaySeconds: 15, failureThreshold: 3}
    volumeMounts: [{name: tmp, mountPath: /tmp}]
  volumes: [{name: tmp, emptyDir: {}}]
```
