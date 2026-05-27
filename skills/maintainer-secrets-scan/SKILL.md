---
description: |
  Use when the maintainer agent needs to run secret-scanning on
  the entrusted repo's working tree + recent commit history.
  Three modes: SCAN (audit), PRE-PUBLISH (block if HIGH/CRITICAL),
  AUDIT (diagnose which tools are installed). Closes audit MAJOR-1:
  Mega-Linter's REPOSITORY_GITLEAKS config exists but no caller
  ever invokes Mega-Linter. Tool fallback chain: trufflehog →
  gitleaks → bundled fast_security_scan.py.
  Trigger with phrases like "scan for secrets", "secret-scan
  pre-publish", "check for committed credentials", or "audit
  secret-scan tools".
---

# maintainer-secrets-scan — secret-scanning gate for entrusted repos

## Overview

The audit found `REPOSITORY_GITLEAKS: true` in `.mega-linter.yml`
but no workflow ever calls Mega-Linter, so the gate is dormant.
This skill wakes it up: every entrusted repo gets actively scanned
on every patrol cycle AND blocked from publish if a HIGH/CRITICAL
finding is in the working tree or the last 50 commits. The skill
prefers `trufflehog` (most authoritative), falls back to `gitleaks`
(faster, smaller pattern set), and finally to the bundled
`scripts/fast_security_scan.py` (no install needed — always works).

## Prerequisites

- `git` on PATH; the entrusted repo is checked out (working tree
  may be dirty).
- `uv` on PATH (for the bundled scanner's PEP 723 inline deps).
- At least one of: `trufflehog`, `gitleaks`, or the bundled
  `scripts/fast_security_scan.py` (which ships with this plugin
  and is always available — the chain never bottoms out).
- `gh auth token` returns a value (only required if the scan
  result needs to be filed as an issue).

## Instructions

Pick the mode that matches the caller:

### Mode: `scan` (default audit, every patrol cycle)

1. Resolve which scanner to use — see the protocols reference in
   Resources below for the file path and complete TOC (Tool
   detection chain is the relevant section).
2. Run the scanner against (a) the working tree and (b) the last
   50 commits of git history (`git log -p -n 50`).
3. Apply the false-positive suppression file if present — see
   the false-positive-suppression reference in Resources below for
   the file path and complete TOC.
4. Bucket findings by severity (CRITICAL / HIGH / MEDIUM / LOW).
5. Write a JSON + Markdown report to
   `$MAIN_ROOT/reports/maintainer-secrets-scan/<TS>-scan.{json,md}`.
6. Return a JSON summary on stdout:
   `{mode, tool_used, findings: {critical, high, medium, low},
   report_md, report_json}`.

### Mode: `pre-publish` (hook for publish.py-style pipelines)

1. Run `scan` internally (same as above).
2. If `findings.critical > 0 || findings.high > 0`, **exit 1**
   (caller treats this as "block publish"). Print the report path
   to stderr.
3. Otherwise exit 0. MEDIUM / LOW findings are informational and
   do NOT block publish (they go to the report file for the next
   patrol cycle to triage).

### Mode: `audit` (diagnose which tools are installed)

1. Probe each scanner in the chain: `trufflehog --version`,
   `gitleaks version`, then check for the bundled
   `scripts/fast_security_scan.py`.
2. Print a Markdown table on stdout — see
   [references/protocols.md](references/protocols.md): [Audit-mode
   output](references/protocols.md#audit-mode-output).
3. Print install hints for the missing optional tools:
   - `brew install trufflehog` (or the official upstream installer
     documented in the [TruffleHog README](https://github.com/trufflesecurity/trufflehog#installation))
   - `brew install gitleaks` (or
     `go install github.com/gitleaks/gitleaks/v8@latest`)

Per-tool invocation, JSON output schema, severity mapping, and
the full tool detection algorithm are in
[references/protocols.md](references/protocols.md):

- [Tool detection chain](references/protocols.md#tool-detection-chain)
- [trufflehog invocation](references/protocols.md#trufflehog-invocation)
- [gitleaks invocation](references/protocols.md#gitleaks-invocation)
- [fast_security_scan.py invocation](references/protocols.md#fast_security_scanpy-invocation)
- [Severity mapping](references/protocols.md#severity-mapping)
- [Output schema](references/protocols.md#output-schema)
- [Audit-mode output](references/protocols.md#audit-mode-output)

## Output

- **scan**: stdout JSON
  `{mode: "scan", tool_used, findings: {critical, high, medium,
  low}, report_md, report_json}` + the report files on disk.
- **pre-publish**: stdout JSON (same shape as `scan`); exit code
  `1` if `critical + high > 0` else `0`.
- **audit**: stdout Markdown table; exit code `0` if at least one
  scanner is available, `2` if NONE (which is impossible because
  the bundled `fast_security_scan.py` always ships — exit 2 here
  means the plugin itself is corrupt).

Report files (always):
- `$MAIN_ROOT/reports/maintainer-secrets-scan/<TS>-scan.json` —
  full findings array for the next patrol cycle to diff against.
- `$MAIN_ROOT/reports/maintainer-secrets-scan/<TS>-scan.md` —
  per-severity tables for the authorized user to read.

## Error Handling

| Error | Action |
|-------|--------|
| All three scanners unavailable | Exit 2 with "plugin self-test failed — bundled fast_security_scan.py missing" — this is a packaging bug, not a runtime error |
| trufflehog/gitleaks exits non-zero with no JSON output | Fall through to the next scanner in the chain; surface the failure in the report |
| The repo has > 50 commits but the user only wants HEAD | Pass `--commits-depth 1`; default is 50, configurable per call |
| `.maintainer-secrets-ignore` malformed | Stop, surface — never silently ignore a malformed suppression file (could be an attacker-authored override) |
| Working tree contains uncommitted binary blobs >10 MiB | Skip those files (every tool has its own large-file skip), log to report |
| CRITICAL finding in commit history but NOT in working tree | Treat as CRITICAL — the secret is in the public history; rotation is required |

## Examples

```
Patrol cycle pre-step → maintainer-secrets-scan scan
→ tool_used=trufflehog
→ findings: {critical: 0, high: 0, medium: 2, low: 5}
→ report_md: $MAIN_ROOT/reports/maintainer-secrets-scan/<TS>-scan.md
→ exit 0 (no block)
```

```
publish.py wrapper → maintainer-secrets-scan pre-publish
→ tool_used=gitleaks (trufflehog not installed)
→ findings: {critical: 1, high: 0, medium: 0, low: 0}
→ exit 1 → publish.py refuses to push → operator sees report
```

```
Developer asks "do we have a secret-scanner installed?":
→ maintainer-secrets-scan audit
→ stdout:
   | Tool        | Installed | Version |
   |---|---|---|
   | trufflehog  | no        | (brew install trufflehog) |
   | gitleaks    | yes       | 8.18.4                    |
   | bundled     | yes       | always                    |
→ exit 0
```

## Scope

ONLY a scanner gate. Does NOT:

- Apply fixes to leaked secrets. If a credential leaked, the user
  rotates it; this skill cannot un-leak a token from git history.
- Strip secrets from agent-authored prose — that's
  `maintainer-redact`'s job. Both skills together form the chain:
  redact (scrub prose) → secrets-scan (audit committed bytes).
- Modify the entrusted repo. The scan is read-only; report files
  go under `$MAIN_ROOT/reports/`, never into the entrusted
  repo's tree.

Per RULE 1.7 the subagent that invokes this skill MUST NOT
commit, push, or modify any file outside `$MAIN_ROOT/reports/`.

## Resources

- [Per-tool invocation + JSON schema + severity mapping](references/protocols.md):
  - Tool detection chain
  - trufflehog invocation
  - gitleaks invocation
  - fast_security_scan.py invocation
  - Severity mapping
  - Output schema
  - Audit-mode output
- [False-positive suppression (.maintainer-secrets-ignore)](references/false-positive-suppression.md):
  - Suppression file format
  - Match semantics
  - Authoring rules
  - Tool-specific propagation
- Source: `scripts/fast_security_scan.py` (bundled fallback —
  always available, DO NOT modify from this skill).
- Companion skills: `maintainer-redact` (prose-level scrub),
  `maintainer-guardian` T5 (continuous secret-leak detector),
  `maintainer-approval-gate` (protected-paths gate).
- Audit finding: MAJOR-1, audit E (dormant gitleaks gate —
  REPOSITORY_GITLEAKS configured but Mega-Linter never called).
