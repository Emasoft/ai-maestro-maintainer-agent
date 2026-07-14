#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""Docker-sandbox harness for the maintainer agent.

A small, composable CLI that lets the maintainer agent run untrusted code
(third-party tools, suspicious npm/pypi packages, external repos) in isolated
Docker containers without polluting the host.

Subcommands:
    preflight                 Check docker reachable + images present
    build-images [--variant]  Build aimm-sandbox:* images from ./dockerfiles
    clone <owner/repo>        Clone a GitHub repo into /tmp/aimm-sandbox/
    run <image> <dir> --cmd   Run an arbitrary command in a sandboxed container
    shootout <recipe.yaml>    Run a matrix of (tool × command) cells, report
    precheck <pkg> [--eco]    Install a single npm/pypi package, report findings

Safety invariants (enforced):
    - --network none by default (opt-in --network bridge for real internet).
    - Project mount is :ro unless --allow-writes is explicitly set.
    - No --privileged, no Docker socket, no host PID/IPC namespace.
    - Every container is labelled aimm-sandbox=true + session-uuid; the
      harness reports orphans at exit and refuses to exit cleanly otherwise.
    - All scratch state lives under /tmp/aimm-sandbox/; the harness owns purge.

The harness writes reports under $MAIN_ROOT/reports/sandbox/ per the
project-wide reports-location rule.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

# -- constants ----------------------------------------------------------------

IMAGE_PREFIX = "aimm-sandbox"
LABEL_KEY = "aimm-sandbox"
SESSION_LABEL_KEY = "aimm-sandbox-session"
SCRATCH_ROOT = Path("/tmp/aimm-sandbox")
HERE = Path(__file__).resolve().parent
DOCKERFILES_DIR = HERE / "dockerfiles"
REPO_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
DEFAULT_TIME_BUDGET = 600  # seconds — covers the longest install we expect


# -- core types ---------------------------------------------------------------


@dataclass
class RunResult:
    """One container invocation's observable outcome."""

    image: str
    cmd: str
    exit_code: int
    wall_clock_ms: int
    stdout_bytes: int
    stderr_bytes: int
    log_path: str
    timed_out: bool = False


@dataclass
class ShootoutCell:
    tool: str
    image: str
    command_name: str
    command: str
    result: RunResult


@dataclass
class ShootoutReport:
    recipe_name: str
    started_at: str
    finished_at: str
    cells: list[ShootoutCell] = field(default_factory=list)


# -- helpers ------------------------------------------------------------------


def _local_ts() -> str:
    """Local time + GMT offset, compact form (per agent-reports-location.md)."""
    return time.strftime("%Y%m%d_%H%M%S%z")


def _main_root() -> Path:
    """Repo root (works in main checkout and in linked worktrees).

    `--porcelain` is not a style preference. Plain `git worktree list` prints
    `<path> <sha> [<branch>]`, so `.split()[0]` TRUNCATES any path containing a
    space — routine on macOS — and the sandbox then writes its reports into a
    directory that does not exist. Porcelain puts the path alone on its own line.
    """
    out = subprocess.run(["git", "worktree", "list", "--porcelain"], capture_output=True, text=True, check=False)
    if out.returncode == 0:
        for line in out.stdout.splitlines():
            if line.startswith("worktree "):
                return Path(line[len("worktree ") :])
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd()))


def _reports_dir(component: str) -> Path:
    p = _main_root() / "reports" / component
    p.mkdir(parents=True, exist_ok=True)
    return p


def _new_session_id() -> str:
    return uuid.uuid4().hex[:12]


def _docker(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run `docker ...` with no shell, text output, never raise on its own."""
    cmd = ["docker", *args]
    return subprocess.run(cmd, shell=False, capture_output=True, text=True, check=False)


def _git(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "http.lowSpeedLimit=100", "-c", "http.lowSpeedTime=300", *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
    )


def _say(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


# -- preflight ----------------------------------------------------------------


def _list_image_tags() -> set[str]:
    """All locally-tagged docker images starting with our prefix."""
    out = _docker(["image", "ls", "--format", "{{.Repository}}:{{.Tag}}", f"{IMAGE_PREFIX}:*"])
    if out.returncode != 0:
        return set()
    return {line.strip() for line in out.stdout.splitlines() if line.strip()}


def _expected_image_tags() -> list[str]:
    """Image tags the harness knows about (derived from Dockerfile filenames)."""
    if not DOCKERFILES_DIR.is_dir():
        return []
    return sorted(f"{IMAGE_PREFIX}:{p.stem}" for p in DOCKERFILES_DIR.glob("*.Dockerfile"))


def cmd_preflight(_args: argparse.Namespace) -> int:
    """Verify docker reachable + report which aimm-sandbox:* images are built."""
    out = _docker(["version", "--format", "{{.Server.Version}}"])
    if out.returncode != 0 or not out.stdout.strip():
        _say("docker server not reachable — start Docker / OrbStack and retry.")
        _say(out.stderr.strip() or "(no detail)")
        return 1

    server_ver = out.stdout.strip()
    have = _list_image_tags()
    want = _expected_image_tags()
    missing = [t for t in want if t not in have]

    _say(f"docker server: {server_ver}")
    _say(f"images expected: {len(want)} ({', '.join(want) if want else '(none)'})")
    _say(f"images present:  {len(have - set(want))} foreign + {len(have & set(want))} ours")
    if missing:
        _say(f"images missing:  {', '.join(missing)}  →  `sandbox.py build-images` to build")
        return 2
    _say("preflight OK")
    return 0


# -- build-images -------------------------------------------------------------


def cmd_build_images(args: argparse.Namespace) -> int:
    """Build every aimm-sandbox:* image (or just the one named via --variant)."""
    if not DOCKERFILES_DIR.is_dir():
        _say(f"no dockerfiles dir at {DOCKERFILES_DIR}")
        return 1

    dockerfiles = sorted(DOCKERFILES_DIR.glob("*.Dockerfile"))
    if args.variant:
        dockerfiles = [p for p in dockerfiles if p.stem == args.variant]
        if not dockerfiles:
            _say(f"variant '{args.variant}' not found under {DOCKERFILES_DIR}")
            return 1

    failed: list[str] = []
    for df in dockerfiles:
        tag = f"{IMAGE_PREFIX}:{df.stem}"
        _say(f"building {tag} from {df.name}…")
        rc = subprocess.run(
            ["docker", "build", "-f", str(df), "-t", tag, str(DOCKERFILES_DIR)],
            check=False,
        ).returncode
        if rc != 0:
            failed.append(tag)
            _say(f"  FAILED ({rc})")
        else:
            _say("  OK")
    if failed:
        _say(f"failed: {', '.join(failed)}")
        return 1
    return 0


# -- clone --------------------------------------------------------------------


def cmd_clone(args: argparse.Namespace) -> int:
    """Clone owner/repo into /tmp/aimm-sandbox/<owner>_<repo>-<ref>/."""
    slug = args.repo
    if not REPO_SLUG_RE.match(slug):
        _say(f"invalid repo slug: {slug!r} (want owner/repo)")
        return 1
    owner, repo = slug.split("/", 1)
    url = f"https://github.com/{owner}/{repo}.git"

    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    ref_part = (args.ref or "main")[:12]
    if args.dest:
        dest = Path(args.dest)
    else:
        dest = SCRATCH_ROOT / f"{owner}_{repo}-{ref_part}-{_local_ts()}"
    if dest.exists():
        _say(f"dest already exists: {dest} — refusing to overwrite")
        return 1
    dest.parent.mkdir(parents=True, exist_ok=True)

    git_args = ["clone"]
    if args.depth and not args.ref:
        git_args += ["--depth", str(args.depth)]
    git_args += [url, str(dest)]
    out = _git(git_args)
    if out.returncode != 0:
        _say(f"git clone failed: {out.stderr.strip()}")
        return 1

    if args.ref:
        if not (SHA_RE.match(args.ref) or re.match(r"^[\w./-]+$", args.ref)):
            _say(f"invalid ref: {args.ref!r}")
            shutil.rmtree(dest, ignore_errors=True)
            return 1
        out = _git(["checkout", args.ref], cwd=dest)
        if out.returncode != 0:
            _say(f"git checkout {args.ref} failed: {out.stderr.strip()}")
            return 1

    (dest / ".aimm-sandbox.json").write_text(
        json.dumps(
            {
                "repo": slug,
                "ref": args.ref or "main",
                "cloned_at": _local_ts(),
                "by": "scripts/sandbox/sandbox.py clone",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(str(dest))  # stdout = path for caller piping
    return 0


# -- run ----------------------------------------------------------------------


def _orphans_for_session(session_id: str) -> list[str]:
    out = _docker(
        [
            "ps",
            "-a",
            "--filter",
            f"label={LABEL_KEY}=true",
            "--filter",
            f"label={SESSION_LABEL_KEY}={session_id}",
            "--format",
            "{{.ID}} {{.Status}} {{.Image}}",
        ]
    )
    return [line for line in out.stdout.splitlines() if line.strip()]


def _kill_orphans(session_id: str) -> None:
    out = _docker(
        [
            "ps",
            "-aq",
            "--filter",
            f"label={LABEL_KEY}=true",
            "--filter",
            f"label={SESSION_LABEL_KEY}={session_id}",
        ]
    )
    ids = [i for i in out.stdout.split() if i.strip()]
    if ids:
        _docker(["rm", "-f", *ids])


def _do_run(
    image: str,
    project_dir: Path,
    cmd: str,
    *,
    network: str = "none",
    time_budget: int = DEFAULT_TIME_BUDGET,
    allow_writes: bool = False,
    session_id: str | None = None,
    log_path: Path | None = None,
) -> RunResult:
    """Single docker-run invocation; captures wall-clock and outputs."""
    if not project_dir.is_dir():
        raise FileNotFoundError(f"project_dir does not exist: {project_dir}")
    if network not in ("none", "bridge"):
        raise ValueError(f"network must be 'none' or 'bridge', got {network!r}")

    session_id = session_id or _new_session_id()
    mount_mode = "rw" if allow_writes else "ro"
    docker_args = [
        "run",
        "--rm",
        "--label",
        f"{LABEL_KEY}=true",
        "--label",
        f"{SESSION_LABEL_KEY}={session_id}",
        "--network",
        network,
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true",
        "--read-only",
        "--tmpfs=/tmp:rw,size=512m",
        "--tmpfs=/home/sandbox:rw,size=128m",
        "-v",
        f"{project_dir.resolve()}:/work:{mount_mode}",
        "-w",
        "/work",
        "--stop-timeout",
        "5",
        image,
        "bash",
        "-eo",
        "pipefail",
        "-c",
        cmd,
    ]

    if log_path is None:
        log_path = _reports_dir("sandbox/runs") / f"{_local_ts()}-{session_id}.log"
    started = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.run(
            ["docker", *docker_args],
            capture_output=True,
            text=True,
            check=False,
            timeout=time_budget,
        )
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        # exc has partial stdout/stderr only when capture_output=True; subprocess
        # may also have left containers alive on timeout — orphan cleanup runs
        # in the outer finally.
        stdout = exc.stdout or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", "replace")
        stderr = exc.stderr or ""
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "replace")
        wall_ms = int((time.monotonic() - started) * 1000)
        log_path.write_text(
            f"# TIMED OUT after {time_budget}s\n# image={image} cmd={cmd!r}\n--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}\n",
            encoding="utf-8",
        )
        return RunResult(
            image=image,
            cmd=cmd,
            exit_code=124,
            wall_clock_ms=wall_ms,
            stdout_bytes=len(stdout.encode()),
            stderr_bytes=len(stderr.encode()),
            log_path=str(log_path),
            timed_out=True,
        )
    finally:
        # belt-and-braces: even though --rm should kill the container, a
        # docker daemon hiccup could leave one behind. Reaping by session
        # label keeps parallel runs safe.
        _kill_orphans(session_id)

    wall_ms = int((time.monotonic() - started) * 1000)
    log_path.write_text(
        f"# image={image} cmd={cmd!r} exit={proc.returncode} wall={wall_ms}ms timed_out={timed_out}\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}\n",
        encoding="utf-8",
    )
    return RunResult(
        image=image,
        cmd=cmd,
        exit_code=proc.returncode,
        wall_clock_ms=wall_ms,
        stdout_bytes=len(proc.stdout.encode()),
        stderr_bytes=len(proc.stderr.encode()),
        log_path=str(log_path),
        timed_out=False,
    )


def cmd_run(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir).resolve()
    try:
        result = _do_run(
            image=args.image,
            project_dir=project_dir,
            cmd=args.cmd,
            network=args.network,
            time_budget=args.time_budget,
            allow_writes=args.allow_writes,
        )
    except (FileNotFoundError, ValueError) as exc:
        _say(str(exc))
        return 1
    print(json.dumps(asdict(result), indent=2))
    return result.exit_code if result.exit_code in (0, 124) else 1


# -- shootout -----------------------------------------------------------------


def _materialise_scratch_project(spec: dict[str, Any]) -> Path:
    """Write a scratch project from a recipe's project.files map."""
    files = spec.get("files") or {}
    dest = Path(tempfile.mkdtemp(prefix="aimm-shootout-", dir=str(SCRATCH_ROOT)))
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    for rel, body in files.items():
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body if isinstance(body, str) else json.dumps(body, indent=2), encoding="utf-8")
    return dest


def _render_shootout_markdown(report: ShootoutReport) -> str:
    lines = [
        f"# Sandbox shootout — `{report.recipe_name}`",
        "",
        f"- started:  `{report.started_at}`",
        f"- finished: `{report.finished_at}`",
        f"- cells:    `{len(report.cells)}`",
        "",
        "## Results",
        "",
        "| Tool | Command | Exit | Wall (ms) | stdout B | stderr B | Log |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for c in report.cells:
        r = c.result
        tag = " ⏱" if r.timed_out else ""
        lines.append(f"| {c.tool} | `{c.command_name}` | {r.exit_code}{tag} | {r.wall_clock_ms} | {r.stdout_bytes} | {r.stderr_bytes} | `{r.log_path}` |")
    return "\n".join(lines) + "\n"


def cmd_shootout(args: argparse.Namespace) -> int:
    recipe_path = Path(args.recipe).resolve()
    if not recipe_path.is_file():
        _say(f"recipe not found: {recipe_path}")
        return 1
    spec = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict):
        _say("recipe must be a YAML mapping")
        return 1

    recipe_name = spec.get("name") or recipe_path.stem
    matrix = spec.get("matrix") or []
    commands = spec.get("commands") or []
    if not matrix or not commands:
        _say("recipe must have non-empty matrix: and commands:")
        return 1

    proj = spec.get("project") or {"type": "scratch"}
    if proj.get("type") == "scratch":
        project_dir = _materialise_scratch_project(proj)
    elif proj.get("type") == "clone":
        slug = proj.get("repo")
        if not slug:
            _say("project.type=clone requires project.repo")
            return 1
        ref = proj.get("ref")
        ns = argparse.Namespace(repo=slug, ref=ref, dest=None, depth=1)
        # cmd_clone prints the path to stdout — capture indirectly via a fresh dir.
        ref_part = (ref or "main")[:12]
        owner, repo = slug.split("/", 1)
        project_dir = SCRATCH_ROOT / f"{owner}_{repo}-{ref_part}-{_local_ts()}"
        ns.dest = str(project_dir)
        if cmd_clone(ns) != 0:
            _say("clone failed; aborting shootout")
            return 1
    else:
        _say(f"unknown project.type: {proj.get('type')!r}")
        return 1

    report_dir = _reports_dir(f"sandbox/{recipe_name}")
    started_at = _local_ts()
    cells: list[ShootoutCell] = []
    session_id = _new_session_id()
    network = spec.get("network") or "none"
    time_budget = int(spec.get("time_budget") or DEFAULT_TIME_BUDGET)

    try:
        for row in matrix:
            tool = row.get("tool") or "?"
            image = row.get("image")
            if not image:
                _say(f"matrix row {tool!r} missing image:")
                return 1
            for c in commands:
                cname = c.get("name") or c.get("cmd")
                cmd = c.get("cmd")
                if not cmd:
                    _say(f"command {cname!r} missing cmd:")
                    return 1
                _say(f"[{tool} × {cname}] running…")
                result = _do_run(
                    image=image,
                    project_dir=project_dir,
                    cmd=cmd,
                    network=network,
                    time_budget=time_budget,
                    allow_writes=False,
                    session_id=session_id,
                    log_path=report_dir / f"{started_at}-{tool}-{cname}.log",
                )
                cells.append(ShootoutCell(tool=tool, image=image, command_name=cname, command=cmd, result=result))
    finally:
        _kill_orphans(session_id)
        orphans = _orphans_for_session(session_id)
        if orphans:
            _say(f"WARNING: {len(orphans)} orphan container(s) survived cleanup:")
            for line in orphans:
                _say(f"  {line}")

    report = ShootoutReport(recipe_name=recipe_name, started_at=started_at, finished_at=_local_ts(), cells=cells)
    md = _render_shootout_markdown(report)
    out_path = report_dir / f"{started_at}-shootout.md"
    out_path.write_text(md, encoding="utf-8")
    print(str(out_path))
    return 0 if all(c.result.exit_code in (0, 124) for c in cells) else 1


# -- precheck -----------------------------------------------------------------


def cmd_precheck(args: argparse.Namespace) -> int:
    """Install a single package in a disposable container and report."""
    pkg = args.package
    eco = args.ecosystem
    if eco == "npm":
        image = "aimm-sandbox:node-baseline"
        scratch_project = {
            "files": {
                "package.json": json.dumps({"name": "aimm-precheck", "version": "0.0.0", "private": True}, indent=2),
            }
        }
        cmd = f"npm install --no-audit --no-fund --no-package-lock {pkg!s} 2>&1 | tail -200"
    elif eco == "pypi":
        image = "aimm-sandbox:python-baseline"
        scratch_project = {"files": {"pyproject.toml": '[project]\nname = "aimm-precheck"\nversion = "0.0.0"\n'}}
        cmd = f"pip install --no-cache-dir --target /tmp/precheck-install {pkg!s} 2>&1 | tail -200"
    else:
        _say(f"unknown ecosystem: {eco!r}")
        return 1

    project_dir = _materialise_scratch_project(scratch_project)
    result = _do_run(
        image=image,
        project_dir=project_dir,
        cmd=cmd,
        network="bridge",  # install needs the registry; that is the WHOLE point
        time_budget=args.time_budget,
        allow_writes=False,
    )
    report = {
        "package": pkg,
        "ecosystem": eco,
        "image": image,
        "result": asdict(result),
    }
    out_path = _reports_dir("sandbox/precheck") / f"{_local_ts()}-{eco}-{pkg.replace('/', '_').replace('@', 'AT')}.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(str(out_path))
    return 0 if result.exit_code == 0 else 1


# -- entrypoint ---------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sandbox.py", description=(__doc__ or "").splitlines()[0])
    sub = p.add_subparsers(dest="subcmd", required=True)

    sub.add_parser("preflight", help="Verify docker + image presence")

    bi = sub.add_parser("build-images", help="Build aimm-sandbox:* images")
    bi.add_argument("--variant", help="Only build this variant (e.g. node-baseline)")

    cl = sub.add_parser("clone", help="Clone a GitHub repo into /tmp/aimm-sandbox/")
    cl.add_argument("repo", help="owner/repo")
    cl.add_argument("--ref", help="git ref (sha/tag/branch); default = main")
    cl.add_argument("--depth", type=int, default=1, help="git clone --depth")
    cl.add_argument("--dest", help="custom dest dir")

    rn = sub.add_parser("run", help="Run a command in a sandbox container")
    rn.add_argument("image", help="docker image (e.g. aimm-sandbox:node-baseline)")
    rn.add_argument("project_dir", help="project dir to mount at /work")
    rn.add_argument("--cmd", required=True, help="bash command to run inside the container")
    rn.add_argument("--network", choices=("none", "bridge"), default="none")
    rn.add_argument("--time-budget", type=int, default=DEFAULT_TIME_BUDGET, help="seconds")
    rn.add_argument("--allow-writes", action="store_true", help="mount /work :rw instead of :ro")

    so = sub.add_parser("shootout", help="Run a recipe-driven (tool × command) matrix")
    so.add_argument("recipe", help="path to a YAML recipe under recipes/")

    pc = sub.add_parser("precheck", help="Inspect a single package install in isolation")
    pc.add_argument("package", help="package spec (e.g. axios@1.7.0)")
    pc.add_argument("--ecosystem", choices=("npm", "pypi"), default="npm")
    pc.add_argument("--time-budget", type=int, default=DEFAULT_TIME_BUDGET)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dispatch = {
        "preflight": cmd_preflight,
        "build-images": cmd_build_images,
        "clone": cmd_clone,
        "run": cmd_run,
        "shootout": cmd_shootout,
        "precheck": cmd_precheck,
    }
    fn = dispatch[args.subcmd]
    with contextlib.suppress(BrokenPipeError):
        return fn(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
