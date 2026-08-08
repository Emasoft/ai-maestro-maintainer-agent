#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Detect drift in the hub governance artifacts this plugin is bound by.

WHY THIS EXISTS. On 2026-08-08 three sessions in this fleet, independently, cited
a governance rule that had moved underneath them. One (mine) shipped a wrong verb
list; another retracted a claim that was true; a third circulated a summary that
was accurate when written. Nobody was careless — the artifact simply changed
faster than anyone re-read it, and nothing local could see that.

THE CHANGE SIGNAL IS THE PER-FILE BLOB SHA, NEVER THE BRANCH COMMIT SHA. The
hub's `3-pillars-spec.md` clause `3P-VER-05` forbids the branch sha outright, and
the reason is that it fails in the DANGEROUS direction: a branch sha moves on
every unrelated commit, so a consumer polls, sees movement, refetches a
byte-identical document, and records "checked, current" — manufacturing
confidence instead of supplying information. Silence would be safer than that. A
blob sha changes if and only if those bytes change.

WHY SIX FILES AND NOT ONE. `GOVERNANCE-RULES.md` carries a `spec-version`, but the
five DEP overlays under `rules/aimaestro/` carry NO version field, so an
overlay-only edit moves no number anywhere. Watching the rule catalog alone would
miss it silently. Six blobs are the complete fingerprint.

Exit codes are the interface, so a caller can gate on them without parsing:
    0  every watched artifact matches the baseline
    3  drift detected — at least one blob moved (or an artifact vanished)
    4  could not determine (network/auth failure) — NOT the same as "no drift",
       because reporting "clean" from a failed fetch is the exact false-negative
       this file exists to prevent.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = "Emasoft/ai-maestro"
REF = "governance-rules"

# The rule catalog plus the five DEP overlays. The overlays carry no version
# field, which is precisely why they are watched by blob rather than by version.
WATCHED = (
    # NORMATIVE first (ruled 2026-08-08, ai-maestro#37): the spec's granular
    # renderings are the norm and `docs/GOVERNANCE-RULES.md` is its PROVENANCE.
    # Watching only the doc meant watching the record of the decision rather than
    # the decision — the doc can lag the spec, and a consumer polling the lagging
    # copy sees nothing while the norm has already moved.
    "design/specs/governance-spec.md",
    "docs/GOVERNANCE-RULES.md",
    "rules/aimaestro/aimaestro-agent-rules.md",
    "rules/aimaestro/aimaestro-kanban-multiagent.md",
    "rules/aimaestro/aimaestro-manager-approval-defaults.md",
    "rules/aimaestro/aimaestro-prrd-governance.md",
    "rules/aimaestro/aimaestro-trdd-approval.md",
)

BASELINE = Path(__file__).resolve().parents[1] / "design" / "governance-baseline.json"


def compare(baseline: dict[str, str], current: dict[str, str | None]) -> list[str]:
    """Report lines for every watched path whose blob differs from the baseline.

    PURE — no network, no filesystem. This is the part worth testing, and keeping
    it pure is what makes it testable without mocking a hub that would then prove
    nothing about the real one.

    A path absent from `current` (fetch returned nothing) is reported as UNKNOWN
    rather than silently skipped: an artifact we could not read is not an
    artifact that agrees with us.
    """
    out: list[str] = []
    for path in sorted(set(baseline) | set(current)):
        want = baseline.get(path)
        got = current.get(path)
        if got is None:
            out.append(f"UNKNOWN  {path}  (baseline {want or '-'}, fetch returned nothing)")
        elif want is None:
            out.append(f"NEW      {path}  (now {got[:12]}, absent from baseline)")
        elif want != got:
            out.append(f"DRIFT    {path}  ({want[:12]} -> {got[:12]})")
    return out


def fetch_blob(path: str) -> str | None:
    """The blob sha of one file at REF, or None when it cannot be determined."""
    try:
        res = subprocess.run(
            ["gh", "api", f"repos/{REPO}/contents/{path}?ref={REF}", "--jq", ".sha"],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = res.stdout.strip()
    return sha if res.returncode == 0 and sha else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--update", action="store_true", help="rewrite the baseline from the current blobs")
    args = ap.parse_args()

    current = {p: fetch_blob(p) for p in WATCHED}
    unresolved = [p for p, s in current.items() if s is None]

    if args.update:
        if unresolved:
            print(f"refusing to write a baseline with {len(unresolved)} unresolved blob(s): {unresolved}")
            return 4
        BASELINE.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"baseline written: {BASELINE}")
        return 0

    if not BASELINE.is_file():
        print(f"no baseline at {BASELINE} — run with --update to record one")
        return 4

    findings = compare(json.loads(BASELINE.read_text(encoding="utf-8")), current)
    if unresolved and not [f for f in findings if not f.startswith("UNKNOWN")]:
        # Nothing moved among what we COULD read, but we could not read everything.
        for line in findings:
            print(line)
        print(f"cannot determine: {len(unresolved)} artifact(s) unreadable")
        return 4
    if findings:
        for line in findings:
            print(line)
        print(f"\n{len(findings)} governance artifact(s) changed — re-read the ROW before citing it.")
        return 3
    print(f"clean: all {len(WATCHED)} governance artifacts match the baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
