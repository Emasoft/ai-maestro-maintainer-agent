# Operations, prerequisites and worked examples

Supporting reference for [maintainer-k8s-audit](../SKILL.md): the full
tool table, the `harden`-mode deploy-neutral fix-class rationale, the
error-handling table, and end-to-end examples of each mode.

## Table of Contents

- [Prerequisites — the tool table](#prerequisites--the-tool-table)
- [Tracked-file triage](#tracked-file-triage)
- [Harden mode — deploy-neutral fix classes](#harden-mode--deploy-neutral-fix-classes)
- [Error handling](#error-handling)
- [Worked examples](#worked-examples)

## Prerequisites — the tool table

Every tool below is OPTIONAL except `yamllint`. When one is absent the
skill records the gap in `notes[]` and continues with the rest of the
audit rather than failing — except in `gate` mode, where a missing
scanner that CI runs is a HARD FAIL (a local green would be meaningless).

| Tool | Used for | Notes |
|---|---|---|
| `kubeconform` | schema validation of manifests and rendered charts | the maintained successor to `kubeval`, which is archived upstream and ships schemas many Kubernetes versions behind — never introduce `kubeval` into a repo that does not already pin it |
| `kube-score` | opinionated workload scoring (probes, limits, PDB, anti-affinity) | the highest signal-per-second tool in the set |
| `kubesec` | pod-security scoring with a numeric risk score | complements kube-score, does not replace it |
| `polaris` | policy-based audit with configurable severities | good CI gate; `--set-exit-code-on-danger` |
| `kube-linter` | static lint (latest-tag, non-root, unset limits) | SARIF output, easy to wire to a PR |
| `helm` (v3) | `helm lint`, `helm template` | required for any repo holding a `Chart.yaml` |
| `ansible-lint`, `ansible-playbook` | playbook and role audit | required for any repo holding playbooks or roles |
| `checkov`, `trivy` | the two scanners this repo's CI already runs | HARD requirement in `gate` mode |
| `yamllint` | YAML hygiene, duplicate keys, tabs | the one hard requirement |
| `kubectl` | `--dry-run=server`, and every `triage`-mode command | read-only usage only; see Scope |

Install through the host package manager (`brew install kubeconform
kube-score kubesec polaris kube-linter helm yamllint trivy`, `uvx
checkov` or `pipx install checkov`, `pipx install ansible-lint`). Run
`maintainer-tooling-bootstrap audit` if unsure what is present; the
skill calls `command -v` before invoking any tool.

## Tracked-file triage

Done FIRST, before any tool runs — everything in this table is a finding
even if every scanner is green:

| File state in git | Severity | Why |
|---|---|---|
| A `kind: Secret` manifest with a populated `data:` / `stringData:` | CRITICAL | base64 is an encoding, not encryption — the value is in the clone and in every fork |
| A credential-shaped default in `values.yaml` (`password`, `token`, `apiKey`, `*_SECRET`) | CRITICAL | ships in the packaged chart and in every registry that mirrors it |
| An unencrypted Ansible vars file holding a credential | CRITICAL | vault it, then rotate — the value is already in history |
| A committed `kubeconfig` / `*.kubeconfig` / `admin.conf` | CRITICAL | cluster-admin credential in the repo |
| `Chart.lock` missing while `Chart.yaml` declares dependencies | HIGH | subchart versions unpinned; a supply-chain swap is undetectable |
| `requirements.yml` with an unpinned collection or role | HIGH | same, for Ansible |
| `.helmignore` missing | MEDIUM | `helm package` sweeps `.git/`, `.env`, CI files into the tarball |
| A `*.retry` file, `ansible.log` | LOW | noise; may name hosts |

A CRITICAL here stops the audit for that file and chains to
`maintainer-secrets-scan` — treat every value in it as leaked (rotate
first, then purge from history; removing the file is not enough).

## Harden mode — deploy-neutral fix classes

`harden` applies ONLY the reversible, DEPLOY-NEUTRAL fix classes — the
ones that cannot change what the cluster does:

- `yamllint` formatting fixes (whitespace, indentation, document start
  markers) and de-duplication of a duplicate key, where the two values
  are identical.
- `ansible-lint --fix` for its auto-fixable rules only (FQCN rewrites
  such as `apt:` → `ansible.builtin.apt:`, key order, Jinja spacing) —
  semantically identical, verified by re-running `--syntax-check`
  afterwards.
- `no_log: true` on a task the secret heuristic flags. It only
  suppresses output; it cannot change the task's effect.
- Add or repair `.helmignore` (affects packaging, not rendering).
- Pin a `Chart.yaml` dependency to the version ALREADY resolved in
  `Chart.lock`, and a `requirements.yml` entry to the version already
  installed. Pinning to what is already in use changes nothing but makes
  the swap detectable.
- Add the PodSecurity `warn` and `audit` namespace labels. These are
  advisory and reject nothing. `enforce` is NOT auto-applied — it can
  make the next deploy fail.
- Add a `values.schema.json`, but ONLY after `helm lint` passes with
  EVERY values file the repo ships — a schema that rejects an existing
  overlay breaks the next release.

Everything else — `securityContext`, `resources`, probes, digest
pinning, NetworkPolicy, RBAC narrowing, PodSecurity `enforce`, file
`mode:`, `changed_when` — is NOT auto-applied. Each is written up as a
remediation patch in the report, with its diff and its blast radius, for
human approval.

## Error handling

| Error | Action |
|-------|--------|
| A scanner is missing | Note the gap, continue; in `gate` mode a missing `checkov`/`trivy` is a HARD FAIL — CI runs them, so a local green proves nothing |
| `kubeconform` reports `no schema found` for a CRD | EXPECTED, not a failure. Add the CRD's own schema via `-schema-location`, or accept `-ignore-missing-schemas` and validate the `spec` against the CRD's published docs |
| `helm template` fails but `helm lint` passed | The chart is broken. `helm lint` does not render every path — report as HIGH `chart-does-not-render` and name the values file that triggered it |
| `helm lint` needs a value the repo does not ship | Never invent one. Re-run with the repo's own `-f`; if the value is a secret, report the chart as `unvalidated-needs-credentials` |
| A scanner reports an ID the catalogue lacks | Report verbatim with the scanner's remediation URL; never guess the fix |
| Duplicate YAML key found | HIGH, always. The visible config is not the applied config |
| A `Secret` manifest with real data, or a credential in `values.yaml` | CRITICAL, stop, chain to `maintainer-secrets-scan`. Rotate first — a `git rm` does not un-leak it |
| `ansible-lint` flags a rule the repo intentionally allows | Only an ID-scoped `skip_list` entry in `.ansible-lint` WITH a WHY comment is acceptable; `gate` fails on an undocumented one |
| `kubectl` has no cluster context | `scan`/`harden`/`gate` proceed (they need no cluster). `triage` cannot — say so, do not fabricate a diagnosis |
| `harden` cannot write (read-only fs) | Surface the error; do not partial-write |

## Worked examples

Audit an entrusted repo before a release:

```text
User: "audit our kubernetes manifests"
→ 14 manifests, 1 chart (charts/api), 0 playbooks
→ yamllint: duplicate key `securityContext` (api/deploy.yaml:31) → HIGH
→ kubeconform -strict: 1 error, unknown field `readOnlyRootFileSystem`
  (typo: capital S — the API server would silently ignore it) → HIGH
→ kube-score: 6 containers with no resource limits; 4 with no probes
→ kubesec: score -21 on worker.yaml (privileged: true, hostPID: true)
→ polaris: 2 danger (runAsRoot, latest tag) → exit non-zero
→ RBAC: ClusterRole `api` grants verbs ["*"] on ["*"] → CRITICAL
→ Report: reports/maintainer-k8s-audit/<ts>-k8s-audit.md
→ Exit 1 (CRITICAL present)
```

Apply only what cannot change cluster behaviour:

```text
User: "fix what is safe to fix"
→ harden mode
→ yamllint: 9 files reformatted; the duplicate securityContext key had
  two IDENTICAL values → de-duplicated (safe)
→ .helmignore added to charts/api (was sweeping .git/ into the tarball)
→ Chart.yaml: dependency `postgresql` pinned to 15.5.38 — the version
  Chart.lock already resolves, so nothing deployed changes
→ namespace api: pod-security.kubernetes.io/warn+audit=restricted added
  (advisory only; `enforce` NOT applied — it would fail the next deploy)
→ NOT auto-applied, written up as patches with blast radius:
  the 6 missing `resources` blocks, the 4 missing probes, the RBAC
  wildcard narrowing, and the digest pinning of 3 images
→ Exit 0
```

Diagnose a live workload:

```text
User: "why is the payments pod in CrashLoopBackOff"
→ triage mode (read-only)
→ kubectl logs payments-7d9 --previous  → OOM at 512Mi heap
→ kubectl get pod payments-7d9 -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'
  → OOMKilled (exit 137)
→ Root cause is in the REPO, not the cluster:
  deploy.yaml:44 sets resources.limits.memory: 256Mi with no request
→ Proposed manifest patch (needs approval): requests 384Mi / limits 512Mi
→ No kubectl apply, no rollout restart, no delete — diagnosis only
```
