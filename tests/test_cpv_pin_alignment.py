"""The CPV validator pin must be identical in publish.py and both workflows.

TRDD-O5D54XLG set out to "align the CPV validator ref across all pipeline
callsites" and was marked complete on 2026-07-03. On 2026-08-07 it was measured
drifted again: `.github/workflows/{ci,release}.yml` had been re-pinned to
v2.158.0 while `scripts/publish.py` still carried v2.152.1 in three executable
call sites and a docstring.

Why that matters more than a stale string: publish.py's gate is the LOCAL
push guard and the workflows are the REMOTE one. When they run different
validator builds, a plugin can pass the push gate and fail CI (or the reverse)
and neither failure explains itself — the two gates are not testing the same
contract. The drift is silent by construction because each side is internally
consistent.

The original fix aligned the strings; it could drift again because there were
four copies. This file plus the CPV_REF constant is the durable half: one
definition in publish.py, and this test failing the build the moment a workflow
disagrees with it. Alignment that is only ever asserted once is a snapshot;
alignment that is asserted on every run is an invariant.

No mocks: reads the real publish.py and the real workflow YAML.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import publish  # scripts/ is on sys.path via conftest

REPO = Path(__file__).resolve().parents[1]
WORKFLOWS = (".github/workflows/ci.yml", ".github/workflows/release.yml")

# The `uvx --from git+https://github.com/<owner>/claude-plugins-validation@<ref>`
# form, in either a YAML `run:` block or python source.
CPV_PIN = re.compile(r"git\+https://github\.com/[\w.-]+/claude-plugins-validation@(?P<ref>[\w.+-]+)")


def _pins_in(path: Path) -> list[str]:
    return CPV_PIN.findall(path.read_text(encoding="utf-8"))


def test_publish_defines_a_single_cpv_ref() -> None:
    """publish.py pins the validator ONCE, via the CPV_REF constant."""
    assert hasattr(publish, "CPV_REF"), "publish.CPV_REF is gone — the single source of truth"
    match = CPV_PIN.search(publish.CPV_REF)
    assert match, f"CPV_REF is not a pinned git+https ref: {publish.CPV_REF!r}"


def test_publish_py_carries_no_second_hardcoded_pin() -> None:
    """No call site may re-spell the pin — that is how it drifted the first time."""
    pins = set(_pins_in(REPO / "scripts" / "publish.py"))
    expected = {CPV_PIN.search(publish.CPV_REF).group("ref")}  # type: ignore[union-attr]
    assert pins <= expected, f"publish.py hardcodes {sorted(pins - expected)} alongside CPV_REF ({sorted(expected)}). Use the constant so there is one place to bump."


@pytest.mark.parametrize("workflow", WORKFLOWS)
def test_workflow_pin_matches_publish(workflow: str) -> None:
    """CI and the local gate must fetch the SAME validator build."""
    path = REPO / workflow
    assert path.is_file(), f"{workflow} is missing — this test would silently pass"
    pins = set(_pins_in(path))
    assert pins, f"{workflow} pins no CPV ref — did the invocation move or get removed?"
    expected = CPV_PIN.search(publish.CPV_REF).group("ref")  # type: ignore[union-attr]
    assert pins == {expected}, f"{workflow} pins {sorted(pins)} but publish.CPV_REF pins {expected!r}. The local push gate and CI would validate against different builds, so one can pass while the other fails with no explanation. Bump both."


def test_the_pin_detector_actually_detects_a_pin() -> None:
    """The regex must bite, or every assertion above is vacuously true."""
    assert CPV_PIN.search("uvx --from git+https://github.com/Emasoft/claude-plugins-validation@v2.158.0 --with pyyaml").group("ref") == "v2.158.0"  # type: ignore[union-attr]
    # ...and must not claim a pin where there is none.
    assert not CPV_PIN.search("uvx --from git+https://github.com/Emasoft/some-other-tool@v1.0.0")
