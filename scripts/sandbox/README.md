# sandbox/ — maintainer-agent Docker sandbox harness

A small, composable Docker sandbox the maintainer agent uses to:

- Test third-party tools (Aikido Safe Chain, Socket Firewall, etc.) before
  recommending them to the user.
- Reproduce user-reported issues by cloning external repos into a throwaway
  container.
- Install suspicious npm / pypi packages in network-isolated containers and
  observe what they actually do — never on the host.
- Run side-by-side comparisons (shootouts) of two implementations / tools
  against the same command matrix.

The harness writes every report under `$MAIN_ROOT/reports/sandbox/<recipe>/`
per the project-wide reports rule, and self-checks for orphan containers at
the end of every run.

## Quick reference

```bash
# Preflight: docker reachable? required images present?
uv run scripts/sandbox/sandbox.py preflight

# Build / pull all aimm-sandbox:* images (one-time, ~3 min on a cold cache).
uv run scripts/sandbox/sandbox.py build-images

# Clone any GitHub repo into a sandbox-only dir (NOT the project tree).
uv run scripts/sandbox/sandbox.py clone octocat/Spoon-Knife
# → /tmp/aimm-sandbox/octocat_Spoon-Knife-<sha>/

# Run an arbitrary command inside an image, with the project mounted RO.
uv run scripts/sandbox/sandbox.py run aimm-sandbox:node-baseline \
   /tmp/aimm-sandbox/octocat_Spoon-Knife-<sha> \
   --cmd 'echo hi && node --version' \
   --network none --time-budget 30

# Side-by-side matrix run: every (tool × command) cell is one container.
uv run scripts/sandbox/sandbox.py shootout \
   scripts/sandbox/recipes/runtime-guard-shootout.yaml

# Single-package inspection: install ONE npm / pypi package in a disposable
# container and capture stdout / network / file writes.
uv run scripts/sandbox/sandbox.py precheck axios@1.7.0 --ecosystem npm
```

## Safety invariants

1. Containers run `--rm --network none` by default; explicit opt-in for
   `--network bridge` (real internet).
2. The project mount is **read-only** (`:ro`); writes go to the container's
   ephemeral overlay or `/out` (also ephemeral).
3. No `--privileged`, no Docker-socket bind, no host PID/IPC namespace, no
   root user inside the container.
4. Every container carries the label `aimm-sandbox=true`; the harness
   `docker ps --filter label=aimm-sandbox=true` before AND after every run
   and refuses to exit cleanly if any orphan is found.
5. All scratch state lives under `/tmp/aimm-sandbox/` (never the project
   tree, never `$HOME`); the harness owns purge.

## Images

| Tag | Purpose | Build context |
|---|---|---|
| `aimm-sandbox:node-baseline` | Node 24 + git/curl/jq, no extras | `dockerfiles/node-baseline.Dockerfile` |
| `aimm-sandbox:python-baseline` | Python 3.12 + uv + git, no extras | `dockerfiles/python-baseline.Dockerfile` |
| `aimm-sandbox:node-safe-chain` | baseline + Aikido Safe Chain wired | `dockerfiles/node-safe-chain.Dockerfile` |
| `aimm-sandbox:node-sfw` | baseline + Socket Firewall (`sfw`) | `dockerfiles/node-sfw.Dockerfile` |
| `aimm-sandbox:mitm` | mitmproxy sidecar for network capture | `dockerfiles/mitm.Dockerfile` |
