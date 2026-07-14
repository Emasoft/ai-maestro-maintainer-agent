# Azure Pipelines audit — `azure-pipelines.yml` and templates

Targets: every tracked `azure-pipelines.yml` / `azure-pipelines.yaml`,
any `*.pipeline.yml`, and the template YAML they `extends:`/`template:`.
Parse with `python3` + `yaml.safe_load`; scan raw lines for the
inline-script checks. Each check is *what to look for → why → the fix*.

## Table of Contents

- [Live validation — the preview API](#live-validation--the-preview-api)
- [1. Variable groups and secret variables](#1-variable-groups-and-secret-variables)
- [2. Service connections](#2-service-connections)
- [3. Protected environments and branch policies](#3-protected-environments-and-branch-policies)
- [4. Agents and container images](#4-agents-and-container-images)
- [5. Runtime-macro script injection](#5-runtime-macro-script-injection)
- [6. `resources: repositories` and template trust](#6-resources-repositories-and-template-trust)
- [7. Checkout credential persistence and `System.AccessToken`](#7-checkout-credential-persistence-and-systemaccesstoken)
- [Static-scan cues](#static-scan-cues)

## Live validation — the preview API

Azure has no offline schema linter. The authoritative check is the
Pipelines **preview** REST API: it validates syntax, task existence, and
task inputs and returns the *final* YAML — WITHOUT queuing a run.

Send a `POST` to the preview endpoint — read-only, and it needs a PAT:

```text
POST https://dev.azure.com/<ORG>/<PROJECT>/_apis/pipelines/<PIPELINE_ID>/preview?api-version=7.1
```

- **Auth** — HTTP Basic with an empty username and the PAT as the
  password (with an HTTP client such as curl, that is the `-u ":<AZDO_PAT>"` form).
- **Header** — `Content-Type: application/json`.
- **Body** — a JSON object carrying the flag and the YAML to validate:

  ```json
  {"previewRun": true, "yamlOverride": "<azure-pipelines.yml contents, JSON-string-escaped>"}
  ```

`previewRun: true` means *validate, do not queue*, so no run is queued.
`yamlOverride` is the pipeline YAML you want checked, encoded as a JSON
string — read the file and escape it with a JSON tool (e.g. jq) rather
than pasting raw multi-line YAML into the body.

**Limits (state them in the report):** preview cannot check variable
*contents*, `vmImage` validity, branch names, service-connection
existence, or `template:` refs that live in another repo. So a green
preview is necessary, not sufficient — the static checks below cover
what preview cannot. When no PAT/pipeline id is available, note the gap
and run the static pass only.

## 1. Variable groups and secret variables

**Look for**:

- a variable defined inline with a credential-shaped literal value
  (`password`, `token`, `secret`, `apiKey`, an AWS key, a connection
  string) — CRITICAL;
- a sensitive-*named* variable (`*password*`, `*secret*`, `*token*`,
  `*key*`, `*credential*`) set as a plain value, not a secret — MEDIUM
  (`variable-not-secret`);
- a secret referenced with macro syntax `$(SECRET)` inside an inline
  script (see §5) — that pulls it into the log-visible command text.

**Why** inline pipeline variables are in git and print to logs. A
sensitive value that is not marked secret is echoed verbatim in the run
log.

**Fix** move secrets into a **variable group** linked from *Pipelines →
Library* (backed by Azure Key Vault for rotation), and reference the
group rather than inlining values:

```yaml
variables:
  - group: production-secrets        # secret vars live here, masked in logs
  - name: buildConfiguration         # non-secret inline value is fine
    value: Release
```

A secret variable is never available as an ambient environment variable
inside a script — it must be mapped in explicitly via an `env:` block
(§5). Flag `##vso[task.setvariable variable=x;issecret=true]` usage as
the *correct* pattern; flag a sensitive value logged with
`echo`/`Write-Host` as `secret-in-logs` (MEDIUM).

## 2. Service connections

**Look for** a task input (`azureSubscription`,
`connectedServiceName`, `dockerRegistryServiceConnection`) set to a raw
36-char GUID rather than a named connection; and any pipeline that reaches
a production service connection from an unprotected branch.

**Why** a hardcoded connection GUID is non-portable and obscures which
credential is in play. More importantly, a service connection *is* a
standing credential to an external system — its exposure is governed by
who can run a pipeline that uses it.

**Fix** reference service connections by **name**, and in the Azure
DevOps UI restrict each connection's *security → pipeline permissions* to
only the pipelines that need it, and gate production connections behind a
protected environment approval (§3). Do not grant "Grant access to all
pipelines" on a production connection.

## 3. Protected environments and branch policies

**Look for** a `deployment` job or a production stage with no
`environment:` that carries an approval check, and a deploy reachable
from any branch.

**Why** Azure enforces manual approvals, business hours, and other gates
through **environment checks**, and restricts merges through **branch
policies** — neither lives in the YAML value alone. A deploy with no
environment check ships on green with no human in the loop.

**Fix** target a protected `environment` (configure the *Approvals and
checks* on it in the UI) and gate the stage on the ref:

```yaml
jobs:
  - deployment: DeployProd
    environment: production      # add Approvals + branch-control checks in the UI
    condition: eq(variables['Build.SourceBranch'], 'refs/heads/main')
    strategy:
      runOnce:
        deploy:
          steps: [ ... ]
```

The YAML `condition:` is a defence-in-depth signal; the *authoritative*
control is the environment check and the branch policy in the project
settings — verify both exist, do not trust the YAML alone.

## 4. Agents and container images

**Look for** a sensitive job on a `self-hosted` pool without a clear
trust story, and any `container:` / `resources.containers[].image`
pinned to `:latest` (or untagged).

**Why** a self-hosted agent is a persistent machine that may be shared or
reachable by untrusted jobs; `:latest` means the executed image bytes can
change with no diff.

**Fix** run sensitive jobs on isolated, trusted agents (a dedicated pool
or ephemeral Microsoft-hosted agents), and pin every container to
`major.minor.patch` plus a digest where it matters:

```yaml
resources:
  containers:
    - container: build
      image: node:20.11-alpine3.19@sha256:<digest>   # never :latest
```

**Pin task versions too.** A `task: Foo@*` (or a missing version)
lets the task *code* that runs change under you; pin the major version
(`task: Foo@2`) so a reviewer knows which task implementation executes.
Flag `@*`/unpinned tasks as `unpinned-task-version` (MEDIUM) — the task
analog of an unpinned image.

**Cache restore keys can cross refs.** A `Cache@2` `restoreKeys:`
fallback can restore a cache written by a *different* branch when the
exact key misses. If a trusted job restores a cache an untrusted branch
could have populated, that is a cache-poisoning path — key the cache on
a per-ref token and keep `restoreKeys:` from widening to shared refs
(LOW→MEDIUM by what consumes the cache).

## 5. Runtime-macro script injection

**Look for** an inline `script:`/`bash:`/`pwsh:` step that embeds a
macro `$(...)` expansion of a value an outsider can influence —
`$(System.PullRequest.SourceBranch)`, a PR title, `$(Build.SourceVersionMessage)`,
or any user-supplied pipeline parameter.

**Why** macro `$(...)` values are **textually substituted into the
script before the shell parses it**. A crafted branch name or PR title
can therefore break out of the intended command and run attacker-chosen
shell — a classic CI injection. (Compile-time `${{ }}` and runtime
`$[ ]` expressions behave differently; the danger is specifically inline
`$(...)` of untrusted text in a script body.)

**Fix** never interpolate untrusted input into script text. Map the
value through an `env:` block so it is passed via the environment — where
it is a plain string the shell never re-parses — and reference it as an
ordinary environment variable:

```yaml
- script: |
    # safe: $SOURCE_BRANCH comes through the environment, not substituted into the text
    echo "building for $SOURCE_BRANCH"
  env:
    SOURCE_BRANCH: $(System.PullRequest.SourceBranch)   # bound, not inlined
```

This mirrors the GitHub-Actions "don't interpolate `${{ }}` into `run:`"
rule; here the dangerous form is inline `$(...)`. Report an unmapped
untrusted `$(...)` in a script as HIGH.

**Know the three expansion syntaxes — two of them are textual.** Azure
has `$(var)` (macro, expanded at runtime by *textual substitution*
before the shell parses), `$[ ... ]` (runtime expression, evaluated by
the agent — not pasted into script text), and `${{ ... }}` (compile-time
template expression, expanded on the server *before the run exists*).
Both `$(...)` and `${{ ... }}` land in the file as text, so a
`${{ parameters.someInput }}` pasted straight into a `script:` body is
*also* injectable when that parameter can carry untrusted text — it is
substituted into the command string just like a macro. The safe rule is
the same for both: never let untrusted text reach a script body as
inlined characters; bind it through `env:` and reference it as a shell
variable. `$[ ... ]` does not have this textual-paste problem.

## 6. `resources: repositories` and template trust

**Look for** a `resources: repositories:` entry or an `extends:` /
`template:` reference to another repo pinned to a moving branch, or to a
repo writable by non-owners.

**Why** an `extends` template controls the whole pipeline's shape;
`resources.repositories` pulls in code your jobs check out and run. A
template loaded from a branch can change under you; one from an untrusted
repo is remote code execution in your pipeline's trust context.

**Fix** pin the resource to an immutable `ref` (a tag or commit), and
prefer a required `extends` template (an org-level "template governance"
pattern) whose repo is admin-controlled:

```yaml
resources:
  repositories:
    - repository: templates
      type: git
      name: platform/pipeline-templates
      ref: refs/tags/v3.2.0        # immutable, not refs/heads/main
```

## 7. Checkout credential persistence and `System.AccessToken`

**Look for** a `checkout:` step with `persistCredentials: true`, and any
script that reads `$(System.AccessToken)` and then hands it to an
untrusted step (an echo, or a downloaded script).

**Why** `System.AccessToken` is the pipeline's built-in OAuth credential
— it can call the Azure DevOps REST API and, depending on the job
authorization scope, reach the repo and other project resources. When
`persistCredentials: true`, checkout writes that token into the on-disk
git config of the workspace, where *every later step on that agent* —
including a compromised dependency's post-install, or an untrusted
template's step — can read and reuse it. The token then outlives the one
step that legitimately needed it.

**Fix** leave `persistCredentials: false` (the default) unless a
specific later step genuinely needs to push with the pipeline identity;
when it does, isolate that step and run no untrusted code after it in the
same job. Never echo `$(System.AccessToken)` and never pass it into a
downloaded script. Also set `clean: true` so a persisted credential from
a prior run does not linger in a reused workspace.

```yaml
- checkout: self
  persistCredentials: false   # the token is NOT written to the on-disk git config
  clean: true
```

Report `persistCredentials: true` on a checkout in a job that also runs
untrusted or third-party steps as HIGH; report a logged/forwarded
`System.AccessToken` as HIGH.

## Static-scan cues

| Finding | Cue | Severity |
|---|---|---|
| Hardcoded secret | secret-shaped literal in `variables:` or a script | CRITICAL |
| Sensitive var not secret | sensitive *name*, plain value, no variable group | MEDIUM |
| Hardcoded service connection | `azureSubscription`/`*ServiceConnection` = 36-char GUID | LOW |
| `:latest` container | `container:`/`image:` ending `:latest` or untagged | MEDIUM |
| Macro injection | inline `$(…PullRequest…\|…SourceVersionMessage…)` in a script | HIGH |
| Unpinned template repo | `resources.repositories[].ref` = `refs/heads/*` | MEDIUM |
| Unpinned task version | `task:` with `@*` or no `@<major>` | MEDIUM |
| Persisted checkout token | `checkout:` with `persistCredentials: true` | HIGH |
| Access-token exposure | `$(System.AccessToken)` echoed or piped to a script | HIGH |
| Checkout not clean | `checkout:` with `clean: false` | LOW |

Read the surrounding YAML before classifying — a cue is a hint, not a
verdict.
