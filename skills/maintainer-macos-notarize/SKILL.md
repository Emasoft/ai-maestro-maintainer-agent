---
description: |
  Audit or bootstrap Apple code-signing and notarization in a repo that
  ships macOS binaries (.app, .dmg, .pkg, CLI). Two modes: AUDIT finds
  the dangerous patterns — a cert imported into the login keychain, a
  missing cleanup step, app-specific-password auth, unstapled artifacts,
  secrets echoed to logs. BOOTSTRAP writes a release job using an
  ephemeral keychain and App Store Connect API-key auth.
  Trigger with "notarize the mac build", "set up code signing",
  "why does Gatekeeper block my app", "audit macOS signing".
---

# maintainer-macos-notarize — Apple code-signing and notarization, done safely

## Overview

An unsigned or un-notarized macOS binary is blocked by Gatekeeper with *"cannot
be opened because the developer cannot be verified"*. Fixing that means three
distinct steps that are routinely confused:

| Step | What it proves | Done by |
|---|---|---|
| **Sign** | this binary came from an identified developer, unmodified | `codesign` (needs a Developer ID cert) |
| **Notarize** | Apple scanned it and found no known malware | `xcrun notarytool submit` (needs App Store Connect credentials) |
| **Staple** | the notarization ticket travels WITH the file | `xcrun stapler staple` |

Skipping **staple** is the classic bug: the app passes on the build machine
(which fetches the ticket online) and fails for a user who is offline or behind a
firewall. Nothing in CI catches it.

Doing this in CI means putting a **signing identity** on a shared runner. That is
the part worth being careful about, and it is where the audit half of this skill
spends its time.

## Prerequisites

- An Apple Developer account with a **Developer ID Application** certificate
  (exported as `.p12`), and an **App Store Connect API key** (`.p8`).
- A macOS runner (`macos-latest`) — `codesign`, `notarytool`, and `stapler` are
  Xcode tools and do not exist on Linux.
- Six repo secrets. The audit reports which are missing:

  | Secret | What it is |
  |---|---|
  | `MACOS_CERT_P12` | the Developer ID cert, base64-encoded |
  | `MACOS_CERT_PASSWORD` | its export password |
  | `APPLE_API_KEY_P8` | the App Store Connect `.p8` key, base64-encoded |
  | `APPLE_API_KEY_ID` | the key's ID |
  | `APPLE_API_ISSUER_ID` | the issuer UUID |
  | `APPLE_TEAM_ID` | the 10-character team ID |

## Instructions

### 1. Detect

Confirm the repo actually ships a macOS artifact before doing any of this — a
signing job on a repo with no `.app`/`.dmg`/`.pkg` is dead weight:

```bash
MAIN_ROOT="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
grep -rlE "\.(app|dmg|pkg)\b|electron-builder|tauri|codesign|notarytool" \
  --include='*.yml' --include='*.yaml' --include='*.json' --include='*.toml' . | head
```

### 2. AUDIT — the seven findings

Run the audit against the repo's workflows. Each finding below is a real failure
mode, not a style note; see [instructions](references/instructions.md) for the
detection recipe and the fix for each.

| # | Finding | Why it matters |
|---|---|---|
| 1 | Cert imported into the **login keychain** (`security import` with no `-k <path>`, or `default-keychain` touched) | the identity persists on the runner after the job. On a self-hosted runner, the next job — including one from a fork PR — can sign with it. |
| 2 | **No cleanup step**, or one without `if: always()` | a failed job leaves the keychain, the `.p12`, and the `.p8` on disk. `if: always()` is what makes cleanup run on the failure path, which is the only path that matters. |
| 3 | **App-specific-password** auth (`--apple-id` + `--password`) | a long-lived credential tied to a human's Apple ID, with no scoping and no rotation story. The API key (`--key`/`--key-id`/`--issuer`) is scoped and revocable. |
| 4 | **No `stapler staple`** | ships an artifact that only validates online. Works in CI, fails for an offline user. |
| 5 | Secret **echoed or written unquoted** (`echo "$CERT"`, `set -x` in a signing step) | GitHub masks known secret values in logs, but not a base64 fragment or a derived value. |
| 6 | **No `timeout-minutes`** on the signing job | notarization can hang. The job default is 6 hours — a hung notarize burns 360 runner-minutes at the macOS multiplier. |
| 7 | Repo-wide **`permissions: contents: write`** | the signing job needs no write scope at all until it uploads. Scope per-job. |

### 3. BOOTSTRAP — write the job

Copy `references/templates/macos-notarize.yml` into `.github/workflows/`, adapt
the build command, and set the six secrets. The template's load-bearing parts:

- an **ephemeral keychain** created in `$RUNNER_TEMP`, never the login keychain;
- `security set-key-partition-list`, without which `codesign` blocks on a GUI
  prompt that no runner can answer — the single most common "it hangs forever";
- **App Store Connect API-key** auth;
- `notarytool submit --wait` then **`stapler staple`**;
- a cleanup step with **`if: always()`**;
- `timeout-minutes`, per-job `permissions`, and a `concurrency` group.

### 4. VERIFY

The only check that matters is the one that simulates a user's Mac:

```bash
spctl --assess --type execute --verbose=4 "path/to/YourApp.app"   # -> "accepted"
stapler validate "path/to/YourApp.app"                            # -> "worked"
codesign --verify --deep --strict --verbose=2 "path/to/YourApp.app"
```

`spctl` says whether **Gatekeeper** would let it run. `stapler validate` is the
one that catches the offline-user bug, because it checks the ticket is *attached*
rather than merely *issued*.

### 5. Report

```bash
MAIN_ROOT="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
DIR="$MAIN_ROOT/reports/maintainer-macos-notarize"
mkdir -p "$DIR"
REPORT="$DIR/$(date +%Y%m%d_%H%M%S%z)-notarize-audit.md"
```

## Done when (terminating conditions)

- [ ] **AUDIT** — every one of the seven findings is reported as PRESENT, ABSENT,
  or N/A, with a `file:line`. A clean repo yields "0 findings"; a repo that ships
  no macOS artifact yields "N/A — no macOS artifact" and stops there.
- [ ] **BOOTSTRAP** — the workflow exists, `actionlint` passes on it, and the six
  secrets are listed as set-or-missing. **Do NOT claim the pipeline works until a
  real tag has run it**: signing cannot be verified without the actual
  certificate, and saying otherwise is a claim you have not checked.
- [ ] **VERIFY** — `spctl --assess` prints `accepted` AND `stapler validate`
  prints `worked`. Both. `spctl` alone passes on a machine that can reach Apple,
  which is exactly the case that hides the missing-staple bug.

## Boundaries

- Does **not** create, download, or rotate certificates or API keys. Those are
  owner-identity credentials — the skill reports which are missing and stops.
- Does **not** commit a `.p12`, a `.p8`, or any base64 of one. They go in repo
  secrets; a cert in git history is a rotation event.
- Does **not** sign anything locally. Signing happens on the runner, from repo
  secrets, so the identity is never on a developer's machine.
- Does **not** apply to iOS/App Store submission (a different pipeline:
  provisioning profiles, `altool`, TestFlight).

## Resources

- [Full step-by-step instructions](references/instructions.md):
  - Step 1: Detect a macOS artifact
  - Step 2: Audit the seven findings
  - Step 3: Bootstrap the signing job
  - Step 4: Verify like a user's Mac
  - Step 5: Troubleshooting
  - Report
- `references/templates/macos-notarize.yml` — the workflow template.
- `tests/test_macos_notarize.py` — asserts the template carries the ephemeral
  keychain, API-key auth, the staple step, and `if: always()` cleanup, and that
  the audit detector catches each of the seven findings.
