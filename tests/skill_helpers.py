"""
Pure Python re-implementations of the skill snippets — exactly the
algorithms the SKILL.md / references/*.md files describe in their bash/
python helpers, lifted into importable Python so tests can call them
directly.

The skills themselves are markdown instructions to the agent; this
module IS the testable code path. Each function references the
SKILL doc that specifies it.

NO MOCKS — everything operates on real filesystem paths / real
subprocess output / real strings provided by the caller.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path, PurePath


# ---------------------------------------------------------------------------
# State-path resolution helper
# Implements the cascade documented in
# skills/maintainer-guardian/references/threat-classes.md (Atomic write
# pattern section):
#     AGENT_DIR="${AIMAESTRO_AGENT_DIR:-${CLAUDE_PROJECT_DIR:-$PWD}}"
# ---------------------------------------------------------------------------
def resolve_agent_dir(env: dict | None = None, cwd: Path | str | None = None) -> Path:
    """Return the agent working directory per the cascade rule.

    Priority order, exactly as documented in threat-classes.md:
      1. $AIMAESTRO_AGENT_DIR (AI Maestro preferred env var)
      2. $CLAUDE_PROJECT_DIR  (Claude Code project dir)
      3. The caller's cwd (last-resort fallback; defaults to os.getcwd()).
    """
    # Use a fresh local (not the annotated `env` param) so the type checker
    # infers the dict|os._Environ union freely; both expose .get().
    resolved = env if env is not None else os.environ
    aimaestro = resolved.get("AIMAESTRO_AGENT_DIR")
    if aimaestro:
        return Path(aimaestro)
    claude = resolved.get("CLAUDE_PROJECT_DIR")
    if claude:
        return Path(claude)
    if cwd is None:
        cwd = os.getcwd()
    return Path(cwd)


def state_dir(env: dict | None = None, cwd: Path | str | None = None) -> Path:
    """Return `<agent_dir>/.aimaestro/state` per the SKILL doc."""
    return resolve_agent_dir(env=env, cwd=cwd) / ".aimaestro" / "state"


# ---------------------------------------------------------------------------
# T5 — Secret-leak regex sweep
# Patterns documented in threat-classes.md > T5 section.
# ---------------------------------------------------------------------------
SECRET_PATTERNS = {
    "aws_access_key": re.compile(r"AKIA[0-9A-Z]{16}"),
    "github_pat": re.compile(r"ghp_[0-9a-zA-Z]{36}"),
    "gitlab_pat": re.compile(r"glpat-[0-9a-zA-Z\-_]{20}"),
    "slack_token": re.compile(r"xox[baprs]-"),
    "google_oauth": re.compile(r"ya29\.[0-9A-Za-z\-_]+"),
    "openai_anthropic_key": re.compile(r"sk-[a-zA-Z0-9]{32,}"),
}


def scan_for_secrets(text: str) -> list[tuple[str, str]]:
    """Return a list of (kind, matched_value) for every secret-looking token.

    Matches every pattern in SECRET_PATTERNS; multiple matches per kind are
    returned individually. Empty input → empty list.
    """
    hits: list[tuple[str, str]] = []
    for kind, pat in SECRET_PATTERNS.items():
        for m in pat.finditer(text):
            hits.append((kind, m.group(0)))
    return hits


# ---------------------------------------------------------------------------
# Protected-paths matcher
# Implements the CHECK semantics in
# skills/maintainer-approval-gate/references/protected-paths.md.
# ---------------------------------------------------------------------------
def parse_protected_globs(text: str) -> list[str]:
    """Parse the protected-paths text format: one glob per line, # comments."""
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Reject anything that looks like markdown code-fence / heading.
        if line.startswith("`") or line.startswith("```"):
            continue
        out.append(line)
    return out


# Canonical protected paths — extracted from the markdown table inside
# protected-paths.md so the tests can exercise the exact glob set.
CANONICAL_PROTECTED_GLOBS = [
    ".github/workflows/**",
    ".github/actions/**",
    ".github/dependabot.yml",
    ".github/CODEOWNERS",
    "scripts/publish.py",
    "scripts/setup_marketplace_pat.py",
    ".gitignore",
    ".gitattributes",
    ".npmrc",
    ".pnpmrc",
    ".nvmrc",
    ".python-version",
    ".tool-versions",
    "LICENSE",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    ".claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",
    "agents/**/*.md",
    "hooks/**",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
]


def matches_protected(path: str, globs: list[str]) -> list[str]:
    """Return every glob in `globs` that matches `path`.

    Uses pathlib.PurePath.match semantics, exactly per the SKILL doc:
        Glob matching uses pathlib.PurePath.match semantics: `**` is
        recursive, `*` is non-recursive within one component.

    pathlib.PurePath.match only handles `**` correctly when invoked via
    PurePath.full_match (Python 3.13+) or by manual prefix-stripping for
    `**`-suffixed globs. To stay portable across 3.10-3.13 we expand
    `**` ourselves: `prefix/**` matches any path whose first components
    are `prefix/`.
    """
    p = PurePath(path)
    hits: list[str] = []
    for g in globs:
        if "**" in g:
            # Normalize "prefix/**" and "prefix/**/suffix" forms.
            parts = g.split("/**")
            # Case A: simple "prefix/**" — match any path under prefix.
            if len(parts) == 2 and parts[1] in ("", "/", "/*"):
                prefix = parts[0]
                if prefix and (path == prefix or path.startswith(prefix + "/")):
                    hits.append(g)
                    continue
            # Case B: "prefix/**/suffix" e.g. "agents/**/*.md"
            if len(parts) == 2:
                prefix, suffix = parts[0], parts[1].lstrip("/")
                # Strip trailing dir-segment glob (e.g. "*.md")
                if prefix and path.startswith(prefix + "/"):
                    rest = path[len(prefix) + 1 :]
                    # suffix like "*.md" — match the final path component
                    if "/" in suffix:
                        # not supported; skip
                        pass
                    else:
                        final = rest.split("/")[-1]
                        if PurePath(final).match(suffix):
                            hits.append(g)
                            continue
        else:
            if p.match(g):
                hits.append(g)
    return hits


def planned_diff_hits(planned_paths: list[str], globs: list[str]) -> list[str]:
    """Return the planned paths that match any protected glob."""
    out: list[str] = []
    for p in planned_paths:
        if matches_protected(p, globs):
            out.append(p)
    return out


# ---------------------------------------------------------------------------
# Planned-diff fingerprint (D2 — replay-proof approval binding)
# protected-paths.md > "Diff-fingerprint binding":
#     git diff HEAD -- | git hash-object --stdin | cut -c1-12
# git hash-object computes SHA-1 of `blob <len>\0<content>`; we reproduce that
# exact formula so the Python model and the documented bash agree byte-for-byte.
# ---------------------------------------------------------------------------
def diff_fingerprint(diff_text: str) -> str:
    """12-char git-blob fingerprint of a planned diff (matches git hash-object)."""
    data = diff_text.encode()
    blob = b"blob " + str(len(data)).encode() + b"\0" + data
    return hashlib.sha1(blob).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Approval-comment grammar matcher
# protected-paths.md > "Approval-comment grammar" + the VERIFY snippet.
# ---------------------------------------------------------------------------
APPROVE_RE = re.compile(r"\bapprove-protected-edit\b")
REJECT_RE = re.compile(r"\breject-protected-edit\b")


def classify_approval(comments: list[dict], authorized_user: str, fingerprint: str) -> str:
    """Return 'ok' / 'pending' / 'rejected' from a list of issue comments.

    Each comment is a dict with keys:
        author: { login: str }
        body:   str

    Matches the exact algorithm in protected-paths.md's VERIFY section (D2):
      * a comment from authorized_user with `reject-protected-edit` → rejected
        (wins over any approval; needs no fingerprint).
      * else an `approve-protected-edit` from authorized_user that ALSO carries
        the current `fingerprint` → ok.
      * else pending. This is fail-closed and covers a missing approval, an
        impostor approval, AND a stale/bare approval that lacks the current
        fingerprint (the diff was re-scoped since it was approved).
    """
    rejected = False
    approved = False
    for c in comments:
        login = (c.get("author") or {}).get("login")
        body = c.get("body", "")
        if login != authorized_user:
            continue
        if REJECT_RE.search(body):
            rejected = True
        # The approval must carry the CURRENT fingerprint (literal substring),
        # not merely the phrase — this is the replay-proof binding. An empty
        # fingerprint can never match, so the gate stays closed (fail-closed).
        if APPROVE_RE.search(body) and fingerprint and fingerprint in body:
            approved = True
    if rejected:
        return "rejected"
    if approved:
        return "ok"
    return "pending"


# ---------------------------------------------------------------------------
# workflow-bootstrap — language detection
# Implements the table in skills/workflow-bootstrap/references/instructions.md.
# Order matters: `package.json && !pyproject.toml` is checked AFTER python/rust/go.
# ---------------------------------------------------------------------------
def detect_language(repo: Path) -> str:
    """Return the language tag per the bootstrap table."""
    lang = "generic"
    if (repo / "pyproject.toml").exists():
        lang = "python"
    if (repo / "Cargo.toml").exists():
        lang = "rust"
    if (repo / "go.mod").exists():
        lang = "go"
    if (repo / "package.json").exists() and not (repo / "pyproject.toml").exists():
        lang = "node"
    return lang


def has_existing_workflows(repo: Path) -> bool:
    """True iff `.github/workflows/` contains any *.yml/*.yaml file."""
    wf = repo / ".github" / "workflows"
    if not wf.is_dir():
        return False
    for p in wf.iterdir():
        if p.suffix in (".yml", ".yaml") and p.is_file():
            return True
    return False


# ---------------------------------------------------------------------------
# jq --arg trap detector
# Implements the regex in
# skills/workflow-fix-safe/references/instructions.md > Step 4 > jq audit:
#     jq[^|]*"[^"]*\$\{[A-Z_][A-Z0-9_]*\}
# ---------------------------------------------------------------------------
JQ_TRAP_RE = re.compile(r"jq[^|]*\"[^\"]*\$\{[A-Z_][A-Z0-9_]*\}")


def detect_jq_arg_trap(yaml_text: str) -> list[tuple[int, str]]:
    """Return (line_number, line_text) tuples for every jq --arg trap line.

    A line is a trap iff it contains `jq` followed by a double-quoted
    string that interpolates a bash variable `${VAR}`. This is the
    documented vulnerable shape from the article's `--arg` walkthrough.

    Note: jq invocations that use the correct `--arg name "$VAR"` form
    are NOT flagged — those interpolate at the SHELL level (outside the
    jq filter string), so the regex finds no `${VAR}` inside the
    `jq ... "..."` filter quotes.
    """
    hits: list[tuple[int, str]] = []
    for idx, line in enumerate(yaml_text.splitlines(), start=1):
        if JQ_TRAP_RE.search(line):
            hits.append((idx, line))
    return hits


# ---------------------------------------------------------------------------
# Atomic-write helper (the pattern in threat-classes.md)
# ---------------------------------------------------------------------------
def atomic_write_json(target: Path, content: str) -> None:
    """Write `content` to `target` atomically: tmp file in same dir, then mv.

    Mirrors the bash snippet `mv -f "$TMP" "$STATE_DIR/guardian-baseline.json"`
    on a POSIX filesystem: os.replace is atomic when src+dst are on the same fs.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(content)
    os.replace(tmp, target)


# ---------------------------------------------------------------------------
# Git helper — last-touched commit for a path (T4 detector)
# ---------------------------------------------------------------------------
def last_commit_sha_for(repo: Path, path: str) -> str | None:
    """Return the SHA of the most recent commit touching `path`, or None.

    `path` may be missing or untracked → returns None.
    """
    r = subprocess.run(
        ["git", "log", "--format=%H", "-1", "--", path],
        cwd=repo,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if r.returncode != 0:
        return None
    out = r.stdout.strip()
    return out or None
