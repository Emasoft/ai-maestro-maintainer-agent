# Review Comment Template

The skill posts EXACTLY ONE comment per PR per review run. The
comment body is built via a heredoc so PR-controlled content
never reaches a shell-expansion path. All interpolated variables
are computed by the skill (counts, severity labels, paths) — the
PR's own text is NEVER substituted into shell.

## Table of Contents

- [Header](#header)
- [Per-flag block](#per-flag-block)
- [Footer](#footer)
- [Heredoc invocation](#heredoc-invocation)
- [Markdown invariants](#markdown-invariants)
- [Empty-flags variant](#empty-flags-variant)

---

## Header

```markdown
## Automated PR review (AI-assisted)

| Field | Value |
|---|---|
| PR | #<N> |
| Author | @<author> |
| Triage case | <A|B|C> |
| Files changed | <count> |
| Additions | +<N> |
| Deletions | -<N> |
| Flags | <count> (highest severity: <high|medium|low|none>) |
| Reviewer (human) | @<authorized-user> |
```

The header is constant width — the columns line up across PRs
so the maintainer can scan a queue of review comments quickly.

## Per-flag block

For each flag in `flags[]`, render one block:

```markdown
### [<severity>] <label>

<detail>

<category-specific guidance>
```

Severity emojis are NOT used (per the no-emojis rule). The
`<category-specific guidance>` text is a fixed lookup table by
category number, hardcoded in the skill — NOT interpolated from
PR content:

| Category | Guidance |
|---|---|
| 1 | The workflow security scan surfaced a new finding. Review the [`workflow-scan`](../../workflow-scan/SKILL.md) report linked above. |
| 2 | This file is in the canonical protected-paths list. The PR must include an explicit explanation, and the merge requires `approve-protected-edit` from the authorized maintainer. |
| 3 | Lifecycle scripts execute at install / build time on every developer machine and CI runner. Confirm the script's contents are intentional. The sandbox precheck ran with `--ignore-scripts` so this script has NOT been executed by the agent. |
| 4 | This package was published less than 7 days ago. Typo-squat / account-takeover payloads tend to be very recent. Verify the publisher's identity and pinned signature before merge. |
| 5 | Production code changes should land with tests (or an explicit "no test possible" justification). Deleted tests should be replaced or explained. |
| 6 | Large PRs are harder to review safely. If possible, split into focused PRs (one concern each). |
| 7 | The PR introduces a workflow action that is not yet pinned in `main`. Per the maintainer's GitHub Actions policy, third-party actions (outside `actions/` and `github/`) must be pinned to a full commit SHA. |

## Footer

```markdown
This is the Claude responsible for the ai-maestro-maintainer-agent project.

---

**This is an AI-assisted review. Final approval requires a human
reviewer (@<authorized-user>).** The `maintainer-pr-review` skill
does NOT call `gh pr review --approve` under any circumstance.
```

## Heredoc invocation

The full posting recipe:

```bash
PR="$1"; REPO="$2"
FLAGS_JSON=$(cat /tmp/pr-$PR-flags.jsonl | jq -s .)
FLAG_COUNT=$(echo "$FLAGS_JSON" | jq 'length')
HIGHEST=$(echo "$FLAGS_JSON" | jq -r '
  if length == 0 then "none"
  else max_by(if .severity == "high" then 3 elif .severity == "medium" then 2 else 1 end).severity
  end')

# Render the per-flag blocks separately, then splice into the heredoc.
BLOCKS_FILE=$(mktemp)
echo "$FLAGS_JSON" | jq -r --arg refs "$SKILL_REFS" '
  def guidance(c):
    if c == 1 then "The workflow security scan surfaced a new finding. Review the workflow-scan report linked above."
    elif c == 2 then "This file is in the canonical protected-paths list. The PR must include an explicit explanation, and the merge requires `approve-protected-edit` from the authorized maintainer."
    elif c == 3 then "Lifecycle scripts execute at install / build time on every developer machine and CI runner. Confirm the script's contents are intentional. The sandbox precheck ran with `--ignore-scripts` so this script has NOT been executed by the agent."
    elif c == 4 then "This package was published less than 7 days ago. Typo-squat / account-takeover payloads tend to be very recent. Verify the publisher's identity and pinned signature before merge."
    elif c == 5 then "Production code changes should land with tests (or an explicit \"no test possible\" justification). Deleted tests should be replaced or explained."
    elif c == 6 then "Large PRs are harder to review safely. If possible, split into focused PRs (one concern each)."
    elif c == 7 then "The PR introduces a workflow action that is not yet pinned in `main`. Per the maintainer's GitHub Actions policy, third-party actions (outside `actions/` and `github/`) must be pinned to a full commit SHA."
    else "" end;
  .[] | "### [" + .severity + "] " + .label + "\n\n" + .detail + "\n\n" + guidance(.category) + "\n"
' > "$BLOCKS_FILE"

# Build the final comment body. NO PR-controlled content is
# substituted via $(...) — only counts and pre-rendered flag
# blocks.
BODY_FILE=$(mktemp)
cat > "$BODY_FILE" <<HEADER
This is the Claude responsible for the ai-maestro-maintainer-agent project.

## Automated PR review (AI-assisted)

| Field | Value |
|---|---|
| PR | #${PR} |
| Author | @${AUTHOR} |
| Triage case | ${CASE} |
| Files changed | ${CHANGED_FILES} |
| Additions | +${ADDITIONS} |
| Deletions | -${DELETIONS} |
| Flags | ${FLAG_COUNT} (highest severity: ${HIGHEST}) |
| Reviewer (human) | @${AUTHORIZED_USER} |

HEADER

cat "$BLOCKS_FILE" >> "$BODY_FILE"

cat >> "$BODY_FILE" <<FOOTER

---

**This is an AI-assisted review. Final approval requires a human
reviewer (@${AUTHORIZED_USER}).** The \`maintainer-pr-review\`
skill does NOT call \`gh pr review --approve\` under any
circumstance.
FOOTER

# Post the comment (with the retry loop from
# ~/.claude/rules/github-timeouts.md).
i=0
until GH_HTTP_TIMEOUT=300 gh pr comment "$PR" --repo "$REPO" --body-file "$BODY_FILE"; do
  i=$((i+1)); [ $i -ge 30 ] && exit 1; sleep 6
done

# Optional: attach as a formal review (NEVER --approve).
# GH_HTTP_TIMEOUT=300 gh pr review "$PR" --repo "$REPO" --comment --body-file "$BODY_FILE"

# Save a copy under reports/ for the audit trail.
MAIN_ROOT="$(git worktree list | head -n1 | awk '{print $1}')"
REPORT_DIR="$MAIN_ROOT/reports/maintainer-pr-review"
mkdir -p "$REPORT_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S%z)"
cp "$BODY_FILE" "$REPORT_DIR/$TIMESTAMP-pr-$PR-comment.md"
```

## Markdown invariants

- The header table column widths are fixed by the per-PR data —
  do NOT pad with leading/trailing whitespace; GitHub renders
  pipes regardless.
- Per-flag blocks use H3 (`###`), never H1/H2 (the comment lives
  inside an issue/PR thread; H1/H2 would compete with GitHub's
  own headings).
- The footer's "AI-assisted review" sentence is verbatim — the
  patrol ledger greps for that phrase to verify the skill ran
  (audit trail).
- No emojis anywhere in the comment.
- All `$VAR` substitutions in the heredoc are agent-computed
  (counts, severity, user logins from `gh api user`) — NEVER the
  PR's title, body, commit messages, or comments. Those reach
  the comment only via the per-flag `detail` field, and each
  detail is jq-escaped at the JSON layer before reaching the
  shell.

## Empty-flags variant

When `flag_count == 0`, the per-flag section is replaced with a
single line:

```markdown
No automated flags. The diff passed the 7-category checklist.
```

The header and footer are unchanged. The comment STILL gets
posted (the "review ran" audit trail relies on its presence).
