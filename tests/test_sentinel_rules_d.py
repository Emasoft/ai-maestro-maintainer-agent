"""Batch D rule tests — permissions / timeouts / env / dispatch injection.

Ports the positive and negative cases from the Ruby test suite
(test/rules/test_{missing,excessive}_permissions.rb,
test_missing_timeouts.rb, test_missing_env_protection.rb,
test_workflow_dispatch_injection.rb). No mocks — every test builds a real
``Workflow`` from inline YAML, runs the real rule, and asserts on the
returned findings.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from sentinel.rules.excessive_permissions import ExcessivePermissions
from sentinel.rules.missing_env_protection import MissingEnvProtection
from sentinel.rules.missing_permissions import MissingPermissions
from sentinel.rules.missing_timeouts import MissingTimeouts
from sentinel.rules.workflow_dispatch_injection import WorkflowDispatchInjection
from sentinel.workflow import Workflow


# --- missing-permissions ---------------------------------------------------


def test_missing_permissions_flags_missing() -> None:
    """Flags a workflow with no top-level permissions block (medium)."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n"
    wf = Workflow(filename="ci.yml", content=yaml)
    findings = MissingPermissions().check(wf)
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].message is not None and "permissions" in findings[0].message


def test_missing_permissions_no_flag_with_permissions() -> None:
    """Does not flag when a top-level permissions block is present."""
    yaml = "on: push\npermissions:\n  contents: read\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n"
    wf = Workflow(filename="ci.yml", content=yaml)
    assert MissingPermissions().check(wf) == []


def test_missing_permissions_no_flag_with_empty_permissions() -> None:
    """Does not flag when permissions is an explicit empty mapping."""
    yaml = "on: push\npermissions: {}\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n"
    wf = Workflow(filename="ci.yml", content=yaml)
    assert MissingPermissions().check(wf) == []


def test_missing_permissions_rule_name() -> None:
    """Rule exposes the exact upstream name string."""
    assert MissingPermissions().name == "missing-permissions"


# --- excessive-permissions -------------------------------------------------


def test_excessive_permissions_flags_contents_write_with_no_write_steps() -> None:
    """Flags contents: write when no step performs a write operation (low)."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: write\n    steps:\n      - uses: actions/checkout@v4\n      - run: npm test\n"
    wf = Workflow(filename="ci.yml", content=yaml)
    findings = ExcessivePermissions().check(wf)
    assert len(findings) == 1
    assert findings[0].severity == "low"
    assert findings[0].rule == "excessive-permissions"
    assert findings[0].message is not None and "contents: write" in findings[0].message


def test_excessive_permissions_safe_when_job_has_git_push() -> None:
    """Does not flag when a run: step contains git push."""
    yaml = 'on: push\njobs:\n  release:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: write\n    steps:\n      - uses: actions/checkout@v4\n      - run: |\n          git add .\n          git commit -m "update"\n          git push\n'
    wf = Workflow(filename="ci.yml", content=yaml)
    assert ExcessivePermissions().check(wf) == []


def test_excessive_permissions_safe_when_contents_read() -> None:
    """Does not flag when permission is contents: read."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    permissions:\n      contents: read\n    steps:\n      - uses: actions/checkout@v4\n      - run: npm test\n"
    wf = Workflow(filename="ci.yml", content=yaml)
    assert ExcessivePermissions().check(wf) == []


def test_excessive_permissions_safe_when_no_permissions_block() -> None:
    """Does not flag a job with no permissions block at all."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - run: npm test\n"
    wf = Workflow(filename="ci.yml", content=yaml)
    assert ExcessivePermissions().check(wf) == []


# --- missing-timeouts ------------------------------------------------------


def test_missing_timeouts_flags_job_without_timeout() -> None:
    """Flags a job lacking timeout-minutes (low)."""
    yaml = 'on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo "hello"\n'
    wf = Workflow(filename="ci.yml", content=yaml)
    findings = MissingTimeouts().check(wf)
    assert len(findings) == 1
    assert findings[0].severity == "low"
    assert findings[0].message is not None and "no timeout-minutes" in findings[0].message


def test_missing_timeouts_safe_with_timeout_minutes() -> None:
    """Does not flag when timeout-minutes is present."""
    yaml = 'on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    timeout-minutes: 15\n    steps:\n      - run: echo "hello"\n'
    wf = Workflow(filename="ci.yml", content=yaml)
    assert MissingTimeouts().check(wf) == []


def test_missing_timeouts_multiple_jobs_one_missing() -> None:
    """Flags only the job that lacks a timeout among multiple jobs."""
    yaml = 'on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    timeout-minutes: 15\n    steps:\n      - run: echo "build"\n  deploy:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo "deploy"\n'
    wf = Workflow(filename="ci.yml", content=yaml)
    findings = MissingTimeouts().check(wf)
    assert len(findings) == 1
    assert findings[0].message is not None and "deploy" in findings[0].message


def test_missing_timeouts_rule_name() -> None:
    """Rule exposes the exact upstream name string."""
    assert MissingTimeouts().name == "missing-timeouts"


# --- missing-env-protection ------------------------------------------------


def test_missing_env_protection_flags_npm_publish_without_environment() -> None:
    """Flags npm publish in a job lacking environment protection (medium)."""
    yaml = "on: push\njobs:\n  release:\n    runs-on: ubuntu-latest\n    steps:\n      - run: npm publish\n"
    wf = Workflow(filename="release.yml", content=yaml)
    findings = MissingEnvProtection().check(wf)
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].rule == "missing-env-protection"


def test_missing_env_protection_flags_mvn_deploy_without_environment() -> None:
    """Flags mvn deploy in a job lacking environment protection."""
    yaml = "on: push\njobs:\n  release:\n    runs-on: ubuntu-latest\n    steps:\n      - run: mvn deploy -P release\n"
    wf = Workflow(filename="release.yml", content=yaml)
    findings = MissingEnvProtection().check(wf)
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].rule == "missing-env-protection"


def test_missing_env_protection_flags_cargo_publish_without_environment() -> None:
    """Flags cargo publish in a job lacking environment protection."""
    yaml = "on: push\njobs:\n  release:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo publish\n"
    wf = Workflow(filename="release.yml", content=yaml)
    findings = MissingEnvProtection().check(wf)
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].rule == "missing-env-protection"


def test_missing_env_protection_safe_when_environment_is_set() -> None:
    """Does not flag when the job declares an environment."""
    yaml = "on: push\njobs:\n  release:\n    runs-on: ubuntu-latest\n    environment: production\n    steps:\n      - run: npm publish\n"
    wf = Workflow(filename="release.yml", content=yaml)
    assert MissingEnvProtection().check(wf) == []


def test_missing_env_protection_oidc_alone_is_not_flagged() -> None:
    """id-token: write WITHOUT a real publish indicator is not a publish job.

    Calibration 2026-05-25: OIDC id-token: write is used for codecov, cloud-auth
    in tests, attestation and Pages deploys, so it is no longer a standalone
    publish signal — a job that only holds it (no publish command/action) and
    just runs `echo` is not flagged (was a false positive on CI/test/scan jobs).
    """
    yaml = 'on: push\njobs:\n  release:\n    runs-on: ubuntu-latest\n    permissions:\n      id-token: write\n      contents: read\n    steps:\n      - run: echo "deploying"\n'
    wf = Workflow(filename="release.yml", content=yaml)
    assert MissingEnvProtection().check(wf) == []


def test_missing_env_protection_flags_publish_action_without_environment() -> None:
    """A known publish action (pypa/gh-action-pypi-publish) with no environment flags."""
    yaml = "on: push\njobs:\n  release:\n    runs-on: ubuntu-latest\n    permissions:\n      id-token: write\n    steps:\n      - uses: pypa/gh-action-pypi-publish@release/v1\n"
    wf = Workflow(filename="release.yml", content=yaml)
    findings = MissingEnvProtection().check(wf)
    assert len(findings) == 1
    assert findings[0].rule == "missing-env-protection"


def test_missing_env_protection_dry_run_publish_is_not_flagged() -> None:
    """A `--dry-run` publish uploads nothing, so it is not a real publication."""
    yaml = "on: push\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n      - run: cargo publish --workspace --dry-run\n"
    wf = Workflow(filename="check.yml", content=yaml)
    assert MissingEnvProtection().check(wf) == []


def test_missing_env_protection_flags_pnpm_publish_without_environment() -> None:
    """Flags pnpm publish in a job lacking environment protection."""
    yaml = "on: push\njobs:\n  release:\n    runs-on: ubuntu-latest\n    steps:\n      - run: pnpm publish --no-git-checks\n"
    wf = Workflow(filename="release.yml", content=yaml)
    assert len(MissingEnvProtection().check(wf)) == 1


def test_missing_env_protection_flags_twine_upload_without_environment() -> None:
    """Flags twine upload in a job lacking environment protection."""
    yaml = "on: push\njobs:\n  release:\n    runs-on: ubuntu-latest\n    steps:\n      - run: twine upload dist/*\n"
    wf = Workflow(filename="release.yml", content=yaml)
    assert len(MissingEnvProtection().check(wf)) == 1


def test_missing_env_protection_flags_docker_push_without_environment() -> None:
    """Flags docker push in a job lacking environment protection."""
    yaml = "on: push\njobs:\n  release:\n    runs-on: ubuntu-latest\n    steps:\n      - run: docker push myimage:latest\n"
    wf = Workflow(filename="release.yml", content=yaml)
    assert len(MissingEnvProtection().check(wf)) == 1


def test_missing_env_protection_flags_terraform_apply_without_environment() -> None:
    """Flags terraform apply in a job lacking environment protection."""
    yaml = "on: push\njobs:\n  deploy:\n    runs-on: ubuntu-latest\n    steps:\n      - run: terraform apply -auto-approve\n"
    wf = Workflow(filename="deploy.yml", content=yaml)
    assert len(MissingEnvProtection().check(wf)) == 1


def test_missing_env_protection_flags_dotnet_nuget_push_without_environment() -> None:
    """Flags dotnet nuget push in a job lacking environment protection."""
    yaml = "on: push\njobs:\n  release:\n    runs-on: ubuntu-latest\n    steps:\n      - run: dotnet nuget push *.nupkg\n"
    wf = Workflow(filename="release.yml", content=yaml)
    assert len(MissingEnvProtection().check(wf)) == 1


def test_missing_env_protection_flags_gradlew_publish_without_environment() -> None:
    """Flags ./gradlew publish in a job lacking environment protection."""
    yaml = "on: push\njobs:\n  release:\n    runs-on: ubuntu-latest\n    steps:\n      - run: ./gradlew publish\n"
    wf = Workflow(filename="release.yml", content=yaml)
    assert len(MissingEnvProtection().check(wf)) == 1


def test_missing_env_protection_flags_poetry_publish_without_environment() -> None:
    """Flags poetry publish in a job lacking environment protection."""
    yaml = "on: push\njobs:\n  release:\n    runs-on: ubuntu-latest\n    steps:\n      - run: poetry publish --build\n"
    wf = Workflow(filename="release.yml", content=yaml)
    assert len(MissingEnvProtection().check(wf)) == 1


def test_missing_env_protection_flags_fly_deploy_without_environment() -> None:
    """Flags fly deploy in a job lacking environment protection."""
    yaml = "on: push\njobs:\n  deploy:\n    runs-on: ubuntu-latest\n    steps:\n      - run: fly deploy\n"
    wf = Workflow(filename="deploy.yml", content=yaml)
    assert len(MissingEnvProtection().check(wf)) == 1


def test_missing_env_protection_safe_no_publish_commands() -> None:
    """Does not flag a build job with no publish/deploy commands."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: npm install\n      - run: npm test\n"
    wf = Workflow(filename="ci.yml", content=yaml)
    assert MissingEnvProtection().check(wf) == []


# --- workflow-dispatch-injection -------------------------------------------


def test_workflow_dispatch_injection_flags_inputs_in_run_block() -> None:
    """Flags ${{ inputs.name }} interpolated into a run: block (high)."""
    yaml = 'on:\n  workflow_dispatch:\n    inputs:\n      name:\n        description: "Name to greet"\njobs:\n  greet:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Greet\n        run: |\n          echo "Hello ${{ inputs.name }}"\n'
    wf = Workflow(filename="ci.yml", content=yaml)
    findings = WorkflowDispatchInjection().check(wf)
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].message is not None and "inputs.name" in findings[0].message


def test_workflow_dispatch_injection_flags_github_event_inputs_in_run_block() -> None:
    """Flags ${{ github.event.inputs.name }} in a run: block."""
    yaml = 'on:\n  workflow_dispatch:\n    inputs:\n      name:\n        description: "Name to greet"\njobs:\n  greet:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Greet\n        run: |\n          echo "Hello ${{ github.event.inputs.name }}"\n'
    wf = Workflow(filename="ci.yml", content=yaml)
    findings = WorkflowDispatchInjection().check(wf)
    assert len(findings) == 1
    assert findings[0].message is not None and "github.event.inputs.name" in findings[0].message


def test_workflow_dispatch_injection_safe_in_env_block() -> None:
    """Does not flag a dispatch input referenced only inside an env: block."""
    yaml = 'on:\n  workflow_dispatch:\n    inputs:\n      name:\n        description: "Name to greet"\njobs:\n  greet:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Greet\n        env:\n          NAME: ${{ inputs.name }}\n        run: echo "Hello $NAME"\n'
    wf = Workflow(filename="ci.yml", content=yaml)
    assert WorkflowDispatchInjection().check(wf) == []


def test_workflow_dispatch_injection_flags_input_in_run_block_after_env_block() -> None:
    """Flags an input in a run: block even when an env: block precedes it."""
    yaml = 'on:\n  workflow_dispatch:\n    inputs:\n      name:\n        description: "Name"\njobs:\n  greet:\n    runs-on: ubuntu-latest\n    steps:\n      - env:\n          FOO: bar\n        run: |\n          echo "Hello ${{ inputs.name }}"\n'
    wf = Workflow(filename="ci.yml", content=yaml)
    findings = WorkflowDispatchInjection().check(wf)
    assert len(findings) == 1
    assert findings[0].message is not None and "inputs.name" in findings[0].message


def test_workflow_dispatch_injection_safe_in_with_block() -> None:
    """Does not flag a dispatch input passed through a with: block."""
    yaml = 'on:\n  workflow_dispatch:\n    inputs:\n      name:\n        description: "Name to greet"\njobs:\n  greet:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: some/action@v1\n        with:\n          greeting: ${{ inputs.name }}\n'
    wf = Workflow(filename="ci.yml", content=yaml)
    assert WorkflowDispatchInjection().check(wf) == []


def test_workflow_dispatch_injection_no_flag_for_commented_out_line() -> None:
    """Does not flag a fully commented-out line containing an input expr."""
    yaml = 'on:\n  workflow_dispatch:\n    inputs:\n      name:\n        description: "Name"\njobs:\n  greet:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Greet\n        run: |\n          # echo "Hello ${{ inputs.name }}"\n          echo "safe"\n'
    wf = Workflow(filename="ci.yml", content=yaml)
    assert WorkflowDispatchInjection().check(wf) == []


def test_workflow_dispatch_injection_flags_expr_in_trailing_comment() -> None:
    """Flags an input expr that appears in a trailing comment on a run line."""
    yaml = 'on:\n  workflow_dispatch:\n    inputs:\n      name:\n        description: "Name"\njobs:\n  greet:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Greet\n        run: |\n          echo "safe" # ${{ inputs.name }}\n'
    wf = Workflow(filename="ci.yml", content=yaml)
    assert len(WorkflowDispatchInjection().check(wf)) == 1


def test_workflow_dispatch_injection_flags_despite_step_guard_equals_push() -> None:
    """Flags despite a step-level if: github.event_name == 'push' guard."""
    yaml = 'on:\n  workflow_dispatch:\n    inputs:\n      name:\n        description: "Name"\n  push:\njobs:\n  greet:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Greet\n        if: github.event_name == \'push\'\n        run: |\n          echo "Hello ${{ inputs.name }}"\n'
    wf = Workflow(filename="ci.yml", content=yaml)
    assert len(WorkflowDispatchInjection().check(wf)) == 1


def test_workflow_dispatch_injection_flags_despite_job_guard() -> None:
    """Flags despite a job-level if: github.event_name == 'push' guard."""
    yaml = 'on:\n  workflow_dispatch:\n    inputs:\n      name:\n        description: "Name"\n  push:\njobs:\n  greet:\n    if: github.event_name == \'push\'\n    runs-on: ubuntu-latest\n    steps:\n      - name: Greet\n        run: |\n          echo "Hello ${{ inputs.name }}"\n'
    wf = Workflow(filename="ci.yml", content=yaml)
    assert len(WorkflowDispatchInjection().check(wf)) == 1


def test_workflow_dispatch_injection_still_flags_workflow_dispatch_only() -> None:
    """Flags inputs even when workflow_dispatch is the only trigger (no safe-trigger exemption)."""
    yaml = 'on:\n  workflow_dispatch:\n    inputs:\n      name:\n        description: "Name"\njobs:\n  greet:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Greet\n        run: |\n          echo "Hello ${{ inputs.name }}"\n'
    wf = Workflow(filename="ci.yml", content=yaml)
    assert len(WorkflowDispatchInjection().check(wf)) == 1


def test_workflow_dispatch_injection_still_flags_without_guard() -> None:
    """Flags inputs in a run: block with workflow_dispatch + push and no guard."""
    yaml = 'on:\n  workflow_dispatch:\n    inputs:\n      name:\n        description: "Name"\n  push:\njobs:\n  greet:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Greet\n        run: |\n          echo "Hello ${{ inputs.name }}"\n'
    wf = Workflow(filename="ci.yml", content=yaml)
    assert len(WorkflowDispatchInjection().check(wf)) == 1
