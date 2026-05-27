# Validate-mode checklist — `maintainer-generate-docs`

`validate` mode reads each existing community file and runs the
content checks below. A failure does NOT cause the skill to
modify the file — the caller is expected to read the failure
list and fix by hand (or run `update-stale` after backing the
file up explicitly).

## Table of contents

- [Why content checks (not just presence)](#why-content-checks-not-just-presence)
- [Per-file checklist](#per-file-checklist)
- [Failure shape](#failure-shape)
- [Stale heuristic](#stale-heuristic)

## Why content checks (not just presence)

A `CONTRIBUTING.md` that's an empty stub is no better than a
missing one — contributors still don't know how to run the
tests. GitHub's "Community Standards" tab only checks file
presence; this skill goes further and checks that each file
contains the MINIMUM useful content. The checks are intentionally
generous (substring match) so a file written in a different style
than the templates still passes.

## Per-file checklist

### `CONTRIBUTING.md`

| Check | Pass criterion (case-insensitive) |
|---|---|
| Mentions how to clone | regex `git\s+clone` OR `gh\s+repo\s+clone` |
| Mentions how to run tests | regex `test\|pytest\|jest\|vitest\|cargo\s+test\|go\s+test\|npm\s+test` |
| Mentions the branch convention | substring `branch` |
| Mentions the commit-message convention | substring `commit` |
| Mentions where to file bug reports | substring `issue` OR `bug` |
| Mentions where to find the code of conduct | substring `conduct` OR `CODE_OF_CONDUCT` |
| Body length | ≥ 30 non-blank lines (a stub is < 30) |

### `SECURITY.md`

| Check | Pass criterion |
|---|---|
| Has a private disclosure channel | regex `security[/-]advisor\|advisory\|security@\|private` |
| Has a disclosure email OR a GitHub Security Advisory URL | regex `@` (any email) OR `security/advisories` |
| Says "do NOT file a public issue" (or equivalent warning) | regex `do\s+not\s+file\|private\s+disclosure\|public\s+issue` (case-insensitive) |
| Has a turnaround table OR explicit response timelines | regex `\bday[s]?\b\|\bweek[s]?\b\|turnaround\|respond` |
| Body length | ≥ 25 non-blank lines |

### `CODE_OF_CONDUCT.md`

| Check | Pass criterion |
|---|---|
| Adopts a recognised CoC standard | regex `contributor\s+covenant\|code\s+of\s+conduct\|covenant` |
| Has a contact address for enforcement | regex `@` (any email) OR substring `contact` |
| Body length | ≥ 50 non-blank lines (Contributor Covenant is ~130 lines; aggressive stubs are caught here) |

### `ACKNOWLEDGMENTS.md`

| Check | Pass criterion |
|---|---|
| Names at least one author | regex `author\|maintainer\|^\s*-\s+` |
| Has at least one credit / dependency mention | regex `\bdepend\|\bcredit\|\bbuilt\s+on\|\bthanks` |
| Body length | ≥ 10 non-blank lines |

### `AUTHORS`

| Check | Pass criterion |
|---|---|
| Has at least one line that looks like a person | regex `\b[A-Z][a-z]+\b` somewhere |
| Body length | ≥ 1 non-blank line |

### `.github/PULL_REQUEST_TEMPLATE.md`

| Check | Pass criterion |
|---|---|
| Has a Summary section | substring `Summary` OR `What changed` |
| Has a verification / testing section | regex `verify\|test\|how\s+to` (case-insensitive) |
| Has a checklist | substring `- [ ]` |
| Body length | ≥ 15 non-blank lines |

### `.github/ISSUE_TEMPLATE/bug_report.yml`

| Check | Pass criterion |
|---|---|
| Valid YAML (parses with `yaml.safe_load`) | parses without exception |
| Has a `name:` field | YAML top-level `name` present |
| Has a `body:` list | YAML top-level `body` is a list |
| Asks for reproduction steps | any input/textarea has label matching regex `reproduce\|reproduction\|steps` (case-insensitive) |
| Asks for expected vs actual | regex `expected.*actual\|actual.*expected` (case-insensitive) somewhere in labels |

### `.github/ISSUE_TEMPLATE/feature_request.yml`

| Check | Pass criterion |
|---|---|
| Valid YAML | parses without exception |
| Has a `name:` field | present |
| Has a `body:` list | present |
| Asks for the problem | label substring `problem` OR `motivation` OR `use case` |
| Asks for the proposed solution | label substring `solution` OR `propose` OR `feature` |

### `.github/ISSUE_TEMPLATE/config.yml`

| Check | Pass criterion |
|---|---|
| Valid YAML | parses without exception |
| Has `blank_issues_enabled:` set (true or false) | top-level key present |

## Failure shape

The skill emits one line per failing check:

```
fail: <file>: <check name> — <human-readable reason>
```

Example:

```
fail: SECURITY.md: Has a private disclosure channel — no match for /security[/-]advisor|advisory|security@|private/
fail: CONTRIBUTING.md: Body length — only 12 non-blank lines (need ≥ 30)
```

Exit code is non-zero if ANY check fails. JSON disposition lists
every failure under `validate_failures: [...]` so the caller can
ingest the result programmatically.

## Stale heuristic

A file is "stale" when:

```
TS_LAST_COMMIT=$(git log -1 --format=%ct -- "<file>")
NOW=$(date +%s)
[ $((NOW - TS_LAST_COMMIT)) -gt $((365 * 24 * 60 * 60)) ]
```

i.e. its last git commit is more than 365 days old. The threshold
is configurable via `--stale-days N`. The check uses commit time,
not file mtime — file mtime is unreliable across clones.

`update-stale` mode regenerates these files after copying the old
file to `<file>.bak-<TIMESTAMP>`. The backup MUST land in the
same directory as the original so the caller's recovery is a
single `mv`.
