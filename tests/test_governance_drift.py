"""The pure comparison in scripts/governance_drift.py.

Only `compare()` is tested, and deliberately so: it is the whole decision. The
fetch half shells out to `gh`, and a mocked hub would prove nothing about the real
one — it would only assert that my fake returns what I told it to.

The cases below are the ones that decide whether this detector is worth having.
The dangerous direction is a FALSE CLEAN: a governance artifact moved, or could
not be read, and the tool says "clean" — because a caller gating on exit 0 then
proceeds to cite a rule that changed. Every test here is aimed at that.
"""

from __future__ import annotations

from governance_drift import WATCHED, compare  # scripts/ is on sys.path via conftest

A = "a" * 40
B = "b" * 40


def test_identical_maps_report_nothing() -> None:
    """The only case that may be silent."""
    assert compare({"x": A}, {"x": A}) == []


def test_a_changed_blob_is_reported_with_both_shas() -> None:
    """DRIFT names old and new so a reader can diff without re-fetching."""
    (line,) = compare({"x": A}, {"x": B})
    assert line.startswith("DRIFT")
    assert A[:12] in line and B[:12] in line


def test_an_unreadable_artifact_is_not_silence() -> None:
    """A fetch that returned nothing must NOT read as agreement.

    This is the false-clean the file exists to prevent: `None` means we could not
    look, which is not the same as looking and finding no change.
    """
    (line,) = compare({"x": A}, {"x": None})
    assert line.startswith("UNKNOWN")


def test_an_artifact_missing_from_the_baseline_is_reported() -> None:
    """A newly watched path is surfaced rather than absorbed."""
    (line,) = compare({}, {"x": A})
    assert line.startswith("NEW")


def test_a_baseline_path_absent_from_the_fetch_is_reported() -> None:
    """Dropping a path from the fetch must not quietly shrink the watch set."""
    (line,) = compare({"x": A}, {})
    assert line.startswith("UNKNOWN")


def test_only_the_changed_path_is_reported_among_many() -> None:
    """A real run compares six paths; one moving must not flag the other five."""
    base = {p: A for p in WATCHED}
    cur = dict(base)
    cur[WATCHED[3]] = B
    findings = compare(base, cur)
    assert len(findings) == 1
    assert WATCHED[3] in findings[0]


def test_the_watch_set_covers_the_catalog_and_all_five_overlays() -> None:
    """Six blobs are the complete fingerprint.

    The overlays carry NO version field, so watching only the versioned catalog
    would miss an overlay-only edit with nothing anywhere reporting a change.
    """
    assert len(WATCHED) == 6
    assert sum(1 for p in WATCHED if p.startswith("rules/aimaestro/")) == 5
    assert "docs/GOVERNANCE-RULES.md" in WATCHED


def test_the_comparison_is_order_independent() -> None:
    """Findings are sorted, so output is stable and diffable across runs."""
    base = {"b": A, "a": A}
    cur = {"a": B, "b": B}
    assert [line.split()[1] for line in compare(base, cur)] == ["a", "b"]
