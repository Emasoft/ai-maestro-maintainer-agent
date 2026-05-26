# aimm-sandbox:node-sfw
# Node baseline + Socket Firewall Free (`sfw`). Unlike safe-chain this
# tool does not modify shell init — the user prefixes commands with
# `sfw` to opt in (e.g. `sfw npm install foo`). The image ships sfw on
# PATH so the harness's recipes can call it directly.
FROM node:24-bookworm-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git ca-certificates curl jq tini procps \
 && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /work /out \
 && chown node:node /work /out

RUN npm install -g sfw

USER node
WORKDIR /work
ENV NODE_ENV=development \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    CI=1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash"]
