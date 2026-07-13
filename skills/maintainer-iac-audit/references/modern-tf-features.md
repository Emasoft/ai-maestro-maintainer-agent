# Modern Terraform features an auditor must recognize

## Table of Contents

- [Why this file exists](#why-this-file-exists)
- [Ephemeral values and write-only arguments](#ephemeral-values-and-write-only-arguments)
- [State-management blocks: import, moved, removed](#state-management-blocks-import-moved-removed)
- [Actions blocks](#actions-blocks)
- [The query command and list resources](#the-query-command-and-list-resources)

## Why this file exists

The scanners were written against yesterday's Terraform. Several newer
language surfaces carry real audit weight that Checkov and Trivy may
not score yet, so a human reviewer has to catch them. Every version
number below is a floor — confirm it against the Terraform the
entrusted repo actually pins (`required_version`) and runs; treat a
feature the repo's version predates as inapplicable rather than
missing.

## Ephemeral values and write-only arguments

`sensitive = true` keeps a value out of CLI output but NOT out of the
state file. The pair below is the only way a secret never lands in
state at all:

- **Ephemeral resources / values (Terraform 1.10 and newer)** exist only during
  a single run and are never persisted. Ephemeral input variables and
  ephemeral outputs let a fetched secret flow through a run without
  being written down.
- **Write-only arguments (Terraform 1.11 and newer)** — a provider argument
  whose value is consumed at apply time and never stored. The AWS
  pattern is `password_wo` paired with `password_wo_version` (bumping
  the version is what triggers a re-send).

Audit stance: when a resource takes a secret AND the provider exposes a
write-only variant, recommend it over a plain `sensitive` variable —
the plain variable still deposits the secret in state. Provider support
is uneven, so this is a "recommend where supported", not a blanket
finding. It does not change the plan's effect on infrastructure, so it
is a safe remediation to propose.

## State-management blocks: import, moved, removed

These declarative blocks replace the old imperative `terraform import`
/ `terraform state mv` / `terraform state rm` CLI calls. Prefer the
blocks: they leave a diff a reviewer can see, whereas a CLI state
mutation leaves none.

| Block | Since | What it does | Audit note |
|---|---|---|---|
| `import` | 1.5+ | brings an existing cloud resource under management | benign; confirm the target address and id are right |
| `moved` | 1.1+ | renames/relocates a resource in state without destroy | benign refactor; the safe way to rename |
| `removed` | 1.7+ | stops managing a resource | **read its `lifecycle` carefully** |

**The `removed` block is the dangerous one.** Its nested `lifecycle`
decides the fate of the real resource:

```hcl
# SAFE: forget the resource, leave it running in the cloud
removed {
  from = aws_instance.legacy
  lifecycle {
    destroy = false
  }
}
```

A `removed` block with `destroy = true` (or a `lifecycle` that permits
destroy) will DELETE the live resource on the next apply. A PR that
adds a `removed` block to a stateful resource — a database, a bucket, a
KMS key — is exactly the kind of change whose title says "cleanup" and
whose effect is data loss. Flag it in the PR title, confirm the intent,
and cross-check `prevent_destroy` on the target.

## Actions blocks

**Actions (Terraform 1.14 and newer)** are a new invocation surface: an `action`
block can invoke a Lambda, invalidate a CDN cache, or run a
provider-defined operation, triggered either explicitly at apply or by
a resource's lifecycle events. Because they RUN something as a side
effect of an apply, an auditor reads two things: *what* the action
invokes (is it a privileged operation?) and *what triggers it* (a
lifecycle event on which resource). An action wired to a broad trigger,
or invoking a high-privilege target, is a review item even when no
scanner flags it. This is emerging (provider support was still landing
as of late 2025) — confirm the repo's version and provider actually
support it before treating its absence or presence as anything.

## The query command and list resources

**The `query` command with `.tfquery.hcl` files (Terraform 1.14 and newer)** is,
uniquely, an audit TOOL rather than a thing to audit. It lets you
enumerate live resources declaratively — for example to surface
untagged resources, publicly-reachable resources, or resources matching
a name pattern — without writing them into configuration. Where the
installed Terraform supports it, a query file is a read-only way to
inventory an account for the exact misconfiguration classes this skill
hunts. Confirm the version supports the command before relying on it;
until then, the scanners plus the plan-JSON pass remain the primary
path. Never let a query run mutate anything — it is read-only by
design, and an audit keeps it that way.
