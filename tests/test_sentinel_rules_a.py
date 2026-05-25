"""Tests for Sentinel batch-A rules (secrets + injection).

Ports test/rules/test_hardcoded_secrets.rb, test_shell_injection_expr.rb,
test_shell_injection_jq.rb, test_github_script_injection.rb, and
test_curl_pipe_shell.rb. No mocks: each test builds a real Workflow from
inline YAML, runs the rule, and asserts on the findings.
"""

from __future__ import annotations

import os
import re
import sys
from textwrap import dedent

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from sentinel.rules.curl_pipe_shell import CurlPipeShell
from sentinel.rules.github_script_injection import GithubScriptInjection
from sentinel.rules.hardcoded_secrets import HardcodedSecrets
from sentinel.rules.shell_injection_expr import ShellInjectionExpr
from sentinel.rules.shell_injection_jq import ShellInjectionJq
from sentinel.workflow import Workflow

# --------------------------------------------------------------------------
# hardcoded-secrets
# --------------------------------------------------------------------------


def test_hardcoded_secrets_flags_aws_access_key() -> None:
    """An inline AWS access key is flagged once as critical."""
    yaml = dedent("""\
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Deploy
                run: |
                  export AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
    """)
    findings = HardcodedSecrets().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "critical"
    assert re.search(r"AWS access key", findings[0].message or "")


def test_hardcoded_secrets_flags_github_pat() -> None:
    """An inline GitHub PAT is flagged with the matching label."""
    yaml = dedent("""\
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Clone
                run: |
                  git clone https://ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij@github.com/org/repo
    """)
    findings = HardcodedSecrets().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1
    assert re.search(r"GitHub personal access token", findings[0].message or "")


def test_hardcoded_secrets_safe_when_using_secrets_expression() -> None:
    """A ${{ secrets.* }} reference produces no finding."""
    yaml = dedent("""\
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Deploy
                env:
                  API_KEY: ${{ secrets.API_KEY }}
                run: echo "deploying"
    """)
    findings = HardcodedSecrets().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_hardcoded_secrets_safe_when_line_is_comment() -> None:
    """A secret-shaped value inside a comment line is not flagged."""
    yaml = dedent("""\
        on: push
        # AKIAIOSFODNN7EXAMPLE is an example key
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - run: echo "hello"
    """)
    findings = HardcodedSecrets().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_hardcoded_secrets_flags_hardcoded_password() -> None:
    """A hardcoded password yields at least one password finding."""
    yaml = dedent("""\
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Login
                run: |
                  password: mysecretpassword123
    """)
    findings = HardcodedSecrets().check(Workflow("ci.yml", yaml))
    assert len(findings) >= 1
    assert any(re.search(r"password", f.message or "", re.IGNORECASE) for f in findings)


def test_hardcoded_secrets_safe_password_with_secrets_ref() -> None:
    """A password set to a secrets reference produces no password finding."""
    yaml = dedent("""\
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Login
                run: |
                  password: ${{ secrets.DB_PASSWORD }}
    """)
    findings = HardcodedSecrets().check(Workflow("ci.yml", yaml))
    assert [f for f in findings if re.search(r"password", f.message or "", re.IGNORECASE)] == []


def test_hardcoded_secrets_safe_password_true() -> None:
    """A boolean `true` password value is not flagged."""
    yaml = dedent("""\
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            services:
              mariadb:
                image: mariadb:latest
                env:
                  MARIADB_ALLOW_EMPTY_ROOT_PASSWORD: true
    """)
    findings = HardcodedSecrets().check(Workflow("ci.yml", yaml))
    assert [f for f in findings if re.search(r"password", f.message or "", re.IGNORECASE)] == []


def test_hardcoded_secrets_safe_password_false() -> None:
    """A boolean `false` password value is not flagged."""
    yaml = dedent("""\
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            services:
              db:
                image: postgres:latest
                env:
                  SOME_PASSWORD: false
    """)
    findings = HardcodedSecrets().check(Workflow("ci.yml", yaml))
    assert [f for f in findings if re.search(r"password", f.message or "", re.IGNORECASE)] == []


# --------------------------------------------------------------------------
# shell-injection-expr
# --------------------------------------------------------------------------


def test_shell_injection_expr_flags_pr_title_in_run_block() -> None:
    """PR title interpolated in a run: block is flagged as critical."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Greet
                run: |
                  echo "${{ github.event.pull_request.title }}"
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "critical"
    assert re.search(r"pull_request\.title", findings[0].message or "")


def test_shell_injection_expr_no_flag_in_env_block() -> None:
    """A dangerous expr inside an env: block (not run:) is not flagged."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Greet
                env:
                  PR_TITLE: ${{ github.event.pull_request.title }}
                run: echo "$PR_TITLE"
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_shell_injection_expr_no_flag_in_with_block() -> None:
    """A dangerous expr inside a with: block is not flagged."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: some/action@v1
                with:
                  title: ${{ github.event.pull_request.title }}
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_shell_injection_expr_no_flag_for_safe_context_github_sha() -> None:
    """github.sha is not an attacker-controlled context — no finding."""
    yaml = dedent("""\
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Show SHA
                run: echo "${{ github.sha }}"
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_shell_injection_expr_no_flag_github_actor_in_run() -> None:
    """github.actor is not a dangerous context — no finding."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Show actor
                run: echo "${{ github.actor }}"
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_shell_injection_expr_no_flag_triggering_actor_in_run() -> None:
    """github.triggering_actor is not a dangerous context — no finding."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Show actor
                run: echo "${{ github.triggering_actor }}"
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_shell_injection_expr_flags_head_ref_in_run() -> None:
    """github.head_ref interpolated in run: is flagged once."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Show ref
                run: echo "${{ github.head_ref }}"
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_shell_injection_expr_flags_issue_body_in_run() -> None:
    """github.event.issue.body interpolated in run: is flagged once."""
    yaml = dedent("""\
        on: issues
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Process issue
                run: |
                  echo "${{ github.event.issue.body }}"
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_shell_injection_expr_flags_comment_body_in_run() -> None:
    """github.event.comment.body interpolated in run: is flagged once."""
    yaml = dedent("""\
        on: issue_comment
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Process comment
                run: echo "${{ github.event.comment.body }}"
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_shell_injection_expr_flags_inline_run_without_name() -> None:
    """An inline `- run:` without a name: still gets flagged."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - run: echo "${{ github.event.pull_request.title }}"
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_shell_injection_expr_flags_expr_in_run_block_after_env_block() -> None:
    """A run: block that follows an env: block within the step is flagged."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - env:
                  FOO: bar
                run: |
                  echo "${{ github.event.pull_request.title }}"
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1
    assert re.search(r"pull_request\.title", findings[0].message or "")


def test_shell_injection_expr_no_flag_expr_inside_env_block_before_run() -> None:
    """A dangerous expr inside env: that follows run: is not flagged."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - run: |
                  echo "hello"
                env:
                  TITLE: ${{ github.event.pull_request.title }}
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_shell_injection_expr_no_flag_for_push_only_trigger() -> None:
    """A push-only workflow is safe-triggered — no finding."""
    yaml = dedent("""\
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Show ref
                run: echo "${{ github.head_ref }}"
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_shell_injection_expr_no_flag_for_workflow_dispatch_only_trigger() -> None:
    """A workflow_dispatch-only workflow is safe-triggered — no finding."""
    yaml = dedent("""\
        on: workflow_dispatch
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Show ref
                run: echo "${{ github.head_ref }}"
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_shell_injection_expr_flags_pull_request_trigger_with_head_ref() -> None:
    """A pull_request trigger with head_ref in run: is flagged once."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Show ref
                run: echo "${{ github.head_ref }}"
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_shell_injection_expr_flags_mixed_triggers_with_unsafe() -> None:
    """Mixed push+pull_request triggers are not all-safe — flagged once."""
    yaml = dedent("""\
        on:
          push:
          pull_request:
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Show ref
                run: echo "${{ github.head_ref }}"
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_shell_injection_expr_no_flag_for_commented_out_line() -> None:
    """A commented-out dangerous line inside run: is not flagged."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Show ref
                run: |
                  # echo "${{ github.head_ref }}"
                  echo "safe"
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_shell_injection_expr_no_flag_with_step_guard_excludes_pull_request() -> None:
    """A step `if: github.event_name == 'push'` guard suppresses the finding."""
    yaml = dedent("""\
        on:
          push:
          pull_request:
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Safe
                if: github.event_name == 'push'
                run: |
                  echo "${{ github.event.pull_request.title }}"
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_shell_injection_expr_no_flag_with_job_guard_excludes_pull_request() -> None:
    """A job-level `if: github.event_name == 'push'` guard suppresses the finding."""
    yaml = dedent("""\
        on:
          push:
          pull_request:
        jobs:
          build:
            if: github.event_name == 'push'
            runs-on: ubuntu-latest
            steps:
              - name: Run
                run: |
                  echo "${{ github.event.pull_request.title }}"
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_shell_injection_expr_flags_expr_in_trailing_comment() -> None:
    """A dangerous expr in a trailing YAML comment is still flagged."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Safe
                run: |
                  echo "safe" # ${{ github.event.pull_request.title }}
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_shell_injection_expr_still_flags_expr_before_trailing_comment() -> None:
    """A dangerous expr before a trailing comment is flagged once."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Unsafe
                run: |
                  echo "${{ github.event.pull_request.title }}" # some comment
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_shell_injection_expr_adjacent_step_guard_does_not_protect_next_step() -> None:
    """A guard on one step does not protect the following unguarded step."""
    yaml = dedent("""\
        on:
          push:
          pull_request:
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Guarded
                if: github.event_name == 'push'
                run: echo "safe"
              - name: Unguarded
                run: |
                  echo "${{ github.event.pull_request.title }}"
    """)
    findings = ShellInjectionExpr().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_shell_injection_expr_rule_name() -> None:
    """The rule exposes the expected name."""
    assert ShellInjectionExpr().name == "shell-injection-expr"


# --------------------------------------------------------------------------
# shell-injection-jq
# --------------------------------------------------------------------------


def test_shell_injection_jq_flags_jq_with_attacker_variable() -> None:
    """An attacker var in a double-quoted jq --arg is flagged as critical."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Build JSON
                run: |
                  jq -n --arg title "${PR_TITLE}" '{title: $title}'
    """)
    findings = ShellInjectionJq().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "critical"
    assert re.search(r"PR_TITLE", findings[0].message or "")


def test_shell_injection_jq_flags_curl_with_attacker_variable() -> None:
    """An attacker var in a double-quoted curl -d payload is flagged."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Post to API
                run: |
                  curl -X POST -d "${ISSUE_TITLE}" https://api.example.com
    """)
    findings = ShellInjectionJq().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1
    assert re.search(r"ISSUE_TITLE", findings[0].message or "")


def test_shell_injection_jq_no_flag_for_safe_variable_in_jq() -> None:
    """A non-attacker var (GITHUB_SHA) in jq is not flagged."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Build JSON
                run: |
                  jq -n --arg sha "${GITHUB_SHA}" '{sha: $sha}'
    """)
    findings = ShellInjectionJq().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_shell_injection_jq_flags_branch_name_variable() -> None:
    """BRANCH_NAME in a jq --arg is flagged once."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Build JSON
                run: |
                  jq -n --arg branch "${BRANCH_NAME}" '{branch: $branch}'
    """)
    findings = ShellInjectionJq().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_shell_injection_jq_flags_jq_with_multiple_flags_before_arg() -> None:
    """jq with multiple flags before --arg still matches and is flagged."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Build JSON
                run: |
                  jq -nc -r --arg title "${PR_TITLE}" '{title: $title}'
    """)
    findings = ShellInjectionJq().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_shell_injection_jq_no_flag_for_innocuous_var_with_attacker_substring() -> None:
    """A var merely containing an attacker substring is not attacker-controlled."""
    rule = ShellInjectionJq()
    assert rule._potentially_attacker_controlled("AUTHOR_VERIFIED") is False
    assert rule._potentially_attacker_controlled("MY_BRANCH_DATA") is False


def test_shell_injection_jq_rule_name() -> None:
    """The rule exposes the expected name."""
    assert ShellInjectionJq().name == "shell-injection-jq"


def test_shell_injection_jq_no_flag_for_push_only_trigger() -> None:
    """A push-only workflow is safe-triggered — no finding."""
    yaml = dedent("""\
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Build JSON
                run: |
                  jq -n --arg title "${PR_TITLE}" '{title: $title}'
    """)
    findings = ShellInjectionJq().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_shell_injection_jq_no_flag_for_schedule_only_trigger() -> None:
    """A schedule-only workflow is safe-triggered — no finding."""
    yaml = dedent("""\
        on: schedule
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Build JSON
                run: |
                  jq -n --arg title "${PR_TITLE}" '{title: $title}'
    """)
    findings = ShellInjectionJq().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_shell_injection_jq_still_flags_for_pull_request_trigger() -> None:
    """A pull_request-triggered jq attacker var is flagged once."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Build JSON
                run: |
                  jq -n --arg title "${PR_TITLE}" '{title: $title}'
    """)
    findings = ShellInjectionJq().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_shell_injection_jq_still_flags_for_mixed_triggers_with_unsafe() -> None:
    """Mixed push+pull_request triggers are not all-safe — flagged once."""
    yaml = dedent("""\
        on:
          push:
          pull_request:
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Build JSON
                run: |
                  jq -n --arg title "${PR_TITLE}" '{title: $title}'
    """)
    findings = ShellInjectionJq().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_shell_injection_jq_no_flag_for_commented_out_line() -> None:
    """A commented-out jq line is not flagged."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Build JSON
                run: |
                  # jq -n --arg title "${PR_TITLE}" '{title: $title}'
                  echo "safe"
    """)
    findings = ShellInjectionJq().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_shell_injection_jq_flags_expr_in_trailing_comment() -> None:
    """A jq attacker var in a trailing comment is still flagged."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Build JSON
                run: |
                  echo "safe" # jq -n --arg title "${PR_TITLE}" '{title: $title}'
    """)
    findings = ShellInjectionJq().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_shell_injection_jq_no_flag_in_env_block() -> None:
    """A jq attacker var inside an env: block (not run:) is not flagged."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Build JSON
                env:
                  CMD: |
                    jq -n --arg title "${PR_TITLE}" '{title: $title}'
                run: echo "$CMD"
    """)
    findings = ShellInjectionJq().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_shell_injection_jq_no_flag_with_step_guard() -> None:
    """A step `if: github.event_name == 'push'` guard suppresses the jq finding."""
    yaml = dedent("""\
        on:
          push:
          pull_request:
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Build JSON
                if: github.event_name == 'push'
                run: |
                  jq -n --arg title "${PR_TITLE}" '{title: $title}'
    """)
    findings = ShellInjectionJq().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_shell_injection_jq_no_flag_with_job_guard() -> None:
    """A job-level guard suppresses the jq finding."""
    yaml = dedent("""\
        on:
          push:
          pull_request:
        jobs:
          build:
            if: github.event_name == 'push'
            runs-on: ubuntu-latest
            steps:
              - name: Build JSON
                run: |
                  jq -n --arg title "${PR_TITLE}" '{title: $title}'
    """)
    findings = ShellInjectionJq().check(Workflow("ci.yml", yaml))
    assert findings == []


# --------------------------------------------------------------------------
# github-script-injection
# --------------------------------------------------------------------------


def test_github_script_injection_flags_pr_title_in_script_block() -> None:
    """PR title in an actions/github-script block is flagged as critical."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/github-script@v7
                with:
                  script: |
                    const title = "${{ github.event.pull_request.title }}";
                    console.log(title);
    """)
    findings = GithubScriptInjection().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "critical"
    assert re.search(r"pull_request\.title", findings[0].message or "")


def test_github_script_injection_safe_when_using_context_payload() -> None:
    """Using context.payload (not ${{ }}) produces no finding."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/github-script@v7
                with:
                  script: |
                    const title = context.payload.pull_request.title;
                    console.log(title);
    """)
    findings = GithubScriptInjection().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_github_script_injection_safe_when_not_in_github_script_step() -> None:
    """A script: under a non-github-script action is not flagged."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: some/other-action@v1
                with:
                  script: |
                    const title = "${{ github.event.pull_request.title }}";
    """)
    findings = GithubScriptInjection().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_github_script_injection_flags_issue_body_in_script() -> None:
    """github.event.issue.body in a github-script block is flagged once."""
    yaml = dedent("""\
        on: issues
        jobs:
          triage:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/github-script@v7
                with:
                  script: |
                    const body = "${{ github.event.issue.body }}";
                    github.rest.issues.createComment({
                      issue_number: context.issue.number,
                      owner: context.repo.owner,
                      repo: context.repo.repo,
                      body: body
                    });
    """)
    findings = GithubScriptInjection().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1
    assert re.search(r"issue\.body", findings[0].message or "")


def test_github_script_injection_no_flag_with_step_guard_excludes_pull_request() -> None:
    """A step guard on the github-script step suppresses the finding."""
    yaml = dedent("""\
        on:
          push:
          pull_request:
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - if: github.event_name == 'push'
                uses: actions/github-script@v7
                with:
                  script: |
                    const title = "${{ github.event.pull_request.title }}";
    """)
    findings = GithubScriptInjection().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_github_script_injection_no_flag_with_job_guard_excludes_pull_request() -> None:
    """A job-level guard suppresses the github-script finding."""
    yaml = dedent("""\
        on:
          push:
          pull_request:
        jobs:
          build:
            if: github.event_name == 'push'
            runs-on: ubuntu-latest
            steps:
              - uses: actions/github-script@v7
                with:
                  script: |
                    const title = "${{ github.event.pull_request.title }}";
    """)
    findings = GithubScriptInjection().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_github_script_injection_no_flag_expr_only_in_trailing_comment() -> None:
    """A JS // comment is not a YAML comment, so the expr is still flagged."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/github-script@v7
                with:
                  script: |
                    const safe = "hello"; // ${{ github.event.pull_request.title }}
    """)
    findings = GithubScriptInjection().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_github_script_injection_flags_expr_in_yaml_trailing_comment() -> None:
    """A YAML # trailing comment containing the expr is still flagged."""
    yaml = dedent("""\
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/github-script@v7
                with:
                  script: |
                    const safe = "hello"; # ${{ github.event.pull_request.title }}
    """)
    findings = GithubScriptInjection().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_github_script_injection_still_flags_without_guard() -> None:
    """Mixed triggers without a guard still flag the github-script expr."""
    yaml = dedent("""\
        on:
          push:
          pull_request:
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/github-script@v7
                with:
                  script: |
                    const title = "${{ github.event.pull_request.title }}";
    """)
    findings = GithubScriptInjection().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_github_script_injection_no_flag_for_push_only() -> None:
    """A push-only workflow is safe-triggered — no github-script finding."""
    yaml = dedent("""\
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/github-script@v7
                with:
                  script: |
                    const title = "${{ github.event.pull_request.title }}";
    """)
    findings = GithubScriptInjection().check(Workflow("ci.yml", yaml))
    assert findings == []


# --------------------------------------------------------------------------
# curl-pipe-shell
# --------------------------------------------------------------------------


def test_curl_pipe_shell_flags_curl_pipe_sh() -> None:
    """`curl ... | sh` is flagged once at high severity."""
    yaml = dedent("""\
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Install
                run: curl -fsSL https://example.com/install.sh | sh
    """)
    findings = CurlPipeShell().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "high"


def test_curl_pipe_shell_flags_curl_pipe_bash() -> None:
    """`curl ... | bash` is flagged once."""
    yaml = dedent("""\
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Install
                run: curl -fsSL https://example.com/install.sh | bash
    """)
    findings = CurlPipeShell().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_curl_pipe_shell_flags_wget_pipe_sh() -> None:
    """`wget ... -O - | sh` is flagged once."""
    yaml = dedent("""\
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Install
                run: wget -q https://example.com/install.sh -O - | sh
    """)
    findings = CurlPipeShell().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_curl_pipe_shell_no_flag_commented_out() -> None:
    """A commented-out curl|sh line is not flagged."""
    yaml = dedent("""\
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Install
                run: |
                  # curl -fsSL https://example.com/install.sh | sh
                  echo "doing it properly"
    """)
    findings = CurlPipeShell().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_curl_pipe_shell_no_flag_curl_without_pipe() -> None:
    """A curl download without a shell pipe is not flagged."""
    yaml = dedent("""\
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Download
                run: curl -fsSL -o installer.sh https://example.com/install.sh
    """)
    findings = CurlPipeShell().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_curl_pipe_shell_flags_curl_pipe_sudo_sh() -> None:
    """`curl ... | sudo sh` is flagged once."""
    yaml = dedent("""\
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Install
                run: curl -fsSL https://example.com/install.sh | sudo sh
    """)
    findings = CurlPipeShell().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_curl_pipe_shell_flags_curl_pipe_sudo_bash() -> None:
    """`curl ... | sudo bash` is flagged once."""
    yaml = dedent("""\
        on: push
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - name: Install
                run: curl -fsSL https://example.com/install.sh | sudo bash
    """)
    findings = CurlPipeShell().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1


def test_curl_pipe_shell_rule_name() -> None:
    """The rule exposes the expected name."""
    assert CurlPipeShell().name == "curl-pipe-shell"
