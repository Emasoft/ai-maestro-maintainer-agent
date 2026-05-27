# Security Policy

The ai-maestro-maintainer-agent plugin's value proposition is
supply-chain hardening — so we hold ourselves to the same standard
the agent applies to every entrusted repo it guards.

## Reporting a vulnerability

**Do NOT file a public GitHub issue for a vulnerability.**

Use one of these private channels instead:

1. **Preferred — GitHub Security Advisories.** Visit
   <https://github.com/Emasoft/ai-maestro-maintainer-agent/security/advisories/new>
   and submit a private advisory. Anyone with a GitHub account can do
   this; the report is visible only to repository maintainers.
2. **Alternative — email.** Send to
   `713559+Emasoft@users.noreply.github.com` with subject
   `[security] <short description>`. Maintainer email is the
   GitHub-routed noreply address; messages reach Emasoft directly.

Please include:

- The plugin version (output of `cat .claude-plugin/plugin.json | jq .version`).
- The Claude Code version (`claude --version`).
- The OS + arch + `gh` version (`gh --version`).
- A redacted reproduction case (drop any `/Users/<name>` segments
  before submitting per the redaction convention in
  `CONTRIBUTING.md`).
- The expected vs observed behaviour.
- Your assessment of severity (CRITICAL / MAJOR / MINOR / NIT) — your
  reasoning, not your verdict; we will reach our own conclusion but
  your reasoning saves us time.

## What we will do

| Step | Target turnaround |
|---|---|
| Acknowledge receipt | within 72 hours |
| Reproduce and triage | within 7 days |
| Develop a fix | within 30 days for CRITICAL/MAJOR; best-effort for MINOR/NIT |
| Coordinated disclosure | within 90 days of initial report (CRITICAL/MAJOR); we will work with you on the schedule |
| Credit you in the release notes | always, unless you ask not to be named |

We do not offer a bug bounty. We do offer credit, a public
acknowledgment in the release notes, and a GitHub Security Advisory
CVE if the issue warrants one.

## Scope

**In scope** (please report):

- Any vulnerability that lets an attacker bypass
  `maintainer-approval-gate` (the canonical protected-paths gate) and
  cause the agent to commit / push a malicious change.
- Any vulnerability that lets an attacker escape the
  `scripts/sandbox/sandbox.py` Docker harness onto the host (mount
  escape, capability re-grant, host-network leak when `--network none`
  was requested, secret leakage from the agent's process to the
  container's userland).
- Any vulnerability in `scripts/sentinel/*` (the supply-chain scanner)
  that produces a **false negative** on a documented threat class —
  i.e. malicious content the scanner SHOULD flag but does not.
- Hardcoded secrets in the repo (we run secret-scan gates locally and
  in CI; finding one would be an oversight we want to know about).
- Prompt-injection paths in the agent's skills that let an issue
  body / PR title / comment trick the agent into editing a protected
  path.
- Any path that lets the agent write outside its declared
  `$AGENT_DIR/.aimaestro/state/` + `$MAIN_ROOT/reports/` + `/tmp/`
  boundary onto the host.

**Out of scope** (we welcome you to file as a feature request
instead):

- Vulnerabilities in repos the agent is *maintaining* (those are the
  responsibility of those repos' own maintainers; the agent is a
  tool, not a service).
- Issues in third-party dependencies — please report those upstream
  (zizmor, actionlint, git-cliff, uv, ruff, mypy). We will fast-track
  a pin bump once a fix lands upstream.
- Issues in Claude Code itself — report to Anthropic.
- Issues in the user's own `.aimaestro/state/` files (those are
  per-host, never shipped).
- Theoretical issues without a working exploit path. We are happy to
  discuss those, but they go through the regular issue / discussion
  channels, not the security one.

## What counts as a vulnerability vs. a bug

A vulnerability has two properties:

1. **Adversarial impact** — an attacker can cause an effect a benign
   user cannot achieve, OR a non-privileged user can cause an effect
   reserved for a privileged user.
2. **Reachable** — there is a concrete code path from an
   externally-controllable input to the impact.

If both hold, file via the security channel. If only one holds (e.g.
"this could fail safely in a way I don't like" — no adversarial
impact), file as a regular bug.

## Disclosure policy

- We follow a **90-day coordinated-disclosure window** for
  CRITICAL/MAJOR.
- If we cannot ship a fix within 90 days, we will publish the
  advisory anyway with mitigations and recommend users disable the
  affected skill until a fix lands.
- If you find a fix before us, please send the patch via the security
  channel — we will integrate, credit, and release.
- If the vulnerability is being actively exploited in the wild, the
  90-day window collapses to 7 days and we will release a mitigation
  immediately even if the full fix is not ready.

## Supported versions

| Plugin version | Supported | Notes |
|---|---|---|
| `1.2.x` | ✓ active | current minor |
| `1.1.x` | ✓ security fixes only | previous minor |
| `1.0.x` | ✗ unsupported | upgrade to 1.2 |
| `< 1.0` | ✗ pre-release | upgrade to 1.2 |

`uv` resolution + `pyproject.toml` `[dependency-groups]` means
upgrading is `uv sync --upgrade-package ai-maestro-maintainer-agent`.

## Known design constraints (not vulnerabilities)

- The agent runs with the host's `gh` CLI authentication. If the host
  is compromised, the agent's reach is the same as the host's `gh`
  token's reach. Operate the agent on hosts you trust.
- The agent stores per-agent state under
  `$AGENT_DIR/.aimaestro/state/`. If an attacker has filesystem
  access to that directory, they can edit the issue ledger and the
  Guardian baseline. This is the same as having filesystem access to
  any other state dir; harden the host accordingly.
- `scripts/sandbox/sandbox.py` is a **defense in depth** layer. It is
  not a security boundary on its own — the underlying Docker daemon
  is. If your Docker daemon is compromised, the sandbox cannot help.

If you find behavior that *could* be considered a security boundary
but is documented above as not one, please still file via the
security channel — we may have under-promised in the docs.

## Credits

We thank every researcher who has reported responsibly. Names are
listed in `ACKNOWLEDGMENTS.md` and in the relevant release notes.

## Last reviewed

2026-05-27 (TRDD-e1c2677a audit pass).
