# False-positive suppression — `.maintainer-secrets-ignore`

Secret scanners produce false positives. A test fixture that
ships a deliberately-fake AWS key for a unit test, a docs page
that quotes the literal shape of a GitHub PAT, a CHANGELOG entry
that mentions a long-ago-rotated token — all of these are
legitimate findings that the maintainer must allow.

This file describes the `.maintainer-secrets-ignore` mechanism
that the skill consults on every scan.

## Table of Contents

- [Suppression file format](#suppression-file-format)
- [Match semantics](#match-semantics)
- [Authoring rules](#authoring-rules)
- [Tool-specific propagation](#tool-specific-propagation)

---

## Suppression file format

The suppression file lives at the entrusted repo's root:

```
<repo>/.maintainer-secrets-ignore
```

It is plain text. Each line is either:

1. A comment (starts with `#`) — ignored.
2. A blank line — ignored.
3. A suppression entry — a single record on one line with
   tab-separated or 4-space-separated columns:

```text
<rule-id> <TAB> <path-glob> <TAB> <reason>
```

Example:

```text
# Test fixtures that intentionally ship example tokens
aws-access-key-id    tests/fixtures/aws-fake.txt    intentional example for unit tests
github-pat           docs/security/leak-incident-2026-03.md    historical incident report, key rotated
slack-bot-token      tests/data/slack-fixture.json    test-only stub for webhook tests

# Documentation that quotes the SHAPE of a token (the example chars are fake)
github-pat           docs/security/threat-model.md    documents PAT shape; literal example is fake
```

The three columns are **mandatory** on every entry — no
positional shortcuts, no glob-default-everything. A suppression
without a `reason` column is rejected.

## Match semantics

A finding is suppressed when ALL THREE of the following match:

1. `rule_id` — exact string match against the normalised rule
   name in the report (e.g. `aws-access-key-id`). Each scanner
   emits its own rule IDs; see [protocols.md](protocols.md) for
   the canonical list. The skill normalises tool-specific rule
   names (e.g. trufflehog's `Github` detector → `github-pat`
   when the body starts `ghp_`).
2. `path-glob` — `pathlib.PurePath.match` semantics on the
   finding's `file` field. `**` is recursive, `*` is
   non-recursive within one component. Globs are evaluated
   relative to the repo root.
3. The finding's `commit` field is either NULL (working-tree
   hit) OR appears in the `--repo-history` cone of the current
   `HEAD~50` window. Suppressions for historical commits
   continue to apply even after the secret rotates because
   the commit history is immutable.

If any of the three checks fails, the finding is NOT
suppressed and contributes to the severity buckets normally.

## Authoring rules

Every entry MUST include a non-trivial `reason`. "false
positive" is NOT a valid reason — the reviewer needs to know
WHY this is a false positive without rerunning the scan. Good
reasons:

- "intentional example for unit tests"
- "historical incident report; key rotated <DATE>"
- "documents the SHAPE of the token; literal example is fake"
- "vendor onboarding page; sample format only"

Bad reasons:

- "false positive"
- "n/a"
- "ignore"

The maintainer agent SHOULD audit `.maintainer-secrets-ignore`
on every patrol cycle (chained from `maintainer-guardian`) and
file an issue if an entry's `reason` is `false positive` or
similar — that's a maintainer footgun, not a real suppression.

### Maximum entries

`.maintainer-secrets-ignore` is intentionally append-only and
small. Soft cap: 50 entries per repo. When the cap is exceeded,
file a tracking issue suggesting the user rotate the underlying
secrets (most "intentional example" fixtures should be replaced
with deterministically-fake placeholders that don't match any
known token shape — e.g. `ghp_FAKE_FAKE_FAKE_FAKE_FAKE_FAKE_FAK`
which fails the GitHub-PAT regex on character class but reads
like a real example to a human).

### Authorisation

Adding an entry to `.maintainer-secrets-ignore` IS a protected
edit (the file is on the canonical protected-paths list, since
it weakens a security gate). Per
`maintainer-approval-gate`, the agent CANNOT add suppression
entries on its own — only the authorized user can. Agent-side
the workflow is:

1. Scan finds a suspected false positive.
2. Agent files an issue suggesting the suppression line to
   paste, with the three columns pre-filled and a draft reason.
3. Authorized user reviews; if they agree, they edit
   `.maintainer-secrets-ignore` themselves OR reply with
   `approve-protected-edit` on the issue, at which point the
   agent applies the edit via the approval-gate flow.

## Tool-specific propagation

Each underlying scanner has its own native suppression file
format (`.trufflehog-ignore`, `.gitleaks.toml`, etc.). The
maintainer-secrets-scan skill does NOT translate
`.maintainer-secrets-ignore` into per-tool formats — it instead
applies the suppression filter ONCE, AFTER the scanner returns,
on the unified findings array.

Reasoning: if we generated per-tool ignore files, the same
suppression would have to live in N places and would drift.
Filtering on the normalised output is the single source of
truth.

The only exception is the bundled `fast_security_scan.py` — it
has no native ignore file, so the skill applies the filter on
its raw JSON output directly. Same code path, same result.

### Native ignore files we DO honor (additive, not authoritative)

If the entrusted repo already has a native ignore file, we honor
it AS WELL AS `.maintainer-secrets-ignore`. The two compose
(union of suppressions). The skill never REWRITES a native ignore
file — it only reads.

| Tool | Native ignore file | Read? |
|---|---|---|
| trufflehog | `--exclude-paths trufflehog-excludes.txt` | yes (passed to the invocation) |
| gitleaks | `.gitleaks.toml` `[allowlist]` block | yes (gitleaks itself applies) |
| fast_security_scan | (none) | n/a (only `.maintainer-secrets-ignore` applies) |

If the maintainer-secrets-scan filter suppresses N findings but
the native filter suppresses M (with possibly different sets),
the report's `suppressed_count` field reflects the UNION (every
finding the user has explicitly allowed via either channel).
