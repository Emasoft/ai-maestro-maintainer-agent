"""
Tests for workflow-bootstrap skill.

Spec: skills/workflow-bootstrap/SKILL.md
      skills/workflow-bootstrap/references/instructions.md

Focus areas (4 tests):
  - Language detection table (python / node / rust / go / generic)
  - Refusal on existing workflows
  - Template files actually exist and pin actions to v-tags (not @main/etc.)
  - npmrc-hardened template applies the documented defences
"""

from __future__ import annotations

from pathlib import Path


from conftest import BOOTSTRAP_REFS
from skill_helpers import detect_language, has_existing_workflows


def test_detect_language_python(tmp_path: Path) -> None:
    """pyproject.toml → 'python'."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    assert detect_language(tmp_path) == "python"


def test_detect_language_node_when_only_package_json(tmp_path: Path) -> None:
    """package.json (and no pyproject.toml) → 'node'."""
    (tmp_path / "package.json").write_text('{"name":"x"}')
    assert detect_language(tmp_path) == "node"


def test_detect_language_python_wins_over_package_json(tmp_path: Path) -> None:
    """When BOTH pyproject.toml and package.json are present, python wins."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "package.json").write_text('{"name":"x"}')
    assert detect_language(tmp_path) == "python"


def test_detect_language_rust_and_go(tmp_path: Path) -> None:
    """Cargo.toml → rust; go.mod → go; generic when neither."""
    # Rust
    rust_dir = tmp_path / "rust"
    rust_dir.mkdir()
    (rust_dir / "Cargo.toml").write_text("[package]\nname='x'\n")
    assert detect_language(rust_dir) == "rust"
    # Go
    go_dir = tmp_path / "go"
    go_dir.mkdir()
    (go_dir / "go.mod").write_text("module x\n")
    assert detect_language(go_dir) == "go"
    # Generic
    gen_dir = tmp_path / "gen"
    gen_dir.mkdir()
    assert detect_language(gen_dir) == "generic"


def test_has_existing_workflows_refusal_trigger(tmp_path: Path) -> None:
    """Bootstrap refuses iff any *.yml or *.yaml exists in .github/workflows/."""
    repo = tmp_path / "repo"
    repo.mkdir()
    # No directory → no existing workflows
    assert has_existing_workflows(repo) is False
    # Empty workflows dir → still no existing workflows
    wf = repo / ".github" / "workflows"
    wf.mkdir(parents=True)
    assert has_existing_workflows(repo) is False
    # A yml file → existing workflows triggers refusal
    (wf / "release.yml").write_text("name: release\non: push\njobs: {}\n")
    assert has_existing_workflows(repo) is True


def test_templates_exist_and_python_template_pins_with_v_tags() -> None:
    """The python template uses `@vN` form (which workflow-pin-actions pins to SHA)."""
    py = BOOTSTRAP_REFS / "templates" / "python.yml"
    assert py.exists(), f"missing template: {py}"
    text = py.read_text()
    # Must use vN form (not @main, not @master) — pin-actions converts these
    # to SHAs on the first run per the template comment.
    assert "actions/checkout@v" in text
    assert "actions/setup-python@v" in text
    # And the hardening defaults are present.
    assert "permissions:" in text
    assert "contents: read" in text
    assert "concurrency:" in text
    assert "timeout-minutes:" in text
    assert "persist-credentials: false" in text


def test_npmrc_hardened_applies_documented_defences() -> None:
    """The .npmrc template applies all 3 documented supply-chain defences."""
    npmrc = BOOTSTRAP_REFS / "templates" / "npmrc-hardened"
    assert npmrc.exists()
    text = npmrc.read_text()
    # The 3 defences from instructions.md:
    # 1) 24h quarantine on new packages
    assert "minimum-release-age" in text
    # 2) Block exotic transitive deps (git/tarball)
    assert "block-exotic-subdeps" in text
    # 3) Frozen-lockfile so lockfile-out-of-sync fails CI
    assert "frozen-lockfile" in text
