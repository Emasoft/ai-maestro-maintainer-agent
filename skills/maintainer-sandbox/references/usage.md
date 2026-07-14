# maintainer-sandbox — usage reference

The CLI driver is `scripts/sandbox/sandbox.py`. Every subcommand
returns structured data on stdout and human-readable progress on
stderr, so the agent loop can both capture the result programmatically
and stream progress to the user.

## Table of Contents

- [Pick the right entry point](#pick-the-right-entry-point)
- [Images](#images)
- [CLI reference](#cli-reference)
- [Shootout recipe schema](#shootout-recipe-schema)
- [Safety invariants](#safety-invariants)
- [Common workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)

---

## Images

Built from `scripts/sandbox/dockerfiles/*.Dockerfile` by `build-images`. Every
one runs as a non-root user on a pinned base — enforced by
`tests/test_dockerfile_hardening.py`, not merely intended.

| Image | For |
|---|---|
| `aimm-sandbox:node-baseline` | running an untrusted npm install / test in a clean Node container |
| `aimm-sandbox:node-sfw`, `:node-safe-chain` | the same, under a specific supply-chain defence, for shootouts |
| `aimm-sandbox:python-baseline` | the same, for pypi |
| `aimm-sandbox:mitm` | optional mitmproxy sidecar — records outbound traffic when a recipe sets `capture_network: true` |
| `aimm-sandbox:agent-cli` | a dev container carrying the **Claude Code CLI** plus a working toolchain (git, python, node, build tools, ripgrep, jq) |

**`agent-cli` is the one image that is NOT for untrusted code.** The others exist
to run hostile packages with `--network none`; an agent CLI has to reach the API,
so it needs `--network bridge` and a key at run time:

```bash
uv run scripts/sandbox/sandbox.py run aimm-sandbox:agent-cli "$REPO" \
  --cmd 'claude -p "audit this repo"' --network bridge --allow-writes
```

What it isolates is the **filesystem and the toolchain** — the repo's postinstall
scripts, its dependencies, and whatever the agent does to them never touch the
host. It does not isolate the network. Pin the CLI at build time when
reproducibility matters:
`docker build --build-arg CLAUDE_CODE_VERSION=2.1.191 …`.

**No image here fetches anything over the network at build time** — apt, npm, and
pip only. That is why `gh` is absent from `agent-cli`: it has no Debian package,
and adding its apt repo would make this the one image that reaches out mid-build.
`python-baseline` learned the same lesson (its curl-based `uv` installer kept
breaking when the upstream layout drifted; it uses `pip install uv` now). A
derived image can add whatever a specific task needs.

---

## Pick the right entry point

| Question | Entry point |
|---|---|
| "Does this docker image exist? Is Docker even running?" | `preflight` |
| "Rebuild / update all sandbox images." | `build-images` |
| "I need a copy of a GitHub repo somewhere safe to poke at." | `clone` |
| "Run this arbitrary shell snippet in a clean container." | `run` |
| "Run the same workload under N tools, give me a side-by-side." | `shootout` |
| "Just tell me what THIS one package does when installed." | `precheck` |

## CLI reference

```text
uv run scripts/sandbox/sandbox.py preflight

uv run scripts/sandbox/sandbox.py build-images [--variant <name>]

uv run scripts/sandbox/sandbox.py clone <owner/repo> \
    [--ref <sha|tag|branch>] [--depth N] [--dest <dir>]

uv run scripts/sandbox/sandbox.py run <image> <project-dir> \
    --cmd '<bash command>' \
    [--network none|bridge] \
    [--time-budget <seconds>] \
    [--allow-writes]

uv run scripts/sandbox/sandbox.py shootout <recipe.yaml>

uv run scripts/sandbox/sandbox.py precheck <pkg-spec> \
    [--ecosystem npm|pypi] [--time-budget <seconds>]
```

Exit codes:

- `0` — success (or every cell in a shootout succeeded).
- `1` — operational failure (bad input, docker error, lint).
- `2` — preflight detected docker OK but images missing.
- `124` — a `run` cell timed out (Linux `timeout`-style code).

## Shootout recipe schema

```yaml
# scripts/sandbox/recipes/my-recipe.yaml
name: my-recipe                  # report dir / heading slug

project:                         # how to materialise /work
  type: scratch                  # or 'clone'
  files:                         # for type=scratch
    package.json: |
      {"name": "x", "version": "0.0.0"}
  # for type=clone:
  # repo: owner/repo
  # ref: <sha|tag|branch>        # optional

network: bridge                  # or 'none' (default)
time_budget: 240                 # seconds per cell

matrix:                          # rows = tool variants
  - tool: baseline
    image: aimm-sandbox:node-baseline
  - tool: safe-chain
    image: aimm-sandbox:node-safe-chain

commands:                        # cols = workload steps
  - name: install-axios
    cmd: npm install --no-audit axios@1.7.7

  - name: install-malicious
    cmd: npm install --no-audit event-stream@3.3.6
```

Every (matrix row × command) pair becomes one container invocation.
The result is rendered to a markdown table under
`reports/sandbox/<recipe-name>/<ts>-shootout.md`, with per-cell logs in
the same directory.

## Safety invariants

These are enforced in `_do_run` (read `scripts/sandbox/sandbox.py` for
the live truth):

| Invariant | Mechanism |
|---|---|
| Throwaway container | `docker run --rm` always |
| No host pollution | `--read-only` rootfs + `--tmpfs=/tmp:rw,size=512m` |
| No host net by default | `--network none`; bridge is opt-in per call |
| No privileged | `--cap-drop=ALL --security-opt=no-new-privileges:true` |
| Project mount read-only | `-v <dir>:/work:ro` unless `--allow-writes` |
| Reapable PID-1 | `tini` entrypoint in every image |
| Audit trail | `--label aimm-sandbox=true` + per-run session label |
| Self-check | orphan reap by session label in a `try/finally` |

## Common workflows

### 1. Verify a runtime-guard tool before recommending

```bash
uv run scripts/sandbox/sandbox.py preflight
uv run scripts/sandbox/sandbox.py build-images
uv run scripts/sandbox/sandbox.py shootout \
    scripts/sandbox/recipes/runtime-guard-shootout.yaml
# → reports/sandbox/runtime-guard-shootout/<ts>-shootout.md
```

### 2. Inspect one suspicious npm package

```bash
uv run scripts/sandbox/sandbox.py precheck art-template@4.13.6 --ecosystem npm
# → reports/sandbox/precheck/<ts>-npm-art-template@4.13.6.json
# tail the .log file in the report for the install output.
```

### 3. Reproduce an external repo's CI failure

```bash
DEST=$(uv run scripts/sandbox/sandbox.py clone someuser/somerepo --ref <sha>)
uv run scripts/sandbox/sandbox.py run aimm-sandbox:node-baseline "$DEST" \
    --cmd 'npm ci && npm test' \
    --network bridge --time-budget 900
```

### 4. Test a hardening template against a real install

```bash
# Bootstrap a scratch project that uses the workflow-bootstrap
# npmrc-hardened template, then attempt to install a too-fresh package.
uv run scripts/sandbox/sandbox.py shootout \
    scripts/sandbox/recipes/npmrc-min-release-age-test.yaml
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `docker server not reachable` | Start Docker Desktop / OrbStack; retry preflight. |
| `useradd: UID 1000 is not unique` while building node-* images | Means the base image already has a UID-1000 user. Reuse it (`node`) instead of creating one. (Already the case in shipped Dockerfiles; only matters if you fork.) |
| `mv: cannot stat '/root/.local/bin/uv'` while building python-baseline | The curl installer's layout drifted; ship Dockerfile uses `pip install uv` instead, which is layout-stable. |
| Timeout (exit 124) on `npm install` | Pass `--time-budget 900` (or higher); registry latency from a fresh image's first run can spike. |
| Orphan container warning at exit | Inspect: `docker ps --filter label=aimm-sandbox=true -a`. Kill: `docker rm -f $(docker ps -aq --filter label=aimm-sandbox=true)`. |
| `Network bridge` blocked by corp firewall | Configure the docker daemon's DNS upstream (`--dns 8.8.8.8`), or use OrbStack's settings UI. |
