"""
Guardrail: shipped content must not carry an `@name` that GitHub resolves to a
real account, and must not carry a raw email address.

WHY THIS EXISTS (2026-08-02): the plugin shipped example lines using
@owner / @random / @random-contributor / @attacker as placeholders. All four are
live GitHub accounts, and the PRRD byline's bare `@owner` paged a real
organization from every agent that copied it. "Obviously fake-looking" is not a
property of a handle — it is a guess about namespace occupancy, and the
namespace is full.

THE GRAMMAR IS MEASURED, NOT REASONED. Every rule below was verified against
GitHub's own renderer (`gh api /markdown`, checking for the `user-mention`
class), because two earlier versions of this file were wrong in the other
direction — they flagged things that are inert:

    PAGES                       INERT
    @janitor                    @lru_cache        (word char continues the token)
    @janitor.                    @types/node       (a slash follows)
    (@janitor)                  actions/checkout@v4  (word char precedes)
    @foo-bar                    x@janitor
    @staticmethod               user@gmail.com    (an address does not page its domain)
                                @<manager>        (the bracket is not a handle char)
                                `@janitor`        (code span)

So a handle pages only at a WORD BOUNDARY and never before `/`. A trailing `\b`
is REQUIRED, not optional: without it `@lru_cache` matches its `lru` prefix and
reports an account the reader cannot find and GitHub never notifies.

Emails are still refused, for a DIFFERENT reason: pasting one is a PII leak,
which the owner's rule calls "a separate and sufficient reason". They are not
reported as mentions, because they are not mentions.

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

# AN EMITTER FENCE IS NOT INERT (hole found by the CORE plugin's guard,
# Emasoft/ai-maestro#109, fixed there in 07db70e; adopted here 2026-08-05).
#
# Exempting every fence is correct about the DOCUMENT and wrong about the WORLD:
# GitHub does not linkify inside a fence, so the block is inert WHERE IT SITS —
# but a fence containing `gh issue comment --body "... @handle ..."` or
# `amp-send ... "<body>"` is a COMMAND, and its OUTPUT is a comment body carrying
# that handle bare. The doc is safe; running the doc pages a stranger.
#
# So a fence that emits a message body is scanned AS PROSE. Measured when this
# landed: 20 emitter fences in the shipped corpus, 0 leaks — i.e. no live hole,
# but nothing would have reported the first one. A wording gap that only becomes
# a hole later is still worth closing before the hole exists.
EMITTER_FENCE = re.compile(
    r"\bgh\s+(?:issue|pr|api|release|gist)\b[^\n]*?(?:--body|--body-file|--field|--raw-field)"
    r"|(?:^|\s)amp-(?:send|reply)\b",
    re.S,
)

# A GitHub mention, per the measurements above:
#   - '@' not preceded by a word char, '/', '>' or a backtick — those are the
#     attached forms (`checkout@v4`, `x@janitor`, `<pkg>@<ver>`), which are inert.
#   - handle is [A-Za-z0-9][A-Za-z0-9-]* — '<' is not a handle char, so the
#     bracketed placeholder `@<role>` does not match, and it does not page.
#   - (?![\w/]) is the WORD BOUNDARY that makes `@lru_cache` and `@types/node`
#     inert. Do not remove it to "catch more": it would report prefixes that
#     GitHub never notifies, which is how this guard cried wolf twice.
MENTION = re.compile(r"(?:^|[^\w/`>@-])@(?P<handle>[A-Za-z0-9][A-Za-z0-9-]*)(?![\w/])")

# A raw email. NOT a mention — measured inert, an address does not page its
# domain — but refused anyway because pasting one leaks PII into a public repo
# whose edit history is kept.
EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Sigils that share the mention shape but are not handles. Every entry is a
# hole, so the list stays short.
ALLOWED_HANDLES = frozenset(
    {
        "echo",     # Makefile recipe-silencing sigil
        "if",       # Makefile recipe
        "Library",  # Jenkins shared-library annotation
    }
)

# Addresses that are documentation, not anyone's mailbox: the reserved example
# domain (RFC 2606) and GitHub's own no-reply form.
ALLOWED_EMAIL = re.compile(r"@(example\.(com|org|net)|users\.noreply\.github\.com)$")


def _shipped_markdown() -> list[Path]:
    files: list[Path] = []
    for d in SHIPPED_DIRS:
        files.extend(sorted((REPO_ROOT / d).rglob("*.md")))
    return files


def _strip_code(text: str) -> str:
    """Blank out inert code, preserving line numbering.

    A fence that EMITS a message body (see EMITTER_FENCE) is deliberately left in
    place — the handle inside it reaches GitHub when the command runs. Its inline
    spans are still blanked, because a backticked handle survives into the body
    as backticked text and GitHub does not linkify it there either.
    """
    def blank(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    def fence(match: re.Match[str]) -> str:
        block = match.group(0)
        return block if EMITTER_FENCE.search(block) else blank(match)

    return INLINE_SPAN.sub(blank, FENCED_BLOCK.sub(fence, text))


def test_shipped_markdown_exists() -> None:
    """The scan covers a non-empty file set (guards a silently-empty glob)."""
    files = _shipped_markdown()
    assert len(files) > 20, f"expected the shipped markdown corpus, found {len(files)}"


def test_strip_code_preserves_line_numbers() -> None:
    """Blanking code must not shift line numbers, or offenders get misreported."""
    src = "a\n```\n@owner\n```\nb `@x` c\n"
    assert len(_strip_code(src).splitlines()) == len(src.splitlines())
    assert "@owner" not in _strip_code(src)


def test_mention_grammar_matches_measured_github_behaviour() -> None:
    """Each case was verified with `gh api /markdown` (user-mention class)."""
    for text, expected in [
        ("ping @janitor now", "janitor"),        # PAGES
        ("ping @janitor.", "janitor"),           # PAGES — trailing dot is a boundary
        ("see (@janitor) here", "janitor"),      # PAGES — parens are boundaries
        ("a @foo-bar b", "foo-bar"),             # PAGES — '-' is a handle char
        ("ping @staticmethod x", "staticmethod"),  # PAGES — looking technical is not inert
        ("we use @lru_cache here", None),        # inert — '_' continues the word
        ("a @types/node b", None),               # inert — a slash follows
        ("pin actions/checkout@v4", None),       # inert — word char precedes
        ("mail x@janitor today", None),          # inert — word char precedes
        ("mail user@gmail.com", None),           # inert as a MENTION (PII, caught below)
        ("the @<manager> role", None),           # inert — '<' is not a handle char
    ]:
        match = MENTION.search(text)
        got = match.group("handle") if match else None
        assert got == expected, f"{text!r}: expected {expected!r}, got {got!r}"


def test_an_emitter_fence_is_scanned_but_a_plain_fence_is_not() -> None:
    """The fence is inert where it sits; its OUTPUT is not.

    Without this the guard passes a doc that instructs an agent to POST a bare
    handle — the document is clean and the comment it produces pages a stranger.
    """
    emitter = 'run:\n\n```bash\ngh issue comment 1 --body "thanks @janitor"\n```\n'
    assert "@janitor" in _strip_code(emitter), "an emitter fence was wrongly exempted"

    amp = '```bash\namp-send "$M" "subj" "ping @janitor"\n```\n'
    assert "@janitor" in _strip_code(amp), "an amp-send fence was wrongly exempted"

    # A fence that emits nothing stays exempt — that is the prescribed fix for a
    # handle you must WRITE, and a guard that flags its own remedy gets deleted.
    plain = "```python\n@janitor\ndef f(): ...\n```\n"
    assert "@janitor" not in _strip_code(plain), "a non-emitting fence must stay inert"

    # A BACKTICKED handle inside an emitter survives into the body as backticked
    # text, which GitHub does not linkify — so it must not be reported.
    safe = '```bash\ngh issue comment 1 --body "thanks `@janitor`"\n```\n'
    assert "@janitor" not in _strip_code(safe), "a backticked handle in an emitter is inert"


def test_email_regex_catches_addresses_but_allows_reserved() -> None:
    """Raw addresses are refused as PII; documentation addresses are not."""
    assert EMAIL.search("mail user@gmail.com") is not None
    for allowed in ("a@example.com", "bot@users.noreply.github.com"):
        match = EMAIL.search(f"write to {allowed}")
        assert match is not None and ALLOWED_EMAIL.search(match.group(0))


def test_no_at_mentions_that_github_would_resolve() -> None:
    """No shipped content pages an account or leaks an address outside a span."""
    offenders: list[str] = []
    for path in _shipped_markdown():
        rel = path.relative_to(REPO_ROOT)
        scannable = _strip_code(path.read_text(encoding="utf-8"))
        for lineno, line in enumerate(scannable.splitlines(), 1):
            for match in MENTION.finditer(line):
                if match.group("handle") in ALLOWED_HANDLES:
                    continue
                offenders.append(
                    f"{rel}:{lineno}: pages @{match.group('handle')}"
                    f"  |  {line.strip()[:90]}"
                )
            for match in EMAIL.finditer(line):
                if ALLOWED_EMAIL.search(match.group(0)):
                    continue
                offenders.append(
                    f"{rel}:{lineno}: raw address {match.group(0)} (PII)"
                    f"  |  {line.strip()[:90]}"
                )

    assert not offenders, (
        "Shipped content pages a real account, or pastes a raw address. Write "
        "the name in plain words, or wrap it in backticks; use example.com for "
        "addresses:\n  " + "\n  ".join(offenders)
    )
