# maintainer-macos-notarize — runnable recipes

## Table of Contents

- [Step 1: Detect a macOS artifact](#step-1-detect-a-macos-artifact)
- [Step 2: Audit the seven findings](#step-2-audit-the-seven-findings)
- [Step 3: Bootstrap the signing job](#step-3-bootstrap-the-signing-job)
- [Step 4: Verify like a user's Mac](#step-4-verify-like-a-users-mac)
- [Step 5: Troubleshooting](#step-5-troubleshooting)
- [Report](#report)

---

## Step 1: Detect a macOS artifact

Do this first. A signing job on a repo that ships no macOS binary is dead weight,
and the honest audit result is `N/A`, not `0 findings`.

```bash
MAIN_ROOT="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
grep -rlE "\.(app|dmg|pkg)\b|electron-builder|tauri|codesign|notarytool|macos-latest" \
  --include='*.yml' --include='*.yaml' --include='*.json' --include='*.toml' . \
  | grep -v node_modules | head
```

Nothing? Stop. Report `N/A — repo ships no macOS artifact`.

## Step 2: Audit the seven findings

Run the detector over the repo's workflows. It is deliberately conservative: it
reports what it can prove from the YAML, and says `CHECK` where a human must look.

```bash
uv run - <<'PY'
import re, sys, pathlib

WF = sorted(pathlib.Path(".github/workflows").glob("*.y*ml"))
if not WF:
    print("N/A — no workflows"); sys.exit(0)

# Only audit jobs that actually sign; a Linux test job is not our business.
SIGNS = re.compile(r"codesign|notarytool|security\s+import|macos-latest|macos-\d", re.I)

FINDINGS = []
for f in WF:
    t = f.read_text(encoding="utf-8", errors="replace")
    if not SIGNS.search(t):
        continue
    L = t.splitlines()

    def at(rx):
        for i, line in enumerate(L, 1):
            if re.search(rx, line, re.I):
                return i
        return None

    imp = at(r"security\s+import")
    # 1. cert into the LOGIN keychain: `security import` with no -k target
    if imp and not re.search(r"security\s+import[^\n]*-k\s", t, re.I):
        FINDINGS.append((f, imp, 1, "cert imported without -k: it lands in the LOGIN keychain and outlives the job"))
    # 2. cleanup, and cleanup that runs on the FAILURE path
    if imp:
        if not re.search(r"delete-keychain", t, re.I):
            FINDINGS.append((f, imp, 2, "no `security delete-keychain` — the signing identity is left on the runner"))
        elif not re.search(r"if:\s*always\(\)", t, re.I):
            FINDINGS.append((f, at(r"delete-keychain"), 2, "cleanup exists but has no `if: always()` — it is skipped on the failure path, the one path that matters"))
    # 3. app-specific-password auth instead of an App Store Connect API key
    if re.search(r"notarytool[^\n]*--apple-id|--password\b", t, re.I):
        FINDINGS.append((f, at(r"--apple-id|--password\b"), 3, "app-specific-password auth — use --key/--key-id/--issuer (scoped, revocable)"))
    # 4. notarized but never stapled
    if re.search(r"notarytool\s+submit", t, re.I) and not re.search(r"stapler\s+staple", t, re.I):
        FINDINGS.append((f, at(r"notarytool\s+submit"), 4, "notarized but never stapled — the artifact only validates ONLINE and fails for an offline user"))
    # 5. a secret echoed, or set -x in a step that handles one
    if re.search(r"echo\s+\"?\$\{?\{?\s*secrets\.|set\s+-x", t, re.I):
        FINDINGS.append((f, at(r"echo\s+\"?\$\{?\{?\s*secrets\.|set\s+-x"), 5, "a secret may be echoed to the log (GitHub masks known values, not derived ones)"))
    # 6/7. job-level hygiene
    if not re.search(r"timeout-minutes:", t):
        FINDINGS.append((f, 1, 6, "no timeout-minutes — a hung notarize burns the 6h default at the macOS 10x runner multiplier"))
    if re.search(r"^permissions:\s*\n\s+contents:\s*write", t, re.M):
        FINDINGS.append((f, at(r"^permissions:"), 7, "repo-wide `contents: write` — scope it to the one job that uploads"))

if not FINDINGS:
    print("0 findings — signing workflow looks sound. Still run Step 4 against a real build.")
for f, line, n, msg in FINDINGS:
    print(f"[{n}] {f}:{line}  {msg}")
PY
```

Each finding maps to the fix in the template — see the table in `SKILL.md`.

## Step 3: Bootstrap the signing job

```bash
MAIN_ROOT="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
mkdir -p .github/workflows
cp "$MAIN_ROOT/skills/maintainer-macos-notarize/references/templates/macos-notarize.yml" \
   .github/workflows/release-macos.yml
```

Then, in order:

1. Replace the **Build** step with the repo's real build command.
2. Set `ARTIFACT` to the produced `.app`/`.dmg`/`.pkg` path.
3. Set the six secrets (`gh secret set NAME -b "$VALUE"` — pass the value with
   `-b`; piping it on stdin produces a silently broken secret).
4. `actionlint .github/workflows/release-macos.yml`.

Do **not** report the pipeline as working until a real tag has run it. Signing
cannot be verified without the actual certificate, and claiming otherwise is a
claim you have not checked.

## Step 4: Verify like a user's Mac

```bash
codesign --verify --deep --strict --verbose=2 "$ARTIFACT"   # signature intact
stapler validate "$ARTIFACT"                                # -> "worked"
spctl --assess --type execute --verbose=4 "$ARTIFACT"       # -> "accepted"
```

**Both of the last two, not just `spctl`.** `spctl` passes on any machine that
can reach Apple — which includes every CI runner — so it happily accepts an
artifact whose ticket was never stapled. `stapler validate` is the one that
catches the offline-user bug, because it asks whether the ticket is *attached*
rather than merely *issued*.

## Step 5: Troubleshooting

| Symptom | Cause |
|---|---|
| The sign step **hangs until the job times out** | `security set-key-partition-list` was not run. `codesign` is blocking on a GUI "allow access?" prompt that no runner can answer. |
| `The binary is not signed with a valid Developer ID certificate` | signed with a *Development* cert, not **Developer ID Application**. Only the latter notarizes. |
| `The executable does not have the hardened runtime enabled` | `codesign` was missing `--options runtime`. Notarization requires it and the message rarely says so. |
| Notarization **succeeds** but the app is still blocked on a user's Mac | the ticket was never **stapled**, or was stapled to the `.app` but you shipped a `.dmg` built *before* the staple. Staple the artifact you actually ship. |
| `Team ID is not valid` | `notarytool` is using the wrong issuer/key pair, or the cert belongs to a different team. |
| `errSecInternalComponent` during codesign | the keychain is locked. `security unlock-keychain` must run in the **same step** — each `run:` is a fresh shell. |
| Works locally, fails in CI | locally you are signing from the login keychain, which is already unlocked and partitioned. That is the exact state CI does not have. |

## Report

```bash
MAIN_ROOT="$(git worktree list --porcelain | sed -n '1s/^worktree //p')"
DIR="$MAIN_ROOT/reports/maintainer-macos-notarize"
mkdir -p "$DIR"
REPORT="$DIR/$(date +%Y%m%d_%H%M%S%z)-notarize-audit.md"
```
