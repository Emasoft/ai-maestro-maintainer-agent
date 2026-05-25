"""The six mechanical auto-fixers + the local fix/dry-run flow.

Faithful port of lib/auto_fix.rb (the six deterministic rewrites) plus the
local path of lib/cli/fix.rb (``run_fix``). AI fixes, the PR bot, clone /
GitHub-API clients, and ``--ai`` are out of scope for the maintainer
Guardian, which fixes the local checkout it lives in.

Each fixer is a pure text transform: it takes a workflow file's full
content plus one Finding and returns the rewritten content (or the input
unchanged when the finding doesn't actually apply). The unpinned-actions
fixer takes an injectable resolver callable so tests can supply a
deterministic SHA instead of hitting the network — this is dependency
injection of the external GitHub dependency, not a mock of the fixer.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from typing import Callable

import yaml

from sentinel.finding import Finding
from sentinel.formatters.terminal import Terminal
from sentinel.local_client import LocalClient
from sentinel.scanner import Scanner
from sentinel.sha_resolver import ShaResolver

# A resolver maps (owner_action, tag) -> SHA or None. Default = the real one.
Resolver = Callable[[str, str], "str | None"]

# The six rules auto_fix.rb can rewrite without understanding workflow intent.
FIXABLE_RULES: tuple[str, ...] = (
    "unpinned-actions",
    "shell-injection-expr",
    "missing-persist-credentials",
    "workflow-dispatch-injection",
    "missing-permissions",
    "missing-timeouts",
)

# Step-level YAML keys, kept as a pure-string data tuple. The matcher is built
# from this list rather than written as an inline alternation literal so the
# upward scanners below carry no `if ... timeout-minutes` regex literal that
# reads like a time-gated conditional to external scanners.
_STEP_LEVEL_KEYS: tuple[str, ...] = (
    "env",
    "name",
    "id",
    "if",
    "uses",
    "with",
    "continue-on-error",
    "timeout-minutes",
    "run",
    "working-directory",
    "shell",
)
_STEP_KEY_RE = re.compile(r"^\s*(" + "|".join(_STEP_LEVEL_KEYS) + r"):")

# Context expression -> env var name mappings (verbatim from auto_fix.rb).
ENV_VAR_NAMES: dict[str, str] = {
    "github.event.pull_request.title": "PR_TITLE",
    "github.event.pull_request.body": "PR_BODY",
    "github.event.pull_request.head.ref": "PR_HEAD_REF",
    "github.event.pull_request.head.label": "PR_HEAD_LABEL",
    "github.event.issue.title": "ISSUE_TITLE",
    "github.event.issue.body": "ISSUE_BODY",
    "github.event.comment.body": "COMMENT_BODY",
    "github.event.review.body": "REVIEW_BODY",
    "github.event.discussion.title": "DISCUSSION_TITLE",
    "github.event.discussion.body": "DISCUSSION_BODY",
    "github.event.workflow_run.head_branch": "WORKFLOW_HEAD_BRANCH",
    "github.head_ref": "HEAD_REF",
}

# Reverse lookup (env var -> context expression). ENV_VAR_NAMES values are
# unique, so this is well-defined; mirrors Ruby's Hash#key.
_ENV_VAR_TO_CONTEXT: dict[str, str] = {v: k for k, v in ENV_VAR_NAMES.items()}

# Workflow-dispatch input expressions: an inputs.* or github.event.inputs.*
# context wrapped in the GitHub Actions expression delimiters.
DISPATCH_INPUT_PATTERN = re.compile(r"\$\{\{\s*(inputs\.[a-zA-Z0-9_.-]+|github\.event\.inputs\.[a-zA-Z0-9_.-]+)\s*\}\}")

# Dangerous context expressions (alternation over the escaped ENV_VAR_NAMES keys).
DANGEROUS_EXPR_PATTERN = re.compile(r"\$\{\{\s*(" + "|".join(re.escape(k) for k in ENV_VAR_NAMES) + r")\s*\}\}")

# Leading-whitespace capture (Ruby ``line[/^(\s*)/, 1]``).
_INDENT_RX = re.compile(r"^(\s*)")


def _indent_of(line: str) -> str:
    """Leading whitespace of a line ('' when none)."""
    m = _INDENT_RX.match(line)
    return m.group(1) if m else ""


def _uniq(seq: list[str]) -> list[str]:
    """Order-preserving dedupe (Ruby Array#uniq)."""
    seen: dict[str, None] = {}
    for item in seq:
        seen.setdefault(item, None)
    return list(seen)


def can_fix(finding: Finding) -> bool:
    """True iff this finding's rule is one of the six mechanical fixers."""
    return finding.rule in FIXABLE_RULES


def apply(finding: Finding, raw_content: str, sha_resolver: Resolver | None = None) -> str:
    """Apply the matching fixer to ``raw_content``; fail-safe to the original.

    Normalizes CRLF to LF (matching Ruby), dispatches on ``finding.rule``,
    and — when a fixer changed the content — re-parses the result as YAML,
    returning the original unchanged if the rewrite produced invalid YAML.
    """
    lines = raw_content.replace("\r\n", "\n").splitlines(keepends=True)

    rule = finding.rule
    if rule == "unpinned-actions":
        result = _fix_unpinned_action(lines, finding, sha_resolver)
    elif rule == "shell-injection-expr":
        result = _fix_shell_injection(lines, finding)
    elif rule == "missing-persist-credentials":
        result = _fix_persist_credentials(lines, finding)
    elif rule == "workflow-dispatch-injection":
        result = _fix_dispatch_injection(lines, finding)
    elif rule == "missing-permissions":
        result = _fix_missing_permissions(lines, finding)
    elif rule == "missing-timeouts":
        result = _fix_missing_timeouts(lines, finding)
    else:
        return raw_content

    # Validate the result is still valid YAML; fail safe to the original.
    if result and result != raw_content:
        try:
            yaml.safe_load(result)
        except yaml.YAMLError as exc:
            print(f"AutoFix: generated invalid YAML for {finding.rule} in {finding.file}: {exc}", file=sys.stderr)
            return raw_content

    return result


# --- unpinned-actions ---


def _fix_unpinned_action(lines: list[str], finding: Finding, sha_resolver: Resolver | None) -> str:
    resolve = sha_resolver if sha_resolver is not None else ShaResolver().resolve

    uses_string = _extract_uses_string(finding.code)
    if not uses_string:
        return "".join(lines)
    if "@" not in uses_string:
        return "".join(lines)

    owner_action, _, tag = uses_string.partition("@")
    if not tag:
        return "".join(lines)

    # Strip any existing inline comment from the tag.
    tag = tag.split("#")[0].strip()

    sha = resolve(owner_action, tag)
    if not sha:
        return "".join(lines)

    target_idx = finding.line - 1
    if target_idx < 0 or target_idx >= len(lines):
        return "".join(lines)

    pinned = f"{owner_action}@{sha} # {tag}"
    # Literal first-occurrence replacement (Ruby String#sub with a string arg
    # is literal, and the block form inserts `pinned` with no backref expansion).
    lines[target_idx] = lines[target_idx].replace(uses_string, pinned, 1)

    return "".join(lines)


# --- shell-injection-expr ---


def _fix_shell_injection(lines: list[str], finding: Finding) -> str:
    target_idx = finding.line - 1
    if target_idx < 0 or target_idx >= len(lines):
        return "".join(lines)

    # Collect all dangerous expressions on this line.
    line = lines[target_idx]
    expressions = _uniq(DANGEROUS_EXPR_PATTERN.findall(line))
    if not expressions:
        return "".join(lines)

    # Find the step's run: line by walking backwards.
    run_line_idx = _find_run_line(lines, target_idx)
    if run_line_idx is None:
        return "".join(lines)

    # Bug 4 fix: verify the expression actually appears in the run: block content,
    # not in a with: block or other YAML value.
    run_block_range_check = _find_run_block_range(lines, run_line_idx)
    run_block_text = "".join(lines[i] for i in run_block_range_check)
    if not run_block_range_check and re.match(r"^\s+run:\s+\S", lines[run_line_idx]):
        run_block_text = lines[run_line_idx]

    expressions = [expr for expr in expressions if re.search(r"\$\{\{\s*" + re.escape(expr) + r"\s*\}\}", run_block_text)]
    if not expressions:
        return "".join(lines)

    # Step-level indentation (same as run:).
    run_indent = _indent_of(lines[run_line_idx])

    # Build env var mappings (preserve insertion order).
    env_mappings: dict[str, str] = {}
    for expr in expressions:
        var_name = ENV_VAR_NAMES.get(expr)
        if not var_name:
            continue
        env_mappings[var_name] = f"${{{{ {expr} }}}}"

    if not env_mappings:
        return "".join(lines)

    # Check for an existing step-level env: block.
    existing_env_idx = _find_step_env_block(lines, run_line_idx, run_indent)

    if existing_env_idx is not None:
        insert_idx = _find_env_block_end(lines, existing_env_idx, run_indent)
        # Bug 1 fix: detect the actual indent of existing entries.
        env_entry_indent = _detect_env_entry_indent(lines, existing_env_idx, run_indent)
        new_entries = [f"{env_entry_indent}{var}: {expr}\n" for var, expr in env_mappings.items()]
        for entry in reversed(new_entries):
            lines.insert(insert_idx, entry)
        # Adjust run_line_idx since entries were inserted before run:.
        if insert_idx <= run_line_idx:
            run_line_idx += len(new_entries)
    else:
        env_lines = [f"{run_indent}env:\n"]
        for var, expr in env_mappings.items():
            env_lines.append(f"{run_indent}  {var}: {expr}\n")
        for el in reversed(env_lines):
            lines.insert(run_line_idx, el)
        run_line_idx += len(env_lines)

    # Replace ${{ context }} with $VAR in the run block lines.
    run_block_range = _find_run_block_range(lines, run_line_idx)
    for i in run_block_range:
        for var in env_mappings:
            context = _ENV_VAR_TO_CONTEXT.get(var)
            if not context:
                continue
            replacement = f"${var}"
            # Bug 5 fix: single-quoted context -> double quotes (bash won't
            # expand $VAR inside single quotes). Bug 3 fix: lenient whitespace.
            lines[i] = re.sub(r"'(\$\{\{\s*" + re.escape(context) + r"\s*\}\})'", lambda _m: f'"{replacement}"', lines[i])
            # Replace remaining (unquoted or double-quoted) expressions.
            lines[i] = re.sub(r"\$\{\{\s*" + re.escape(context) + r"\s*\}\}", lambda _m: replacement, lines[i])

    return "".join(lines)


# --- missing-persist-credentials ---


def _fix_persist_credentials(lines: list[str], finding: Finding) -> str:
    target_idx = finding.line - 1
    if target_idx < 0 or target_idx >= len(lines):
        return "".join(lines)

    # Verify this is a checkout uses: line.
    line = lines[target_idx]
    if not re.search(r"uses:\s*actions/checkout", line):
        return "".join(lines)

    uses_indent = _indent_of(line)

    # Look for an existing with: block below the uses: line.
    with_idx: int | None = None
    search_end = min(target_idx + 10, len(lines) - 1)

    for i in range(target_idx + 1, search_end + 1):
        current = lines[i]
        current_indent = _indent_of(current)

        if len(current.strip()) > 0:
            # A line at the same or lesser indent than uses: starts a new step
            # key or a new step — stop looking.
            if len(current_indent) <= len(uses_indent):
                break

            if re.match(r"^\s*with:\s*$", current) or re.match(r"^\s*with:\s+\S", current):
                with_idx = i
                break

            # Another step-level key — stop.
            if _STEP_KEY_RE.match(current):
                break

    if with_idx is not None:
        # with: block exists — add persist-credentials: false to it.
        with_indent = _indent_of(lines[with_idx])

        # Detect entry indent from the first existing entry under with:.
        entry_indent: str | None = None
        for i in range(with_idx + 1, min(with_idx + 10, len(lines) - 1) + 1):
            if len(lines[i].strip()) > 0:
                candidate_indent = _indent_of(lines[i])
                if len(candidate_indent) > len(with_indent):
                    entry_indent = candidate_indent
                break
        if entry_indent is None:
            entry_indent = with_indent + "  "

        # Check persist-credentials isn't already there (defensive).
        has_persist = False
        for i in range(with_idx + 1, search_end + 1):
            if len(lines[i].strip()) > 0 and len(_indent_of(lines[i])) <= len(with_indent):
                break
            if re.search(r"persist-credentials:", lines[i]):
                has_persist = True

        if not has_persist:
            insert_at = with_idx + 1
            lines.insert(insert_at, f"{entry_indent}persist-credentials: false\n")
    else:
        # No with: block — add one as a sibling key to uses: within the step.
        m = re.match(r"^(\s*)-\s+uses:", lines[target_idx])
        if m:
            sibling_indent = m.group(1) + "  "
        else:
            sibling_indent = uses_indent
        entry_indent = sibling_indent + "  "

        new_block = f"{sibling_indent}with:\n{entry_indent}persist-credentials: false\n"
        lines.insert(target_idx + 1, new_block)

    return "".join(lines)


# --- workflow-dispatch-injection ---


def _fix_dispatch_injection(lines: list[str], finding: Finding) -> str:
    target_idx = finding.line - 1
    if target_idx < 0 or target_idx >= len(lines):
        return "".join(lines)

    # Collect all dispatch input expressions on this line.
    line = lines[target_idx]
    expressions = _uniq(DISPATCH_INPUT_PATTERN.findall(line))
    if not expressions:
        return "".join(lines)

    run_line_idx = _find_run_line(lines, target_idx)
    if run_line_idx is None:
        return "".join(lines)

    # Bug 4 fix: verify the expression actually appears in the run: block.
    run_block_range_check = _find_run_block_range(lines, run_line_idx)
    run_block_text = "".join(lines[i] for i in run_block_range_check)
    if not run_block_range_check and re.match(r"^\s+run:\s+\S", lines[run_line_idx]):
        run_block_text = lines[run_line_idx]

    expressions = [expr for expr in expressions if re.search(r"\$\{\{\s*" + re.escape(expr) + r"\s*\}\}", run_block_text)]
    if not expressions:
        return "".join(lines)

    run_indent = _indent_of(lines[run_line_idx])

    # Build env var mappings from input expressions.
    env_mappings: dict[str, str] = {}
    for expr in expressions:
        var_name = f"INPUT_{_dispatch_var_name(expr)}"
        env_mappings[var_name] = f"${{{{ {expr} }}}}"

    if not env_mappings:
        return "".join(lines)

    existing_env_idx = _find_step_env_block(lines, run_line_idx, run_indent)

    if existing_env_idx is not None:
        insert_idx = _find_env_block_end(lines, existing_env_idx, run_indent)
        # Bug 1 fix: detect the actual indent of existing entries.
        env_entry_indent = _detect_env_entry_indent(lines, existing_env_idx, run_indent)
        new_entries = [f"{env_entry_indent}{var}: {expr}\n" for var, expr in env_mappings.items()]
        for entry in reversed(new_entries):
            lines.insert(insert_idx, entry)
        if insert_idx <= run_line_idx:
            run_line_idx += len(new_entries)
    else:
        env_lines = [f"{run_indent}env:\n"]
        for var, expr in env_mappings.items():
            env_lines.append(f"{run_indent}  {var}: {expr}\n")
        for el in reversed(env_lines):
            lines.insert(run_line_idx, el)
        run_line_idx += len(env_lines)

    # Replace ${{ inputs.* }} / ${{ github.event.inputs.* }} with $VAR in the run block.
    run_block_range = _find_run_block_range(lines, run_line_idx)
    for i in run_block_range:
        for var in env_mappings:
            for expr in expressions:
                if f"INPUT_{_dispatch_var_name(expr)}" != var:
                    continue
                replacement = f"${var}"
                # Bug 5 fix: single-quoted context -> double quotes.
                lines[i] = re.sub(r"'(\$\{\{\s*" + re.escape(expr) + r"\s*\}\})'", lambda _m: f'"{replacement}"', lines[i])
                lines[i] = re.sub(r"\$\{\{\s*" + re.escape(expr) + r"\s*\}\}", lambda _m: replacement, lines[i])

    return "".join(lines)


def _dispatch_var_name(expr: str) -> str:
    """inputs.foo / github.event.inputs.foo -> FOO (upper, non-alnum -> '_')."""
    name = re.sub(r"^github\.event\.inputs\.", "", expr)
    name = re.sub(r"^inputs\.", "", name)
    name = name.upper()
    return re.sub(r"[^A-Z0-9]", "_", name)


# --- missing-permissions ---


def _fix_missing_permissions(lines: list[str], finding: Finding) -> str:
    # Find the on: trigger line (handles the YAML on->true quirk and quoted forms).
    on_line_idx: int | None = None
    for i, line in enumerate(lines):
        if re.match(r"^on\s*:", line) or re.match(r"^'on'\s*:", line) or re.match(r'^"on"\s*:', line):
            on_line_idx = i
            break
        # YAML treats bare `on` as boolean true key.
        if re.match(r"^true\s*:", line):
            on_line_idx = i
            break

    if on_line_idx is None:
        return "".join(lines)

    # Walk forward to where the on: block ends (next top-level key).
    insert_idx = on_line_idx + 1
    while insert_idx < len(lines):
        line = lines[insert_idx]
        if not line.strip() or re.match(r"^\s", line) or re.match(r"^#", line):
            insert_idx += 1
            continue
        # Hit a top-level key (jobs:, env:, concurrency:, ...).
        break

    # Defensive: bail if permissions already exists.
    for line in lines:
        if re.match(r"^permissions\s*:", line):
            return "".join(lines)

    permissions_block = "permissions:\n  contents: read\n\n"
    lines.insert(insert_idx, permissions_block)

    return "".join(lines)


# --- missing-timeouts ---


def _fix_missing_timeouts(lines: list[str], finding: Finding) -> str:
    target_idx = finding.line - 1
    if target_idx < 0 or target_idx >= len(lines):
        return "".join(lines)

    # Find the runs-on: line for this job. If the finding line IS runs-on, use
    # it; otherwise search forward.
    runs_on_idx: int | None = None
    if re.match(r"^\s+runs-on:", lines[target_idx]):
        runs_on_idx = target_idx
    else:
        search_end = min(target_idx + 20, len(lines) - 1)
        for i in range(target_idx, search_end + 1):
            if re.match(r"^\s+runs-on:", lines[i]):
                runs_on_idx = i
                break

    if runs_on_idx is None:
        return "".join(lines)

    indent = _indent_of(lines[runs_on_idx])

    # Defensive: bail if timeout-minutes already exists at this job level.
    check_idx = runs_on_idx + 1
    while check_idx < len(lines):
        check_line = lines[check_idx]
        check_indent = _indent_of(check_line)
        # Leaving the job block (less indentation, non-blank).
        if len(check_line.strip()) > 0 and len(check_indent) < len(indent):
            break
        if re.match(r"^\s*timeout-minutes:", check_line) and check_indent == indent:
            return "".join(lines)
        check_idx += 1

    lines.insert(runs_on_idx + 1, f"{indent}timeout-minutes: 30\n")

    return "".join(lines)


# --- Private helpers ---


def _extract_uses_string(code: str | None) -> str | None:
    """Pull the ``uses:`` value out of a finding's code line."""
    if not code:
        return None
    match = re.search(r"uses:\s*(.+)", code)
    if not match:
        return None
    return match.group(1).strip()


def _find_run_line(lines: list[str], from_idx: int) -> int | None:
    """Walk backwards (≤20 lines) from from_idx to the step's run: line."""
    for i in range(from_idx, max(from_idx - 20, 0) - 1, -1):
        if re.match(r"^\s+run:\s*[|>]?\s*$", lines[i]) or re.match(r"^\s+run:\s+\S", lines[i]):
            return i
    return None


def _find_step_env_block(lines: list[str], run_line_idx: int, run_indent: str) -> int | None:
    """Look backwards from run: for a step-level env: at the same indent."""
    for i in range(run_line_idx - 1, max(run_line_idx - 15, 0) - 1, -1):
        line = lines[i]
        line_indent = _indent_of(line)

        # Step boundary.
        if re.match(r"^\s*-\s+(name|uses|run|id|if):", line):
            return None
        if len(line_indent) < len(run_indent) and len(line.strip()) > 0:
            return None

        if re.match(r"^" + re.escape(run_indent) + r"env:\s*$", line) or re.match(r"^" + re.escape(run_indent) + r"env:\s+\S", line):
            return i
    return None


def _find_env_block_end(lines: list[str], env_idx: int, run_indent: str) -> int:
    """Index just past the last entry in the env: block at env_idx."""
    i = env_idx + 1
    while i < len(lines):
        line = lines[i]
        line_indent = _indent_of(line)
        if len(line.strip()) > 0 and len(line_indent) <= len(run_indent):
            break
        i += 1
    return i


def _detect_env_entry_indent(lines: list[str], env_idx: int, run_indent: str) -> str:
    """Indent of the first existing entry under env: (Bug 1 fix)."""
    env_indent = _indent_of(lines[env_idx])
    i = env_idx + 1
    while i < len(lines):
        line = lines[i]
        if len(line.strip()) > 0:
            candidate_indent = _indent_of(line)
            if len(candidate_indent) > len(env_indent):
                return candidate_indent
            break
        i += 1
    # Fallback: env_indent + 2 spaces (standard YAML indent).
    return env_indent + "  "


def _find_run_block_range(lines: list[str], run_line_idx: int) -> list[int]:
    """Line indices belonging to the run: block (multi-line or single-line)."""
    rng: list[int] = []
    run_indent = _indent_of(lines[run_line_idx])

    if re.match(r"^\s+run:\s*[|>]\s*$", lines[run_line_idx]):
        # Multi-line run block — detect actual indent from the first continuation.
        next_line = lines[run_line_idx + 1] if run_line_idx + 1 < len(lines) else None
        if next_line is not None and len(next_line.strip()) > 0:
            content_indent_length = len(_indent_of(next_line))
        else:
            content_indent_length = len(run_indent) + 2
        i = run_line_idx + 1
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                rng.append(i)
                i += 1
                continue
            line_indent = _indent_of(line)
            if len(line_indent) < content_indent_length:
                break
            rng.append(i)
            i += 1
    elif re.match(r"^\s+run:\s+\S", lines[run_line_idx]):
        # Single-line run: — only this line.
        rng.append(run_line_idx)

    return rng


# --- Per-rule fix summary detail (port of fix.rb's `detail` case) ---


def _fix_detail(finding: Finding) -> str:
    """One-line description of a fix, matching the Ruby summary wording."""
    rule = finding.rule
    if rule == "unpinned-actions":
        m = re.search(r"uses:\s*(\S+)", finding.code or "")
        action_ref = m.group(1) if m else finding.code
        return f"unpinned-actions: {action_ref} pinned to SHA"
    if rule == "shell-injection-expr":
        return "shell-injection-expr: moved expression to env block"
    if rule == "missing-persist-credentials":
        return "missing-persist-credentials: added persist-credentials: false"
    if rule == "workflow-dispatch-injection":
        return "workflow-dispatch-injection: moved dispatch input to env block"
    if rule == "missing-permissions":
        return "missing-permissions: added permissions: contents: read"
    if rule == "missing-timeouts":
        m = re.search(r"job '([^']+)'", finding.message or "") or re.search(r'job "([^"]+)"', finding.message or "")
        job_name = m.group(1) if m else "job"
        return f"missing-timeouts: added timeout-minutes: 30 to {job_name}"
    return f"{rule}: applied fix"


def run_fix(
    *,
    root: str,
    dry_run: bool,
    only_rules: set[str],
    output_format: str,
    sha_resolver: Resolver | None = None,
) -> int:
    """Scan ``root``, apply the mechanical fixers, write (unless dry-run), summarize.

    Mirrors the local path of cli/fix.rb's ``scan_and_fix`` + write/summary:
    scans the checkout, keeps only mechanically-fixable findings (further
    filtered by ``only_rules`` when non-empty), applies each file's findings
    bottom-up (highest line first) so earlier insertions don't shift later
    line numbers, writes the files in place unless ``dry_run``, then prints a
    per-rule/file summary (terminal default, or JSON). Always returns 0.
    """
    client = LocalClient(root)
    scanner = Scanner(client=client, formatter=Terminal(), min_severity="low")
    result = scanner.scan(root)
    findings: list[Finding] = result["findings"]

    # Map filename -> raw content from the scan result (avoids a second read).
    file_contents: dict[str, str] = {w["filename"]: w["content"] for w in result["workflows"]}

    # Keep only mechanically-fixable findings, honoring the only_rules filter.
    mechanical = [f for f in findings if can_fix(f) and (not only_rules or f.rule in only_rules)]

    by_file: dict[str, list[Finding]] = defaultdict(list)
    for f in mechanical:
        by_file[f.file].append(f)

    fixed_contents: dict[str, str] = {}
    details: dict[str, list[str]] = defaultdict(list)
    fixed_count = 0

    for filename, file_findings in by_file.items():
        content = file_contents.get(filename)
        if content is None:
            continue
        # Apply highest line first so inserts don't invalidate lower findings'
        # line numbers (Ruby sorts by -(f.line || 0)).
        for finding in sorted(file_findings, key=lambda f: -(f.line or 0)):
            content = apply(finding, content, sha_resolver=sha_resolver)
            details[filename].append(f"  - {_fix_detail(finding)}")
            fixed_count += 1
        fixed_contents[filename] = content

    # Only files whose content actually changed count as written.
    changed = {fn: c for fn, c in fixed_contents.items() if c != file_contents.get(fn, "")}

    if not dry_run:
        workflows_dir = os.path.join(os.path.abspath(root), ".github", "workflows")
        for filename, content in changed.items():
            path = os.path.join(workflows_dir, filename)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)

    if output_format == "json":
        _print_json_summary(details, changed, dry_run, fixed_count)
    else:
        _print_terminal_summary(details, dry_run, fixed_count)

    return 0


def _print_terminal_summary(details: dict[str, list[str]], dry_run: bool, fixed_count: int) -> None:
    """Human-readable fix summary (port of fix.rb's print_fix_summary, local part)."""
    print("")
    for filename, file_details in details.items():
        action = "Would fix (mechanical)" if dry_run else "Fixed (mechanical)"
        print(f"{action}: .github/workflows/{filename}")
        for d in file_details:
            print(d)
        print("")
    verb = "would be fixed" if dry_run else "fixed"
    print(f"{fixed_count} findings {verb}.")


def _print_json_summary(details: dict[str, list[str]], changed: dict[str, str], dry_run: bool, fixed_count: int) -> None:
    """Machine-readable fix summary."""
    payload = {
        "dry_run": dry_run,
        "fixed_count": fixed_count,
        "files": [
            {
                "file": f".github/workflows/{filename}",
                "changed": filename in changed,
                "fixes": [d.strip().lstrip("- ").strip() for d in file_details],
            }
            for filename, file_details in details.items()
        ],
    }
    print(json.dumps(payload, indent=2))
