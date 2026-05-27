# Contributing to ai-maestro-maintainer-agent

Thank you for your interest in this plugin. The maintainer agent's
own repository follows the same governance the agent applies to every
entrusted repo it guards — so contributing here is also a working
example of the contract the agent enforces elsewhere.

## Two contribution paths

**Bug reports** — welcome from anyone. File an issue using the bug
template. Include: `gh --version`, `claude --version`, the
`MAINTAINER_POLL_INTERVAL_MS` value if you set one, and a minimal
reproduction (a redacted patrol log is ideal). The maintainer agent
itself triages bug reports from any author; the same applies to human
review.

**Feature requests / change proposals** — accepted only from
`@Emasoft` (the repository owner). This mirrors the agent's R19.6
constraint that feature requests come only from the authorized GitHub
user. If you would like a feature, please open a Discussion or file an
issue using the feature-request template and tag `@Emasoft`. The
owner may choose to author or sponsor the work, or to mark it as
`wontfix`.

This isn't unfriendly — it is the same rule the agent applies on every
repo it maintains. The rule keeps the scope of the project focused
and the supply-chain attack surface (malicious feature requests that
trick a maintainer into shipping CI changes) closed.

## Local setup

```bash
# 1. Clone and enter the repo
git clone https://github.com/Emasoft/ai-maestro-maintainer-agent
cd ai-maestro-maintainer-agent

# 2. Create the Python environment (uv is mandatory; the project ships
#    uv.lock for reproducibility)
uv venv --python 3.12
source .venv/bin/activate

# 3. Install dependencies + the project itself
uv sync

# 4. Run the test suite (421 tests; Docker-dependent tests auto-skip if
#    no Docker daemon is reachable)
uv run --with pytest --with pytest-reportlog --with pyyaml pytest tests/ -v

# 5. Run linters before committing
uv run ruff check scripts/ tests/
uv run --with mypy mypy scripts/
```

The CI workflow runs the same five gates: `ruff` → `mypy` → `pytest`
→ `cpv-remote-validate plugin . --strict` → `zizmor`. Local-vs-CI
parity is enforced; if your change passes locally it will pass in CI.

## Branch convention

| Branch prefix | Meaning |
|---|---|
| `fix/<issue-number>-<slug>` | Bug fix tied to a specific issue |
| `feat/<short-slug>` | New feature (author = `@Emasoft` only) |
| `docs/<slug>` | Documentation-only change |
| `chore/<slug>` | Tooling / CI / hygiene |
| `refactor/<slug>` | Behaviour-preserving restructure |
| `test/<slug>` | New tests / test fixes |

Never push to `main` directly. Open a PR; the agent or the owner will
review.

## Commit messages

Conventional Commits format is required (parseable by `git-cliff`):

```
type(scope): subject line (≤ 70 chars)

A blank line, then the WHY in 2-4 paragraphs.

Optional: which Audit finding, which TRDD, which issue.
```

`type` ∈ `{feat, fix, docs, chore, refactor, test, perf, style, ci,
build, revert}`. `scope` is the area touched (e.g. `sentinel`,
`sandbox`, `guardian`, `triage`, `cicd`, `docs`).

The body MUST include the *why* of the change — what problem it solves
and what alternative was considered. Reviewers (and the agent on a
future patrol) need this to understand the change six months later.
A subject line alone is not enough.

## TRDDs for non-trivial work

If your PR introduces a new skill, a new threat class, a new public
API, or refactors a core path (>200 lines across >3 files), author a
TRDD first:

```
design/tasks/TRDD-<YYYYMMDD_HHMMSS+ZHHMM>-<uid-first-8>-<short-slug>.md
```

See `~/.claude/rules/trdd-design-tasks.md` for the frontmatter shape
and the rationale. The TRDD lives in the same PR as the
implementation. The PR template asks for the TRDD ID.

## ADRs for design decisions

If your PR commits to a non-obvious technical choice (e.g. "use
sqlite3, not LMDB"; "switch to Polars from pandas"; "drop Python 3.10
support"), author an ADR:

```
design/adrs/ADR-NNNN-<short-slug>.md
```

ADRs follow the Michael Nygard format: Context / Decision / Status /
Consequences. The PR template asks for the ADR number when relevant.

## Approval-gate-protected paths

The agent itself refuses to edit any of these without an
`approve-protected-edit` reply from `@Emasoft` on the originating
issue. Human contributors are expected to follow the same convention
— if your PR touches any of these, call out the *why* in the PR
description explicitly:

- `.github/workflows/**` (any CI change)
- `scripts/publish.py`
- `scripts/sentinel/**` (Sentinel scanner)
- `scripts/sandbox/sandbox.py` (Docker harness)
- `.gitignore`
- `.npmrc`
- `LICENSE`
- `.claude-plugin/**`
- `agents/**/*.md` (the main agent itself)
- Any lockfile (`uv.lock`, `package-lock.json`, etc.)

The canonical list lives in
`skills/maintainer-approval-gate/references/protected-paths.md`. If
you need to add a path to that list as part of your PR, justify it in
the PR description.

## Path redaction in PR / commit / issue text

When you copy logs / paths into a PR description, issue comment, or
commit message, redact host-specific paths:

```
/Users/<anyone>/<rest>        →  $HOME/<rest>
/home/<anyone>/<rest>         →  $HOME/<rest>
/Volumes/<anyone>/<rest>      →  $HOME/<rest>   (macOS)
C:\\Users\\<anyone>\\<rest>   →  %USERPROFILE%\\<rest>
<absolute path to this repo>  →  $PROJECT_DIR/<rest>
```

The agent enforces this via the `maintainer-redact` skill on the
content it authors. Human contributors are expected to do the same.

## Pre-push checks

The repo ships a `pre-push` git hook that re-runs the publish
pipeline's gates. Don't skip it with `--no-verify`. If a hook fails,
read the message and fix the underlying issue — bypassing hooks is
the exact pattern the Guardian's adversarial-content detector flags
as suspicious.

## What we will and won't accept

We *will* review PRs that:

- Fix bugs documented in an open issue.
- Extend the Sentinel rule catalogue with NEW detection patterns
  (each rule needs a fixture in `tests/fixtures/`).
- Improve cross-platform compatibility (Windows / macOS / Linux).
- Add tests for under-covered paths (the sandbox CLI dispatch layer
  is currently the biggest gap — see Audit B's report under
  `reports/audit/`).
- Improve documentation (READMEs, skill references, ADRs).
- Update vendored upstreams (zizmor / actionlint pin bumps via
  Dependabot are auto-merged).

We *will not* merge PRs that:

- Add new skills, new threat classes, or new public API surface
  without a prior TRDD authored by `@Emasoft`.
- Bypass the publish pipeline (no manual tag pushes; always
  `uv run python scripts/publish.py`).
- Skip the test suite (`--no-verify` on commits; `if: never()` in
  CI; etc.).
- Add a new `pull_request_target` workflow without an explicit
  threat-model paragraph in the PR description.

## License

By contributing, you agree your work is licensed under MIT (same as
the rest of the repo).

## Code of Conduct

This project follows the [Contributor Covenant
v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).
See `CODE_OF_CONDUCT.md` for the full text.

## Reporting security issues

Do NOT open public issues for security vulnerabilities. See
`SECURITY.md` for the private disclosure channel.

## Questions?

Open a GitHub Discussion or comment on an existing issue. The
maintainer agent patrols this repo every 5 minutes by default — your
question will be triaged automatically.
