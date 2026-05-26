"""Sandbox-harness tests.

Unit tests run in milliseconds and need only Python + filesystem.
Integration tests (marked with 🐌 in their docstring + a docker_available()
skip) start real Docker containers labelled aimm-sandbox=true and verify
the harness's safety invariants (mount mode, network isolation, orphan
reap on exit).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from sandbox import sandbox as sb

# -- helpers ------------------------------------------------------------------


def _docker_available() -> bool:
    """True iff `docker version` returns a server version string."""
    if shutil.which("docker") is None:
        return False
    out = subprocess.run(
        ["docker", "version", "--format", "{{.Server.Version}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return out.returncode == 0 and bool(out.stdout.strip())


def _image_present(tag: str) -> bool:
    """True iff `docker image ls <tag>` finds the tag locally."""
    out = subprocess.run(
        ["docker", "image", "ls", "--format", "{{.Repository}}:{{.Tag}}", tag],
        capture_output=True,
        text=True,
        check=False,
    )
    return out.returncode == 0 and tag in out.stdout


def _count_sandbox_containers() -> int:
    """Number of aimm-sandbox containers visible to docker (all states)."""
    out = subprocess.run(
        ["docker", "ps", "-aq", "--filter", "label=aimm-sandbox=true"],
        capture_output=True,
        text=True,
        check=False,
    )
    return len([line for line in out.stdout.split() if line.strip()])


needs_docker = pytest.mark.skipif(
    not _docker_available(), reason="docker server not reachable"
)
needs_node_baseline = pytest.mark.skipif(
    not (_docker_available() and _image_present("aimm-sandbox:node-baseline")),
    reason="aimm-sandbox:node-baseline image not built (run `sandbox.py build-images`)",
)


# -- unit tests (no Docker) ---------------------------------------------------


def test_expected_image_tags_matches_dockerfiles():
    """_expected_image_tags() derives one aimm-sandbox:<stem> per Dockerfile."""
    tags = sb._expected_image_tags()
    df_stems = sorted(p.stem for p in sb.DOCKERFILES_DIR.glob("*.Dockerfile"))
    assert tags == [f"{sb.IMAGE_PREFIX}:{s}" for s in df_stems]


def test_expected_image_tags_includes_baselines():
    """The shipped dockerfile set always includes node-baseline + python-baseline."""
    tags = set(sb._expected_image_tags())
    assert "aimm-sandbox:node-baseline" in tags
    assert "aimm-sandbox:python-baseline" in tags


def test_clone_rejects_bad_slug(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    """cmd_clone refuses anything that is not owner/repo and exits non-zero."""
    ns = argparse.Namespace(repo="not-a-slug", ref=None, depth=1, dest=str(tmp_path / "x"))
    assert sb.cmd_clone(ns) == 1
    err = capsys.readouterr().err
    assert "invalid repo slug" in err


def test_run_rejects_bad_network():
    """_do_run validates the network arg before touching docker."""
    with pytest.raises(ValueError, match="network must be"):
        sb._do_run(
            image="aimm-sandbox:node-baseline",
            project_dir=Path("/tmp"),  # NOTE: not used because validation happens first... but project_dir is required
            cmd="echo hi",
            network="hijack",
        )


def test_run_rejects_missing_project_dir(tmp_path: Path):
    """_do_run raises FileNotFoundError when the project dir does not exist."""
    ghost = tmp_path / "does-not-exist"
    with pytest.raises(FileNotFoundError):
        sb._do_run(
            image="aimm-sandbox:node-baseline",
            project_dir=ghost,
            cmd="echo hi",
            network="none",
        )


def test_render_shootout_markdown_has_table_header():
    """The shootout report always renders a stable markdown table header."""
    report = sb.ShootoutReport(
        recipe_name="t",
        started_at="20260526_120000+0200",
        finished_at="20260526_120100+0200",
        cells=[
            sb.ShootoutCell(
                tool="baseline",
                image="aimm-sandbox:node-baseline",
                command_name="hello",
                command="echo hi",
                result=sb.RunResult(
                    image="aimm-sandbox:node-baseline",
                    cmd="echo hi",
                    exit_code=0,
                    wall_clock_ms=42,
                    stdout_bytes=3,
                    stderr_bytes=0,
                    log_path="/tmp/x.log",
                ),
            )
        ],
    )
    md = sb._render_shootout_markdown(report)
    assert "# Sandbox shootout — `t`" in md
    assert "| Tool | Command | Exit |" in md
    assert "| baseline | `hello` | 0 | 42 |" in md


def test_runtime_guard_shootout_recipe_parses():
    """The shipped runtime-guard recipe is valid YAML with the expected shape."""
    import yaml

    recipe_path = Path(__file__).resolve().parent.parent / "scripts" / "sandbox" / "recipes" / "runtime-guard-shootout.yaml"
    assert recipe_path.is_file()
    spec = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    assert spec["name"] == "runtime-guard-shootout"
    assert {row["tool"] for row in spec["matrix"]} == {"baseline", "safe-chain", "sfw"}
    assert all("cmd" in c and "name" in c for c in spec["commands"])


# -- integration (real Docker, 🐌 slow) --------------------------------------


@needs_docker
def test_preflight_with_docker_available(capsys: pytest.CaptureFixture[str]):
    """🐌 preflight returns 0 or 2 depending on whether images are built."""
    rc = sb.cmd_preflight(argparse.Namespace())
    err = capsys.readouterr().err
    assert rc in (0, 2)
    assert "docker server:" in err


@needs_node_baseline
def test_run_executes_command_in_container(tmp_path: Path):
    """🐌 a `run` with node-baseline executes the command and returns exit 0."""
    pkg = tmp_path / "scratch"
    pkg.mkdir()
    (pkg / "marker.txt").write_text("hello", encoding="utf-8")
    result = sb._do_run(
        image="aimm-sandbox:node-baseline",
        project_dir=pkg,
        cmd="cat /work/marker.txt && node --version",
        network="none",
        time_budget=60,
    )
    assert result.exit_code == 0, f"unexpected exit: {result}"
    log = Path(result.log_path).read_text(encoding="utf-8")
    assert "hello" in log
    assert "v24." in log or "v25." in log or "v26." in log  # node major


@needs_node_baseline
def test_run_network_none_blocks_internet(tmp_path: Path):
    """🐌 with --network none the container cannot reach external hosts."""
    pkg = tmp_path / "scratch"
    pkg.mkdir()
    result = sb._do_run(
        image="aimm-sandbox:node-baseline",
        project_dir=pkg,
        cmd="curl --max-time 5 -fsS https://example.com >/dev/null",
        network="none",
        time_budget=30,
    )
    # `curl: (6) Could not resolve host` → exit 6 on network=none.
    assert result.exit_code != 0, "network=none must block external curl"


@needs_node_baseline
def test_run_timeout_returns_124(tmp_path: Path):
    """🐌 a command exceeding --time-budget returns exit 124 with timed_out=True."""
    pkg = tmp_path / "scratch"
    pkg.mkdir()
    result = sb._do_run(
        image="aimm-sandbox:node-baseline",
        project_dir=pkg,
        cmd="sleep 30",
        network="none",
        time_budget=2,
    )
    assert result.exit_code == 124
    assert result.timed_out is True


@needs_node_baseline
def test_run_leaves_no_orphans(tmp_path: Path):
    """🐌 after a normal run, no aimm-sandbox containers remain in any state."""
    pkg = tmp_path / "scratch"
    pkg.mkdir()
    before = _count_sandbox_containers()
    sb._do_run(
        image="aimm-sandbox:node-baseline",
        project_dir=pkg,
        cmd="true",
        network="none",
        time_budget=30,
    )
    # the harness reaps by session label in a finally; total count is stable.
    assert _count_sandbox_containers() == before


@needs_node_baseline
def test_run_mount_is_readonly_by_default(tmp_path: Path):
    """🐌 `--allow-writes` defaults to False, so writes to /work are refused."""
    pkg = tmp_path / "scratch"
    pkg.mkdir()
    result = sb._do_run(
        image="aimm-sandbox:node-baseline",
        project_dir=pkg,
        cmd="touch /work/should-fail 2>&1 | head -1",
        network="none",
        time_budget=20,
    )
    log = Path(result.log_path).read_text(encoding="utf-8")
    assert ("Read-only file system" in log) or ("Permission denied" in log)


@needs_docker
def test_clone_handles_real_repo(tmp_path: Path):
    """🐌 clone fetches a tiny public repo into a sandbox dir + writes manifest."""
    dest = tmp_path / "spoon"
    ns = argparse.Namespace(repo="octocat/Spoon-Knife", ref=None, depth=1, dest=str(dest))
    assert sb.cmd_clone(ns) == 0
    assert (dest / ".git").is_dir()
    manifest = json.loads((dest / ".aimm-sandbox.json").read_text(encoding="utf-8"))
    assert manifest["repo"] == "octocat/Spoon-Knife"
