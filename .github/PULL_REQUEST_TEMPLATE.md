<!--
Thank you for your contribution to ai-maestro-maintainer-agent.

Before submitting, please confirm the items below. The maintainer agent
runs the same checks as CI; if all boxes are ticked locally, CI will
pass.
-->

## Summary

<!-- 1-2 sentences. What does this PR change and why? -->

## Type of change

- [ ] Bug fix (closes #<issue-number>)
- [ ] New feature (author = `Emasoft` only per R19.6)
- [ ] Documentation only
- [ ] Refactor / cleanup / chore
- [ ] Test addition / fix
- [ ] CI / tooling change

## Linked work

- Closes / fixes: #<issue-number>
- TRDD (if non-trivial): `design/tasks/TRDD-<...>.md`
- ADR (if design decision): `design/adrs/ADR-<NNNN>-<slug>.md`
- Audit finding (if reactive): `reports/audit/<date>-audit-<X>-<...>.md` finding `<id>`

## What changed

<!--
List the files / surfaces touched, grouped by component. Include the WHY
behind any non-obvious choice. A reviewer (or the agent on a future
patrol) needs to be able to reconstruct the rationale six months from
now.
-->

## How to verify

<!--
Concrete steps a reviewer can run locally to verify the change works.
For UI / runtime changes, paste a redacted log. For new tests, name the
test file. For docs, point at the doc.
-->

## Protected paths touched

<!-- Tick all that apply. If ANY are ticked, the PR description must justify why. -->

- [ ] None
- [ ] `.github/workflows/**` (CI)
- [ ] `scripts/publish.py`
- [ ] `scripts/sentinel/**` (Sentinel scanner)
- [ ] `scripts/sandbox/sandbox.py` (Docker harness)
- [ ] `.gitignore`
- [ ] `.npmrc`
- [ ] `LICENSE`
- [ ] `.claude-plugin/**`
- [ ] `agents/**/*.md`
- [ ] A lockfile (`uv.lock`, `package-lock.json`, etc.)
- [ ] `skills/maintainer-approval-gate/references/protected-paths.md`

## Checklist (verified locally)

- [ ] `uv run ruff check scripts/ tests/` is clean
- [ ] `uv run --with mypy mypy scripts/` is clean
- [ ] `uv run --with pytest --with pyyaml pytest tests/ -q` passes
- [ ] If `.github/workflows/` was touched: `uvx zizmor --gh-token "$(gh auth token)" .github/workflows/` is clean
- [ ] If `.github/workflows/` was touched: `actionlint .github/workflows/*.yml` is clean
- [ ] Conventional Commits subject line(s) — `git log -1 --format=%s` parses cleanly via git-cliff
- [ ] Commit body contains the **WHY** in 2-4 paragraphs (not just WHAT — that's already in the diff)
- [ ] Path-redaction applied to any logs / paths quoted in the description or commit body (no `/Users/<name>` segments — see CONTRIBUTING.md)
- [ ] No secrets committed (no tokens, PATs, .env files)
- [ ] If a new skill: SKILL.md passes Nixtla-strict frontmatter (description literal-block, "Use when" + "Trigger with", 6 body sections)
- [ ] If a new test: not a mock of the unit under test
- [ ] Changes are bisectable (one logical change per commit)

## Out-of-scope items I noticed but did not address

<!-- 
List anything you ran into but deferred. The agent will use this to file
follow-up issues automatically.
-->

## For reviewer

<!-- Anything specific you want the reviewer to look at first. -->
