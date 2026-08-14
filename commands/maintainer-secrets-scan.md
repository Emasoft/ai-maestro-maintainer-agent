---
description: Scan the maintained repo for committed secrets via trufflehog / fast_security_scan. Three modes — scan / pre-publish / audit.
argument-hint: "[scan|pre-publish|audit]"
---

Run secret-scanning gates against the maintained repo's working
tree + last 50 commits. Three modes:

- `scan` (default) — full scan; writes a SARIF + markdown report
  under `$MAIN_ROOT/reports/maintainer-secrets-scan/`. Exits 0 if
  no HIGH/CRITICAL findings; exits 1 otherwise.
- `pre-publish` — hook for publish.py-style pipelines. Exits 0 if
  clean; exits 1 if any HIGH/CRITICAL → block publish.
- `audit` — diagnose: which scanners are installed (trufflehog /
  fast_security_scan), what versions, what's missing. Print
  install hints (`brew install trufflehog`, etc.).

Loads skill: **maintainer-secrets-scan**

Tool fallback chain: prefer `trufflehog` (most authoritative) →
bundled `scripts/fast_security_scan.py` (re2-based, no external
install, smaller pattern set). At least the bundled scanner is
always available.

Severity:
- **CRITICAL** — private keys, full PATs, AWS root access keys
- **HIGH** — partial PATs, recent commits adding tokens
- **MEDIUM** — generic high-entropy strings on suspect lines
- **LOW** — `.env.example` placeholders, test fixtures

Only HIGH/CRITICAL block publish. MEDIUM/LOW are informational.

False positives can be suppressed by adding a path or regex
pattern to `.maintainer-secrets-ignore` at the repo root (see
the skill's `references/false-positive-suppression.md`).

This command does NOT auto-revoke leaked secrets. If a real
leak is detected: rotate the secret immediately at the provider
(GitHub, AWS, Slack, etc.), then `git filter-repo` the leak out
of history, then force-push (R19.7 exception — secret leaks
warrant emergency action).
