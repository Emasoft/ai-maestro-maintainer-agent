# ADR-0004 — Python port of jpr5/sentinel rather than Ruby-gem runtime dep

Status: accepted
Date: 2026-05-27
Authors: Emasoft

## Context

The Guardian's T1 threat class (workflow drift) wants a fast,
deterministic scanner that catches structural classes zizmor and
actionlint miss — things like:

- `build-publish-same-job` (same job builds and publishes, no
  credential window)
- `credential-window` (credentials provisioned beyond their use)
- `ide-config-injection` (IDE config files committed alongside CI)
- `missing-frozen-lockfile` (CI install without `--frozen-lockfile`)
- `dangerous-lifecycle-scripts` (`preinstall`, `postinstall` etc.
  in untrusted packages)
- `jq-arg-escape-sequences` (jq command-substitution traps)

[jpr5/sentinel](https://github.com/jpr5/sentinel) is a mature Ruby
gem that catches these. We had three options:

1. **Runtime-depend on the Ruby gem.** Install via `gem install
   sentinel`, invoke via subprocess from the agent.
2. **Bundle the Ruby gem.** Vendor the gem source under
   `scripts/sentinel-rb/` and invoke through a `bundle exec`
   wrapper.
3. **Port the gem to Python.** Re-implement the 32 rules and the
   YAML / workflow inspection helpers in Python, ship under
   `scripts/sentinel/`.

Option 1 was the path of least implementation effort but had three
problems:

- Every Claude Code user would need Ruby installed. Many do not
  (it is not part of Claude Code's runtime requirements and is not
  in `pyproject.toml`).
- The Ruby gem's release cadence is not under our control. An
  upstream regression would silently propagate into our Guardian
  pipeline.
- Cross-language dependency complicates `publish.py` —
  `publish.py` is pure Python.

Option 2 fixed the "needs Ruby" problem only partially (still
needed) and worsened the cadence problem (vendoring snapshots a
specific version forever unless we manually re-vendor).

Option 3 (Python port) had high upfront cost (32 rules to port,
faithful behaviour parity required) but eliminated both upstream
problems. It also fit cleanly into the existing Python toolchain:

- `pyproject.toml`-managed deps via `uv`.
- `pytest`-runnable rule tests.
- `ruff` + `mypy` enforce code quality at the same standard as the
  rest of the agent's Python.
- The CLI surface (`scripts/sentinel_scan.py`) is callable from any
  skill via the existing Bash tool pattern.

## Decision

We port jpr5/sentinel to Python. The port lives under
`scripts/sentinel/` and ships:

- `scanner.py` — top-level entry; loads rules + workflows; emits
  findings.
- `workflow.py` — YAML workflow parsing, block-scalar handling,
  job-line resolution. Robust against quoted `uses:` lines and
  `outputs:`/`with:`/`env:` shadowing.
- `local_client.py` — pre-commit config fetching, etc.
- `rules/*.py` — 32 detection rules, one file per rule, each
  inheriting from `rules/base.py`.
- `formatters/*.py` — Terminal, JSON, SARIF.
- `autofix.py` — 6 mechanical fixers (line-numbered bottom-up
  application; YAML re-validation; bail to original on parse
  failure).
- `sha_resolver.py` — `gh api`-backed tag → 40-char-commit-SHA
  resolution.

The port maintains **faithful behavioural parity** with the Ruby
gem for the 32 rules: same severity levels, same finding shape,
same false-positive calibration. Validated against 8 real public
repos with zero false positives (`fix(sentinel): calibrate rules
to zero false positives on 8 real repos`, commit `418a518`).

## Consequences

**Easier:**

- Single-language stack — Python end to end. `pyproject.toml` +
  `uv.lock` are reproducible across machines.
- Rule maintenance is a Python file; reviewers + contributors who
  know Python (most of the audience) can extend the catalogue.
- The CLI is fast (~60 ms cold run on 3 workflow files; the Ruby
  gem takes ~400 ms for the same scan plus Ruby startup).
- Findings can be parsed by any Python script without shelling
  out (we return JSON, but in-process consumption is trivial).
- The agent's failure mode on a buggy rule is well-bounded:
  `rule_engine.py:35` catches per-rule exceptions and skips the
  bad rule with an stderr message, mirroring the Ruby gem's
  `rescue => e` behavior.

**More difficult:**

- We carry the maintenance burden of the port. When jpr5/sentinel
  ships a new rule, we must port it (or decide not to).
  Mitigated by the slow upstream cadence + the fact that we
  intentionally diverge in calibration (we'd port a NEW
  detection class but not blindly accept a calibration change).
- Initial port effort: ~3 person-weeks (32 rules × ~30 min each +
  test fixtures + calibration loop on 8 real repos). Cost is
  amortised across every Guardian invocation.

**Neutral:**

- The port lives in `scripts/sentinel/` and is independently
  consumable by any user who wants the scanner without the rest of
  the plugin. They install the plugin and `uv run --with pyyaml
  scripts/sentinel_scan.py scan ...`. We do NOT publish to PyPI
  separately; if there is demand we will spin out a sister package.
- Test coverage of the port is comprehensive: 335+ tests across
  `tests/test_sentinel_*.py` (8 files). Same as the Ruby gem's
  Mountain of fixtures.

## References

- Upstream: <https://github.com/jpr5/sentinel>
- TRDD: `design/tasks/TRDD-20260525_093556+0200-e5816c13-sentinel-python-port.md`
- Source: `scripts/sentinel/` (8 files + `rules/` subdir of 32)
- Tests: `tests/test_sentinel_*.py` (8 files)
- Calibration commit: `418a518 fix(sentinel): calibrate rules to
  zero false positives on 8 real repos`
- Acknowledgment to the upstream maintainer is recorded in
  `ACKNOWLEDGMENTS.md`.
