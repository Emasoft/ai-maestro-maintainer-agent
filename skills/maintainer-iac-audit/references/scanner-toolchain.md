# IaC scanner toolchain — what to run, and what NOT to add

## Table of Contents

- [Tool status — what is alive, what is dead](#tool-status--what-is-alive-what-is-dead)
- [What this repo's CI already runs](#what-this-repos-ci-already-runs)
- [terraform fmt / validate without credentials](#terraform-fmt--validate-without-credentials)
- [tflint](#tflint)
- [Checkov](#checkov)
- [Trivy](#trivy)
- [Scanning the plan JSON instead of the HCL](#scanning-the-plan-json-instead-of-the-hcl)
- [Documented suppression — the only permitted escape hatch](#documented-suppression--the-only-permitted-escape-hatch)
- [Exit codes](#exit-codes)

## Tool status — what is alive, what is dead

The IaC scanner landscape churned hard; a stale recommendation is a
real risk here (an agent installing an unmaintained scanner and
trusting its silence).

| Tool | Status | What the maintainer does |
|---|---|---|
| **Checkov** (Bridgecrew/Prisma) | Alive, ~3000 policies, multi-framework | RUN — CI already runs it |
| **Trivy** (Aqua) | Alive; absorbed tfsec, scans IaC + containers + secrets | RUN — CI already runs it |
| **tfsec** | DEPRECATED — merged into Trivy, no longer maintained | Do NOT add. If a repo still calls `tfsec`, that is a finding: migrate the call to `trivy config` and carry the ignore comments over |
| **Terrascan** | ARCHIVED by Tenable (Nov 2025), unmaintained | Do NOT add. If present, treat as a finding: an unmaintained scanner ships no new policies, so its green result is meaningless. Replace with Checkov or Trivy |
| **tflint** | Alive; provider-aware lint (invalid instance types, deprecated syntax) | OPTIONAL — complements, never replaces, the security scanners |
| **terraform-docs** / **infracost** | Alive, out of scope | Suggest only if the owner asks |

**Rule:** two security scanners is the target, not five. Adding a
third overlapping scanner buys duplicate findings and a slower gate;
adding a *dead* one buys false confidence.

## What this repo's CI already runs

`.mega-linter.yml` enables `REPOSITORY_CHECKOV` and
`REPOSITORY_TRIVY`. Consequences the audit must respect:

- Any `.tf` merged into a repo on this pipeline is scanned in CI
  whether or not anyone asked. A local audit that skips Checkov or
  Trivy is not an audit — it is a preview of a CI failure.
- Checkov's repo-wide skips live in ONE place:
  `REPOSITORY_CHECKOV_ARGUMENTS: "--skip-check CKV2_GHA_1,CKV_DOCKER_2"`.
  A new repo-wide skip is appended THERE, with a comment above it
  saying why the check is inapplicable.
- Trivy's repo-wide ignores live in ONE place: `.trivyignore` at the
  repo root (Trivy reads it automatically), one ID per line, each
  preceded by a WHY comment.
- Never edit `.mega-linter.yml` to remove `REPOSITORY_CHECKOV` or
  `REPOSITORY_TRIVY`, and never add `--soft-fail` / `--exit-code 0`
  to make a gate pass.

## terraform fmt / validate without credentials

```bash
terraform fmt -check -recursive -diff .   # non-zero exit => drift; -diff shows it
terraform fmt -recursive .                # the safe auto-fix (harden mode)

terraform init -backend=false             # no backend, no cloud credentials
terraform validate                        # types, required args, refs
terraform validate -json                  # machine-readable for the report
```

`-backend=false` is the whole trick for auditing someone else's repo:
`validate` needs an initialized module (providers + modules resolved)
but does NOT need the real remote state, and with `-backend=false` it
never contacts it. A module that cannot `init -backend=false` is a
HIGH finding — it cannot be validated by anyone, including CI.

For a repo using OpenTofu, substitute `tofu` for `terraform`
throughout; the flags shown here are identical.

## tflint

```bash
tflint --init                 # download the rulesets named in .tflint.hcl
tflint --recursive            # walk sub-modules
tflint --format compact       # or: --format sarif  (for the report)
tflint --chdir=envs/prod      # one root module
```

Configuration lives in `.tflint.hcl`; the provider ruleset must be
declared there (name, version, source) or tflint only applies its
small core ruleset. A repo with `tflint` in CI but no `.tflint.hcl`
is a MEDIUM finding: the lint is running near-empty.

## Checkov

```bash
checkov -d .                                   # scan a directory
checkov -d . --framework terraform --compact   # terraform only, failures only
checkov -d . -o sarif --output-file-path .     # SARIF for the report
checkov -d . --skip-check CKV_AWS_20           # ONLY with a documented reason
checkov -d . --download-external-modules true  # resolve remote modules
checkov -d . --baseline .checkov.baseline      # only NEW findings
```

- Exit code `0` = clean, `1` = findings. `--soft-fail` forces `0` —
  forbidden in `gate` mode, and its presence in a repo's CI is itself
  a finding.
- `--create-baseline` is legitimate ONLY as a migration step on a
  large legacy repo: it freezes the existing debt so *new* code is
  gated. It must be paired with a TRDD to burn the baseline down, or
  it is just a permanent mute.

## Trivy

```bash
trivy config .                                       # misconfig scan of the IaC
trivy config --severity HIGH,CRITICAL --exit-code 1 .
trivy config --format sarif --output trivy.sarif .
trivy config --tf-vars prod.tfvars .                 # resolve variables properly
trivy config --tf-exclude-downloaded-modules .       # skip vendored module code
```

`--tf-vars` matters: without the real variable values Trivy evaluates
defaults, so a bucket made public *by a variable* can scan clean.
Pass the repo's own non-secret tfvars; if the tfvars carry secrets,
scan the plan JSON instead (below).

## Scanning the plan JSON instead of the HCL

The single highest-value upgrade to an IaC audit. Both scanners read
a Terraform plan in JSON, and the plan has `for_each`, `count`,
variables, locals, and module inputs already RESOLVED — so it finds
the misconfigurations that HCL-level scanning structurally cannot
see.

```bash
terraform plan -out=tfplan                  # needs the repo's own credentials
terraform show -json tfplan > tfplan.json   # the resolved graph

checkov -f tfplan.json --repo-root-for-plan-enrichment . --deep-analysis
trivy config tfplan.json
```

`tfplan` and `tfplan.json` contain resolved values, and therefore
possibly secrets. Write them to a temp dir, never into the repo, and
delete them when the scan is done. They must NEVER be committed and
never attached to a PR comment.

## Documented suppression — the only permitted escape hatch

A check that genuinely does not apply is suppressed **narrowly, by
ID, with the reason next to it**. That is the pattern this repo
already uses for `CKV_DOCKER_2` / `AVD-DS-0026` (container
HEALTHCHECK on ephemeral run-once containers). Four legitimate forms:

```hcl
# Checkov, one resource, with the reason after the colon:
resource "aws_s3_bucket" "logs" {
  #checkov:skip=CKV_AWS_21:versioning is handled by the bucket-replication stack
  bucket = var.log_bucket
}

# Trivy, one resource, reason in the comment above:
# access logs are shipped by the agent, not the bucket — see ADR-014
#trivy:ignore:AVD-AWS-0089
resource "aws_s3_bucket" "logs" {
  bucket = var.log_bucket
}
```

Repo-wide (only when the check is inapplicable to EVERY file):
append the ID to `REPOSITORY_CHECKOV_ARGUMENTS` in `.mega-linter.yml`
with a comment, and/or append it to `.trivyignore` with a comment.

Forbidden, in every mode:

- disabling `REPOSITORY_CHECKOV` / `REPOSITORY_TRIVY`;
- `--soft-fail`, `--exit-code 0`, dropping `--severity` to `CRITICAL`
  only, or any other threshold relaxation;
- a bare suppression with no reason (`gate` mode fails on it);
- suppressing a check because the fix is *hard*. Hard-to-fix is a
  TRDD, not an ignore line.

Before writing ANY suppression, re-run the scanner and copy the ID
from its output. IDs drift between scanner releases; a hand-typed ID
that no longer exists silently suppresses nothing — or, worse, the
wrong thing.

## Exit codes

| Command | 0 | non-zero |
|---|---|---|
| `terraform fmt -check` | formatted | drift |
| `terraform validate` | valid | invalid config |
| `terraform plan -detailed-exitcode` | no changes | `1` error, `2` changes pending |
| `checkov` | clean | `1` findings (unless `--soft-fail`) |
| `trivy config` | always `0` unless `--exit-code` is set | set `--exit-code 1` in a gate |
| `tflint` | clean | issues found |

`trivy config` defaulting to exit `0` is the classic silent-gate bug:
a CI step that runs `trivy config .` without `--exit-code 1` passes
forever, no matter how many CRITICAL findings it prints. Grep the
entrusted repo's workflows for exactly that.
