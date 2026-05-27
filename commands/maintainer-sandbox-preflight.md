---
description: Verify Docker is reachable and the aimm-sandbox images are built. Exit 0 = ready, 2 = images missing, 1 = docker unreachable.
argument-hint: ""
---

Confirm the host has a reachable Docker daemon and the
`aimm-sandbox:*` images are present. The sandbox harness will fail
fast on `sandbox run` / `sandbox shootout` / `sandbox precheck` if
preflight does not pass.

Loads skill: **maintainer-sandbox** (entry point: `preflight`)

Underlying CLI:

```bash
uv run scripts/sandbox/sandbox.py preflight
```

Exit codes:

| Code | Meaning | Next step |
|---|---|---|
| 0 | Docker reachable + images present | Ready |
| 2 | Docker reachable + images missing | Run `uv run scripts/sandbox/sandbox.py build-images` |
| 1 | Docker unreachable | Start Docker Desktop / OrbStack / Colima |

Required images:

- `aimm-sandbox:node-baseline` — Node 24 + npm + git + tini
- `aimm-sandbox:python-baseline` — Python 3.12 + uv + pip + git + tini
- `aimm-sandbox:node-safe-chain` — node-baseline + @aikidosec/safe-chain (optional)
- `aimm-sandbox:node-sfw` — node-baseline + Socket Firewall `sfw` (optional)
- `aimm-sandbox:mitm` — mitmproxy (optional)

The two `*-baseline` images are mandatory. The other three are
only required if you intend to run the corresponding
`shootout` recipe.

This command is read-only: it inspects the local docker daemon but
does NOT build, pull, or remove anything.
