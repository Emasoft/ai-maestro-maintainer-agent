"""
Skill-doc contract tests for EVERY skill this plugin ships.

No mocks. Every assertion runs against the REAL shipped SKILL.md + its
references/ on disk. The universal contract (parametrized over `SHIPPED_SKILLS`,
which is globbed from `skills/*/SKILL.md`) checks each skill's frontmatter
validity, the no-tool-grant-frontmatter invariant (ADR-0002 / PRRD S7), the
presence of the core body sections, and that every `references/...` link in the
body resolves to a real file (broken-reference guard). Per-skill tests below add
the structural invariant unique to each skill.

Consistent with this repo's grouped-test convention (test_sentinel_rules_a..f
cover many rules in one module): one table-driven module gives every skill real,
regression-catching coverage without a near-duplicate stub file per skill.

NEITHER THE COUNT NOR THE MEMBERSHIP IS WRITTEN OUT HERE, and both omissions are
the same lesson learned twice. A hardcoded total went stale first (it read "20"
while the table held 21), so the count was deleted and the hand-maintained list
was declared the source of truth. The list then went stale too — 24 names against
32 skills on disk — leaving eight skills with no contract coverage and nothing to
report it, because a parametrized test over a short list passes exactly like a
complete one. The scope of a whole-corpus guard has to be DERIVED, or it decays
into a snapshot of the day it was written.
"""

from __future__ import annotations

import re

import pytest
import yaml

from conftest import REPO_ROOT

SKILLS_ROOT = REPO_ROOT / "skills"

# EVERY skill that ships, discovered from disk. Never a hand-maintained list.
#
# It WAS a hand-maintained list, with a comment instructing the next author to
# append to it. That instruction was followed once and then missed eight times:
# by 2026-08-11 the table held 24 names while 32 skills shipped, so
# maintainer-approval-gate, -commit-msg-why, -guardian, -macos-notarize, -redact,
# -sandbox, -worktree and workflow-bootstrap had NO contract coverage — silently,
# because a parametrized test over a short list is green in exactly the way a
# complete one is.
#
# The module docstring already recorded this failure one level down: a hardcoded
# COUNT went stale ("20" while the table held 21), and the fix was to delete the
# count and call the list the single source of truth. The list was the same bug
# with a slower clock. A test whose SCOPE is hand-maintained decays toward
# testing whatever existed the day it was written, and nothing reports the decay
# — so the scope has to come from the filesystem.
SHIPPED_SKILLS = sorted(p.parent.name for p in SKILLS_ROOT.glob("*/SKILL.md"))

TOOL_GRANT_KEYS = ("allowed-tools", "disallowed-tools", "tools")


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body) for a SKILL.md. Frontmatter is the YAML
    between the first two `---` delimiters."""
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    assert m, "SKILL.md must open with a --- frontmatter block"
    fm = yaml.safe_load(m.group(1)) or {}
    return fm, m.group(2)


def _skill_text(skill: str) -> str:
    p = SKILLS_ROOT / skill / "SKILL.md"
    assert p.is_file(), f"missing SKILL.md for {skill}"
    return p.read_text(encoding="utf-8")


# ─────────────────────── the scope guard (read this first) ───────────────────────


def test_the_contract_scope_is_derived_and_covers_every_shipped_skill() -> None:
    """The parametrized corpus must equal what is on disk, re-derived here.

    This is the test that was missing for the eight skills that shipped without
    contract coverage. It is deliberately NOT `assert SHIPPED_SKILLS ==
    SHIPPED_SKILLS`: it walks the filesystem again, independently, so the
    assertion still bites if someone replaces the glob with a literal list —
    which is exactly how the coverage was lost the first time. A hand-written
    list can be correct on the day it lands; what it cannot be is self-maintaining.

    It also refuses an EMPTY corpus. A glob that stops matching (a moved skills/
    root, a renamed SKILL.md) would make all four parametrized contracts vacuous
    and every one of them would still report green — the failure mode that makes
    a broken guard indistinguishable from a satisfied one.
    """
    on_disk = {p.parent.name for p in SKILLS_ROOT.glob("*/SKILL.md")}
    assert on_disk, f"no skills discovered under {SKILLS_ROOT} — every contract below is vacuous"
    assert len(on_disk) >= 25, f"only {len(on_disk)} skills found; the glob has probably stopped matching"
    missing = sorted(on_disk - set(SHIPPED_SKILLS))
    assert not missing, (
        f"{len(missing)} shipped skill(s) are outside the contract's scope: {missing}. "
        "If SHIPPED_SKILLS was turned back into a hand-maintained list, that is the bug — "
        "derive it from the filesystem instead of appending."
    )


# ─────────────────────────── universal contract ───────────────────────────


@pytest.mark.parametrize("skill", SHIPPED_SKILLS)
def test_frontmatter_valid_with_nonempty_description(skill: str) -> None:
    """Every skill's frontmatter parses as YAML and carries a non-empty description."""
    fm, _ = _split_frontmatter(_skill_text(skill))
    assert "description" in fm, f"{skill}: no description in frontmatter"
    assert str(fm["description"]).strip(), f"{skill}: empty description"


@pytest.mark.parametrize("skill", SHIPPED_SKILLS)
def test_no_tool_grant_frontmatter(skill: str) -> None:
    """No skill declares allowed-tools/disallowed-tools/tools (ADR-0002 / PRRD S7).

    This is the regression guard for the M4 finding (kanban's allowed-tools);
    it holds the whole skill set to the invariant, not just the one that drifted.
    """
    fm, _ = _split_frontmatter(_skill_text(skill))
    present = [k for k in TOOL_GRANT_KEYS if k in fm]
    assert not present, f"{skill}: forbidden tool-grant frontmatter key(s): {present}"


@pytest.mark.parametrize("skill", SHIPPED_SKILLS)
def test_has_core_body_sections(skill: str) -> None:
    """Each skill documents at least an Overview/Instructions plus a Scope or Resources."""
    _, body = _split_frontmatter(_skill_text(skill))
    headings = set(re.findall(r"^##\s+(.+?)\s*$", body, re.M))
    h_lower = {h.lower() for h in headings}
    assert h_lower & {"overview", "instructions"}, f"{skill}: no Overview/Instructions section"
    assert h_lower & {"scope", "resources", "output"}, f"{skill}: no Scope/Resources/Output section"


@pytest.mark.parametrize("skill", SHIPPED_SKILLS)
def test_referenced_files_resolve(skill: str) -> None:
    """Every STANDALONE-LOCAL `references/<file>.md` link in the SKILL body exists.

    The negative lookbehind restricts matching to a `references/` that is NOT
    part of a longer path — so cross-skill links
    (`maintainer-approval-gate/references/protected-paths.md`,
    `skills/maintainer-triage/references/...`) and directory/glob mentions
    (`references/templates/`) are intentionally out of scope here; this test
    guards the skill's OWN local `.md` references against rot.
    """
    skill_dir = SKILLS_ROOT / skill
    _, body = _split_frontmatter(_skill_text(skill))
    refs = set(re.findall(r"(?<![\w./-])references/([A-Za-z0-9._\-]+\.md)", body))
    missing = [r for r in refs if not (skill_dir / "references" / r).is_file()]
    assert not missing, f"{skill}: broken local references/ link(s): {missing}"


# ─────────────────────────── per-skill invariants ───────────────────────────


def test_tooling_bootstrap_covers_all_platform_ids() -> None:
    """install-recipes documents every supported platform ID for the mandatory tools."""
    recipes = (SKILLS_ROOT / "maintainer-tooling-bootstrap" / "references" / "install-recipes.md").read_text()
    for plat in ("macos", "apt", "dnf", "pacman", "apk"):
        assert f"`{plat}`" in recipes, f"install-recipes missing platform ID: {plat}"


def test_config_lint_covers_core_formats() -> None:
    """per-format-linters documents the headline config formats."""
    linters = (SKILLS_ROOT / "maintainer-config-lint" / "references" / "per-format-linters.md").read_text().lower()
    for fmt in ("json", "yaml", "toml"):
        assert fmt in linters, f"per-format-linters missing format: {fmt}"


def test_protect_branch_names_all_three_baseline_rulesets() -> None:
    """workflow-protect-branch documents the full ratified ruleset triple."""
    text = _skill_text("workflow-protect-branch")
    for rs in ("baseline-history-protect", "baseline-pr-and-checks", "baseline-tag-protect"):
        assert rs in text, f"workflow-protect-branch does not mention {rs}"


def test_pin_actions_documents_sha_pinning() -> None:
    """workflow-pin-actions documents full-length commit-SHA pinning."""
    text = _skill_text("workflow-pin-actions").lower()
    assert "sha" in text and ("40" in text or "commit" in text), "pin-actions: no SHA-pin contract"


def test_detect_stack_recognizes_manifest_files() -> None:
    """detect-stack's detection surface references real ecosystem manifest files."""
    skill_dir = SKILLS_ROOT / "maintainer-detect-stack"
    blob = _skill_text("maintainer-detect-stack")
    for ref in (skill_dir / "references").glob("*.md"):
        blob += ref.read_text(encoding="utf-8")
    hits = [m for m in ("package.json", "pyproject.toml", "go.mod", "Cargo.toml") if m in blob]
    assert len(hits) >= 2, f"detect-stack references too few manifest files: {hits}"


def test_trdd_adr_template_is_v2_column_schema() -> None:
    """The trdd-adr template + seed README emit v2 column:, never v1 status: (M3/M13).

    Regression guard tying back to #10 P1 — these are the surfaces that
    propagate the schema into every new TRDD and every bootstrapped project.
    """
    for ref in ("trdd-template.md", "seed-readmes.md"):
        text = (SKILLS_ROOT / "maintainer-trdd-adr" / "references" / ref).read_text()
        assert "column:" in text, f"{ref}: missing v2 column: schema"
        # no v1 status: frontmatter line (allow prose like "no v1 `status:` field")
        assert not re.search(r"^status:\s*(not-started|in-progress|completed|failed|blocked|superseded)\s*$", text, re.M), \
            f"{ref}: still emits a v1 status: frontmatter line"
