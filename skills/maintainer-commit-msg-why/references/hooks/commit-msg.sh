#!/usr/bin/env bash
# commit-msg hook: enforce conventional-commits subject + a WHY paragraph.
# Installed by the maintainer-commit-msg-why skill. Do NOT edit on the
# target repo by hand — re-run the skill in `install` mode to refresh.
#
# Validation gates (all must pass, in order):
#   1. Subject line matches: <type>(<scope>)?: <subject>
#      type ∈ {feat, fix, docs, chore, refactor, test, perf, style, ci,
#              build, revert}.
#      subject is non-empty and ≤ 70 characters.
#   2. Body has at least 2 paragraphs (paragraph = block of non-blank
#      lines separated by a blank line). Subject + body counts as 2.
#   3. Body contains at least one WHY-marker (case-insensitive) from:
#      {why, rationale, context, reason, because}.
#
# Bypass: set COMMIT_MSG_HOOK_BYPASS=1. Logged to stderr; the audit
# script flags commits authored under bypass via the trailer
# `X-Commit-Msg-Bypass: 1` that this hook appends to the message.
#
# Exit non-zero rejects the commit. Comment lines (^#) and the diff
# section (Git's "------------- >8 -------------" cut marker) are
# stripped before validation.

set -eu

MSG_FILE="${1:-}"
if [ -z "$MSG_FILE" ] || [ ! -r "$MSG_FILE" ]; then
    printf 'commit-msg hook: missing or unreadable message file: %s\n' "$MSG_FILE" >&2
    exit 2
fi

# Strip comment lines and everything after the scissors marker.
SCRATCH="$(mktemp -t commit-msg.XXXXXX)"
trap 'rm -f "$SCRATCH"' EXIT
awk '
    /^# ------------------------ >8 ------------------------$/ { exit }
    /^#/ { next }
    { print }
' "$MSG_FILE" > "$SCRATCH"

# Bypass path — append trailer, log, exit clean.
if [ "${COMMIT_MSG_HOOK_BYPASS:-}" = "1" ]; then
    printf '\nX-Commit-Msg-Bypass: 1\n' >> "$MSG_FILE"
    printf 'commit-msg hook: BYPASS active (COMMIT_MSG_HOOK_BYPASS=1).\n' >&2
    printf '  Commit will record the X-Commit-Msg-Bypass trailer.\n' >&2
    exit 0
fi

SUBJECT="$(awk 'NF { print; exit }' "$SCRATCH")"
if [ -z "$SUBJECT" ]; then
    printf 'commit-msg hook: REJECTED — empty commit message.\n' >&2
    exit 1
fi

# Gate 1 — subject format.
TYPE_RE='^(feat|fix|docs|chore|refactor|test|perf|style|ci|build|revert)(\([a-z0-9._/-]+\))?: .+'
if ! printf '%s' "$SUBJECT" | grep -Eq "$TYPE_RE"; then
    printf 'commit-msg hook: REJECTED — subject does not match conventional-commits.\n' >&2
    printf '  Expected: <type>(<scope>)?: <subject>\n' >&2
    printf '  Types: feat|fix|docs|chore|refactor|test|perf|style|ci|build|revert\n' >&2
    printf '  Got:   %s\n' "$SUBJECT" >&2
    exit 1
fi

# Gate 1b — subject length.
SUBJECT_LEN="${#SUBJECT}"
if [ "$SUBJECT_LEN" -gt 70 ]; then
    printf 'commit-msg hook: REJECTED — subject is %d chars (max 70).\n' "$SUBJECT_LEN" >&2
    printf '  Got: %s\n' "$SUBJECT" >&2
    exit 1
fi

# Count paragraphs in the FULL stripped message.
PARAS="$(awk '
    BEGIN { paras = 0; in_para = 0 }
    NF > 0 { if (!in_para) { paras++; in_para = 1 } ; next }
    { in_para = 0 }
    END { print paras }
' "$SCRATCH")"

if [ "$PARAS" -lt 2 ]; then
    printf 'commit-msg hook: REJECTED — need ≥ 2 paragraphs (subject + WHY body).\n' >&2
    printf '  Got %d paragraph(s). Add a blank line then a paragraph explaining\n' "$PARAS" >&2
    printf '  WHY the change is needed (rationale, context, reason, because).\n' >&2
    exit 1
fi

# Gate 3 — WHY marker in the body (everything after the first paragraph).
BODY="$(awk '
    BEGIN { paras = 0; in_para = 0; printing = 0 }
    NF > 0 {
        if (!in_para) { paras++; in_para = 1 }
        if (paras >= 2) { printing = 1 }
        if (printing) print
        next
    }
    { in_para = 0; if (printing) print }
' "$SCRATCH")"

if ! printf '%s' "$BODY" | grep -Eiq 'why|rationale|context|reason|because'; then
    printf 'commit-msg hook: REJECTED — body does not contain a WHY marker.\n' >&2
    printf '  Include at least one of (case-insensitive):\n' >&2
    printf '    why | rationale | context | reason | because\n' >&2
    printf '  Body so far:\n' >&2
    printf '%s\n' "$BODY" | sed 's/^/    /' >&2
    exit 1
fi

exit 0
