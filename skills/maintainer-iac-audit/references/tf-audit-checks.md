# Terraform finding catalogue — shape, why, safe fix

## Table of Contents

- [Severity model](#severity-model)
- [Secrets in the configuration](#secrets-in-the-configuration)
- [Secrets in .tfvars](#secrets-in-tfvars)
- [State files](#state-files)
- [Remote-state backend](#remote-state-backend)
- [Version pinning](#version-pinning)
- [The provider lock file](#the-provider-lock-file)
- [Public exposure](#public-exposure)
- [Encryption](#encryption)
- [IAM least privilege](#iam-least-privilege)
- [Logging and tagging](#logging-and-tagging)
- [Check-ID mapping (indicative — always confirm against the run)](#check-id-mapping-indicative--always-confirm-against-the-run)

Every entry is written for an auditor, not an author: *the shape you
will see in the entrusted repo*, *why it is dangerous*, *the fix that
is safe to propose*. Insecure HCL is described, never pasted — the
code blocks below are the REMEDIATED form, so anything copied out of
this file is safe to paste into a repo.

## Severity model

| Severity | Meaning | Gate behaviour |
|---|---|---|
| CRITICAL | A secret is already exposed, or the internet can reach a data store today | `gate` fails; fix before anything else |
| HIGH | A control that should exist does not (no encryption, no pinning, no lock file) | `gate` fails |
| MEDIUM | Weakens defence in depth (no logging, no versioning, loose IAM) | Report, TRDD it |
| LOW | Hygiene (formatting, naming, missing tags/description) | Aggregate; auto-fixable in `harden` |

Two rules that override the table: a **tracked state file is always
CRITICAL** (it is a credential dump, not a config smell), and a
**suppression with no reason is always a finding**, whatever it hides.

## Secrets in the configuration

**Shape.** A literal on the right-hand side of an argument whose name
contains `password`, `secret`, `token`, `api_key`, `access_key`, or
`private_key` — anything not sourced from `var.`, `data.`, or an
`ephemeral` block.

**Why.** It is in git history forever. Removing the line does not
un-leak it; only rotation does.

**Detect.**

```bash
grep -rnE '(password|secret|token|api_key|access_key|private_key)[[:space:]]*=[[:space:]]*"' \
  --include='*.tf' --include='*.tfvars' .
```

**Fix.** A `sensitive` variable fed from the environment
(`TF_VAR_db_password`) or a secret manager, plus rotation of the
leaked value and a history purge (chain `maintainer-secrets-scan`):

```hcl
variable "db_password" {
  description = "Master password, supplied via TF_VAR_db_password or the CI secret store"
  type        = string
  sensitive   = true
}

resource "aws_db_instance" "app" {
  username = "app"
  password = var.db_password
}
```

`sensitive = true` keeps the value out of CLI output — **it does NOT
keep it out of the state file.** On Terraform 1.10+, an `ephemeral`
resource plus a write-only argument (`password_wo`,
`password_wo_version`) is the only way a secret never lands in state
at all; recommend it when the provider supports it.

**Sensitive outputs.** An `output` that returns a password, key, or
connection string without `sensitive = true` prints it to every
console and CI log that runs `apply`:

```hcl
output "db_endpoint" {
  value     = aws_db_instance.app.address
  sensitive = false          # an endpoint is fine
}

output "db_password" {
  value     = var.db_password
  sensitive = true           # required
}
```

## Secrets in `.tfvars`

**Shape.** `prod.tfvars` (or `terraform.tfvars`) tracked in git,
holding a real credential.

**Why.** Same as above — committed, permanent, and usually
world-readable inside the org.

**Fix.** Keep a tracked `terraform.tfvars.example` with placeholder
values; gitignore the real one; feed the real values from the CI
secret store as `TF_VAR_*` environment variables or `-var-file` from
a path outside the repo. Rotate anything already committed.

Note the nuance: *non-secret* tfvars (region, instance size, CIDR
plan) SHOULD be committed — they are the environment's declared
shape. A blanket `*.tfvars` gitignore is a smell in the opposite
direction: it hides the diff that review depends on. Gitignore the
secret-bearing files by name.

## State files

**Shape.** `terraform.tfstate`, `*.tfstate.backup`, or `.terraform/`
tracked in git; or a backend with no encryption.

**Why.** State stores every attribute of every resource in
plaintext — including database passwords, generated keys, and
provider-returned secrets — regardless of `sensitive = true`.

**Fix.**

1. Treat every value in the state as LEAKED: rotate, then purge the
   file from history. Removing it in a new commit is not enough.
2. `.gitignore`:

   ```gitignore
   .terraform/
   *.tfstate
   *.tfstate.*
   crash.log
   *.tfplan
   tfplan.json
   ```

3. Move to a remote backend (below).

**Never** `cat` a state file, never pipe `terraform state pull` into
a report, a log, or an LLM prompt. If a value must be inspected, do
it locally and report only the resource address.

`.terraform.lock.hcl` is the exception in the opposite direction — it
MUST be committed. A `.gitignore` that excludes it is a HIGH finding.

## Remote-state backend

**Shape to flag.** A `backend "s3"` (or gcs/azurerm) block with no
`encrypt`, no KMS key, and no locking; or no `backend` block at all
in a repo more than one person touches (local state = one laptop owns
production).

**Fix (Terraform 1.11+, S3 native locking):**

```hcl
terraform {
  backend "s3" {
    bucket       = "org-terraform-state"
    key          = "prod/vpc/terraform.tfstate"
    region       = "us-east-1"
    encrypt      = true
    kms_key_id   = "<KMS_KEY_ARN>"
    use_lockfile = true
  }
}
```

`use_lockfile = true` uses S3 conditional writes and needs no
DynamoDB table. On Terraform < 1.11 the locking argument is
`dynamodb_table = "<LOCK_TABLE>"` — still supported, now the legacy
path. **No locking at all** is a HIGH finding: two concurrent applies
corrupt state.

Backend checklist: encryption ON · locking ON · bucket versioning ON
(the only way back from a corrupted state) · bucket public access
blocked · IAM scoped to the CI role · one state key per environment
and component (a single mega-state means one bad apply can destroy
every environment).

## Version pinning

**Shape.** `required_providers` with no `version`, or an open
constraint (`>= 5.0`); a `module` block with no `version` /
no `?ref=`.

**Why.** An unpinned provider or module means the code you reviewed
is not the code that runs — a new upstream release (or a compromised
one) is pulled silently on the next `init`.

**Fix.**

```hcl
terraform {
  required_version = ">= 1.6, < 2.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"     # patch/minor float, major pinned
    }
  }
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.1.2"          # registry module: exact version
}

module "internal" {
  # git module: pin to a tag, or better, an immutable commit SHA
  source = "git::https://github.com/org/tf-modules.git//vpc?ref=v1.4.0"
}
```

A git module pinned to a *branch* (`?ref=main`) is a HIGH finding —
the ref is mutable, so the module can change under the repo with no
diff. A tag is acceptable; a full commit SHA is immutable and best.

## The provider lock file

**Shape.** `.terraform.lock.hcl` missing, gitignored, or stale.

**Why.** The lock file pins the exact provider *versions and
checksums*. Without it, `terraform init` re-resolves the constraint
and can pull a different artifact than the one that was reviewed —
the IaC equivalent of an unpinned Action.

**Fix.**

```bash
# Regenerate for every platform the team + CI actually run on,
# so no one is forced to re-lock (and thereby weaken) the file:
terraform providers lock \
  -platform=linux_amd64 \
  -platform=darwin_arm64 \
  -platform=darwin_amd64

git add .terraform.lock.hcl
```

Gate it in CI with `terraform init -lockfile=readonly` — that fails
the build if the lock file would have to change, which is exactly the
event a reviewer must see.

## Public exposure

| Shape seen in the repo | Severity | Safe fix |
|---|---|---|
| Security-group `ingress` whose `cidr_blocks` is the open-to-the-world range `0.0.0.0/0` on 22 / 3389 / a database port | CRITICAL | Replace with a variable holding the admin/VPN CIDR, or reference the peer security group by id |
| `aws_s3_bucket_public_access_block` with any of its four booleans `false`, or absent entirely | HIGH | All four `true` |
| `publicly_accessible = true` on an RDS instance | CRITICAL | `false`; reach it through a bastion or VPN |
| A database/cache subnet group placed in public subnets | HIGH | Private subnets only |
| `http_tokens = "optional"` on an EC2 metadata options block (IMDSv1) | HIGH | `http_tokens = "required"` |

Detection first pass (fast, before the scanners):

```bash
grep -rn '0\.0\.0\.0/0' --include='*.tf' .
grep -rn 'publicly_accessible[[:space:]]*=[[:space:]]*true' --include='*.tf' .
grep -rnE '(encrypted|encryption)[[:space:]]*=[[:space:]]*false' --include='*.tf' .
```

Remediated forms:

```hcl
variable "admin_cidr" {
  description = "CIDR allowed to reach the admin port"
  type        = string
}

resource "aws_security_group_rule" "ssh_admin_only" {
  type              = "ingress"
  description       = "SSH from the admin network only"
  security_group_id = aws_security_group.app.id
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = [var.admin_cidr]
}

resource "aws_s3_bucket_public_access_block" "app" {
  bucket                  = aws_s3_bucket.app.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

`0.0.0.0/0` on an *egress* rule, or on 80/443 for a public web
listener, is normal — do not report it as CRITICAL. The severity is
carried by the PORT and the RESOURCE, not by the CIDR alone.

## Encryption

At rest — check every store: RDS (`storage_encrypted = true`, with a
customer-managed `kms_key_id` where policy requires it), S3
(a `aws_s3_bucket_server_side_encryption_configuration` resource),
EBS, DynamoDB, ElastiCache (`at_rest_encryption_enabled`),
Elasticsearch/OpenSearch, SQS, Kinesis, and CloudWatch log groups
(`kms_key_id`).

In transit — TLS listeners with a modern `ssl_policy`, HTTP→HTTPS
redirect, `transit_encryption_enabled` on ElastiCache, and TLS
enforced on database connections.

A resource whose encryption argument DEFAULTS to on (some do) still
deserves an explicit `true` — the default is the provider's, and it
can change between major provider versions.

## IAM least privilege

**Shape.** A policy statement with `Action = "*"` or `"s3:*"` and
`Resource = "*"`; a trust policy that accepts any principal; a
long-lived access key in CI.

**Fix.** Enumerate the actions, scope the resources to ARNs, add
conditions (external id for third-party assume-role, MFA for humans).
In CI, replace static keys with OIDC federation
(`aws-actions/configure-aws-credentials` with `role-to-assume`) — see
`references/pipeline-and-drift.md`.

```hcl
data "aws_iam_policy_document" "app_read_bucket" {
  statement {
    effect  = "Allow"
    actions = ["s3:GetObject", "s3:ListBucket"]
    resources = [
      aws_s3_bucket.app_data.arn,
      "${aws_s3_bucket.app_data.arn}/*",
    ]
  }
}
```

## Logging and tagging

- CloudTrail: multi-region, management events on, log bucket private
  and encrypted.
- VPC flow logs on every VPC that carries production traffic.
- Log groups: an explicit `retention_in_days` (the default is "keep
  forever", which is both a cost and a privacy finding) and a KMS key.
- Tags: a `locals.common_tags` merged into every resource
  (`Environment`, `Owner`, `ManagedBy = "Terraform"`, cost centre).
  Missing tags are LOW — but they are what makes drift and cost
  attributable later, so report them.

## Check-ID mapping (indicative — always confirm against the run)

A dash means "no ID recorded here — copy it from the run".

| Finding | Checkov | Trivy |
|---|---|---|
| Unrestricted SSH ingress | `CKV_AWS_24` | `AVD-AWS-0132` |
| Unrestricted HTTP ingress | `CKV_AWS_260` | — |
| S3 public access | `CKV_AWS_53`…`CKV_AWS_56` | — |
| S3 encryption | — | `AVD-AWS-0086` |
| S3 versioning | `CKV_AWS_21` | `AVD-AWS-0089` |
| RDS encryption at rest | `CKV_AWS_16` | `AVD-AWS-0107` |
| RDS publicly accessible | `CKV_AWS_17` | — |
| EBS encryption | — | `AVD-AWS-0078` |
| IMDSv1 allowed | `CKV_AWS_79` | — |

IDs move between scanner releases, and this table is a distillation
snapshot, not a live index. Use it to ORIENT a report — never to
author a suppression. The ID that goes into a `#checkov:skip=` line,
a `.trivyignore` entry, or `REPOSITORY_CHECKOV_ARGUMENTS` is copied
character-for-character from the scanner output being suppressed.
