"""Sentinel rule batch B tests — triggers/forks.

Faithful 1:1 port of the Ruby test/rules/test_*.rb suites for the five
batch-B rules: dangerous_triggers, overly_broad_triggers,
self_hosted_runner_fork, allow_forks_artifact, cache_poisoning.

No mocks: each case builds a real Workflow from inline YAML, runs the rule,
and asserts on the returned findings (rule name, severity, count, message,
and line where the Ruby test pins one).
"""

from __future__ import annotations

from textwrap import dedent

from sentinel.rules.allow_forks_artifact import AllowForksArtifact
from sentinel.rules.cache_poisoning import CachePoisoning
from sentinel.rules.dangerous_triggers import DangerousTriggers
from sentinel.rules.overly_broad_triggers import OverlyBroadTriggers
from sentinel.rules.self_hosted_runner_fork import SelfHostedRunnerFork
from sentinel.workflow import Workflow


def _wf(yaml: str) -> Workflow:
    """Build a Workflow named ci.yml from a dedented inline YAML string."""
    return Workflow("ci.yml", dedent(yaml).lstrip("\n"))


# --- dangerous-triggers ---------------------------------------------------


def test_dangerous_triggers_flags_prt_with_pr_head_checkout() -> None:
    """pull_request_target + checkout of PR head SHA is flagged critical."""
    wf = _wf(
        """
        on: pull_request_target
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
                with:
                  ref: ${{ github.event.pull_request.head.sha }}
        """
    )
    findings = DangerousTriggers().check(wf)
    assert len(findings) == 1
    assert findings[0].severity == "critical"
    assert "pull_request_target" in (findings[0].message or "")


def test_dangerous_triggers_no_flag_prt_without_checkout() -> None:
    """pull_request_target without any checkout step is not flagged."""
    wf = _wf(
        """
        on: pull_request_target
        jobs:
          label:
            runs-on: ubuntu-latest
            steps:
              - run: echo "just labeling"
        """
    )
    assert DangerousTriggers().check(wf) == []


def test_dangerous_triggers_no_flag_regular_pr_with_checkout() -> None:
    """A plain pull_request trigger checking out head is not flagged."""
    wf = _wf(
        """
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
                with:
                  ref: ${{ github.event.pull_request.head.sha }}
        """
    )
    assert DangerousTriggers().check(wf) == []


def test_dangerous_triggers_no_flag_prt_checkout_default_ref() -> None:
    """pull_request_target checkout with the default ref is not flagged."""
    wf = _wf(
        """
        on: pull_request_target
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
        """
    )
    assert DangerousTriggers().check(wf) == []


def test_dangerous_triggers_flags_prt_with_head_ref() -> None:
    """pull_request_target + checkout of github.head_ref is flagged."""
    wf = _wf(
        """
        on: pull_request_target
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
                with:
                  ref: ${{ github.head_ref }}
        """
    )
    assert len(DangerousTriggers().check(wf)) == 1


def test_dangerous_triggers_no_flag_refs_heads_branch_name() -> None:
    """A literal refs/heads/main checkout ref is not flagged."""
    wf = _wf(
        """
        on: pull_request_target
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
                with:
                  ref: refs/heads/main
        """
    )
    assert DangerousTriggers().check(wf) == []


def test_dangerous_triggers_rule_name() -> None:
    """The rule advertises name dangerous-triggers."""
    assert DangerousTriggers().name == "dangerous-triggers"


# --- overly-broad-triggers ------------------------------------------------


def test_overly_broad_triggers_flags_push_no_filters() -> None:
    """push: {} (empty hash, no filters) is flagged low."""
    wf = _wf(
        """
        on:
          push: {}
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - run: echo hi
        """
    )
    findings = OverlyBroadTriggers().check(wf)
    push_findings = [f for f in findings if f.code and "push" in f.code]
    assert len(push_findings) >= 1
    assert push_findings[0].severity == "low"


def test_overly_broad_triggers_no_flag_push_with_branches() -> None:
    """push with a branches filter is not flagged."""
    wf = _wf(
        """
        on:
          push:
            branches: [main]
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - run: echo hi
        """
    )
    findings = OverlyBroadTriggers().check(wf)
    assert [f for f in findings if f.code and "push" in f.code] == []


def test_overly_broad_triggers_no_flag_push_with_branches_ignore() -> None:
    """push with a branches-ignore filter is not flagged."""
    wf = _wf(
        """
        on:
          push:
            branches-ignore: [experimental]
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - run: echo hi
        """
    )
    findings = OverlyBroadTriggers().check(wf)
    assert [f for f in findings if f.code and "push" in f.code] == []


def test_overly_broad_triggers_no_flag_push_with_paths() -> None:
    """push with a paths filter is not flagged."""
    wf = _wf(
        """
        on:
          push:
            paths: ["src/**"]
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - run: echo hi
        """
    )
    findings = OverlyBroadTriggers().check(wf)
    assert [f for f in findings if f.code and "push" in f.code] == []


def test_overly_broad_triggers_no_flag_push_with_tags() -> None:
    """push with a tags filter is not flagged."""
    wf = _wf(
        """
        on:
          push:
            tags: ["v*"]
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - run: echo hi
        """
    )
    findings = OverlyBroadTriggers().check(wf)
    assert [f for f in findings if f.code and "push" in f.code] == []


def test_overly_broad_triggers_flags_pull_request_no_filters() -> None:
    """pull_request: {} (no filters) is flagged."""
    wf = _wf(
        """
        on:
          pull_request: {}
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - run: echo hi
        """
    )
    findings = OverlyBroadTriggers().check(wf)
    pr_findings = [f for f in findings if f.code and "pull_request" in f.code]
    assert len(pr_findings) >= 1


def test_overly_broad_triggers_flags_bare_push_nil_config() -> None:
    """A bare push: with nil config is flagged."""
    wf = _wf(
        """
        on:
          push:
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - run: echo hi
        """
    )
    findings = OverlyBroadTriggers().check(wf)
    push_findings = [f for f in findings if f.code and "push" in f.code]
    assert len(push_findings) >= 1


def test_overly_broad_triggers_rule_name() -> None:
    """The rule advertises name overly-broad-triggers."""
    assert OverlyBroadTriggers().name == "overly-broad-triggers"


# --- self-hosted-runner-fork ----------------------------------------------


def test_self_hosted_runner_fork_flags_self_hosted_with_pull_request() -> None:
    """self-hosted runner under pull_request is flagged high."""
    wf = _wf(
        """
        on: pull_request
        jobs:
          build:
            runs-on: self-hosted
            steps:
              - uses: actions/checkout@v4
              - run: echo "building"
        """
    )
    findings = SelfHostedRunnerFork().check(wf)
    assert len(findings) == 1
    assert findings[0].severity == "high"
    msg = findings[0].message or ""
    assert "self-hosted" in msg.lower() and "pull_request" in msg.lower()


def test_self_hosted_runner_fork_safe_with_github_hosted_runner() -> None:
    """A GitHub-hosted runner under pull_request is not flagged."""
    wf = _wf(
        """
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
              - run: echo "building"
        """
    )
    assert SelfHostedRunnerFork().check(wf) == []


def test_self_hosted_runner_fork_safe_with_self_hosted_push_only() -> None:
    """self-hosted runner under push-only is not flagged."""
    wf = _wf(
        """
        on: push
        jobs:
          build:
            runs-on: self-hosted
            steps:
              - uses: actions/checkout@v4
              - run: echo "building"
        """
    )
    assert SelfHostedRunnerFork().check(wf) == []


def test_self_hosted_runner_fork_flags_multiple_self_hosted_jobs() -> None:
    """Two self-hosted jobs under pull_request produce two findings."""
    wf = _wf(
        """
        on: pull_request
        jobs:
          build:
            runs-on: self-hosted
            steps:
              - uses: actions/checkout@v4
          test:
            runs-on: self-hosted
            steps:
              - uses: actions/checkout@v4
        """
    )
    assert len(SelfHostedRunnerFork().check(wf)) == 2


def test_self_hosted_runner_fork_flags_self_hosted_with_mixed_runners() -> None:
    """Only the self-hosted job among mixed runners is flagged."""
    wf = _wf(
        """
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/checkout@v4
          deploy:
            runs-on: self-hosted
            steps:
              - uses: actions/checkout@v4
        """
    )
    assert len(SelfHostedRunnerFork().check(wf)) == 1


def test_self_hosted_runner_fork_safe_with_self_hosted_labeled_gate() -> None:
    """self-hosted gated by types: [labeled] is not flagged."""
    wf = _wf(
        """
        on:
          pull_request:
            types: [labeled]
        jobs:
          build:
            runs-on: self-hosted
            steps:
              - uses: actions/checkout@v4
              - run: echo "building"
        """
    )
    assert SelfHostedRunnerFork().check(wf) == []


# --- allow-forks-artifact -------------------------------------------------


def test_allow_forks_artifact_flags_allow_forks_true() -> None:
    """allow_forks: true on an artifact download is flagged medium."""
    wf = _wf(
        """
        on: workflow_run
        jobs:
          process:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/download-artifact@v4
                with:
                  allow_forks: true
        """
    )
    findings = AllowForksArtifact().check(wf)
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert "fork-produced artifacts" in (findings[0].message or "")


def test_allow_forks_artifact_safe_without_allow_forks() -> None:
    """An artifact download without allow_forks is not flagged."""
    wf = _wf(
        """
        on: workflow_run
        jobs:
          process:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/download-artifact@v4
        """
    )
    assert AllowForksArtifact().check(wf) == []


def test_allow_forks_artifact_safe_with_allow_forks_false() -> None:
    """allow_forks: false is not flagged."""
    wf = _wf(
        """
        on: workflow_run
        jobs:
          process:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/download-artifact@v4
                with:
                  allow_forks: false
        """
    )
    assert AllowForksArtifact().check(wf) == []


def test_allow_forks_artifact_rule_name() -> None:
    """The rule advertises name allow-forks-artifact."""
    assert AllowForksArtifact().name == "allow-forks-artifact"


# --- cache-poisoning ------------------------------------------------------


def test_cache_poisoning_flags_cache_key_with_github_head_ref() -> None:
    """A cache key embedding github.head_ref is flagged medium."""
    wf = _wf(
        """
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/cache@v3
                with:
                  path: ~/.cache
                  key: ${{ runner.os }}-${{ github.head_ref }}-cache
        """
    )
    findings = CachePoisoning().check(wf)
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].rule == "cache-poisoning"
    assert "fork-controllable" in (findings[0].message or "")


def test_cache_poisoning_safe_with_hashfiles_only() -> None:
    """A cache key using only hashFiles() is not flagged."""
    wf = _wf(
        """
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/cache@v3
                with:
                  path: node_modules
                  key: ${{ runner.os }}-node-${{ hashFiles('**/package-lock.json') }}
        """
    )
    assert CachePoisoning().check(wf) == []


def test_cache_poisoning_flags_cache_key_with_github_ref_on_pull_request() -> None:
    """A cache key using github.ref on a pull_request trigger is flagged."""
    wf = _wf(
        """
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/cache@v3
                with:
                  path: ~/.cache
                  key: ${{ runner.os }}-${{ github.ref }}-deps
        """
    )
    findings = CachePoisoning().check(wf)
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert "github.ref" in (findings[0].message or "")


def test_cache_poisoning_safe_with_fixed_string_key() -> None:
    """A fixed-string cache key is not flagged."""
    wf = _wf(
        """
        on: pull_request
        jobs:
          build:
            runs-on: ubuntu-latest
            steps:
              - uses: actions/cache@v3
                with:
                  path: ~/.cache
                  key: my-project-cache-v1
        """
    )
    assert CachePoisoning().check(wf) == []
