"""
Tests for the markdown memory system (issue #9).

Spec: rules/memory-protocol.md
      skills/maintainer-memory-recall/SKILL.md
      skills/maintainer-memory-write/SKILL.md

No mocks. Recall tests run the EXACT bash recipe documented in the recall
SKILL.md against a real fixture memory dir — once with memgrep on PATH
(skipped if the binary is absent on this host) and once with a stripped
PATH that genuinely lacks memgrep, proving the grep fallback. Write tests
author a note per the write skill's schema and validate it with a real
YAML parse + a real round-trip recall.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from conftest import REPO_ROOT

RECALL_SKILL = REPO_ROOT / "skills" / "maintainer-memory-recall" / "SKILL.md"
WRITE_SKILL = REPO_ROOT / "skills" / "maintainer-memory-write" / "SKILL.md"
MEMORY_RULE = REPO_ROOT / "rules" / "memory-protocol.md"

# The canonical recall snippet both the rule and the recall skill document.
# Tests run THIS string (not a paraphrase) so doc drift breaks the suite.
RECALL_SNIPPET = (
    'if command -v memgrep >/dev/null 2>&1; then\n'
    '  memgrep recall "$SYMPTOM" "$MEMDIR"\n'
    'else\n'
    '  grep -rliE "$SYMPTOM" "$MEMDIR" 2>/dev/null\n'
    'fi\n'
)


def _make_fixture_memdir(root: Path) -> Path:
    """Create a real memory dir with two symptom-indexed notes + an off-topic one."""
    memdir = root / "memory"
    memdir.mkdir()
    (memdir / "project_publish_gate.md").write_text(
        "---\n"
        "name: project_publish_gate\n"
        'description: "publish push rejected GH013 after enabling branch protection — why is the push blocked"\n'
        "metadata:\n"
        "  node_type: memory\n"
        "  type: project\n"
        "---\n"
        "The fix is TWO rulesets: history-protect (no bypass) + pr-and-checks "
        "(admin bypass), because bypass_actors is whole-ruleset.\n",
        encoding="utf-8",
    )
    (memdir / "feedback_pipe_truncation.md").write_text(
        "---\n"
        "name: feedback_pipe_truncation\n"
        'description: "command output looks truncated / wrong line count when piping through tee then head"\n'
        "metadata:\n"
        "  node_type: memory\n"
        "  type: feedback\n"
        "---\n"
        "SIGPIPE kills tee before it finishes writing; capture to a file first.\n",
        encoding="utf-8",
    )
    (memdir / "reference_unrelated.md").write_text(
        "---\n"
        "name: reference_unrelated\n"
        'description: "where is the marketplace dashboard for plugin downloads"\n'
        "metadata:\n"
        "  node_type: memory\n"
        "  type: reference\n"
        "---\n"
        "It is on the GitHub releases page.\n",
        encoding="utf-8",
    )
    return memdir


def _run_recall(symptom: str, memdir: Path, *, path_env: str | None = None) -> str:
    """Run the documented recall snippet verbatim in a real bash subprocess."""
    script = f'SYMPTOM="{symptom}"\nMEMDIR="{memdir}"\n{RECALL_SNIPPET}'
    env = None
    if path_env is not None:
        env = {"PATH": path_env, "HOME": str(memdir.parent)}
    proc = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )
    return proc.stdout


def test_recall_skill_documents_memgrep_gate_and_grep_fallback() -> None:
    """The recall SKILL.md carries the exact memgrep gate + grep -rliE fallback snippet."""
    text = RECALL_SKILL.read_text(encoding="utf-8")
    assert "command -v memgrep >/dev/null 2>&1" in text
    assert 'grep -rliE "$SYMPTOM" "$MEMDIR"' in text
    # The rule documents the same canonical pair, so the two cannot drift apart.
    rule = MEMORY_RULE.read_text(encoding="utf-8")
    assert "command -v memgrep >/dev/null 2>&1" in rule
    assert 'grep -rliE "$SYMPTOM" "$MEMDIR"' in rule


def test_write_skill_documents_schema_and_index_line() -> None:
    """The write SKILL.md documents the full note schema and the MEMORY.md index step."""
    text = WRITE_SKILL.read_text(encoding="utf-8")
    for needle in ("name:", "description:", "node_type: memory", "MEMORY.md"):
        assert needle in text, f"write SKILL.md missing schema element: {needle}"
    # The non-destructive correction protocol must be present (lessons, not deletes).
    assert "Notes and lessons learned" in text


@pytest.mark.skipif(shutil.which("memgrep") is None, reason="memgrep binary not installed on this host")
def test_recall_with_memgrep_returns_ranked_fixture_note(tmp_path: Path) -> None:
    """memgrep path: a symptom query returns the matching note ranked in the output."""
    memdir = _make_fixture_memdir(tmp_path)
    out = _run_recall("publish push rejected GH013 branch protection", memdir)
    assert "project_publish_gate" in out, f"expected publish-gate note in recall output, got: {out!r}"
    # Ranking sanity: the off-topic marketplace note must not outrank the hit.
    if "reference_unrelated" in out:
        assert out.index("project_publish_gate") < out.index("reference_unrelated")


def test_recall_fallback_without_memgrep_uses_grep(tmp_path: Path) -> None:
    """Fallback path: with a PATH that lacks memgrep, the snippet degrades to grep and still finds the note."""
    memdir = _make_fixture_memdir(tmp_path)
    # A real minimal PATH (no ~/.cargo/bin) — memgrep is genuinely absent here.
    stripped = "/usr/bin:/bin"
    probe = subprocess.run(
        ["bash", "-c", "command -v memgrep"],
        capture_output=True,
        text=True,
        env={"PATH": stripped},
    )
    assert probe.returncode != 0, "precondition: memgrep must be absent from the stripped PATH"
    out = _run_recall("truncated.*tee|tee.*head", memdir, path_env=stripped)
    assert "feedback_pipe_truncation.md" in out
    assert "reference_unrelated.md" not in out


def test_write_produces_schema_valid_note_and_index_line(tmp_path: Path) -> None:
    """Write path: a note authored per the write skill parses as schema-valid YAML and lands in MEMORY.md."""
    memdir = tmp_path / "memory"
    memdir.mkdir()
    slug = "feedback_cpv_strict_blocked"
    note = memdir / f"{slug}.md"
    # Authored exactly as the write skill instructs (frontmatter schema + one fact).
    note.write_text(
        "---\n"
        f"name: {slug}\n"
        'description: "publish blocked / CPV strict exit 3 but the findings look wrong"\n'
        "metadata:\n"
        "  node_type: memory\n"
        "  type: feedback\n"
        "---\n"
        "Upstream scanner false positives; the suppression decision lives upstream.\n"
        "\n"
        "**Why:** exit-3 blocks publish.py G3.\n"
        "**How to apply:** verify findings before editing our code.\n",
        encoding="utf-8",
    )
    index = memdir / "MEMORY.md"
    index.write_text(
        f"- [CPV strict blocks publish]({slug}.md) — upstream FPs, don't fix locally.\n",
        encoding="utf-8",
    )

    raw = note.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    assert m, "note must have YAML frontmatter delimited by ---"
    fm = yaml.safe_load(m.group(1))
    assert fm["name"] == slug == note.stem
    assert fm["description"].strip(), "description (the recall surface) must be non-empty"
    assert fm["metadata"]["node_type"] == "memory"
    assert fm["metadata"]["type"] in {"user", "feedback", "project", "reference"}
    assert m.group(2).strip(), "body must carry the one fact"
    assert f"({slug}.md)" in index.read_text(encoding="utf-8")

    # Round-trip (write-then-recall, Test B of the dual-test method) on the
    # always-available fallback path: the SYMPTOM query finds the new note.
    out = _run_recall("publish blocked.*CPV|CPV strict exit 3", memdir, path_env="/usr/bin:/bin")
    assert f"{slug}.md" in out
