# fast_security_scan.py — design notes

## What

A multi-pattern security scanner that scans text files for matches against
a catalog of regular expressions (secret markers, GitHub Actions injection
patterns, dangerous shell idioms). Designed to replace the shell-based
`grep -nE` fallback in the Guardian T5 detector with a faster, more
flexible Python tool.

## Why fast

Three architectural choices give the scanner its speed:

1. **RE2 Set (one DFA for all patterns).**
   Google's RE2 supports a `Set` API that compiles N regexes into ONE
   deterministic finite automaton. Matching a file is then one linear
   pass over the input — O(n) regardless of pattern count. The Set's
   `Match()` returns the *indexes* of patterns that hit; the scanner then
   re-runs `re2.finditer()` for each hit to extract spans + line numbers.

2. **Python `re` fallback for the patterns RE2 can't compile.**
   RE2 deliberately omits lookaround (`(?=...)` / `(?!...)`) and
   backreferences to guarantee linear-time matching. Patterns that need
   either fall back to Python's `re` module, run individually. The
   fallback list is usually short and only triggers on patterns that
   genuinely need those features.

3. **`multiprocessing.Pool` for file fan-out.**
   Each worker compiles the catalog once at startup, then handles files
   as the orchestrator hands them in via `imap_unordered`. CPU-bound
   regex matching releases the GIL in `re2`, so workers run in true
   parallel. Default `--workers` is `os.cpu_count()`.

Typical performance on this plugin (~200 text files across `.github/`,
`scripts/`, `skills/`, `tests/`, `agents/`):

```text
$ time uv run --with google-re2 scripts/fast_security_scan.py [paths...]
0.46s user 0.18s system 462% cpu 0.138 total
```

138 ms wall time, 4.6× CPU utilization (4–5 cores active on a
14-thread machine).

## Catalog format

The built-in `DEFAULT_CATALOG` is a list of `Pattern` dataclasses:

```python
@dataclass(frozen=True)
class Pattern:
    name: str           # rule id, e.g. "aws-access-key-id"
    severity: str       # CRITICAL | HIGH | MEDIUM | LOW
    description: str    # human-readable explanation
    regex: str          # the regex (RE2 or Python re-compatible)
    fallback: bool = False   # force Python re even if RE2 would compile
```

External catalogs can be loaded via `--catalog catalog.json`:

```json
{
  "patterns": [
    {
      "name": "my-custom-secret",
      "severity": "CRITICAL",
      "description": "My internal secret format",
      "regex": "MYORG-[A-Z0-9]{32}"
    }
  ]
}
```

## Usage

```bash
# Scan all .github/workflows/*.yml
uv run --with google-re2 scripts/fast_security_scan.py --workflows

# Scan the last 48h of git history
uv run --with google-re2 scripts/fast_security_scan.py --recent-commits 48

# Scan explicit paths
uv run --with google-re2 scripts/fast_security_scan.py path/to/file.py path/to/dir/

# JSON output (machine-readable)
uv run --with google-re2 scripts/fast_security_scan.py --workflows --format json

# Filter by severity
uv run --with google-re2 scripts/fast_security_scan.py --severity CRITICAL --workflows

# Single-process (deterministic; useful for debugging)
uv run --with google-re2 scripts/fast_security_scan.py --workers 1 path/to/file
```

## Exit codes

- `0` — no findings at or above the requested severity
- `1` — findings present
- `2` — scanner error (catalog malformed, I/O failure, etc.)

## Integration points

| Caller | Mode |
|---|---|
| `maintainer-guardian` T5 secret-leak detector | `--recent-commits 48 --severity CRITICAL --format json` |
| `maintainer-guardian` T1 workflow-drift cross-check | `--workflows --format json` (complement to zizmor, not replacement) |
| Ad-hoc audit | `--severity HIGH path/to/anything` |

The scanner is **not** a replacement for `zizmor`. Zizmor does AST-level
YAML analysis (knowing the difference between a `run:` block and a `with:`
input) that pure regex can't match. The fast scanner complements zizmor
with a wider catalog of secret-leak markers and faster turnaround for
recurring scans inside long-running agents.

## Catalog growth

When adding a new pattern, prefer RE2-compatible syntax (no lookaround,
no backref) so it joins the one-pass DFA. If you genuinely need
lookaround (e.g. "match X not preceded by Y"), set `fallback=True` and
the scanner will run it through Python `re` instead. Mixing both is
fine; the fallback list is typically a small fraction of the catalog.

## What lives where

- `scripts/fast_security_scan.py` — the scanner itself
- `scripts/fast_security_scan.md` — this design doc
- `skills/maintainer-guardian/references/threat-classes.md` (T5 section)
  — how the Guardian skill invokes the scanner
- `tests/test_fast_security_scan.py` (when added) — pytest coverage
