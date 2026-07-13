# Audit checklist — what to check, what is wrong, how to fix

Nine classes. Each entry is *check → defect → fix*. Remediation code lives
in [remediation-templates](remediation-templates.md); this file is the
diagnosis.

## Table of Contents

- [1. Base image](#1-base-image)
- [2. Runtime user](#2-runtime-user)
- [3. Secrets in layers](#3-secrets-in-layers)
- [4. HEALTHCHECK](#4-healthcheck)
- [5. Multi-stage](#5-multi-stage)
- [6. Layers and cache](#6-layers-and-cache)
- [7. Build context](#7-build-context)
- [8. Instruction hygiene](#8-instruction-hygiene)
- [9. Obsolete patterns — remove on sight](#9-obsolete-patterns--remove-on-sight)

## 1. Base image

| Check | Defect | Fix |
|---|---|---|
| `FROM` carries a tag | `FROM node` or `FROM node:latest` — unreproducible, silently changes under you | Pin a real version tag: `FROM node:24-bookworm-slim` (`CKV_DOCKER_7`, `DS-0001`) |
| Tag vs digest | A tag is mutable; `node:24-slim` today is not `node:24-slim` next month | For anything security-sensitive, pin the digest too: `FROM node:24-bookworm-slim@sha256:…` |
| Image is minimal | `FROM ubuntu` to run one static binary — a whole distro of attack surface | Prefer `-slim`, Alpine, distroless, or `scratch` for static binaries |
| Image is official | A random namespace image in the supply-chain hot path | Prefer official or verified-publisher images |

A tag satisfies the scanners. A digest satisfies *reproducibility*. They
are different guarantees — a pinned tag still floats. Digest-pin any image
that sits in a supply-chain-sensitive path, and bump it deliberately.

"Minimal" deserves a number, not an adjective, and each minimal base carries
a cost (Alpine's musl libc, distroless's absent shell, scratch's missing CA
bundle and user database) — the size table and the per-base tradeoffs are in
[image-scanning-and-runtime](image-scanning-and-runtime.md). That same file
covers the separate question a policy scan never answers: whether the built
image ships known CVEs (`trivy image` / `docker scout`), which is distinct
from the `DS-*`/`CKV_DOCKER_*` misconfiguration check.

## 2. Runtime user

| Check | Defect | Fix |
|---|---|---|
| A user is created | No `USER` at all → the container runs as root | Create one and switch to it (`CKV_DOCKER_3`) |
| The LAST `USER` is non-root | `USER` set, then a later `USER root` for a fix-up, never switched back | Ensure the final `USER` is unprivileged (`CKV_DOCKER_8`, `DS-0002`) |
| The base's default user is declared | Base already runs non-root, but the Dockerfile never says so | Declare it anyway: `USER mitmproxy`. Scanners assert the *file*, not the base's metadata — and an explicit `USER` survives a base-image change |
| The user owns its files | Non-root user cannot write `/work` | `COPY --chown=` / `chown` the writable dirs |
| UID does not collide | `useradd -u 1000` on a `node:*` image collides with the existing `node` user (UID 1000) | Reuse the base's user, or pick a free high UID |

The "declare the default" row is a real fix, not a formality: `mitm.Dockerfile`
in this repo inherits a non-root base yet still failed the policy until
`USER mitmproxy` was written out.

## 3. Secrets in layers

| Check | Defect | Fix |
|---|---|---|
| No credential in `ENV`/`ARG` | `ENV API_KEY=sk_live_…` — baked into the image, visible to anyone who pulls it | Remove it. Pass secrets at RUN time, or use a BuildKit secret mount |
| Secret not written-then-deleted | `RUN echo "$TOKEN" > /cfg` … `RUN rm /cfg` — the file still exists in the earlier layer | Use `--mount=type=secret`; deleting in a later layer does NOT remove it from history |
| Build args are not secrets | `ARG NPM_TOKEN` lands in `docker history` | BuildKit secret mount |
| No credential in the context | A stray `.env` copied by `COPY . .` | `.dockerignore`, and narrow the `COPY` |

CRITICAL every time. A secret in a layer is compromised the moment the
image is shared — treat it as a rotation event, not a cleanup task.

## 4. HEALTHCHECK

| Check | Defect | Fix |
|---|---|---|
| Long-running service has one | Orchestrator cannot tell a hung container from a healthy one | Add `HEALTHCHECK` (`CKV_DOCKER_2`, `DS-0026`) |
| Ephemeral container "missing" one | The scanner still fires — but the check does not apply | Documented suppression. See [suppression-policy](suppression-policy.md) |

The single most-often *wrongly suppressed* check. A run-once tool container
that executes one command and exits has no health to report; a shipped
service that takes traffic absolutely does. Decide by image kind, and write
the reason down.

## 5. Multi-stage

| Check | Defect | Fix |
|---|---|---|
| Build tools absent from runtime | Single stage ships compilers, headers, and the whole SDK | Split builder and runtime stages |
| Only artefacts cross the boundary | `COPY --from=builder /app /app` drags build junk along | Copy the narrowest possible path |
| Stage aliases are unique | Two stages named `builder` (`CKV_DOCKER_11`) | Rename |
| Build deps removed if single-stage is unavoidable | `gcc` left installed after a native build | Install, use, and remove in ONE layer (virtual package group) |

Typical impact: a Go service goes from ~1 GB to ~10 MB. This is the single
highest-leverage size fix.

Not every extra `FROM` is a defect. A `--target`-gated **test stage** (tests
run during the build, test deps never reach production) and a
`--platform`-driven **multi-arch cross-compile** stage are legitimate
patterns — recognise them before flagging. Templates for both, plus the
`COPY --from=<registry-image>` supply-chain case, are in
[remediation-templates](remediation-templates.md).

## 6. Layers and cache

| Check | Defect | Fix |
|---|---|---|
| Layers ordered least-to-most volatile | `COPY . .` before the dependency install → every source edit re-installs every dependency | Copy the manifest, install, THEN copy the source |
| Package cache cleaned in-layer | `rm -rf /var/lib/apt/lists/*` in a *later* `RUN` frees nothing | Clean in the SAME `RUN` |
| `update` is not alone | `RUN apt-get update` as its own layer → stale-cache bugs (`CKV_DOCKER_5`) | Chain `update && install` |
| Package versions pinned | `apt-get install -y git` drifts (`DL3008`, `DL3016`, `DL3013`, `DL3018`) | Pin, or document why not |
| `--no-install-recommends` | apt drags in tens of unneeded packages | Always pass it |

On pinning: distro package pins go stale fast and break rebuilds when the
archive drops the old version. A *deliberate, documented* decision not to
pin apt versions is defensible for an ephemeral container; silently
ignoring `DL3008` on a shipped service is not.

## 7. Build context

| Check | Defect | Fix |
|---|---|---|
| Context is as narrow as possible | `docker build .` at repo root ships `.git`, `node_modules`, `.env` to the daemon | Narrow the context, or add `.dockerignore` |
| `.dockerignore` exists when needed | Wide context with no ignore file → slow builds and secret leaks | Add one |

**Check the actual build command before raising this.** If the context is
already a directory containing only Dockerfiles — as it is here
(`docker build -f "$DF" -t "$TAG" scripts/sandbox/dockerfiles`) — there is
nothing to ignore and no finding to raise. A `.dockerignore` demanded on a
context that holds no secrets is noise, and noise is what teaches people to
ignore audits.

## 8. Instruction hygiene

| Check | Defect | Fix |
|---|---|---|
| `COPY` not `ADD` | `ADD` silently auto-extracts archives and fetches URLs (`CKV_DOCKER_4`) | Use `COPY`; keep `ADD` only for deliberate extraction |
| Exec-form `CMD`/`ENTRYPOINT` | Shell form wraps the process in `/bin/sh -c`, which swallows `SIGTERM` → the container ignores `docker stop` and gets killed | `CMD ["node", "server.js"]` |
| PID 1 reaps children | The app as PID 1 does not reap zombies left by misbehaving post-install scripts | An init shim — this repo uses `tini`: `ENTRYPOINT ["/usr/bin/tini", "--"]` |
| Absolute `WORKDIR` | `WORKDIR app` is relative and surprising (`CKV_DOCKER_10`) | `WORKDIR /work` |
| No `RUN cd` | `RUN cd /app && …` does not persist | `WORKDIR` |
| `LABEL` not `MAINTAINER` | `MAINTAINER` is deprecated (`CKV_DOCKER_6`) | `LABEL org.opencontainers.image.authors=…` |
| Port 22 not exposed | SSH in a container (`CKV_DOCKER_1`) | Remove it; use `docker exec` |
| TLS verification intact | Any `CKV2_DOCKER_*` hit — disabled cert checks | Never disable TLS verification to make a build pass |
| `pipefail` before piped `RUN` | A failing command mid-pipe is ignored (`DL4006`) | `SHELL ["/bin/bash", "-o", "pipefail", "-c"]` |

The exec-form row is the one people underrate: shell form is why a
container takes 10 seconds to die and then loses in-flight work.

## 9. Obsolete patterns — remove on sight

Each verified against current tooling. Carrying these forward is how an
audit ages badly.

| Pattern | Status | Replacement |
|---|---|---|
| `docker build --squash` | **Removed.** Docker 29 warns: *"experimental flag squash is removed with BuildKit"* | Use a multi-stage build |
| `npm ci --only=production` | **Deprecated.** npm 11 warns: *"Use `--omit=dev` to omit dev dependencies"* | `npm ci --omit=dev` |
| `MAINTAINER` | Deprecated instruction | `LABEL org.opencontainers.image.authors=…` |
| `ADD` for a local file | Implicit, surprising behaviour | `COPY` |
| Installing a tool by piping a downloaded script straight into a shell | Unauditable, unpinnable, runs whatever the server returns | Install from the package manager with a pinned version |

That last row is a security finding, not a style nit: a build step that
downloads a script and runs it in one breath cannot be reviewed, cannot be
pinned, and hands the build to whoever controls that URL. This repo hit it
directly — the `uv` installer was moved to a pinned
`pip install "uv==${UV_VERSION}"` for exactly this reason.

Also worth knowing (not obsolete, just newer than most Dockerfiles):
`COPY --link` (rebuild-friendly layers), `COPY --chmod`, and buildx
`--provenance` / `--sbom` attestations. All verified to exist; reach for
them when hardening a shipped image.
