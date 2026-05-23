"""
Tests for the jq --arg trap detector.

Spec: skills/workflow-fix-safe/references/instructions.md
      > Step 4 > "jq command-substitution audit (the --arg trap)"

The documented regex pattern is:
    jq[^|]*"[^"]*\\$\\{[A-Z_][A-Z0-9_]*\\}

A line is a trap iff it contains `jq` followed by a double-quoted string
that interpolates a bash variable `${VAR}` inside the quotes (where bash
expands BEFORE jq sees the filter, opening a command-injection hole).

The hardened pattern uses `--arg name "$VAR"` so the value is passed as
a named jq argument (outside the filter quotes), which the detector
correctly leaves alone.
"""

from __future__ import annotations

from skill_helpers import detect_jq_arg_trap


def test_jq_trap_flags_vulnerable_shape() -> None:
    """A jq invocation with `${VAR}` inside the double-quoted filter is flagged."""
    yaml = """\
env:
  PR_TITLE: ${{ github.event.pull_request.title }}
run: |
  PAYLOAD=$(jq -nc --arg text "New PR: ${PR_TITLE}" '{text: $text}')
"""
    hits = detect_jq_arg_trap(yaml)
    assert len(hits) == 1
    line_num, line_text = hits[0]
    assert "jq" in line_text
    assert "${PR_TITLE}" in line_text
    # And it points at the right line in the input.
    assert line_num == 4


def test_jq_trap_does_not_flag_hardened_shape() -> None:
    """The correct `--arg name "$VAR"` form is NOT flagged (no ${} in filter)."""
    yaml = """\
env:
  PR_TITLE: ${{ github.event.pull_request.title }}
run: |
  PAYLOAD=$(jq -nc \\
    --arg title "$PR_TITLE" \\
    '{text: ("New PR: " + $title)}')
"""
    # The hardened form has $PR_TITLE (no braces) in a shell context,
    # NOT inside the jq filter string. The regex requires the `${...}`
    # form, so this MUST NOT match.
    hits = detect_jq_arg_trap(yaml)
    assert hits == []


def test_jq_trap_skips_lines_without_jq() -> None:
    """A line with `${VAR}` but no `jq` invocation is not flagged."""
    yaml = """\
env:
  PR_TITLE: ${{ github.event.pull_request.title }}
run: |
  echo "Plain echo with ${PR_TITLE} — no jq involved."
  curl -d "{\\"text\\":\\"${PR_TITLE}\\"}" https://example/webhook
"""
    hits = detect_jq_arg_trap(yaml)
    assert hits == []


def test_jq_trap_flags_multiple_lines_independently() -> None:
    """Multiple offending jq lines all surface in the detector output."""
    yaml = """\
env:
  TITLE: ${{ inputs.title }}
  AUTHOR: ${{ inputs.author }}
run: |
  A=$(jq -nc --arg t "Title: ${TITLE}" '{t: $t}')
  echo "between line"
  B=$(jq -nc --arg a "Author: ${AUTHOR}" '{a: $a}')
"""
    hits = detect_jq_arg_trap(yaml)
    assert len(hits) == 2
    line_numbers = [n for n, _ in hits]
    # Lines 5 and 7 in the YAML above.
    assert line_numbers == [5, 7]
