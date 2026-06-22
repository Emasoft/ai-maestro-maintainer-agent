# aimm-sandbox:mitm
# Optional mitmproxy sidecar — when a shootout recipe sets
# capture_network: true, the harness pairs the tool container with
# this one to record every outbound DNS/HTTP/HTTPS call. Useful for
# telemetry analysis ("what does Socket Firewall phone home with?").
# Pin the base (not :latest) for reproducible sandbox behavior and to satisfy
# the pinned-base-tag policy (CKV_DOCKER_7 / Trivy AVD-DS-0001). Bump deliberately.
FROM mitmproxy/mitmproxy:12.2.3

# The official mitmproxy image already runs mitmdump on entry; we just
# need a stable CA-export so the harness can pin it into the tool
# container's trust store at run time.
VOLUME ["/home/mitmproxy/.mitmproxy"]
EXPOSE 8080 8081

# The official mitmproxy image already runs as the non-root `mitmproxy` user;
# declare it explicitly so the image satisfies the non-root-USER policy
# (CKV_DOCKER_3 / Trivy AVD-DS-0002) instead of relying on the base default.
USER mitmproxy
CMD ["mitmdump", "--listen-port", "8080", "--set", "block_global=false"]
