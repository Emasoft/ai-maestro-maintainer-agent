# GitLab CI audit — `.gitlab-ci.yml` and included files

The checks below run against every tracked `.gitlab-ci.yml` and every
file it pulls in with `include:`. Parse with `python3` +
`yaml.safe_load` (never `yaml.load`); fall back to line scanning only
for the raw-script checks. Each check is *what to look for → why it is
dangerous → the safe fix*.

## Table of Contents

- [Live validation — the CI Lint API](#live-validation--the-ci-lint-api)
- [1. Secrets — masked, protected, never hardcoded](#1-secrets--masked-protected-never-hardcoded)
- [2. Protected branches and tags — the ref gate](#2-protected-branches-and-tags--the-ref-gate)
- [3. `rules:` / `only:` / `except:` correctness](#3-rules--only--except-correctness)
- [4. Runner trust and privileged docker](#4-runner-trust-and-privileged-docker)
- [5. Images — pin the tag, prefer a digest](#5-images--pin-the-tag-prefer-a-digest)
- [6. Artifacts and cache poisoning](#6-artifacts-and-cache-poisoning)
- [7. Script hygiene and remote `include:` trust](#7-script-hygiene-and-remote-include-trust)
- [Remediation templates (paste, then adapt)](#remediation-templates-paste-then-adapt)

## Live validation — the CI Lint API

The GitLab CI Lint API is the authoritative validator: it resolves
`include:`, `extends`, and variable interpolation the way the server
will. Use the **project-scoped** endpoint so includes resolve.

```bash
# Needs a token with the `api` scope; read-only, does not create a pipeline.
CONTENT="$(jq -Rs . < .gitlab-ci.yml)"
curl -sS --header "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  --header "Content-Type: application/json" \
  --data "{\"content\": $CONTENT, \"include_merged_yaml\": true}" \
  "$CI_SERVER_URL/api/v4/projects/$PROJECT_ID/ci/lint"
```

The response carries `valid` (bool), `errors[]`, `warnings[]`, and
`merged_yaml`. The `glab` CLI wraps the same API: `glab ci lint`
(current dir) or `glab ci lint --dry-run` for a pipeline-creation
simulation. If no token or server is reachable, note the gap and rely on
the static checks below — never report PASS from a skipped lint.

## 1. Secrets — masked, protected, never hardcoded

**Look for** a credential-shaped literal assigned in `variables:` or
passed on a `script:` command line: `password`, `api[_-]?key`,
`token`, `secret`, `AWS_SECRET_ACCESS_KEY`, a `Bearer`/`Basic` auth
header value, a `-----BEGIN … PRIVATE KEY-----` block, or a
`postgres://user:pass@…` connection string. A value that is a `$VAR`
reference is fine; a literal is the finding.

**Why** anything committed to `.gitlab-ci.yml` is in git history for
every clone, forever, and rides into job logs.

**Fix** move the value to a CI/CD variable set in *Settings → CI/CD →
Variables* with both flags on:

- **Masked** — the value is replaced with `[MASKED]` in job logs.
- **Protected** — the variable is only exposed to jobs running on a
  protected branch or protected tag, so a fork or an unprotected feature
  branch can never read the production credential.

For dynamic secrets prefer the `secrets:` keyword backed by Vault:

```yaml
deploy:
  secrets:
    DATABASE_PASSWORD:
      vault: production/db/password@secret
  script:
    - deploy --db-password "$DATABASE_PASSWORD"
```

A masked variable still leaks if a script echoes it — flag any
`echo`/`print` of a `$…PASSWORD`/`$…TOKEN`/`$…SECRET` variable
(`secret-in-logs`, MEDIUM), and flag `CI_DEBUG_TRACE: "true"` on any job
that can reach a protected variable (`debug-trace-exposes-secrets`,
HIGH) — debug trace prints the full expanded environment.

## 2. Protected branches and tags — the ref gate

**Look for** a deploy/publish/release job whose only guard is a branch
*name*, or a job with no `rules:` at all that nonetheless holds a
production credential.

**Why** GitLab runs pipelines for fork merge requests and for every
feature branch. A job gated on `$CI_COMMIT_BRANCH == "main"` still
*evaluates* on other refs, and a job with a protected variable that is
reachable from an unprotected ref is a credential-exfil path.

**Fix** gate on the protected-ref signal, not the name, and require a
protected environment for production:

```yaml
deploy-production:
  rules:
    - if: '$CI_COMMIT_REF_PROTECTED == "true" && $CI_COMMIT_BRANCH == "main"'
      when: manual            # human approval on the deploy
  environment:
    name: production          # mark Protected in Settings → CI/CD → Environments
  resource_group: production  # serialize — no concurrent prod deploys
```

Release-on-tag jobs must pin the tag *shape* and use protected tags:

```yaml
release:
  rules:
    - if: '$CI_COMMIT_TAG =~ /^v\d+\.\d+\.\d+$/ && $CI_COMMIT_REF_PROTECTED == "true"'
```

## 3. `rules:` / `only:` / `except:` correctness

**Look for**: `only:`/`except:` still in use (legacy, superseded by
`rules:` and easy to get subtly wrong when mixed); a `rules:` list whose
first matching clause is broader than intended; a deploy job missing an
explicit `when:` (defaults to `on_success`, so it runs automatically);
`when: always` on a job that touches production.

**Why** rule ordering is first-match-wins. A permissive early clause
silently enables a job on refs the author never meant to cover —
including fork pipelines.

**Fix** convert `only:`/`except:` to `rules:`; order clauses
most-specific-first; make the production path explicit and manual. State
the intended trigger set in a comment so the next reader can verify it.

## 4. Runner trust and privileged docker

**Look for** a sensitive job with no `tags:` (so it lands on any shared
runner), and Docker-in-Docker configured with the runner in privileged
mode.

**Why** a shared runner may be a multi-tenant machine; a privileged dind
container can escape to the host and read every other job's secrets on
that runner.

**Fix** tag sensitive jobs onto a dedicated, trusted runner and disable
shared runners for the project when it handles production credentials:

```yaml
deploy-production:
  tags: [production-runner, secured]
  script:
    - deploy production
```

For image builds prefer a rootless, unprivileged builder (`buildah`,
`kaniko`, or BuildKit rootless) over privileged dind. If privileged dind
is genuinely required, that is a HIGH finding written up for human
sign-off — never auto-"fixed", because removing it can break the build.

## 5. Images — pin the tag, prefer a digest

**Look for** `image: something:latest`, or `image:` with no tag at all
(implies `:latest`), on any job.

**Why** `:latest` is a moving target: the bytes your pipeline executes
can change under you with no diff, which is both a reproducibility and a
supply-chain problem.

**Fix** pin `major.minor.patch` and, for anything security-sensitive,
append a digest so the content is immutable:

```yaml
test:
  image: node:20.11-alpine3.19@sha256:<digest>
```

Third-party images (not official library images) get an extra note:
verify the publisher before trusting them.

## 6. Artifacts and cache poisoning

**Look for** an over-broad artifact glob (`paths: ["./**"]` or a bare
`.`), no `expire_in:`, no `exclude:` for secret-shaped files, and a
`cache:` whose `key:` is shared across refs.

**Why** a wide artifact glob sweeps `.env`, `*.pem`, `*.key`,
`credentials.*`, and `.git/` into a downloadable artifact. A cache keyed
without the ref lets a job on an untrusted branch write a poisoned cache
that a trusted job later restores and executes.

**Fix** scope artifacts to build outputs, exclude secret shapes, set an
expiry, and key the cache per ref with a read-only policy where a job
only consumes it:

```yaml
build:
  script: [make build]
  artifacts:
    paths: [dist/]
    exclude: ["**/*.env", "**/*.pem", "**/*.key", "**/credentials.*", ".git/"]
    expire_in: 1 hour
  cache:
    key: "$CI_COMMIT_REF_SLUG"
    paths: [.cache/]
    policy: pull            # this job only reads the cache; it cannot poison it
```

## 7. Script hygiene and remote `include:` trust

**Look for**:

- an install step that pipes a *downloaded* script straight into a shell
  interpreter (the download-and-pipe-to-shell anti-pattern) — HIGH;
- `eval` applied to an interpolated variable — code-injection shape, HIGH;
- a world-writable `chmod 777`, the TLS-disabling curl flags `-k` /
  `--insecure`, or `git config … http.sslVerify false` — disabled
  verification, HIGH;
- a script with no `set -euo pipefail`, so a failed step is silently
  ignored — MEDIUM.

**Fix (download-and-verify instead of pipe-to-shell)** download the
installer to a file, verify a published checksum with `sha256sum -c`,
then run the verified file — the byte stream is pinned and inspectable
before it executes. Replace an `eval`-on-a-variable with an explicit
command and validated arguments. Never disable TLS verification; point
the client at the correct CA bundle instead. Add `set -euo pipefail` to
every multi-line `script:`.

**Remote includes**: `include: remote:` pulls YAML from a URL and
`include: project:`/`component:` from another project — both execute in
your pipeline's trust context. Pin `project:` includes to a `ref:` that
is a commit SHA (not a moving branch), and treat an unpinned or
third-party `remote:` include as a MEDIUM supply-chain finding.

## Remediation templates (paste, then adapt)

Masked+protected variable in place of a literal:

```yaml
# BEFORE (finding): deploy --api-key sk_live_...        # hardcoded — CRITICAL
# AFTER: set API_KEY in Settings → CI/CD → Variables (Masked + Protected)
deploy:
  script:
    - deploy --api-key "$API_KEY"
```

Protected, manual, single-flight production deploy: see §2.

Pinned, scoped, expiring artifacts + pull-only cache: see §6.
