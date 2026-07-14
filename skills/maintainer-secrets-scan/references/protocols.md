# Per-tool invocation, JSON schema, and severity mapping

Source-of-truth for how `maintainer-secrets-scan` shells out to
the three supported scanners. The skill orchestrates; this
document records the exact invocation each scanner expects, the
output shape we normalise to, and the severity translation table.

## Table of Contents

- [Tool detection chain](#tool-detection-chain)
- [trufflehog invocation](#trufflehog-invocation)
- [gitleaks invocation](#gitleaks-invocation)
- [fast_security_scan.py invocation](#fast_security_scanpy-invocation)
- [Severity mapping](#severity-mapping)
- [Output schema](#output-schema)
- [Audit-mode output](#audit-mode-output)

---

## Tool detection chain

The skill always uses **exactly one** scanner per scan invocation
— the highest-ranked one available. The chain:

1. **trufflehog** — most authoritative; verifies live credentials
   via the issuing service when `--only-verified` is set. Slow on
   first run (model warm-up) but the only tool that distinguishes
   "looks like a secret" from "is a working secret".
2. **gitleaks** — fast, regex-based; large built-in pattern set
   focused on dev-time credentials. No live-verification step.
3. **bundled `scripts/fast_security_scan.py`** — always available;
   smaller pattern set than gitleaks but covers the headline
   token families (AWS, GitHub, GitLab, Slack, Anthropic, OpenAI,
   Stripe, PEM keys).

Detection probe:

```bash
detect_tool() {
  if command -v trufflehog >/dev/null 2>&1; then
    echo "trufflehog"; return 0
  fi
  if command -v gitleaks >/dev/null 2>&1; then
    echo "gitleaks"; return 0
  fi
  # Bundled fallback — the script lives next to this skill's plugin.
  if [ -f "$AGENT_DIR/scripts/fast_security_scan.py" ]; then
    echo "bundled"; return 0
  fi
  return 2   # plugin packaging bug
}
```

`$AGENT_DIR` resolves to the maintainer plugin's working dir —
see [Atomic write pattern](../../maintainer-guardian/references/threat-classes.md#atomic-write-pattern)
for the resolution recipe (`$AGENT_WORK_DIR` →
`$CLAUDE_PROJECT_DIR` → `$PWD`).

## trufflehog invocation

```bash
trufflehog \
  --json \
  --only-verified \
  --since-commit=HEAD~50 \
  filesystem "$REPO_PATH" \
  > "$RAW_JSON"
```

Each line of `$RAW_JSON` is one JSON object. Key fields:

| Field | Meaning |
|---|---|
| `DetectorName` | Token family (e.g. `Github`, `AWS`, `Slack`) |
| `Raw` | The raw matched string (DO NOT echo back in reports) |
| `RawV2` | Optional normalised form |
| `SourceMetadata.Data.Filesystem.file` | File path on disk |
| `SourceMetadata.Data.Filesystem.line` | Line number |
| `Verified` | `true` if the issuing service confirmed the key works |

Drop `--only-verified` if the scan should include
suspected-but-unverified secrets too (typical for the
`pre-publish` mode — better to block on a false positive than
let an unverified-but-real key ship).

Git history scan (separate invocation):

```bash
trufflehog \
  --json \
  git \
  --since-commit=HEAD~50 \
  "file://$REPO_PATH" \
  >> "$RAW_JSON"
```

## gitleaks invocation

```bash
gitleaks \
  detect \
  --source="$REPO_PATH" \
  --report-format=json \
  --report-path="$RAW_JSON" \
  --log-opts="-n 50" \
  --exit-code=0
```

`--exit-code=0` is important: gitleaks defaults to exit 1 on any
finding, but the skill wants the JSON file produced regardless
and decides block/no-block based on severity buckets, not on the
tool's exit code.

Output JSON is a top-level array. Key fields per entry:

| Field | Meaning |
|---|---|
| `RuleID` | Internal rule (e.g. `aws-access-token`) |
| `Description` | Human label |
| `Secret` | Matched body (DO NOT echo) |
| `File` | Path relative to `--source` |
| `StartLine` | Line number |
| `Commit` | Commit SHA (only set for history hits) |
| `Date` | Commit date (history hits only) |

## fast_security_scan.py invocation

```bash
uv run --with google-re2 "$AGENT_DIR/scripts/fast_security_scan.py" \
  --recent-commits 1200 \
  --severity LOW \
  --format json \
  "$REPO_PATH" \
  > "$RAW_JSON"
```

(`--recent-commits 1200` = 50 days × 24 h ≈ "last 50 commits"
when the repo averages one commit per day; tune per-repo.)

The JSON shape ships in
`scripts/fast_security_scan.md`. Key fields per finding:

| Field | Meaning |
|---|---|
| `rule` | Catalog rule name (e.g. `github-personal-access-token`) |
| `severity` | `CRITICAL` / `HIGH` / `MEDIUM` / `LOW` |
| `file` | Path |
| `line`, `column` | 1-indexed location |
| `match` | The full matched substring (DO NOT echo into agent prose; OK to keep in the report file) |
| `description` | Per-rule explanation from `security_catalog.json` |

## Severity mapping

Each tool emits its own severity vocabulary. We normalise to four
levels (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`) so the `pre-publish`
mode can apply a single threshold.

| Tool | Tool field | Maps to |
|---|---|---|
| trufflehog | `Verified=true` AND known-critical detector (AWS, GitHub, GitLab, Slack, PEM) | `CRITICAL` |
| trufflehog | `Verified=true` AND less-critical detector (low-blast-radius vendor) | `HIGH` |
| trufflehog | `Verified=false` AND known-critical detector | `HIGH` |
| trufflehog | `Verified=false` AND less-critical | `MEDIUM` |
| gitleaks | RuleID matches a CRITICAL pattern list (AWS, GitHub, GitLab, Slack, PEM) | `CRITICAL` |
| gitleaks | otherwise | `HIGH` |
| fast_security_scan | reads `severity` directly from the catalog | passthrough |

The CRITICAL pattern list lives in
`scripts/security_catalog.json` — the same list the bundled
scanner uses for its own severity field. Keep them in sync when
extending.

## Output schema

The skill writes TWO files per scan; both live under
`$MAIN_ROOT/reports/maintainer-secrets-scan/<TS>-scan.{json,md}`
(local-time timestamp with GMT offset, per
`~/.claude/rules/agent-reports-location.md`).

### JSON shape (`<TS>-scan.json`)

```json
{
  "mode": "scan",
  "tool_used": "trufflehog | gitleaks | bundled",
  "tool_version": "1.2.3",
  "ts": "2026-05-27T13:45:01+0200",
  "repo_path": "$PROJECT_DIR",
  "commits_scanned": 50,
  "summary": {
    "critical": 0,
    "high": 0,
    "medium": 2,
    "low": 5
  },
  "findings": [
    {
      "severity": "MEDIUM",
      "rule": "github-app-installation-token",
      "file": "tests/fixtures/secrets.txt",
      "line": 12,
      "commit": null,
      "tool_specific": { "trufflehog_detector": "Github", "verified": false }
    }
  ],
  "suppressed_count": 3,
  "suppression_file": ".maintainer-secrets-ignore"
}
```

The `findings[].file` MUST already be redacted by
`scripts/redact.py` before being written to disk — the report
file itself is gitignored under `reports/` but it can be shared
out-of-band, so the path-leak rules apply.

The `findings[].commit` field is null for working-tree hits and a
full SHA for git-history hits.

### Markdown shape (`<TS>-scan.md`)

Human-readable summary. Required sections in order:

1. `# Secret-scan report — <repo> — <TS>`
2. `## Summary` — the severity table.
3. `## Critical findings` — one row per finding; empty section
   is OK ("(none)").
4. `## High findings` — same.
5. `## Medium / Low` — collapsed table.
6. `## Suppressed` — entries from `.maintainer-secrets-ignore`
   that matched this scan (so the user can audit the
   suppression list).
7. `## Tool details` — which scanner was used, its version, and
   the exact invocation.

**Never echo the raw matched bytes** of a credential into the
Markdown report. Show only `<RULE> in <FILE>:<LINE>` (commit hash
if applicable). The JSON file may include `tool_specific` data
that contains the raw bytes; treat the JSON file as
gitignored-private (under `reports/`).

## Audit-mode output

Markdown table on stdout:

```
| Tool                 | Installed | Version |
|----------------------|-----------|---------|
| trufflehog           | yes       | 3.81.10 |
| gitleaks             | no        | (brew install gitleaks) |
| bundled (fast_scan)  | yes       | always  |
```

Exit code: `0` if at least one scanner is available; `2` if NONE
(impossible by construction — the bundled scanner always ships
with the plugin).

Install hints printed below the table (one per missing tool):

```
trufflehog not installed. To install:
  brew install trufflehog
  # or download -> review -> run (never execute a remote stream directly):
  curl -fsSLo /tmp/trufflehog-install.sh https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh
  less /tmp/trufflehog-install.sh
  sh /tmp/trufflehog-install.sh -b /usr/local/bin

gitleaks not installed. To install:
  brew install gitleaks
  # or:
  go install github.com/gitleaks/gitleaks/v8@latest
```
