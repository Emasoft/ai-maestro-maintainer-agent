"""Tests for Sentinel rule batch E (credentials/publish).

Ports the positive and negative cases of the Ruby test suites:
  test/rules/test_build_publish_same_job.rb
  test/rules/test_credential_window.rb
  test/rules/test_missing_persist_creds.rb
  test/rules/test_unscoped_app_token.rb
  test/rules/test_docker_build_arg_secrets.rb

No mocks: a real Workflow is built from inline YAML and the rule's
check() is asserted against directly.
"""

from __future__ import annotations

import os
import sys

# Make the scripts/ package importable without installing.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from sentinel.rules.build_publish_same_job import BuildPublishSameJob  # noqa: E402
from sentinel.rules.credential_window import CredentialWindow  # noqa: E402
from sentinel.rules.docker_build_arg_secrets import DockerBuildArgSecrets  # noqa: E402
from sentinel.rules.missing_persist_creds import MissingPersistCreds  # noqa: E402
from sentinel.rules.unscoped_app_token import UnscopedAppToken  # noqa: E402
from sentinel.workflow import Workflow  # noqa: E402


def _wf(name: str, yaml: str) -> Workflow:
    """Build a Workflow from inline YAML text."""
    return Workflow(name, yaml)


# --- build-publish-same-job -------------------------------------------------


def test_build_publish_flags_npm_install_and_publish_with_token() -> None:
    """npm install + npm publish with NPM_TOKEN in step env is flagged high."""
    yaml = """\
on: push
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - run: npm install
      - run: npm publish
        env:
          NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
"""
    findings = BuildPublishSameJob().check(_wf("release.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].rule == "build-publish-same-job"


def test_build_publish_safe_when_install_and_publish_in_separate_jobs() -> None:
    """install and publish split across two jobs is not flagged."""
    yaml = """\
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: npm install
      - run: npm test
  publish:
    runs-on: ubuntu-latest
    needs: build
    steps:
      - run: npm publish
        env:
          NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
"""
    findings = BuildPublishSameJob().check(_wf("release.yml", yaml))
    assert findings == []


def test_build_publish_flags_pnpm_install_and_publish() -> None:
    """pnpm install + pnpm publish with a token is flagged high."""
    yaml = """\
on: push
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - run: pnpm install
      - run: pnpm publish
        env:
          NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
"""
    findings = BuildPublishSameJob().check(_wf("release.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "high"


def test_build_publish_safe_when_no_publish_secrets() -> None:
    """install + publish with no secret in scope is not flagged."""
    yaml = """\
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: npm install
      - run: npm publish
"""
    findings = BuildPublishSameJob().check(_wf("ci.yml", yaml))
    assert findings == []


def test_build_publish_flags_when_secrets_in_job_level_env() -> None:
    """A publish secret in the job-level env (not step env) is still flagged."""
    yaml = """\
on: push
jobs:
  release:
    runs-on: ubuntu-latest
    env:
      NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
    steps:
      - run: npm install
      - run: npm publish
"""
    findings = BuildPublishSameJob().check(_wf("release.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "high"


def test_build_publish_flags_python_pip_install_and_twine_upload_with_pypi_token() -> None:
    """pip install + twine upload with PYPI_TOKEN is flagged high."""
    yaml = """\
on: push
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - run: pip install -r requirements.txt
      - run: python setup.py sdist bdist_wheel
      - run: twine upload dist/*
        env:
          PYPI_TOKEN: ${{ secrets.PYPI_TOKEN }}
"""
    findings = BuildPublishSameJob().check(_wf("publish.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].rule == "build-publish-same-job"


def test_build_publish_flags_ruby_bundle_install_and_gem_push_with_api_key() -> None:
    """bundle install + gem push with GEM_HOST_API_KEY is flagged high."""
    yaml = """\
on: push
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - run: bundle install
      - run: rake build
      - run: gem push pkg/*.gem
        env:
          GEM_HOST_API_KEY: ${{ secrets.RUBYGEMS_API_KEY }}
"""
    findings = BuildPublishSameJob().check(_wf("release.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].rule == "build-publish-same-job"


def test_build_publish_flags_rust_cargo_build_and_publish_with_registry_token() -> None:
    """cargo build + cargo publish with CARGO_REGISTRY_TOKEN is flagged high."""
    yaml = """\
on: push
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - run: cargo build --release
      - run: cargo publish
        env:
          CARGO_REGISTRY_TOKEN: ${{ secrets.CARGO_REGISTRY_TOKEN }}
"""
    findings = BuildPublishSameJob().check(_wf("release.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].rule == "build-publish-same-job"


# --- credential-window ------------------------------------------------------


def test_credential_window_flags_large_gap_between_config_and_push() -> None:
    """git config then push more than 5 steps later is flagged high."""
    yaml = """\
on: push
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: git config --global url."https://x-access-token:${TOKEN}@github.com/".insteadOf "https://github.com/"
      - run: echo step1
      - run: echo step2
      - run: echo step3
      - run: echo step4
      - run: echo step5
      - run: echo step6
      - run: git push origin main
"""
    findings = CredentialWindow().check(_wf("ci.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].message is not None
    assert "steps before push" in findings[0].message


def test_credential_window_no_flag_small_gap() -> None:
    """git config then push within the allowed window is not flagged."""
    yaml = """\
on: push
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: git config --global url."https://x-access-token:${TOKEN}@github.com/".insteadOf "https://github.com/"
      - run: echo build
      - run: git push origin main
"""
    findings = CredentialWindow().check(_wf("ci.yml", yaml))
    assert findings == []


def test_credential_window_no_flag_without_push() -> None:
    """git config with no push step in the job is not flagged."""
    yaml = """\
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: git config --global url."https://x-access-token:${TOKEN}@github.com/".insteadOf "https://github.com/"
      - run: echo done
"""
    findings = CredentialWindow().check(_wf("ci.yml", yaml))
    assert findings == []


def test_credential_window_no_flag_without_git_config() -> None:
    """A push with no git-config credential step is not flagged."""
    yaml = """\
on: push
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - run: echo step1
      - run: git push origin main
"""
    findings = CredentialWindow().check(_wf("ci.yml", yaml))
    assert findings == []


def test_credential_window_flags_first_cred_step_not_last() -> None:
    """The gap is measured from the FIRST credential step, so an early one flags."""
    yaml = """\
on: push
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: git config --global url."https://x-access-token:t1@github.com/".insteadOf "https://github.com/"
      - run: echo step1
      - run: echo step2
      - run: echo step3
      - run: echo step4
      - run: echo step5
      - run: echo step6
      - run: git config --global url."https://x-access-token:t2@github.com/".insteadOf "https://github.com/"
      - run: git push origin main
"""
    findings = CredentialWindow().check(_wf("ci.yml", yaml))
    assert len(findings) == 1
    assert findings[0].message is not None
    assert "steps before push" in findings[0].message


def test_credential_window_rule_name() -> None:
    """The rule exposes the expected name."""
    assert CredentialWindow().name == "credential-window"


# --- missing-persist-credentials --------------------------------------------


def test_missing_persist_flags_checkout_without_persist_credentials() -> None:
    """A bare actions/checkout (no persist-credentials) is flagged high."""
    yaml = """\
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""
    findings = MissingPersistCreds().check(_wf("ci.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert findings[0].message is not None
    assert "persist-credentials" in findings[0].message


def test_missing_persist_no_flag_with_persist_credentials_false() -> None:
    """checkout with persist-credentials: false is not flagged."""
    yaml = """\
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
"""
    findings = MissingPersistCreds().check(_wf("ci.yml", yaml))
    assert findings == []


def test_missing_persist_no_flag_when_job_does_git_push() -> None:
    """A pushing job with implicit persist still flags (must be explicit)."""
    yaml = """\
on: push
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: git push origin main
"""
    findings = MissingPersistCreds().check(_wf("ci.yml", yaml))
    assert len(findings) == 1


def test_missing_persist_no_flag_when_job_pushes_with_explicit_true() -> None:
    """A pushing job with persist-credentials: true is not flagged."""
    yaml = """\
on: push
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: true
      - run: git push origin main
"""
    findings = MissingPersistCreds().check(_wf("ci.yml", yaml))
    assert findings == []


def test_missing_persist_flags_multiple_checkouts() -> None:
    """Two bare checkout steps yield two findings."""
    yaml = """\
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/checkout@v4
"""
    findings = MissingPersistCreds().check(_wf("ci.yml", yaml))
    assert len(findings) == 2


def test_missing_persist_no_flag_for_non_actions_checkout() -> None:
    """A third-party checkout-like action is not flagged."""
    yaml = """\
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: some-org/checkout-helper@v1
"""
    findings = MissingPersistCreds().check(_wf("ci.yml", yaml))
    assert findings == []


def test_missing_persist_rule_name() -> None:
    """The rule exposes the expected name."""
    assert MissingPersistCreds().name == "missing-persist-credentials"


# --- unscoped-app-token -----------------------------------------------------


def test_unscoped_app_token_flags_token_without_permissions() -> None:
    """create-github-app-token without any permission-* input is flagged medium."""
    yaml = """\
on: push
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/create-github-app-token@v1
        with:
          app-id: ${{ vars.APP_ID }}
          private-key: ${{ secrets.APP_KEY }}
"""
    findings = UnscopedAppToken().check(_wf("release.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].rule == "unscoped-app-token"


def test_unscoped_app_token_safe_with_permission_contents() -> None:
    """A single permission-contents input scopes the token (not flagged)."""
    yaml = """\
on: push
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/create-github-app-token@v1
        with:
          app-id: ${{ vars.APP_ID }}
          private-key: ${{ secrets.APP_KEY }}
          permission-contents: write
"""
    findings = UnscopedAppToken().check(_wf("release.yml", yaml))
    assert findings == []


def test_unscoped_app_token_safe_with_multiple_permissions() -> None:
    """Multiple permission-* inputs scope the token (not flagged)."""
    yaml = """\
on: push
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/create-github-app-token@v1
        with:
          app-id: ${{ vars.APP_ID }}
          private-key: ${{ secrets.APP_KEY }}
          permission-contents: write
          permission-pull-requests: read
"""
    findings = UnscopedAppToken().check(_wf("release.yml", yaml))
    assert findings == []


def test_unscoped_app_token_flags_even_when_sha_pinned() -> None:
    """A SHA-pinned app-token action without scoping is still flagged medium."""
    yaml = """\
on: push
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/create-github-app-token@a0de51f8db146e4c6353ead8c66a8a5e4d1373ff
        with:
          app-id: ${{ vars.APP_ID }}
          private-key: ${{ secrets.APP_KEY }}
"""
    findings = UnscopedAppToken().check(_wf("release.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "medium"


# --- docker-build-arg-secrets -----------------------------------------------


def test_docker_build_arg_flags_secrets_in_build_args() -> None:
    """A secrets.* reference inside build-args is flagged medium."""
    yaml = """\
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: docker/build-push-action@v5
        with:
          build-args: |
            NPM_TOKEN=${{ secrets.NPM_TOKEN }}
"""
    findings = DockerBuildArgSecrets().check(_wf("docker.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "medium"
    assert findings[0].rule == "docker-build-arg-secrets"


def test_docker_build_arg_safe_when_build_args_has_no_secrets() -> None:
    """build-args with only literal values is not flagged."""
    yaml = """\
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: docker/build-push-action@v5
        with:
          build-args: |
            NODE_ENV=production
            APP_VERSION=1.0.0
"""
    findings = DockerBuildArgSecrets().check(_wf("docker.yml", yaml))
    assert findings == []


def test_docker_build_arg_handles_multiline_build_args() -> None:
    """A secret on a middle line of a multi-line build-args block is flagged."""
    yaml = """\
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: docker/build-push-action@v5
        with:
          build-args: |
            NODE_ENV=production
            API_KEY=${{ secrets.API_KEY }}
            APP_VERSION=1.0.0
"""
    findings = DockerBuildArgSecrets().check(_wf("docker.yml", yaml))
    assert len(findings) == 1
    assert findings[0].code is not None
    assert "secrets." in findings[0].code


def test_docker_build_arg_safe_when_secrets_in_docker_secrets_input() -> None:
    """A secret in the docker secrets: input (not build-args) is not flagged."""
    yaml = """\
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: docker/build-push-action@v5
        with:
          secrets: |
            NPM_TOKEN=${{ secrets.NPM_TOKEN }}
          build-args: |
            NODE_ENV=production
"""
    findings = DockerBuildArgSecrets().check(_wf("docker.yml", yaml))
    assert findings == []


def test_docker_build_arg_does_not_flag_non_secret_build_args() -> None:
    """build-args referencing github.* (not secrets.) is not flagged."""
    yaml = """\
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: docker/build-push-action@v5
        with:
          build-args: |
            COMMIT_SHA=${{ github.sha }}
            BRANCH=${{ github.ref_name }}
"""
    findings = DockerBuildArgSecrets().check(_wf("docker.yml", yaml))
    assert findings == []
