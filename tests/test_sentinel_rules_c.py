"""Tests for Sentinel batch-C rules (pinning + AWS credentials).

Ports test/rules/test_unpinned_actions.rb, test_unpinned_artifact.rb,
test_unpinned_docker_image.rb, test_github_dependency_refs.rb, and
test_static_aws_credentials.rb. No mocks: each test builds a real
Workflow from inline YAML, runs the rule, and asserts on the findings.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from sentinel.rules.github_dependency_refs import GithubDependencyRefs
from sentinel.rules.static_aws_credentials import StaticAwsCredentials
from sentinel.rules.unpinned_actions import UnpinnedActions
from sentinel.rules.unpinned_artifact import UnpinnedArtifact
from sentinel.rules.unpinned_docker_image import UnpinnedDockerImage
from sentinel.workflow import Workflow

# --------------------------------------------------------------------------
# unpinned-actions
# --------------------------------------------------------------------------


def test_unpinned_actions_flags_tag_pinned_third_party() -> None:
    """Third-party tag-pinned action is flagged at medium severity."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: pnpm/action-setup@v4\n"
    findings = UnpinnedActions().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "medium"


def test_unpinned_actions_sha_pinned_no_flag() -> None:
    """A SHA-pinned action produces no finding."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11\n"
    findings = UnpinnedActions().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_unpinned_actions_local_action_no_flag() -> None:
    """A local (./) action reference produces no finding."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: ./my-action\n"
    findings = UnpinnedActions().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_unpinned_actions_docker_action_no_flag() -> None:
    """A docker:// action reference produces no finding."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: docker://alpine:3.18\n"
    findings = UnpinnedActions().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_unpinned_actions_first_party_severity_low() -> None:
    """An actions/* tag-pinned action is flagged at low severity."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n"
    findings = UnpinnedActions().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "low"


def test_unpinned_actions_github_first_party_severity_low() -> None:
    """A github/* tag-pinned action is flagged at low severity."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: github/codeql-action/analyze@v3\n"
    findings = UnpinnedActions().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "low"


def test_unpinned_actions_multiple_actions_mixed() -> None:
    """Mixed steps yield one medium (third-party) and one low (first-party)."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11\n      - uses: pnpm/action-setup@v4\n      - uses: ./local-action\n      - uses: actions/setup-node@v4\n"
    findings = UnpinnedActions().check(Workflow("ci.yml", yaml))
    assert len(findings) == 2
    severities = [f.severity for f in findings]
    assert "medium" in severities
    assert "low" in severities


def test_unpinned_actions_rule_name() -> None:
    """Rule exposes the canonical name 'unpinned-actions'."""
    assert UnpinnedActions().name == "unpinned-actions"


def test_unpinned_actions_rule_severity() -> None:
    """Default class severity is medium."""
    assert UnpinnedActions().severity == "medium"


# --------------------------------------------------------------------------
# unpinned-artifact
# --------------------------------------------------------------------------


def test_unpinned_artifact_flags_download_artifact_without_name() -> None:
    """download-artifact with no with: block is flagged at low severity."""
    yaml = "on: push\njobs:\n  deploy:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/download-artifact@v4\n      - run: ls -la\n"
    findings = UnpinnedArtifact().check(Workflow("deploy.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "low"
    assert findings[0].rule == "unpinned-artifact"
    assert findings[0].message is not None and "without specific name" in findings[0].message


def test_unpinned_artifact_safe_with_specific_name() -> None:
    """download-artifact with a name produces no finding."""
    yaml = "on: push\njobs:\n  deploy:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/download-artifact@v4\n        with:\n          name: build-output\n      - run: ls -la\n"
    findings = UnpinnedArtifact().check(Workflow("deploy.yml", yaml))
    assert findings == []


def test_unpinned_artifact_flags_with_block_missing_name() -> None:
    """download-artifact with a with: block but no name is flagged."""
    yaml = "on: push\njobs:\n  deploy:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/download-artifact@v4\n        with:\n          path: ./dist\n      - run: ls -la\n"
    findings = UnpinnedArtifact().check(Workflow("deploy.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "low"
    assert findings[0].message is not None and "without specific name" in findings[0].message


def test_unpinned_artifact_safe_with_name_and_path() -> None:
    """download-artifact with both name and path produces no finding."""
    yaml = "on: push\njobs:\n  deploy:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/download-artifact@v4\n        with:\n          name: my-artifact\n          path: ./dist\n      - run: ls -la\n"
    findings = UnpinnedArtifact().check(Workflow("deploy.yml", yaml))
    assert findings == []


# --------------------------------------------------------------------------
# unpinned-docker-image
# --------------------------------------------------------------------------


def test_unpinned_docker_image_flags_docker_protocol_latest() -> None:
    """docker://node:latest is flagged at low severity."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: docker://node:latest\n"
    findings = UnpinnedDockerImage().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "low"
    assert findings[0].message is not None and ":latest" in findings[0].message


def test_unpinned_docker_image_flags_image_latest() -> None:
    """A container image: node:latest is flagged."""
    yaml = 'on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    container:\n      image: node:latest\n    steps:\n      - run: echo "hello"\n'
    findings = UnpinnedDockerImage().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1
    assert findings[0].message is not None and ":latest" in findings[0].message


def test_unpinned_docker_image_safe_with_sha_digest() -> None:
    """An image pinned by sha256 digest produces no finding."""
    yaml = 'on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    container:\n      image: node@sha256:abc123def456\n    steps:\n      - run: echo "hello"\n'
    findings = UnpinnedDockerImage().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_unpinned_docker_image_safe_with_specific_tag() -> None:
    """An image pinned to a specific version tag produces no finding."""
    yaml = 'on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    container:\n      image: node:18.17.0\n    steps:\n      - run: echo "hello"\n'
    findings = UnpinnedDockerImage().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_unpinned_docker_image_rule_name() -> None:
    """Rule exposes the canonical name 'unpinned-docker-image'."""
    assert UnpinnedDockerImage().name == "unpinned-docker-image"


# --------------------------------------------------------------------------
# github-dependency-refs
# --------------------------------------------------------------------------


def _dep_wf(run_line: str) -> Workflow:
    """Build a one-step workflow whose run: is the given command line."""
    yaml = f"on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Install\n        run: {run_line}\n"
    return Workflow("ci.yml", yaml)


def test_github_dependency_refs_rule_name() -> None:
    """Rule exposes the canonical name 'github-dependency-refs'."""
    assert GithubDependencyRefs().name == "github-dependency-refs"


def test_github_dependency_refs_rule_severity() -> None:
    """Rule severity is medium."""
    assert GithubDependencyRefs().severity == "medium"


def test_github_dependency_refs_rule_description() -> None:
    """Description mentions GitHub refs."""
    desc = GithubDependencyRefs().description
    assert "GitHub" in desc and "ref" in desc


def test_github_dependency_refs_flags_npm_install_github_ref() -> None:
    """npm install of a github: ref is flagged."""
    findings = GithubDependencyRefs().check(_dep_wf("npm install github:owner/repo#abc123"))
    assert len(findings) == 1
    assert findings[0].message is not None and "GitHub" in findings[0].message and "ref" in findings[0].message


def test_github_dependency_refs_flags_yarn_add_git_https() -> None:
    """yarn add of a git+https GitHub URL is flagged."""
    findings = GithubDependencyRefs().check(_dep_wf("yarn add git+https://github.com/owner/repo"))
    assert len(findings) == 1
    assert findings[0].message is not None and "GitHub" in findings[0].message and "ref" in findings[0].message


def test_github_dependency_refs_flags_pnpm_add_github_ref() -> None:
    """pnpm add of a github: ref is flagged."""
    findings = GithubDependencyRefs().check(_dep_wf("pnpm add github:owner/repo#main"))
    assert len(findings) == 1


def test_github_dependency_refs_flags_bun_add_github_ref() -> None:
    """bun add of a github: ref is flagged."""
    findings = GithubDependencyRefs().check(_dep_wf("bun add github:owner/repo#sha256"))
    assert len(findings) == 1


def test_github_dependency_refs_safe_npm_install_registry_package() -> None:
    """npm install of a registry package produces no finding."""
    findings = GithubDependencyRefs().check(_dep_wf("npm install express"))
    assert findings == []


def test_github_dependency_refs_safe_pnpm_install_registry_package() -> None:
    """pnpm install of a registry package produces no finding."""
    findings = GithubDependencyRefs().check(_dep_wf("pnpm install lodash"))
    assert findings == []


def test_github_dependency_refs_safe_comment_line() -> None:
    """A commented-out github: install inside a run block is not flagged."""
    yaml = 'on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Install\n        run: |\n          # npm install github:owner/repo#abc123\n          echo "skipped"\n'
    findings = GithubDependencyRefs().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_github_dependency_refs_fix_message() -> None:
    """The fix recommends installing from the registry."""
    findings = GithubDependencyRefs().check(_dep_wf("npm install github:owner/repo#abc123"))
    assert findings[0].fix is not None and "registry" in findings[0].fix


# --------------------------------------------------------------------------
# static-aws-credentials
# --------------------------------------------------------------------------


def test_static_aws_credentials_flags_static_keys() -> None:
    """configure-aws-credentials with static keys and no OIDC is flagged."""
    yaml = "on: push\njobs:\n  deploy:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: aws-actions/configure-aws-credentials@v4\n        with:\n          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}\n          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}\n          aws-region: us-east-1\n"
    findings = StaticAwsCredentials().check(Workflow("deploy.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].rule == "static-aws-credentials"


def test_static_aws_credentials_safe_with_oidc_role_to_assume() -> None:
    """configure-aws-credentials with role-to-assume produces no finding."""
    yaml = (
        "on: push\n"
        "jobs:\n"
        "  deploy:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: aws-actions/configure-aws-credentials@v4\n"
        "        with:\n"
        "          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}\n"
        "          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}\n"
        "          role-to-assume: arn:aws:iam::123456789012:role/my-role\n"
        "          aws-region: us-east-1\n"
    )
    findings = StaticAwsCredentials().check(Workflow("deploy.yml", yaml))
    assert findings == []


def test_static_aws_credentials_safe_when_action_is_not_configure_aws() -> None:
    """A non-AWS action carrying aws-access-key-id is not flagged."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n        with:\n          aws-access-key-id: something\n"
    findings = StaticAwsCredentials().check(Workflow("ci.yml", yaml))
    assert findings == []


def test_static_aws_credentials_flags_even_when_sha_pinned() -> None:
    """SHA-pinning the AWS action does not exempt static keys from the flag."""
    yaml = (
        "on: push\n"
        "jobs:\n"
        "  deploy:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: aws-actions/configure-aws-credentials@e3dd6a429d7300ae5d9a1e72e33b6b189ab18237\n"
        "        with:\n"
        "          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}\n"
        "          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}\n"
        "          aws-region: us-east-1\n"
    )
    findings = StaticAwsCredentials().check(Workflow("deploy.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "medium"
