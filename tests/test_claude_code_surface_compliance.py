"""This plugin must not use Claude Code surfaces that upstream removed or changed.

Every check here corresponds to a dated CHANGELOG entry, and every one was
measured absent from this tree on 2026-08-07 against Claude Code 2.1.224, then
re-measured on 2026-08-15 against Claude Code 2.1.233 (auditing the 2.1.225 →
2.1.232 changelog; the CLI claims below were re-run against the live binary,
not re-dated), then again on 2026-08-22 against 2.1.240 (auditing the 2.1.233 →
2.1.240 changelog). The file exists so that stays true without anyone re-reading
a changelog.

The 2026-08-22 pass added ONE detector (the Todo/Task tool family, removed on
modern models in 2.1.233) and confirmed the rest of that changelog needed no
edit here: the persona's session-channel bullet already carried 2.1.232's
bare-name `SendMessage` delivery, and this tree names no model id, no
`extraKnownMarketplaces`/`strictKnownMarketplaces` setting, and no
`allowed-tools` frontmatter for the renamed/aliased surfaces to invalidate. That
"nothing to change" is recorded deliberately — an audit that finds nothing looks
identical to an audit nobody ran.

WHY A TEST RATHER THAN A NOTE. A fact verified in ANOTHER repo keeps living
there: the check's scope stops at this tree while the surface keeps changing
upstream, so a doc that was right when written rots with the suite green and
nothing on either side can span the boundary to notice. That is not theoretical
here — it happened twice in 48 hours (a governance rule narrowed the day before
this plugin quoted it as absolute; a validator pin sat 50 releases stale while
the fix for the finding blocking a release shipped upstream unreachable). A
detector in the suite is the only thing local that can see it.

THE DETECTORS ARE SELF-CHECKED IN BOTH DIRECTIONS. Each must bite on a real
violation and stay quiet on correct writing. A guard that cannot fail is
decorative; a guard that reddens on correct code gets deleted. Both failure
modes have already happened in this repo, so both are pinned.

Scope note: these check the SHIPPED surfaces an agent loads or executes.
design/ is excluded — TRDDs are a historical record and are allowed to describe
what the world used to look like.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

SHIPPED_DIRS = ("agents", "skills", "commands", "hooks")


def _shipped_files() -> list[Path]:
    """Every file an agent loads as instructions or the harness executes."""
    out: list[Path] = []
    for d in SHIPPED_DIRS:
        root = REPO / d
        if root.is_dir():
            out.extend(sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in {".md", ".json"}))
    readme = REPO / "README.md"
    if readme.is_file():
        out.append(readme)
    return out


def _text(paths: list[Path]) -> list[tuple[Path, str]]:
    return [(p, p.read_text(encoding="utf-8", errors="replace")) for p in paths]


def test_the_shipped_file_set_is_not_empty() -> None:
    """A scan over an empty list passes while checking nothing."""
    assert len(_shipped_files()) > 20, f"only {len(_shipped_files())} shipped files discovered"


# ── Removed / deprecated features ────────────────────────────────────────────

# Removed in 2.1.222. Any instruction naming it sends an agent after a feature
# that no longer exists.
ULTRAPLAN = re.compile(r"\bultraplan\b", re.IGNORECASE)


def test_no_reference_to_the_removed_ultraplan_feature() -> None:
    """`ultraplan` was removed in 2.1.222 — instructions must not send agents to it."""
    offenders = [f"{p.relative_to(REPO)}" for p, t in _text(_shipped_files()) if ULTRAPLAN.search(t)]
    assert not offenders, f"references a removed feature (2.1.222): {offenders}"


def test_the_ultraplan_detector_bites() -> None:
    """Positive control — else the assertion above is vacuous."""
    assert ULTRAPLAN.search("run /ultraplan first")
    assert not ULTRAPLAN.search("run /plan first")


# Removed in 2.1.233 on Opus 4.8, Sonnet 5, Fable 5, Mythos 5 "and newer models"
# — i.e. on every model this plugin actually runs under. A shipped instruction
# naming one sends an agent to a tool that is not in its tool list, and the
# failure is silent in the worst way: the agent reads "record it with TaskCreate",
# cannot, and either invents a substitute or drops the bookkeeping. The global
# TRDD rule still teaches this idiom (`a TaskCreate entry naming the id`), so the
# likely path into this tree is an author copying that sentence into a skill.
# `CLAUDE_CODE_ENABLE_TODO_TOOLS=1` restores them, but a shipped instruction
# cannot assume a host set it.
#
# CASE-SENSITIVE, and that is load-bearing. This repo's kanban has a `todo`
# COLUMN, `task-type:` is a TRDD frontmatter field, and "task" is ordinary
# English throughout. A case-insensitive match would redden on correct writing on
# nearly every file — and a guard that reddens on correct writing gets deleted,
# which is how a repo loses a detector it still needs. Only the exact tool
# identifiers match.
TODO_TASK_TOOLS = re.compile(r"\b(?:TaskCreate|TaskUpdate|TaskGet|TaskList|TodoWrite)\b")


def test_no_reference_to_the_removed_todo_task_tools() -> None:
    """TaskCreate/Update/Get/List and TodoWrite are gone on modern models (2.1.233)."""
    offenders = [f"{p.relative_to(REPO)}" for p, t in _text(_shipped_files()) if TODO_TASK_TOOLS.search(t)]
    assert not offenders, f"names a Todo/Task tool removed on modern models (2.1.233) — track work in a TRDD card instead: {offenders}"


def test_the_todo_task_tool_detector_bites() -> None:
    """Positive control, both directions — the repo's own `todo`/`task` prose must NOT match."""
    assert TODO_TASK_TOOLS.search("record it with TaskCreate naming the id")
    assert TODO_TASK_TOOLS.search("call TodoWrite to update the list")
    assert TODO_TASK_TOOLS.search("TaskUpdate, TaskGet and TaskList are gone too")
    # The writing this guard must stay quiet on — all of it is live in this tree.
    assert not TODO_TASK_TOOLS.search("column: todo")
    assert not TODO_TASK_TOOLS.search("task-type: feature")
    assert not TODO_TASK_TOOLS.search("move the card to todo and pull the next task")
    assert not TODO_TASK_TOOLS.search("the session todo list is ephemeral")


# Deprecated in 2.1.222 when `/review` folded into `/code-review`; `/code-review
# ultra` is the surface now and `/ultrareview` is a legacy alias. Matched as the
# WHOLE word `ultrareview` only — never bare `review`, which legitimately appears
# in paths like `references/review-checklist.md` (a guard that reddens on correct
# writing gets deleted).
ULTRAREVIEW = re.compile(r"\bultrareview\b", re.IGNORECASE)


def test_no_reference_to_the_deprecated_ultrareview_alias() -> None:
    """`/ultrareview` is a deprecated alias (2.1.222) — name `/code-review ultra`."""
    offenders = [f"{p.relative_to(REPO)}" for p, t in _text(_shipped_files()) if ULTRAREVIEW.search(t)]
    assert not offenders, f"references the deprecated /ultrareview alias (2.1.222 — use /code-review ultra): {offenders}"


def test_the_ultrareview_detector_bites() -> None:
    """Positive control, both directions — bare `/review` must NOT match."""
    assert ULTRAREVIEW.search("run /ultrareview on the branch")
    assert not ULTRAREVIEW.search("run /code-review ultra on the branch")
    assert not ULTRAREVIEW.search("see references/review-checklist.md")


# ── gitleaks is banned (USER directive 2026-08-14) ───────────────────────────

# Single-threaded, single-process, and capped on file count — too slow to be
# useful at repo scale, so the USER banned it outright: no shipped instruction
# may send an agent to it (TruffleHog and the bundled fast_security_scan.py
# cover detection). Scope is wider than the other detectors because the ban
# also covers root config/docs that reference scanners.
GITLEAKS = re.compile(r"\bgitleaks\b", re.IGNORECASE)


def _gitleaks_scope() -> list[Path]:
    extra = [REPO / n for n in (".mega-linter.yml", "CONTRIBUTING.md", "SECURITY.md", "ACKNOWLEDGMENTS.md")]
    return _shipped_files() + [p for p in extra if p.is_file()]


def test_no_reference_to_the_banned_gitleaks_scanner() -> None:
    """gitleaks is banned (USER, 2026-08-14) — no shipped file may name it."""
    offenders = [f"{p.relative_to(REPO)}" for p, t in _text(_gitleaks_scope()) if GITLEAKS.search(t)]
    assert not offenders, f"references the banned gitleaks scanner (USER directive 2026-08-14 — use trufflehog or the bundled scanner): {offenders}"


def test_the_gitleaks_detector_bites() -> None:
    """Positive control — and the replacement scanners must not trip it."""
    assert GITLEAKS.search("fall back to gitleaks detect")
    assert GITLEAKS.search("write a .gitleaks.toml allowlist")
    assert not GITLEAKS.search("fall back to trufflehog filesystem")
    assert not GITLEAKS.search("run fast_security_scan.py --workflows")


# ── `claude plugin` takes ONE positional ─────────────────────────────────────

# Reported on ai-maestro-maintainer-agent#35 and confirmed against the CLI's own
# usage line on 2.1.224, re-confirmed on 2.1.233 (the new `-y/--yes` flag is
# boolean, which the counter already treats safely):
# `Usage: claude plugin install|i [options] <plugin>` —
# ONE positional (`plugin@marketplace`). Commander SILENTLY DROPS a second one, so
# `install foo bar` resolves `foo` and ignores the marketplace. It works by luck
# until a plugin name is ambiguous, and then installs the wrong thing.
_PLUGIN_CMD = re.compile(r"claude\s+plugin\s+(?:install|uninstall|update)\s+(?P<args>[^\n`|;&]+)")

# Enumerated from `claude plugin install --help` / `update --help`, not assumed.
# Everything else (-h/--help, and any flag a future release adds) is treated as
# boolean, which is the SAFE direction: an unrecognised value-flag then makes its
# value look like a second positional and the test reddens loudly. The inverse
# default — assume every flag consumes the next token — is what the first draft
# did, and it let `--yes plugin@mkt` count as ZERO positionals: a real violation
# preceded by any boolean flag would have passed silently. A guard that
# under-counts is decorative; one that over-counts merely argues with you.
_VALUE_FLAGS = {"--config", "--scope", "-s"}


def _positional_count(argstr: str) -> int:
    """Count positionals, skipping only flags KNOWN to consume the next token."""
    n = 0
    skip_next = False
    for tok in argstr.split():
        if skip_next:
            skip_next = False
            continue
        if tok.startswith("-"):
            if "=" not in tok and tok in _VALUE_FLAGS:
                skip_next = True
            continue
        n += 1
    return n


def test_claude_plugin_invocations_pass_a_single_positional() -> None:
    """A second positional is silently dropped, so the marketplace never applies."""
    offenders: list[str] = []
    for path, text in _text(_shipped_files()):
        for m in _PLUGIN_CMD.finditer(text):
            if _positional_count(m.group("args")) > 1:
                offenders.append(f"{path.relative_to(REPO)}: {m.group(0).strip()[:80]}")
    assert not offenders, f"`claude plugin <verb>` takes ONE positional (plugin@marketplace); a second is silently dropped, so resolution works only by luck: {offenders}"


def test_the_positional_counter_distinguishes_the_two_forms() -> None:
    """The counter must separate the correct call from the silently-broken one."""
    assert _positional_count("ai-maestro-maintainer-agent@ai-maestro-plugins") == 1
    assert _positional_count("my-plugin my-marketplace") == 2  # the broken shape
    # A real value-flag consumes its value; neither is a positional.
    assert _positional_count("--scope user my-plugin@mkt") == 1
    assert _positional_count("-s project my-plugin@mkt") == 1
    assert _positional_count("--config key=value my-plugin@mkt") == 1
    assert _positional_count("--scope=user my-plugin@mkt") == 1


def test_a_boolean_flag_does_not_swallow_the_violation() -> None:
    """The regression that broke the first draft — and it hid a violation, not a pass.

    Assuming every flag takes a value made `--help plugin@mkt` count ZERO
    positionals, so `--help a b` counted ONE and the broken form went unreported.
    An unknown flag must never consume the token after it.
    """
    assert _positional_count("--help my-plugin@mkt") == 1
    assert _positional_count("--some-future-boolean a b") == 2  # still caught


# ── Agent names may not contain ':' (2.1.218) ────────────────────────────────


def test_agent_names_carry_no_colon() -> None:
    """':' is reserved for plugin namespacing; such agent files are rejected."""
    offenders: list[str] = []
    checked: list[str] = []
    for path in sorted((REPO / "agents").glob("*.md")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("name:"):
                name = line.partition(":")[2].strip()
                checked.append(name)
                if ":" in name:
                    offenders.append(f"{path.relative_to(REPO)}: {name}")
                break
    # Without this the whole check passes by finding no agents to check.
    assert checked, "no agent declared a name: — the glob or the frontmatter key moved"
    assert not offenders, f"agent names must not contain ':' (2.1.218): {offenders}"


# ── Permission-rule forms that now warn at startup (2.1.210) ─────────────────

# `Write(path)`, `NotebookEdit(path)` and `Glob(path)` emit a startup warning —
# the supported spellings are `Edit(path)` and `Read(path)`.
WARNED_PERM_RULE = re.compile(r"\b(?:Write|NotebookEdit|Glob)\(\s*[^)\s]+\s*\)")


def test_no_permission_rules_in_the_warned_forms() -> None:
    """Write()/NotebookEdit()/Glob() rules warn at startup — use Edit()/Read()."""
    offenders: list[str] = []
    for path, text in _text(_shipped_files()):
        for m in WARNED_PERM_RULE.finditer(text):
            offenders.append(f"{path.relative_to(REPO)}: {m.group(0)}")
    assert not offenders, f"permission rules that warn at startup (2.1.210): {offenders}"


def test_the_permission_rule_detector_cuts_both_ways() -> None:
    """It must catch the warned forms and leave the prescribed ones alone."""
    assert WARNED_PERM_RULE.search("Write(src/**)")
    assert WARNED_PERM_RULE.search("Glob(**/*.py)")
    assert not WARNED_PERM_RULE.search("Edit(src/**)")
    assert not WARNED_PERM_RULE.search("Read(docs/**)")
    # Prose naming the tools is not a permission rule.
    assert not WARNED_PERM_RULE.search("use the Write tool, then Glob for files")


# ── Hook `if:` path semantics changed (2.1.214) ──────────────────────────────

# A single-segment `dir/**` in a hook `if:` condition now matches ONLY `<cwd>/dir`.
# Any-depth matching must be spelled `**/dir/**`. A condition written under the
# old semantics silently stops firing rather than erroring.
SINGLE_SEGMENT_GLOB = re.compile(r"^(?!\*\*/)[A-Za-z0-9_.-]+/\*\*$")


def test_hook_if_conditions_use_explicit_any_depth_globs() -> None:
    """`dir/**` now means <cwd>/dir only; any-depth must be `**/dir/**` (2.1.214)."""
    hooks = REPO / "hooks" / "hooks.json"
    if not hooks.is_file():
        pytest.skip("this plugin ships no hooks.json")
    blob = json.dumps(json.loads(hooks.read_text(encoding="utf-8")))
    offenders = [c for c in re.findall(r'"if"\s*:\s*"([^"]+)"', blob) if SINGLE_SEGMENT_GLOB.match(c)]
    assert not offenders, f"hook `if:` conditions using a single-segment `dir/**` match only <cwd>/dir since 2.1.214 and silently stop firing elsewhere; write `**/dir/**`: {offenders}"


def test_the_single_segment_glob_detector_cuts_both_ways() -> None:
    """Catches the narrowed form, accepts the explicit any-depth spelling."""
    assert SINGLE_SEGMENT_GLOB.match("src/**")
    assert SINGLE_SEGMENT_GLOB.match("scripts/**")
    assert not SINGLE_SEGMENT_GLOB.match("**/src/**")  # the prescribed fix
    assert not SINGLE_SEGMENT_GLOB.match("src/lib/**")  # already multi-segment
