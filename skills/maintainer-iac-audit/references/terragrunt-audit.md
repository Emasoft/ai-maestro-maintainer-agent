# Terragrunt audit — what breaks, what leaks, what is deprecated

## Table of Contents

- [root.hcl vs terragrunt.hcl](#roothcl-vs-terragrunthcl)
- [CLI migration (Terragrunt 0.93+)](#cli-migration-terragrunt-093)
- [Deprecated attributes](#deprecated-attributes)
- [The remote_state block](#the-remote_state-block)
- [generate blocks](#generate-blocks)
- [The errors block](#the-errors-block)
- [The engine block](#the-engine-block)
- [Hooks run arbitrary commands](#hooks-run-arbitrary-commands)
- [Terragrunt stacks](#terragrunt-stacks)
- [dependency and mock_outputs](#dependency-and-mock_outputs)
- [Hardcoded values in inputs](#hardcoded-values-in-inputs)
- [Pinning, in the Terragrunt layer](#pinning-in-the-terragrunt-layer)
- [Strict mode in CI](#strict-mode-in-ci)
- [The audit command sequence](#the-audit-command-sequence)
- [Terragrunt audit checklist](#terragrunt-audit-checklist)

Applies when the repo contains `terragrunt.hcl`, `root.hcl`, or
`terragrunt.stack.hcl`. Everything in `tf-audit-checks.md` still
applies to the Terraform modules underneath; this file covers the
Terragrunt layer on top.

## root.hcl vs terragrunt.hcl

Modern Terragrunt names the root configuration `root.hcl` and the
children include it explicitly:

```hcl
# child unit
include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}
```

A root file still named `terragrunt.hcl` with children calling a bare
`find_in_parent_folders()` is the LEGACY layout. It still works, but
the `root-terragrunt-hcl` strict control errors on it, so it will
break the day the team turns strict mode on. Report as LOW-MEDIUM
with the migration as the fix; never rename it silently — the include
paths in every child must move in the same commit.

A **bare `include` block** (no label) is likewise deprecated in
favour of a named include.

## CLI migration (Terragrunt 0.93+)

The CLI was redesigned. A repo whose CI, Makefile, or docs still call
the old commands is a MEDIUM finding — they warn today and fail once
strict mode is enabled.

| Deprecated | Current |
|---|---|
| `run-all <cmd>` | `run --all <cmd>` |
| `plan-all` / `apply-all` | `run --all plan` / `run --all apply` |
| `hclfmt` | `hcl fmt` |
| `hclvalidate` | `hcl validate` |
| `validate-inputs` | `hcl validate --inputs` |
| `graph-dependencies` | `dag graph` |
| `render-json` | `render --json -w` |
| `terragrunt-info` | `info print` |
| `--terragrunt-*` flags | the unprefixed flag |
| `--terragrunt-parallelism=N` | `--parallelism N` |
| `--terragrunt-non-interactive` | removed — no longer needed or supported |
| `TERRAGRUNT_*` env vars | `TG_*` env vars |

Grep the entrusted repo for the left column:

```bash
grep -rnE 'terragrunt (run-all|plan-all|apply-all|hclfmt|hclvalidate|validate-inputs|graph-dependencies|render-json)' \
  --include='*.yml' --include='*.yaml' --include='*.sh' --include='Makefile' .
grep -rn 'TERRAGRUNT_' --include='*.yml' --include='*.yaml' --include='*.sh' .
```

## Deprecated attributes

| Deprecated | Replacement |
|---|---|
| `skip = true` | an `exclude` block |
| `retryable_errors` | an `errors` block with a `retry` rule |
| bare `include {}` | a named `include "root" {}` |
| root file named `terragrunt.hcl` | `root.hcl` |

## The `remote_state` block

This is where Terragrunt centralises the backend for every unit — so
one missing argument here is a repo-wide finding, not a per-module
one.

```hcl
remote_state {
  backend = "s3"

  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }

  config = {
    bucket       = "org-terraform-state"
    key          = "${path_relative_to_include()}/terraform.tfstate"
    region       = var.region
    encrypt      = true          # HIGH finding if absent or false
    kms_key_id   = "<KMS_KEY_ARN>"
    use_lockfile = true          # native S3 locking; the modern lock
  }
}
```

Audit: `encrypt = true` present · locking configured (`use_lockfile`,
or the legacy `dynamodb_table` on older Terraform) · the state `key`
derived from the path (`path_relative_to_include()`) so units cannot
collide on one key · bucket versioning on.

A `remote_state` block with no `generate` stanza means each unit needs
its own hand-written `backend.tf` — check those instead, and expect
drift between them.

## `generate` blocks

`generate "provider"` writes a `provider.tf` into every unit. Two
audit points:

- **Credentials.** The provider block should assume a role
  (`assume_role { role_arn = ... }`) or rely on the ambient CI
  identity — never carry an access key in the generated content. A
  key inside a `generate` heredoc is a CRITICAL secret finding: it is
  committed AND it is written into every unit's working directory.
- **`if_exists`.** `overwrite_terragrunt` only replaces files
  Terragrunt itself generated; `overwrite` clobbers a hand-written
  file. Prefer `overwrite_terragrunt`.

## The `errors` block

The `errors` block replaces the deprecated `retryable_errors`
attribute. It carries a `retry` rule (which is fine) and an `ignore`
rule — and the `ignore` rule is the audit-relevant one:

```hcl
errors {
  retry "transient_api" {
    retryable_errors = [".*RequestLimitExceeded.*"]
    max_attempts     = 3
    sleep_interval_sec = 5
  }

  ignore "known_benign" {
    signals          = [".*specific benign message.*"]
    message          = "documented reason this class is safe to ignore"
  }
}
```

An `ignore` rule whose pattern is broad (`.*`, or a catch-all) silently
swallows real failures — the run reports success while the underlying
operation failed. Flag any `ignore` that is not narrowly scoped to a
named, documented benign error class. A broad `ignore` is the
Terragrunt equivalent of a scanner `--soft-fail`: a gate that can no
longer fail.

## The `engine` block

Terragrunt can run through a pluggable execution `engine` (used, e.g.,
to run OpenTofu). The engine is CODE that Terragrunt downloads and
executes, so its `source` is a supply-chain surface exactly like a
module or a provider:

- An `engine` sourced from a git repo with no pinned ref, or from an
  arbitrary HTTPS URL, is a HIGH finding — unreviewed code runs on
  every plan and apply.
- Pin the engine to an immutable version/ref, prefer a first-party or
  vendored source, and treat an engine pointing at an unknown host the
  way you would treat an unpinned third-party Action.

## Hooks run arbitrary commands

`before_hook`, `after_hook`, and `error_hook` blocks (and any
`run_cmd()` in a config) execute host commands during a Terragrunt run.
Audit them as a code-execution surface: what command runs, whether its
arguments are attacker-influenceable, and whether it reaches the
network or a credential. A hook that curls a remote script and runs it,
or that shells out to an unpinned tool, is a finding — the same
supply-chain reasoning as the engine block. Report the command shape
and the risk; never reproduce a runnable exploit line in the report.

## Terragrunt stacks

Repos may use `terragrunt.stack.hcl` (stacks, GA around v0.78.0+) to
generate many units from one definition. Two audit points:

- The generated `.terragrunt-stack/` directory is build output, like
  `.terragrunt-cache/` — it MUST be gitignored. A tracked
  `.terragrunt-stack/` is a MEDIUM finding (vendored generated code,
  and it can drift from its source-of-truth stack file).
- Each unit's `source` in the stack file is pinned to an immutable
  version/ref, for the same reason a module source is — a git-based
  unit source on a mutable branch is a HIGH finding.

## `dependency` and `mock_outputs`

```hcl
dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    vpc_id     = "vpc-00000000"
    subnet_ids = ["subnet-00000000"]
  }

  mock_outputs_allowed_terraform_commands = ["validate", "plan", "init"]
}
```

`mock_outputs` exists so `validate`/`plan` work before the dependency
is applied. **`mock_outputs_allowed_terraform_commands` is the safety
belt**: without it, the mock values are usable by `apply` too — and
Terragrunt will happily build production infrastructure wired to
`vpc-00000000`. A `mock_outputs` block with no
`mock_outputs_allowed_terraform_commands` is a HIGH finding.

Also flag: a unit reading another unit's state directly through a
`terraform_remote_state` data source instead of declaring a
`dependency` — the dependency graph then does not know about the
edge, so `run --all` can order the units wrongly.

## Hardcoded values in `inputs`

`inputs` become `TF_VAR_*` for the underlying module, so a secret
there is a secret in the environment of every child process AND in
the repo:

```hcl
inputs = {
  environment  = local.env          # from env.hcl, not a literal
  account_id   = local.account_id   # from account.hcl
  db_password  = get_env("DB_PASSWORD")   # from the secret store, never a literal
}
```

Flag: hardcoded account ids, regions, environment names, and any
credential-shaped literal. The DRY fix is `read_terragrunt_config()`
of an `env.hcl` / `account.hcl` / `region.hcl`, or `get_env()` with no
default for a value that MUST be supplied.

## Pinning, in the Terragrunt layer

```hcl
terraform {
  # registry module, version in the query string
  source = "tfr:///terraform-aws-modules/vpc/aws?version=5.1.2"
}

terragrunt_version_constraint = ">= 0.93.0"
terraform_version_constraint  = ">= 1.6.0, < 2.0.0"
```

A `terraform.source` pointing at a git branch (`?ref=main`) or with
no ref at all is a HIGH finding, for the same reason as an unpinned
Terraform module: the code that runs is not the code that was
reviewed.

## Strict mode in CI

Strict mode turns every deprecation into an error, which is exactly
what a maintainer wants in a gate — the repo learns about a breaking
CLI change on a PR, not during an incident.

```bash
terragrunt info strict                 # list the available controls
terragrunt --strict-mode run --all plan            # flag form
TG_STRICT_MODE=true terragrunt run --all plan      # env-var form (CI)
TG_STRICT_CONTROL='cli-redesign,deprecated-commands' terragrunt run --all plan
```

The `--strict-mode` flag and the `TG_STRICT_MODE` env var are
equivalent; the env var is the usual CI form. The named controls a gate
can turn on one at a time:

| Control | Errors on |
|---|---|
| `cli-redesign` | deprecated CLI syntax (the redesigned-CLI shapes) |
| `deprecated-commands` | deprecated commands (`run-all`, `hclfmt`, `hclvalidate`, …) |
| `root-terragrunt-hcl` | a root file still named `terragrunt.hcl` (use `root.hcl`) |
| `bare-include` | a bare `include {}` block (use a named include) |
| `skip-dependencies-inputs` | not a safety control — a performance opt-in that stops reading dependency inputs |

Recommend enabling it in CI once the deprecation findings above are
cleared — not before, or the gate is red on day one. Turn the controls
on incrementally so each deprecation is fixed as its control lights up.

## The audit command sequence

```bash
terragrunt hcl fmt --check          # formatting, no side effects
terragrunt hcl validate             # HCL syntax
terragrunt hcl validate --inputs    # unset required / unused inputs
terragrunt dag graph                # dependency graph; cycles surface here
terragrunt run --all validate       # needs init; no cloud mutation
```

`run --all apply` / `destroy` are NEVER part of an audit.

Also confirm `.terragrunt-cache/` is gitignored — it is a download
cache and can contain vendored module code and provider binaries.

## Terragrunt audit checklist

- [ ] Root file is `root.hcl`; every include is named and explicit
- [ ] No deprecated CLI command in CI, Makefile, scripts, or docs
- [ ] No `TERRAGRUNT_*` env var left (they are `TG_*` now)
- [ ] No `skip` / `retryable_errors` attribute
- [ ] `remote_state`: `encrypt = true`, locking on, path-derived key
- [ ] No credential inside a `generate` heredoc
- [ ] Every `mock_outputs` is fenced by
      `mock_outputs_allowed_terraform_commands`
- [ ] No hardcoded account id / region / environment / secret in `inputs`
- [ ] `terraform.source` pinned to a version or an immutable ref
- [ ] `terragrunt_version_constraint` + `terraform_version_constraint` set
- [ ] No broad `ignore` rule in an `errors` block (it masks real failures)
- [ ] `engine` block, if present, pinned to an immutable, trusted source
- [ ] Hooks / `run_cmd` run no unpinned or network-fetched command
- [ ] `.terragrunt-cache/` gitignored
- [ ] `.terragrunt-stack/` gitignored; every stack unit `source` pinned
