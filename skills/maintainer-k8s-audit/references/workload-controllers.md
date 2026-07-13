# Workload controllers — correctness, immutability and reliability

The catalogue in [k8s-manifest-checks.md](k8s-manifest-checks.md) audits
the pod SECURITY surface. This file audits the CONTROLLER surface — the
Deployment / StatefulSet / DaemonSet / Job / CronJob / HPA / PDB / PVC /
Ingress fields whose defects do not compromise the cluster but silently
break rollouts, wedge node drains, pile up resources, or refuse to
schedule. Every fix here changes cluster behaviour, so each is a proposed
patch, never an auto-fix.

## Table of Contents

- [Immutable fields — flag every edit](#immutable-fields--flag-every-edit)
- [Deployment, StatefulSet and DaemonSet](#deployment-statefulset-and-daemonset)
- [Job, CronJob and HorizontalPodAutoscaler](#job-cronjob-and-horizontalpodautoscaler)
- [PodDisruptionBudget and PersistentVolumeClaim](#poddisruptionbudget-and-persistentvolumeclaim)
- [Ingress and controller API deprecations](#ingress-and-controller-api-deprecations)

## Immutable fields — flag every edit

Some fields cannot be changed after the object is created; an apply that
edits one fails, or (worse) is silently ignored. When a diff touches one of
these, the finding is "this needs a delete-and-recreate, plan for it", not
a routine change:

| Object | Immutable after creation |
|---|---|
| Deployment / StatefulSet / DaemonSet | `spec.selector` (and thus `.matchLabels`) |
| StatefulSet | `spec.volumeClaimTemplates` (resize = delete the SS keeping pods, patch the PVCs, recreate) |
| PersistentVolumeClaim | everything except `spec.resources.requests.storage` (expand only) |
| Service | `spec.clusterIP` |
| Job | `spec.template`, `spec.selector`, `spec.completions` |

A rolling update that changes a selector label is the classic trap — see
Deployment below.

## Deployment, StatefulSet and DaemonSet

The three replica controllers — their selector, replica and scheduling
traps.

### Deployment

| Finding | Sev | Why |
|---|---|---|
| a mutable/rolling label (e.g. `app.kubernetes.io/version`) inside `spec.selector.matchLabels` | HIGH | the selector is immutable, so the version label can never change — every version bump is blocked, or forces a delete-and-recreate outage. Keep `version` in `metadata.labels`, NOT in the selector |
| `spec.replicas` set on a Deployment that is also targeted by an HPA | MEDIUM | the static replica count and the HPA fight each other; the manifest replica value flaps. Omit `replicas` when an HPA manages the Deployment |
| `spec.selector` edited in a diff | HIGH | immutable — the apply will fail; the change needs a delete-and-recreate |

### StatefulSet

| Finding | Sev | Why |
|---|---|---|
| no headless Service named in `spec.serviceName` (a Service with `clusterIP: None`) | HIGH | without it the pods get no stable network identity and stay `Pending` — the single most common StatefulSet misconfiguration |
| `spec.volumeClaimTemplates` edited (e.g. a size bump) | HIGH | immutable; a resize means delete the StatefulSet with `--cascade=orphan`, patch each PVC, then recreate — a planned operation, never a blind apply |

### DaemonSet

| Finding | Sev | Why |
|---|---|---|
| a DaemonSet expected to run on every node but with no control-plane toleration | MEDIUM | control-plane nodes carry a `NoSchedule` taint; without a matching toleration the DaemonSet silently skips them, leaving the control plane unmonitored |

```yaml
      tolerations:
      - key: node-role.kubernetes.io/control-plane
        operator: Exists
        effect: NoSchedule
```

## Job, CronJob and HorizontalPodAutoscaler

Batch and autoscaling controllers — restart policy, garbage collection,
overlap and scaling-metric traps.

### Job and CronJob

| Finding | Sev | Why |
|---|---|---|
| `restartPolicy: Always` on a Job/CronJob pod template | HIGH | rejected by the API server — a Job pod must be `Never` or `OnFailure`; `Always` will not apply |
| no `ttlSecondsAfterFinished` on a Job | MEDIUM | completed Jobs and their pods are never garbage-collected — they accumulate indefinitely and clutter the namespace (and count against quota) |
| CronJob with `concurrencyPolicy: Allow` (the default) and a run that can outlast its interval | MEDIUM | overlapping runs pile up and can exhaust resources; use `Forbid` or `Replace` for a job that must not overlap |
| CronJob `schedule` with no `timeZone` | LOW | the schedule is interpreted in the cluster's time zone (UTC unless the controller says otherwise); set `timeZone` (GA in 1.27) for an unambiguous wall-clock schedule |

### HorizontalPodAutoscaler

| Finding | Sev | Why |
|---|---|---|
| the target's containers have no `resources.requests` for the scaled metric | HIGH | CPU/memory *utilization* is computed as a percentage of the request — with no request, the HPA cannot compute a ratio and never scales |
| an HPA plus a static `spec.replicas` on the same target | MEDIUM | they fight (see Deployment) |
| `apiVersion: autoscaling/v2beta1` or `v2beta2` | MEDIUM | both beta versions are removed on current clusters — migrate to `autoscaling/v2` (stable since 1.23) |

## PodDisruptionBudget and PersistentVolumeClaim

Availability and storage objects — disruption headroom and the
immutability of a bound PVC.

### PodDisruptionBudget

| Finding | Sev | Why |
|---|---|---|
| `minAvailable` equal to the workload's replica count (or `maxUnavailable: 0`) | HIGH | zero voluntary disruptions are ever permitted — a `kubectl drain` or a node upgrade hangs forever waiting for a pod it is not allowed to evict. Leave at least one pod of headroom |
| no PDB on a multi-replica workload that needs availability during node maintenance | LOW | a drain can take every replica at once |

### PersistentVolumeClaim

| Finding | Sev | Why |
|---|---|---|
| a PVC field other than the storage request edited after binding | HIGH | immutable once bound; only `spec.resources.requests.storage` can grow (and only if the StorageClass allows expansion) |
| `accessModes` the backend cannot satisfy (e.g. `ReadWriteMany` on a block StorageClass) | HIGH | the PVC never binds; the pod stays `Pending`. `RWX` needs a file backend (NFS, CephFS, …) — most block storage is `RWO` only |

## Ingress and controller API deprecations

| Finding | Sev | Why |
|---|---|---|
| Ingress routed via the `kubernetes.io/ingress.class` annotation | MEDIUM | that annotation is deprecated — use the `spec.ingressClassName` field, which is the supported, validated mechanism on current clusters |
| `policy/v1beta1` PodSecurityPolicy | HIGH | PodSecurityPolicy was removed in 1.25 — there is no `policy/v1` PSP; migrate to Pod Security admission (namespace labels, see k8s-manifest-checks.md) or a policy engine |
| `autoscaling/v2beta1` / `v2beta2` HPA | MEDIUM | see the HPA section — removed, use `autoscaling/v2` |

These join the built-in deprecations in k8s-manifest-checks.md;
`kubeconform -kubernetes-version` pinned to the target cluster and a
server-side dry-run (see
[validation-and-dry-run.md](validation-and-dry-run.md)) both catch a
removed apiVersion before the apply does.
