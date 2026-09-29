---
trdd-id: d4112f1e-c932-4461-a3ed-869961655b09
title: Per-author trust elevation for maintainer-approval-gate protected paths
column: backburner
review-after: 2026-11-13
created: 2026-05-23T17:35:00+0200
current-owner: maintainer-agent-session
task-type: security
updated: 2026-08-13T12:40:00+0200
---

## TRDD-d4112f1e — Per-author trust elevation for maintainer-approval-gate protected paths

**Filename:** `design/tasks/TRDD-20260523_173500+0200-d4112f1e-per-author-trust-elevation.md`
**Tracked in:** this repo (`design/tasks/` is git-tracked)

## 1. Origin & scope

The rustling-sniffing-melody plan's "Out of scope" section called out a
future extension to the `maintainer-approval-gate` skill:

> GAP-3 details: per-author protected-paths override — the canonical list
> applies uniformly; per-author trust elevation is a future extension.

Today, the gate's protected-paths list (defined at
`skills/maintainer-approval-gate/references/protected-paths.md`,
lines 20–62, canonical list) plus its per-repo additive override at
`.aimaestro/protected-paths.txt` (same file, lines 68–81) apply
**uniformly to every issue author**: if the planned diff touches a
canonical or override path, `CHECK` halts and `VERIFY` will only resume
when `$AUTHORIZED_USER` posts `approve-protected-edit` on the
originating issue (`SKILL.md` lines 36–43; `protected-paths.md`
lines 83–104 for the grammar).

This TRDD specifies the design for an **opt-in, per-author trust
elevation file** that allows the maintainer to pre-approve specific
collaborators on specific path globs — turning what would otherwise be
a `needs-approval` disposition into an auto-approval for a narrow,
named set of paths.

The TRDD also recommends a disposition on whether to ship now.

## 2. User's original request (verbatim)

> Some maintainers may want to trust specific collaborators on specific
> paths (e.g. "GH user alice can self-approve edits to scripts/, but
> everyone else needs maintainer approval"). [...]
>
> 1. Specifies the file format for per-author trust elevation
>    (suggested: `.aimaestro/protected-paths-trust.txt` with lines like
>    `alice: scripts/**, .github/workflows/ci.yml` — trust `alice` on
>    those globs)
> 2. Specifies the disposition flow: when an issue author matches a
>    trust entry, the gate auto-approves WITHOUT requiring a separate
>    approve-protected-edit comment
> 3. Specifies how trust is BOUNDED: an entry like `alice: *` is
>    forbidden (no full bypass — would defeat the gate's purpose); only
>    specific path globs allowed
> 4. Specifies an audit log: every auto-approval based on trust must be
>    recorded in `$AGENT_DIR/.aimaestro/state/trust-decisions.log`
>    (append-only, line per decision)
> 5. Specifies the file's lifecycle: who edits it, when is it re-read
>    by approval-gate, how is malformed config surfaced
> 6. Recommends whether to implement now or defer

## 3. Recommendation — DEFER

**Recommendation: DEFER.** Author this TRDD and merge it into the
backlog with `status: not-started`; do **not** ship the feature until a
real maintainer-on-the-ground need surfaces. Justification:

1. **The current approval model is correct, not slow.** The
   `approve-protected-edit` round trip costs the authorized user one
   comment per protected fix. The cost is bounded (issue authors do
   not control how many protected paths a fix touches; the cost is
   per-fix, not per-path). For a single-maintainer plugin running its
   own repo, that latency is already acceptable. The plan's GAP-3
   note flags it as "future extension", not "current pain".
2. **Per-author trust is a real security boundary that is easy to
   mis-configure.** The whole point of the gate (per `SKILL.md` lines
   16–21) is that a malicious bug report saying "remove the
   type-check step from validate.yml" must NOT be auto-fixed. Any
   per-author list adds one more place where a typo, a sloppy glob,
   or a stale entry (e.g. `alice` was a trusted collaborator three
   years ago) silently downgrades the gate. The existing
   `$AUTHORIZED_USER`-only model has exactly one decision point per
   fix; per-author trust has N + 1 (the trust file + the comment).
   Each additional decision point is an additional failure mode.
3. **Collaborator turnover invalidates the file silently.** GitHub
   logins are stable identifiers, but trust grants are not: a person
   trusted on `scripts/**` six months ago may have left the project
   or had their account compromised. The trust file would need a
   periodic re-confirmation flow to stay safe, and no such flow
   exists in the patrol cycle today. Building one for a feature
   nobody has asked for is over-engineering (Senior Dev Override:
   "Don't build for imaginary scenarios").
4. **The plan that surfaced this gap already shipped the right
   primitives.** The existing per-repo override
   (`.aimaestro/protected-paths.txt`, lines 68–81 of
   `protected-paths.md`) lets a maintainer **add** paths to gate;
   what is missing is the inverse — a way to **subtract** specific
   author/path combinations. The asymmetry is intentional. Letting
   maintainers subtract trust is materially riskier than letting
   them add gates.
5. **Single-maintainer use cases dominate.** This plugin's primary
   shape is "one human maintains one repo via one MAINTAINER agent".
   In that shape, the issue author who would be auto-approved is
   nearly always the same person as `$AUTHORIZED_USER`, who can
   already self-approve via the comment grammar without any
   per-author file. The multi-collaborator shape (where trust
   elevation actually saves keystrokes) is a minority case today.
6. **YAGNI / KISS.** The TRDD design below is fully specified so
   that, when a real maintainer asks for the feature, the
   implementation is a copy-paste away — but until that request
   exists, the codepath would be dead weight in the gate.

The TRDD stays on the board at `column: backburner` (not `superseded`
or `failed`) to keep the design ready. If a maintainer requests the
feature, set `column: todo`, follow §6 below, and ship.

**Parked explicitly, 2026-08-13 — `review-after: 2026-11-13`.** The
`[trdd-drift]` detector flagged this card at 63 days untouched, which
was a fair signal about the BOARD even though the deferral itself is
correct: a card that is waiting on an external trigger is
indistinguishable, from the outside, from one that silently stalled.
`review-after:` is a snooze, not a mute — it suppresses the drift
warning until the date and then lets it fire again, which is the
behaviour wanted here. **The real trigger remains a maintainer asking
for the feature, not the date.** If that request arrives first, act on
it and ignore the date; if the date arrives first, re-confirm the
DEFER above still holds (§3's reasoning is about a single-maintainer
repo — re-check that premise) and re-park it.

*Field note for whoever picks this up:* this card predates TRDD v2, and
paragraphs above still say `status:`. There is no `status:` field in
this card's frontmatter — the state machine is `column:`. Read every
`status: X` in this body as a historical spelling of the column, and
change `column:` when you act.

## 4. Specification (deferred, but fully described)

This section is the authoritative spec for if/when the feature is
implemented. Reading order: §4.1 file format → §4.2 disposition flow
→ §4.3 bounded-trust invariants → §4.4 audit log → §4.5 lifecycle →
§4.6 malformed-config surface.

### 4.1 File format — `.aimaestro/protected-paths-trust.txt`

Location: **inside the maintained repository**, at
`.aimaestro/protected-paths-trust.txt` (sibling of the existing
`.aimaestro/protected-paths.txt` per-repo override defined at
`protected-paths.md` lines 68–81). Living in the maintained repo (not
in `$AGENT_DIR`) means trust grants travel with the repo — a fresh
clone of the maintained repo has the trust file from day one, no
agent-side state to migrate.

Syntax: one trust entry per line, **GitHub login**, then `:`, then a
comma-separated list of **path globs**. `#` starts a comment. Blank
lines are ignored.

```text
# .aimaestro/protected-paths-trust.txt
# Format: <github-login>: <glob1>, <glob2>, ...
# Globs are matched with the same pathlib.PurePath.match semantics as
# the canonical protected list (protected-paths.md lines 109–118).
# An entry permits ALL planned protected hits to be exclusively within
# the listed globs for the named user. See §4.3 for the bounded-trust
# invariants — wildcards-of-everything are rejected at load time.

alice: scripts/**, .github/workflows/ci.yml
bob:   docs/**
```

Encoding: UTF-8, LF line endings (CRLF is normalised on load — but the
load step warns on CRLF because Windows-edited files commonly have
trailing whitespace that breaks glob matching otherwise).

Login normalisation: the GH login on the left of `:` is **trimmed of
whitespace, lowercased**, then compared case-insensitively against
the issue author's login (GitHub logins are case-insensitive). This
means `Alice:`, `alice:`, and `  ALICE  :` all refer to the same
collaborator. The right-hand side is **trimmed but case-sensitive**
because paths on Linux filesystems are case-sensitive.

### 4.2 Disposition flow

When `CHECK` is invoked (per `SKILL.md` lines 32–43), after computing
`HITS` (per `protected-paths.md` lines 121–137), the gate enters an
additional pre-comment step **only if `HITS` is non-empty AND the
trust file is present and well-formed**:

1. Resolve the issue author's GitHub login. The caller (the
   `maintainer-fix` skill) already knows the issue number; the author
   is one `gh issue view N --json author --jq .author.login` away.
2. Look up the author's row in
   `.aimaestro/protected-paths-trust.txt`. Match is
   case-insensitive on the login.
3. If no row matches → fall through to today's behaviour (post the
   `approve-protected-edit` comment, label
   `awaiting-maintainer-approval`, return `needs-approval`).
4. If a row matches → check that **every** entry in `HITS` is matched
   by **at least one** of the user's allowed globs (using the same
   `pathlib.PurePath.match` semantics as the canonical list). This is
   an **AND across the hits**, not an OR — partial trust is no trust.
5. If all `HITS` are covered → emit a `trust-decisions.log` line (§4.4),
   skip the comment, skip the label, and return a NEW disposition
   **`auto-approved-by-trust`**. Caller proceeds with the commit as
   if approved.
6. If at least one hit is NOT covered by the user's globs → fall
   through to today's behaviour (return `needs-approval`) **and**
   emit a `trust-decisions.log` line recording the partial-trust
   denial. The maintainer can then choose to expand the trust file
   manually if the gap is intentional.

`VERIFY` is unchanged: it never needs to consult the trust file
because the trust path is decided at `CHECK` time and never produces
a `needs-approval` disposition. If `CHECK` already returned
`auto-approved-by-trust`, the fix never enters the `VERIFY` loop in
the first place. (This preserves the current SKILL.md output contract
on lines 65–68: `VERIFY` still returns `{mode, status, approver,
approval_comment_url}` exactly as today.)

#### New `CHECK` output

The output schema in `SKILL.md` lines 65–67 gains one new disposition
value, leaving the existing keys untouched:

```json
{
  "mode": "check",
  "hits": ["scripts/publish.py"],
  "action": "auto-approved-by-trust",
  "trust_match": {
    "author": "alice",
    "globs": ["scripts/**"]
  },
  "comment_url": null
}
```

The `comment_url` is `null` because no comment was posted. The
`trust_match` field is the audit trail returned inline.

### 4.3 Bounded-trust invariants (security-critical)

The trust file MUST reject all of the following at load time and
treat the file as malformed (per §4.6) — falling through to today's
behaviour as if the file were absent. The intent is to make
"effectively unlimited trust" impossible to spell.

Forbidden glob expressions (one of these in any user's row → file
rejected with a single specific error):

| Glob | Why forbidden |
|---|---|
| `*` (bare) | Matches every top-level file. Equivalent to "trust on everything in the repo root". |
| `**` (bare) | Matches every path. Full bypass. |
| `**/*` | Matches every path. Full bypass. |
| `*/**` | Matches every path under any top-level dir. Full bypass. |
| Empty string | A row with no globs is a "trust on nothing" — likely a typo of "trust on everything". Reject to surface the mistake. |

Forbidden user expressions (same handling):

| Login | Why forbidden |
|---|---|
| `*` | "Trust everyone". Defeats the gate. |
| Empty string before `:` | Likely a typo. Reject. |
| The string `$AUTHORIZED_USER` literal | Suggests the maintainer was confused about the gate's identity model — `$AUTHORIZED_USER` is already self-trusting via the comment grammar; an entry for them is dead config. Reject to surface the misunderstanding. |

Additional rules:

1. **No leading `/`.** Globs are relative to the repo root, same as
   the canonical list (`protected-paths.md` line 64). A leading `/`
   is rejected as a typo (Unix users sometimes start absolute paths
   with `/`).
2. **No `..`.** A glob containing `..` is rejected — it could escape
   the repo root and would not match anything anyway, so it can only
   be a mistake.
3. **At least one glob per user row.** The empty right-hand side is
   forbidden (see table above).
4. **One row per user.** Duplicate user keys cause file rejection
   (rather than silently merging) because intent is ambiguous
   ("which row is authoritative?") and a typo of an existing user
   would otherwise silently disable the original entry.
5. **The trust file is OPT-IN.** Absence of the file is the safe
   default. There is no implicit trust.
6. **Trust is ADDITIVE within a row, ALL-OR-NOTHING across hits.**
   See §4.2 step 4: partial trust → no trust. This is deliberate —
   trust elevation must be a single boolean decision, not a
   path-by-path split that could leave half the commit gated and
   half not (which would be operationally confusing).

### 4.4 Audit log — `$AGENT_DIR/.aimaestro/state/trust-decisions.log`

Append-only file, one line per decision made by the trust path. Lives
in `$AGENT_DIR/.aimaestro/state/` alongside `processed-issues.json`,
`branch-rules.json`, `guardian-baseline.json`, and
`guardian-state.json` (per the State paths table in
`agents/ai-maestro-maintainer-agent-main-agent.md` lines 108–117).
This keeps the audit trail bundled with the rest of the agent's
governance state for AI Maestro backups + host-to-host migration.

Format: one JSON object per line (JSONL), so `jq -c` /
`grep` / `tail -f` all work.

```json
{"ts":"2026-05-23T17:42:11+0200","issue":42,"author":"alice","hits":["scripts/publish.py"],"globs_matched":["scripts/**"],"decision":"auto-approved-by-trust"}
{"ts":"2026-05-23T17:55:04+0200","issue":47,"author":"bob","hits":["scripts/publish.py",".github/workflows/ci.yml"],"globs_matched":["docs/**"],"decision":"needs-approval-partial-trust"}
{"ts":"2026-05-23T18:10:22+0200","issue":51,"author":"carol","hits":[".gitignore"],"globs_matched":[],"decision":"needs-approval-no-trust-entry"}
```

Required fields per line:

| Field | Type | Source |
|---|---|---|
| `ts` | ISO 8601 + offset string | `date +%Y-%m-%dT%H:%M:%S%z` |
| `issue` | integer | issue number passed to `CHECK` |
| `author` | string | issue author login (lowercased to match file) |
| `hits` | array of strings | paths that triggered the gate |
| `globs_matched` | array of strings | user's globs that covered AT LEAST one hit (empty array if no trust entry exists) |
| `decision` | enum | `auto-approved-by-trust` \| `needs-approval-partial-trust` \| `needs-approval-no-trust-entry` \| `needs-approval-trust-file-malformed` |

Why JSONL instead of a free-form log:
1. **Machine-readable.** `jq` / structured parsers can query the log
   from the patrol-status command without regex'ing.
2. **Append-safe under concurrent writes.** A single
   `printf '%s\n' "$LINE" >> trust-decisions.log` is atomic up to
   `PIPE_BUF` (4096 bytes on Linux/macOS) for one line. Concurrent
   writers cannot interleave bytes mid-line.
3. **Lex-sortable by `ts`.** ISO 8601 with TZ offset sorts
   chronologically on string compare (per the
   `~/.claude/rules/agent-reports-location.md` rationale on line 100).

Retention: the log is **append-only forever**; the agent never
rotates or truncates it. It is the audit trail. If the file grows
large in practice (years of fixes), a separate `trust-decisions-N.log`
rotation TRDD can be authored then. Until that data exists, premature
rotation is over-engineering.

### 4.5 Lifecycle

| Question | Answer |
|---|---|
| **Who edits the file?** | The repo maintainer, via normal git commits to the maintained repo. The file is tracked, reviewed in PRs like any other repo file. The MAINTAINER agent does NOT auto-edit the trust file — that would be a self-elevating loop. |
| **Where does the file live?** | `.aimaestro/protected-paths-trust.txt` at the repo root of the maintained repo (NOT `$AGENT_DIR`). Travels with the repo. |
| **When is it read?** | Lazily, once per `CHECK` invocation. There is no caching of the parsed contents between CHECK calls (parsing one short file is sub-millisecond; caching would introduce a stale-config window for cheap and is not worth the complexity). Each fix gets a fresh read. |
| **How is presence detected?** | `os.path.exists()` on the path. Absence → safe default (today's behaviour, no trust applied). |
| **How is malformed config surfaced?** | See §4.6 — falls through to today's behaviour with a comment on the originating issue alerting the maintainer + a `decision: needs-approval-trust-file-malformed` line in the audit log. |
| **When is the file invalidated?** | Never automatically. The maintainer is responsible for removing stale entries (e.g. when a collaborator leaves). The audit log gives them visibility — if `trust-decisions.log` shows entries for a user they no longer trust, they update the file. |
| **What about per-repo + per-author conflict?** | None possible. The per-repo `.aimaestro/protected-paths.txt` ADDS to the canonical protected list (`protected-paths.md` lines 70–73); the per-author trust file SUBTRACTS from gating only for a specific author. They operate on different axes. |
| **What about the trust-file path being itself protected?** | The trust file lives at `.aimaestro/protected-paths-trust.txt`. The canonical protected-paths list (lines 22–62 of `protected-paths.md`) does NOT currently include `.aimaestro/**`. **This TRDD recommends adding `.aimaestro/**` to the canonical list as part of any future implementation work** (see §6 step 1) so that edits to the trust file itself, the per-repo override file, and any future `.aimaestro/` config require `approve-protected-edit` from `$AUTHORIZED_USER`. This closes the obvious self-elevation loop where a collaborator with trust on `scripts/**` could submit a PR that edits the trust file to grant themselves trust on `.github/**`. |

### 4.6 Malformed-config surface

Malformed config = any of:
- File present but unreadable (permissions / IO error).
- Syntax error on any line (missing `:`, no globs after `:`, etc.).
- ANY bounded-trust invariant from §4.3 violated by ANY row.
- Duplicate user keys.

When malformed, the gate behaves as follows:

1. **Fail closed.** Treat the trust file as absent. Today's
   `needs-approval` disposition is the result of any protected-path
   hit. No trust is granted. This is the **fail-fast** behaviour
   required by the project's iron rule ("No fallbacks, workarounds,
   bypasses or tricks. The code either WORKS as intended, or the
   program EXITS with error.") — except that here, "exits with
   error" is replaced by "produces the strictest possible outcome,
   never the most permissive" because the gate has a strictly
   safer fallback (today's behaviour). The trust file is
   convenience config, not load-bearing code.
2. **Post one warning comment on the originating issue** explaining
   that the trust file at `.aimaestro/protected-paths-trust.txt` is
   malformed and the error message from the parser. Body template:

   ```text
   This fix would modify protected path(s):

   ```
   <HITS>
   ```

   I attempted to consult `.aimaestro/protected-paths-trust.txt` for
   per-author trust elevation but the file is malformed:

   > <PARSER-ERROR-LINE>

   Falling back to the standard approval flow. Reply with
   `approve-protected-edit` (from @$AUTHORIZED_USER) to land this
   commit, OR fix the trust file and re-trigger the fix.
   ```

3. **Emit a `decision: needs-approval-trust-file-malformed` audit
   line** so the maintainer can find the failure in
   `trust-decisions.log` even if they missed the comment.

4. **Do NOT cache the failure.** The next CHECK invocation parses
   afresh. If the maintainer fixed the file between cycles, the
   next fix uses the corrected trust grants.

5. **Never auto-fix the malformed file.** The gate is read-only on
   the trust file. Auto-editing would be a self-elevation loop
   (see §4.5).

## 5. Test scenarios (when implemented)

Each scenario is a single behaviour check. All scenarios run inside
`tests/scenarios/SCEN-NNN_*.scen.md` files when the feature is
implemented; this TRDD lists the scenarios so the author of the
implementation already has the test plan.

| # | Scenario | Expected disposition |
|---|---|---|
| 1 | No trust file; issue from any author touches `.github/workflows/ci.yml` | `needs-approval` (today's behaviour) |
| 2 | Trust file present, author `alice`, globs `scripts/**`; issue from `alice` touches only `scripts/publish.py` | `auto-approved-by-trust`, audit line emitted |
| 3 | Same as #2 but issue from `bob` (no trust row) | `needs-approval-no-trust-entry`, audit line emitted |
| 4 | Trust file maps `alice: scripts/**`; issue from `alice` touches `scripts/publish.py` AND `.github/workflows/ci.yml` | `needs-approval-partial-trust` (the workflow path is not in alice's globs), audit line emitted |
| 5 | Trust file contains `alice: *` | File rejected as malformed at load time, fail-closed, warning comment posted |
| 6 | Trust file contains `alice: scripts/**\n alice: docs/**` (duplicate user) | File rejected, fail-closed |
| 7 | Trust file contains `Alice: scripts/**` (different case); issue from `alice` | Match succeeds (login compare is case-insensitive) |
| 8 | Trust file present, syntactically valid, but file mode is `000` (unreadable) | Fail-closed, warning comment posted |
| 9 | Issue from `$AUTHORIZED_USER` with trust file present | Trust file is consulted normally — but `$AUTHORIZED_USER` is never in the trust file (rejected at load time per §4.3) so falls through to today's behaviour: `$AUTHORIZED_USER` self-approves via the comment grammar |
| 10 | `VERIFY` invocation after `CHECK` returned `auto-approved-by-trust` | `VERIFY` is never invoked in this flow; caller proceeds directly to commit. Test verifies the caller logic skips `VERIFY` when CHECK action is `auto-approved-by-trust`. |
| 11 | Trust file present but issue has no protected hits (`HITS == []`) | Trust file is never consulted. Today's `noop` disposition (`SKILL.md` line 73). |
| 12 | Trust file edits committed in the SAME PR that triggers the fix | The edit to `.aimaestro/protected-paths-trust.txt` would itself match the canonical protected list once `.aimaestro/**` is added (§4.5). The CHECK would gate the self-elevation, so the trust file change requires `approve-protected-edit` from `$AUTHORIZED_USER` first. Test verifies this self-elevation loop is closed. |

## 6. Implementation sketch (if/when undeferred)

If the feature is undeferred:

1. **Add `.aimaestro/**` to the canonical protected-paths list**
   (`skills/maintainer-approval-gate/references/protected-paths.md`,
   line 47 region — under the existing "Plugin-specific" block, add
   a new "Per-repo agent config" block with `.aimaestro/**`). This
   ensures the trust file itself, the per-repo override file, and
   any future `.aimaestro/` config require `$AUTHORIZED_USER`
   approval to edit. Closes the self-elevation loop (§4.5).
2. **Extend `protected-paths.md`** with a new section
   "Per-author trust elevation" placed after the "Per-repo override"
   section (after line 81), specifying §4.1 + §4.3 verbatim.
3. **Extend `SKILL.md`**:
   - In the `## Instructions` `**CHECK**` block (lines 32–43), add
     step 2.5 between today's step 2 (load lists) and step 3 (post
     comment): "If the trust file
     `.aimaestro/protected-paths-trust.txt` exists, parse it. If
     malformed, post the malformed-file warning per §4.6, emit the
     audit line, and continue to step 3 as if no trust file
     existed. Otherwise, look up the issue author; if all `HITS`
     are covered by the user's globs, return
     `auto-approved-by-trust`."
   - In the `## Output` block (lines 64–68), add the new disposition
     value and the `trust_match` field per §4.2.
   - In the `## Error Handling` table (lines 70–77), add rows for
     trust-file-malformed and trust-file-partial-coverage.
4. **Update the helper script** that the CHECK block uses to compute
   `HITS` (the python heredoc on `protected-paths.md` lines 129–136).
   New script signature: takes the planned diff AND the issue author
   login; returns a structured disposition (one of the new
   `decision:` enum values) plus the `globs_matched` array. Keep
   it inline in the heredoc — the script is short enough that
   factoring it into a separate file would create more friction
   than it saves.
5. **Audit log writer**: append-only JSONL writer at
   `$AGENT_DIR/.aimaestro/state/trust-decisions.log`. Touch the
   `agents/ai-maestro-maintainer-agent-main-agent.md` State paths
   table (lines 108–117) to add the new file. Single function: open
   in append mode, write one `json.dumps(...)` line + newline,
   close. No locking primitive — `printf` to a JSONL file is atomic
   per line under `PIPE_BUF`.
6. **Caller (`maintainer-fix` skill) change**: when the gate returns
   `auto-approved-by-trust`, skip the `VERIFY` loop entirely. The
   caller's commit step proceeds immediately. The commit message
   gets a footer noting the trust-elevation:

   ```text
   fix: <description> (closes #<number>)

   Trust-elevated under .aimaestro/protected-paths-trust.txt:
     author: <login>
     globs:  <comma-separated globs that covered the hits>
   ```

   The footer is visible in git log forever, so even if the trust
   file is later edited or removed, the historical audit trail is
   intact in the commit history.
7. **Tests**: implement scenarios #1–#12 from §5 as scenario tests
   under `tests/scenarios/SCEN-NNN_*.scen.md`. Add fixture
   `.aimaestro/protected-paths-trust.txt` files under
   `tests/fixtures/trust-files/` covering well-formed,
   bare-wildcard, duplicate-user, empty-globs, leading-slash,
   `..`-escape, and unreadable-mode cases.
8. **Documentation**: update `agents/ai-maestro-maintainer-agent-main-agent.md`:
   - In the State paths table (lines 108–117), add the audit log
     entry.
   - In the Guardian Mode section (lines 48–77, point 3), append
     a note that CHECK MAY auto-approve under the trust file
     before posting the request comment.
   - In the supply-chain table (line 231), update the gate's row
     to mention `auto-approved-by-trust`.
9. **Release**: minor version bump (additive new feature, no
   breaking changes — the trust file is opt-in and absence
   preserves today's behaviour exactly).

Estimated touch surface: ~5 files in the plugin (SKILL.md,
protected-paths.md, the inline python helper, the main agent
descriptor, the trust-log writer if factored out), plus 12 scenario
tests + their fixtures. Pure new code; no existing tests need
updating because today's `needs-approval` flow is preserved as the
default.

## 7. Security considerations

| Concern | Mitigation |
|---|---|
| Stale trust grants (collaborator left the project) | Audit log gives visibility. No automated invalidation. Maintainer is responsible. Periodic re-review is a manual process — could later be promoted to a quarterly Guardian check, but out of scope for v1. |
| Compromised collaborator account | Out of scope — this is GitHub's account-security problem, not the gate's. The gate inherits GitHub's authentication; if a trusted collaborator's account is hijacked, every protected commit from that account is auto-approved. The maintainer's response is: revert the commits, remove the row from the trust file, force-rotate any leaked secrets. |
| Self-elevation via edits to the trust file | Closed by adding `.aimaestro/**` to the canonical protected list (§6 step 1). Edits to the trust file require `approve-protected-edit` from `$AUTHORIZED_USER`. |
| Path traversal in globs (`..`) | Rejected at load time (§4.3 rule 2). Fails closed. |
| Glob too broad (matches everything) | Bare wildcards rejected at load time (§4.3 table). Subtler "too broad" globs (e.g. `**/*.yml`) are technically allowed and the maintainer's call — the file is a maintainer-edited config, reviewed in PRs. |
| Race: trust file modified between CHECK and commit | The gate parses fresh on every CHECK and never caches; commits happen seconds after CHECK in the same fix run. The race window exists in theory but is bounded by single-fix latency. If the maintainer commits a trust-file edit at the exact moment a fix is mid-run, the worst case is one extra fix using slightly-stale trust state. Subsequent fixes use the new state. |
| Log tampering | The audit log lives in `$AGENT_DIR/.aimaestro/state/`, owned by the agent's working-dir filesystem permissions (per the governance contract in `ai-maestro-maintainer-agent-main-agent.md` lines 79–122). Adversarial access to the agent's working dir is outside the trust boundary of this feature; if an attacker has write access there, they can also edit `processed-issues.json` and silently re-process every issue. Defense-in-depth (read-only filesystem mounts, etc.) is a host-level concern. |
| Comment grammar collision | Trust does NOT use the comment grammar. The `approve-protected-edit` / `reject-protected-edit` strings (`protected-paths.md` lines 83–105) are unchanged. Trust elevation is a pre-comment shortcut, not a comment grammar extension. |

## 8. Out of scope (explicit non-goals)

- **Time-bounded trust** (e.g. "alice trusted on scripts/** until
  2026-06-30"). Adds calendar logic + expiry checks; not needed for
  v1.
- **Trust on specific issue labels** (e.g. "alice trusted on
  scripts/** only when the issue has label `low-risk`"). Adds
  label-state coupling; not needed.
- **Multiple authorised users** (`$AUTHORIZED_USERS` plural). The
  R19.6 model (`SKILL.md` lines 4–8 of the main agent descriptor)
  is one authorised user per agent. Extending that is a separate
  TRDD, not a side effect of this one.
- **Trust file syntax richness** (YAML, TOML, JSON). Plain-text with
  `:` and commas is intentional — it stays diffable, reviewable in
  PRs, and editable without a parser dependency. The maintainer
  reads and writes this file by hand; a richer syntax adds
  marshalling complexity for no human benefit.
- **`reject-by-trust`** (auto-rejecting a specific author). The gate
  is permissive-by-trust, not restrictive-by-trust. Restricting
  specific authors is a triage concern (`maintainer-triage` could
  refuse to enter the fix pipeline at all for blocked authors),
  not a protected-paths concern.
- **Per-team trust** (e.g. "everyone in the `infra-team` GH team is
  trusted on scripts/**"). Requires GH team membership lookup +
  caching + invalidation. Adds substantial complexity for marginal
  benefit over per-user grants. Defer to a separate TRDD if
  requested.

## 9. Acceptance criteria (when undeferred)

This TRDD reaches `status: completed` when:

1. `.aimaestro/protected-paths-trust.txt` (per §4.1) is documented
   in `protected-paths.md`.
2. `.aimaestro/**` is added to the canonical protected paths list.
3. `SKILL.md` describes the `auto-approved-by-trust` disposition in
   both Instructions and Output sections.
4. The CHECK helper script implements §4.2 + §4.3 fully.
5. The audit log writer (§4.4) is in place; the main agent
   descriptor's State paths table mentions the log file.
6. All 12 test scenarios from §5 pass.
7. The main agent descriptor's Guardian Mode + supply-chain table
   reflect the new disposition.
8. A minor version bump is released and the CHANGELOG mentions the
   new feature.

When all 8 are checked, change `status: not-started` to
`status: completed` and bump `updated:` to the implementation date.

## 10. References (in this repo, by line)

- `skills/maintainer-approval-gate/SKILL.md` lines 4–9
  (the description/trigger block).
- `skills/maintainer-approval-gate/SKILL.md` lines 16–21
  (the rationale: "a malicious bug report saying 'remove the
  type-check step from validate.yml' must NOT be auto-fixed").
- `skills/maintainer-approval-gate/SKILL.md` lines 32–43
  (the CHECK instructions, where step 2.5 is inserted).
- `skills/maintainer-approval-gate/SKILL.md` lines 64–68
  (the Output schema, gaining the new `trust_match` field).
- `skills/maintainer-approval-gate/SKILL.md` lines 70–77
  (the Error Handling table).
- `skills/maintainer-approval-gate/references/protected-paths.md`
  lines 20–62 (the canonical protected-paths list).
- `skills/maintainer-approval-gate/references/protected-paths.md`
  lines 64–66 (match semantics: relative to repo root, `**` recursive).
- `skills/maintainer-approval-gate/references/protected-paths.md`
  lines 68–81 (per-repo override mechanism — the additive sibling
  of this TRDD's subtractive trust file).
- `skills/maintainer-approval-gate/references/protected-paths.md`
  lines 83–104 (approval-comment grammar — UNCHANGED by this TRDD).
- `skills/maintainer-approval-gate/references/protected-paths.md`
  lines 109–118 (`pathlib.PurePath.match` semantics, reused for
  trust globs).
- `skills/maintainer-approval-gate/references/protected-paths.md`
  lines 121–137 (the existing CHECK python helper, extended in §6).
- `skills/maintainer-approval-gate/references/protected-paths.md`
  lines 164–185 (the existing VERIFY shell, UNCHANGED).
- `agents/ai-maestro-maintainer-agent-main-agent.md` lines 79–122
  (State paths governance, where the new audit log entry is added).
- `agents/ai-maestro-maintainer-agent-main-agent.md` lines 108–117
  (State paths table — new row for `trust-decisions.log`).
- `agents/ai-maestro-maintainer-agent-main-agent.md` line 231
  (supply-chain table row for the gate, updated to mention the new
  disposition).
- `agents/ai-maestro-maintainer-agent-main-agent.md` lines 48–77
  (Guardian Mode point 3 — protected-edit invariant statement).

Closes (when implemented): GAP-3 from the rustling-sniffing-melody
plan's "Out of scope" list.
