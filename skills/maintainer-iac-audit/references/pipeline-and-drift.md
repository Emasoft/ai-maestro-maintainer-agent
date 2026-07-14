# IaC pipeline, plan review, and drift

## Table of Contents

- [The gate order](#the-gate-order)
- [Plan review in a PR without leaking values](#plan-review-in-a-pr-without-leaking-values)
- [Drift detection](#drift-detection)
- [The lock-file CI check](#the-lock-file-ci-check)
- [Apply gating](#apply-gating)
- [Remediation-PR protocol](#remediation-pr-protocol)

The audit does not stop at the `.tf` files: half the real risk lives
in *how* the repo runs Terraform. This file covers the gate the
entrusted repo should have, how a plan is reviewed without leaking
secrets, and how drift is detected.

## The gate order

Cheap and safe first; anything needing cloud credentials last.

1. `terraform fmt -check -recursive` — no credentials, milliseconds.
2. `terraform init -backend=false` + `terraform validate` — no
   credentials, no backend contact.
3. `tflint --recursive` — no credentials.
4. `checkov` + `trivy config` — no credentials (this is what CI's
   `REPOSITORY_CHECKOV` / `REPOSITORY_TRIVY` already do).
5. `terraform init -lockfile=readonly` — fails if the lock file would
   have to change.
6. `terraform plan -out=tfplan` — **needs credentials**; read-only
   against the cloud, but it does refresh state.
7. Re-scan the resolved plan JSON (`checkov -f tfplan.json`,
   `trivy config tfplan.json`) — the highest-signal step.

Steps 1-5 belong on every PR. Steps 6-7 belong on PRs that touch IaC,
under an identity that can plan but not apply.

## Plan review in a PR without leaking values

A plan can print secret values (any attribute not marked
`sensitive`). So:

- **Do not paste raw plan output into a PR comment.** Post a
  *summary* — resource counts and the addresses being created,
  changed, replaced, destroyed — and keep the full plan as a
  restricted CI artifact.
- Watch specifically for `-/+` (replace) and `-` (destroy) on
  stateful resources. A destroy on a database in a PR whose title
  says "rename a tag" is the single most valuable thing an IaC review
  ever catches.
- Extract the summary from the plan JSON rather than scraping the
  human output:

  ```bash
  terraform show -json tfplan \
    | jq -r '.resource_changes[]
             | select(.change.actions != ["no-op"])
             | "\(.change.actions|join(",")) \(.address)"'
  ```

- Delete `tfplan` / `tfplan.json` after the scan; never commit them.

A workflow shape that satisfies the above — pin every third-party
action to a commit SHA (`workflow-pin-actions` does this; tags are
shown here for readability):

```yaml
permissions:
  contents: read
  id-token: write        # OIDC — so no long-lived cloud key is needed
  pull-requests: write   # only if the job posts the summary comment

jobs:
  plan:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v5
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ vars.TF_PLAN_ROLE_ARN }}   # plan-only role
          aws-region: ${{ vars.AWS_REGION }}
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_wrapper: false
      - run: terraform init -lockfile=readonly
      - run: terraform validate
      - run: terraform plan -out=tfplan
      - run: terraform show -json tfplan > tfplan.json
      - run: trivy config --exit-code 1 --severity HIGH,CRITICAL tfplan.json
```

Findings to raise against an existing workflow: a long-lived
`AWS_ACCESS_KEY_ID` secret instead of OIDC · a plan job with
`permissions: write-all` · a plan job whose role can also apply ·
`trivy config` with no `--exit-code 1` (a gate that can never fail) ·
`pull_request_target` on a job that checks out the fork's code.

## Drift detection

Drift = the cloud no longer matches the state. It is how a "reviewed"
repo ends up describing infrastructure that does not exist.

```bash
terraform plan -detailed-exitcode -refresh-only
# exit 0 = no drift · 1 = error · 2 = drift detected
```

Run it on a schedule (nightly / weekly) rather than on every PR, and
have the job open an issue on exit `2` naming the drifted resource
addresses. Do NOT auto-reconcile: `terraform apply -refresh-only`
accepts the out-of-band change into state, and `terraform apply`
reverts it — which of the two is correct is a human decision, and the
wrong one deletes something. The maintainer reports; the owner picks.

Recurring drift on the same resource is itself a finding: something
outside Terraform (a console click, another tool, an autoscaler) owns
that resource, so either Terraform should stop managing it (a
`removed` block) or the other writer should stop.

## The lock-file CI check

```bash
terraform init -lockfile=readonly
```

Fails when `.terraform.lock.hcl` would need to change — i.e. when
somebody bumped a provider constraint without re-locking, or the lock
file is missing platform hashes. That failure is the *intended*
outcome: the fix is to run `terraform providers lock -platform=…` for
every platform the team uses and commit the result, in the same PR
that changed the constraint.

## Apply gating

- `apply` runs from the default branch after merge, never from a PR.
- The apply identity is a separate role from the plan identity.
- Production apply sits behind a GitHub Environment with a required
  reviewer.
- `prevent_destroy = true` in the `lifecycle` block of every stateful
  production resource (database, state bucket, KMS key) — it turns an
  accidental destroy into a plan-time error.
- The maintainer agent never runs `apply` itself. Ever.

## Remediation-PR protocol

- **One finding class per PR.** Formatting, pinning, and a security
  fix in one PR means the reviewer sees 400 changed lines and
  approves the one dangerous hunk by accident.
- Order the work: (1) secrets + tracked state — these are incidents,
  not PRs; (2) pinning + lock file — no plan diff, safe to merge;
  (3) formatting — no plan diff; (4) security fixes that DO change
  the plan, one at a time, each with its plan diff in the PR body.
- Every PR body carries: the finding, the scanner ID as printed, the
  file:line, why it is dangerous, and the plan diff (`0 to add, 1 to
  change, 0 to destroy` — or the reason there is none).
- A fix that would replace or destroy a stateful resource is called
  out in the PR title, not buried in the body.
- Never bundle a suppression into a fix PR. A suppression is its own
  PR, with its own justification, so it can be reviewed as the
  security decision it is.
