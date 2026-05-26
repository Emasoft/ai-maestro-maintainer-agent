# aimm-sandbox:node-safe-chain
# Node baseline + Aikido Safe Chain pre-installed and shell-wired, so
# every npm/yarn/pnpm/npx/pnpx command inside the container is routed
# through the Aikido malware proxy. The setup is contained to the
# container's own .bashrc — it never touches the host.
FROM node:24-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git ca-certificates curl jq tini procps \
 && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /work /out \
 && chown node:node /work /out

# Install Safe Chain globally (root install; user-level setup runs once
# at image build time and the resulting .bashrc is cached so the runtime
# tmpfs at /home/node can be reseeded by the entrypoint shim).
RUN npm install -g @aikidosec/safe-chain

USER node
RUN safe-chain setup --yes || true \
 && cp -r /home/node/.bashrc /tmp/safe-chain-bashrc 2>/dev/null || true

USER root
RUN cat >/usr/local/bin/aimm-safe-chain-entrypoint <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
# /home/node is mounted as tmpfs at runtime (writable, ephemeral); we
# reseed the shell init each time the container starts.
if [ -f /tmp/safe-chain-bashrc ] && [ -w "$HOME" ]; then
  cp /tmp/safe-chain-bashrc "$HOME/.bashrc"
fi
exec "$@"
EOF
RUN chmod +x /usr/local/bin/aimm-safe-chain-entrypoint
USER node
WORKDIR /work
ENV NODE_ENV=development \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    CI=1

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/aimm-safe-chain-entrypoint"]
CMD ["bash"]
