"""The two transient-vs-permanent classifiers in scripts/cpv_network_resilience.py.

Why these two, and why now. TRDD-4QC0DV9O tracks components shipping without a
test; CPV counts 18. Sixteen are markdown commands, and the seventeenth
(`setup_marketplace_pat.py`) is untested for a principled reason — every function
in it shells out to `gh` to check admin rights and WRITE repository secrets, so a
real test would mutate a live repo's secrets and a mocked one would prove nothing.
That leaves these two, which are pure: string/exception in, bool out. No mocks, no
network, no fixtures.

What makes them worth pinning rather than just coverable:

  * THE PRECEDENCE RULE IS LOAD-BEARING AND SILENT. `is_transient_subprocess_error`
    documents that a permanent signature always wins over a transient one, because
    real stderr chains both ("401 Unauthorized: rate limit exceeded"). Invert that
    and the pipeline retries an auth failure until it exhausts its attempts, then
    reports a network problem. Nothing else in the tree would notice.
  * THIS FILE IS A CPV TEMPLATE. publish.py warns it can be refreshed by
    `cpv standardize --force-templates`, so its body can change from OUTSIDE this
    repo. That is precisely the cross-project staleness class that bit this plugin
    twice on 2026-08-07 (a rule narrowed upstream, a validator pin 50 releases
    stale) — a fact verified in another repo keeps living there. A local test is
    the only thing here that can notice the refresh changed behavior.

Every case is a REAL call with a REAL exception object.
"""

from __future__ import annotations

import socket
import ssl
import urllib.error
from http.client import BadStatusLine, RemoteDisconnected

import pytest

from cpv_network_resilience import (  # scripts/ is on sys.path via conftest
    is_transient_http_error,
    is_transient_subprocess_error,
)

# ── is_transient_subprocess_error ────────────────────────────────────────────


@pytest.mark.parametrize(
    "stderr",
    [
        "fatal: unable to access 'https://github.com/x': Failed to connect to github.com port 443",
        "error: RPC failed; HTTP 502 curl 22",
        "The remote end hung up unexpectedly",
        "gh: Service Unavailable (HTTP 503)",
        "dial tcp 140.82.121.6:443: i/o timeout",
        'Get "https://api.github.com/x": context deadline exceeded',
        "ssh: connect to host github.com port 22: Network is unreachable",
        "fatal: unable to access 'https://github.com/x': Could not resolve host: no such host",
    ],
)
def test_transient_subprocess_signatures_are_retryable(stderr: str) -> None:
    """Real network-glitch stderr is classified transient."""
    assert is_transient_subprocess_error(stderr, 1) is True


@pytest.mark.parametrize(
    "stderr",
    [
        "! [rejected] main -> main (non-fast-forward)",
        "git@github.com: Permission denied (publickey).",
        "gh: HTTP 401: Bad credentials",
        "remote: Repository not found. HTTP 404",
        "GraphQL: name already exists on this account",
    ],
)
def test_permanent_subprocess_signatures_are_not_retryable(stderr: str) -> None:
    """An auth/logic failure must never be retried, however the run exits."""
    assert is_transient_subprocess_error(stderr, 1) is False


@pytest.mark.parametrize(
    "stderr",
    [
        "gh: HTTP 401 Unauthorized: rate limit exceeded",
        "fatal: Authentication failed; the operation timed out",
        "! [rejected] non-fast-forward (RPC failed; HTTP 503)",
    ],
)
def test_permanent_wins_when_both_signatures_appear(stderr: str) -> None:
    """THE precedence rule: a chained error carrying both is PERMANENT.

    Invert this and the pipeline retries an auth failure to exhaustion and then
    blames the network. Each string here contains a genuine transient phrase, so
    a classifier that checked transient-first would return True on all three.
    """
    assert is_transient_subprocess_error(stderr, 1) is False


def test_success_and_empty_stderr_are_never_transient() -> None:
    """A zero exit is not a failure, and a failure with no stderr is unclassifiable."""
    assert is_transient_subprocess_error("Failed to connect to github.com port 443", 0) is False
    assert is_transient_subprocess_error("", 1) is False


def test_unrecognised_stderr_defaults_to_not_retrying() -> None:
    """An unknown failure is not assumed transient — retrying it just wastes attempts."""
    assert is_transient_subprocess_error("error: pathspec 'nope' did not match", 1) is False


# ── is_transient_http_error ──────────────────────────────────────────────────


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example.com", code, "msg", {}, None)  # type: ignore[arg-type]


@pytest.mark.parametrize("code", [408, 429, 500, 502, 503, 504])
def test_retryable_http_status_codes(code: int) -> None:
    """Timeout / rate-limit / 5xx may clear up on retry."""
    assert is_transient_http_error(_http_error(code)) is True


@pytest.mark.parametrize("code", [400, 401, 403, 404, 422])
def test_client_error_status_codes_are_permanent(code: int) -> None:
    """A 4xx that is not 408/429 will return the same answer next time."""
    assert is_transient_http_error(_http_error(code)) is False


@pytest.mark.parametrize(
    "exc",
    [
        socket.timeout("timed out"),
        TimeoutError("timed out"),
        ssl.SSLError("handshake"),
        RemoteDisconnected("closed"),
        BadStatusLine("''"),
        ConnectionResetError("reset"),
    ],
)
def test_transport_level_exceptions_are_transient(exc: BaseException) -> None:
    """Real transport failures, constructed as the real exception types."""
    assert is_transient_http_error(exc) is True


def test_urlerror_recurses_into_its_reason() -> None:
    """URLError is a wrapper — the verdict belongs to what it wraps, either way."""
    assert is_transient_http_error(urllib.error.URLError(socket.timeout("t"))) is True
    assert is_transient_http_error(urllib.error.URLError("nodename nor servname provided")) is False


def test_none_and_unrelated_exceptions_are_not_transient() -> None:
    """No error is not a transient error, and neither is a bug in our own code."""
    assert is_transient_http_error(None) is False
    assert is_transient_http_error(ValueError("bad input")) is False
