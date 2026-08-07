"""R42: no agent may drive another agent's session — messaging is the only channel.

The rule (ai-maestro governance R42, all six sub-rules currently prose-only on the
server side): no injected command, keystroke, prompt, or queued input into another
agent's session, by API, CLI or tmux. **No title is exempt** — MANAGER and
CHIEF-OF-STAFF are bound identically. Self-drive stays permitted; the sole global
carve-out is the janitor's machine-wide switches, which are not ours.

Why this file exists at all. On 2026-08-07 the ai-maestro server Claude asked this
plugin directly, on `Emasoft/ai-maestro#67`: *"Does any maintainer skill drive
another agent's session? If the answer is no, say so and I will note this thread as
R42-clean."* We measured, answered no, and that answer is now on the record. Nothing
in the tree kept it true — a helper reaching for `osascript` six months from now
would falsify a published compliance claim silently. This is the guard that turns
the answer into an invariant.

Two traps this file is written around, both paid for in the session that produced it:

  * MATCH THE MECHANISM, NOT THE VOCABULARY. The word "keystroke" appears twice in
    this repo, in an ADR and a TRDD, both discussing UI ergonomics. Prose about
    keystrokes drives nothing. So the pattern below lists TOOLS THAT ACTUALLY SEND
    INPUT, never the English noun, and a hit only counts in an executable position.
  * A PROHIBITION TEST THAT CANNOT DETECT A VIOLATION IS DECORATIVE. The audit that
    produced the #67 answer first ran `grep -r ... $D` with an unquoted path list;
    zsh does not word-split parameters, so all eight paths were passed as one
    nonexistent path and every probe returned zero. A search that never ran and a
    clean tree emit byte-identical output. Hence `test_the_drive_detector_actually_
    detects_a_drive` — the positive control that proves this file can still bite.

Nothing is mocked: every assertion reads the shipped files.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# Tools that actually send input into somebody else's session. Deliberately NOT
# the word "keystroke"/"inject" -- those are how the rule is DISCUSSED, and a
# detector that matches the discussion flags every doc explaining the rule.
DRIVE = re.compile(
    r"""(?x)
    \bosascript\b                      # macOS: the iTerm/Terminal write-text path
  | \btmux\s+send-keys\b
  | \bscreen\s+-X\s+stuff\b
  | \bwezterm\s+cli\s+send-text\b
  | \bkitty\s+@\s+send-text\b
  | \bxdotool\b
  | \bpexpect\b                        # pty puppeteering from python
  | \bimport\s+pty\b
  | \bos\.openpty\b
  | \bpty\.spawn\b
    """
)

# Files an agent executes or reads as instructions. `.md`/`.json` are instruction
# surfaces; `.py` is code. Both can carry a drive mechanism, in different shapes.
_DOC_GLOBS = (
    "agents/*.md",
    "skills/*/SKILL.md",
    "skills/*/references/*.md",
    "commands/*.md",
)


def _surfaces() -> list[Path]:
    """Every shipped file that could carry a drive mechanism."""
    out: list[Path] = []
    for pattern in _DOC_GLOBS:
        out.extend(sorted(REPO.glob(pattern)))
    hooks = REPO / "hooks" / "hooks.json"
    if hooks.is_file():
        out.append(hooks)
    out.extend(sorted((REPO / "scripts").rglob("*.py")))
    return out


def _executable_hits(path: Path, text: str) -> list[str]:
    """Drive-mechanism hits in an EXECUTABLE position, ignoring prose and comments.

    For markdown/json an instruction only executes if it sits in a fenced block;
    for python a line that is wholly a comment documents the rule rather than
    breaking it. Everything else counts.
    """
    if path.suffix in {".md", ".json"}:
        blocks = re.findall(r"```.*?```", text, re.DOTALL)
        return [m.group(0) for b in blocks for m in DRIVE.finditer(b)]
    return [m.group(0) for line in text.splitlines() if not line.lstrip().startswith("#") for m in DRIVE.finditer(line)]


@pytest.mark.parametrize("surface", _surfaces(), ids=lambda p: str(p.relative_to(REPO)))
def test_no_shipped_surface_drives_another_session(surface: Path) -> None:
    """No shipped file can inject input into an agent session (R42)."""
    hits = _executable_hits(surface, surface.read_text(encoding="utf-8"))
    assert not hits, f"{surface.relative_to(REPO)} carries a session-drive mechanism: {hits}. R42 makes this a violation with no title exempt — route it through AMP messaging instead. If this really is SELF-drive (permitted), narrow this test deliberately and say why here; do not widen the pattern to hide it."


def test_the_drive_detector_actually_detects_a_drive() -> None:
    """The detector must bite, or this file reports a compliance it never checked."""
    assert DRIVE.search('osascript -e \'tell app "iTerm" to write text "hi"\'')
    assert DRIVE.search("tmux send-keys -t %3 '/compact' Enter")
    assert DRIVE.search("import pty")
    assert DRIVE.search("child = pexpect.spawn('claude')")


def test_the_drive_detector_ignores_prose_about_the_rule() -> None:
    """Discussing keystrokes is not sending them — the detector must not flag docs."""
    assert not DRIVE.search("elevation actually saves keystrokes) is a minority case")
    assert not DRIVE.search("skill names but cannot fire them with one keystroke")
    assert not DRIVE.search("R42: no agent may inject a prompt into another session")
    assert not DRIVE.search("the branch you EXPECT it to be on (default: wt/<name>)")


def test_the_executable_position_classifier_cuts_both_ways() -> None:
    """A fenced/live mechanism is flagged; the same words in prose or a comment are not.

    The regex self-check above proves the PATTERN bites. This proves the half that
    decides WHERE a hit counts -- the part that would silently pass everything if
    the fence-matching or the comment-skip were inverted.
    """
    assert _executable_hits(Path("a.md"), "```bash\nosascript -e 'x'\n```")
    assert _executable_hits(Path("a.py"), "subprocess.run(['osascript', '-e', 'x'])")
    assert not _executable_hits(Path("a.md"), "we never use osascript; R42 forbids it.")
    assert not _executable_hits(Path("a.py"), "# we deliberately do not call osascript")


def test_the_surface_list_is_not_empty() -> None:
    """A parametrized suite over an empty list passes while testing nothing."""
    surfaces = _surfaces()
    assert len(surfaces) > 20, f"only {len(surfaces)} surfaces discovered — the globs stopped matching, so every parametrized case above silently vanished rather than failing."
