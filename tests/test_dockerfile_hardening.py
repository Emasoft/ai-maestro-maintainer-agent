"""
Security invariants that EVERY Dockerfile in this repo must satisfy.

Why this file exists
--------------------
`scripts/sandbox/dockerfiles/agent-cli.Dockerfile` was adapted from
johannesjo/parallel-code. The upstream original violated three rules this plugin
enforces on everybody else's repos:

  1. `curl -fsSL https://…/install.sh | bash` — the plugin literally ships
     `scripts/sentinel/rules/curl_pipe_shell.py` to flag that pattern in the
     repos it maintains. Shipping it ourselves would be the maintainer breaking
     its own rule.
  2. It ran as ROOT (it created an `agent` user and then never used it).
  3. Its base image was unpinned (`FROM ubuntu:22.04` was fine; the antigravity
     install was not — but plenty of upstreams pin nothing at all).

Fixing that one file is not enough. The next Dockerfile someone adds — or the
next upstream someone adapts — reintroduces it. These tests make the whole CLASS
impossible: they scan every Dockerfile in the repo, so a regression fails the
suite instead of shipping.

Checkov and Trivy already enforce non-root-USER and pinned-base in CI. These
tests are not redundant with that: they run locally in under a second (CI's Lint
job takes four minutes), they cover `curl | sh`, which neither Docker linter
checks, and they state the reason in the failure message so the next author
learns the rule instead of just seeing a rule ID.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILES = sorted((REPO_ROOT / "scripts" / "sandbox" / "dockerfiles").glob("*.Dockerfile"))

# A fetch piped straight into a shell. The fetched script is unauthenticated,
# unpinned, and runs with the builder's privileges — whoever controls that URL
# controls the image. Matches `curl … | bash`, `wget … | sh -s --`, etc.
CURL_PIPE_SHELL = re.compile(r"\b(curl|wget)\b[^|\n]*\|[^|\n]*\b(ba|z|k)?sh\b")

# `apt-key` is deprecated precisely because it adds a key to a GLOBAL trust store:
# the key then validates packages from EVERY repo, not just the one it came from.
# The signed-by keyring pattern binds a key to a single source.
APT_KEY = re.compile(r"\bapt-key\s+add\b")

FROM_LINE = re.compile(r"^\s*FROM\s+(?P<image>\S+)", re.MULTILINE | re.IGNORECASE)
USER_LINE = re.compile(r"^\s*USER\s+(?P<user>\S+)", re.MULTILINE | re.IGNORECASE)


def _dockerfile_ids() -> list[str]:
    return [p.name for p in DOCKERFILES]


def test_there_is_at_least_one_dockerfile() -> None:
    """Guard the guard: if the glob breaks, every test below would vacuously pass."""
    assert DOCKERFILES, "no Dockerfiles found — the glob is wrong and these tests prove nothing"


@pytest.mark.parametrize("df", DOCKERFILES, ids=_dockerfile_ids())
def test_dockerfile_drops_root(df: Path) -> None:
    """Every image ends as a non-root USER (Checkov CKV_DOCKER_3 / Trivy AVD-DS-0002).

    Creating an unprivileged user is not enough — the upstream this was adapted
    from did exactly that and then never switched to it, so every container came
    up as uid 0.
    """
    text = df.read_text(encoding="utf-8")
    users = USER_LINE.findall(text)
    assert users, f"{df.name} never issues USER, so the container runs as root. Creating a user is not the same as becoming one."
    final = users[-1]
    assert final not in ("root", "0"), f"{df.name} ends as USER {final}"


@pytest.mark.parametrize("df", DOCKERFILES, ids=_dockerfile_ids())
def test_dockerfile_base_image_is_pinned(df: Path) -> None:
    """Every FROM names a specific tag or digest — never `latest`, never bare."""
    text = df.read_text(encoding="utf-8")
    images = FROM_LINE.findall(text)
    assert images, f"{df.name} has no FROM line"
    for image in images:
        if image.lower() in ("scratch",):
            continue
        assert "@sha256:" in image or ":" in image, f"{df.name} uses an unpinned base image {image!r} — an untagged image means `latest`, so the same Dockerfile builds a different container tomorrow"
        assert not image.endswith(":latest"), f"{df.name} pins {image!r}, which is not a pin"


@pytest.mark.parametrize("df", DOCKERFILES, ids=_dockerfile_ids())
def test_dockerfile_never_pipes_a_download_into_a_shell(df: Path) -> None:
    """No `curl … | bash`. This plugin ships a Sentinel rule that flags it in OTHER repos.

    The fetched script is unauthenticated, unpinned, and executed with the
    builder's privileges. Whoever controls that URL controls the image — and
    every container built from it.
    """
    text = df.read_text(encoding="utf-8")
    # Comments explain WHY we don't do this; they must not trip the detector.
    code = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    hit = CURL_PIPE_SHELL.search(code)
    assert not hit, f"{df.name} pipes a download into a shell: {hit.group(0)!r}. Fetch a pinned artifact and verify its checksum, or install from a signed apt repo. scripts/sentinel/rules/curl_pipe_shell.py flags this exact pattern in the repos this plugin maintains."


@pytest.mark.parametrize("df", DOCKERFILES, ids=_dockerfile_ids())
def test_dockerfile_never_uses_apt_key_add(df: Path) -> None:
    """Keys go in a per-source keyring, never the global apt trust store."""
    code = "\n".join(line for line in df.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#"))
    assert not APT_KEY.search(code), f"{df.name} uses `apt-key add`, which trusts the key for EVERY apt source. Use `signed-by=/etc/apt/keyrings/<name>.gpg` so the key validates only the repo it came from."


@pytest.mark.parametrize("df", DOCKERFILES, ids=_dockerfile_ids())
def test_dockerfile_fetches_nothing_over_the_network_at_build_time(df: Path) -> None:
    """No image here reaches out mid-build. Packages come from apt, npm, or pip.

    This is the rule the whole directory already followed, now enforced.
    python-baseline learned it the hard way: its curl-based `uv` installer kept
    breaking when the upstream changed its layout, and it moved to `pip install uv`.

    Two costs to a build-time fetch, and the second is the one that matters:
    the build depends on a third party's uptime, and the supplier can change what
    lands in the image without the Dockerfile changing at all. A package manager
    at least verifies signatures and pins a version.

    `apt-get install curl` is fine — that installs the BINARY for the container to
    use at run time. What is banned is INVOKING curl/wget against a URL in a RUN.
    """
    code = "\n".join(line for line in df.read_text(encoding="utf-8").splitlines() if not line.lstrip().startswith("#"))
    fetch = re.search(r"\b(curl|wget)\b[^\n]*\bhttps?://", code)
    assert not fetch, f"{df.name} fetches over the network at build time: {fetch.group(0)[:60]!r}. Install from apt/npm/pip instead — every other image here does, and a build-time fetch is both an uptime dependency and a supply-chain foothold."


def test_the_curl_pipe_shell_detector_actually_detects() -> None:
    """The detector must not be a rubber stamp — feed it the real line from the upstream."""
    # The exact line in johannesjo/parallel-code's docker/Dockerfile.
    assert CURL_PIPE_SHELL.search("RUN curl -fsSL https://antigravity.google/cli/install.sh | bash -s -- --dir /usr/local/bin"), "must catch the upstream's antigravity installer"
    assert CURL_PIPE_SHELL.search("wget -qO- https://example.com/i.sh | sh"), "must catch the wget|sh form"

    # Patterns that are NOT a pipe-into-shell must not be flagged. (We ban these
    # anyway under the stricter no-build-time-fetch rule above — but this detector
    # is about the pipe specifically, and a detector that over-matches teaches the
    # next author the wrong lesson.)
    assert not CURL_PIPE_SHELL.search("curl -fsSL https://example.com/key.gpg -o /etc/apt/keyrings/k.gpg"), "a plain download to a file is not an execution"
    assert not CURL_PIPE_SHELL.search("curl -fsSL https://example.com/key.gpg | gpg --dearmor -o /etc/apt/keyrings/k.gpg"), "piping into gpg is not piping into a shell"
    assert not CURL_PIPE_SHELL.search("apt-get install -y --no-install-recommends curl wget"), "installing the curl BINARY is not invoking it"


def test_agent_cli_image_installs_the_claude_cli_and_stays_reproducible() -> None:
    """agent-cli ships the Claude Code CLI, pinnable at build time, running unprivileged."""
    df = REPO_ROOT / "scripts" / "sandbox" / "dockerfiles" / "agent-cli.Dockerfile"
    text = df.read_text(encoding="utf-8")

    assert "@anthropic-ai/claude-code" in text, "agent-cli exists to carry the Claude Code CLI"
    assert "ARG CLAUDE_CODE_VERSION" in text, "the CLI version must be overridable at build time, or an image rebuild silently changes what is inside it"
    assert USER_LINE.findall(text)[-1] == "node", "agent-cli must end as the unprivileged node user"
    assert "tini" in text, "PID 1 must reap what the agent (or a repo postinstall) leaves behind"
