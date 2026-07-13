---
name: maintainer-shell-audit
description: 'Audit and harden shell scripts, git hooks and Makefiles that ALREADY EXIST in an entrusted repo — runs shellcheck and shfmt (checkmake and bashate when present), classifies every finding as fix-or-documented-suppress, and re-scans to prove green, never weakening a security guard to satisfy a linter. Trigger with "audit our shell scripts", "shellcheck is failing", "harden this bash script", "lint the git hooks", "why does SC2086 fire", "audit the Makefile", or "make says missing separator".'
license: Apache-2.0
metadata:
  version: "1.0.0"
---

# maintainer-shell-audit — audit and harden existing shell and Make

## Overview

The maintainer inherits shell it did not write: release scripts, CI
steps, git hooks, one-off helpers, and the Makefile that ties them
together. This skill is an AUDIT, not an authoring tool. Authoring
recipes appear only as *remediation templates* — the target is always a
file that already exists.

It catches ten classes of defect — from unquoted expansions (SC2086) and
set-time traps (SC2064) to the common Makefile bugs (`.PHONY`,
`.DELETE_ON_ERROR`, tab-vs-space); the full list is [the audit
checklist](#the-audit-checklist).

Three rules carry the whole skill.

1. **Contract before style.** A finding is only a finding once you know
   what the script IS — a sourced `-e`-less helper, a POSIX-only git hook,
   and a release orchestrator are three risk profiles that trip the same
   codes for different reasons. Read the script end-to-end first.
2. **Fix, or suppress with a documented rationale — never suppress to go
   green.** Silencing a code you have not understood converts a defect
   into a lie. See the suppression-policy reference.
3. **Never weaken a guard to satisfy a linter.** This is the rule that
   outranks the other two, and it exists because of this repo.

This repo is its own worked example. `.githooks/pre-push` is a
process-ancestry push guard — it walks its ancestor process tree for
`scripts/publish.py` and refuses any push not made through the release
orchestrator (not gated on an env var, which is trivially spoofed).
ShellCheck flags it (`SC2221`/`SC2222`: two `case` alternatives, the first
subsuming the second) — both real. The right fix deletes the dead
alternative, leaving the match set **bit-for-bit identical**; broadening
the pattern to "justify" both widens what the guard accepts — a security
regression dressed as a lint fix. Full write-up in the suppression-policy
reference.

> When a linter's advice and a guard's job disagree, the guard wins.
> Report the finding, propose the semantics-preserving fix, and if none
> exists, suppress with the reason written at the call site.

## Prerequisites

- `shellcheck` — **the only hard requirement.** Verified against 0.11.0.
- `git` — to enumerate tracked scripts.
- `shfmt` (3.13.1), `checkmake`, `mbake`, `bashate`, `checkbashisms` — all
  OPTIONAL. `shfmt` formats shell; `checkmake` lints and `mbake` formats +
  validates Makefiles; `bashate` and `checkbashisms` overlap shellcheck
  (the latter for `#!/bin/sh` bashisms, which `shellcheck -s sh` also
  covers). Run each only if the entrusted repo already uses it; the
  tool-matrix reference documents all six.

Never make the audit depend on an optional tool. If one is missing, run
the rest, mark the report `PARTIAL`, and name every tool skipped. A
PARTIAL run never reports PASS.

## Instructions

1. **Discover the targets.** Most shell in a repo has no `.sh`
   extension — git hooks never do. Match on the shebang, not the name:

   ```bash
   git ls-files -z | while IFS= read -r -d '' f; do
     case "$f" in *.sh|*.bash|*.bats) printf '%s\n' "$f"; continue ;; esac
     [ -f "$f" ] || continue
     IFS= read -r line < "$f" || continue
     # *sh* covers sh/bash/dash/ksh/zsh — separate alternatives = dead branches (SC2221)
     case "$line" in \#!*sh*) printf '%s\n' "$f" ;; esac
   done
   ```

   Makefiles hide under several names:

   ```bash
   git ls-files | grep -E '(^|/)(GNUmakefile|[Mm]akefile)(\.[^/]+)?$|\.mk$'
   ```

2. **Read each script end-to-end and classify it.** This decides which
   findings even apply:

   | Script kind | Strict header | POSIX-only |
   |---|---|---|
   | Security guard (pre-push/-commit) | YES — a silent failure means it did not run | often YES |
   | Release orchestrator / publisher | YES | NO — bash is fine |
   | CI step | YES | depends on the runner image |
   | Sourced helper library | NO — `set -e` leaks into the caller | match the caller |
   | Interactive dev utility | YES, but exit codes matter less | NO |

   The distinction that bites most: **a sourced file must not set shell
   options**, because it mutates its caller's shell. A standalone script
   must.

3. **Run the scanner matrix** — shellcheck (is this script correct?),
   shfmt (is it formatted consistently?), checkmake (does the Makefile
   miss structure?), and `make --dry-run` (does it even parse?). Full
   invocations, exit codes, the `.shellcheckrc` surface, and the 11
   verified optional checks are in the tool-matrix reference. The baseline
   pass, at the severity the maintainer cares about:

   ```bash
   shellcheck -S style -x -f gcc -- "$@"
   ```

   `-x` follows `source`d files, `-S style` shows everything, `-f gcc`
   gives one finding per line (greppable, and it is what CI wants).
   shfmt checks formatting without touching the file:

   ```bash
   shfmt -d -i 4 -- "$@"
   ```

4. **Classify every finding** against the shell-findings and
   makefile-findings references (both organised as *what to check → what
   is wrong → how to fix*), by severity: **CRITICAL** — a caller-controlled
   string reaching a shell-execution sink, a bypassable guard, or a secret
   in a script or Make variable; **HIGH** — a missing strict header, an
   unquoted expansion in a path or `rm` argument, an unchecked `cd`, a
   predictable temp path, or a Makefile with no `.DELETE_ON_ERROR`;
   **MEDIUM** — a set-time trap (`SC2064`), `read` without `-r`, looping
   over a directory listing, a missing `.PHONY`, or a masked exit code
   (`SC2155`); **LOW** — backticks, useless cat/echo, formatting drift, a
   missing final newline.

5. **Decide fix vs suppress for each finding**, using the
   suppression-policy reference. A suppression is a claim that the check
   does not apply — never that the finding is inconvenient.

6. **Remediate.** Apply the smallest change that removes the finding at
   its root. Copy-paste fixes are in the hardening-templates reference.
   Never "fix" a finding by deleting the code that triggered it, and never
   by loosening a check the script performs.

7. **Re-scan to prove green.** A fix is not done until the same scanner
   that failed now passes — re-run the step-3 command and paste the clean
   output into the report. A suppression must be proven to actually take
   effect (an ignore that silently fails to match is worse than none). And
   for anything with behaviour (a hook, a guard), a clean lint is NOT proof
   it still works: exercise it — for `.githooks/pre-push`, a direct `git
   push` must still be REFUSED after the edit. Lint proves shape; only
   execution proves the contract.

8. **Report** to `$MAIN_ROOT/reports/maintainer-shell-audit/`:

   ```bash
   MAIN_ROOT="$(git worktree list | head -n1 | awk '{print $1}')"
   DIR="$MAIN_ROOT/reports/maintainer-shell-audit"
   mkdir -p "$DIR"
   REPORT="$DIR/$(date +%Y%m%d_%H%M%S%z)-shell-audit.md"
   ```

## The audit checklist

Ten classes. Each maps to a section of the shell-findings or
makefile-findings reference.

| # | Class | What to check |
|---|---|---|
| 1 | Shebang + dialect | Shebang matches the features used (`#!/bin/sh` with arrays is a bug) |
| 2 | Strict header | `set -euo pipefail` on standalone scripts, absent on sourced ones |
| 3 | Quoting + expansion | Every expansion quoted (`SC2086`, `SC2046`, `SC2068`) |
| 4 | Error propagation | `cd` checked, exit codes not masked (`SC2164`, `SC2155`, `SC2181`) |
| 5 | Cleanup + traps | A `trap … EXIT` expanding at trap time, not set time (`SC2064`) |
| 6 | Temp files | `mktemp` with a template, never a predictable `/tmp/$$` path |
| 7 | Input handling | `read -r`, safe `IFS`, globs guarded against no-match |
| 8 | Injection sinks | No caller-controlled string reaching a shell-execution sink |
| 9 | Makefile structure | `.PHONY`, `.DELETE_ON_ERROR`, `SHELL`, `.SHELLFLAGS`, tabs |
| 10 | Portability | bashisms under `#!/bin/sh`; GNU-only flags on BSD/macOS |

## The strict header

`set -euo pipefail` plus `IFS=$'\n\t'` is the right default for a
standalone script — but a **sourced** helper must NOT set it (it mutates
its caller's shell). It is not magic: `set -e` has four holes that each
produced a real "it succeeded" bug (tested-context suppression, `SC2155`
masking, SIGPIPE under `pipefail`, `"$@"` under `set -u` on bash 3.2), all
with reproductions and fixes in the shell-findings reference (§2).

## Makefile audit

There is no Makefile in this repo — this half is for entrusted downstream
repos that have one. The five findings behind most real Makefile bugs:
missing `.PHONY`; missing `.DELETE_ON_ERROR` (a failed recipe leaves a
fresh-mtime half-output the next `make` trusts); a default `SHELL` with no
`-e` (fix: `SHELL := bash` + `.SHELLFLAGS := -eu -o pipefail -c`); spaces
instead of a tab (`*** missing separator`); and one shell per recipe line
(`cd` does not carry across lines). Full catalogue — expansion operators,
`$$` escaping, special targets and automatic variables, parallel-build
races, the GNU-Make version caveats, and the Make security findings — in
the makefile-findings reference.

## Fix vs suppress

The one rule that must never bend:

> A suppression is a claim that the check does not apply. It is never a
> claim that the finding is inconvenient — and never a way to make a
> guard's linter quiet by making the guard weaker.

A suppression is legitimate only when the code genuinely cannot apply to
this script kind (step 2), the rationale sits on the line above the finding
as `# shellcheck disable=SC####  # <why>` (never in a commit message), it
names exactly ONE code, and every neighbouring check stays ENFORCED. A bare
`disable=`, a repo-wide `.shellcheckrc` blanket, lowering `-S`, or excluding
the file are all forbidden — anything else is a fix. Procedure and worked
example: the suppression-policy reference.

## Output

- `$MAIN_ROOT/reports/maintainer-shell-audit/<ts>-shell-audit.md` — one
  section per script/Makefile: script kind, findings by severity, the
  fix-or-suppress decision with its rationale, and the re-scan proof.
- stdout: the report's absolute path. stderr: one summary line
  (`N scripts, M makefiles, C critical, H high, M medium, L low, S suppressed`).
- Exit `1` if any CRITICAL or HIGH finding remains unfixed; else `0`.

## Error Handling

Tool-absence and scanner-behaviour cases — `shellcheck` missing (the audit
degrades to a READ-ONLY `PARTIAL` review), an unresolved `source`, a
`-S style`-only code, shfmt on a hook, `checkmake` missing, `*** missing
separator`, a fixture-scoped finding, and the STOP case where a fix would
change a guard's accept/reject set (rule 3) — are catalogued with their
exact actions in the tool-matrix reference (its "Error handling" section).

## Examples

The push guard trips the linter:

```
User: "shellcheck is complaining about our pre-push hook"
→ SC2221/SC2222 at .githooks/pre-push:35 — two case alternatives, the
  first subsumes the second. Both REAL.
→ Fix: delete the dead alternative. Match set unchanged — bit-for-bit.
→ Never broaden the pattern to "justify" both — that widens what the
  guard accepts. The guard outranks the linter.
→ Prove it: a bare `git push` is still REFUSED after the edit.
```

Two more, in brief. "audit our shell scripts" → discover by shebang, run
`shellcheck -S style -x`, classify each hit (unchecked `cd` → HIGH,
set-time trap → MEDIUM), fix at the root, re-scan to zero. "make says
missing separator" → the line is space-indented, not tab; fix the tab,
then audit the `.PHONY`/`.DELETE_ON_ERROR`/default-`SHELL` findings the
parse error was hiding.

## Scope

- ONLY reads and edits shell scripts, git hooks, Makefiles, and the lint
  config that governs them (`.shellcheckrc`, `.editorconfig`,
  `checkmake.ini`). Does not run the scripts it audits, except to
  re-exercise a guard whose contract an edit could have changed.
- Does NOT lint JSON/YAML/TOML/`.env`/Dockerfile config
  (`maintainer-config-lint`), audit Dockerfiles (`maintainer-dockerfile-audit`,
  which owns `RUN`-line hygiene), scan git history for secrets
  (`maintainer-secrets-scan` — this skill only catches a credential
  hardcoded in a script or Make variable), or audit GitHub Actions workflow
  YAML (`workflow-fix-safe` / `workflow-bootstrap`, though shell inside a
  `run:` block IS in scope). This skill is the DEEP pass on executable
  shell and Make: correctness, guard semantics, and the fix-vs-suppress
  decision config-lint does not make.
- Never weakens a scanner, a guard, or a gate to make a build pass.

## Resources

Each reference carries its own Table of Contents; its sections are listed
after the link so you can see what is inside before opening it.

- [tool-matrix](references/tool-matrix.md) — shellcheck; shfmt; checkmake; mbake (Makefile formatter + validator); bashate; checkbashisms; Error handling — when a tool is missing or misbehaves.
- [shell-findings](references/shell-findings.md) — Shebang and dialect; The strict header; Quoting and expansion — the highest-yield class; Error propagation; Cleanup and traps; Temp files; Input handling and globs; Injection sinks — the CRITICAL class; Exit codes; Portability; Useless constructs and wrong-operator comparisons.
- [makefile-findings](references/makefile-findings.md) — Structure — the five findings that matter most; Variable expansion — `=` vs `:=` vs `?=` vs `+=`; Recipe-shell semantics; Parallelism and ordering; Portability; Security findings; The verification pass; Special targets and automatic variables.
- [portability](references/portability.md) — Bashisms and their POSIX equivalents; Test-and-comparison portability; POSIX parameter expansion; The array-free rewrite; GNU vs BSD userland; Detecting bashisms mechanically.
- [hardening-templates](references/hardening-templates.md) — The strict preamble (standalone scripts); Cleanup with a trap and mktemp; Checked directory change; Declare-then-assign (unmask the exit code); Safe argument parsing with getopts; Safe file iteration; Array for a command with variable arguments; Makefile preamble; Multi-line recipe that needs one shell; Re-scan proof (paste into the report).
- [suppression-policy](references/suppression-policy.md) — The one rule; When a suppression is legitimate; The decision procedure; Where a suppression lives; The worked example — this repo's push guard (the rule that outranks all others); The forbidden shortcuts (all are "suppress to go green").
- Companion skills: `maintainer-config-lint` (broad multi-format config
  lint), `maintainer-dockerfile-audit` (container images),
  `maintainer-secrets-scan` (secrets in history), `maintainer-fix` (lands
  the remediation).
