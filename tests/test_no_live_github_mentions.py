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

The rule enforced here is therefore mechanical, not taste-based: an @handle in
shippable content must be written in the angle-bracket placeholder form
(@<something>), which cannot resolve in ANY markdown context. A backtick code
span is deliberately NOT accepted as sufficient on its own, because the span
suppresses the notification only until someone copies the text out of it —
which is exactly what an agent does when it lifts an example into a comment
body.

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

# An @handle: '@' not preceded by a word char, '/', a backtick, or '<', and NOT
# followed by '.<alnum>' (an email/host tail such as `*@users.noreply.github.com`
# or `<token>@github.com`, neither of which notifies anyone).
#   - '/' before  guards `actions/setup-node@v4` and `pkg@1.2.3`
#   - '<' before  guards the sanctioned placeholder form `@<repo-owner>`
#   - a word char guards emails and the Make/Jenkins sigils
# A trailing '.' that ENDS a sentence still counts as a mention ("ping @owner."),
# which is why the exclusion requires an alphanumeric right after the dot.
MENTION = re.compile(r"(?:^|[^\w/`<@.-])@([A-Za-z][A-Za-z0-9-]{0,38})\b(?!\.\w)")

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

# Action/package version pins: `@v4`, and the doc placeholder `@vN`.
_VERSION_PIN = re.compile(r"^v(\d|N$)")


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
            for match in MENTION.finditer(line):
                handle = match.group(1)
                if handle in ALLOWED_HANDLES or _VERSION_PIN.match(handle):
                    continue
                rel = path.relative_to(REPO_ROOT)
                offenders.append(f"{rel}:{lineno}: @{handle}  |  {line.strip()[:100]}")

    assert not offenders, (
        "Shipped markdown contains @mentions that GitHub may resolve to real "
        "accounts. Rewrite each as the placeholder form @<role-name>:\n  "
        + "\n  ".join(offenders)
    )
