# Acknowledgments

`ai-maestro-maintainer-agent` builds on the work of many people. This
file collects the names and projects we depend on, with gratitude.

## Authors

- **Emasoft** ([@Emasoft](https://github.com/Emasoft)) — author and
  current maintainer.

## Upstream projects we depend on

### Security scanning

- **[zizmor](https://github.com/zizmorcore/zizmor)** by William Woodruff
  and contributors — GitHub Actions static analyzer. The
  `maintainer-guardian` T1 detector and the `workflow-scan` skill both
  invoke `uvx zizmor` directly. zizmor catches workflow security
  classes the bundled Sentinel port intentionally leaves to it
  (untrusted-action-input, expression-injection patterns, etc.).
- **[actionlint](https://github.com/rhysd/actionlint)** by Linda_pp
  (rhysd) — workflow YAML linter. Used by `workflow-scan` as the
  third engine alongside zizmor and the Sentinel port.
- **[jpr5/sentinel](https://github.com/jpr5/sentinel)** by Jason
  Wescott — the original Ruby gem this plugin's `scripts/sentinel/`
  module is a Python port of. The 32-rule catalogue and the rule
  shape are derived from the upstream gem; the test fixtures are
  written fresh.
- **[git-cliff](https://git-cliff.org)** by orhun and contributors —
  generates `CHANGELOG.md` from Conventional Commits. Configured in
  `cliff.toml`.

### Build / packaging / quality

- **[uv](https://github.com/astral-sh/uv)** by Astral — Python package
  manager. Mandatory for `uv run`, `uv sync`, `uvx`. The publish
  pipeline assumes `uv` on PATH.
- **[ruff](https://github.com/astral-sh/ruff)** by Astral — Python
  linter + formatter. Local-vs-CI parity gate.
- **[mypy](https://github.com/python/mypy)** by Jukka Lehtosalo, Guido
  van Rossum, and contributors — static type checker.
- **[pytest](https://docs.pytest.org)** by Holger Krekel and
  contributors — test runner.
- **[pyyaml](https://pyyaml.org)** by Kirill Simonov — YAML parsing
  used by the Sentinel port.
- **[google-re2](https://github.com/google/re2)** — fast regex engine
  used by `scripts/fast_security_scan.py` for secret-pattern matching
  at scale.

### Infrastructure

- **[Docker](https://www.docker.com)** / **[OrbStack](https://orbstack.dev)**
  / **[Colima](https://github.com/abiosoft/colima)** — container
  runtimes the `maintainer-sandbox` skill drives. The harness itself
  is daemon-agnostic; any OCI-compatible runtime works.
- **[GitHub CLI (gh)](https://cli.github.com)** — authentication and
  REST/GraphQL access. The agent assumes a host-authenticated `gh`.

### Documentation / authoring

- **[Contributor Covenant](https://www.contributor-covenant.org)** v2.1
  by Coraline Ada Ehmke — adopted verbatim as `CODE_OF_CONDUCT.md`.
- **[Michael Nygard's ADR format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions)**
  — `design/adrs/` follows this template.

## Inspirations and references

- **Atai Barkai's 2026-05-20 supply-chain article** ("Supply chain
  attacks are at an all-time high") catalogued the eight attack
  vectors that drove the Guardian's T1–T6 design. The
  `art-template@4.13.{3,4,5,6}` incident mentioned in
  `skills/maintainer-guardian/SKILL.md` examples comes from this
  article.
- **[Anthropic's Claude Code SDK + agent docs](https://docs.anthropic.com/en/docs/claude-code)**
  — the agent / skill / hook structure follows the published
  conventions (Nixtla-strict frontmatter, `model: inherit`, etc.).

## Security disclosure credits

This list will grow as researchers report and we publish coordinated
disclosure advisories. None yet.

## Community

This is an early-stage plugin and the community is small. If you
would like to be acknowledged here for a non-code contribution
(documentation review, bug repro, design feedback, sandbox testing on
unusual platforms), please open a PR adding your name. We will
verify the contribution and merge.

## License

All contributions are accepted under MIT (see `LICENSE`). The
upstreams above retain their own licenses; this acknowledgment file
does not redistribute their code, only documents the dependency
relationship.
