"""
Regression tests for the `{plugin-name}--v{version}` RESOLVER TAG in publish.py
(ai-maestro#28 / TRDD-JT3U4ZVM).

Why this file exists: since Claude Code 2.1.110 a version-constrained plugin
dependency resolves ONLY against tags named `{plugin-name}--v{version}`. A repo
whose releases carry only `v{version}` looks, to the resolver, like a repo with
no tags at all — every constrained dependency on it fails with "no git tag
satisfying <range>". That exact gap grounded the whole ai-maestro fleet for a
day, so it gets real tests rather than a code comment.

No mocks. Every case runs against a REAL git repo and a REAL plugin.json on
disk. The dry-run path returns BEFORE publish.py's gh-auth precheck, so the full
tag contract (which tags get built, and that they ship in ONE atomic push) is
exercised for real with no network and no GitHub account.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import publish  # scripts/ is on sys.path via conftest

PLUGIN_NAME = "ai-maestro-maintainer-agent"
VERSION = "9.9.9"


def _write_manifest(repo: Path, data: dict | None) -> None:
    """Write .claude-plugin/plugin.json (or omit it entirely when data is None)."""
    if data is None:
        return
    d = repo / ".claude-plugin"
    d.mkdir(parents=True, exist_ok=True)
    (d / "plugin.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


@pytest.fixture
def plugin_repo(tmp_git_repo: Path) -> Path:
    """A real git repo carrying a real, well-formed plugin.json."""
    _write_manifest(tmp_git_repo, {"name": PLUGIN_NAME, "version": VERSION})
    return tmp_git_repo


# ─────────────────────────── get_plugin_name ───────────────────────────


def test_get_plugin_name_reads_the_name_from_the_manifest(plugin_repo: Path) -> None:
    """get_plugin_name returns the `name` field of .claude-plugin/plugin.json."""
    assert publish.get_plugin_name(plugin_repo) == PLUGIN_NAME


def test_get_plugin_name_exits_when_the_manifest_has_no_name(tmp_git_repo: Path) -> None:
    """A manifest without `name` HARD-FAILS — never a guessed or defaulted tag name."""
    _write_manifest(tmp_git_repo, {"version": VERSION})  # no "name"
    with pytest.raises(SystemExit) as e:
        publish.get_plugin_name(tmp_git_repo)
    assert e.value.code == 1


def test_get_plugin_name_exits_when_the_manifest_is_absent(tmp_git_repo: Path) -> None:
    """A missing plugin.json HARD-FAILS rather than silently producing a bad tag."""
    with pytest.raises(SystemExit) as e:
        publish.get_plugin_name(tmp_git_repo)
    assert e.value.code == 1


def test_get_plugin_name_exits_on_a_blank_name(tmp_git_repo: Path) -> None:
    """A whitespace-only `name` is treated as absent — it would build the tag `--v9.9.9`."""
    _write_manifest(tmp_git_repo, {"name": "   ", "version": VERSION})
    with pytest.raises(SystemExit) as e:
        publish.get_plugin_name(tmp_git_repo)
    assert e.value.code == 1


def test_resolver_tag_uses_the_manifest_name_not_the_directory_name(tmp_git_repo: Path) -> None:
    """The tag is derived from the MANIFEST, not the checkout's folder name.

    The resolver filters on the plugin's declared name; a tag built from whatever
    the user happened to call their clone directory would never match.
    """
    _write_manifest(tmp_git_repo, {"name": "declared-name", "version": VERSION})
    assert publish.get_plugin_name(tmp_git_repo) == "declared-name"
    assert publish.get_plugin_name(tmp_git_repo) != tmp_git_repo.name


# ─────────────────── the tag contract, via the real dry-run ───────────────────


def test_dry_run_announces_both_the_release_tag_and_the_resolver_tag(
    plugin_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Dry-run plans BOTH tags: v{version} AND {plugin-name}--v{version}."""
    publish.stage_commit_and_push(plugin_repo, VERSION, dry_run=True)
    out = capsys.readouterr().out
    assert f"v{VERSION}" in out
    assert f"{PLUGIN_NAME}--v{VERSION}" in out


def test_the_release_v_tag_is_still_emitted(
    plugin_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The plain v{version} tag must SURVIVE — Releases and the marketplace notify chain read it.

    Guards the obvious wrong fix: replacing the release tag with the resolver tag
    instead of shipping both.
    """
    publish.stage_commit_and_push(plugin_repo, VERSION, dry_run=True)
    out = capsys.readouterr().out
    assert f"Would tag: v{VERSION}" in out


def test_dry_run_pushes_both_tags_in_a_single_atomic_transaction(
    plugin_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both tags ride ONE atomic push, so a release can never land half-tagged.

    A commit carrying one tag but not the other is precisely the state that makes
    the resolver failure hard to diagnose — the repo looks released, but no
    constrained dependency can resolve it.
    """
    publish.stage_commit_and_push(plugin_repo, VERSION, dry_run=True)
    out = capsys.readouterr().out
    push_lines = [ln for ln in out.splitlines() if "Would push (atomic)" in ln]
    assert len(push_lines) == 1, f"expected exactly ONE atomic push, got: {push_lines}"
    assert f"v{VERSION}" in push_lines[0]
    assert f"{PLUGIN_NAME}--v{VERSION}" in push_lines[0]


def test_dry_run_skips_a_resolver_tag_that_already_exists_locally(
    plugin_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Tag creation is idempotent — an interrupted publish must be resumable.

    A real git tag is created first, then dry-run must report it as skipped rather
    than planning to recreate it (which would abort the real run).
    """
    resolver_tag = f"{PLUGIN_NAME}--v{VERSION}"
    subprocess.run(
        ["git", "tag", "-a", resolver_tag, "-m", f"Release {resolver_tag}"],
        cwd=plugin_repo, check=True,
    )
    publish.stage_commit_and_push(plugin_repo, VERSION, dry_run=True)
    out = capsys.readouterr().out
    assert f"Would skip tag (already exists locally): {resolver_tag}" in out


def test_a_manifest_without_a_name_aborts_the_push_stage(tmp_git_repo: Path) -> None:
    """stage_commit_and_push itself aborts on a nameless manifest — the guard is wired in.

    Proves the fail-fast is reached from the real call site, not just when
    get_plugin_name is called directly in isolation.
    """
    _write_manifest(tmp_git_repo, {"version": VERSION})  # no "name"
    with pytest.raises(SystemExit) as e:
        publish.stage_commit_and_push(tmp_git_repo, VERSION, dry_run=True)
    assert e.value.code == 1
