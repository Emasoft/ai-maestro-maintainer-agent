# Action currency — dead runtimes, hard sunsets, and stale-major findings

This skill pins an action to the 40-char SHA **at its current ref** and
preserves the existing major (`@v4` stays `@v4`). It does NOT bump majors.
So a pinned-but-stale major is still stale — this file is how to DETECT
and FLAG that as a finding, plus the runtime deprecations that make a
stale major an outright failure rather than a warning.

## Table of Contents

- [Pin vs flag: what this skill does and does not do](#pin-vs-flag-what-this-skill-does-and-does-not-do)
- [Node.js runtime EOL timeline](#nodejs-runtime-eol-timeline)
- [Hard sunsets (permanent failures, not warnings)](#hard-sunsets-permanent-failures-not-warnings)
- [Current major versions (dated snapshot — re-verify)](#current-major-versions-dated-snapshot--re-verify)
- [Detecting a stale major](#detecting-a-stale-major)
- [Third-party actions: review the bundled dist, not just src](#third-party-actions-review-the-bundled-dist-not-just-src)

## Pin vs flag: what this skill does and does not do

- **Does:** resolve `foo/bar@v4` to `foo/bar@<sha>  # v4.3.1`. The
  supply-chain posture improves (immutable ref) but the *version* is
  unchanged.
- **Does NOT:** move `@v4` to `@v6`. A major bump can carry breaking
  changes and needs human review — surface it as a currency FINDING, not
  an auto-fix.

So after a pin run, a workflow can be zizmor-clean on `unpinned-uses` yet
still be running a dead-runtime action. The currency check below is a
separate, read-only pass that produces findings.

## Node.js runtime EOL timeline

A JavaScript action declares its runtime in `runs.using:` (`node12`,
`node16`, `node20`, `node24`). GitHub warns at runtime when an action
uses an end-of-life Node runtime, and eventually forces the minimum up.

| Runtime | End of life | Consequence |
|---|---|---|
| `node12` | April 2022 | deprecated; GitHub warns, migration overdue |
| `node16` | September 2023 | deprecated; GitHub warns |
| `node20` | April 2026 | current baseline for most actions |
| `node22` / `node24` | current | newest actions target these |

An action's runtime is decided by its major version — this is exactly why
a stale major matters: `actions/checkout@v2` runs on `node12`,
`@v3` on `node16`, `@v4`/`@v5` on `node20`, `@v6` on `node20`+/`node24`.
Flag any `uses:` whose resolved major maps to `node12`/`node16`.

## Hard sunsets (permanent failures, not warnings)

These are not "please upgrade" warnings — the old version STOPS working:

| Action | Sunset | Minimum that works |
|---|---|---|
| `actions/upload-artifact` | v3 upload service shut down | v4 |
| `actions/download-artifact` | v3 download service shut down | v4 |
| `actions/cache` | legacy cache service sunset **Feb 1 2025** | v4.2.0+ (v5 on `node24`) |

A workflow still on `actions/upload-artifact@v3` does not warn — it
FAILS. Treat a hard-sunset action as a high-severity currency finding,
distinct from a merely-stale major.

## Current major versions (dated snapshot — re-verify)

A snapshot for the staleness comparison below; action releases move, so
re-verify against each action's releases page before asserting "outdated".

| Action | Current major | Minimum supported |
|---|---|---|
| `actions/checkout` | v6 | v4 |
| `actions/setup-node` | v6 | v4 |
| `actions/setup-python` | v5 | v4 |
| `actions/setup-go` | v5 | v4 |
| `actions/setup-java` | v4 | v4 |
| `actions/cache` | v4 / v5 | v4.2.0 |
| `actions/upload-artifact` / `download-artifact` | v4 | v4 |
| `docker/build-push-action` | v6 | v5 |
| `aws-actions/configure-aws-credentials` | v4 | v4 |

## Detecting a stale major

A read-only currency pass, run alongside (not instead of) SHA-pinning:

1. Extract every `uses: owner/action@ref` and its resolved major.
2. Compare the major to the current-major snapshot.
3. Classify:
   - **DEPRECATED** — below minimum supported, or a hard-sunset version,
     or a `node12`/`node16` runtime. High severity: it fails or is about
     to. This is a finding for human review (a major bump), never an
     auto-fix by this skill.
   - **OUTDATED** — behind current major but at/above minimum. Low
     severity: informational, upgrade when convenient.
   - **UP-TO-DATE** — at current major.
4. Offline / rate-limited: if the current-major lookup is unavailable,
   mark unknown actions as unverified rather than asserting "latest" — do
   not claim currency you did not confirm.

The SHA-pinning this skill performs and the major-bump a DEPRECATED
finding requires are two different edits with two different risk levels;
keep them separate.

## Third-party actions: review the bundled dist, not just src

For a JavaScript action, the file that actually runs is the **bundled**
`dist/` entry named in `runs.main:` (e.g. `dist/index.js`), NOT the
`src/` TypeScript. Action authors commit the compiled bundle and do not
gitignore it, so a supply-chain review of a third-party action must read
the bundle that ships at the pinned SHA — reviewing `src/` alone can miss
a bundle that does not match its source. SHA-pinning is what makes such a
review meaningful: it freezes the exact `dist/` you reviewed, so a later
retag cannot swap the bundle underneath you. This is the deeper reason the
pin targets a commit SHA and not a moving tag.
