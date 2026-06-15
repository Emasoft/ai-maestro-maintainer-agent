"""
Skill-doc contract tests for the 14 skills the fleet-readiness audit (#10 M12)
found without dedicated test coverage:

  patrol, triage, fix, pr-triage, pr-review, workflow-scan, workflow-fix-safe,
  workflow-pin-actions, workflow-protect-branch, detect-stack, tooling-bootstrap,
  config-lint, generate-docs, trdd-adr.

No mocks. Every assertion runs against the REAL shipped SKILL.md + its
references/ on disk. The universal contract (parametrized over all 14) checks
each skill's frontmatter validity, the no-tool-grant-frontmatter invariant
(ADR-0002 / PRRD S7), the presence of the core body sections, and that every
`references/...` link in the body resolves to a real file (broken-reference
guard). Per-skill tests add the structural invariant unique to each skill.

Consistent with this repo's grouped-test convention (test_sentinel_rules_a..f
cover many rules in one module): one table-driven module gives every one of the
14 skills real, regression-catching coverage without 14 near-duplicate stub
files.
"""

from __future__ import annotations

import re

import pytest
import yaml

from conftest import REPO_ROOT

SKILLS_ROOT = REPO_ROOT / "skills"

# The 14 skills the audit flagged as uncovered.
AUDIT_UNCOVERED_SKILLS = [
    "maintainer-patrol",
    "maintainer-triage",
    "maintainer-fix",
    "maintainer-pr-triage",
    "maintainer-pr-review",
    "workflow-scan",
    "workflow-fix-safe",
    "workflow-pin-actions",
    "workflow-protect-branch",
    "maintainer-detect-stack",
    "maintainer-tooling-bootstrap",
    "maintainer-config-lint",
    "maintainer-generate-docs",
    "maintainer-trdd-adr",
]

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


# ─────────────────────────── universal contract ───────────────────────────


@pytest.mark.parametrize("skill", AUDIT_UNCOVERED_SKILLS)
def test_frontmatter_valid_with_nonempty_description(skill: str) -> None:
    """Every skill's frontmatter parses as YAML and carries a non-empty description."""
    fm, _ = _split_frontmatter(_skill_text(skill))
    assert "description" in fm, f"{skill}: no description in frontmatter"
    assert str(fm["description"]).strip(), f"{skill}: empty description"


@pytest.mark.parametrize("skill", AUDIT_UNCOVERED_SKILLS)
def test_no_tool_grant_frontmatter(skill: str) -> None:
    """No skill declares allowed-tools/disallowed-tools/tools (ADR-0002 / PRRD S7).

    This is the regression guard for the M4 finding (kanban's allowed-tools);
    it holds the whole skill set to the invariant, not just the one that drifted.
    """
    fm, _ = _split_frontmatter(_skill_text(skill))
    present = [k for k in TOOL_GRANT_KEYS if k in fm]
    assert not present, f"{skill}: forbidden tool-grant frontmatter key(s): {present}"


@pytest.mark.parametrize("skill", AUDIT_UNCOVERED_SKILLS)
def test_has_core_body_sections(skill: str) -> None:
    """Each skill documents at least an Overview/Instructions plus a Scope or Resources."""
    _, body = _split_frontmatter(_skill_text(skill))
    headings = set(re.findall(r"^##\s+(.+?)\s*$", body, re.M))
    h_lower = {h.lower() for h in headings}
    assert h_lower & {"overview", "instructions"}, f"{skill}: no Overview/Instructions section"
    assert h_lower & {"scope", "resources", "output"}, f"{skill}: no Scope/Resources/Output section"


@pytest.mark.parametrize("skill", AUDIT_UNCOVERED_SKILLS)
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
