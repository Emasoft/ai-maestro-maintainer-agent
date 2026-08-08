"""No ruleset this plugin applies may EVER require linear history.

USER directive, 2026-08-08, stated as a standing rule: never require linear
history in GitHub projects; no branch ruleset must ever use linear-history. It
was also ratified into the hub baseline the same day — "an unrealistic
requirement nobody was ever able to follow; development is too complex and
articulated, with many faux passes. Non-linear history is allowed in all repos."

WHY A TEST AND NOT JUST THE REMOVAL. I removed `required_linear_history` from six
carriers in v1.13.3. A removal performed once is not a rule — it is a state, and
this particular state has three ways to revert without anyone deciding to:

  1. `cpv standardize --force-templates` refreshes pipeline files from canon, and
     this repo has already had a template re-introduce something it had removed.
  2. The rule lived in a JSON ruleset TEMPLATE, the kind of file copied wholesale
     from another repo when bootstrapping a new one.
  3. It reads as a hardening measure, so a future agent tightening branch
     protection would add it back believing that is an improvement.

Each of those is silent: branch protection would simply start refusing merge
commits, and the failure surfaces as a confusing push rejection on someone else's
repo, far from the change that caused it.

WHAT IS BANNED AND WHAT IS NOT. Only the PAYLOAD forms — the shapes that actually
reach the GitHub API and change a repo. Prose is untouched, deliberately: the
skills explain WHY the rule was removed, and that explanation is what stops the
next reader re-adding it. Banning the words would delete the reasoning and leave
only the prohibition, which is the weaker artifact.

The guardian's delta watch-list is likewise exempt BY DESIGN. It names
`required_linear_history` so that a repo which acquires the rule from anywhere
gets flagged — that is enforcement of this directive, not a violation of it.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The two shapes GitHub's rulesets API accepts. Both are payloads: they change a
# repo when sent. Matching these and not the bare identifier is what keeps the
# explanatory prose legal.
PAYLOAD_FORMS = re.compile(
    r"""(?x)
    "type"\s*:\s*"required_linear_history"     # rules[] entry
  | "required_linear_history"\s*:\s*true       # flat/legacy branch-protection body
    """
)

# design/archived/ is a historical record: those TRDDs describe the baseline as it
# was when they were written, and rewriting them would falsify the record. They
# ship nothing and apply nothing.
SCANNED = ("skills", "commands", "agents", "scripts", "hooks", "design/requirements")


def _files() -> list[Path]:
    out: list[Path] = []
    for d in SCANNED:
        root = REPO / d
        if root.is_dir():
            out.extend(p for p in root.rglob("*") if p.is_file() and p.suffix in {".md", ".json", ".py", ".yml"})
    return sorted(out)


def test_no_shipped_surface_carries_a_linear_history_payload() -> None:
    """The standing USER rule, enforced where it can actually take effect."""
    offenders = [f"{p.relative_to(REPO)}: {m.group(0)}" for p in _files() for m in PAYLOAD_FORMS.finditer(p.read_text(encoding="utf-8", errors="replace"))]
    assert not offenders, f"a ruleset payload requires linear history, which the USER has forbidden outright (2026-08-08): {offenders}. Non-linear history is allowed in ALL repos. Remove the rule — do not add a bypass actor, and do not make it conditional: the directive has no exceptions."


def test_the_payload_detector_matches_both_api_shapes() -> None:
    """Positive control — a prohibition test that cannot fire is decoration."""
    assert PAYLOAD_FORMS.search('{ "type": "required_linear_history" }')
    assert PAYLOAD_FORMS.search('"required_linear_history": true')
    assert PAYLOAD_FORMS.search('{"type":"required_linear_history"}')  # no spaces


def test_the_detector_leaves_the_explanation_and_the_monitor_alone() -> None:
    """Prose and the guardian's watch-list must stay legal.

    If this test ever fails, someone widened the pattern to the bare identifier —
    which would force the removal of the text explaining WHY the rule is banned,
    and of the guardian entry that detects it being re-added. Both make the ban
    weaker, so both are protected here rather than left to reviewer discretion.
    """
    assert not PAYLOAD_FORMS.search("`required_linear_history` was removed by USER ruling 2026-08-08")
    assert not PAYLOAD_FORMS.search("the rule-type list (deletion, non_fast_forward, required_linear_history, ...)")
    assert not PAYLOAD_FORMS.search("| `baseline-history-protect` | `deletion`, `non_fast_forward` |")


def test_the_scan_reaches_the_ruleset_templates() -> None:
    """A guard over an empty or wrong file set passes while checking nothing.

    Pinned to the template directory specifically because that is where the rule
    actually lived, and where a wholesale copy would put it back.
    """
    scanned = _files()
    assert len(scanned) > 50, f"only {len(scanned)} files scanned — the globs stopped matching"
    names = {p.name for p in scanned}
    assert "ruleset-no-force-no-delete.json" in names, "the history-protect ruleset template is not in the scan, so the one file most likely to reintroduce the rule is unchecked"
