# Full step-by-step — `workflow-bootstrap`

## Table of Contents

- [Language detection table](#language-detection-table)
- [Template inventory](#template-inventory)
- [Step-by-step commands](#step-by-step-commands)
- [Post-merge ruleset apply](#post-merge-ruleset-apply)
- [Per-language walk-throughs](#per-language-walk-throughs)

## Language detection table

| Repo file fingerprint | Detected language | Template used |
|---|---|---|
| `pyproject.toml` present | py3 | `templates/python.yml` |
| `package.json` present (and no py3 source) | nodejs | `templates/node.yml` |
| `Cargo.toml` present | rust-lang | `templates/rust.yml` |
| `go.mod` present | golang | `templates/go.yml` |
| None of the above | generic | `templates/generic.yml` |

When two markers are present (e.g. a Python project that also
ships a small Node-based frontend), the skill picks the language
of the deepest-named source directory and warns. If unsure, fall
back to `generic.yml` + a comment in the rendered workflow.

## Template inventory

Every template ships with these hardening defaults baked in:

- Top-level `permissions: contents: read`.
- Top-level `concurrency: { group: ..., cancel-in-progress: false }`.
- Per-job `timeout-minutes: 15` (overridable per job).
- `actions/checkout@vN` with `persist-credentials: false`.
- `actions/setup-<lang>@vN` with `enable-cache: false`.
- No `${{ github.event.* }}` interpolation in `run:` blocks —
  every shell value flows through env vars.
- A sibling **workflow-security** job that runs `uvx zizmor
  --format=sarif`, uploads SARIF, then re-runs zizmor in text
  mode as a fail-on-findings step.

Files in this directory:

| Path | Purpose |
|---|---|
| `templates/python.yml` | py3 CI (ruff + mypy + pytest + uv-based) |
| `templates/node.yml` | nodejs CI (`npm ci && npm test`) |
| `templates/rust.yml` | rust-lang CI (`cargo fmt --check && cargo clippy && cargo test`) |
| `templates/go.yml` | golang CI (`go vet && go test`) |
| `templates/generic.yml` | Language-agnostic baseline + manual customization stub |
| `templates/zizmor-job.yml` | The `workflow-security` job (appended to every CI workflow) |
| `templates/dependabot.yml` | Weekly `github-actions` Dependabot config (always seeded) |
| `templates/npmrc-hardened` | `.npmrc` with 24h quarantine + exotic-subdep block (nodejs only) |
| `templates/ruleset-no-force-no-delete.json` | History-protect ruleset (`non_fast_forward` + `deletion`, no bypass) — consumed by `workflow-protect-branch` post-merge |
| `templates/ruleset-required-checks.json` | Required-checks ruleset (strict, admin RepositoryRole bypass) — consumed by `workflow-protect-branch` post-merge |

## Step-by-step commands

```bash
# Step 1 — refuse if any existing workflow file
if compgen -G ".github/workflows/*.y*ml" > /dev/null; then
  echo "REFUSED: .github/workflows/ already contains files." >&2
  echo "  Use workflow-fix-safe + workflow-pin-actions instead." >&2
  exit 64
fi

# Step 2 — detect language
LANG=generic
[ -f pyproject.toml ] && LANG=python
[ -f Cargo.toml ]     && LANG=rust
[ -f go.mod ]         && LANG=go
[ -f package.json ] && [ ! -f pyproject.toml ] && LANG=node

# Step 3-4 — write workflows
SKILL_REFS="$(git worktree list | head -n1 | awk '{print $1}')/skills/workflow-bootstrap/references/templates"
mkdir -p .github/workflows
cp "$SKILL_REFS/$LANG.yml"        .github/workflows/ci.yml
cp "$SKILL_REFS/zizmor-job.yml"   .github/workflows/security.yml

# Step 5 — seed supply-chain config + stash the ruleset spec.
#
# dependabot.yml is ALWAYS seeded — it tracks the github-actions
# ecosystem so SHA-pinned actions don't go silently stale.
# .npmrc is seeded only on Node repos and adds the 24h package
# quarantine + exotic-subdep block from the Atai-Barkai playbook.
cp "$SKILL_REFS/dependabot.yml" .github/dependabot.yml
if [ "$LANG" = "node" ]; then
  cp "$SKILL_REFS/npmrc-hardened" .npmrc
fi

# Ruleset specs are stashed to tmpfiles (NOT committed) —
# workflow-protect-branch picks them up post-merge. TWO rulesets:
# a no-bypass history-protect ruleset and an admin-bypass
# required-checks ruleset (see workflow-protect-branch for why the
# split is required on direct-push repos).
RULESET_HIST_TMP=$(mktemp -t ruleset-hist.XXXXXX.json)
RULESET_CHECKS_TMP=$(mktemp -t ruleset-checks.XXXXXX.json)
cp "$SKILL_REFS/ruleset-no-force-no-delete.json" "$RULESET_HIST_TMP"
cp "$SKILL_REFS/ruleset-required-checks.json"    "$RULESET_CHECKS_TMP"
echo "rulesets stashed at: $RULESET_HIST_TMP , $RULESET_CHECKS_TMP"

# Step 6 — feature branch
git checkout -b chore/bootstrap-ci

# Step 7 — SHA-pin every uses: ref
# Chain the workflow-pin-actions skill here.

# Step 8 — verify zizmor + actionlint clean
# Chain the workflow-scan skill here.

# Step 9 — commit by name (include the supply-chain seeds)
git add .github/workflows/ci.yml .github/workflows/security.yml \
        .github/dependabot.yml
if [ -f .npmrc ]; then
  git add .npmrc
fi
git commit -m "chore: bootstrap secure CI baseline (zizmor-clean)"

# Step 10 — print follow-up
cat <<EOF
ok: bootstrap branch chore/bootstrap-ci is ready.
  1. Open the PR: gh pr create --base main --head chore/bootstrap-ci
  2. After merge, apply BOTH rulesets (or just invoke the
     workflow-protect-branch skill, which does this idempotently):
     gh api -X POST "repos/\$REPO/rulesets" --input $RULESET_HIST_TMP
     gh api -X POST "repos/\$REPO/rulesets" --input $RULESET_CHECKS_TMP
EOF
```

## Post-merge ruleset apply

Two rulesets ship as templates, not one — see
`workflow-protect-branch` for the full rationale (a single combined
ruleset with an admin bypass would also let admin force-push/delete,
because `bypass_actors` applies to the whole ruleset). The
`templates/ruleset-required-checks.json` spec requires both `ci` and
`workflow-security` status checks. `workflow-protect-branch`
auto-detects job names from local workflows, so by the time the PR
has merged and the bootstrap commit is on `main`, running
`workflow-protect-branch` will pick up exactly those job names and
POST both rulesets to GitHub. Prefer invoking the skill over the raw
`gh api` calls above — the skill is idempotent and verifies the
bypass shapes.

## Per-language walk-throughs

### Python

```
User: "set up workflows for this new Python repo"
→ pyproject.toml present → python template
→ ci.yml: ruff + mypy + pytest via uv
→ security.yml: workflow-security job
→ pin-actions → SHA-pin checkout / setup-python / setup-uv / upload-artifact
→ scan → 0 findings
→ commit chore/bootstrap-ci
```

### Node

```
→ package.json present, no pyproject.toml → node template
→ ci.yml: setup-node + npm ci + npm test
```

### Rust

```
→ Cargo.toml present → rust template
→ ci.yml: setup-rust + cargo fmt --check + cargo clippy + cargo test
```

### Go

```
→ go.mod present → go template
→ ci.yml: setup-go + go vet + go test
```

### Refusal on existing workflows

```
→ .github/workflows/release.yml exists
→ REFUSE; recommend: workflow-fix-safe + workflow-pin-actions
→ exit 64
```
