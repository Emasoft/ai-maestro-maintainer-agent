# Remediation templates

Copy-paste fixes for the defects in [audit-checklist](audit-checklist.md).
These are REMEDIATION templates — the target is always a Dockerfile that
already exists. Do not use this file to author a new image from scratch.

Apply the smallest change that removes the finding at its root.

## Table of Contents

- [Non-root user](#non-root-user)
- [Pinned base image](#pinned-base-image)
- [HEALTHCHECK (services only)](#healthcheck-services-only)
- [Multi-stage — strip build tooling from the runtime](#multi-stage--strip-build-tooling-from-the-runtime)
- [Single-stage that cannot be split — drop the build deps](#single-stage-that-cannot-be-split--drop-the-build-deps)
- [Layer cache — order least-to-most volatile](#layer-cache--order-least-to-most-volatile)
- [Package install hygiene](#package-install-hygiene)
- [Secrets — never bake, always mount](#secrets--never-bake-always-mount)
- [Installing a third-party tool safely](#installing-a-third-party-tool-safely)
- [PID-1 init — reap zombies, forward signals](#pid-1-init--reap-zombies-forward-signals)
- [.dockerignore](#dockerignore)
- [Instruction hygiene](#instruction-hygiene)
- [Hardening a shipped image further](#hardening-a-shipped-image-further)

## Non-root user

The fix depends on what the base image already gives you. Check first —
inventing a second UID-1000 user on a `node:*` image collides with the
`node` user that is already there.

```dockerfile
# Debian / Ubuntu base, no suitable user exists
RUN useradd -m -u 10001 appuser \
 && mkdir -p /work /out \
 && chown appuser:appuser /work /out
USER appuser
```

```dockerfile
# Alpine base
RUN addgroup -g 10001 -S appgroup \
 && adduser -S appuser -u 10001 -G appgroup
USER appuser
```

```dockerfile
# Base ALREADY ships a non-root user (node:*, mitmproxy/*, distroless)
# Reuse it — and DECLARE it, or the policy check still fails.
RUN mkdir -p /work /out && chown node:node /work /out
USER node
```

```dockerfile
# Distroless
USER nonroot:nonroot
```

A high UID (>10000) avoids collisions with host users when the container
shares a namespace. Whatever user you pick, make sure it OWNS every
directory it must write.

## Pinned base image

```dockerfile
# Before — floats, unreproducible
FROM node:latest

# After — pinned tag (satisfies CKV_DOCKER_7 / DS-0001)
FROM node:24-bookworm-slim

# Hardened — pinned digest (reproducible; bump deliberately)
FROM node:24-bookworm-slim@sha256:cb4e8f7c443347358b7875e717c29e27bf9befc8f5a26cf18af3c3dec80e58c5
```

Leave a comment saying WHY the digest is pinned, or the next person will
"helpfully" drop it during a version bump.

## HEALTHCHECK (services only)

Only for long-running images. If the container runs one command and exits,
the correct remediation is a documented suppression, not a fake health
probe — see [suppression-policy](suppression-policy.md).

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -fsS http://localhost:8080/health || exit 1
```

The probe must exist IN the image. On a distroless or `scratch` runtime
there is no `curl` and no shell — use a static health binary you already
ship, or accept that the check is inapplicable and document it.

## Multi-stage — strip build tooling from the runtime

The highest-leverage size and attack-surface fix.

```dockerfile
# syntax=docker/dockerfile:1

FROM golang:1.24-alpine AS builder
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /out/server ./cmd/server

FROM gcr.io/distroless/static-debian12
COPY --from=builder /out/server /server
USER nonroot:nonroot
ENTRYPOINT ["/server"]
```

Node, production dependencies only — note `--omit=dev`, NOT the deprecated
`--only=production`:

```dockerfile
# syntax=docker/dockerfile:1

FROM node:24-bookworm-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

FROM node:24-bookworm-slim
WORKDIR /app
COPY --from=deps --chown=node:node /app/node_modules ./node_modules
COPY --chown=node:node . .
USER node
CMD ["node", "server.js"]
```

Python, with the dependency tree built in a throwaway stage:

```dockerfile
# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
# <prefix> is the shared usr/local tree — on the default search path, world-readable
COPY --from=builder /install <prefix>
WORKDIR /app
COPY . .
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser
CMD ["python", "app.py"]
```

Install into the shared `usr/local` prefix (the `<prefix>` above), not a
per-user `root/.local` tree — a non-root user cannot read the `root` home,
so the `--user`-into-`root/.local` pattern produces an image that fails the
moment you add the `USER` the policy demands.

## Single-stage that cannot be split — drop the build deps

```dockerfile
RUN apk add --no-cache --virtual .build-deps gcc musl-dev \
 && pip install --no-cache-dir -r requirements.txt \
 && apk del .build-deps
```

Install, use, and remove in ONE `RUN`. Removing them in a later layer frees
nothing.

## Layer cache — order least-to-most volatile

```dockerfile
# Before — any source edit re-installs every dependency
COPY . .
RUN npm ci

# After — dependencies re-install only when the manifest changes
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
```

BuildKit cache mounts keep the package cache across builds:

```dockerfile
# syntax=docker/dockerfile:1
RUN --mount=type=cache,target=/root/.npm npm ci --omit=dev
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt
```

## Package install hygiene

```dockerfile
# Before — update in its own layer, no cleanup, recommends pulled in
RUN apt-get update
RUN apt-get install -y git curl

# After — one layer, cleaned in-layer, no recommends
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*
```

Pin versions where the image is a shipped artefact. Look the exact version
up against the base image's package archive — do NOT copy a version string
out of a template:

```dockerfile
RUN apt-get install -y --no-install-recommends git=<archive-version>
RUN npm install -g sfw@<version>                # fixes DL3016
RUN pip install --no-cache-dir "uv==0.4.27"     # fixes DL3013
```

An apt pin that is not in the base image's archive fails the build
outright, and archives drop old versions — which is exactly why an
ephemeral container may reasonably choose NOT to pin apt (documented), while
a shipped service should.

## Secrets — never bake, always mount

```dockerfile
# Before — CRITICAL. Present in the image and in `docker history`.
ARG NPM_TOKEN
ENV NPM_TOKEN=$NPM_TOKEN
RUN npm ci

# After — the secret is mounted for one RUN and never lands in a layer
# syntax=docker/dockerfile:1
RUN --mount=type=secret,id=npmrc,target=/root/.npmrc npm ci --omit=dev
```

```bash
docker build --secret id=npmrc,src="$HOME/.npmrc" .
```

A secret written in one layer and deleted in a later one is STILL in the
image. The only real fix is to never write it.

## Installing a third-party tool safely

Never fetch a script and feed it straight into a shell. That step cannot be
reviewed, cannot be pinned, and delegates the build to whoever controls the
URL. Install from the package manager with an explicit version:

```dockerfile
ARG UV_VERSION=0.4.27
RUN pip install --no-cache-dir "uv==${UV_VERSION}" \
 && uv --version
```

If a project genuinely ships no package, fetch the artefact, verify its
checksum or signature as a separate reviewable step, and only then run it.

## PID-1 init — reap zombies, forward signals

```dockerfile
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash"]
```

Without an init, a post-install script that forks and dies leaves zombies,
and `SIGTERM` may never reach the real process.

## `.dockerignore`

Only when the build context is actually wide (see class 7). Starter:

```gitignore
.git/
node_modules/
.venv/
__pycache__/
dist/
build/
*.log
.env
.env.*
*.pem
*.key
reports/
```

`.env`, `*.pem`, and `*.key` are the load-bearing lines — they are how a
credential ends up in an image via `COPY . .`.

## Instruction hygiene

```dockerfile
# Signals: exec form, so SIGTERM reaches the process
CMD ["python", "app.py"]

# Ownership without an extra layer
COPY --chown=appuser:appuser . /app

# Absolute WORKDIR instead of `RUN cd`
WORKDIR /app

# Metadata (LABEL replaces the deprecated MAINTAINER)
LABEL org.opencontainers.image.source="https://github.com/owner/repo"
LABEL org.opencontainers.image.authors="team@example.com"

# Fail a piped RUN on the first error
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
```

## Hardening a shipped image further

```bash
# Attestations — provenance and SBOM ride along with the image
docker buildx build --provenance=true --sbom=true -t app:1.2.3 .
```

`COPY --link` produces layers that survive a base-image change without a
rebuild; `COPY --chmod=0644` sets permissions without an extra `RUN chmod`.
