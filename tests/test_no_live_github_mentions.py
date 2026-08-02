"""
Guardrail: no shipped file may contain an @mention that GitHub would
resolve to a real account.

WHY THIS EXISTS (2026-08-02): the plugin shipped six example lines using
@owner / @random / @random-contributor / @attacker as placeholders. All four
are live GitHub accounts. One of them sat inside an example of a comment the
agent POSTS (maintainer-approval-gate/SKILL.md), so following the example
verbatim notified a real organization about a repo it has nothing to do with.
"Obviously fake-looking" is not a property of the handle — it is a guess about
the namespace, and the namespace is fully populated.

CORRECTION (2026-08-02, same day): the first version of this guard PERMITTED an
angle-bracket placeholder `@<role-name>` and asserted it could not resolve. That
was wrong, and the form is now banned here too. GitHub's mention extractor reads
the RAW body, not the sanitized HTML, so the brackets protect nothing — in the
field, `@<manager>` and `@<janitor>` paged the real `manager` and `janitor`
accounts. Rendering the same text through GitHub's own /markdown API shows
`@<manager>` collapsing to a bare `@` with no mention link, which is exactly why
the form looked safe: THE RENDER IS NOT EVIDENCE OF WHO GETS NOTIFIED.

So the enforced rule is the strict one — no `@` immediately followed by a name,
in any form, anywhere in shipped content. Write the role in plain words ("the
repo owner"), or a bare handle with no `@` (`<author>`), or, when a literal `@`
is unavoidable (an action pin, a URL, an email), keep it attached to a preceding
word or slash so it cannot read as a mention.

A backtick span IS a real defence in a posted body, but it is not accepted here
on its own: a span protects the text only while the text stays inside it, and
lifting an example out of a span into a comment body is exactly what an agent
does.

NO MOCKS: this walks the real files that ship.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories whose markdown is loaded into an agent's context or copied into
# GitHub comment bodies. design/ and tests/ are excluded: TRDDs quote real
# upstream threads on purpose, and test data must be free to contain the very
# strings we are banning.
SHIPPED_DIRS = ("skills", "commands", "agents")

# A bare @handle: '@' not preceded by a word char, '/', '>', a backtick, or '<',
# and NOT followed by '.<alnum>' (an email/host tail such as
# `*@users.noreply.github.com` or `<token>@github.com`, neither of which
# notifies anyone).
#   - '/' or a word char before → an attached pin: `actions/checkout@v4`,
#     `pkg@1.2.3`. Attached is safe; BARE `@v4` is not — `@v3`/`@v4`/`@v7` are
#     real accounts, so there is no version-number allowlist here.
#   - '>' before → a pin on a placeholder: `<action>@<tag>`, `setup-<lang>@vN`.
# A trailing '.' that ENDS a sentence is still a mention ("ping @owner."), which
# is why the exclusion requires an alphanumeric right after the dot.
MENTION = re.compile(r"(?:^|[^\w/`<>@.-])@([A-Za-z][A-Za-z0-9-]{0,38})\b(?!\.\w)")

# The refuted placeholder form. Banned on its own line of defence because the
# bracket does NOT stop the notification (see the CORRECTION above). Excluded
# only where '@' is attached to a preceding word/slash/'>' — a version pin such
# as `actions/checkout@<sha>` or `<pkg>@<ver>`, which addresses no one.
ANGLE_MENTION = re.compile(r"(?:^|[^\w/`>])@<")

# Non-mention '@word' constructs that share the lexical shape. Each is a
# language sigil or a package namespace, not a GitHub handle.
ALLOWED_HANDLES = frozenset(
    {
        "echo",       # Makefile recipe-silencing sigil
        "if",         # Makefile recipe
        "Library",    # Jenkins shared-library annotation
        "aikidosec",  # npm scope in `@aikidosec/safe-chain`, not a GitHub user
    }
)


def _shipped_markdown() -> list[Path]:
    files: list[Path] = []
    for d in SHIPPED_DIRS:
        files.extend(sorted((REPO_ROOT / d).rglob("*.md")))
    return files


def test_shipped_markdown_exists() -> None:
    """The scan covers a non-empty file set (guards a silently-empty glob)."""
    files = _shipped_markdown()
    assert len(files) > 20, f"expected the shipped markdown corpus, found {len(files)}"


def test_no_at_mentions_that_github_would_resolve() -> None:
    """No shipped markdown carries an @handle outside the @<placeholder> form."""
    offenders: list[str] = []
    for path in _shipped_markdown():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            rel = path.relative_to(REPO_ROOT)
            for match in MENTION.finditer(line):
                handle = match.group(1)
                if handle in ALLOWED_HANDLES:
                    continue
                offenders.append(f"{rel}:{lineno}: @{handle}  |  {line.strip()[:100]}")
            if ANGLE_MENTION.search(line):
                offenders.append(f"{rel}:{lineno}: @<...>  |  {line.strip()[:100]}")

    assert not offenders, (
        "Shipped content contains an '@' followed by a name. GitHub resolves that "
        "against real accounts from the RAW body, so neither angle brackets nor a "
        "clean HTML render make it safe. Use plain words ('the repo owner') or a "
        "bare handle with no '@' ('<author>'):\n  " + "\n  ".join(offenders)
    )
