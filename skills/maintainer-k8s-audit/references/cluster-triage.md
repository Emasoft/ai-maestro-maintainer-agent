# Live-cluster triage — read-only runbooks

`triage` mode is for a workload from an entrusted repo that is
misbehaving on a live cluster. It is strictly READ-ONLY: it ends in a
diagnosis and a proposed manifest change, never in a mutation. The whole
point of triage is to map a runtime symptom back to the manifest field
that is actually wrong — because the fix belongs in the repo, not typed
into a live cluster by hand.

## Table of Contents

- [The read-only command toolkit](#the-read-only-command-toolkit)
- [The triage decision tree](#the-triage-decision-tree)
- [Pod startup failures — CrashLoopBackOff, ImagePullBackOff, OOMKilled, Pending](#pod-startup-failures--crashloopbackoff-imagepullbackoff-oomkilled-pending)
- [Runtime failures — probes, endpoints, storage](#runtime-failures--probes-endpoints-storage)
- [Exit codes, symptom map and gotchas](#exit-codes-symptom-map-and-gotchas)

## The read-only command toolkit

Every command here is a read: `get`, `describe`, `logs`, `events`,
`top`, `auth can-i`, plus ephemeral debug pods that touch nothing
persistent.

```bash
kubectl get pods -n NS -o wide
kubectl describe pod POD -n NS                         # Events section is the first stop
kubectl logs POD -n NS                                 # current container
kubectl logs POD -n NS --previous                      # the crashed container — where the cause is
kubectl logs POD -n NS -c INIT                         # a specific init container
kubectl get events -n NS --sort-by=.lastTimestamp      # cluster-level story, newest last
kubectl get pod POD -n NS -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'
kubectl get pod POD -n NS -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}'
kubectl top pod POD -n NS --containers                 # live CPU/mem vs limits
kubectl top nodes
kubectl get endpoints SVC -n NS                        # empty = selector matches nothing
kubectl get pods -n NS --show-labels                   # compare against the Service selector
kubectl auth can-i --list --as=system:serviceaccount:NS:SA   # what an SA is actually allowed
kubectl run tmp --rm -it --image nicolaka/netshoot -- /bin/bash   # ephemeral net-debug pod
kubectl exec POD -n NS -- nslookup kubernetes.default  # DNS from inside the pod
kubectl exec POD -n NS -- cat /etc/resolv.conf         # the pod's resolver config
kubectl get --raw /apis/metrics.k8s.io/v1beta1/namespaces/NS/pods/POD  # metrics fallback when top/metrics-server is down
```

Read-only accelerators worth having on top of raw `kubectl`: `stern` tails
logs across many pods at once (one command in place of N `kubectl logs`),
`k9s` is a terminal UI over the same read verbs, and `kubectx`/`kubens`
switch context/namespace without editing kubeconfig by hand. All are
conveniences over the read verbs above — none mutate anything.

**MUTATING — never run in triage; each is a human's call with the
diagnosis in hand:** `kubectl apply`, `delete`, `scale`, `patch`,
`rollout restart`, `rollout undo`, `cordon`, `drain`,
`delete pod --force`. Capture state first (`kubectl get … -o yaml`
saved to the report) so the human has a rollback point before they act.

## The triage decision tree

```
kubectl get pods → read the STATUS column
├─ Pending            → scheduling: resources / nodeSelector / taints / PVC   (Pending runbook)
├─ ImagePullBackOff   → the image reference or the pull secret               (ImagePull runbook)
├─ CrashLoopBackOff   → logs --previous → app error | OOM | probe            (CrashLoop runbook)
├─ Init:Error / Init:CrashLoopBackOff → logs -c INIT                          (Init runbook)
├─ CreateContainerConfigError → a referenced ConfigMap/Secret is missing     (Config runbook)
├─ Running, not working → endpoints / probe / NetworkPolicy / DNS            (Service runbook)
└─ Evicted / Error    → node pressure                                        (Node runbook)
```

When the STATUS alone is ambiguous, cross-cut it with a problem-LAYER axis:
classify the symptom as Application, Pod, Service, Node, Cluster, Storage or
Configuration before drilling. The status column says WHERE a pod is stuck;
the layer says WHICH subsystem to read first (e.g. a `Running`-but-broken
pod is a Service-layer or Configuration-layer problem, not a Pod-layer one).

## Pod startup failures — CrashLoopBackOff, ImagePullBackOff, OOMKilled, Pending

### CrashLoopBackOff

- **Symptom:** the pod starts, exits, restarts, backoff grows; restart
  count climbs.
- **Commands:** `kubectl describe pod` (Events + Last State),
  `kubectl logs POD --previous` (the crashed container holds the
  reason), then check for OOM:
  `-o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'`.
- **Ranked causes:** application error on boot (bad config / missing env
  var) → OOMKilled (see below) → an aggressive `livenessProbe` killing a
  slow-starting app before it is up → a missing volume/Secret.
- **Manifest fix:** add the missing env/ConfigMap/Secret reference;
  raise the memory limit; relax `livenessProbe.initialDelaySeconds` or
  add a `startupProbe`; mount the missing volume.

### ImagePullBackOff / ErrImagePull

- **Symptom:** pod never starts; Events show a pull error.
- **Commands:** `kubectl describe pod` (the exact registry error),
  `-o jsonpath='{..image}'` to read the ref as applied,
  `kubectl get pod -o yaml | ...` for `imagePullSecrets`,
  `kubectl get secrets -n NS`.
- **Ranked causes:** wrong image name/tag → private registry with no /
  wrong pull secret → registry rate-limit or network → digest that no
  longer exists.
- **Manifest fix:** correct the image ref; attach `imagePullSecrets`
  (ideally on the ServiceAccount); pin a real, existing digest.

### OOMKilled (exit 137)

- **Symptom:** the container restarts; Last State `reason: OOMKilled`,
  exit code 137.
- **Commands:**
  `-o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'`,
  `kubectl top pod POD --containers` to see the real ceiling, then read
  `resources` from the pod YAML.
- **Ranked causes:** `resources.limits.memory` too low → no memory limit
  and the node reclaimed it under pressure → a genuine leak in the app.
- **Manifest fix:** set `resources.requests.memory == limits.memory` at
  a value above the observed working set (from `kubectl top`). This is
  the single most common manifest defect surfaced by triage: a memory
  limit that is missing or set below what the app actually uses.

### Pending (unschedulable)

- **Symptom:** pod stuck `Pending`, never scheduled.
- **Commands:** `kubectl describe pod` (the scheduler's reason in
  Events), `kubectl top nodes` / `kubectl describe nodes`,
  `kubectl get pvc -n NS`,
  `kubectl get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints`,
  `kubectl get resourcequota -n NS`.
- **Ranked causes:** requests exceed free capacity on every node → a
  `nodeSelector`/`affinity` matches no node → node taints with no
  matching toleration → an unbound PVC → a ResourceQuota already full.
- **Manifest fix:** lower `resources.requests`; correct or drop the
  `nodeSelector`/affinity; add the toleration; fix the PVC's
  `storageClassName`.

### Init container failures

- **Symptom:** pod stuck `Init:Error` or `Init:CrashLoopBackOff`; the
  main container never starts.
- **Commands:** `kubectl logs POD -c INIT_NAME` (and `--previous`),
  `kubectl describe pod` for which init container index failed.
- **Ranked causes:** the init's own command fails → a dependency it
  waits for is never ready → a missing mounted Secret/ConfigMap.
- **Manifest fix:** correct the init container's command/args; fix the
  dependency reference; supply the missing mount.

### CreateContainerConfigError / CreateContainerError

- **Symptom:** pod cannot create the container; Events name a missing
  reference.
- **Commands:** `kubectl describe pod` (names the missing object),
  `kubectl get configmap,secret -n NS`.
- **Ranked causes:** an `envFrom`/`valueFrom` points at a ConfigMap or
  Secret that does not exist in the namespace → a key referenced in a
  Secret is absent → a namespace mismatch.
- **Manifest fix:** create/rename the referenced object, or correct the
  reference; names are case-sensitive and namespace-scoped.

## Runtime failures — probes, endpoints, storage

### Probe failures

- **Symptom:** pod is Running but never Ready, or restarts on liveness.
- **Commands:** `kubectl describe pod` (probe failure Events),
  read `readinessProbe`/`livenessProbe` from the pod YAML, `kubectl
  exec` to hit the probe endpoint from inside the pod.
- **Ranked causes:** wrong probe `path`/`port` → `initialDelaySeconds`
  too short for boot → the endpoint genuinely unhealthy.
- **Manifest fix:** correct the path/port; raise `initialDelaySeconds`
  or add a `startupProbe`; keep liveness more forgiving than readiness
  (an aggressive liveness probe is itself the cause of a CrashLoop).

### Service has no endpoints / DNS

- **Symptom:** the Service is unreachable; connections time out or
  refuse.
- **Commands:** `kubectl get endpoints SVC -n NS` (empty is the tell),
  `kubectl get pods --show-labels` vs the Service `selector`,
  `kubectl get networkpolicies -n NS`, DNS from a debug pod
  (`nslookup SVC.NS.svc.cluster.local`), CoreDNS health
  (`kubectl get pods -n kube-system -l k8s-app=kube-dns`, plus
  `kubectl get endpoints kube-dns -n kube-system`), and the pod's own
  `/etc/resolv.conf`.
- **Ranked causes:** the Service `selector` does not match the pod
  labels → `targetPort` ≠ the container port → a NetworkPolicy blocks
  the traffic (or blocks DNS on port 53) → the pods are not Ready.
- **Manifest fix:** align the Service `selector` with the pod labels;
  fix `targetPort`; add a NetworkPolicy allow rule (include DNS egress).

### PVC pending / node pressure / evictions

- **Symptom:** PVC stuck `Pending` (pod cannot mount); or pods `Evicted`
  under node pressure.
- **Commands:** `kubectl describe pvc PVC -n NS`, `kubectl get pv`,
  `kubectl get storageclass`; for nodes `kubectl describe node NODE`
  (look for the `MemoryPressure`, `DiskPressure`, `PIDPressure`
  conditions, and the node's `Allocated resources` block — what is
  actually holding its capacity), `kubectl top node`.
- **Ranked causes (PVC):** no matching PV / no dynamic provisioner →
  wrong `storageClassName` → capacity exhausted. **(node):**
  DiskPressure evicting pods → over-committed requests.
- **Manifest fix:** correct `storageClassName` / `resources.requests`
  for the volume; right-size pod `requests` so the scheduler stops
  over-packing the node.

## Exit codes, symptom map and gotchas

### Exit-code semantics

| Exit code | Meaning | Where it points |
|---|---|---|
| 0 | clean exit | a Job that finished, or a container that was expected to stay up but did not — check the command |
| 1 | generic application error | read `logs --previous`; the app's own error |
| 137 | SIGKILL (128+9) — almost always **OOMKilled** | `resources.limits.memory` too low or absent |
| 143 | SIGTERM (128+15) — graceful shutdown | usually normal; a pod terminated by a rollout or scale-down |

### Runtime symptom → the manifest field that is wrong

| Runtime symptom | The field to fix in the repo |
|---|---|
| OOMKilled (137) | `resources.requests.memory` / `resources.limits.memory` — too low or missing |
| CrashLoopBackOff at boot | a missing env / `configMapKeyRef` / `secretKeyRef`, or a too-aggressive `livenessProbe` |
| ImagePullBackOff | `image` (wrong ref) or `imagePullSecrets` (missing) |
| Pending | `resources.requests`, `nodeSelector`/`affinity`, `tolerations`, or the PVC's `storageClassName` |
| never Ready | `readinessProbe` path/port/`initialDelaySeconds` |
| Service unreachable, no endpoints | the Service `selector` vs pod labels, or `targetPort` |
| CreateContainerConfigError | an `envFrom`/`valueFrom` reference to a non-existent ConfigMap/Secret |
| Evicted | over-committed `resources.requests`, or a `hostPath`/emptyDir filling the node disk |

### Gotchas

- The reason lives in `logs --previous`, not `logs` — the current
  container is the fresh restart, not the one that crashed.
- `kubectl describe` Events age out (default ~1h). If Events are empty,
  the failure may predate the window — use `get events --sort-by` and
  the pod's `lastState`, not describe alone.
- A pod can be `Running` and completely broken; `Running` means the
  container process exists, `Ready` means it passes readiness. Read the
  Ready column, not the Status column.
- A negative kubesec score or a kube-score CRITICAL on the *manifest*
  often predicts the *runtime* failure (no memory limit → future OOM).
  Triage and the static audit are two views of one defect.
