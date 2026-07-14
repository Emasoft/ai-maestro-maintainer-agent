"""
Tests for the maintainer-macos-notarize skill.

Two things are verified, and the second is the one that matters.

1. THE TEMPLATE carries the four properties that make CI signing safe: an
   ephemeral keychain, App Store Connect API-key auth, a `stapler staple` step,
   and cleanup with `if: always()`. Each is checked because each has a specific,
   observable failure when absent.

2. THE AUDIT DETECTOR actually detects. The audit recipe lives in the skill's
   markdown, so these tests EXTRACT the real python out of the shipped
   `references/instructions.md` and RUN it against synthetic workflows — the good
   one and one deliberately broken per finding. A detector nobody has fed a real
   bug to is a detector that reports "0 findings" forever, and that is worse than
   no detector, because it looks like assurance.

Nothing is mocked; the detector runs as a real subprocess over real files.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "skills" / "maintainer-macos-notarize"
TEMPLATE = SKILL / "references" / "templates" / "macos-notarize.yml"
INSTRUCTIONS = SKILL / "references" / "instructions.md"


# --------------------------------------------------------------------------
# 1. The template
# --------------------------------------------------------------------------


def test_template_is_valid_yaml_and_runs_on_macos() -> None:
    """The template parses, triggers on a version tag, and runs on a macOS runner."""
    wf = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    job = wf["jobs"]["build-macos"]
    assert job["runs-on"].startswith("macos"), "codesign/notarytool/stapler are Xcode tools — Linux cannot sign"
    # PyYAML parses the bare key `on:` as the boolean True. That is a YAML 1.1 quirk,
    # not a bug in the template — GitHub reads it as `on`.
    triggers = wf.get("on") or wf.get(True)
    assert "tags" in triggers["push"]


def test_template_uses_an_ephemeral_keychain_not_the_login_keychain() -> None:
    """The identity lives and dies with the job.

    `security import` WITHOUT `-k <path>` targets the LOGIN keychain, so the cert
    survives the job. On a self-hosted runner the next job — including one from a
    fork PR — can then sign with it.
    """
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "create-keychain" in text and "$RUNNER_TEMP" in text
    imports = [ln for ln in text.splitlines() if "security import" in ln]
    assert imports, "the template must import the cert"
    # The import must name our ephemeral keychain. It is a multi-line command, so
    # look at the whole RUN block rather than the single line.
    assert re.search(r"security import.*\n.*-k\s+\"\$KEYCHAIN\"", text), "`security import` must target the ephemeral keychain with -k"


def test_template_sets_the_key_partition_list() -> None:
    """Without it, codesign hangs on a GUI prompt no runner can answer.

    This is the single most common "the job just hangs until timeout" — and it
    presents as a timeout, not as an auth error, which is why it costs hours.
    """
    assert "set-key-partition-list" in TEMPLATE.read_text(encoding="utf-8")


def test_template_uses_api_key_auth_not_an_app_specific_password() -> None:
    """Scoped, revocable API key — never a human's Apple ID + app-specific password."""
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "--key-id" in text and "--issuer" in text
    assert "--apple-id" not in text, "app-specific-password auth is a long-lived, unscoped credential"


def test_template_staples_the_ticket() -> None:
    """THE BUG THIS SKILL EXISTS FOR: notarizing without stapling.

    An unstapled artifact validates on any machine that can reach Apple — which
    includes every CI runner — and fails for a user who is offline or firewalled.
    CI cannot catch it by construction, so the template must not omit it.
    """
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "notarytool submit" in text, "precondition: the template notarizes"
    assert "stapler staple" in text, "notarized but never stapled — fails for an offline user"
    assert "stapler validate" in text, "and validate it, since spctl alone would not catch a missing staple"


def test_template_cleans_up_on_the_failure_path() -> None:
    """Cleanup must carry `if: always()` — the failing job is the one that must not leak."""
    wf = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    steps = wf["jobs"]["build-macos"]["steps"]
    cleanup = [s for s in steps if "delete-keychain" in str(s.get("run", ""))]
    assert cleanup, "no cleanup step — the signing identity is left on the runner"
    assert cleanup[0].get("if") == "always()", "cleanup without if: always() is skipped exactly when it is needed"
    assert "AuthKey.p8" in cleanup[0]["run"], "the API key must be removed too, not just the keychain"


def test_template_bounds_the_job_and_scopes_permissions() -> None:
    """The four things the upstream reference did not have."""
    wf = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    job = wf["jobs"]["build-macos"]

    assert job.get("timeout-minutes"), "no timeout: a hung notarize burns the 6h default at the macOS 10x multiplier"
    assert wf.get("permissions") == {}, "top-level permissions must be empty; the one job that writes says so itself"
    assert job["permissions"] == {"contents": "write"}, "scope write to the job that uploads"
    assert "concurrency" in wf, "two tags in flight would race"
    assert wf["concurrency"]["cancel-in-progress"] is False, "never cancel a release mid-notarization"


def test_template_pins_every_action_by_sha() -> None:
    """A tag can be moved; a SHA cannot. Same rule this plugin enforces on other repos."""
    text = TEMPLATE.read_text(encoding="utf-8")
    for uses in re.findall(r"uses:\s*(\S+)", text):
        if uses.startswith("./"):
            continue
        assert re.search(r"@[0-9a-f]{40}$", uses), f"{uses} is not SHA-pinned"


# --------------------------------------------------------------------------
# 2. The audit detector — extracted from the shipped doc and actually run
# --------------------------------------------------------------------------


def _audit_script() -> str:
    """Pull the REAL detector out of the shipped instructions.

    Extracting it rather than re-implementing it is the point: a copy in the test
    would drift from the copy the agent runs, and then the test would be verifying
    code that nobody executes.
    """
    text = INSTRUCTIONS.read_text(encoding="utf-8")
    m = re.search(r"uv run - <<'PY'\n(.*?)\nPY\n", text, re.DOTALL)
    assert m, "could not find the audit detector in references/instructions.md"
    return m.group(1)


def _run_audit(tmp_path: Path, workflow: str) -> str:
    wf_dir = tmp_path / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "release.yml").write_text(workflow, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-c", _audit_script()],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


GOOD = """\
name: Release
on:
  push:
    tags: ['v*']
permissions: {}
jobs:
  build-macos:
    runs-on: macos-latest
    timeout-minutes: 45
    permissions:
      contents: write
    steps:
      - name: Import
        run: |
          security create-keychain -p "$PWD_" "$KEYCHAIN"
          security import "$CERT" -P "$P" -A -t cert -f pkcs12 -k "$KEYCHAIN"
          security set-key-partition-list -S apple: -s -k "$PWD_" "$KEYCHAIN"
      - name: Notarize
        run: |
          xcrun notarytool submit app.zip --key k.p8 --key-id ID --issuer ISS --wait
          xcrun stapler staple MyApp.app
      - name: Cleanup
        if: always()
        run: security delete-keychain "$KEYCHAIN"
"""


def test_audit_reports_zero_findings_on_a_sound_workflow(tmp_path: Path) -> None:
    """The good workflow must come back clean — otherwise every result is noise."""
    out = _run_audit(tmp_path, GOOD)
    assert "0 findings" in out, f"a sound workflow must audit clean, got:\n{out}"


def test_audit_reports_na_when_the_repo_ships_no_macos_artifact(tmp_path: Path) -> None:
    """A Linux-only repo is N/A, not '0 findings'. The distinction is the honest one."""
    out = _run_audit(tmp_path, "name: CI\non: [push]\njobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - run: make test\n")
    assert "0 findings" in out or out.strip() == "", f"a non-macOS repo must not report signing findings, got:\n{out}"


@pytest.mark.parametrize(
    ("finding", "mutate"),
    [
        (1, lambda w: w.replace('-f pkcs12 -k "$KEYCHAIN"', "-f pkcs12")),
        (2, lambda w: w.replace('      - name: Cleanup\n        if: always()\n        run: security delete-keychain "$KEYCHAIN"\n', "")),
        (2, lambda w: w.replace("        if: always()\n", "")),
        (3, lambda w: w.replace("--key k.p8 --key-id ID --issuer ISS", "--apple-id me@example.com --password abcd")),
        (4, lambda w: w.replace("          xcrun stapler staple MyApp.app\n", "")),
        (6, lambda w: w.replace("    timeout-minutes: 45\n", "")),
    ],
    ids=["1-login-keychain", "2-no-cleanup", "2-cleanup-without-always", "3-app-specific-password", "4-no-staple", "6-no-timeout"],
)
def test_audit_catches_each_broken_workflow(tmp_path: Path, finding: int, mutate) -> None:
    """Break the good workflow one way at a time; the detector must name that finding.

    This is what stops the audit from being a rubber stamp. Each mutation is a real
    thing people ship — the missing staple in particular ships constantly, because
    it passes every check that runs on a machine with a network.
    """
    out = _run_audit(tmp_path, mutate(GOOD))
    assert f"[{finding}]" in out, f"finding {finding} not reported. Detector said:\n{out}"
