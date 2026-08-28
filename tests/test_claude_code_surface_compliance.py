"""This plugin must not use Claude Code surfaces that upstream removed or changed.

Every check here corresponds to a dated CHANGELOG entry, and every one was
measured absent from this tree on 2026-08-07 against Claude Code 2.1.224, then
re-measured on 2026-08-15 against Claude Code 2.1.233 (auditing the 2.1.225 →
2.1.232 changelog; the CLI claims below were re-run against the live binary,
not re-dated), then again on 2026-08-22 against 2.1.240 (auditing the 2.1.233 →
2.1.240 changelog), then again on 2026-08-26 against 2.1.246 (auditing the
2.1.240 → 2.1.246 changelog), then again on 2026-08-27 against 2.1.247 (auditing
the 2.1.246 → 2.1.247 changelog), then again on 2026-08-28 against 2.1.248
(auditing the 2.1.247 → 2.1.248 changelog). The file exists so that stays true
without anyone re-reading a changelog.

The 2026-08-22 pass added ONE detector (the Todo/Task tool family, removed on
modern models in 2.1.233) and confirmed the rest of that changelog needed no
edit here: the persona's session-channel bullet already carried 2.1.232's
bare-name `SendMessage` delivery, and a whole-tree grep found no model id, no
`extraKnownMarketplaces`/`strictKnownMarketplaces` setting, and no
`allowed-tools` frontmatter for the renamed/aliased surfaces to invalidate. That
"nothing to change" is recorded deliberately — an audit that finds nothing looks
identical to an audit nobody ran.

The 2026-08-26 pass added ONE detector: a UTF-8 BOM at the head of a shipped
file (2.1.239 for agent/skill/command `.md`, 2.1.246 for `plugin.json`). It was
measured ABSENT from the whole tree first, so it is not a fix but a trap, and it
earns its place by FAILURE MODE rather than by pattern: a BOM made a shipped
`.md` *silently ignored* — no error, no warning, the skill simply did not exist
— which is the one class a green suite can never otherwise reveal. Its PREDICATE
is byte-exact and cannot be wrong; its FILE SET was wrong twice before it
settled, which is the corollary below and the more useful half of the story.

2.1.246's WILDCARD-BEFORE-SUBCOMMAND WARNING WAS AUDITED AND DELIBERATELY GOT NO
DETECTOR. Upstream now warns at startup on a Bash allow rule whose `*` precedes
the subcommand (`Bash(git * main)`), because such a rule also matches options
inserted into that slot. Measured on 2026-08-26: the shipped set is 140 files
containing ZERO `Bash(...)` occurrences of any spelling, so there was nothing to
fix. No guard was added, for a reason worth recording:

  the class is not separable by pattern match. `Bash(git * main)` (a fronted
  subcommand — warned) and `Bash(cp * dest)` (a shell glob and a destination —
  not warned) are the SAME lexical shape. Telling them apart requires knowing
  that git has subcommands and cp does not, which no regex encodes.

Five implementations were written and measured before that was accepted; four
were demonstrably wrong and each was wrong in a NEW direction — missing glued
spellings, biting `find . -name "*.py"`, dropping quoted-but-dangerous rules
like `Bash(git * commit -m "*")`, and finally biting `cp * dest`. A fifth,
scoped to `.json` so the surrounding context proves the string is a rule, is
believed correct — and was NOT shipped. Two reasons were given at the time and
only ONE of them holds up. The weak one: it was never measured against a case
table. That is true but carries little weight, because measuring it was one
command away; "unmeasured" was a state that could have been fixed rather than a
reason to drop it, and treating it as decisive would be a rationalisation.

The reason that survives is structural, not a matter of anyone's patience: scoped
to `.json` it would guard five files that hold no permission rules, so its worth
is the chance this plugin ever ships a `settings.json` carrying a Bash allow
rule, times the chance CI notices before the CLI does — and the CLI warns on
exactly this at startup, with a real parser, on the real rules. That product is
small for reasons that can be stated. `test_the_bash_wildcard_class_still_has_no_detector`
below is the enforceable form of "do not write a sixth"; a docstring is not a
control.

THE LESSON FROM THAT, because it generalises past this one detector: every wrong
version was validated against a hand-written case table, and the table was
written AFTER the pattern, from the pattern's shape — so the oracle inherited
the instrument's blind spot and could not reveal it. It is an ORDERING failure,
not an authorship one: a table written from the spec BEFORE any pattern exists
does not share the blind spot, and the same author can write it. Generating
cases from the spec did help here (it found three real misses nobody had named)
but was not sufficient, because those cases were generated along the axis the
last fix had just changed — the dimension a fix introduces is the one its author
is least likely to probe. Bigger table, same blind spot, one axis over. When a
guard needs its fifth rewrite, question whether the property is checkable at
this cost, not the pattern.

AND THE COROLLARY, learned immediately afterwards at this file's own expense: a
byte-exact predicate has no oracle problem, but its FILE LIST is an oracle too.
The BOM detector below shipped scanning a set inherited from detectors written
for a different question, and that set excluded `.claude-plugin/plugin.json` —
the one file 2.1.246 names. It was green because the set lacked the thing, which
is the failure this docstring had just finished describing, in the guard that
had been kept for having no such problem.

The first repair was to ENUMERATE the set instead of inheriting it, and that was
still wrong — the same failure with extra steps. Enumeration is green for
whatever the author did not think to list, and the list came from the changelog
entries read that day, so it missed `.mcp.json`, `.claude/settings.json` (named
in this very docstring, two paragraphs up) and a root-level `marketplace.json`.
That is v1's original error — deriving a rule from upstream's EXAMPLES rather
than from the property — reproduced three commits after the lesson was written
down, in the paragraph explaining the lesson.

What finally worked was changing the QUESTION, not the answer. "Which files does
Claude Code parse?" has no stable answer: it needs recall, it drifts every
release, and being wrong is silent. "Does this repo ship a BOM in a tracked text
file?" has no oracle at all — nothing to enumerate, nothing to keep current —
and it strictly contains every parse surface, including ones upstream has not
invented yet. When a set keeps being wrong, widen the property until the set
stops being a judgement call. That is cheaper than getting the judgement right,
and it cannot rot.

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

THE 2026-08-27 PASS AGAINST 2.1.247 ADDED NO DETECTOR AND CHANGED NO SHIPPED
FILE. All 33 changelog bullets were read IN FULL — the first draft of this pass
triaged eleven of them from a 140-character truncation, which is a proxy for a
bullet and got caught before it was believed — and triaged: 25 are CLI-internal
(TUI input handling, cloud-session and sign-in plumbing, terminal rendering)
with no plugin surface, and the 8 that touch one were each measured clean.
Sixteen topics were settled by grep over the tracked tree; the remainder were
dismissed from the bullet text alone, which is judgement, and is recorded as
judgement rather than folded into the word "measured". No
`SendFeedback`/`feedbackDrafts`/`/feedback` reference, and still no
`allowed-tools`/`disallowed-tools`/`tools:` frontmatter for the new feedback
surface to land on. No `spinnerTipsOverride` or `tipsFile`. No shipped
statement of a Sonnet auto-compact threshold — the two `context window` hits
are an ADR's generic phrase and a frozen archived TRDD. No claim that a
sub-agent DIES on a first-call model 404: README's model-overload paragraph is
about the session `fallbackModel`, which the new fallback chain is compatible
with rather than contradicted by. No UNC, `/net/` or `/Volumes/` markdown link
target, and no control or invisible codepoint in any `](...)` target. No
`/claude-api` reference to go stale on its new `cost-optimize` and Admin API
coverage. And no marketplace plugin entry, version-less or otherwise, because
this repo ships a plugin and no `marketplace.json` (nor a tracked `.mcp.json`).

COUNT THE SOURCE, NOT THE SUMMARY. That triage was delegated and came back as
eight items, which is what a complete audit and a partial one both look like.
The changelog has THIRTY-THREE bullets. Re-running the eight greps confirms
those eight are clean and says nothing at all about the other twenty-five: a
list's COMPLETENESS is the one property re-running its own instrument cannot
test. Reading the source settled it — the pre-filter was right, all 25 really
are CLI-internal — but "the filter was right" was an unverified assumption
until the source was read, which is the file-set failure one level up. A
delegate's blind spot arrives together with its findings.

2.1.247's CONTROL/INVISIBLE-CHARACTER NAME REJECTION WAS AUDITED AND
DELIBERATELY GOT NO DETECTOR. Upstream now rejects a plugin or marketplace name
containing control or invisible characters. Measured:
`.claude-plugin/plugin.json` is the only tracked manifest, and all 229 tracked
`.md`/`.json`/`.toml`/`.yml`/`.yaml` files — 1,654,338 characters — were scanned
for any codepoint whose Unicode general category is Cc, Cf, Co or Cs (newline
and tab excepted), plus NBSP and narrow NBSP. ZERO occurrences: not in a `name`,
not in prose. The instrument was sanity-checked against a needle first and bit
on all four classes.

THE PREDICATE IS A CATEGORY QUERY, NOT A CODEPOINT LIST, and the first draft of
this paragraph is why. It enumerated NBSP, soft hyphen, zero-width, bidi, word
joiner and U+FEFF — silently omitting the TAG block U+E0000-U+E007F (the modern
invisible-text-smuggling vector), the invisible math operators U+2061-U+2064,
and whatever Unicode assigns next. A paragraph whose thesis is that a file set
is an oracle had chosen its codepoint set the same way, one line below saying
so. `unicodedata.category` is maintained by someone else and updates with the
standard; a list in a docstring is maintained by whoever last remembered it.

Two shapes were considered and both rejected. Scoping the check to `name`
fields rebuilds the field-and-file oracle this docstring documents getting
wrong twice. Widening it to "no invisible codepoint anywhere" — the move that
rescued the BOM guard — does NOT transfer, and the reason is exact: the BOM
property has no exceptions, nothing wants a BOM, whereas U+200D is the joiner
inside ordinary multi-person and skin-tone emoji, NBSP and the bidi marks have
legitimate typographic uses, and CR is a legal line ending. The widened
predicate therefore has real false positives, which makes it a guard that gets
suppressed rather than fixed. That is the separability failure again, one level
up from the Bash class: "invisible codepoint" is no more separable from
"legitimate Unicode" by a codepoint list than `git * main` is from `cp * dest`
by a lexical one.

What remains is the wildcard-class trade, and it lands the same way. The worth
is P(an invisible character reaches a hand-typed kebab-case name in this repo)
times P(CI notices before the CLI does) — and 2.1.247 IS upstream driving the
second term to nearly zero, by rejecting exactly this itself, at load, on the
real field. Should one ever land, the fix is the narrowest available: a charset
pin `^[a-z0-9-]+$` on `plugin.json`'s own `name`, whose coverage is already
pinned by `test_the_bom_set_actually_contains_the_manifest`. Not the widened
predicate.

THE 2026-08-28 PASS AGAINST 2.1.248 ADDED NO DETECTOR EITHER, BUT UNLIKE THE
LAST TWO IT FOUND A REAL BUG. 49 bullets, counted from the fetched changelog
before triage and all read in full. Two shipped files changed, neither of them
this one:

`scripts/worktree.py` — 2.1.248 makes a backgrounded session HOLD THE
WORKTREE'S LOCK while it runs, expressly so cleanup leaves its checkout alone.
`remove_worktree` did `if not _git_ok("worktree","remove","--force",path):
_rmtree_with_backoff(path)`, and its own comment named "a lock" as an expected
cause of that refusal — so the fallback took the directory anyway. Measured on
real git 2.55.0, not assumed: `remove --force` on a locked worktree exits 128
with `cannot remove a locked working tree` and leaves the directory in place
(a lock needs `-f -f`). So upstream's new safety signal was being converted
into precisely the data loss it was added to prevent, and `force=` made it
worse rather than better — a live session that happens to be clean and on the
expected branch passes every `assert_safe_to_destroy` check, leaving the lock
as the only thing between it and the rm-rf. The guard now consults the `locked`
flag the porcelain parser was already producing and refuses, naming the lock
reason; `force=` deliberately does not override it, because callers mean
"discard work I own" by it, never "kill someone else's session".

`agents/…-main-agent.md` — the session-channel bullet's gate list now records
that 2.1.248 changed `crossSessionInbound`'s FAILURE mode: an invalid value
used to be ignored (a bad write left the channel open) and now warns and HOLDS,
or REFUSES under managed settings. The passage's thesis is unchanged; what is
new is that a silent channel has a second reading — a typo in that value, not
only an absent peer.

2.1.248's `experimental.cacheTtl` AGENT-FRONTMATTER FIELD WAS AUDITED AND
DELIBERATELY NOT ADOPTED. The changelog alone could not settle it, so the
decision came from the installed binary's own schema: `experimental: {cacheTtl}`
is documented there as "Prompt cache TTL for this agent's requests … when no
`subagentPromptCacheTtl` setting or env var is set", with "1h" ignored during
subscription overage — while the neighbouring MAIN-conversation TTL already
defaults to "1 hour on a Claude subscription within its usage limits". This
plugin ships one agent, launched by README as `claude --agent …`, i.e. as the
main conversation. So the field is a no-op in the documented launch mode, live
only if the agent is ever spawned as a SUBAGENT with no subagent TTL set, and
inert in overage regardless. An `experimental.` key that buys nothing in the
mode we actually run is a maintenance surface, not a saving.

The remaining 45 bullets were measured and needed no edit. The one that could
have broken this plugin at runtime — a hook whose stdout is a `{…}` that is not
valid JSON is now a hook ERROR, where it used to pass through as text — does
not apply: `hooks/hooks.json` carries exactly one hook (`SessionStart`, an
`echo` of prose beginning `[`), there are no `PermissionRequest`/`PreToolUse`
hooks to print an invalid answer, and `.claude/settings.json` declares no hooks
at all. Whole-tree greps found no reference to `ultrareview`, `--restricted` /
`CLAUDE_CODE_RESTRICTED`, `workflow-authoring`, `/loop`, `ScheduleWakeup`, or
`prod.env`, so the items touching those surfaces have nothing here to
invalidate. `recover_stale` was checked specifically and is NOT exposed to the
lock hazard: a locked worktree is still REGISTERED, so the orphan scan skips it
and `git worktree prune` never prunes it.

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
import subprocess
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
    # NOTE, since the docstring above says the Bash wildcard class got NO
    # detector for being pattern-inseparable. Two DIFFERENT questions, and an
    # earlier version of this comment ran them together:
    #
    # SEPARABILITY — this section is fine. `Write(...)`/`Glob(...)` are
    # permission-rule spellings with no ordinary-command twin, unlike
    # `Bash(cp * dest)`, so there is no `git *main` vs `git *.py` ambiguity.
    #
    # FALSE POSITIVES — this section is NOT immune, and the earlier comment
    # implied separability covered that too. It does not. `WARNED_PERM_RULE`
    # needs only a non-empty argument, so a sentence about the Write TOOL that
    # writes `Write(path)` WOULD match; the bite test below passes only because
    # its example has no parentheses at all. This plugin ships skills that
    # describe tool usage, so that is one documentation sentence away.
    #
    # Left alone rather than pre-emptively re-engineered, because the tree is
    # green and the risk is stated. If it ever fires on documentation, do what
    # the BOM detector did — fix the SET, or change the question — and do not
    # widen the regex, which is the move that failed four times above.


# ── The wildcard-before-subcommand class has NO detector, on purpose ─────────

# The symbols the four measured-wrong versions used. Matched at a LINE START
# only, so this file's own indented mention of them does not count as a revival.
_DELETED_BASH_SYMBOLS = ("_BASH_RULE", "_WILDCARD_BEFORE_TOKEN", "_bash_rules_with_leading_wildcard")


def _revived_bash_detector_names(source: str) -> list[str]:
    return [n for n in _DELETED_BASH_SYMBOLS if f"\n{n}" in source or f"def {n}" in source]


def test_the_bash_wildcard_class_still_has_no_detector() -> None:
    """A guard on the DECISION, since a docstring saying "do not" is not a control.

    Five patterns were written for 2.1.246's wildcard-before-subcommand warning
    and four were measured wrong, each in a new direction, because
    `Bash(git * main)` and `Bash(cp * dest)` are the same lexical shape. The
    module docstring records that; this fails if someone re-derives a sixth
    without reading it. It cannot false-positive — it asserts about this file,
    not about the tree.

    If a future Claude Code release makes the class separable (a documented rule
    grammar, say), delete this test in the same commit that adds the detector,
    and say so.
    """
    revived = _revived_bash_detector_names(Path(__file__).read_text(encoding="utf-8"))
    assert not revived, f"a Bash wildcard detector was re-added ({revived}) — read the docstring's account of the four measured-wrong versions first, then delete this test deliberately if you still mean to"


def test_the_absence_guard_bites_and_does_not_self_match() -> None:
    """It must fire on a revived symbol and NOT on its own mention of the names.

    A test that greps its own source is the `pgrep` self-match hazard: the
    scanner's argv contains the pattern. Anchoring on a line start is what keeps
    the indented tuple above from matching itself.

    THE FIXTURES ARE ASSEMBLED, NEVER WRITTEN OUT, and that is not fussiness —
    the first version of this test spelled `"def _bash_rules_with_leading_..."`
    as a literal and turned the suite red, because the fixture WAS a revival
    occurrence in the very file the guard scans. Same shape as the `[w]rite`
    bracket trick for `pgrep`: a self-scanning check must not contain the
    string it looks for.
    """
    const, helper = _DELETED_BASH_SYMBOLS[0], _DELETED_BASH_SYMBOLS[2]
    assert _revived_bash_detector_names(f'import re\n{const} = re.compile(r"x")\n') == [const]
    assert _revived_bash_detector_names("def " + helper + "(t):\n    pass\n") == [helper]
    # An indented mention (this file's own tuple) must stay quiet.
    assert not _revived_bash_detector_names(f'    names = ("{const}",)\n')


# ── A UTF-8 BOM makes a shipped file silently ignored (2.1.239, 2.1.246) ─────

# 2.1.239 fixed agents, skills and commands whose `.md` starts with a UTF-8 BOM
# being SILENTLY IGNORED; 2.1.246 fixed plugin installation failing on a
# `plugin.json` saved with one. Both are upstream fixes, so a BOM is no longer
# fatal on a current CLI — the guard exists because the failure mode is
# invisible: no error, no warning, the skill simply does not appear, and every
# user still on an older CLI sees exactly that. An editor or a Windows
# round-trip adds one without anyone typing it.
#
# THE SET IS CHOSEN HERE, NOT INHERITED, AND THAT IS THE LOAD-BEARING PART.
# This detector first shipped scanning `_shipped_files()` — the set the OTHER
# detectors use, which is `.md`/`.json` under agents/skills/commands/hooks plus
# README. Measured afterwards: that set does NOT contain
# `.claude-plugin/plugin.json`, which is the one file 2.1.246 actually names,
# nor the repo-root `*.agent.toml`. The predicate was unimpeachable and the
# guard was pointed at nothing — the same correct-instrument-wrong-set failure
# the docstring above describes for the Bash class, reproduced in the detector
# kept BECAUSE it "had no oracle problem". A byte-exact predicate has no oracle
# problem; a file list is an oracle, and this one had been chosen for a
# different question.
_BOM = b"\xef\xbb\xbf"

# THE SET IS NOT "WHAT CLAUDE CODE PARSES" — that question was got wrong twice.
# First by inheriting `_shipped_files()`, which missed `.claude-plugin/plugin.json`,
# the one file 2.1.246 names. Then by ENUMERATING three globs, which is the same
# failure with extra steps: green for everything not thought of, and the list was
# built from the changelog entries read that day, so it reproduced v1's original
# error — deriving a rule from upstream's EXAMPLES instead of from the property.
# `.mcp.json`, `.claude/settings.json` and a root-level `marketplace.json` were
# all missing, and `hooks/hooks.json` was covered only by accident of another
# detector's set.
#
# So the question changed instead of the answer. A BOM is never wanted in a
# tracked UTF-8 text file — not by Claude Code, not by cspell, not by anything —
# so the property is not "does Claude Code parse this" but "does this repo ship
# a BOM anywhere". That has NO oracle: no list to keep current, nothing to
# recall, and it strictly contains every parse surface that exists now or is
# added later, including files upstream has not invented yet.
#
# `git ls-files` is the set, which also makes gitignored runtime state
# (`.claude/janitor/`, `.claude/scheduled_tasks.*`, the memgrep index) fall out
# for free rather than by an exclusion list that would need its own maintenance.
# The SUFFIX list is still an enumeration, and knowingly so — it omits `.jsonc`,
# `.sh`, `.js`, `.txt`, `.env`. That is a bounded, visible, one-line judgement
# rather than a hidden one, and the omitted types fail LOUDLY: a BOM before
# `#!/usr/bin/env bash` is an exec-format error, not a silent skip. Widening to
# every tracked file would need a binary-file exclusion, which is a new
# judgement call — a worse trade than the gap it closes.
_BOM_SUFFIXES = frozenset({".md", ".json", ".toml", ".yml", ".yaml"})


def _bom_sensitive_files() -> list[Path]:
    """Every git-TRACKED text file. No enumeration, so nothing to keep current.

    SKIPS rather than errors without git. `check=True` here made a git-less
    checkout — an sdist export, a Docker stage that COPYs source without `.git`,
    a vendored install — fail two tests with a CalledProcessError traceback
    about git, which says "your repo is broken" when the truth is "not checked
    here". Every other detector in this file degrades to a smaller set when its
    input is thin; this one detonated. Measured: 2 failed, 20 passed in a clone
    with `.git` removed. Same `pytest.skip` shape the hooks.json detector uses.
    """
    proc = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        pytest.skip(f"no git work tree at {REPO} — BOM scan needs `git ls-files` for its file set")
    return sorted(p for rel in proc.stdout.split("\0") if rel and (p := REPO / rel).suffix in _BOM_SUFFIXES and p.is_file())


def _has_bom(path: Path) -> bool:
    """The predicate, kept separate so the bite test can call it on a tmp path."""
    with path.open("rb") as fh:
        return fh.read(3) == _BOM


def _files_starting_with_a_bom(paths: list[Path]) -> list[str]:
    return [str(p.relative_to(REPO)) for p in paths if _has_bom(p)]


def test_the_bom_set_actually_contains_the_manifest() -> None:
    """Per-detector empty-set pin: the tree-wide floor cannot see this gap.

    `test_the_shipped_file_set_is_not_empty` asserts >20 files and would stay
    green with the manifest missing, which is exactly how that gap survived.

    The manifest assertion is UNCONDITIONAL, deliberately. An earlier version
    guarded it with `if manifest.is_file()`, which meant the pin went quiet in
    the one scenario worth catching — someone relocates the manifest, the file
    stops existing at the expected path, and the guard stops guarding without
    saying so. A plugin repo without a manifest is broken anyway, so the honest
    assertion is that it exists AND is covered.

    THE EMPTY-SET FLOOR IS FIRST, and it is not redundant with the manifest
    assertion below. Measured: `git ls-files` in a repo with nothing tracked
    exits 0 with no output, so `returncode != 0` does not skip and the set comes
    back EMPTY — at which point `test_no_shipped_file_starts_with_a_utf8_bom`
    passes vacuously, scanning nothing. The manifest line does catch it, but
    reports "the manifest is missing" for a set that is entirely absent, sending
    the reader after the wrong fault. This is the gate-pointed-at-nothing shape
    the docstring above spends four paragraphs on, in the one detector kept, and
    it was the only detector without the non-empty floor every other one has.
    """
    files = _bom_sensitive_files()
    assert len(files) > 20, f"BOM set collapsed to {len(files)} files — scanning nothing passes vacuously"
    covered = {str(p.relative_to(REPO)) for p in files}
    assert ".claude-plugin/plugin.json" in covered, "2.1.246 names plugin.json — the BOM set must reach the manifest, and a plugin repo must have one"
    # The whole point of the tracked-files set is that it needs no per-type
    # upkeep; this pins the property rather than any particular glob.
    assert any(c.endswith(".agent.toml") for c in covered), "a BOM in a parsed .agent.toml is the same silent class"
    assert "hooks/hooks.json" in covered, "hooks.json must be covered on purpose, not by another detector's set"


def test_no_shipped_file_starts_with_a_utf8_bom() -> None:
    """A BOM makes a shipped .md silently ignored (2.1.239) and a plugin.json fail to install (2.1.246).

    THE FLOOR LIVES HERE, in the test that consumes the set. It was first put
    only in the sibling manifest test, which bought less than it appeared to:
    that made a sibling go red on an empty set, but this test's own verdict
    stayed PASS, so `pytest -k utf8_bom`, a bare node id, `--last-failed`, or a
    CI shard running a subset still scanned zero files green with nothing red
    anywhere. Measured: this test alone passes against a repo tracking one file.

    A guard that depends on which tests were selected is not a guard on the
    property — and putting it beside the problem instead of on it is the same
    shape as the defect it was added to fix.
    """
    files = _bom_sensitive_files()
    assert len(files) > 20, f"BOM set collapsed to {len(files)} files — scanning nothing passes vacuously"
    offenders = _files_starting_with_a_bom(files)
    assert not offenders, f"UTF-8 BOM at the head of a parsed file — silently ignored by Claude Code before 2.1.239/2.1.246, and still on any older CLI: {offenders}"


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
