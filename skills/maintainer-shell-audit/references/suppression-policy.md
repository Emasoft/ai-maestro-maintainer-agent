# Suppression policy — fix, or suppress with a reason

A linter finding has exactly two honest outcomes: **fix it**, or
**suppress it with a documented rationale that says why it does not
apply.** There is no third outcome. Silencing a code you have not
understood turns a defect into a lie the next reader believes.

## Table of Contents

- [The one rule](#the-one-rule)
- [When a suppression is legitimate](#when-a-suppression-is-legitimate)
- [The decision procedure](#the-decision-procedure)
- [Where a suppression lives](#where-a-suppression-lives)
- [The worked example — this repo's push guard (the rule that outranks all others)](#the-worked-example--this-repos-push-guard-the-rule-that-outranks-all-others)
- [The forbidden shortcuts (all are "suppress to go green")](#the-forbidden-shortcuts-all-are-suppress-to-go-green)

## The one rule

> A suppression is a claim that the check does not apply to THIS code. It
> is never a claim that the finding is inconvenient — and, for a security
> guard, it is never a way to make the linter quiet by making the guard
> weaker.

## When a suppression is legitimate

ALL of these must hold:

1. **The code genuinely cannot apply.** Not "is annoying here" —
   *cannot*. The intentional-word-splitting `SC2086` on a deliberately
   unquoted flag list is the textbook case, and even there an array is
   the better fix.
2. **The rationale is written where the next reader looks** — inline,
   directly above the finding, as
   `# shellcheck disable=SC####  # <why it does not apply>`. Not in a
   commit message, not in a PR comment, not in your head.
3. **It names ONE code.** A bare `disable=` with no code, lowering `-S`
   to hide a whole severity class, a repo-wide `.shellcheckrc` blanket,
   or excluding the file from lint entirely are all forbidden.
4. **The neighbouring checks stay ENFORCED.** Suppressing one code must
   not quietly take its neighbours down with it.
5. **The suppression is proven to take effect.** An ignore that silently
   fails to match is worse than none — it advertises coverage that is not
   there. Prove it with a control run: the finding fires without the
   directive, and is gone with it.

Anything that fails one of these is a fix, not a suppression.

## The decision procedure

```
Finding fires
  │
  ├─ Is it a real defect in THIS script's contract?
  │     YES → FIX it at the root (hardening-templates.md). Done.
  │     NO  ↓
  │
  ├─ Does the check genuinely not apply to this script kind?
  │     NO  → it is a real defect after all → FIX it.
  │     YES ↓
  │
  ├─ Can the code be removed so the finding never fires?
  │     (e.g. use an array instead of intentional word-splitting)
  │     YES → do that. A removed finding beats a suppressed one.
  │     NO  ↓
  │
  └─ Suppress inline, one code, with the reason. Prove it with a
     control run. Leave the neighbours enforced.
```

## Where a suppression lives

Preferred — inline, applies to the next command only:

```bash
# shellcheck disable=SC2086  # $FLAGS is a deliberately-split flag list; array not viable here
mytool $FLAGS
```

Repo-wide (`.shellcheckrc` `disable=`) is legitimate for exactly one
thing: a code the project has consciously and permanently opted out of
across EVERY file. It is never the place to silence one script's finding
— that widens a one-line decision into a blanket, and the next file that
trips the same code slips through unreviewed.

## The worked example — this repo's push guard (the rule that outranks all others)

`.githooks/pre-push` is this repo's process-ancestry push guard. It walks
its own ancestor process tree looking for `scripts/publish.py`; if the
push did not descend from the release orchestrator, it is refused. The
guard is deliberately NOT gated on an environment variable — an env var
is spoofable, a process tree is not — and it is the ONLY push path in the
repo.

ShellCheck reports two live findings on it, both at line 35, on the
`case` that matches the ancestor's command line:

- `SC2221` — this pattern always overrides a later one on line 35.
- `SC2222` — this pattern never matches because of a previous pattern.

Both are REAL. The two `case` alternatives on that line are
`*python*scripts/publish.py*` and `*python*/scripts/publish.py*`, and the
first already subsumes the second (any string matching the second matches
the first). The second alternative is dead.

**The right fix, and the wrong "fix"**

- **Right:** delete the dead alternative, leaving a single
  `*python*scripts/publish.py*`. The set of command lines the guard
  accepts is **bit-for-bit unchanged** — a semantics-preserving cleanup
  that also clears the linter.
- **Wrong:** "make both alternatives useful" by broadening one of them
  (e.g. dropping `python` so any process whose command line contains
  `scripts/publish.py` matches). That WIDENS what the guard accepts —
  `bash -c "touch scripts/publish.py && git push"` would now pass — which
  is a security regression disguised as a lint fix. The guard's own header
  comment names that exact bypass as something it must reject.
- **Also wrong:** `# shellcheck disable=SC2221,SC2222` with no change.
  The findings are real; suppressing them hides a genuine dead-code
  branch that a future editor might "revive" by widening it — reintroducing
  the bypass the suppression was papering over.

**The principle this establishes**

When a linter's advice and a guard's job disagree, **the guard wins**,
and the only acceptable resolution is one that preserves — or tightens,
never loosens — what the guard accepts. Report the finding, propose the
semantics-preserving fix, and if none exists, suppress inline with the
reason. Never trade the guard's strictness for a green linter.

**Proving the fix**

Lint-clean is NOT proof a guard still works. After editing
`.githooks/pre-push`, re-exercise the contract:

- A bare `git push` (not descended from `publish.py`) must still be
  REFUSED with a non-zero exit.
- A push driven through `scripts/publish.py` must still be ALLOWED.

Only that behavioural check proves the edit preserved the guard. A
diff that keeps the accept/reject set identical AND passes both
exercises is a safe fix; anything else is not.

## The forbidden shortcuts (all are "suppress to go green")

| Shortcut | Why it is forbidden |
|---|---|
| Lower `-S` from `warning` to `error` | Hides an entire severity class, not one finding |
| Repo-wide `disable=` for a one-script finding | Widens a local decision into a blanket the next file inherits |
| Exclude the file from lint | The finding is still there; now nobody sees it |
| Delete the code that triggered the finding | "Fixes" the symptom by removing the function |
| Broaden a guard's match to "justify" a dead branch | Trades security for a green check — the worst outcome |
| Suppress without a control run | Advertises coverage that may not exist |

Every one of these makes a report say PASS while the defect stays. The
maintainer never trades a true finding for a green check.
