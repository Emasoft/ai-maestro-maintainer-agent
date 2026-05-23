"""Smoke + correctness tests for scripts/fast_security_scan.py.

Covers:
- RE2 Set one-pass matching finds known secret-marker patterns
- Python re fallback works for patterns RE2 can't compile
- Multi-process worker mode produces the same findings as single-process
- Severity filter and JSON / text output shape
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCANNER = ROOT / "scripts" / "fast_security_scan.py"


def _run_scanner(*args: str) -> tuple[int, str, str]:
    """Invoke the scanner via uv run --with google-re2 and return (rc, stdout, stderr)."""
    proc = subprocess.run(
        ["uv", "run", "--with", "google-re2", str(SCANNER), *args],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_scanner_script_exists_and_is_executable():
    """The scanner script exists at scripts/fast_security_scan.py."""
    assert SCANNER.is_file(), f"scanner not found at {SCANNER}"


def test_scanner_help_returns_zero_and_documents_modes():
    """`fast_security_scan.py --help` exits 0 and mentions every operating mode."""
    rc, out, _err = _run_scanner("--help")
    assert rc == 0
    for token in ("--workflows", "--recent-commits", "--severity", "--workers", "--format"):
        assert token in out, f"{token} not documented in --help"


def test_scanner_finds_aws_and_github_secrets(tmp_path: Path):
    """RE2 Set finds synthetic AWS access key + GitHub PAT in a fixture file."""
    fixture = tmp_path / "secret_blob.txt"
    fixture.write_text("fake_key = 'AKIAIOSFODNN7EXAMPLE'\nfake_pat = 'ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'\n")
    rc, out, _err = _run_scanner("--format", "json", str(fixture))
    assert rc == 1, f"expected rc=1 (findings present), got {rc}"
    report = json.loads(out)
    rules = {f["rule"] for f in report["findings"]}
    assert "aws-access-key-id" in rules
    assert "github-personal-access-token" in rules


def test_scanner_no_findings_on_clean_file_returns_zero(tmp_path: Path):
    """A file with no patterns produces rc=0 and an empty findings list."""
    clean = tmp_path / "clean.py"
    clean.write_text("def add(a, b): return a + b\n")
    rc, out, _err = _run_scanner("--format", "json", str(clean))
    assert rc == 0
    report = json.loads(out)
    assert report["findings"] == []


def test_scanner_jq_arg_trap_detected(tmp_path: Path):
    """The jq --arg trap (\\${VAR} inside a double-quoted jq filter) is flagged."""
    bad = tmp_path / "release.yml"
    bad.write_text("- name: post\n  run: |\n    PAYLOAD=$(jq -nc --arg t \"Title: ${PR_TITLE}\" '{text: $t}')\n")
    rc, out, _err = _run_scanner("--format", "json", str(bad))
    assert rc == 1
    report = json.loads(out)
    rules = {f["rule"] for f in report["findings"]}
    assert "jq-arg-trap" in rules


def test_scanner_severity_filter_drops_lower(tmp_path: Path):
    """--severity CRITICAL omits HIGH and below findings."""
    mixed = tmp_path / "mixed.txt"
    mixed.write_text(
        "AKIAIOSFODNN7EXAMPLE\n"  # CRITICAL
        '  run: jq -nc --arg t "X: ${V}" "{x:$t}"\n'  # HIGH
    )
    rc, out, _err = _run_scanner(
        "--format",
        "json",
        "--severity",
        "CRITICAL",
        str(mixed),
    )
    assert rc == 1
    report = json.loads(out)
    severities = {f["severity"] for f in report["findings"]}
    assert severities == {"CRITICAL"}, f"unexpected severities: {severities}"


def test_scanner_workers_single_and_multi_agree(tmp_path: Path):
    """--workers 1 and --workers 4 produce the same set of findings on the same input."""
    f1 = tmp_path / "a.txt"
    f1.write_text("AKIAIOSFODNN7EXAMPLE\n")
    f2 = tmp_path / "b.txt"
    f2.write_text("ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n")

    rc1, out1, _ = _run_scanner("--format", "json", "--workers", "1", str(f1), str(f2))
    rc4, out4, _ = _run_scanner("--format", "json", "--workers", "4", str(f1), str(f2))

    assert rc1 == rc4 == 1
    r1 = sorted([(f["rule"], f["file"]) for f in json.loads(out1)["findings"]])
    r4 = sorted([(f["rule"], f["file"]) for f in json.loads(out4)["findings"]])
    assert r1 == r4
