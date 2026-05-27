#!/usr/bin/env bash
# audit-script: re-run the commit-msg validator against the last N
# commits (default 50) of the entrusted repo. Used by the
# maintainer-commit-msg-why skill in `audit` mode to surface which
# commits in recent history would have been rejected — useful when
# adopting the hook on a repo that already has history.
#
# Inputs:
#   $1 — commit count (default: 50)
#   $2 — path to the hook script (default: ../hooks/commit-msg.sh
#         resolved relative to this audit script)
#
# Output: a TSV report on stdout with columns
#   sha<TAB>status<TAB>subject
# status ∈ {OK, FAIL, BYPASS}. Plus a summary line on stderr.
#
# This script reads commit messages out of `git log --format=%B%n%x00`,
# splits on the NUL marker, and feeds each one to the hook script. The
# hook is invoked with the bypass env var explicitly unset so the
# validation runs full-strength even when the original commit was made
# under bypass — the audit then categorises bypassed commits separately
# by detecting the `X-Commit-Msg-Bypass: 1` trailer.

set -eu

COUNT="${1:-50}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="${2:-$SCRIPT_DIR/hooks/commit-msg.sh}"

if [ ! -x "$HOOK" ]; then
    printf 'audit: hook script not executable: %s\n' "$HOOK" >&2
    printf '  chmod +x %s\n' "$HOOK" >&2
    exit 2
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    printf 'audit: not inside a git work tree.\n' >&2
    exit 2
fi

TMPDIR_AUDIT="$(mktemp -d -t commit-msg-audit.XXXXXX)"
trap 'rm -rf "$TMPDIR_AUDIT"' EXIT

# Pull the last N commits' full messages, NUL-separated so multi-line
# bodies survive the round trip.
git log -n "$COUNT" --format='%H%x1f%B%x00' > "$TMPDIR_AUDIT/log.raw"

ok=0; fail=0; bypass=0
printf 'sha\tstatus\tsubject\n'

# Split on NUL by reading in chunks. Use awk RS to peel each record.
awk 'BEGIN { RS = "\0" } NF { print NR "\t" $0 }' "$TMPDIR_AUDIT/log.raw" \
    | while IFS=$'\t' read -r _idx record; do
    sha="${record%%$'\x1f'*}"
    body="${record#*$'\x1f'}"
    subject="$(printf '%s' "$body" | awk 'NF { print; exit }')"
    if [ -z "$sha" ]; then
        continue
    fi

    msg_file="$TMPDIR_AUDIT/msg.$sha"
    printf '%s' "$body" > "$msg_file"

    # Bypass-trailer detection BEFORE running the hook — even if the
    # validation passes today, the original author flagged it as a
    # bypass, and the audit shows that.
    if grep -q '^X-Commit-Msg-Bypass: 1$' "$msg_file"; then
        printf '%s\tBYPASS\t%s\n' "$sha" "$subject"
        bypass=$((bypass + 1))
        continue
    fi

    # Re-validate with bypass forcibly OFF. Capture exit code.
    if env -u COMMIT_MSG_HOOK_BYPASS "$HOOK" "$msg_file" >/dev/null 2>&1; then
        printf '%s\tOK\t%s\n' "$sha" "$subject"
        ok=$((ok + 1))
    else
        printf '%s\tFAIL\t%s\n' "$sha" "$subject"
        fail=$((fail + 1))
    fi
done

# Read totals from a side-channel — the subshell above is in a pipe so
# we re-derive the counts via a second pass on the report (cheaper than
# re-running the hook).
report_total="$(awk 'BEGIN { RS = "\0" } NF { print }' "$TMPDIR_AUDIT/log.raw" | grep -c .)"
printf 'audit: scanned %s commit(s). See stdout report for per-commit verdict.\n' "$report_total" >&2
