---
description: Install a suspicious npm or pypi package inside a hardened Docker container, observe what it does, write a JSON report. Default network=none (uses --network bridge only when explicitly asked).
argument-hint: "<package-spec> --ecosystem npm|pypi [--time-budget <seconds>]"
---

Install one specific package inside a hardened sandbox container,
observe what it does (network egress attempts, file writes outside
the project mount, shell modifications), and write a JSON report
under `$MAIN_ROOT/reports/sandbox/precheck/`.

Loads skill: **maintainer-sandbox** (entry point: `precheck`)

Underlying CLI:

```bash
uv run scripts/sandbox/sandbox.py precheck <pkg-spec> \
  --ecosystem npm|pypi \
  [--time-budget <seconds>]
```

The container runs with:

- `--cap-drop=ALL --security-opt=no-new-privileges:true`
- `--read-only` rootfs + `--tmpfs=/tmp:rw,size=512m`
- Project mount `:ro` (the install writes only to /tmp inside the
  container)
- Default `--network bridge` for this command (the install needs
  registry access)
- Per-session label `aimm-sandbox-session=<uuid>` for orphan reap

The report contains:

- Exit code of the install command
- stdout + stderr bytes
- Wall-clock time
- Whether the install attempted any unusual network calls (parsed
  from the container's network logs)
- Whether the install ran any `preinstall`/`postinstall` (npm) or
  `setup.py`/`pyproject.toml [build-system].build-backend`
  (pypi) lifecycle hooks

Use this **before** recommending a package to a user or before
adding a dep to a `package.json` / `pyproject.toml` on a
maintained repo. The container is reaped on exit.

Examples:

```bash
/maintainer-sandbox-precheck art-template@4.13.6 --ecosystem npm
/maintainer-sandbox-precheck event-stream@3.3.6 --ecosystem npm
/maintainer-sandbox-precheck requests==2.31.0 --ecosystem pypi
```

Note: a package being clean in precheck does NOT prove it is
benign. Precheck observes ONE install at ONE time on ONE registry
state — supply-chain attacks can land between runs. Use it as
defense in depth, not as a binary "safe / unsafe" verdict.
