# aimm-sandbox:mitm
# Optional mitmproxy sidecar — when a shootout recipe sets
# capture_network: true, the harness pairs the tool container with
# this one to record every outbound DNS/HTTP/HTTPS call. Useful for
# telemetry analysis ("what does Socket Firewall phone home with?").
FROM mitmproxy/mitmproxy:latest

# The official mitmproxy image already runs mitmdump on entry; we just
# need a stable CA-export so the harness can pin it into the tool
# container's trust store at run time.
VOLUME ["/home/mitmproxy/.mitmproxy"]
EXPOSE 8080 8081

CMD ["mitmdump", "--listen-port", "8080", "--set", "block_global=false"]
