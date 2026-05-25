"""Sentinel — deterministic GitHub Actions security scanner (Python port).

A faithful Python port of the Ruby `sentinel-ci` gem (v1.3.0) — the
deterministic GitHub Actions workflow scanner from Atai Barkai's
supply-chain-attack writeup. 32 rules, no external services, pure stdlib
plus PyYAML.

The maintainer Guardian invokes this as a deterministic engine alongside
zizmor: see scripts/sentinel_scan.py for the CLI and the per-rule
detectors under sentinel/rules/.
"""

from __future__ import annotations

# Upstream Ruby gem version this port tracks.
VERSION = "1.3.0"
