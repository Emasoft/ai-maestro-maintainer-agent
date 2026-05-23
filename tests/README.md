# ai-maestro-maintainer-agent — test suite

Pytest-based test suite for the v1.1.0 skill set. Every test exercises
the REAL code path documented in the skill's `SKILL.md` / `references/`
markdown — no mocks. External-binary dependencies (`git`, `gh`, `jq`,
`uvx`) are skipped via `@pytest.mark.skipif` when they're absent.

## Running locally

```bash
# Run via the canonical pipeline runner (table output + pass/fail count):
python3 tests/run-all-tests.py

# Or invoke pytest directly:
uv run --with pytest --with pyyaml -- pytest tests/ -v
```

`tests/run-all-tests.py` is what CPV's `publish.py` G4 gate invokes.
It exits 0 on all-pass, 1 on any failure.

## Coverage

| Skill / module | Tests | File |
|---|---|---|
| state-path resolution helper | 5 | `test_state_path.py` |
| maintainer-guardian (T1-T5 detectors + atomic write) | 6 | `test_guardian.py` |
| maintainer-approval-gate (protected-paths + VERIFY) | 9 | `test_approval_gate.py` |
| workflow-bootstrap (lang detection + templates) | 7 | `test_bootstrap.py` |
| jq --arg trap detector (workflow-fix-safe) | 4 | `test_jq_trap.py` |
| Cross-skill integration tests | 4 | `test_integration.py` |

35 tests total covering the v1.1.0 skill changes. Each test has a
one-line docstring used by the runner table (per CLAUDE.md).

## Test conventions

- **No mocks.** Every test uses real subprocess (git, gh) against real
  tmp filesystems.
- **One assertion focus per test.** A test that breaks tells you
  precisely which contract is violated.
- **Real binaries.** `git`, `gh`, `jq`, `uvx` must be on PATH.
  Tests that need them gracefully skip if not.
- **Slow tests** (if any) are suffixed with the snail emoji 🐌 per
  CLAUDE.md.

## Layout

```
tests/
├── conftest.py             # shared fixtures (tmp_git_repo, clean_env)
├── skill_helpers.py        # pure-Python re-implementations of skill snippets
├── pytest.ini              # pytest config (testpaths, addopts)
├── run-all-tests.py        # G4 gate runner — table + exit code
├── README.md               # this file
├── test_state_path.py      # AGENT_DIR resolution cascade
├── test_guardian.py        # T1-T5 + atomic-write
├── test_approval_gate.py   # protected-paths + VERIFY
├── test_bootstrap.py       # language detection + templates
├── test_jq_trap.py         # jq --arg trap regex
├── test_integration.py     # cross-skill / real-gh / real-git
└── fixtures/               # static test fixtures (empty for now)
```

`skill_helpers.py` is the testable code path — pure Python
re-implementations of the bash/python snippets the skill markdown
files specify. Each function carries a docstring pointing at the
SKILL.md section that defines its semantics.
