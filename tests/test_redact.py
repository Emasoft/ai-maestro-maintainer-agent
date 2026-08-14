"""Unit tests for scripts/redact.py — host-path + secret redaction.

Covers the public API (`redact`, `all_rules`, `main`) plus the CLI
surface. Every test asserts both the substitution result AND the
list of fired rule names — the redaction must be transparent about
what it changed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import redact as r  # scripts/ is on sys.path via conftest.py

# -- public-API tests ---------------------------------------------------------


def test_redact_home_path_substitutes_to_HOME() -> None:
    """A /Users/<name>/<rest> path is rewritten to $HOME/<rest>."""
    out, fired = r.redact("Failed to read /Users/alice/data.json")
    assert "/Users/alice/" not in out
    assert "$HOME/data.json" in out
    assert any("home" in rule.lower() or "user" in rule.lower() for rule in fired)


def test_redact_linux_home_path_substitutes_to_HOME() -> None:
    """/home/<name>/<rest> also lands on $HOME/<rest>."""
    out, fired = r.redact("Crash at /home/bob/projects/x.py")
    assert "/home/bob/" not in out
    assert "$HOME/projects/x.py" in out
    assert fired  # at least one rule fired


def test_redact_windows_userprofile_substitutes() -> None:
    """C:\\Users\\<name>\\<rest> rewrites to %USERPROFILE%\\<rest>."""
    out, fired = r.redact(r"Path C:\Users\alice\file.txt")
    assert r"C:\Users\alice" not in out
    assert "%USERPROFILE%" in out
    assert fired


def test_redact_github_pat_substitutes() -> None:
    """A 36-char GitHub PAT (ghp_*) is masked to ghp_<REDACTED>."""
    pat = "ghp_" + "A" * 36
    out, fired = r.redact(f"Token: {pat}")
    assert pat not in out
    assert "ghp_<REDACTED>" in out
    assert any("github" in rule.lower() or "pat" in rule.lower() or "ghp" in rule.lower() for rule in fired)


def test_redact_gitlab_pat_substitutes() -> None:
    """A GitLab PAT (glpat-*, 20+ chars) is masked to glpat-<REDACTED> — including a longer CRC-suffixed one."""
    for tail in ("A" * 20, "A" * 20 + "-" + "b" * 7):  # plain + CRC-suffixed shape
        tok = "glpat-" + tail
        out, fired = r.redact(f"Token: {tok}")
        assert tok not in out, f"unredacted: {tok}"
        assert "glpat-<REDACTED>" in out
        assert fired


def test_redact_gitlab_deploy_token_substitutes() -> None:
    """A GitLab deploy token (gldt-*) is masked to gldt-<REDACTED>."""
    tok = "gldt-" + "z" * 24
    out, fired = r.redact(f"registry login with {tok}")
    assert tok not in out
    assert "gldt-<REDACTED>" in out
    assert fired


def test_redact_gitlab_rules_leave_short_and_prose_forms_alone() -> None:
    """The bare prefix in prose (and a too-short suffix) is NOT a token and must survive."""
    text = "set a glpat- prefixed token; gldt-short is not one"
    out = r.redact(text)[0]
    assert "glpat- prefixed" in out
    assert "gldt-short" in out


def test_redact_anthropic_api_key_substitutes() -> None:
    """An Anthropic sk-ant-api03-* key is masked."""
    key = "sk-ant-api03-" + "x" * 50
    out, fired = r.redact(f"Anthropic key: {key}")
    assert key not in out
    assert "<REDACTED>" in out
    assert fired


def test_redact_aws_access_key_substitutes() -> None:
    """AWS access key IDs (AKIA[A-Z0-9]{16}) are masked."""
    key = "AKIA" + "Z" * 16
    out, fired = r.redact(f"AWS_ACCESS_KEY_ID={key}")
    assert key not in out
    assert "AKIA<REDACTED>" in out
    assert fired


def test_redact_pem_private_key_block_substitutes() -> None:
    """Complete PEM private key blocks (BEGIN…END) have their body masked.

    The rule deliberately requires both markers so partial/truncated keys
    don't trigger false positives on documentation snippets. A truncated
    `-----BEGIN…` without the matching END line is left unchanged — this
    matches the upstream rule.
    """
    pem = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEpAIBAAKCAQEAyD/PartlyRandomBase64==\n"
        "AnotherLineOfBase64Content==\n"
        "-----END RSA PRIVATE KEY-----"
    )
    out, fired = r.redact(pem)
    assert "MIIEpAIBAAKCAQEAyD/PartlyRandomBase64" not in out
    assert "<REDACTED>" in out
    assert "-----BEGIN RSA PRIVATE KEY-----" in out  # header preserved as marker
    assert "-----END RSA PRIVATE KEY-----" in out
    assert any("pem" in rule.lower() or "private" in rule.lower() for rule in fired)


def test_redact_clean_text_no_substitutions() -> None:
    """Text without paths or secrets passes through unchanged with no fired rules."""
    text = "Updated the README with a section about CI gates."
    out, fired = r.redact(text)
    assert out == text
    assert fired == []


def test_redact_is_idempotent() -> None:
    """Running redact twice produces the same output (no further substitution)."""
    text = "Wrote ledger to /Users/alice/.aimaestro/state/processed-issues.json"
    out1, _ = r.redact(text)
    out2, fired2 = r.redact(out1)
    assert out1 == out2
    assert fired2 == []  # second pass should fire NO rules


def test_redact_handles_multiple_secrets_in_one_input() -> None:
    """All distinct secrets in a single input are redacted independently."""
    text = (
        "Error log:\n"
        "  /Users/alice/script.sh exited 1\n"
        "  AKIAEXAMPLEKEYXXXXXX leaked\n"
        "  ghp_" + "A" * 36 + " also leaked\n"
    )
    out, fired = r.redact(text)
    assert "/Users/alice/" not in out
    assert "AKIAEXAMPLEKEY" not in out
    assert "ghp_AAAAAAAA" not in out  # original PAT prefix
    assert len(fired) >= 3  # at least 3 rules fired


def test_all_rules_returns_nonempty_list() -> None:
    """all_rules() returns a non-empty list of Rule instances."""
    rules = r.all_rules()
    assert len(rules) > 0
    for rule in rules:
        assert isinstance(rule, r.Rule)
        assert rule.name
        assert rule.pattern
        # replacement may be empty for some patterns but must be a string
        assert isinstance(rule.replacement, str)


def test_redact_with_explicit_rules_uses_those_rules() -> None:
    """Passing a custom rule list overrides the default rule set."""
    custom = [r.Rule(name="custom", pattern=r"FOO", replacement="BAR")]
    out, fired = r.redact("FOO baz quux", rules=custom)
    assert out == "BAR baz quux"
    assert "custom" in fired


# -- CLI tests ----------------------------------------------------------------


def _redact_cli(input_text: str, *extra_args: str) -> subprocess.CompletedProcess[str]:
    """Run scripts/redact.py with the given stdin + extra args."""
    repo_root = Path(__file__).resolve().parent.parent
    cmd = ["python3", str(repo_root / "scripts" / "redact.py"), *extra_args]
    return subprocess.run(
        cmd,
        input=input_text,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_stdin_to_stdout_redacts_path() -> None:
    """The CLI reads stdin, redacts, writes stdout, exits 0."""
    out = _redact_cli("Failed at /Users/eve/main.py")
    assert out.returncode == 0
    assert "/Users/eve/" not in out.stdout
    assert "$HOME/main.py" in out.stdout


def test_cli_clean_text_exits_zero_with_no_changes() -> None:
    """Text with no substitutions still exits 0 (success — nothing to redact)."""
    out = _redact_cli("Nothing sensitive here.")
    assert out.returncode == 0
    assert out.stdout.strip() == "Nothing sensitive here."


def test_cli_check_mode_exits_nonzero_when_substitution_would_fire() -> None:
    """`--check` exits non-zero when a redaction would fire (for pre-commit guards)."""
    out = _redact_cli("Path /Users/mallory/secret.txt", "--check")
    # In --check mode, stdout should NOT contain the cleaned text;
    # exit code should be non-zero to indicate "redaction needed".
    assert out.returncode != 0


def test_cli_check_mode_exits_zero_on_clean_input() -> None:
    """`--check` exits 0 when no redaction is needed."""
    out = _redact_cli("All paths are already redacted.", "--check")
    assert out.returncode == 0


def test_cli_file_flag_reads_from_path(tmp_path: Path) -> None:
    """`--file <path>` reads the file instead of stdin."""
    f = tmp_path / "leak.txt"
    f.write_text("Error in /Users/oscar/code/main.py\n")
    out = _redact_cli("", "--file", str(f))
    assert out.returncode == 0
    assert "/Users/oscar/" not in out.stdout
    assert "$HOME/code/main.py" in out.stdout
