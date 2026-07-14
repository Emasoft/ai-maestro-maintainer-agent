---
description: |
  Use when testing something without touching the host: third-party
  tools before recommending, suspicious npm/pypi packages before
  installing, external-repo bug repros, or side-by-side (shootout)
  tool comparisons. Drives a Docker harness under scripts/sandbox/;
  default is no network, read-only project mount, orphan reap on
  exit. Trigger with "sandbox this", "run in a sandbox", "test this
  package without installing", "shootout these two tools",
  "reproduce in a clean container", "verify before recommending".
---

# maintainer-sandbox — Docker-isolated runner for the maintainer agent

## Overview

The maintainer must verify things before recommending them: that a
third-party install does not steal the host shell, that a published npm
package does what its name implies, that a user-reported bug reproduces.
Doing any of that on the host is unsafe — this skill drives a small
Docker harness (`scripts/sandbox/sandbox.py`) that runs the work in a
disposable, network-restricted container and reports back. All scratch
state lives under `/tmp/aimm-sandbox/`; the harness owns purge.

## Prerequisites

- `docker --version` and `docker version --format '{{.Server.Version}}'`
  succeed (Docker Desktop / OrbStack / Colima).
- Disk: ~3 GiB free on `/tmp` (base images + scratch projects).
- `uv` on PATH (sandbox.py is a PEP 723 inline-deps script).

## Instructions

1. **Preflight** — confirm Docker reachable + required images present:

   ```bash
   uv run scripts/sandbox/sandbox.py preflight
   ```

   Exit `0` = ready. Exit `2` = images missing → run:

   ```bash
   uv run scripts/sandbox/sandbox.py build-images
   ```

2. **Pick the right entry point** — see
   [usage](references/usage.md): [Pick the right entry point](references/usage.md#pick-the-right-entry-point)
   for the picker:

   | Need | Use |
   |---|---|
   | "Inspect a single npm/pypi package" | `precheck <pkg> --ecosystem npm` |
   | "Reproduce a bug from external repo" | `clone` → `run` |
   | "Compare 2+ tools on the same workload" | `shootout <recipe.yaml>` |
   | "Run any shell command in isolation" | `run <image> <dir> --cmd '…'` |

3. **Run** — the harness writes a JSON / Markdown report to
   `$MAIN_ROOT/reports/sandbox/<component>/`. Default network is `none`;
   pass `--network bridge` only when the workload genuinely needs the
   internet (package install, git fetch).

4. **Self-check** — every container carries
   `--label aimm-sandbox=true --label aimm-sandbox-session=<uuid>`. The
   harness reaps by session label on exit; if any orphan survives, it
   prints a `WARNING:` block to stderr. Do NOT exit the patrol cycle on
   a sandbox finding without also confirming this line is absent.

5. **Cleanup** — `/tmp/aimm-sandbox/` is purged by the
   `ai-maestro-janitor` plugin's existing screenshot/trashcan rotation
   (it covers `/tmp/aimm-*`). No manual cleanup needed.

Full CLI surface, recipe schema, safety invariants, and example
workflows in [usage](references/usage.md):
[Pick the right entry point](references/usage.md#pick-the-right-entry-point),
[CLI reference](references/usage.md#cli-reference),
[Shootout recipe schema](references/usage.md#shootout-recipe-schema),
[Safety invariants](references/usage.md#safety-invariants),
[Common workflows](references/usage.md#common-workflows),
[Troubleshooting](references/usage.md#troubleshooting).

## Output

- **preflight**: stderr summary + exit code.
- **build-images**: per-image OK/FAILED on stderr.
- **clone**: prints the clone destination path on stdout.
- **run**: JSON `{image, cmd, exit_code, wall_clock_ms, stdout_bytes,
  stderr_bytes, log_path, timed_out}` on stdout.
- **shootout**: prints the report path on stdout; markdown table at that
  path under `reports/sandbox/<recipe>/`.
- **precheck**: prints the JSON report path on stdout.

## Error Handling

| Error | Action |
|-------|--------|
| `docker server not reachable` | Stop, alert user (Docker daemon not up) |
| Image missing during a run | Run `build-images --variant <name>`, retry |
| Network=none but command needs registry | Re-invoke with `--network bridge`; record in report why |
| Container timed out (exit 124) | Increase `--time-budget`; flag in report |
| Orphan container at exit | Stop, alert user — manual `docker rm -f` may be needed |

## Examples

```
maintainer-guardian T6 wants to verify the npmrc-hardened template
actually blocks a malicious install →
  sandbox shootout runtime-guard-shootout.yaml
  → reports/sandbox/runtime-guard-shootout/<ts>-shootout.md
```

```
Triage receives "npm i foo-bar@1.2.3 broke my build" issue →
  sandbox precheck foo-bar@1.2.3 --ecosystem npm
  → reports/sandbox/precheck/<ts>-npm-foo-bar.json
```

```
Reproduce an external project's CI failure →
  sandbox clone someuser/somerepo --ref <sha>
  sandbox run aimm-sandbox:node-baseline <path> --cmd 'npm test' --network bridge --time-budget 600
```

## Scope

ONLY runs Docker containers labelled `aimm-sandbox=true`. Does NOT
modify host package managers, host shell configs, or anything outside
`/tmp/aimm-sandbox/` + `reports/sandbox/`. To stop a runaway: kill the
docker process and run `docker ps --filter label=aimm-sandbox=true -aq |
xargs -r docker rm -f`.

## Resources

- [usage](references/usage.md) — CLI + recipe + safety details:
  - [Pick the right entry point](references/usage.md#pick-the-right-entry-point)
  - [Images](references/usage.md#images)
  - [CLI reference](references/usage.md#cli-reference)
  - [Shootout recipe schema](references/usage.md#shootout-recipe-schema)
  - [Safety invariants](references/usage.md#safety-invariants)
  - [Common workflows](references/usage.md#common-workflows)
  - [Troubleshooting](references/usage.md#troubleshooting)
- Source: `scripts/sandbox/sandbox.py`,
  `scripts/sandbox/dockerfiles/*.Dockerfile`,
  `scripts/sandbox/recipes/*.yaml`.
- Companion skills: `maintainer-guardian` (T6 uses this harness to
  verify package-manager safety knobs survive a real install),
  `maintainer-triage` (use `precheck` on suspicious packages from bug
  reports).
