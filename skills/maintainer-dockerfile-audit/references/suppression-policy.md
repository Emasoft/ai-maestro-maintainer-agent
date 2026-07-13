# Suppression policy — fix, or suppress with a reason

A red CI gate creates pressure to make the red go away. There are two ways
to do that, and only one of them is honest.

> A suppression is a claim that the check **does not apply**.
> It is never a claim that the finding is inconvenient.

Suppressing a check you have not understood converts a security finding
into a lie that outlives you — the next reader sees a green build and
assumes the policy is enforced.

## Table of Contents

- [The decision procedure](#the-decision-procedure)
- [Forbidden, always](#forbidden-always)
- [How to document a suppression](#how-to-document-a-suppression)
- [Worked example — this repo](#worked-example--this-repo)
- [Prove the suppression actually works](#prove-the-suppression-actually-works)
- [Review a suppression when the image changes](#review-a-suppression-when-the-image-changes)

## The decision procedure

Ask these in order. The first NO means **fix it**.

1. **Does the check target a property this image kind can even have?**
   A run-once tool container that executes one command and exits has no
   health to report. A shipped service does. If the property exists, the
   check applies — fix it.
2. **Would satisfying the check make the image worse?**
   A fake `HEALTHCHECK` on an ephemeral container is *more* misleading than
   none. If the honest fix is a lie, the check is inapplicable.
3. **Can you write the reason in one sentence a stranger would accept?**
   If the sentence is "it is annoying", "CI is red", or "we will do it
   later", that is not a rationale. Fix it.
4. **Does the suppression name exactly ONE check?**
   If you are reaching for a whole-scanner disable, a severity downgrade,
   or a file exclusion, stop. That is not suppression; that is blindness.

Everything that survives all four is a legitimate, documented suppression.
Everything else is a fix.

## Forbidden, always

- Disabling a scanner outright (`ENABLE_LINTERS` removal, `--skip-check` on
  a whole family).
- Lowering a severity threshold so the finding drops below the gate.
- Adding the file to a lint-exclude regex to dodge the check.
- Suppressing a finding you have not read.
- Suppressing one check in a way that quietly takes its neighbours down —
  silencing HEALTHCHECK must NOT also silence non-root or pinned-base.
- "Fixing" a finding by deleting the instruction that triggered it.

Weakening the gate is never the remediation. If the gate is genuinely
wrong, fix the gate deliberately and say so — do not route around it.

## How to document a suppression

The rationale goes where the next reader will actually look: **in the
config that performs the suppression.** Not in a commit message, not in a
TRDD, not in a code comment three files away.

A good rationale answers three things:

1. WHAT is suppressed (the check ID).
2. WHY it cannot apply (the property this image kind lacks).
3. WHAT stays enforced (so nobody assumes the whole class was dropped).

## Worked example — this repo

`scripts/sandbox/dockerfiles/*.Dockerfile` failed CI on Checkov and Trivy.
Three policies fired. Two were real defects; one was inapplicable.

| Finding | Verdict | Action |
|---|---|---|
| `CKV_DOCKER_7` / `DS-0001` — unpinned base tag | REAL | Fixed: pinned `FROM mitmproxy/mitmproxy:12.2.3` |
| `CKV_DOCKER_3` / `DS-0002` — no non-root user | REAL | Fixed: declared `USER mitmproxy` |
| `CKV_DOCKER_2` / `DS-0026` — no HEALTHCHECK | INAPPLICABLE | Suppressed, with rationale |

The HEALTHCHECK suppression passes all four tests: these are run-once tool
containers and a throwaway proxy sidecar. They execute one command and
exit. There is no running service to health-check, so a `HEALTHCHECK` would
be decoration — and the other two policies stayed ENFORCED.

Both scanners flag the same property, so BOTH ends must be handled.
Suppressing one and forgetting the other leaves CI red and invites a
second, sloppier suppression.

Checkov, in `.mega-linter.yml`:

```yaml
# Checkov — skip workflow-level permission checks (we set permissions per-job).
# Also skip CKV_DOCKER_2 (HEALTHCHECK): every Dockerfile in this repo is an
# ephemeral maintainer-sandbox container — run-once tool containers that execute
# one command and exit, plus an optional throwaway mitmproxy sidecar. None are
# long-running shipped services, so a container HEALTHCHECK is inapplicable. The
# non-root-USER (CKV_DOCKER_3) and pinned-base-tag (CKV_DOCKER_7) policies stay
# ENFORCED. (Trivy's mirror of this LOW finding, AVD-DS-0026, is scoped the same
# way in .trivyignore.)
REPOSITORY_CHECKOV_ARGUMENTS: "--skip-check CKV2_GHA_1,CKV_DOCKER_2"
```

Trivy, in `.trivyignore` at the repo root (Trivy reads it automatically):

```gitignore
# AVD-DS-0026 (HEALTHCHECK) — every Dockerfile in this repo is an ephemeral
# maintainer-sandbox container: run-once tool containers that execute one
# command and exit, plus an optional throwaway mitmproxy sidecar. None are
# long-running shipped services, so a container HEALTHCHECK is inapplicable.
# This mirrors the Checkov CKV_DOCKER_2 skip documented in .mega-linter.yml.
#
# The non-root-USER (AVD-DS-0002) and pinned-base-tag (AVD-DS-0001) policies are
# NOT ignored — they remain enforced.
AVD-DS-0026
```

Note what each comment does: names the check, explains the property the
image kind lacks, states what remains enforced, and points at its mirror in
the other scanner. A reader who has never seen this repo can audit the
decision without asking anyone.

## Prove the suppression actually works

An ignore entry that silently fails to match is worse than no entry — you
believe you are covered and you are not. Always run a control.

```bash
# Control: no ignore file → the finding MUST appear
docker run --rm -v "$PWD/scripts/sandbox/dockerfiles:/src:ro" \
  aquasec/trivy:latest config -q --skip-version-check --exit-code 1 /src

# With the repo's ignore file → 0 misconfigurations, exit 0
docker run --rm -v "$PWD:/repo:ro" -v "$PWD/scripts/sandbox/dockerfiles:/src:ro" \
  aquasec/trivy:latest config -q --skip-version-check \
  --ignorefile /repo/.trivyignore --exit-code 1 /src
```

If the second run still reports the finding, the ID did not match. Two
traps that cause exactly this:

- **Trivy ID spelling.** Current Trivy prints the SHORT `DS-0026`, while
  this repo's `.trivyignore` says `AVD-DS-0026`. Both work — the legacy
  `AVD-` prefix is still honoured as an alias (verified on Trivy 0.72.0:
  0 misconfigurations, exit 0). Do not "fix" the working `AVD-` entry.
- **Wrong scanner, wrong file.** Trivy suppressions do NOT go in
  `.mega-linter.yml`, and Checkov suppressions do NOT go in `.trivyignore`.

## Review a suppression when the image changes

A suppression is scoped to an image KIND, not to a filename. The moment an
ephemeral tool container becomes a long-running service, the HEALTHCHECK
suppression becomes a lie. Re-run the decision procedure whenever a
Dockerfile's purpose changes — that is precisely when a stale suppression
does its damage.
