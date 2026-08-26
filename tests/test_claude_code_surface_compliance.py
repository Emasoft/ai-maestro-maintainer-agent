"""This plugin must not use Claude Code surfaces that upstream removed or changed.

Every check here corresponds to a dated CHANGELOG entry, and every one was
measured absent from this tree on 2026-08-07 against Claude Code 2.1.224, then
re-measured on 2026-08-15 against Claude Code 2.1.233 (auditing the 2.1.225 →
2.1.232 changelog; the CLI claims below were re-run against the live binary,
not re-dated), then again on 2026-08-22 against 2.1.240 (auditing the 2.1.233 →
2.1.240 changelog), then again on 2026-08-26 against 2.1.246 (auditing the
2.1.240 → 2.1.246 changelog). The file exists so that stays true without anyone
re-reading a changelog.

The 2026-08-22 pass added ONE detector (the Todo/Task tool family, removed on
modern models in 2.1.233) and confirmed the rest of that changelog needed no
edit here: the persona's session-channel bullet already carried 2.1.232's
bare-name `SendMessage` delivery, and a whole-tree grep found no model id, no
`extraKnownMarketplaces`/`strictKnownMarketplaces` setting, and no
`allowed-tools` frontmatter for the renamed/aliased surfaces to invalidate. That
"nothing to change" is recorded deliberately — an audit that finds nothing looks
identical to an audit nobody ran.

The 2026-08-26 pass added TWO detectors — the wildcard-before-subcommand Bash
allow rule that now warns at startup (2.1.246), and a UTF-8 BOM at the head of a
shipped file (2.1.239 for agent/skill/command `.md`, 2.1.246 for `plugin.json`).
Both were measured ABSENT from the whole tree before the guards were written, so
neither is a fix; each is a trap set on a class upstream has just shown can
break us. The BOM one earns its place by FAILURE MODE, not by regex: a BOM made
a shipped `.md` *silently ignored* — no error, no warning, the skill simply did
not exist — which is the one class a green suite can never otherwise reveal.

WHAT THE BASH DETECTOR'S GREEN DOES NOT MEAN. Measured on 2026-08-26: the
shipped file set is 140 files and contains **zero** `Bash(...)` occurrences of
any kind. So that detector passing is not "we checked the Bash rules and none
front a subcommand" — this plugin ships no Bash permission rules at all, and
the guard verifies nothing about the present. It is purely forward-looking.
Recorded because a gate pointed at an empty set looks exactly like a gate
finding nothing wrong, and the difference is the whole point of this file.

That detector also cost two wrong versions before this one, which is worth
knowing before anyone "improves" it: a token-based regex measured 3/16 wrong
(missed glued spellings), a positional rewrite measured 4/16 — WORSE, because
it bit `Bash(find . -name "*.py" -delete)` and every other ordinary argument
glob. The current narrow form measures 1/16, its single miss being a spelling
that is lexically identical to a case that must stay quiet. The full reasoning
sits with the regex; the lesson for this docstring is that the second attempt
failed by testing a hand-rolled model against a table written from the same
model, so the oracle could not see the instrument's error.

Everything else in the 2.1.240 → 2.1.246 delta was measured and needed no edit,
recorded here for the same reason as above. Whole-tree greps (the instrument
sanity-checked against known-present strings first) found: no Todo/Task tool
name, no `ultraplan`/`ultrareview` outside this file's own detectors and one
archived TRDD, no `extraKnownMarketplaces`/`strictKnownMarketplaces`, no
`allowed-tools`/`disallowed-tools` frontmatter, no `claude-*-N` model id, no
`subagent_type`, no `context: fork`. The GitLab token families from 2.1.232 were
re-confirmed already complete across `scripts/security_catalog.json`,
`scripts/redact.py` and `skills/maintainer-redact/references/redaction-map.md`
(both routable prefixes plus all nine non-routable ones). `maintainer-config-lint`
was checked specifically and is NOT affected by the new 2.1.235–2.1.243 settings
keys (`spellcheck`, `keybindingFlavor`, `modelPicker`, `promptCacheTtl`,
`subagentPromptCacheTtl`, `modelPricing`, `workflowSizeGuideline`): it lints
generic JSON/YAML/TOML/.env/Dockerfile and carries no Claude Code settings-key
allowlist to go stale. The `Unknown key` logic in `scripts/sentinel/policy.py`
governs the sentinel's own policy file, not Claude Code settings.

MIND THE GAP BETWEEN THAT SWEEP AND THESE GUARDS. The 2026-08-22 sweep was
whole-tree; `_shipped_files()` below is NOT. It covers `.md`/`.json` under
agents/skills/commands/hooks plus README — so `scripts/` (144 files) and every
`.sh`/`.py`/`.yaml` anywhere are OUTSIDE these detectors. "This tree is clean
today" is a stronger statement than "a future violation will be caught here",
and only the first was measured tree-wide. The narrower guard is deliberate —
these check what an agent LOADS AS INSTRUCTIONS, and a Python script naming a
tool identifier is a different concern with a different owner — but do not read
a green suite as tree-wide coverage. It is not.

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


# ── Bash allow rules: no wildcard BEFORE the subcommand (2.1.246) ────────────

# 2.1.246 warns at startup on a Bash allow rule whose `*` sits before the
# subcommand, e.g. `Bash(git * main)`. The reason is a real widening, not a
# style nit: such a rule ALSO matches options inserted before the subcommand, so
# `Bash(git * main)` grants `git -c core.pager=<anything> main` and every other
# option smuggled into that slot. A trailing `*` (`Bash(gh *)`), the
# prefix-colon form (`Bash(git commit:*)`) and a trailing glob after a dash
# (`Bash(git -*)`) all leave nothing standing after the wildcard, so they are
# safe and must stay quiet — a guard that reddens on correct writing gets
# deleted.
#
# THE SCOPE IS DELIBERATELY NARROW, AND THE NARROWING IS THE INTERESTING PART.
# Two earlier versions of this detector were measured wrong, in opposite
# directions, and the second was worse than the first:
#
#   token-based  `(?:^|\s)\*(?=\s+\S)`   3/16 wrong — missed glued spellings
#   positional   `\*[^*]*[^\s*]`         4/16 wrong — bit `find . -name "*.py"`
#
# The positional rewrite was an attempt to "match the class instead of the
# example". It matched a WIDER class than 2.1.246 warns about, and the case
# table could not see it because the table and the regex had the same author —
# the proxy failure reappearing one level up, in the oracle rather than the
# instrument.
#
# The tension is not fixable by a better regex. `git *main` (a fronted
# subcommand, which upstream warns about) and `git *.py` (a trailing file glob,
# which it does not) are the SAME lexical shape; only intent separates them. A
# guard that fires on `Bash(find . -name "*.py" -delete)` gets deleted by the
# first person it annoys — which is this file's own stated failure mode — so
# the honest move is to cover the shape we can define and say plainly what is
# out of scope, rather than to bite a class we cannot express.
#
# So: a bare `*` TOKEN followed by a bare WORD token — upstream's own spelling
# and the realistic hand-written variants. Measured 1/16 wrong, and that one is
# the glued `git *main`, knowingly out of scope per the paragraph above.
_BASH_RULE = re.compile(r"Bash\(([^)]*)\)")
_WILDCARD_BEFORE_TOKEN = re.compile(r"(?:^|\s)\*\s+[A-Za-z0-9][A-Za-z0-9._-]*(?=\s|$)")


def _bash_rules_with_leading_wildcard(text: str) -> list[str]:
    """Known gaps, stated rather than left to be rediscovered.

    OUT OF SCOPE (fail-open, accepted): the glued spelling `Bash(git *main)`,
    for the reason above; and a rule whose command embeds a paren
    (`Bash(bash -c 'f() { :; }' * main)`) or wraps across a line, because
    `[^)]*` cannot cross a `)`.

    WILL FIRE ON DOCUMENTATION, and that is a policy, not an oversight. The
    `Bash(` literal is unanchored, so a shipped `.md` that pastes the bad form
    verbatim to warn against it reddens the suite. A comment cannot mitigate a
    false positive — only the regex can — so this one is not filed under
    "documented limit": the rule is that a shipped file NAMES the anti-pattern
    ("a wildcard before the subcommand") instead of pasting a live rule. If a
    literal example is truly needed, break the token so it is not a rule.
    """
    return [m.group(0) for m in _BASH_RULE.finditer(text) if _WILDCARD_BEFORE_TOKEN.search(m.group(1))]


def test_no_bash_allow_rule_puts_a_wildcard_before_the_subcommand() -> None:
    """`Bash(git * main)` warns since 2.1.246 — the `*` also matches inserted options."""
    offenders: list[str] = []
    for path, text in _text(_shipped_files()):
        offenders.extend(f"{path.relative_to(REPO)}: {r}" for r in _bash_rules_with_leading_wildcard(text))
    assert not offenders, f"Bash allow rules with a wildcard before the subcommand warn at startup and match options inserted before it (2.1.246): {offenders}"


def test_the_leading_wildcard_detector_cuts_both_ways() -> None:
    """It must catch the widened form and leave every safe spelling alone."""
    assert _bash_rules_with_leading_wildcard("Bash(git * main)")  # upstream's own example
    assert _bash_rules_with_leading_wildcard("Bash(* main)")
    assert _bash_rules_with_leading_wildcard("Bash(npm * run build)")
    assert _bash_rules_with_leading_wildcard("Bash(git * checkout)")
    # ORDINARY ASTERISKS IN ARGUMENTS. Every one of these is a normal command a
    # tooling repo writes, and NONE is the 2.1.246 class. They are pinned first
    # because a previous "wider" version of this detector bit all four — the
    # regression that would get the guard deleted, so it is the one most worth
    # holding down.
    assert not _bash_rules_with_leading_wildcard('Bash(echo "a * b")')
    assert not _bash_rules_with_leading_wildcard('Bash(find . -name "*.py" -delete)')
    assert not _bash_rules_with_leading_wildcard("Bash(git *.py)")
    assert not _bash_rules_with_leading_wildcard('Bash(grep -r "TODO.*x" src)')
    # Trailing wildcard: nothing sits after the `*`, so nothing is being fronted.
    assert not _bash_rules_with_leading_wildcard("Bash(gh *)")
    assert not _bash_rules_with_leading_wildcard("Bash(npm run *)")
    assert not _bash_rules_with_leading_wildcard("Bash(git * )")
    assert not _bash_rules_with_leading_wildcard("Bash(git * *)")
    # A trailing glob after a dash is still trailing — `git -*` fronts nothing.
    # It is arguably dangerous on its own (`git -c core.pager=…` reaches
    # arbitrary config), but that is not 2.1.246's warning: the warning is about
    # a rule that still LOOKS scoped to a subcommand while admitting inserted
    # options. `git -*` is transparently broad. Pinned so the point stays settled.
    assert not _bash_rules_with_leading_wildcard("Bash(git -*)")
    # The prefix-colon form is the prescribed spelling.
    assert not _bash_rules_with_leading_wildcard("Bash(git commit:*)")
    assert not _bash_rules_with_leading_wildcard("Bash(npm run test:*)")
    # Prose naming the tool is not a permission rule.
    assert not _bash_rules_with_leading_wildcard("run Bash(git status) then read the output")


def test_the_glued_spelling_is_a_documented_scope_gap_not_an_accident() -> None:
    """`git *main` is out of scope BECAUSE it cannot be told from `git *.py`.

    Pinned as an explicit expectation rather than left as silence: the next
    reader who notices the miss should find the reason here instead of
    "widening" the regex back into biting every `find -name "*.py"`.
    """
    assert not _bash_rules_with_leading_wildcard("Bash(git *main)")
    # The indistinguishable twin — same lexical shape, opposite verdict wanted.
    assert not _bash_rules_with_leading_wildcard("Bash(git *.py)")


# ── A UTF-8 BOM makes a shipped file silently ignored (2.1.239, 2.1.246) ─────

# 2.1.239 fixed agents, skills and commands whose `.md` starts with a UTF-8 BOM
# being SILENTLY IGNORED; 2.1.246 fixed plugin installation failing on a
# `plugin.json` saved with one. Both are upstream fixes, so a BOM is no longer
# fatal on a current CLI — the guard exists because the failure mode is
# invisible: no error, no warning, the skill simply does not appear, and every
# user still on an older CLI sees exactly that. An editor or a Windows
# round-trip adds one without anyone typing it.
_BOM = b"\xef\xbb\xbf"


def _has_bom(path: Path) -> bool:
    """The predicate, kept separate so the bite test can call it on a tmp path."""
    with path.open("rb") as fh:
        return fh.read(3) == _BOM


def _files_starting_with_a_bom(paths: list[Path]) -> list[str]:
    return [str(p.relative_to(REPO)) for p in paths if _has_bom(p)]


def test_no_shipped_file_starts_with_a_utf8_bom() -> None:
    """A BOM makes a shipped .md silently ignored (2.1.239) and a plugin.json fail to install (2.1.246)."""
    offenders = _files_starting_with_a_bom(_shipped_files())
    assert not offenders, f"UTF-8 BOM at the head of a shipped file — silently ignored by Claude Code before 2.1.239/2.1.246, and still on any older CLI: {offenders}"


def test_the_bom_detector_cuts_both_ways(tmp_path: Path) -> None:
    """It must catch a real BOM and stay quiet on ordinary UTF-8, including non-ASCII."""
    bommed = tmp_path / "bommed.md"
    bommed.write_bytes(_BOM + b"---\nname: x\n---\n")
    clean = tmp_path / "clean.md"
    # Non-ASCII but no BOM — the case a naive "is it ASCII" check would flunk.
    clean.write_text("---\nname: x — dash\n---\n", encoding="utf-8")
    assert _has_bom(bommed)
    assert not _has_bom(clean)
    # And an empty file must not read as a BOM (short read, not a match).
    empty = tmp_path / "empty.md"
    empty.write_bytes(b"")
    assert not _has_bom(empty)


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
