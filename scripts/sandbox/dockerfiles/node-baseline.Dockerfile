# aimm-sandbox:node-baseline
# Minimal Node sandbox the maintainer agent uses to run untrusted
# installs in an isolated, throw-away container. Reuses the upstream
# `node` user (UID 1000) that ships with node:* images.
FROM node:24-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git ca-certificates curl jq tini procps \
 && rm -rf /var/lib/apt/lists/*

# `node` user already exists with UID/GID 1000 — reuse it instead of
# creating our own (a fresh `useradd -u 1000` collides with it).
RUN mkdir -p /work /out \
 && chown node:node /work /out

USER node
WORKDIR /work
ENV NODE_ENV=development \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    CI=1

# Tini gives clean PID-1 semantics so `docker run --rm` reaps zombies
# left by misbehaving postinstall scripts.
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash"]
