#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["google-re2"]
# ///
"""Fast multi-pattern security scanner using google-re2 RE2::Set.

Two-phase scanning:
    1. RE2 Set.Match() — one-pass over the file, returns the indexes of
       patterns that matched. O(n) regardless of pattern count: many
       patterns compile into one DFA.
    2. For each hit index, run re2.finditer() to extract line numbers
       and matched text spans.

Falls back to Python re for patterns RE2 can't compile (lookaround,
backrefs). The fallback path runs each pattern individually — slow but
correct — and is reserved for the small number of patterns that need
it.

Multiprocessing fan-out: each worker handles one file via pool.imap.
GIL is not contended (re2 + I/O release it).

Usage:
    fast_security_scan.py [--catalog PATH] [--workers N] [--format json|text]
                          [--severity CRITICAL|HIGH|MEDIUM|LOW] FILES...
    fast_security_scan.py --workflows           # shorthand for .github/workflows/*.yml
    fast_security_scan.py --recent-commits N    # scan git log -p --since=NN

Exit codes:
    0  no findings
    1  findings at requested --severity or higher
    2  scanner error (catalog malformed, I/O failure, etc.)
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    # google-re2 binding. Pure-C regex engine with multi-pattern Set support.
    import re2  # pyright: ignore[reportMissingImports]
except ImportError:
    print(
        "[fast_security_scan] google-re2 not installed. Run via:  uv run --with google-re2 scripts/fast_security_scan.py",
        file=sys.stderr,
    )
    sys.exit(2)


SEVERITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


@dataclass(frozen=True)
class Pattern:
    """One entry in the security catalog."""

    name: str
    severity: str
    description: str
    regex: str
    # If RE2 can't compile (lookaround / backref), we mark fallback=True so
    # the scanner uses Python's stdlib re for this pattern only.
    fallback: bool = False


@dataclass(frozen=True)
class Finding:
    """A single rule-match in a single file."""

    file: str
    line: int
    column: int
    rule: str
    severity: str
    description: str
    match: str


# ── Catalog ─────────────────────────────────────────────────────────────────

# The pattern catalog is loaded at runtime from scripts/security_catalog.json
# rather than embedded here as Python string literals. This is deliberate:
#
# 1. Catalog updates do not need a Python code change.
# 2. Static-analysis tools (pyright, bandit, codeql, the CPV skillaudit
#    detectors) inspect Python source for credential / injection shapes.
#    Embedding the catalog inline would trigger every analyser's
#    pattern-in-source heuristic and produce a flood of false positives
#    (the data IS the regex; the regex looks like the credential).
#    Moving the patterns to a JSON data file removes them from the
#    Python source surface.

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parent / "security_catalog.json"


# ── Catalog loading ─────────────────────────────────────────────────────────


def load_catalog(path: Path | None) -> list[Pattern]:
    """Return the catalog patterns from JSON.

    Default path: scripts/security_catalog.json (next to this file).
    Override with --catalog to point at a different JSON file.
    """
    if path is None:
        path = DEFAULT_CATALOG_PATH
    raw = json.loads(path.read_text())
    patterns: list[Pattern] = []
    for entry in raw["patterns"]:
        patterns.append(
            Pattern(
                name=entry["name"],
                severity=entry.get("severity", "MEDIUM").upper(),
                description=entry.get("description", ""),
                regex=entry["regex"],
                fallback=bool(entry.get("fallback", False)),
            )
        )
    return patterns


# ── Two-phase compilation ───────────────────────────────────────────────────


def compile_catalog(
    patterns: list[Pattern],
) -> tuple[re2.Set, list[Pattern], list[tuple[Pattern, re.Pattern[str]]]]:
    """Compile the catalog into (RE2 Set, RE2 metadata, Python re fallback list).

    Returns:
        - re2_set: the compiled RE2 Set (one DFA for all RE2-compatible
          patterns; one-pass match).
        - re2_meta: parallel list of Pattern objects indexed by the Set's
          returned indexes. re2_meta[i] is the Pattern that was Added at
          index i.
        - py_fallback: list of (Pattern, compiled Python re) for the
          patterns RE2 rejected (lookaround / backref / unsupported perl).
    """
    re2_set = re2.Set.SearchSet()
    re2_meta: list[Pattern] = []
    py_fallback: list[tuple[Pattern, re.Pattern[str]]] = []

    for pat in patterns:
        if pat.fallback:
            # Explicit fallback marker in the catalog
            py_fallback.append((pat, re.compile(pat.regex)))
            continue
        try:
            # Probe-compile first so we don't poison the Set with a bad pattern
            re2.compile(pat.regex)
        except re2.error:
            py_fallback.append((pat, re.compile(pat.regex)))
            continue
        re2_set.Add(pat.regex)
        re2_meta.append(pat)

    if re2_meta:
        re2_set.Compile()

    return re2_set, re2_meta, py_fallback


# ── File scanning ───────────────────────────────────────────────────────────


def _line_col(text: str, offset: int) -> tuple[int, int]:
    """Convert a byte/char offset into (1-indexed line, 1-indexed column)."""
    line_no = text.count("\n", 0, offset) + 1
    last_nl = text.rfind("\n", 0, offset)
    col = offset - last_nl  # last_nl == -1 → col = offset + 1
    return line_no, col


def scan_text(
    path: str,
    text: str,
    re2_set: re2.Set,
    re2_meta: list[Pattern],
    py_fallback: list[tuple[Pattern, re.Pattern[str]]],
) -> list[Finding]:
    """Phase 1 + Phase 2 scan of a single text blob."""
    findings: list[Finding] = []

    # Phase 1: which RE2 patterns hit? One DFA pass over the whole text.
    if re2_meta:
        hit_indexes = re2_set.Match(text) or []
        # Phase 2: for each hit, locate spans + line numbers via finditer.
        for idx in hit_indexes:
            pat = re2_meta[idx]
            for m in re2.finditer(pat.regex, text):
                line, col = _line_col(text, m.start())
                findings.append(
                    Finding(
                        file=path,
                        line=line,
                        column=col,
                        rule=pat.name,
                        severity=pat.severity,
                        description=pat.description,
                        match=m.group(0),
                    )
                )

    # Python re fallback (always run — only triggers on the explicit fallback
    # patterns + RE2-rejected patterns; usually a short list).
    for pat, py_re in py_fallback:
        for m in py_re.finditer(text):
            line, col = _line_col(text, m.start())
            findings.append(
                Finding(
                    file=path,
                    line=line,
                    column=col,
                    rule=pat.name,
                    severity=pat.severity,
                    description=pat.description,
                    match=m.group(0),
                )
            )

    return findings


# ── Multiprocessing worker ─────────────────────────────────────────────────-

# Each worker process holds the compiled Set in module globals (cheaper than
# re-compiling per file). The pool initializer populates these.
_WORKER_SET: re2.Set | None = None
_WORKER_META: list[Pattern] | None = None
_WORKER_PY_FALLBACK: list[tuple[Pattern, re.Pattern[str]]] | None = None


def _worker_init(patterns: list[Pattern]) -> None:
    """Compile the catalog once per worker process."""
    global _WORKER_SET, _WORKER_META, _WORKER_PY_FALLBACK
    _WORKER_SET, _WORKER_META, _WORKER_PY_FALLBACK = compile_catalog(patterns)


def _worker_scan(path: str) -> list[Finding]:
    """Scan one file. Called by Pool.imap_unordered."""
    assert _WORKER_SET is not None
    assert _WORKER_META is not None
    assert _WORKER_PY_FALLBACK is not None
    try:
        text = Path(path).read_text(errors="replace")
    except OSError as exc:
        # I/O error on this file — surface as a synthetic finding so the
        # caller can decide to fail or skip.
        return [
            Finding(
                file=path,
                line=0,
                column=0,
                rule="scanner-io-error",
                severity="LOW",
                description=f"could not read file: {exc}",
                match="",
            )
        ]
    return scan_text(path, text, _WORKER_SET, _WORKER_META, _WORKER_PY_FALLBACK)


# ── Scan entry points ──────────────────────────────────────────────────────-


def scan_paths(
    paths: list[Path],
    patterns: list[Pattern],
    workers: int,
) -> list[Finding]:
    """Scan a list of file paths in parallel."""
    str_paths = [str(p) for p in paths]
    if workers <= 1 or len(str_paths) == 1:
        # Single-process path (also useful for debugging — preserves tracebacks).
        rset, rmeta, pyfb = compile_catalog(patterns)
        out: list[Finding] = []
        for sp in str_paths:
            try:
                text = Path(sp).read_text(errors="replace")
            except OSError as exc:
                out.append(
                    Finding(
                        file=sp,
                        line=0,
                        column=0,
                        rule="scanner-io-error",
                        severity="LOW",
                        description=f"could not read file: {exc}",
                        match="",
                    )
                )
                continue
            out.extend(scan_text(sp, text, rset, rmeta, pyfb))
        return out

    # Multi-process fan-out
    with mp.Pool(
        processes=workers,
        initializer=_worker_init,
        initargs=(patterns,),
    ) as pool:
        results: list[Finding] = []
        for batch in pool.imap_unordered(_worker_scan, str_paths, chunksize=4):
            results.extend(batch)
        return results


def scan_git_recent_commits(
    since_hours: int,
    patterns: list[Pattern],
    workers: int,
) -> list[Finding]:
    """Scan the last N hours of git history for secret-leak markers.

    Uses `git log -p --since=NN hours ago` and feeds the patch text to the
    scanner as a single virtual file. Findings have file='<git-log>' to
    distinguish from filesystem hits.
    """
    proc = subprocess.run(  # noqa: S603 — argv is a literal list
        ["git", "log", "-p", f"--since={since_hours} hours ago", "--all"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if proc.returncode != 0:
        print(f"[fast_security_scan] git log failed: {proc.stderr}", file=sys.stderr)
        return []
    rset, rmeta, pyfb = compile_catalog(patterns)
    return scan_text("<git-log>", proc.stdout, rset, rmeta, pyfb)


# ── CLI ─────────────────────────────────────────────────────────────────────


def _resolve_workflows() -> list[Path]:
    """Find .github/workflows/*.yml under the current git repo root."""
    proc = subprocess.run(  # noqa: S603
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    if proc.returncode != 0:
        print("[fast_security_scan] not in a git repo", file=sys.stderr)
        sys.exit(2)
    root = Path(proc.stdout.strip())
    wf = root / ".github" / "workflows"
    if not wf.is_dir():
        return []
    return sorted(list(wf.glob("*.yml")) + list(wf.glob("*.yaml")))


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--catalog", type=Path, default=None, help="JSON pattern catalog (default: built-in DEFAULT_CATALOG)")
    ap.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 1), help="multiprocessing worker count (default: CPU count)")
    ap.add_argument("--format", choices=("json", "text"), default="text", help="output format (default: text)")
    ap.add_argument("--severity", choices=tuple(SEVERITY_ORDER.keys()), default="LOW", help="minimum severity to report (default: LOW)")
    ap.add_argument("--workflows", action="store_true", help="shorthand: scan .github/workflows/*.yml under git root")
    ap.add_argument("--recent-commits", type=int, default=0, metavar="HOURS", help="scan git history of the last N hours")
    ap.add_argument("files", nargs="*", type=Path, help="explicit file paths to scan")
    args = ap.parse_args(argv)

    try:
        patterns = load_catalog(args.catalog)
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"[fast_security_scan] catalog load failed: {exc}", file=sys.stderr)
        return 2

    findings: list[Finding] = []

    if args.workflows:
        findings += scan_paths(_resolve_workflows(), patterns, args.workers)

    if args.recent_commits > 0:
        findings += scan_git_recent_commits(args.recent_commits, patterns, args.workers)

    explicit = [p for p in args.files if p.is_file()]
    if explicit:
        findings += scan_paths(explicit, patterns, args.workers)

    # Severity filter
    min_sev = SEVERITY_ORDER[args.severity]
    findings = [f for f in findings if SEVERITY_ORDER.get(f.severity, 0) >= min_sev]

    # Sort: critical first, then by file + line
    findings.sort(key=lambda f: (-SEVERITY_ORDER.get(f.severity, 0), f.file, f.line, f.column))

    if args.format == "json":
        out: dict[str, Any] = {
            "patterns_in_catalog": len(patterns),
            "files_scanned": (len(_resolve_workflows()) if args.workflows else 0) + (1 if args.recent_commits > 0 else 0) + len(explicit),
            "workers": args.workers,
            "findings": [asdict(f) for f in findings],
        }
        json.dump(out, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        if not findings:
            print(f"ok 0 findings ({len(patterns)} patterns × {args.workers} workers)")
        else:
            for f in findings:
                print(f"{f.severity:8} {f.file}:{f.line}:{f.column}  {f.rule}  — {f.match[:80]}")
            print(f"\n{len(findings)} finding(s).")

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
