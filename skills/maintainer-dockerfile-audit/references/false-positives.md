# Known false positives and scanner artefacts

Not every red line is a defect. Some are the scanner's parser losing its
footing. Rewriting a correct Dockerfile to appease a broken parser is a
real regression traded for a cosmetic win — so verify before you "fix".

Every entry below was reproduced against this repo's own Dockerfiles.

## Table of Contents

- [Heredoc breaks BOTH hadolint and Checkov parsers](#heredoc-breaks-both-hadolint-and-checkov-parsers)
- [hadolint DL3013 misfires on an ARG-interpolated version pin](#hadolint-dl3013-misfires-on-an-arg-interpolated-version-pin)
- [hadolint DL3006 misfires on a fully-qualified registry image](#hadolint-dl3006-misfires-on-a-fully-qualified-registry-image)
- [Trivy check-ID prefix changed — and the old one still works](#trivy-check-id-prefix-changed--and-the-old-one-still-works)
- [trivy config has no --no-progress flag](#trivy-config-has-no---no-progress-flag)
- [The general rule](#the-general-rule)

## Heredoc breaks BOTH hadolint and Checkov parsers

**Symptom — hadolint refuses to parse the file at all:**

```text
/dev/stdin:36:1 unexpected 'R' expecting a new line followed by the next instruction
```

**Symptom — Checkov invents instructions that do not exist:**

```text
WARNING: An unsupported instruction SET was used in /node-safe-chain.Dockerfile
WARNING: An unsupported instruction IF was used in /node-safe-chain.Dockerfile
WARNING: An unsupported instruction CP was used in /node-safe-chain.Dockerfile
WARNING: An unsupported instruction FI was used in /node-safe-chain.Dockerfile
WARNING: An unsupported instruction EXEC was used in /node-safe-chain.Dockerfile
WARNING: An unsupported instruction EOF was used in /node-safe-chain.Dockerfile
```

**Cause.** BuildKit supports heredocs in `RUN`:

```dockerfile
RUN cat >/usr/local/bin/entrypoint <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [ -f /tmp/seed ]; then
  cp /tmp/seed /work/app.conf
fi
exec "$@"
EOF
```

Neither scanner models heredoc bodies. Checkov reads the shell lines
(`set`, `if`, `cp`, `fi`, `exec`, `EOF`) as if each were a Dockerfile
instruction; hadolint gives up at the first one. `node-safe-chain.Dockerfile`
in this repo triggers both.

**Verdict.** The Dockerfile is CORRECT — Docker builds it. This is a
scanner limitation.

**What to do.**

- Do NOT restructure a working Dockerfile to satisfy the parser.
- Do NOT suppress a real policy check because it was drowned in this noise.
- Note the artefact in the audit report so the next reader is not alarmed.
- Read the heredoc body yourself: the scanners did not audit it, so YOU are
  the only reviewer that shell got. Check it for secrets and unsafe fetches.
- Checkov still evaluates the file's real instructions — the `CKV_DOCKER_*`
  results for it remain valid. Only the `unsupported instruction` warnings
  are noise. hadolint, by contrast, produces NO findings for the file at
  all; treat it as unscanned by hadolint, not as clean.

That last distinction is the dangerous one. A file that hadolint could not
parse looks exactly like a file with zero findings.

## hadolint DL3013 misfires on an ARG-interpolated version pin

**Symptom:**

```text
-:16 DL3013 warning: Pin versions in pip. Instead of `pip install <package>`
use `pip install <package>==<version>`
```

**The line it flagged, in `python-baseline.Dockerfile`:**

```dockerfile
ARG UV_VERSION=0.4.27
RUN pip install --no-cache-dir --timeout 120 --retries 5 "uv==${UV_VERSION}"
```

**Cause.** The version IS pinned — through a build argument. hadolint does
not resolve `ARG` interpolation, so it sees `uv==${UV_VERSION}` and cannot
confirm a literal version.

**Verdict.** FALSE POSITIVE. The pin is real and, being an `ARG`, is also
overridable at build time — strictly better than a hard-coded literal.

**What to do.** Leave it. If the noise is unacceptable, `hadolint --ignore
DL3013` scoped to that file — never a blanket ignore. Do NOT inline the
literal version just to silence the linter; that throws away the `ARG`
indirection to satisfy a parser limitation.

The same blindness affects `DL3016`/`DL3008` when the version arrives via
`ARG`. Verify whether a pin exists before believing the finding.

## hadolint DL3006 misfires on a fully-qualified registry image

**Symptom.** DL3006 — *"Always tag the version of an image explicitly"* —
fires on a base image that IS explicitly tagged, when the image comes from a
non-Docker-Hub registry:

```dockerfile
FROM gcr.io/distroless/static-debian12
```

**Cause.** `static-debian12` IS the version tag, but hadolint's DL3006
heuristic does not reliably recognise the tag on a fully-qualified registry
reference (`gcr.io/...`, `public.ecr.aws/...`). It reads the whole path as an
untagged image.

**Verdict.** FALSE POSITIVE when the image is genuinely tagged. Confirm the
reference carries a real tag before believing it — if it truly is untagged,
DL3006 is correct and you must add a tag.

**What to do.** Suppress it in-place with an inline directive scoped to that
one line — never a blanket ignore:

```dockerfile
# hadolint ignore=DL3006
FROM gcr.io/distroless/static-debian12
```

The `# hadolint ignore=<RULE[,RULE]>` comment is hadolint's file-local
suppression mechanism (distinct from the `--ignore` CLI flag and a
`.hadolint.yaml` config). Like every suppression, it must name ONE rule and
carry a one-line reason — the same discipline as
[suppression-policy](suppression-policy.md).

## Trivy check-ID prefix changed — and the old one still works

**Symptom.** Trivy reports `DS-0026`, but the repo's `.trivyignore` says
`AVD-DS-0026`. It looks like a stale entry that no longer matches.

**Verified on Trivy 0.72.0:** the legacy `AVD-` prefix is still honoured
as an ALIAS.

- With `.trivyignore` containing `AVD-DS-0026` → 0 misconfigurations,
  exit 0.
- Without it → `DS-0026 (LOW): Add HEALTHCHECK instruction` fires.

**Verdict.** Both spellings suppress. The `AVD-` entry is NOT stale.

**What to do.** Nothing. Do not "modernise" a working ignore file — you
gain nothing and risk a typo that silently disables the suppression. If you
touch it anyway, run the control from
[suppression-policy](suppression-policy.md) and prove it still matches.

## `trivy config` has no `--no-progress` flag

**Symptom:**

```text
FATAL Fatal error unknown flag: --no-progress
```

**Cause.** `--no-progress` is real on other Trivy subcommands, so it is an
easy assumption. It does not exist on `trivy config`.

**Verdict.** Not a Dockerfile finding at all — a broken scan command.

**Why it is dangerous.** Trivy exits FATAL and scans NOTHING. A script that
only checks for the string "MISCONFIGURATION" in the output reads that as
clean and reports a green audit over a scan that never ran.

**What to do.** Use `-q`. And gate on `--exit-code 1` — `trivy config`
exits 0 by default even when findings exist, so a Trivy CI step without it
is decorative.

## The general rule

A finding is a hypothesis, not a verdict. Before changing a Dockerfile,
confirm the tool actually understood it:

- Did the scanner PARSE the file, or bail out? Zero findings and "could not
  parse" look identical in a summary count.
- Is the property the scanner wants already satisfied by indirection
  (an `ARG`, the base image's default user, a narrow build context)?
- Did the scan command itself succeed? Check the exit code, not just the
  absence of the word FAIL.

The audit's credibility rests on not crying wolf. Every false positive you
pass along teaches the next reader to skim the report.
