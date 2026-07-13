# Jenkins audit — `Jenkinsfile` and shared libraries

Jenkins is Groovy, and Groovy is a full programming language — so a
Jenkins pipeline can do far more, and go far more wrong, than a
declarative YAML pipeline. The audit targets are the `Jenkinsfile`, any
`vars/*.groovy` and `src/**/*.groovy` shared-library files, and the
trust boundary between them. These are line-oriented Groovy checks;
there is no safe YAML parser to lean on.

## Table of Contents

- [Live validation — `declarative-linter` (declarative only)](#live-validation--declarative-linter-declarative-only)
- [1. Declarative vs scripted — prefer the constrained form](#1-declarative-vs-scripted--prefer-the-constrained-form)
- [2. The Groovy sandbox and script approval](#2-the-groovy-sandbox-and-script-approval)
- [3. Shared-library trust — the biggest Jenkins trust hazard](#3-shared-library-trust--the-biggest-jenkins-trust-hazard)
- [4. Credentials — never inline, always bound](#4-credentials--never-inline-always-bound)
- [5. Agent trust and privileged docker](#5-agent-trust-and-privileged-docker)
- [6. Input / approval gates and reliability guards](#6-input--approval-gates-and-reliability-guards)
- [7. Groovy interpolation into `sh` — the injection vector](#7-groovy-interpolation-into-sh--the-injection-vector)
- [Static-scan cues (line-oriented)](#static-scan-cues-line-oriented)

## Live validation — `declarative-linter` (declarative only)

Jenkins ships a linter for **Declarative** pipelines. It validates
structure against the declarative schema; it does NOT run the pipeline.

```bash
# CLI jar form (needs a URL + an API token):
java -jar jenkins-cli.jar -s "$JENKINS_URL" -auth "$USER:$TOKEN" \
  declarative-linter < Jenkinsfile

# SSH form:
ssh -l "$USER" -p "$JENKINS_SSH_PORT" "$JENKINS_HOST" declarative-linter < Jenkinsfile

# HTTP endpoint (needs a crumb):
curl -sS -X POST -H "$JENKINS_CRUMB" \
  -F "jenkinsfile=<Jenkinsfile" "$JENKINS_URL/pipeline-model-converter/validate"
```

**A Scripted pipeline has no equivalent linter.** `declarative-linter`
rejects `node { … }` scripted files; there is no server-side validator
for scripted Groovy short of compiling it. That gap is itself a
hardening argument for declarative (see §1). When the file is scripted,
say so in the report and rely on the static checks below.

## 1. Declarative vs scripted — prefer the constrained form

**Look for** a scripted pipeline (`node { … }`, top-level Groovy control
flow) where a declarative one (`pipeline { … }`) would do.

**Why** declarative pipelines are validated by `declarative-linter`,
have a fixed structure a reviewer can reason about, and keep arbitrary
Groovy confined to `script { }` islands. Scripted pipelines are
unrestricted Groovy: unlintable, harder to review, and the natural home
for the sandbox-escape and credential-handling mistakes below.

**Fix** this is a *recommendation*, not an auto-rewrite — porting
scripted to declarative changes behaviour and must be human-driven.
Report it as a MEDIUM maintainability/auditability finding; if the file
stays scripted, hold every other check in this reference to a higher bar.

## 2. The Groovy sandbox and script approval

**Background.** Pipeline Groovy runs under the Script Security sandbox:
calls outside the approved allowlist are blocked until a Jenkins admin
approves them in *Manage Jenkins → In-process Script Approval*. The
sandbox is the wall between a pipeline author and the Jenkins controller
JVM.

**Look for**:

- a pipeline or step that reaches for controller internals — the
  `Jenkins` singleton, `hudson.model.*`, `System` properties, reflection,
  or arbitrary file reads on the controller. These are attempts to
  operate *outside* the sandbox.
- any suggestion in comments/docs to blanket-approve signatures or to
  disable the sandbox for a job.

**Why** an approved dangerous signature (or a disabled sandbox) lets
pipeline Groovy execute with the controller's full authority — every
credential, every job, the whole instance.

**Fix** keep work on the *agent*, not the controller: run shell/build
steps inside a `node`/`agent` block via `sh`/`bat`, never by scripting
controller objects. Never recommend blanket script approval; each
approval is a standing grant a reviewer must justify. Flag controller
object access as HIGH and route the sign-off to a human.

**`@NonCPS` and raw constructors.** A `@NonCPS`-annotated method runs
outside the pipeline's CPS transform as ordinary Groovy — it is where a
pipeline reaches for `new SomeClass(...)`, reflection, and JVM APIs that
the sandbox would otherwise intercept, and it is exactly the code that
tends to accumulate script-approval grants. Treat a `@NonCPS` method
that constructs arbitrary classes, reads controller files, or touches
`System`/reflection as a §2 sandbox finding, not a mere style choice —
read its body, do not wave it through because it is "just a helper".

## 3. Shared-library trust — the biggest Jenkins trust hazard

**Background.** Jenkins loads shared libraries two ways, with very
different trust:

- **Global Pipeline Libraries** (configured by an admin in *Manage
  Jenkins → System*) are **trusted**: their Groovy runs OUTSIDE the
  sandbox with full permissions.
- **Folder-level / project libraries** are **untrusted**: sandboxed like
  ordinary pipeline code.

**Look for**:

- `@Library('name@ref')` where `ref` is a moving branch (`@master`,
  `@main`) rather than a commit SHA or an immutable tag;
- a trusted global library whose source repo is writable by
  non-administrators, or loaded from a fork / untrusted branch;
- `library(...)` loaded dynamically from a runtime-computed string.

**Why** a trusted library runs unsandboxed, so whoever can push to its
repo — or influence which ref is loaded — can run arbitrary code on the
controller. An unpinned `@ref` means the executed bytes can change
between builds with no diff in your repo.

**Fix** pin every `@Library` to an immutable ref:

```groovy
@Library('utils@a1b2c3d')  _   // commit SHA or signed tag, never a branch
```

Restrict write access to trusted-library repos to admins, keep untrusted
contributions in folder-level (sandboxed) libraries, and never build the
library coordinate from untrusted runtime input. Pinning the ref is a
`harden`-safe edit; changing a library's trust tier is a human decision.

## 4. Credentials — never inline, always bound

**Look for** a literal secret in the Groovy: `password = "…"`, a
`-p <literal>` / `--password=<literal>` on a `sh` command, a `Bearer` /
`Basic` auth header value, an `api[_-]?key`/`token`/`secret` assigned a
long literal. A `$VAR` reference is fine; a literal is the finding.

**Why** the value is in git history and prints into the build log.

**Fix** pull secrets from the Jenkins Credentials Manager, which
encrypts them at rest and auto-masks them in logs:

```groovy
withCredentials([usernamePassword(credentialsId: 'docker-hub',
    usernameVariable: 'DOCKER_USER', passwordVariable: 'DOCKER_PASS')]) {
  sh 'echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin'
}
// or, in a declarative environment block:
environment { AWS = credentials('aws-credentials-id') }  // AWS_USR / AWS_PSW
```

Replacing an inline literal with the binding form is `harden`-safe. Also
flag any `echo`/`println` of a bound credential variable — binding masks
the value in logs, but an explicit echo of the expanded string can
defeat masking through transforms; keep secrets out of `echo`.

## 5. Agent trust and privileged docker

**Look for** a sensitive stage with `agent any` (lands on any connected
agent, including an untrusted one), and a `docker` agent given
`args '--privileged'` or a raw docker-socket mount.

**Why** `agent any` can place a production-credentialed job on a
low-trust executor. A privileged docker agent (or a mounted docker
socket) can escape to the host and read other builds' secrets.

**Fix** pin sensitive work to a labelled, trusted agent
(`agent { label 'production' }`), and drop `--privileged` / the socket
mount unless the build genuinely needs it — in which case it is a HIGH
finding written up for human sign-off, not an auto-fix. Also pin the
docker image tag:

```groovy
agent { docker { image 'node:20.11-alpine3.19@sha256:<digest>'; label 'trusted' } }
```

## 6. Input / approval gates and reliability guards

**Look for** a production `deploy` stage with no `input` approval step,
and long-running steps with no `timeout` (a hung build holds an executor
and any credentials it bound).

**Why** an unguarded auto-deploy ships whatever merged; an unbounded
step is a resource and blast-radius risk.

**Fix** gate production behind an explicit `input` and wrap risky work in
a `timeout`:

```groovy
stage('Deploy') {
  steps {
    timeout(time: 30, unit: 'MINUTES') {
      input message: 'Deploy to production?'
      sh './deploy.sh production'
    }
  }
}
```

`input` inside a `node` block holds an executor while it waits — put the
`input` *outside* the `node`/agent allocation so an approval pause does
not pin an agent (and its credentials). Report a missing production
approval as LOW→MEDIUM depending on blast radius.

**Restrict who may approve — `submitter:`.** An `input` step with no
`submitter:` can be approved by *anyone with Build permission*, not just
the release owners, so an "approval gate" that anyone can click is not a
gate. Recommend naming the authorized approvers explicitly:

```groovy
input message: 'Deploy to production?', submitter: 'ops,release-admins'
```

Report a production `input` without a `submitter:` as MEDIUM.

**Single-flight the deploy.** Two concurrent prod deploys can race and
interleave. Serialize with `disableConcurrentBuilds()` in `options`, or
wrap the deploy in a `lock(resource: 'prod-deploy')` so only one build
holds it at a time — the Jenkins analog of GitLab `resource_group:` and
Azure exclusive-lock environments. Absence on a production deploy is LOW.

## 7. Groovy interpolation into `sh` — the injection vector

**Background.** A double-quoted Groovy string interpolates `${...}`
*before* the `sh` step ever hands text to the shell. So
`sh "deploy ${params.TARGET}"` builds the command by pasting the raw
value of `params.TARGET` into the command text — and `params.*`,
`env.CHANGE_TITLE`, `env.BRANCH_NAME`, and any value derived from a PR
or a build parameter are attacker-influenceable. This is the Jenkins
twin of the Azure `$(...)`-in-a-script and GitLab `eval`-on-a-variable
findings: untrusted text substituted into a command string before the
shell parses it.

**Look for** a double-quoted `sh`/`bat` argument that interpolates a
`${params.…}`, `${env.CHANGE_…}`, `${env.BRANCH_NAME}`, or any value
that traces back to a build parameter or SCM metadata. The vulnerable
shape:

```groovy
// VULNERABLE — Groovy pastes the raw value into the command text
sh "git checkout ${params.BRANCH}"
```

**Why** a value carrying shell metacharacters (a semicolon, backticks,
`$(...)`, a newline) breaks out of the intended `git checkout` and runs
attacker-chosen commands on the agent, with whatever credentials that
stage bound.

**Fix** — three layered defences, best first:

- **Constrain the input** with a `choice` parameter so only an allowlist
  of values is ever possible:

  ```groovy
  parameters { choice(name: 'BRANCH', choices: ['main', 'develop', 'release']) }
  ```

- **Validate** a free-form value against a strict pattern before use, and
  `error` out otherwise:

  ```groovy
  if (!params.BRANCH.matches(/^[A-Za-z0-9._\/-]+$/)) { error "rejected branch name" }
  ```

- **Never interpolate — pass through the environment.** Single-quote the
  `sh` body so the *shell* (not Groovy) expands the variable, and inject
  the value via `withEnv`/`env` where it is an ordinary string the shell
  does not re-parse as code:

  ```groovy
  withEnv(["TARGET_BRANCH=${params.BRANCH}"]) {
    sh 'git checkout "$TARGET_BRANCH"'   // single quotes: shell expands, Groovy does not
  }
  ```

Report an unvalidated interpolation of untrusted input into `sh`/`bat`
as HIGH.

## Static-scan cues (line-oriented)

| Finding | Cue on a line | Severity |
|---|---|---|
| Hardcoded password | `(password\|passwd\|pwd)\s*=\s*["']` and no `credentials` | CRITICAL |
| Hardcoded token/key | `(api[_-]?key\|token\|secret)\s*=\s*["'][A-Za-z0-9_-]{16,}` | HIGH |
| Inline Bearer/Basic auth | `Bearer\s+…` / `Basic\s+…` literal, no `$` | HIGH |
| Unpinned library | `@Library\('[^@']+@(master\|main\|latest)'` | MEDIUM |
| Privileged docker | `args\s+'[^']*--privileged` or docker-socket mount | HIGH |
| Controller object access | `Jenkins\.`, `hudson\.`, `System\.`, reflection | HIGH |
| Interpolation into shell | `sh\s+"[^"]*\$\{(params\|env)\.` (double-quoted, untrusted) | HIGH |
| Missing production approval | prod `deploy` stage with no `input` | MEDIUM |
| Unrestricted approval | `input` step with no `submitter:` on a prod gate | MEDIUM |

Every regex above is a *hint*, not a verdict — read the surrounding
Groovy before classifying, exactly as an image kind changes a
Dockerfile finding.
