"""
Guardrail: shipped content must not carry an `@name` that GitHub would resolve
to a real account when the text is posted.

WHY THIS EXISTS (2026-08-02): the plugin shipped example lines using
@owner / @random / @random-contributor / @attacker as placeholders. All four are
live GitHub accounts. One sat inside an example of a comment the agent POSTS, so
following it verbatim notified a real organization about an unrelated repo.
"Obviously fake-looking" is not a property of a handle — it is a guess about
namespace occupancy, and the namespace is full.

THIS FILE HAS BEEN WRONG TWICE. Both corrections are kept, because each was a
plausible defence that the next author will otherwise re-derive:

  1. It permitted `@<role-name>`, on the theory that angle brackets cannot
     resolve. They do not protect anything: GitHub extracts mentions from the
     RAW body, so `@<manager>` paged the real `manager`. Rendering it through
     GitHub's own /markdown API returns a bare `@` with no link — which is
     exactly the trap. THE RENDER IS NOT EVIDENCE OF WHO GETS NOTIFIED.

  2. It rejected backticks as insufficient and skipped anything ending in a
     domain. Per the owner's IRON RULE (~/.claude/rules/github-mentions.md,
     2026-08-02) both were backwards:
       - A code span IS the sanctioned fix — GitHub does not linkify inside one.
         A guard that reddens on correct writing gets deleted, so fenced blocks
         and inline spans are stripped before scanning.
       - A raw email is NOT exempt: `user@gmail.com` pages `@gmail`, because
         GitHub reads the domain as a username. It is a page AND a PII leak.

The handle grammar below mirrors GitHub's own linkifier rather than a tidier
one: a username may not contain `_` or `.`, so GitHub links the VALID PREFIX and
stops. `@lru_cache` therefore pages `lru`, and `@gmail.com` pages `gmail`. Any
regex that requires a word boundary after the handle misses both.

NO MOCKS: this walks the real files that ship.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories whose content is loaded into an agent's context or copied into
# GitHub bodies. design/ and tests/ are excluded: TRDDs quote real upstream
# threads on purpose, and test data must be free to contain what we ban.
SHIPPED_DIRS = ("skills", "commands", "agents")

FENCED_BLOCK = re.compile(r"```.*?```", re.S)
INLINE_SPAN = re.compile(r"`[^`\n]*`")

# '@' + the prefix GitHub would linkify. Deliberately NO trailing \b: the run
# stops at '_' or '.' on its own, which is what GitHub does.
# Not preceded by a word char, '/', '>' or '`' — those mark an ATTACHED pin
# (`actions/checkout@v4`, `<pkg>@<ver>`), which addresses nobody.
# `tail` is captured for REPORTING ONLY and never narrows the match. The handle
# stops at the first character GitHub cannot linkify, so `@lru_cache` pages `lru`
# while the text on the page reads `@lru_cache`. Reporting the prefix alone names
# a string that is not in the file and cannot be grepped for, so the offender line
# prints both. Do NOT "resolve" that mismatch with a trailing \b: `_` is a word
# char, the boundary fails mid-token, the match dies, and a REAL page stops being
# detected — the owner's rule measured `@lru_cache` paging `lru` in the field.
MENTION = re.compile(
    r"(?:^|[^\w/`>@-])@(?P<handle><?[A-Za-z0-9][A-Za-z0-9-]*)(?P<tail>[\w.-]*)"
)

# The one case where an ATTACHED '@' still pages: an email. GitHub reads the
# domain as a username, so `bob@gmail.com` notifies `gmail` AND leaks an address.
# Distinguished from a version pin by the dotted TLD tail: `checkout@v4` has no
# dot, `@gmail.com` does. Without this the "attached is safe" shortcut, which is
# true for pins, silently exempts every raw address.
EMAIL_MENTION = re.compile(r"\w@(?P<handle>[A-Za-z0-9][A-Za-z0-9-]*)\.[A-Za-z]")

# Sigils that share the shape but are not handles, in contexts where a code span
# is not idiomatic. Kept deliberately short — every entry is a hole.
ALLOWED_HANDLES = frozenset(
    {
        "echo",     # Makefile recipe-silencing sigil
        "if",       # Makefile recipe
        "Library",  # Jenkins shared-library annotation
    }
)


def _shipped_markdown() -> list[Path]:
    files: list[Path] = []
    for d in SHIPPED_DIRS:
        files.extend(sorted((REPO_ROOT / d).rglob("*.md")))
    return files


def _handle_of(match: re.Match[str]) -> str:
    """The account GitHub would actually page — a leading '<' is not part of it."""
    return match.group("handle").lstrip("<")


def _written_as(match: re.Match[str]) -> str:
    """The token as it appears in the file, so the offender can be grepped for."""
    tail = match.groupdict().get("tail") or ""
    return "@" + match.group("handle") + tail


def _describe(match: re.Match[str]) -> str:
    """Name the paged account AND the text that pages it when they differ."""
    handle, written = _handle_of(match), _written_as(match)
    return f"@{handle}" if written == f"@{handle}" else f"{written} (pages @{handle})"


def _strip_code(text: str) -> str:
    """Blank out fenced blocks and inline spans, preserving line numbering."""
    def blank(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    return INLINE_SPAN.sub(blank, FENCED_BLOCK.sub(blank, text))


def test_shipped_markdown_exists() -> None:
    """The scan covers a non-empty file set (guards a silently-empty glob)."""
    files = _shipped_markdown()
    assert len(files) > 20, f"expected the shipped markdown corpus, found {len(files)}"


def test_strip_code_preserves_line_numbers() -> None:
    """Blanking code must not shift line numbers, or offenders get misreported."""
    src = "a\n```\n@owner\n```\nb `@x` c\n"
    assert len(_strip_code(src).splitlines()) == len(src.splitlines())
    assert "@owner" not in _strip_code(src)


def test_mention_regex_matches_what_github_linkifies() -> None:
    """The grammar tracks GitHub's linkifier, including the two prefix cases."""
    for text, expected in [
        ("ping @manager now", "manager"),
        ("see @gmail.com for it", "gmail"),  # bare -> GitHub links the prefix
        ("use @lru_cache here", "lru"),      # '_' is invalid -> prefix links
        ("pin actions/checkout@v4", None),   # attached pin
        ("bump to @v4 now", "v4"),           # bare -> @v4 is a real account
        ("the @<manager> role", "manager"),  # brackets do not protect
    ]:
        match = MENTION.search(text)
        got = _handle_of(match) if match else None
        assert got == expected, f"{text!r}: expected {expected!r}, got {got!r}"


def test_email_regex_catches_the_domain_as_a_username() -> None:
    """A raw address pages its domain — the one attached '@' that is not a pin."""
    for text, expected in [
        ("mail user@gmail.com", "gmail"),
        ("pin actions/checkout@v4", None),   # no dotted tail -> a pin, not mail
        ("build <pkg>@<ver> now", None),
    ]:
        match = EMAIL_MENTION.search(text)
        got = _handle_of(match) if match else None
        assert got == expected, f"{text!r}: expected {expected!r}, got {got!r}"


def test_no_at_mentions_that_github_would_resolve() -> None:
    """No shipped content carries an @name outside a code span."""
    offenders: list[str] = []
    for path in _shipped_markdown():
        rel = path.relative_to(REPO_ROOT)
        scannable = _strip_code(path.read_text(encoding="utf-8"))
        for lineno, line in enumerate(scannable.splitlines(), 1):
            for pattern in (MENTION, EMAIL_MENTION):
                for match in pattern.finditer(line):
                    handle = _handle_of(match)
                    if handle in ALLOWED_HANDLES:
                        continue
                    offenders.append(
                        f"{rel}:{lineno}: {_describe(match)}  |  {line.strip()[:100]}"
                    )

    assert not offenders, (
        "Shipped content has an '@' followed by a name, outside a code span. "
        "GitHub resolves that against real accounts from the RAW body, so a "
        "clean HTML render and angle brackets both prove nothing. Fix by writing "
        "the name plain, or wrapping it in backticks:\n  " + "\n  ".join(offenders)
    )
