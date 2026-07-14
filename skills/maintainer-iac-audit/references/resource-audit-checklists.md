# Per-resource audit checklists

## Table of Contents

- [How to use these](#how-to-use-these)
- [RDS and Aurora](#rds-and-aurora)
- [ElastiCache](#elasticache)
- [Lambda](#lambda)
- [ECS and EKS](#ecs-and-eks)
- [Other encrypted stores](#other-encrypted-stores)
- [IAM: require MFA](#iam-require-mfa)
- [MFA-delete on the state bucket](#mfa-delete-on-the-state-bucket)
- [Fast detection greps](#fast-detection-greps)

## How to use these

The finding catalogue in [tf-audit-checks](tf-audit-checks.md) covers
the cross-cutting checks (secrets, public exposure, encryption,
pinning). This file drills into the per-resource boxes a scanner scores
individually — each box is an AUDIT check ("is this true of the
resource already in the repo?"), never an authoring requirement to bolt
on. A box that is unchecked AND unjustified is a finding; a box that is
unchecked with a documented, scoped suppression is not.

## RDS and Aurora

- [ ] `storage_encrypted = true` (customer-managed `kms_key_id` where
      policy requires it) — HIGH if absent
- [ ] `publicly_accessible = false` — CRITICAL if `true`
- [ ] `backup_retention_period` > 0 (a zero disables backups silently) — HIGH
- [ ] Multi-AZ enabled for a production instance — MEDIUM
- [ ] IAM database authentication enabled where the app supports it — MEDIUM
- [ ] Enhanced monitoring / Performance Insights on, with an encrypted
      Insights key — LOW/MEDIUM
- [ ] TLS required on connections (a parameter-group flag such as
      `rds.force_ssl`) — MEDIUM
- [ ] `deletion_protection = true` and a `lifecycle { prevent_destroy = true }`
      on the production database — HIGH (an accidental destroy is
      unrecoverable)

`backup_retention_period = 0` is the quiet one: the instance provisions
fine, the plan is green, and there is no point-in-time recovery the day
it is needed.

## ElastiCache

- [ ] `at_rest_encryption_enabled = true` — HIGH
- [ ] `transit_encryption_enabled = true` — HIGH
- [ ] An auth token set for Redis (`auth_token`, fed from a secret, not
      a literal) — HIGH
- [ ] Subnet group placed in private subnets only — HIGH if public
- [ ] Automatic failover / Multi-AZ for a production replication
      group — MEDIUM

## Lambda

- [ ] Environment variables encrypted with a KMS key (`kms_key_arn`),
      never carrying a plaintext secret — HIGH
- [ ] VPC configuration present when the code reaches private
      resources — MEDIUM
- [ ] Execution role scoped to least privilege, not a wildcard
      policy — HIGH
- [ ] A dead-letter target (`dead_letter_config`) so a failed async
      invoke is not lost — LOW/MEDIUM
- [ ] `reserved_concurrent_executions` set where a runaway invoke would
      be a cost or blast-radius problem — LOW

A plaintext secret inside a Lambda environment variable is a secret in
state and in the console: treat it as a leak, chain
`maintainer-secrets-scan`, and move it to a secret store read at
runtime.

## ECS and EKS

- [ ] Secrets injected via Secrets Manager / SSM Parameter Store
      references, never as a plaintext container environment value — HIGH
- [ ] Container image pinned to a digest and scanned (ECR scan-on-push,
      or the repo's image scanner) — MEDIUM
- [ ] Task/pod IAM role scoped to least privilege — HIGH
- [ ] Network policy enforced (security groups per task, or a
      Kubernetes `NetworkPolicy`) — MEDIUM
- [ ] EKS: RBAC configured and the cluster endpoint not public-open;
      pod-level security controls in place — HIGH
- [ ] ECS: `enable_execute_command` audited — it is a remote-shell path
      into a running task, useful but powerful — MEDIUM

## Other encrypted stores

The at-rest encryption box applies to more than the headliners. Confirm
an explicit encryption argument (and a KMS key where policy needs one)
on: DynamoDB (`server_side_encryption`), SQS (`kms_master_key_id`),
Kinesis (`encryption_type = "KMS"`), EBS volumes, OpenSearch /
Elasticsearch domains (`encrypt_at_rest`), and CloudWatch log groups
(`kms_key_id`). A store whose encryption merely DEFAULTS to on still
deserves an explicit `true` — the default is the provider's and can
change across a major provider release.

## IAM: require MFA

A policy that denies everything unless MFA is present is the standard
guardrail for human principals. The remediated shape (safe to propose):

```hcl
data "aws_iam_policy_document" "require_mfa" {
  statement {
    sid       = "DenyAllWithoutMFA"
    effect    = "Deny"
    actions   = ["*"]
    resources = ["*"]

    condition {
      test     = "BoolIfExists"
      variable = "aws:MultiFactorAuthPresent"
      values   = ["false"]
    }
  }
}
```

`BoolIfExists` (not plain `Bool`) is deliberate: it still denies when
the key is absent, so a request made without ever presenting MFA is
caught, not waved through.

## MFA-delete on the state bucket

The remote-state bucket is the crown jewel — losing or tampering with
state can destroy every environment. Beyond the backend checklist in
[tf-audit-checks](tf-audit-checks.md) (encrypt · lock · version ·
block-public · scoped IAM), add one more box for the STATE bucket
specifically:

- [ ] MFA-delete enabled on the state bucket, so a stray or
      compromised credential cannot silently delete a state version.

MFA-delete cannot be toggled through the standard Terraform S3
resource — it is applied by the account root with the AWS CLI — so the
audit finding is "not enabled", and the fix is a documented manual step
for the owner, not an auto-applied edit.

## Fast detection greps

Cheap first-pass signals, before the scanners run. Each is a hint to
confirm, not a verdict:

```bash
grep -rnE 'backup_retention_period[[:space:]]*=[[:space:]]*0\b' --include='*.tf' .
grep -rn  'publicly_accessible[[:space:]]*=[[:space:]]*true'     --include='*.tf' .
grep -rnE '(at_rest|transit)_encryption_enabled[[:space:]]*=[[:space:]]*false' --include='*.tf' .
grep -rn  'enable_execute_command[[:space:]]*=[[:space:]]*true'  --include='*.tf' .
```

Map every hit to its catalogue entry and to the scanner rule ID printed
in the run — never author a suppression from a grep hit alone.
