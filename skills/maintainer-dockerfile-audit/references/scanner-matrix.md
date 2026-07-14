# Scanner matrix — the four tools and their real invocations

Every command here was executed against this repo's own Dockerfiles. Every
flag is real. Where a flag does NOT exist, that is called out — guessing a
plausible flag is how an audit script silently stops scanning.

## Table of Contents

- [Why four tools](#why-four-tools)
- [Prefer the container form](#prefer-the-container-form)
- [Verified flags](#verified-flags)
- [Exit codes](#exit-codes)
- [Checkov Dockerfile catalogue](#checkov-dockerfile-catalogue-complete-from-checkov--l)
- [Trivy Dockerfile IDs](#trivy-dockerfile-ids)
- [hadolint rules seen most often](#hadolint-rules-seen-most-often)
- [CI wiring in this repo](#ci-wiring-in-this-repo)

## Why four tools

| Tool | Layer it inspects | What it will NOT tell you |
|---|---|---|
| hadolint | Dockerfile SOURCE (lint/style) | Whether the image runs as root |
| Checkov | Dockerfile POLICY (`CKV_DOCKER_*`) | Whether a layer is wasteful |
| Trivy `config` | Dockerfile POLICY (`DS-*`) | Anything hadolint's DL rules cover |
| dive | BUILT IMAGE layers | Anything about the source text |

hadolint passing says nothing about policy. Checkov passing says nothing
about image size. Run all four; treat them as complementary, never as
substitutes.

All four inspect the Dockerfile SOURCE or a built image's LAYERS for
style/policy/waste. None of them tell you whether the built image ships a
**known-vulnerable package** — that is a fifth dimension (image CVE + secret
scanning via `trivy image` / `docker scout` / `grype`) plus layer forensics
via `docker history`. Both live in
[image-scanning-and-runtime](image-scanning-and-runtime.md).

## Prefer the container form

Every scanner ships an official image, so the audit needs no host installs
and cannot drift from CI:

```bash
DF=scripts/sandbox/dockerfiles/node-baseline.Dockerfile

# hadolint — reads the Dockerfile on stdin
docker run --rm -i hadolint/hadolint hadolint --no-color - < "$DF"

# Checkov — scans a directory of Dockerfiles
docker run --rm -v "$PWD/scripts/sandbox/dockerfiles:/src:ro" \
  bridgecrew/checkov:latest -d /src --framework dockerfile --compact --quiet

# Trivy — misconfiguration scan over the same directory
docker run --rm -v "$PWD/scripts/sandbox/dockerfiles:/src:ro" \
  aquasec/trivy:latest config -q --skip-version-check /src

# dive — layer waste, non-interactive
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  wagoodman/dive:latest --ci <image>:<tag>
```

If a host binary is present, use it — same flags, faster. Never make the
audit *depend* on one.

## Verified flags

Only these are confirmed to exist. Do not invent others.

| Tool | Flag | Meaning |
|---|---|---|
| hadolint | `--no-color` | Plain output |
| hadolint | `-f`, `--format` | Output format (`tty`, `json`, …) |
| hadolint | `--ignore RULECODE` | Ignore one rule |
| hadolint | `--error RULECODE` | Promote a rule to error |
| hadolint | `-t`, `--failure-threshold` | Exit-code threshold |
| hadolint | `-` | Read the Dockerfile from stdin |
| Checkov | `-d DIR` | Scan a directory |
| Checkov | `--framework dockerfile` | Restrict to Dockerfile policies |
| Checkov | `--compact`, `--quiet` | Terse output |
| Checkov | `--skip-check ID[,ID]` | Suppress named checks |
| Trivy | `config DIR` | Misconfiguration scan |
| Trivy | `-q`, `--quiet` | Suppress the progress bar |
| Trivy | `--skip-version-check` | No update nag |
| Trivy | `--exit-code N` | Exit N when findings exist |
| Trivy | `--severity` | Filter by severity |
| Trivy | `--ignorefile PATH` | Ignore file (default `.trivyignore`) |
| Trivy | `-f`, `--format` | `table`, `json`, `sarif`, … |
| dive | `--ci` | Skip the TUI, validate against CI rules |

**`trivy config` has no `--no-progress` flag.** It is a real flag on other
Trivy subcommands, and assuming it here makes Trivy exit FATAL — the scan
never runs and a careless script reads that as "clean". Use `-q`.

## Exit codes

- hadolint — non-zero when a rule at or above the failure threshold fires.
- Checkov — non-zero when any non-skipped check fails.
- Trivy — `0` by default **even when findings exist**. To gate CI you must
  pass `--exit-code 1`. A Trivy step without it is decorative.
- dive — non-zero when the image is below the configured efficiency rules.

## Checkov Dockerfile catalogue (complete, from `checkov -l`)

| ID | Instruction | Check |
|---|---|---|
| `CKV_DOCKER_1` | EXPOSE | Ensure port 22 is not exposed |
| `CKV_DOCKER_2` | * | Ensure HEALTHCHECK instructions have been added |
| `CKV_DOCKER_3` | * | Ensure a user for the container has been created |
| `CKV_DOCKER_4` | ADD | Ensure COPY is used instead of ADD |
| `CKV_DOCKER_5` | RUN | Ensure update instructions are not used alone |
| `CKV_DOCKER_6` | MAINTAINER | Ensure LABEL maintainer is used instead of the deprecated MAINTAINER |
| `CKV_DOCKER_7` | FROM | Ensure the base image uses a non-latest version tag |
| `CKV_DOCKER_8` | USER | Ensure the last USER is not root |
| `CKV_DOCKER_9` | RUN | Ensure that APT isn't used |
| `CKV_DOCKER_10` | WORKDIR | Ensure WORKDIR values are absolute paths |
| `CKV_DOCKER_11` | FROM | Ensure FROM aliases are unique in multi-stage builds |

`CKV_DOCKER_6` is the deprecated-`MAINTAINER` check, NOT the APT one —
the APT check is `CKV_DOCKER_9`. Confusing the two leads to skipping the
wrong policy.

The `CKV2_DOCKER_*` family is almost entirely about **disabled TLS
verification** — treat any hit as HIGH:

| ID | Check |
|---|---|
| `CKV2_DOCKER_1` | `sudo` isn't used |
| `CKV2_DOCKER_2` | Certificate validation isn't disabled with curl |
| `CKV2_DOCKER_3` | Certificate validation isn't disabled with wget |
| `CKV2_DOCKER_4` | pip `--trusted-host` isn't used |
| `CKV2_DOCKER_5` | `PYTHONHTTPSVERIFY` isn't disabled |
| `CKV2_DOCKER_6` | `NODE_TLS_REJECT_UNAUTHORIZED` isn't disabled |
| `CKV2_DOCKER_7` | apk `--allow-untrusted` isn't used |
| `CKV2_DOCKER_8` | apt-get `--allow-unauthenticated` isn't used |
| `CKV2_DOCKER_9` | dnf/tdnf/yum `--nogpgcheck` isn't used |
| `CKV2_DOCKER_10` | rpm signature checks aren't bypassed |
| `CKV2_DOCKER_11` | apt `--force-yes` isn't used |
| `CKV2_DOCKER_12` | `NPM_CONFIG_STRICT_SSL` isn't disabled |
| `CKV2_DOCKER_13` | npm/yarn `strict-ssl` isn't set false |
| `CKV2_DOCKER_14` | `GIT_SSL_NO_VERIFY` isn't set |
| `CKV2_DOCKER_15` | yum/dnf `sslverify` isn't disabled |
| `CKV2_DOCKER_16` | `PIP_TRUSTED_HOST` isn't set |
| `CKV2_DOCKER_17` | `chpasswd` isn't used |

## Trivy Dockerfile IDs

Current Trivy (0.72.0) prints the SHORT form — `DS-0026`, not
`AVD-DS-0026`. The commonly-hit ones:

| ID | Severity | Check |
|---|---|---|
| `DS-0001` | HIGH | `:latest` tag used |
| `DS-0002` | HIGH | Image user should not be root |
| `DS-0026` | LOW | No HEALTHCHECK defined |

The legacy `AVD-DS-` prefix is still accepted as an ALIAS in
`.trivyignore` — verified: a `.trivyignore` containing `AVD-DS-0026`
suppresses `DS-0026` on Trivy 0.72.0 (0 misconfigurations, exit 0). Both
spellings work; do not "fix" a working `AVD-` entry.

## hadolint rules seen most often

| ID | Rule |
|---|---|
| `DL3006` | Tag the version of an image explicitly |
| `DL3007` | Do not use `:latest`; pin an explicit version |
| `DL3008` | Pin versions in `apt-get install` |
| `DL3013` | Pin versions in `pip install` |
| `DL3016` | Pin versions in `npm install` |
| `DL3018` | Pin versions in `apk add` |
| `DL3059` | Consecutive `RUN` instructions should be merged |
| `DL4006` | Set `SHELL` with `-o pipefail` before a `RUN` with a pipe |

`DL3013` misfires on version pins supplied through an `ARG`, and `DL3006`
misfires on a fully-qualified non-Docker-Hub registry image that IS tagged —
both are in [false-positives](false-positives.md).

hadolint takes three suppression forms: the `--ignore RULECODE` CLI flag, an
`ignored:` list in `.hadolint.yaml`, and an in-file `# hadolint ignore=RULECODE`
comment placed on the line ABOVE the flagged instruction. The in-file comment
is the right tool for a single genuine false positive (see DL3006 above);
never blanket-ignore a rule to clear a real finding.

## CI wiring in this repo

Checkov and Trivy run through MegaLinter, not as standalone steps:

```yaml
ENABLE_LINTERS:
  - REPOSITORY_CHECKOV
  - REPOSITORY_TRIVY

REPOSITORY_CHECKOV_ARGUMENTS: "--skip-check CKV2_GHA_1,CKV_DOCKER_2"
```

Consequences that trip people up:

- Trivy reads `.trivyignore` from the repo root automatically — that is
  where Trivy suppressions live, NOT in `.mega-linter.yml`.
- Checkov suppressions live in `REPOSITORY_CHECKOV_ARGUMENTS`.
- The two scanners overlap: HEALTHCHECK is `CKV_DOCKER_2` **and**
  `DS-0026`. Suppressing one and forgetting the other leaves CI red and
  invites a second, sloppier suppression. Always fix or suppress both ends.
- hadolint is NOT enabled in this repo's MegaLinter config. Run it
  manually during an audit; its DL findings are real even though CI is
  silent about them.
