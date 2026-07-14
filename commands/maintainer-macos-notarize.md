---
description: Audit or bootstrap Apple code-signing and notarization for a repo that ships macOS binaries. Finds the dangerous patterns (login-keychain cert, no cleanup, app-specific-password auth, missing staple) and writes a hardened release job.
argument-hint: "[audit|bootstrap|verify]"
---

Make a repo's macOS binaries pass Gatekeeper, without leaving a signing identity
on a shared runner.

Loads skill: **maintainer-macos-notarize**

Three steps, routinely confused: **sign** (this came from an identified
developer), **notarize** (Apple scanned it), **staple** (the ticket travels with
the file). Skipping the staple is the classic bug — the app passes on the build
machine, which can reach Apple, and fails for a user who is offline.

Three modes:

- `audit` (default) — scan the repo's workflows for seven findings: a cert
  imported into the **login keychain** (it outlives the job, and on a self-hosted
  runner the next job can sign with it); **no cleanup**, or cleanup without
  `if: always()` (so it is skipped on the failure path — the only path that
  matters); **app-specific-password** auth instead of a scoped App Store Connect
  API key; **no `stapler staple`**; a secret **echoed** to the log; **no
  `timeout-minutes`** (a hung notarize burns the 6h default at the macOS 10×
  runner multiplier); repo-wide **`contents: write`**.
- `bootstrap` — install `references/templates/macos-notarize.yml`: an ephemeral
  keychain in `$RUNNER_TEMP`, API-key auth, `notarytool submit --wait` +
  `stapler staple`, cleanup with `if: always()`, per-job permissions, a timeout,
  and a concurrency group.
- `verify` — `spctl --assess` **and** `stapler validate`. Both. `spctl` alone
  passes on any machine that can reach Apple, so it accepts an artifact whose
  ticket was never stapled — which is exactly the bug.

Never creates, downloads, or rotates a certificate or API key: those are
owner-identity credentials. It reports which of the six required secrets are
missing and stops.

Adapted from johannesjo/parallel-code, whose ephemeral-keychain + API-key pattern
is the right shape but which shipped no job timeout, no concurrency group, and a
repo-wide `contents: write`.
