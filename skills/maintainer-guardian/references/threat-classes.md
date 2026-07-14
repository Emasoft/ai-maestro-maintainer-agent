# Guardian threat classes — T1 through T6

The Guardian skill detects 6 classes of supply-chain threat. Each
class has a detector (read-only), a delta-vs-baseline check, and a
route (what the Guardian does when a delta is positive). T3
additionally carries an absolute baseline-compliance check that fires
independent of any delta (see T3).

## Table of Contents

- [T1 — Workflow drift](#t1--workflow-drift)
- [T2 — Stale SHA pins](#t2--stale-sha-pins)
- [T3 — Branch-rule drift](#t3--branch-rule-drift)
- [T4 — Protected-path activity](#t4--protected-path-activity)
- [T5 — Secret-leak markers](#t5--secret-leak-markers)
- [T6 — Package-manager safety-config drift](#t6--package-manager-safety-config-drift)
- [Routing table](#routing-table)
- [Atomic write pattern](#atomic-write-pattern)

---

## T1 — Workflow drift

**Detection.** Chain the `workflow-scan` skill (read-only). It runs
THREE deterministic engines on `.github/workflows/` and writes a
report under `$MAIN_ROOT/reports/workflow-scan/`:

1. `uvx zizmor` (supply-chain + permission analysis).
2. `actionlint` (YAML / shellcheck-of-`run:`-blocks / glob analysis).
3. The bundled `scripts/sentinel_scan.py` — a faithful Python port
   of the Sentinel scanner (32 deterministic rules). It catches the
   structural classes zizmor does not, e.g. `build-publish-same-job`,
   `credential-window`, `ide-config-injection`,
   `missing-frozen-lockfile`, `dangerous-lifecycle-scripts`,
   `jq-arg-escape-sequences`. Run it in JSON mode:

   ```bash
   uv run --with pyyaml scripts/sentinel_scan.py scan \
     --format json --severity low .
   ```

Parse both into a per-severity finding count `{critical, high,
medium, low}`.

**Baseline shape:**

```json
{
  "t1": {
    "zizmor": {"critical": 0, "high": 0, "medium": 0, "low": 0},
    "actionlint": {"errors": 0},
    "sentinel": {"critical": 0, "high": 0, "medium": 0, "low": 0}
  }
}
```

**Delta.** Any positive delta on `critical` or `high` (from EITHER
engine) is a hit. Medium/low deltas accumulate but do not trigger a
route on their own.

**Route.** If the new finding is mechanically fixable, propose an
auto-fix PR on a new branch `chore/guardian-T1-<ts>`:

- For a Sentinel finding in its 6-rule mechanical set
  (`unpinned-actions`, `shell-injection-expr`,
  `missing-persist-credentials`, `workflow-dispatch-injection`,
  `missing-permissions`, `missing-timeouts`) run
  `uv run --with pyyaml scripts/sentinel_scan.py fix --rule <name> .`
  (use `--dry-run` first to preview the diff).
- Otherwise, if it is in zizmor's safe-fix set, use `workflow-fix-safe`.

Either auto-fix path STILL passes through the `maintainer-approval-gate`
before commit (workflow files are protected paths). If no mechanical
fix applies, file a tracking issue with the rule ID + report link.

---

## T2 — Stale SHA pins

**Detection.** `gh api repos/$REPO/dependabot/alerts --jq '[.[] |
select(.state=="open" and .dependency.package.ecosystem=="actions")]
| length'`. Falls back to checking the latest release SHA for every
SHA-pinned action in `.github/workflows/*.y*ml` if Dependabot is not
enabled.

**Baseline shape:**

```json
{
  "t2": {
    "stale_pins": 0,
    "dependabot_open_prs": 0
  }
}
```

**Delta.** Any new stale pin OR any new open Dependabot PR is a hit.

**Route.** File a tracking issue `chore: stale SHA pin in
<workflow>` with the Dependabot PR link. The issue carries the
`dependencies` + `github-actions` labels Dependabot itself uses, so
the Guardian-filed issue and Dependabot's own PR are linkable.

---

## T3 — Branch-rule drift

T3 runs TWO independent checks, because drift-vs-snapshot ALONE has a
blind spot (D1): a repo that is ALREADY off-baseline at session start
has its wrong state captured as "normal" and is then never flagged. The
absolute check below closes that hole.

- **T3-absolute — baseline compliance (standing).** Compare the
  session-start snapshot against the RATIFIED three-ruleset spec (the
  table below), NOT against a prior snapshot. For each canonical name
  assert: present, `enforcement: active`, the exact rule-type set, and the
  exact bypass shape. A missing ruleset, a wrong rule-type set, a
  stripped/added bypass, a non-`active` enforcement, OR a still-live
  legacy ruleset (`default-branch-*`, `janitor-baseline`,
  `main-hardening`, `main-ci-gate`) is a non-compliance hit. This fires
  on the very FIRST baseline and on every SCAN until the repo complies —
  independent of any delta (same standing-finding semantics as T6 mode
  3). THIS is the check that catches a pre-existing-wrong repo.
- **T3-relative — drift.** Compare the current SHOW against the
  previously-cached `branch-rules.json`. A delta is any change in
  `enforcement`, the rule-type list (`deletion`, `non_fast_forward`,
  `required_linear_history`, `pull_request`, `required_status_checks`,
  `update`), OR `bypass_actors` (stripping the admin bypass from
  pr-and-checks, or adding any bypass to history/tag, is security-relevant
  drift). A baseline ruleset that DISAPPEARS between snapshots is a hit.
  THIS catches a change made DURING the session.

**Detection.** Chain `workflow-protect-branch` SHOW once — its output
feeds both checks. The ratified spec is the absolute reference; keep it
byte-identical with `workflow-protect-branch`:

| name | target | enforcement | rule types | bypass |
|---|---|---|---|---|
| `baseline-history-protect` | branch | active | `deletion, non_fast_forward, required_linear_history` | none |
| `baseline-pr-and-checks` | branch | active | `pull_request, required_status_checks` | RepositoryRole Admin (id 5) |
| `baseline-tag-protect` | tag | active | `deletion, update` | none |

**Baseline shape** (the canonical three-ruleset baseline — see
`workflow-protect-branch`). `baseline_compliance` records the
T3-absolute verdict captured at session start, so a pre-existing-wrong
repo is visible in the snapshot itself, not just in later deltas:

```json
{
  "t3": {
    "baseline-history-protect": {
      "id": 16946501,
      "enforcement": "active",
      "deletion": true,
      "non_fast_forward": true,
      "required_linear_history": true,
      "bypass_actors": 0
    },
    "baseline-pr-and-checks": {
      "id": 17025842,
      "enforcement": "active",
      "pull_request": true,
      "required_checks": ["validate", "workflow-security"],
      "admin_bypass": true
    },
    "baseline-tag-protect": {
      "id": 17118003,
      "enforcement": "active",
      "target": "tag",
      "ref_name": ["refs/tags/v*.*.*"],
      "deletion": true,
      "update": true,
      "bypass_actors": 0
    },
    "baseline_compliance": {
      "compliant": false,
      "deviations": [
        "baseline-tag-protect: missing",
        "default-branch-required-checks: legacy ruleset still live"
      ]
    }
  }
}
```

`baseline_compliance.compliant` is `true` only when all three canonical
rulesets are present with the ratified shape AND no legacy ruleset
remains. The example above shows a pre-existing-wrong repo (the exact
case D1 fixed): tag protection never applied + a legacy checks ruleset
still live. On a compliant repo, `deviations` is `[]`.

**Delta — two kinds.**

1. **T3-absolute (standing).** `baseline_compliance.compliant == false`
   is a hit on EVERY scan until remediated — it does not require a
   change since the last snapshot. This is what surfaces a repo that was
   already off-baseline before the Guardian first looked.
2. **T3-relative (drift).** ANY difference between the current SHOW and
   the previous snapshot is a hit — branch rules don't drift by
   accident; if they changed, someone took action.

**Route.**

- **T3-absolute non-compliance** → alert the authorized user with the
  `deviations` list and recommend `workflow-protect-branch` APPLY (which
  re-applies the ratified pair+tag and sweeps legacy names). Applying the
  ratified baseline as-is is EXEMPT (manager-approval §F), so the fix is
  routine; only a DEVIATION from the baseline would need approval.
- **T3-relative drift** → alert the authorized user via direct message
  (R6 governance edge). Do NOT auto-revert — the user may have made the
  change intentionally. Guardian's job is observability, not policy
  enforcement.

---

## T4 — Protected-path activity

**Detection.** The canonical protected-paths list lives in
`maintainer-approval-gate/references/protected-paths.md`. For each
path, capture `git log --format=%H -1 -- <path>` (latest commit
touching that path).

**Baseline shape:**

```json
{
  "t4": {
    "paths": {
      ".github/workflows/validate.yml": "abc123...",
      "scripts/publish.py": "def456...",
      ".gitignore": "ghi789..."
    }
  }
}
```

**Delta.** Any path whose latest-commit SHA changed between
baseline and scan is a hit.

**Route.** Alert the authorized user with the protected-path
that moved + the commit URL. The agent does NOT block the change
retroactively (the commit already landed); it just surfaces.

For PROSPECTIVE protected-path edits (i.e. ones the agent itself
is about to make as part of fixing an issue), the
`maintainer-approval-gate` skill is the relevant defense — it
catches the edit BEFORE commit, not after.

---

## T5 — Secret-leak markers

**Detection (preferred, fast).** Use the bundled
`scripts/fast_security_scan.py` — a google-re2 RegexSet one-pass
scanner with multiprocessing fan-out. Builds a single DFA from
the catalog and matches every pattern in one pass per file
(O(n) regardless of pattern count). Falls back to Python `re`
for patterns RE2 can't compile (lookaround / backrefs). Typical
plugin-sized scans complete in ~150 ms across all workflows + the
last 48 h of git history.

```bash
uv run --with google-re2 scripts/fast_security_scan.py \
  --recent-commits 48 \
  --severity CRITICAL \
  --format json
```

The catalog ships built-in patterns for AWS / GitHub / GitLab /
Slack / Google / Anthropic / OpenAI / Stripe tokens, PEM private
keys, and GitHub Actions template-injection markers. Extend via
`--catalog catalog.json`.

**Detection (fallback, slow).** When `google-re2` is unavailable,
use shell `grep -nE`:

```bash
git log --all --since="48 hours ago" -p \
  | grep -nE 'AKIA[0-9A-Z]{16}|ghp_[0-9a-zA-Z]{36}|...' \
  || true
```

**Baseline shape:**

```json
{
  "t5": {
    "matches": 0,
    "last_scanned_sha": "abc123..."
  }
}
```

**Delta.** Any non-zero match count is a hit — secrets in commit
history are CRITICAL by definition; baseline is always 0.

**Route.** STOP the patrol cycle, then escalate on BOTH channels:

1. **AMP → MANAGER** (governance escalation, not GitHub-only): send an
   URGENT message to the host MANAGER —
   `amp-send manager-<host> "T5 secret-leak on <repo>" "<body — begins with the self-id line>" --type alert --priority urgent`.
   A live committed secret is a fleet-level incident (rotate + history-purge
   may span repos the maintainer does not own), so the governance layer must
   know immediately, not only the GitHub thread. The message body MUST begin
   with the self-id line (G1.1 extends to AMP bodies): `This is the Claude
   responsible for the ai-maestro-maintainer-agent project.`
2. **GitHub / authorized user**: alert the authorized user with the matching
   commit SHA + the suspected secret kind.

Do NOT echo the secret value back in either message. Do NOT proceed with any
other patrol task until the user (or MANAGER) acknowledges. If `amp-send` is
unavailable (AMP server offline), fall back to the GitHub alert alone and note
the AMP-unreachable condition in it.

---

## T6 — Package-manager safety-config drift

**Why this class exists.** The 2026-05 `art-template` npm compromise
(versions 4.13.{3,4,5,6}, distributing an iOS exploit kit) is the
canonical example of why per-repo package-manager safety knobs MUST
be present *and* MUST stay present. The knobs the maintainer
guarantees on every Node repo it guards:

| Knob | Required value | Defends against |
|---|---|---|
| `minimum-release-age` (pnpm) / `minimumReleaseAge` | `>= 7200` (minutes; ~5 d) | publish-then-delete short attack windows |
| `trust-policy` (pnpm) / `trustPolicy` | `no-downgrade` | install-malicious-then-republish-older-good-version cleanup |
| `block-exotic-subdeps` (pnpm) / `blockExoticSubdeps` | `true` | transitive deps escaping the registry via git/tarball URLs |
| `frozen-lockfile` (pnpm) / `--frozen-lockfile` (CI) | `true` | lockfile drift between local and CI |

Source files in priority order (first hit wins per knob):

1. `package.json` &nbsp;→ &nbsp;`.pnpm` field (camelCase keys).
2. `.npmrc` &nbsp;at repo root (kebab-case keys).
3. `pnpm-workspace.yaml` &nbsp;→ &nbsp;top-level keys.

**Detection (Node repos only — skip if no `package.json`).** Read
each source file, normalise camelCase ↔ kebab-case, and project the
four knobs into a flat dict. The seed template lives at
`workflow-bootstrap/references/templates/npmrc-hardened` so a brand-
new repo bootstrapped by the maintainer already complies.

```bash
# Quick read — JSON-parses package.json, greps the two flat files.
test -f package.json || exit 0
{
  jq -r '.pnpm // {} | to_entries | map("\(.key)=\(.value|tostring)") | .[]' \
      package.json 2>/dev/null
  grep -E '^(minimum-release-age|trust-policy|block-exotic-subdeps|frozen-lockfile)=' \
      .npmrc 2>/dev/null
  yq -r 'with_entries(select(.key|test("^(minimumReleaseAge|trustPolicy|blockExoticSubdeps|frozenLockfile)$"))) | to_entries | map("\(.key)=\(.value)") | .[]' \
      pnpm-workspace.yaml 2>/dev/null
} | awk -F= '{
  # last-set wins per knob (matches pnpm config precedence).
  k=$1; sub(/^[A-Z]/, "", k); gsub(/[A-Z]/, "-&", $1);  # normalise
  s[tolower($1)] = $2
} END { for (k in s) print k "=" s[k] }'
```

**Baseline shape:**

```json
{
  "t6": {
    "is_node_repo": true,
    "minimum-release-age": 7200,
    "trust-policy": "no-downgrade",
    "block-exotic-subdeps": true,
    "frozen-lockfile": true,
    "source_file_shas": {
      "package.json": "ab12cd...",
      ".npmrc": "ef34gh...",
      "pnpm-workspace.yaml": null
    }
  }
}
```

`is_node_repo: false` → the entire T6 detector is a no-op for this
repo (no source file SHAs captured, no delta possible).

**Delta — three failure modes, each a hit.**

1. **Weakening.** Any required knob has been LOWERED, REMOVED, or
   FLIPPED to an unsafe value (e.g. `minimum-release-age` drops
   below `7200`, `trust-policy` removed, `block-exotic-subdeps`
   becomes `false`). The source file's SHA also changed since
   baseline.
2. **Silent strip.** A source file existed at baseline and now
   does not (e.g. someone deleted `.npmrc`) AND the package.json
   `.pnpm` block does not carry the missing knobs.
3. **Missing on a Node repo.** Baseline observed the repo lacked
   one or more knobs entirely; subsequent SCANs accumulate this as
   a standing finding until remediated. (NOT a delta, but emitted
   on every SCAN until the knob is set.)

**Route.**

- Failure mode (1) or (2) → ALERT the authorized user immediately.
  These are *active* removals of supply-chain defences; an agent
  must NEVER apply this kind of change without explicit human
  approval (see also the janitor's global PreToolUse hook that
  refuses min-age bypass flags, tracked at
  `Emasoft/ai-maestro-janitor#TBD`). Refuse to push.
- Failure mode (3) → File a tracking issue labeled `supply-chain`
  with a one-click fix that pastes the relevant block from
  `workflow-bootstrap/references/templates/npmrc-hardened`. Not
  blocking; the agent may continue other work.

---

## Routing table

| Class | Delta | Route |
|---|---|---|
| T1 critical/high | +N | safe-fix PR via workflow-fix-safe OR tracking issue |
| T1 medium/low | +N | accumulate only; weekly digest issue |
| T2 | +N | tracking issue with Dependabot link |
| T3-absolute | non-compliant (standing) | alert + recommend `workflow-protect-branch` APPLY (re-apply ratified baseline — EXEMPT) |
| T3-relative | any change | alert authorized user (R6 direct edge) |
| T4 | any path moved | alert authorized user (post-hoc, observability) |
| T5 | +N | STOP CYCLE + alert (secret in history is critical) |
| T6 weakening / strip | any | alert authorized user; refuse to push |
| T6 missing-on-Node-repo | standing | file tracking issue with template paste |

## Atomic write pattern

Both `guardian-baseline.json` and `guardian-state.json` are written
atomically — same pattern as `branch-rules.json`. State files MUST
live inside the AGENT WORKING DIRECTORY (never under `$HOME`) so
AI Maestro backups and host migration capture them:

```bash
# Resolve the agent working dir:
#   1. $AGENT_WORK_DIR      (authoritative — AI Maestro exports it into the
#      pane env at session creation; the directory-guard hook uses it as the
#      sandbox boundary, so it IS the agent's workdir by definition)
#   2. $CLAUDE_PROJECT_DIR  (Claude Code's own var; plain non-fleet session)
#   3. $PWD                 (last-resort fallback — never rely on it alone;
#      it diverges silently as soon as anything cd's)
AGENT_DIR="${AGENT_WORK_DIR:-${CLAUDE_PROJECT_DIR:-$PWD}}"
STATE_DIR="$AGENT_DIR/.aimaestro/state"
mkdir -p "$STATE_DIR"

TMP="$STATE_DIR/guardian-baseline.json.tmp.$$"
# ...build JSON into $TMP...
mv -f "$TMP" "$STATE_DIR/guardian-baseline.json"
```

`mv -f` is atomic on POSIX filesystems, so a crash mid-scan leaves
the previous baseline intact rather than truncating it.

> **Never** write to `$HOME/.aimaestro/...` or `$HOME/agents/...`.
> Host-global paths are invisible to AI Maestro backups, which
> means after a restore the Guardian starts from a clean baseline
> and re-flags every drift the user already vetted. The same trap
> breaks agent migration between hosts.
