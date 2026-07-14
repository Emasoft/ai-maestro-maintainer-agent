# Image CVE scanning, layer forensics, base-image sizing, and runtime hardening

The four-tool matrix in [scanner-matrix](scanner-matrix.md) answers *is the
Dockerfile SOURCE well-written and does it violate POLICY*. It does not
answer *does the built image ship a known-vulnerable package*, *what is
actually inside each layer*, or *how is the container run in production*.
Those are four separate audit dimensions, collected here.

## Table of Contents

- [Config scan vs image scan — two different questions](#config-scan-vs-image-scan--two-different-questions)
- [Image vulnerability and secret scanning](#image-vulnerability-and-secret-scanning)
- [docker history — layer sizes and baked-in secrets](#docker-history--layer-sizes-and-baked-in-secrets)
- [Base-image size and attack surface](#base-image-size-and-attack-surface)
- [Per-base tradeoffs — alpine, distroless, scratch](#per-base-tradeoffs--alpine-distroless-scratch)
- [Runtime hardening the Dockerfile cannot enforce](#runtime-hardening-the-dockerfile-cannot-enforce)
- [Compliance anchors](#compliance-anchors)

## Config scan vs image scan — two different questions

| Question | Subcommand | Reads |
|---|---|---|
| Does the Dockerfile violate policy? | `trivy config` | the Dockerfile TEXT (misconfiguration IDs `DS-*`) |
| Does the BUILT image carry known CVEs? | `trivy image` | the image's installed packages + OS + language deps |

A Dockerfile can pass every `DS-*` policy and still ship a base image full of
unpatched CVEs — the two scans never overlap. An audit that runs only
`trivy config` has said nothing about the image's vulnerability posture. Run
both, on the built image, whenever the target is a shipped artefact.

## Image vulnerability and secret scanning

All run as containers — no host install, no CI drift:

```bash
IMG=myimage:1.2.3

# Trivy — OS + language CVEs AND secret scanning of the image layers,
# gated so CI actually fails on findings (trivy exits 0 by default).
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy:latest image --scanners vuln,secret \
  --severity HIGH,CRITICAL --exit-code 1 -q "$IMG"

# Docker Scout — Docker's official CVE tool (the CURRENT replacement).
docker scout cves "$IMG"
docker scout quickview "$IMG"

# Grype (Anchore) — second-opinion CVE scanner.
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  anchore/grype:latest "$IMG"
```

Two current-tooling corrections:

- **`docker scan` is gone.** It was the Snyk-backed subcommand; it is
  deprecated and removed. Reach for `docker scout cves` instead — anything
  in the corpus that still says `docker scan` is stale.
- **`trivy image` also finds baked secrets** (`--scanners secret`). This
  complements — it does not replace — `maintainer-secrets-scan`, which
  covers git history. Use `trivy image` to catch a credential that made it
  into an image LAYER even when it was never committed.

`trivy image` and `docker scout` both recommend a less-vulnerable base tag
in their output; treat that recommendation as an input to the base-image
decision, not as an order.

## docker history — layer sizes and baked-in secrets

`dive` gives an interactive layer view; `docker history` gives the same
facts non-interactively and is the fastest way to PROVE a secret is baked in:

```bash
# Biggest layers first — find the bloat without the TUI.
docker history --no-trunc --format 'table {{.Size}}\t{{.CreatedBy}}' myimage:1.2.3 \
  | sort -hr | head

# A secret passed via ARG/ENV is visible right here, in cleartext.
docker history --no-trunc myimage:1.2.3 | grep -iE 'token|secret|password|api[_-]?key'
```

This is the load-bearing evidence for a class-3 (secret-in-layer) finding: a
credential removed in a later `RUN` still appears in the layer that created
it, and `docker history` shows it. A "we deleted it later" defence dies here.

## Base-image size and attack surface

Concrete, approximate sizes to justify a base-image recommendation with a
number instead of an adjective:

| Base | Approx size | Shell / package manager |
|---|---|---|
| `ubuntu:22.04` | ~78 MB | yes |
| `node:20` | ~1 GB | yes |
| `node:20-slim` | ~240 MB | yes |
| `node:20-alpine` | ~130 MB | yes (apk) |
| `python:3.12` | ~1 GB | yes |
| `python:3.12-slim` | ~an order of magnitude smaller than the full tag | yes |
| `alpine:3.21` | ~5–8 MB | yes (apk) |
| `gcr.io/distroless/base` | ~20 MB | no shell, no package manager |
| `gcr.io/distroless/static-debian12` | ~2 MB | no shell, no package manager |
| `scratch` | 0 MB (empty) | nothing at all |

Size is a proxy for attack surface: fewer packages means fewer CVEs to patch.
A shipped Go/Rust service on a full-OS base is almost always a finding —
distroless or scratch drops it by two orders of magnitude.

## Per-base tradeoffs — alpine, distroless, scratch

Each minimal base buys size at a cost the audit must weigh:

| Base | Wins | Costs to check |
|---|---|---|
| **Alpine** | tiny, keeps a package manager | musl libc, not glibc — native C extensions and some wheels break or need rebuilding; verify the app actually runs, don't just shrink it |
| **Distroless** | no shell → far smaller attack surface | cannot `docker exec` a shell to debug; a curl-based HEALTHCHECK cannot run (no shell, no curl) — ship a static probe binary or accept the check is inapplicable; MUST be a multi-stage target |
| **Scratch** | absolutely minimal, static binaries only | no CA certs (HTTPS fails until you copy `ca-certificates.crt` in from the builder); no `/etc/passwd`, so `USER` must be a NUMERIC `uid:gid` — a named user fails to resolve; no shell, no libc, no timezone data |

The scratch pitfalls are the ones most often missed on audit: an outbound
HTTPS call that fails only at runtime because no CA bundle was copied, and a
`USER appuser` that a scratch image cannot resolve. Remediation for both is in
[remediation-templates](remediation-templates.md).

## Runtime hardening the Dockerfile cannot enforce

Some of the strongest container controls live in the RUN invocation or the
orchestrator manifest, not the Dockerfile. An audit of a shipped image should
flag their absence as a deploy-manifest recommendation, not a Dockerfile fix:

| Control | How it is applied | Why it matters |
|---|---|---|
| Read-only root filesystem | `docker run --read-only` (+ tmpfs for writable dirs) | a compromised process cannot rewrite the image |
| Drop capabilities | `docker run --cap-drop=ALL --cap-add=NET_BIND_SERVICE` | strips every Linux capability but the ones the app needs |
| Seccomp / MAC profile | `docker run --security-opt seccomp=...` (AppArmor / SELinux) | narrows the syscall + access surface |
| No-new-privileges | `docker run --security-opt no-new-privileges` | a container process cannot gain rights beyond what it launched with |
| PID + resource limits | `--pids-limit`, `--memory`, `--cpus` | fork-bomb and resource-exhaustion containment |
| Pull-time trust | `DOCKER_CONTENT_TRUST=1` in the client env | verifies image signatures before running |

The Dockerfile makes read-only feasible (write only to declared volumes /
tmpfs) but cannot switch it on — so a Dockerfile designed for a read-only
runtime that then runs read-write is a wasted control worth flagging.

## Compliance anchors

When an audit must map to a framework, cite the source of the control rather
than restating it:

- CIS Docker Benchmark — the canonical control catalogue for Docker.
- NIST SP 800-190 — Application Container Security Guide.
- OWASP Docker Security Cheat Sheet.

Reference them inside a finding ("fails CIS 4.1 — a non-root user must be
created") rather than pasting the framework into the report.
