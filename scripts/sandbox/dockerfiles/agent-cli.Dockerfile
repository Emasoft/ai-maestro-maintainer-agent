# aimm-sandbox:agent-cli
# A dev container with the Claude Code CLI and a working toolchain, so the
# maintainer can run an agent against an untrusted repo without that repo (or
# its postinstall scripts) ever touching the host.
#
# Unlike the other images here, this one is NOT for running untrusted code with
# `--network none`: an agent CLI must reach the API, so it needs
# `--network bridge` and an ANTHROPIC_API_KEY passed at run time. The isolation
# it buys is of the FILESYSTEM and the toolchain, not the network.
#
# Adapted from johannesjo/parallel-code's docker/Dockerfile. Four things in the
# original are deliberately NOT reproduced, because each fails a gate this plugin
# enforces on everyone else's repos:
#
#   1. It fetched a remote install script and piped it straight into a shell.
#      The plugin ships scripts/sentinel/rules/curl_pipe_shell.py to flag exactly
#      that in the repos it maintains: the fetched script is unauthenticated,
#      unpinned, and runs with the builder's privileges, so whoever controls that
#      URL controls the image.
#   2. It ran as ROOT. It created an `agent` user and never issued `USER agent`,
#      so every container came up as uid 0 (Checkov CKV_DOCKER_3 / Trivy
#      AVD-DS-0002 — both enforced here, neither ignored).
#   3. Its base was unpinned. `node:24-bookworm-slim` is a specific,
#      non-`latest` tag (CKV_DOCKER_7 / AVD-DS-0001).
#   4. It added third-party apt repos at build time.
#
# On (4): NO image in this directory fetches anything over the network at build
# time — every one installs from apt, npm, or pip only. python-baseline had to
# learn this the hard way (its curl-based uv installer kept breaking when the
# upstream layout drifted; it now uses `pip install uv`). Every network fetch in
# a Dockerfile is a build-time dependency on someone else's uptime AND a place a
# supplier can change what lands in the image. So the GitHub CLI is NOT installed
# here: it has no Debian package, and adding its apt repo would make this the one
# image that reaches out at build time. A derived image can add it if a task
# genuinely needs it; git and the REST API cover most of what it is used for.
#
# Basing on node: rather than ubuntu: also means the `node` user (uid 1000)
# already exists — a fresh `useradd -u 1000` would collide with it.
FROM node:24-bookworm-slim

# Pin the agent CLI so an image rebuild is reproducible. Override at build time:
#   docker build --build-arg CLAUDE_CODE_VERSION=2.1.191 ...
ARG CLAUDE_CODE_VERSION=latest

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# One apt layer: the toolchain an agent needs to actually build and test a repo.
# build-essential/python3-dev are here on purpose — a native npm or pip module
# that fails to compile is the single most common way an agent burns ten minutes
# on setup instead of on the task.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl wget gnupg \
      git git-lfs openssh-client \
      build-essential pkg-config \
      python3 python3-pip python3-venv python3-dev \
      bash jq ripgrep fd-find fzf tree unzip less nano \
      procps tini \
 && rm -rf /var/lib/apt/lists/*

# Debian ships fd as `fdfind`; agents (and their muscle memory) expect `fd`.
RUN ln -sf /usr/bin/fdfind /usr/local/bin/fd

# The agent CLI itself.
RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
 && npm cache clean --force \
 && claude --version

# Commits work out of the box; detached-HEAD advice is noise in a throwaway container.
RUN git config --system init.defaultBranch main \
 && git config --system advice.detachedHead false

RUN mkdir -p /work /out && chown node:node /work /out

# Drop root. Everything above needed it; nothing below does.
USER node
WORKDIR /work
ENV SHELL=/bin/bash \
    NPM_CONFIG_UPDATE_NOTIFIER=false

# Tini gives clean PID-1 semantics so `docker run --rm` reaps whatever the agent
# (or a repo's postinstall script) leaves behind.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash"]
