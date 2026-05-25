"""YAML-aware workflow wrapper with line-mapping helpers.

Port of lib/workflow.rb. Exposes the exact surface every rule depends on:
raw_lines, line_content, line_of, lines_of, triggers, jobs, steps,
permissions, env, uses_actions, run_blocks, data, parse_error.

PyYAML parses a bare `on:` key as the Python boolean ``True`` (YAML 1.1
treats on/off/yes/no as booleans), exactly like Ruby's Psych — so
``triggers()`` checks both the "on" string key and the ``True`` key.
"""

from __future__ import annotations

import re
from typing import Any, Union

import yaml

# A rule may pass a precompiled pattern or a raw string.
PatternLike = Union[str, "re.Pattern[str]"]


def _rx(pattern: PatternLike) -> "re.Pattern[str]":
    """Compile a string pattern; pass through an already-compiled one."""
    return pattern if isinstance(pattern, re.Pattern) else re.compile(pattern)


# A `run:` step key (optionally a sequence item) and whatever follows the colon.
_RUN_KEY_RE = re.compile(r"^(\s*(?:-\s+)?)run:(.*)$")
# A block-scalar header after `run:` — `|`, `>`, with optional chomp/indent
# indicators (`|-`, `>+`, `|2`, `|2-`, …) and an optional trailing comment.
_BLOCK_SCALAR_RE = re.compile(r"^[|>][0-9+-]*\s*(?:#.*)?$")
_LEAD_WS_RE = re.compile(r"[ \t]*")


class Workflow:
    """One parsed workflow file. Construction never raises on bad YAML."""

    def __init__(self, filename: str, content: str) -> None:
        self.filename = filename
        self.raw = content
        # keepends=True mirrors Ruby String#lines (trailing "\n" retained).
        self.raw_lines = content.splitlines(keepends=True)
        self._parse_error: str | None = None
        self._run_content_cache: set[int] | None = None
        try:
            data = yaml.safe_load(content)
            self.data: dict[Any, Any] = data if isinstance(data, dict) else {}
        except yaml.YAMLError as exc:
            self.data = {}
            self._parse_error = str(exc)

    def parse_error(self) -> bool:
        """True iff the YAML failed to parse."""
        return self._parse_error is not None

    def triggers(self) -> Any:
        """The `on:` mapping/list/string (handles the on->True YAML quirk)."""
        if "on" in self.data and self.data["on"]:
            return self.data["on"]
        if True in self.data and self.data[True]:
            return self.data[True]
        return {}

    def jobs(self) -> dict[str, Any]:
        """The `jobs:` mapping, or {} when absent/malformed."""
        j = self.data.get("jobs")
        return j if isinstance(j, dict) else {}

    def steps(self, job: Any) -> list[Any]:
        """Steps for a job (by id or by job hash)."""
        job_hash = self.jobs().get(job) if isinstance(job, str) else job
        if not isinstance(job_hash, dict):
            return []
        s = job_hash.get("steps")
        return s if isinstance(s, list) else []

    def permissions(self, scope: str = "workflow", job: Any = None) -> Any:
        """Workflow-level or job-level `permissions:` block."""
        if scope == "workflow":
            return self.data.get("permissions")
        if scope == "job":
            j = self.jobs().get(job) if isinstance(job, str) else job
            return j.get("permissions") if isinstance(j, dict) else None
        return None

    def env(self, scope: str = "workflow", step: Any = None) -> dict[str, Any]:
        """Workflow-level or step-level `env:` mapping."""
        if scope == "workflow":
            e = self.data.get("env")
            return e if isinstance(e, dict) else {}
        if scope == "step":
            e = step.get("env") if isinstance(step, dict) else None
            return e if isinstance(e, dict) else {}
        return {}

    def line_of(self, pattern: PatternLike) -> int | None:
        """1-based line number of the first line matching `pattern`, else None."""
        rx = _rx(pattern)
        for i, line in enumerate(self.raw_lines):
            if rx.search(line):
                return i + 1
        return None

    def lines_of(self, pattern: PatternLike) -> list[int]:
        """All 1-based line numbers whose line matches `pattern`."""
        rx = _rx(pattern)
        return [i + 1 for i, line in enumerate(self.raw_lines) if rx.search(line)]

    def job_line(self, job_id: str) -> int | None:
        """1-based line of the real ``<job_id>:`` key directly under ``jobs:``.

        A bare ``line_of(r"^\\s+<job_id>:")`` search returns the *first*
        indented occurrence of the name, which may be a same-named entry in
        some job's ``outputs:`` / ``with:`` / ``env:`` block — e.g. astral-sh/uv
        ci.yml has both an output ``test-integration:`` (6-space indent, line 29)
        and a job ``test-integration:`` (2-space indent, line 218). This walks
        to the top-level ``jobs:`` mapping, learns the job-key indent from the
        first child key, and matches only a key at exactly that indent, so it
        always lands on the job *definition*. Returns None when not locatable;
        callers fall back to ``line_of`` / 0.
        """
        jobs_idx: int | None = None
        for i, line in enumerate(self.raw_lines):
            if re.match(r"^jobs:\s*(?:#.*)?$", line):
                jobs_idx = i
                break
        if jobs_idx is None:
            return None

        child_key_re = re.compile(r"^(\s+)[^\s:#][^:]*:")
        child_indent: int | None = None
        for line in self.raw_lines[jobs_idx + 1 :]:
            if line.strip() == "" or line.lstrip().startswith("#"):
                continue
            m = child_key_re.match(line)
            if m is None:
                break  # first real line under jobs: isn't an indented key
            child_indent = len(m.group(1))
            break
        if child_indent is None:
            return None

        job_re = re.compile(r"^ {" + str(child_indent) + r"}" + re.escape(job_id) + r":")
        for i in range(jobs_idx + 1, len(self.raw_lines)):
            if job_re.match(self.raw_lines[i]):
                return i + 1
        return None

    def line_content(self, num: int | None) -> str | None:
        """rstrip'd content of 1-based line `num`, or None when out of range."""
        if num is None or num < 1 or num > len(self.raw_lines):
            return None
        return self.raw_lines[num - 1].rstrip()

    def uses_actions(self) -> list[dict[str, Any]]:
        """Every `uses:` step with its source line, deduping repeated refs."""
        results: list[dict[str, Any]] = []
        seen_lines: dict[str, int] = {}
        for job_hash in self.jobs().values():
            for step in self.steps(job_hash):
                uses = step.get("uses") if isinstance(step, dict) else None
                if not uses:
                    continue
                # YAML strips quotes from the parsed value, but the raw line may
                # quote it (`uses: "actions/checkout@v4"`, as psf/requests does
                # throughout). Allow an optional surrounding quote so the source
                # line still resolves — otherwise the finding reports line 0.
                all_lines = self.lines_of(re.compile(r"""uses:\s*["']?""" + re.escape(str(uses))))
                idx = seen_lines.get(uses, 0)
                if idx < len(all_lines):
                    line = all_lines[idx]
                elif all_lines:
                    line = all_lines[-1]
                else:
                    line = None
                seen_lines[uses] = idx + 1
                results.append({"uses": uses, "step": step, "line": line})
        return results

    def run_blocks(self) -> list[dict[str, Any]]:
        """Every `run:` step with its source line and resolved env."""
        results: list[dict[str, Any]] = []
        all_run_lines = self.lines_of(re.compile(r"^\s+run:\s*[|>]?\s*"))
        run_idx = 0
        for job_hash in self.jobs().values():
            for step in self.steps(job_hash):
                run = step.get("run") if isinstance(step, dict) else None
                if not run:
                    continue
                if run_idx < len(all_run_lines):
                    line = all_run_lines[run_idx]
                elif all_run_lines:
                    line = all_run_lines[-1]
                else:
                    line = None
                run_idx += 1
                results.append({"run": run, "step": step, "env": step.get("env") or {}, "line": line})
        return results

    def run_content_lines(self) -> set[int]:
        """1-based line numbers that lie inside a `run:` step's shell content.

        Covers the inline form (`run: cmd` — that one line) and the
        block-scalar form (`run: |` / `run: >` — every following line
        indented deeper than the `run:` key, blank lines included). The
        shell-injection rules confine their `${{ }}` / `${VAR}` detection
        to this set so an expression in a job `outputs:` / step `with:`
        block is never mistaken for a run-block injection. Computed from raw
        lines (not the YAML tree) so the reported line numbers stay exact.
        """
        if self._run_content_cache is not None:
            return self._run_content_cache

        result: set[int] = set()
        lines = self.raw_lines
        n = len(lines)
        i = 0
        while i < n:
            m = _RUN_KEY_RE.match(lines[i])
            if not m:
                i += 1
                continue
            run_col = len(m.group(1))
            rest = m.group(2).strip()
            if rest and not _BLOCK_SCALAR_RE.match(rest):
                # Inline `run: cmd` — the command lives on this line.
                result.add(i + 1)
                i += 1
                continue
            # Block scalar (`run: |`/`>`) or bare `run:` — the content is the
            # following run of lines indented deeper than the `run:` key.
            j = i + 1
            while j < n:
                cl = lines[j]
                if cl.strip() == "":
                    result.add(j + 1)
                    j += 1
                    continue
                cind = len(_LEAD_WS_RE.match(cl).group(0))  # type: ignore[union-attr]
                if cind > run_col:
                    result.add(j + 1)
                    j += 1
                else:
                    break
            i = j

        self._run_content_cache = result
        return result
