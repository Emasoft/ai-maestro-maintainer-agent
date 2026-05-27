# Untrusted-PR Sandbox Protocol

Recipe for the Case C precheck: a PR whose author is NOT
`$AUTHORIZED_USER` MUST be cloned and exercised inside a Docker
container before any human review comment is posted. The host
never sees the PR code.

## Table of Contents

- [Why a sandbox](#why-a-sandbox)
- [Clone the PR head into a sandbox](#clone-the-pr-head-into-a-sandbox)
- [Run tests under controlled network](#run-tests-under-controlled-network)
- [Capture observations](#capture-observations)
- [Post the observation comment](#post-the-observation-comment)
- [Failure modes](#failure-modes)

---

## Why a sandbox

A PR from an unknown contributor can contain:

- A malicious `preinstall` / `postinstall` / `prepare` script in
  `package.json` that runs on `npm ci`.
- A malicious `[build-system]` hook in `pyproject.toml` that runs
  on `pip install -e .` or `uv pip install`.
- A test file that calls out to attacker infrastructure when
  imported.
- A build step (`Makefile`, `tox.ini`, `noxfile.py`,
  `pre-commit-hooks.yaml`) that runs arbitrary code.

None of those should ever execute on the host. The
`maintainer-sandbox` harness runs them in a labelled container
with no project mount, default `--network none`, and a strict
time budget. The PR head is fetched into the container via `gh`
inside the container — the host's `git` never touches the PR.

## Clone the PR head into a sandbox

```bash
# Pre-flight — confirm Docker is reachable.
if ! uv run scripts/sandbox/sandbox.py preflight 2>/dev/null; then
  # Sandbox unreachable — fall through to the no-precheck path.
  SANDBOX_AVAILABLE=0
else
  SANDBOX_AVAILABLE=1
fi

if [ "$SANDBOX_AVAILABLE" = "1" ]; then
  # Resolve the head repo from PR metadata.
  HEAD_FULL="$HEAD_OWNER/$HEAD_REPO"

  # Clone the fork's PR head into /tmp/aimm-sandbox/<sid>/...
  CLONE_PATH=$(uv run scripts/sandbox/sandbox.py clone \
    "$HEAD_FULL" --ref "$HEAD_SHA")
fi
```

Notes:

- `sandbox.py clone` writes into `/tmp/aimm-sandbox/<session-uuid>/`.
  The host workspace is untouched.
- We pass `--ref "$HEAD_SHA"` (not a branch name) so a force-push
  between triage and review cannot swap the contents under us.
- If `sandbox preflight` exits 2, the agent does NOT install
  Docker / pull images on its own — it returns
  `sandbox-unavailable` and the reviewer gets the gap noted in
  the comment (see [Failure modes](#failure-modes)).

## Run tests under controlled network

Pick the right image + command based on the PR's ecosystem.
Probe a few well-known marker files:

```bash
# Ecosystem detection
if   [ -f "$CLONE_PATH/package.json" ]; then
  IMAGE="aimm-sandbox:node-baseline"
  CMD='npm ci --ignore-scripts && npm test --if-present'
elif [ -f "$CLONE_PATH/pyproject.toml" ] || [ -f "$CLONE_PATH/setup.py" ]; then
  IMAGE="aimm-sandbox:python-baseline"
  CMD='uv sync --frozen 2>/dev/null || uv pip install -e . ; uv run pytest -q || true'
elif [ -f "$CLONE_PATH/go.mod" ]; then
  IMAGE="aimm-sandbox:go-baseline"
  CMD='go test ./...'
elif [ -f "$CLONE_PATH/Cargo.toml" ]; then
  IMAGE="aimm-sandbox:rust-baseline"
  CMD='cargo test'
else
  IMAGE="aimm-sandbox:generic-baseline"
  CMD='echo "no recognised build manifest" >&2; exit 0'
fi

# Network policy:
# - Install step needs the registry → --network bridge
# - Once installed, tests should NOT need the network → tighten
#   in two phases when feasible.
# For triage we accept --network bridge for the whole run + a
# 600 s time budget. Tighter policy is the reviewer's concern.
SANDBOX_REPORT=$(uv run scripts/sandbox/sandbox.py run \
  "$IMAGE" "$CLONE_PATH" \
  --cmd "$CMD" \
  --network bridge \
  --time-budget 600 \
  --output-format json)
```

**npm `--ignore-scripts` is intentional.** Lifecycle scripts are
exactly the attack surface this precheck is meant to flag — we
want the tests to run WITHOUT executing them. The `pr-review`
skill flags any new lifecycle scripts in its own checklist.

**`uv run pytest … || true`** is intentional too. The precheck
records the exit code in the report — it does NOT abort on a
failing test suite, because a PR's tests CAN legitimately fail
against `main` (that's why the PR exists). The reviewer reads
the exit code from the comment.

## Capture observations

The sandbox harness emits a JSON record at `$SANDBOX_REPORT`
with the shape:

```json
{
  "image": "aimm-sandbox:node-baseline",
  "cmd": "npm ci --ignore-scripts && npm test --if-present",
  "exit_code": 0,
  "wall_clock_ms": 47210,
  "stdout_bytes": 12480,
  "stderr_bytes": 320,
  "log_path": "/.../reports/sandbox/precheck/<ts>-npm.log",
  "timed_out": false
}
```

The skill loads this JSON, extracts the four fields below, and
threads them into the observation comment template.

```bash
EXIT_CODE=$(jq -r .exit_code  "$SANDBOX_REPORT")
WALL_MS=$(  jq -r .wall_clock_ms "$SANDBOX_REPORT")
LOG_PATH=$( jq -r .log_path "$SANDBOX_REPORT")
TIMED_OUT=$(jq -r .timed_out "$SANDBOX_REPORT")
```

The full stdout/stderr log lives at `$LOG_PATH` — it is NOT
copied into the comment. The reviewer can fetch it on demand
from the host (it's in the gitignored `reports/` tree).

## Post the observation comment

The comment is fixed-template — every interpolation goes through
a heredoc so PR content never reaches a shell expansion path.

```bash
gh pr comment "$PR" --repo "$REPO" --body-file - <<COMMENT
**Automated precheck — untrusted PR** (case C)

This PR is from an account that is NOT the authorized maintainer
of this repository. I ran a containerised precheck before any
human review:

| Field | Value |
|---|---|
| Author | @${AUTHOR} |
| Head repo | ${HEAD_OWNER}/${HEAD_REPO} |
| Head SHA | \`${HEAD_SHA}\` |
| Sandbox image | \`${IMAGE}\` |
| Command | \`${CMD}\` |
| Exit code | ${EXIT_CODE} |
| Wall clock | ${WALL_MS} ms |
| Timed out | ${TIMED_OUT} |
| Protected paths touched | ${PROTECTED_PATHS_BULLETS:-(none)} |

The precheck ran with \`--network bridge\` and \`npm --ignore-scripts\`
(or the ecosystem equivalent). Lifecycle scripts in
\`package.json\` / \`pyproject.toml\` were NOT executed. The PR's
test suite outcome is reflected in the exit code above.

**This is an AI-assisted observation, not an approval.** The
authorized maintainer (@${AUTHORIZED_USER}) must review the diff
manually before merge — see the companion review comment from
\`maintainer-pr-review\`.

Full sandbox log: \`${LOG_PATH}\` (gitignored,
72 h retention).
COMMENT
```

The `PROTECTED_PATHS_BULLETS` variable is populated by the
caller from the cross-reference step in
[classification-paths.md](classification-paths.md). Format as a
markdown bullet list (`- \`path\``) so the table cell renders
cleanly.

## Failure modes

| Failure | Behaviour |
|---|---|
| `sandbox preflight` exits 2 (Docker unreachable) | Skip precheck, post a degraded observation comment noting "sandbox unavailable — manual reviewer must run tests themselves", set `sandbox_report: null` in the disposition |
| `sandbox run` exits 124 (timed out) | Include `timed_out: true` in the comment; reviewer treats as suspicious |
| `sandbox clone` fails (private fork, deleted ref) | Return `human-review-required` with reason `unfetchable-diff`; comment includes the failure mode |
| Container leaks past `sandbox run` cleanup | The harness already prints a `WARNING: orphan container` to stderr; the calling agent must surface that as a triage error |
| `gh pr comment` fails | Stop, surface to caller; do NOT retry inside the same triage invocation (rate-limit hint applies) |

The precheck NEVER:

- Pushes anything anywhere.
- Comments on issues other than the PR.
- Closes or merges the PR.
- Approves the PR via `gh pr review --approve`.

It only OBSERVES and REPORTS.
