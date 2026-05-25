r"""Tests for Sentinel batch-F rules (lockfile / lifecycle / misc).

Ports test/rules/test_missing_frozen_lockfile.rb, test_dangerous_lifecycle_scripts.rb,
test_git_config_global.rb, test_ide_config_injection.rb, and
test_jq_arg_escape.rb. No mocks: each test builds a real Workflow from
inline YAML, runs the rule, and asserts on the findings.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from sentinel.rules.dangerous_lifecycle_scripts import DangerousLifecycleScripts
from sentinel.rules.git_config_global import GitConfigGlobal
from sentinel.rules.ide_config_injection import IdeConfigInjection
from sentinel.rules.jq_arg_escape import JqArgEscape
from sentinel.rules.missing_frozen_lockfile import MissingFrozenLockfile
from sentinel.workflow import Workflow

# --------------------------------------------------------------------------
# missing-frozen-lockfile
# --------------------------------------------------------------------------


def _lockfile_wf(run_line: str) -> Workflow:
    """Build a one-step workflow whose run: is the given install command."""
    yaml = f"on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Install\n        run: {run_line}\n"
    return Workflow("ci.yml", yaml)


def test_missing_frozen_lockfile_rule_name() -> None:
    """Rule exposes the canonical name 'missing-frozen-lockfile'."""
    assert MissingFrozenLockfile().name == "missing-frozen-lockfile"


def test_missing_frozen_lockfile_rule_severity() -> None:
    """Rule severity is medium."""
    assert MissingFrozenLockfile().severity == "medium"


def test_missing_frozen_lockfile_rule_description() -> None:
    """Description matches the Ruby string exactly."""
    assert MissingFrozenLockfile().description == "Package install without lockfile enforcement"


def test_missing_frozen_lockfile_flags_npm_install() -> None:
    """npm install (no lockfile flag) is flagged once."""
    findings = MissingFrozenLockfile().check(_lockfile_wf("npm install"))
    assert len(findings) == 1
    assert findings[0].message is not None and re.search(r"npm install", findings[0].message)


def test_missing_frozen_lockfile_safe_npm_ci() -> None:
    """npm ci produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("npm ci")) == []


def test_missing_frozen_lockfile_safe_npm_install_ci_flag() -> None:
    """npm install --ci produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("npm install --ci")) == []


def test_missing_frozen_lockfile_flags_pnpm_install() -> None:
    """pnpm install (no frozen flag) is flagged once."""
    findings = MissingFrozenLockfile().check(_lockfile_wf("pnpm install"))
    assert len(findings) == 1
    assert findings[0].message is not None and re.search(r"pnpm install", findings[0].message)


def test_missing_frozen_lockfile_safe_pnpm_frozen_lockfile() -> None:
    """pnpm install --frozen-lockfile produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("pnpm install --frozen-lockfile")) == []


def test_missing_frozen_lockfile_flags_yarn_install() -> None:
    """yarn install (no frozen flag) is flagged once."""
    findings = MissingFrozenLockfile().check(_lockfile_wf("yarn install"))
    assert len(findings) == 1
    assert findings[0].message is not None and re.search(r"yarn install", findings[0].message)


def test_missing_frozen_lockfile_safe_yarn_frozen_lockfile() -> None:
    """yarn install --frozen-lockfile produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("yarn install --frozen-lockfile")) == []


def test_missing_frozen_lockfile_safe_yarn_immutable() -> None:
    """yarn install --immutable produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("yarn install --immutable")) == []


def test_missing_frozen_lockfile_flags_bun_install() -> None:
    """bun install (no frozen flag) is flagged once."""
    findings = MissingFrozenLockfile().check(_lockfile_wf("bun install"))
    assert len(findings) == 1
    assert findings[0].message is not None and re.search(r"bun install", findings[0].message)


def test_missing_frozen_lockfile_safe_bun_frozen_lockfile() -> None:
    """bun install --frozen-lockfile produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("bun install --frozen-lockfile")) == []


def test_missing_frozen_lockfile_flags_pip_install_package() -> None:
    """pip install with package names is flagged once."""
    findings = MissingFrozenLockfile().check(_lockfile_wf("pip install requests flask"))
    assert len(findings) == 1
    assert findings[0].message is not None and re.search(r"pip install", findings[0].message)


def test_missing_frozen_lockfile_flags_pip3_install_package() -> None:
    """pip3 install with a package name is flagged once."""
    assert len(MissingFrozenLockfile().check(_lockfile_wf("pip3 install requests"))) == 1


def test_missing_frozen_lockfile_safe_pip_requirements_file() -> None:
    """pip install -r requirements.txt produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("pip install -r requirements.txt")) == []


def test_missing_frozen_lockfile_safe_pip_requirement_long_flag() -> None:
    """pip install --requirement produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("pip install --requirement requirements.txt")) == []


def test_missing_frozen_lockfile_safe_pip_constraint() -> None:
    """pip install --constraint produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("pip install --constraint constraints.txt requests")) == []


def test_missing_frozen_lockfile_safe_pip_local_dot() -> None:
    """pip install . (local) produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("pip install .")) == []


def test_missing_frozen_lockfile_safe_pip_local_editable() -> None:
    """pip install -e . (editable local) produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("pip install -e .")) == []


def test_missing_frozen_lockfile_safe_pip_local_dot_with_extras() -> None:
    """pip install .[dev] (local with extras) produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("pip install .[dev]")) == []


def test_missing_frozen_lockfile_flags_uv_pip_install_package() -> None:
    """uv pip install with a package name is flagged once."""
    findings = MissingFrozenLockfile().check(_lockfile_wf("uv pip install requests"))
    assert len(findings) == 1
    assert findings[0].message is not None and re.search(r"pip install", findings[0].message)


def test_missing_frozen_lockfile_safe_uv_pip_requirements() -> None:
    """uv pip install -r requirements.txt produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("uv pip install -r requirements.txt")) == []


def test_missing_frozen_lockfile_flags_bundle_install() -> None:
    """bundle install (no frozen flag) is flagged once."""
    findings = MissingFrozenLockfile().check(_lockfile_wf("bundle install"))
    assert len(findings) == 1
    assert findings[0].message is not None and re.search(r"bundle install", findings[0].message)


def test_missing_frozen_lockfile_flags_bare_bundle() -> None:
    """A bare 'bundle' command is flagged once."""
    assert len(MissingFrozenLockfile().check(_lockfile_wf("bundle"))) == 1


def test_missing_frozen_lockfile_safe_bundle_frozen() -> None:
    """bundle install --frozen produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("bundle install --frozen")) == []


def test_missing_frozen_lockfile_safe_bundle_deployment() -> None:
    """bundle install --deployment produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("bundle install --deployment")) == []


def test_missing_frozen_lockfile_safe_bundle_frozen_env() -> None:
    """BUNDLE_FROZEN=true bundle install produces no finding."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Install\n        run: BUNDLE_FROZEN=true bundle install\n"
    assert MissingFrozenLockfile().check(Workflow("ci.yml", yaml)) == []


def test_missing_frozen_lockfile_no_flag_bundle_exec() -> None:
    """bundle exec rspec produces no finding (skipped subcommand)."""
    assert MissingFrozenLockfile().check(_lockfile_wf("bundle exec rspec")) == []


def test_missing_frozen_lockfile_flags_go_get() -> None:
    """go get ./... is flagged once."""
    findings = MissingFrozenLockfile().check(_lockfile_wf("go get ./..."))
    assert len(findings) == 1
    assert findings[0].message is not None and re.search(r"go get", findings[0].message)


def test_missing_frozen_lockfile_no_flag_go_mod_download() -> None:
    """go mod download produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("go mod download")) == []


def test_missing_frozen_lockfile_flags_cargo_install() -> None:
    """cargo install (no --locked) is flagged once."""
    findings = MissingFrozenLockfile().check(_lockfile_wf("cargo install cargo-audit"))
    assert len(findings) == 1
    assert findings[0].message is not None and re.search(r"cargo install", findings[0].message)


def test_missing_frozen_lockfile_safe_cargo_install_locked() -> None:
    """cargo install --locked produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("cargo install --locked cargo-audit")) == []


def test_missing_frozen_lockfile_no_flag_cargo_build() -> None:
    """cargo build --release produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("cargo build --release")) == []


def test_missing_frozen_lockfile_flags_composer_update() -> None:
    """composer update is flagged once."""
    findings = MissingFrozenLockfile().check(_lockfile_wf("composer update"))
    assert len(findings) == 1
    assert findings[0].message is not None and re.search(r"composer update", findings[0].message)


def test_missing_frozen_lockfile_no_flag_composer_install() -> None:
    """composer install produces no finding."""
    assert MissingFrozenLockfile().check(_lockfile_wf("composer install")) == []


def test_missing_frozen_lockfile_skips_comments() -> None:
    """A commented-out npm install inside a run block is not flagged."""
    yaml = 'on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Install\n        run: |\n          # npm install\n          echo "skipped"\n'
    assert MissingFrozenLockfile().check(Workflow("ci.yml", yaml)) == []


def test_missing_frozen_lockfile_npm_fix_message() -> None:
    """The npm fix recommends npm ci."""
    findings = MissingFrozenLockfile().check(_lockfile_wf("npm install"))
    assert findings[0].fix is not None and re.search(r"npm ci", findings[0].fix)


def test_missing_frozen_lockfile_yarn_fix_message() -> None:
    """The yarn fix mentions both frozen-lockfile and immutable."""
    findings = MissingFrozenLockfile().check(_lockfile_wf("yarn install"))
    assert findings[0].fix is not None and re.search(r"frozen-lockfile.*immutable|immutable.*frozen-lockfile", findings[0].fix)


def test_missing_frozen_lockfile_go_get_fix_message() -> None:
    """The go get fix recommends go mod download."""
    findings = MissingFrozenLockfile().check(_lockfile_wf("go get ./..."))
    assert findings[0].fix is not None and re.search(r"go mod download", findings[0].fix)


def test_missing_frozen_lockfile_composer_update_fix_message() -> None:
    """The composer fix recommends composer install."""
    findings = MissingFrozenLockfile().check(_lockfile_wf("composer update"))
    assert findings[0].fix is not None and re.search(r"composer install", findings[0].fix)


# --------------------------------------------------------------------------
# dangerous-lifecycle-scripts
# --------------------------------------------------------------------------


def _lifecycle_wf_with_secrets(run_line: str) -> Workflow:
    """Build a workflow whose first step runs run_line and a later step uses a secret."""
    yaml = f"on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Install\n        run: {run_line}\n      - name: Publish\n        run: npm publish\n        env:\n          NPM_TOKEN: ${{{{ secrets.NPM_TOKEN }}}}\n"
    return Workflow("ci.yml", yaml)


def _lifecycle_wf_no_secrets(run_line: str) -> Workflow:
    """Build a workflow whose first step runs run_line and no secrets appear."""
    yaml = f"on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Install\n        run: {run_line}\n      - run: npm test\n"
    return Workflow("ci.yml", yaml)


def test_dangerous_lifecycle_scripts_rule_name() -> None:
    """Rule exposes the canonical name 'dangerous-lifecycle-scripts'."""
    assert DangerousLifecycleScripts().name == "dangerous-lifecycle-scripts"


def test_dangerous_lifecycle_scripts_rule_severity() -> None:
    """Rule severity is medium."""
    assert DangerousLifecycleScripts().severity == "medium"


def test_dangerous_lifecycle_scripts_flags_npm_install_with_secrets() -> None:
    """npm install with secrets present is flagged."""
    findings = DangerousLifecycleScripts().check(_lifecycle_wf_with_secrets("npm install"))
    assert any(f.message is not None and "npm" in f.message for f in findings)


def test_dangerous_lifecycle_scripts_no_findings_without_secrets() -> None:
    """npm install without any secrets produces no finding."""
    assert DangerousLifecycleScripts().check(_lifecycle_wf_no_secrets("npm install")) == []


def test_dangerous_lifecycle_scripts_flags_npm_ci_with_secrets() -> None:
    """npm ci with secrets present is flagged."""
    findings = DangerousLifecycleScripts().check(_lifecycle_wf_with_secrets("npm ci"))
    assert any(f.message is not None and "npm" in f.message for f in findings)


def test_dangerous_lifecycle_scripts_flags_pnpm_install_with_secrets() -> None:
    """pnpm install with secrets present is flagged."""
    findings = DangerousLifecycleScripts().check(_lifecycle_wf_with_secrets("pnpm install"))
    assert any(f.message is not None and "pnpm" in f.message for f in findings)


def test_dangerous_lifecycle_scripts_flags_yarn_install_with_secrets() -> None:
    """yarn install with secrets present is flagged."""
    findings = DangerousLifecycleScripts().check(_lifecycle_wf_with_secrets("yarn install"))
    assert any(f.message is not None and "yarn" in f.message for f in findings)


def test_dangerous_lifecycle_scripts_flags_bun_install_with_secrets() -> None:
    """bun install with secrets present is flagged."""
    findings = DangerousLifecycleScripts().check(_lifecycle_wf_with_secrets("bun install"))
    assert any(f.message is not None and "bun" in f.message for f in findings)


def test_dangerous_lifecycle_scripts_safe_npm_ci_ignore_scripts() -> None:
    """npm ci --ignore-scripts produces no finding even with secrets."""
    assert DangerousLifecycleScripts().check(_lifecycle_wf_with_secrets("npm ci --ignore-scripts")) == []


def test_dangerous_lifecycle_scripts_safe_pnpm_ignore_scripts() -> None:
    """pnpm install --ignore-scripts produces no finding even with secrets."""
    assert DangerousLifecycleScripts().check(_lifecycle_wf_with_secrets("pnpm install --ignore-scripts")) == []


def test_dangerous_lifecycle_scripts_safe_bun_no_scripts() -> None:
    """bun install --no-scripts produces no finding even with secrets."""
    assert DangerousLifecycleScripts().check(_lifecycle_wf_with_secrets("bun install --no-scripts")) == []


def test_dangerous_lifecycle_scripts_skips_comments() -> None:
    """A commented-out npm install is not flagged, even with secrets present."""
    yaml = 'on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Install\n        run: |\n          # npm install\n          echo "skipped"\n      - run: npm publish\n        env:\n          NPM_TOKEN: ${{ secrets.NPM_TOKEN }}\n'
    assert DangerousLifecycleScripts().check(Workflow("ci.yml", yaml)) == []


def test_dangerous_lifecycle_scripts_fix_includes_ignore_scripts() -> None:
    """The fix recommends --ignore-scripts."""
    findings = DangerousLifecycleScripts().check(_lifecycle_wf_with_secrets("npm install"))
    assert any(f.fix is not None and "--ignore-scripts" in f.fix for f in findings)


# --------------------------------------------------------------------------
# git-config-global
# --------------------------------------------------------------------------


def test_git_config_global_flags_global_insteadof() -> None:
    """git config --global with insteadOf is flagged at low severity."""
    yaml = 'on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: git config --global url."https://x-token:${TOKEN}@github.com/".insteadOf "https://github.com/"\n'
    findings = GitConfigGlobal().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1
    assert findings[0].severity == "low"
    assert findings[0].message is not None and re.search(r"--global", findings[0].message)


def test_git_config_global_flags_global_credential() -> None:
    """git config --global credential.helper is flagged and code mentions credential."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: git config --global credential.helper store\n"
    findings = GitConfigGlobal().check(Workflow("ci.yml", yaml))
    assert len(findings) == 1
    assert findings[0].code is not None and re.search(r"credential", findings[0].code)


def test_git_config_global_safe_with_local_config() -> None:
    """git config --local insteadOf produces no finding."""
    yaml = 'on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: git config --local url."https://x-token:${TOKEN}@github.com/".insteadOf "https://github.com/"\n'
    assert GitConfigGlobal().check(Workflow("ci.yml", yaml)) == []


def test_git_config_global_safe_global_user_name() -> None:
    """git config --global user.name produces no finding."""
    yaml = 'on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - run: git config --global user.name "CI Bot"\n'
    assert GitConfigGlobal().check(Workflow("ci.yml", yaml)) == []


def test_git_config_global_rule_name() -> None:
    """Rule exposes the canonical name 'git-config-global'."""
    assert GitConfigGlobal().name == "git-config-global"


# --------------------------------------------------------------------------
# ide-config-injection
# --------------------------------------------------------------------------


def _ide_wf(run_line: str) -> Workflow:
    """Build a one-step workflow whose run: is the given command line."""
    yaml = f"on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Setup\n        run: {run_line}\n"
    return Workflow("ci.yml", yaml)


def test_ide_config_injection_rule_name() -> None:
    """Rule exposes the canonical name 'ide-config-injection'."""
    assert IdeConfigInjection().name == "ide-config-injection"


def test_ide_config_injection_rule_severity() -> None:
    """Rule severity is critical."""
    assert IdeConfigInjection().severity == "critical"


def test_ide_config_injection_rule_description() -> None:
    """Description mentions IDE config."""
    assert re.search(r"IDE.*config", IdeConfigInjection().description)


def test_ide_config_injection_flags_echo_to_claude_settings() -> None:
    """echo redirect to .claude/settings.json is flagged once."""
    findings = IdeConfigInjection().check(_ide_wf("echo '{}' > .claude/settings.json"))
    assert len(findings) == 1
    assert findings[0].message is not None and re.search(r"IDE.*config", findings[0].message)


def test_ide_config_injection_flags_tee_to_vscode_tasks() -> None:
    """tee to .vscode/tasks.json is flagged once."""
    findings = IdeConfigInjection().check(_ide_wf("tee .vscode/tasks.json"))
    assert len(findings) == 1
    assert findings[0].message is not None and re.search(r"IDE.*config", findings[0].message)


def test_ide_config_injection_flags_cat_to_cursor_config() -> None:
    """cat redirect to .cursor/settings.json is flagged once."""
    assert len(IdeConfigInjection().check(_ide_wf("cat payload.json > .cursor/settings.json"))) == 1


def test_ide_config_injection_flags_printf_to_claude_commands() -> None:
    """printf redirect to .claude/commands/run.md is flagged once."""
    assert len(IdeConfigInjection().check(_ide_wf("printf '%s' cmd > .claude/commands/run.md"))) == 1


def test_ide_config_injection_safe_normal_echo() -> None:
    """A plain echo produces no finding."""
    assert IdeConfigInjection().check(_ide_wf("echo 'hello world'")) == []


def test_ide_config_injection_safe_comment_line() -> None:
    """A commented-out IDE write inside a run block is not flagged."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Setup\n        run: |\n          # echo '{}' > .claude/settings.json\n          echo \"skipped\"\n"
    assert IdeConfigInjection().check(Workflow("ci.yml", yaml)) == []


def test_ide_config_injection_safe_echo_to_other_path() -> None:
    """An echo redirect to a non-IDE path produces no finding."""
    assert IdeConfigInjection().check(_ide_wf("echo 'data' > config/settings.json")) == []


def test_ide_config_injection_fix_message() -> None:
    """The fix recommends removing IDE config writes."""
    findings = IdeConfigInjection().check(_ide_wf("echo '{}' > .claude/settings.json"))
    assert findings[0].fix is not None and re.search(r"Remove IDE config", findings[0].fix)


# --------------------------------------------------------------------------
# jq-arg-escape-sequences
# --------------------------------------------------------------------------


def test_jq_arg_escape_flags_newline_escape() -> None:
    r"""jq --arg with a \n escape is flagged once."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Build JSON\n        run: jq -n --arg msg \"hello\\nworld\" '{msg: $msg}'\n"
    assert len(JqArgEscape().check(Workflow("ci.yml", yaml))) == 1


def test_jq_arg_escape_flags_tab_escape() -> None:
    r"""jq --arg with a \t escape is flagged once."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Build JSON\n        run: jq -n --arg msg \"col1\\tcol2\" '{msg: $msg}'\n"
    assert len(JqArgEscape().check(Workflow("ci.yml", yaml))) == 1


def test_jq_arg_escape_flags_backslash_escape() -> None:
    r"""jq --arg with a \\ escape is flagged once."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Build JSON\n        run: jq -n --arg path \"C:\\\\Users\" '{path: $path}'\n"
    assert len(JqArgEscape().check(Workflow("ci.yml", yaml))) == 1


def test_jq_arg_escape_no_flag_for_variable_reference() -> None:
    """jq --arg with a $VAR reference produces no finding."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Build JSON\n        run: jq -n --arg name \"$VAR\" '{name: $name}'\n"
    assert JqArgEscape().check(Workflow("ci.yml", yaml)) == []


def test_jq_arg_escape_no_flag_for_plain_text() -> None:
    """jq --arg with plain text produces no finding."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Build JSON\n        run: jq -n --arg name \"plain text\" '{name: $name}'\n"
    assert JqArgEscape().check(Workflow("ci.yml", yaml)) == []


def test_jq_arg_escape_flags_with_multiple_jq_flags_before_arg() -> None:
    r"""jq with multiple flags before --arg and a \n escape is flagged once."""
    yaml = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Build JSON\n        run: jq -nc --arg msg \"hello\\nworld\" '{msg: $msg}'\n"
    assert len(JqArgEscape().check(Workflow("ci.yml", yaml))) == 1


def test_jq_arg_escape_skips_commented_out_lines() -> None:
    r"""A commented-out jq --arg \n line inside a run block is not flagged."""
    yaml = 'on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Build JSON\n        run: |\n          # jq -n --arg msg "hello\\nworld" \'{msg: $msg}\'\n          echo "done"\n'
    assert JqArgEscape().check(Workflow("ci.yml", yaml)) == []


def test_jq_arg_escape_no_flag_for_shell_escaped_quotes() -> None:
    r"""jq --arg with shell-escaped quotes (no \n/\t/\\) produces no finding."""
    yaml = 'on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - name: Build JSON\n        run: jq -n --arg msg "say \\"hello\\"" \'{msg: $msg}\'\n'
    assert JqArgEscape().check(Workflow("ci.yml", yaml)) == []


def test_jq_arg_escape_rule_name() -> None:
    """Rule exposes the canonical name 'jq-arg-escape-sequences'."""
    assert JqArgEscape().name == "jq-arg-escape-sequences"


def test_jq_arg_escape_severity_is_medium() -> None:
    """Rule severity is medium."""
    assert JqArgEscape().severity == "medium"
