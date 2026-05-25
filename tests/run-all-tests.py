#!/usr/bin/env python3
"""
Test runner for ai-maestro-maintainer-agent.

CPV's publish.py G4 gate invokes this runner. Exit codes:
  0 — every test passed (or was legitimately skipped on a missing dep)
  1 — at least one test failed
  2 — runner itself errored before getting to the gate decision

Output: a Unicode-bordered result table with PASS / FAIL / SKIP / ERROR
per test function plus the one-line docstring of each test. Header row
uses ━ (heavy box-drawing); data rows use ─ (light box-drawing). The
last line is `N/M passed.` so a glance tells the reader pass/total.

No leaks: pytest itself owns subprocess lifecycle inside its plugins.
The runner only spawns ONE pytest subprocess and waits for it to exit.

Slow tests are marked with the 🐌 emoji in the function name per
~/.claude/CLAUDE.md test-related rules.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

ANSI_RESET = "\033[0m"
ANSI_GREEN = "\033[32m"
ANSI_RED = "\033[31m"
ANSI_YELLOW = "\033[33m"
ANSI_CYAN = "\033[36m"
ANSI_BOLD = "\033[1m"

USE_COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def _c(code: str, text: str) -> str:
    """Color text iff stdout is a TTY and NO_COLOR is not set."""
    return f"{code}{text}{ANSI_RESET}" if USE_COLOR else text


def collect_test_docstrings() -> dict[str, str]:
    """Parse the test files manually for `def test_*(...)` + docstring.

    Returns a map from `<module>::<func>` → first-line docstring.
    Manual parsing avoids importing the test modules (which would
    trigger fixture autouse and side-effects).
    """
    docs: dict[str, str] = {}
    for tf in sorted(ROOT.glob("test_*.py")):
        mod = tf.stem
        src = tf.read_text()
        lines = src.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()
            if stripped.startswith("def test_"):
                # Find the function name
                name_start = stripped.find("def test_") + len("def ")
                paren = stripped.find("(", name_start)
                if paren < 0:
                    i += 1
                    continue
                func_name = stripped[name_start:paren]
                # The signature may span multiple lines — advance until we
                # find the line ending with `:`.
                j = i
                while j < len(lines) and not lines[j].rstrip().endswith(":"):
                    j += 1
                # Walk down past the signature to the first non-blank line.
                j = j + 1
                while j < len(lines) and lines[j].strip() == "":
                    j += 1
                docstring_line = lines[j].strip() if j < len(lines) else ""
                # Strip a leading string-literal prefix (r/u/b/f, any case) so
                # raw docstrings like r"""...\n...""" are recognised, not just
                # plain triple-quoted ones.
                if len(docstring_line) >= 4 and docstring_line[0] in "rRuUbBfF" and docstring_line[1:4] in ('"""', "'''"):
                    docstring_line = docstring_line[1:]
                # Extract first NON-EMPTY line of docstring
                doc = ""
                if docstring_line.startswith('"""') or docstring_line.startswith("'''"):
                    quote = docstring_line[:3]
                    inner = docstring_line[3:]
                    # Single-line docstring like """Foo bar."""
                    if quote in inner:
                        doc = inner.split(quote)[0].strip()
                    elif inner.strip():
                        # First line has text after the opening quote.
                        doc = inner.strip()
                    else:
                        # Opening quote on its own line — walk down to first
                        # non-empty content line.
                        k = j + 1
                        while k < len(lines):
                            ll = lines[k].strip()
                            if ll == "":
                                k += 1
                                continue
                            if ll.startswith(quote):
                                # Empty docstring closes immediately
                                break
                            # Strip a trailing closing-quote on the same line.
                            content = ll
                            if content.endswith(quote):
                                content = content[:-3].rstrip()
                            doc = content
                            break
                docs[f"{mod}::{func_name}"] = doc or "(no docstring)"
            i += 1
    return docs


def parse_pytest_report(report_path: Path) -> list[dict]:
    """Parse pytest's --report-log JSONL into a list of test result rows."""
    rows: list[dict] = []
    seen: dict[str, dict] = {}
    if not report_path.exists():
        return rows
    for raw_line in report_path.read_text().splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            entry = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if entry.get("$report_type") != "TestReport":
            continue
        nodeid = entry.get("nodeid", "")
        # nodeid format depends on pytest rootdir: it can be
        #   "tests/test_foo.py::test_bar" (run from project root) OR
        #   "test_foo.py::test_bar"       (run from tests/ as rootdir)
        # Accept any nodeid that contains "::" (the func separator).
        if "::" not in nodeid:
            continue
        when = entry.get("when")
        outcome = entry.get("outcome")
        # We want the final-state row for each test:
        #   * if call ran → use call outcome
        #   * if setup failed/skipped → use that
        prev = seen.get(nodeid)
        if when == "setup" and outcome in ("failed", "skipped"):
            # Setup failure / skip — this IS the final outcome for that test.
            seen[nodeid] = {
                "nodeid": nodeid,
                "outcome": outcome,
                "longrepr": entry.get("longrepr"),
            }
        elif when == "call":
            seen[nodeid] = {
                "nodeid": nodeid,
                "outcome": outcome,
                "longrepr": entry.get("longrepr"),
            }
        elif when == "setup" and outcome == "passed" and prev is None:
            # Track for later in case call doesn't run.
            seen[nodeid] = {
                "nodeid": nodeid,
                "outcome": outcome,
                "longrepr": None,
            }
    rows = list(seen.values())
    return rows


def render_table(rows: list[dict], docs: dict[str, str]) -> str:
    """Render the Unicode-bordered result table."""
    if not rows:
        return _c(ANSI_RED, "No test results collected — runner failure.")

    # Compute column widths.
    name_strs: list[str] = []
    desc_strs: list[str] = []
    status_strs: list[str] = []
    plain_rows: list[tuple[str, str, str, str]] = []
    # plain_rows holds the COLORED versions for printing but we measure
    # widths from the PLAIN form.

    for r in rows:
        nodeid = r["nodeid"]
        # nodeid is "tests/test_foo.py::test_bar" — extract "test_foo::test_bar"
        path_part, _, func = nodeid.partition("::")
        mod = Path(path_part).stem
        name = f"{mod}::{func}"
        desc = docs.get(name, "(no docstring)")
        outcome = r["outcome"]
        # Map to status label
        status_map = {
            "passed": ("PASS", ANSI_GREEN),
            "failed": ("FAIL", ANSI_RED),
            "skipped": ("SKIP", ANSI_YELLOW),
            "error": ("ERROR", ANSI_RED),
        }
        label, color = status_map.get(outcome, ("?", ANSI_RED))
        name_strs.append(name)
        desc_strs.append(desc)
        status_strs.append(label)
        plain_rows.append((name, label, color, desc))

    name_w = max(len("Test"), max(len(s) for s in name_strs))
    status_w = 6  # exactly 6 chars per CLAUDE.md
    desc_w = max(len("Description"), max(len(s) for s in desc_strs))

    # Cap desc width so very long docstrings don't blow out the terminal.
    desc_w = min(desc_w, 80)

    HHL = "━"  # heavy horizontal
    LHL = "─"  # light horizontal
    HV = "┃"
    LV = "│"
    H_TL, H_TR, H_BL, H_BR = "┏", "┓", "┡", "┩"  # heavy outer corners
    H_TT, H_BT = "┳", "╇"
    L_BL, L_BR = "└", "┘"  # light bottom corners only
    L_BT = "┴"

    lines: list[str] = []

    def hline(left: str, mid: str, right: str, fill: str) -> str:
        return left + fill * (name_w + 2) + mid + fill * (status_w + 2) + mid + fill * (desc_w + 2) + right

    header_top = hline(H_TL, H_TT, H_TR, HHL)
    header_sep = hline(H_BL, H_BT, H_BR, HHL)
    bottom = hline(L_BL, L_BT, L_BR, LHL)

    lines.append(header_top)
    header = f"{HV} {_c(ANSI_BOLD, 'Test'.ljust(name_w))} {HV} {_c(ANSI_BOLD, 'Status'.ljust(status_w))} {HV} {_c(ANSI_BOLD, 'Description'.ljust(desc_w))} {HV}"
    lines.append(header)
    lines.append(header_sep)

    for name, label, color, desc in plain_rows:
        truncated_desc = desc if len(desc) <= desc_w else desc[: desc_w - 1] + "…"
        line = f"{LV} {name.ljust(name_w)} {LV} {_c(color, label.ljust(status_w))} {LV} {truncated_desc.ljust(desc_w)} {LV}"
        lines.append(line)

    lines.append(bottom)
    return "\n".join(lines)


def main() -> int:
    """Run pytest, render the table, exit with the right code."""
    # 1) Ensure a venv with pytest. The orchestrator runs us via
    #    `uv run --with pytest pytest`, but when invoked stand-alone we
    #    fall back to spawning `uv run --with pytest pytest` ourselves.
    report_path = ROOT / ".pytest-report.jsonl"
    if report_path.exists():
        report_path.unlink()

    # Resolve interpreter: prefer `uv run` for hermetic pytest, else use
    # the current interpreter (assume pytest is on the path).
    cmd: list[str]
    if os.environ.get("PYTEST_RAN_BY_RUNNER") == "1":
        # We're being called recursively — should not happen, but guard.
        return 2
    env = os.environ.copy()
    env["PYTEST_RAN_BY_RUNNER"] = "1"
    if os.environ.get("USE_BARE_PYTEST") == "1":
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(ROOT),
            f"--report-log={report_path}",
            "-q",
            "--tb=short",
            "--no-header",
        ]
    else:
        cmd = [
            "uv",
            "run",
            "--with",
            "pytest",
            "--with",
            "pytest-reportlog",
            "--with",
            "pyyaml",
            "--",
            "pytest",
            str(ROOT),
            f"--report-log={report_path}",
            "-q",
            "--tb=short",
            "--no-header",
        ]

    print(_c(ANSI_CYAN, f"Running: {' '.join(cmd)}"))
    proc = subprocess.run(cmd, cwd=ROOT.parent, env=env)
    pytest_rc = proc.returncode

    rows = parse_pytest_report(report_path)
    docs = collect_test_docstrings()

    print()
    print(render_table(rows, docs))
    print()

    total = len(rows)
    passed = sum(1 for r in rows if r["outcome"] == "passed")
    failed = sum(1 for r in rows if r["outcome"] in ("failed", "error"))
    skipped = sum(1 for r in rows if r["outcome"] == "skipped")

    summary_color = ANSI_GREEN if failed == 0 else ANSI_RED
    print(_c(summary_color, _c(ANSI_BOLD, f"{passed}/{total} passed.")))
    if skipped:
        print(_c(ANSI_YELLOW, f"{skipped} skipped."))
    if failed:
        print(_c(ANSI_RED, f"{failed} failed."))

    # Exit 0 iff pytest itself was happy. pytest returns 5 when no tests
    # were collected — that's also a failure for our purposes.
    if pytest_rc == 0:
        return 0
    if pytest_rc == 5:
        print(_c(ANSI_RED, "ERROR: pytest collected zero tests"), file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
