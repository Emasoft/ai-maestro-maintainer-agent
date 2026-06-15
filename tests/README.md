# ai-maestro-maintainer-agent — test suite

Pytest-based test suite for the whole maintainer plugin (skills, agent,
sentinel scanner, sandbox harness, governance docs). Every test exercises
the REAL code path documented in the skill's `SKILL.md` / `references/`
markdown — no mocks. External-binary dependencies (`git`, `gh`, `jq`,
`uvx`, `docker`) are skipped via `@pytest.mark.skipif` when they're absent.

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
| maintainer-approval-gate (protected-paths + VERIFY) | 13 | `test_approval_gate.py` |
| workflow-bootstrap (lang detection + templates) | 7 | `test_bootstrap.py` |
| jq --arg trap detector (workflow-fix-safe) | 4 | `test_jq_trap.py` |
| maintainer-redact (host-path / secret redaction) | 17 | `test_redact.py` |
| maintainer-secrets-scan (fast_security_scan.py) | 7 | `test_fast_security_scan.py` |
| maintainer-commit-msg-why hook | 11 | `test_commit_msg_hook.py` |
| maintainer-sandbox (Docker harness invariants) | 28 | `test_sandbox.py` |
| **14-skill doc contract suite** (patrol, triage, fix, pr-triage, pr-review, workflow-scan/fix-safe/pin-actions/protect-branch, detect-stack, tooling-bootstrap, config-lint, generate-docs, trdd-adr) | 62 | `test_skill_contracts.py` |
| Sentinel scanner — core + 32 rules + 6 fixers | 336 | `test_sentinel_core.py`, `test_sentinel_autofix.py`, `test_sentinel_rules_a..f.py` |
| Cross-skill / real-gh / real-git integration | 4 | `test_integration.py` |
| Real-repo sandbox e2e | 4 | `test_real_repos.py` |

**533 tests total.** Each test has a one-line docstring used by the runner
table (per CLAUDE.md). Every skill, command, hook, and script ships at least
one real test (PRRD S5); the 14-skill doc-contract suite closed the last
coverage gap (fleet-readiness audit #10 M12), holding the whole skill set to
frontmatter validity, the no-tool-grant invariant (ADR-0002 / PRRD S7),
required body sections, and local-reference integrity.

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
├── test_redact.py          # host-path / secret redaction
├── test_fast_security_scan.py  # secret-scan catalog
├── test_commit_msg_hook.py # commit-message WHY hook
├── test_sandbox.py         # Docker harness invariants
├── test_skill_contracts.py # the 14-skill doc-contract suite
├── test_sentinel_core.py   # scanner core
├── test_sentinel_autofix.py    # the 6 fixers
├── test_sentinel_rules_a..f.py # the 32 detection rules
├── test_integration.py     # cross-skill / real-gh / real-git
├── test_real_repos.py      # real-repo sandbox e2e
└── fixtures/               # static test fixtures
```

`skill_helpers.py` is the testable code path — pure Python
re-implementations of the bash/python snippets the skill markdown
files specify. Each function carries a docstring pointing at the
SKILL.md section that defines its semantics.
