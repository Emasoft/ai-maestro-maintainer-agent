# aimm-sandbox:python-baseline
# Minimal Python sandbox — uv + pip + git, no project deps.
FROM python:3.12-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git ca-certificates curl jq tini procps \
 && rm -rf /var/lib/apt/lists/*

# pip-installed uv lives at a stable system path (/usr/local/bin/uv) on
# python:* images, avoiding the curl-installer's UID-sensitive layout.
ARG UV_VERSION=0.4.27
# --timeout / --retries cover transient PyPI hiccups during the build
# (this image lives in the supply-chain hot path; we don't want a flaky
# build to be the reason a security test fails).
RUN pip install --no-cache-dir --timeout 120 --retries 5 "uv==${UV_VERSION}" \
 && uv --version

RUN useradd -m -u 1000 sandbox \
 && mkdir -p /work /out \
 && chown sandbox:sandbox /work /out

USER sandbox
WORKDIR /work
ENV CI=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_INPUT=1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["bash"]
