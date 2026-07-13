# Shell findings — check → defect → fix

Organised the way an audit reads: *what to check, what is wrong when the
check fails, how to fix it at the root.* Every ShellCheck code in the
tables below was confirmed to fire against ShellCheck 0.11.0, except the
three marked *(catalogue)* which are documented codes not reproduced on
this host.

## Table of Contents

- [1. Shebang and dialect](#1-shebang-and-dialect)
- [2. The strict header](#2-the-strict-header)
- [3. Quoting and expansion — the highest-yield class](#3-quoting-and-expansion--the-highest-yield-class)
- [4. Error propagation](#4-error-propagation)
- [5. Cleanup and traps](#5-cleanup-and-traps)
- [6. Temp files](#6-temp-files)
- [7. Input handling and globs](#7-input-handling-and-globs)
- [8. Injection sinks — the CRITICAL class](#8-injection-sinks--the-critical-class)
- [9. Exit codes](#9-exit-codes)
- [10. Portability](#10-portability)
- [11. Useless constructs and wrong-operator comparisons](#11-useless-constructs-and-wrong-operator-comparisons)

## 1. Shebang and dialect

The shebang is a contract: it names the interpreter the rest of the file
is allowed to assume. A `#!/bin/sh` file using bash-only features is a
bug that hides until it runs on a machine where `/bin/sh` is `dash`.

| Check | Defect | Code | Fix |
|---|---|---|---|
| Shebang present | No shebang → runs under the caller's shell, whatever that is | — | Add `#!/usr/bin/env bash` or `#!/bin/sh` |
| Features match dialect | `[[ … ]]` under `#!/bin/sh` | `SC3010` | Use `[ … ]`, or change the shebang to bash |
| Features match dialect | Arrays under `#!/bin/sh` | `SC3030`, `SC3037` *(catalogue)* | Use bash, or restructure without arrays |
| Features match dialect | `&>` redirect under `#!/bin/sh` | `SC3020` | Use `> file 2>&1` |

`#!/usr/bin/env bash` finds bash on `PATH` (correct on macOS, where the
modern bash is under Homebrew, not `/bin/bash` which is 3.2). `#!/bin/sh`
is right for a hook that must run in the leanest possible environment —
this repo's `.githooks/pre-push` is deliberately POSIX-portable for
exactly that reason.

## 2. The strict header

A standalone script should fail loudly on the first error, on an
undefined variable, and on any failing stage of a pipeline:

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
```

- `-e` — exit on any unchecked command failure.
- `-u` — treat an unset variable as an error.
- `-o pipefail` — a pipeline fails if any stage fails, not just the last.
- `IFS=$'\n\t'` — split words on newline and tab only, not on spaces, so
  a path with a space does not silently fragment.

A **sourced** helper library must NOT set these — it mutates the shell of
whatever sources it. The audit rule is: standalone gets the header,
sourced does not.

**The four pitfalls of `set -e` (each has caused a real "it succeeded" bug)**

1. **Suppressed in a tested context.** Inside `if …`, a `&&`/`||` chain,
   or after `!`, a command's failure becomes a value and `-e` does not
   fire. A helper invoked as `probe && step` runs with `-e` *disabled
   inside it*. ShellCheck's optional `check-set-e-suppressed`
   (see [tool-matrix](tool-matrix.md)) is the mechanical detector.
2. **Masked by assignment.** `local x="$(may_fail)"` keeps `local`'s exit
   status (zero), so the failure of `may_fail` is invisible. This is
   `SC2155` — declare and assign on separate lines:

   ```bash
   local x
   x="$(may_fail)"   # now this line's failure aborts under -e
   ```

3. **SIGPIPE under pipefail.** A pipeline ending in `… | head -n1` can
   report failure under `pipefail` because the upstream stage was killed
   by SIGPIPE when `head` closed the pipe early. That is not an error.
   When a pipeline legitimately ends early, tolerate the specific stage
   rather than removing `pipefail` wholesale.
4. **`$@` under `set -u` on old bash.** On bash < 4.4 (macOS ships 3.2),
   `"$@"` with zero positional parameters trips `-u`. Guard with
   `${1-}`-style defaults on any script that must run on the system bash.

| Check | Defect | Code | Fix |
|---|---|---|---|
| Header present (standalone) | No `set -e`; a mid-script failure is ignored | — | Add the strict header |
| Header absent (sourced) | `set -e` in a sourced file leaks into the caller | — | Remove it from the library; set it in the entrypoint |
| Assignment masks status | `local x="$(cmd)"` | `SC2155` | Split declare and assign |

## 3. Quoting and expansion — the highest-yield class

An unquoted expansion undergoes word-splitting and glob-expansion. In a
path, a `test`, or an `rm` argument, that is the difference between
"delete one file" and "delete several files chosen by the filesystem".

| Check | Defect | Code | Fix |
|---|---|---|---|
| Every expansion quoted | `$var` unquoted → word-split + glob | `SC2086` | `"$var"` |
| Command substitution quoted | `$(cmd)` unquoted | `SC2046` | `"$(cmd)"` |
| Modern command substitution | Legacy backticks (poor nesting, awkward escaping) | `SC2006` | `"$(cmd)"` |
| Array expansion quoted | `$@` / `${arr[@]}` unquoted | `SC2068` | `"$@"`, `"${arr[@]}"` |
| `rm`/`cp` path guarded | `rm -rf "$dir"/` where `$dir` may be empty → operates on `/` | `SC2115` | `rm -rf "${dir:?dir is empty}"/` |
| `printf` format is a literal | `printf "$fmt"` — a `%` or `\` in the data is interpreted | `SC2059` | `printf '%s\n' "$fmt"` |
| Array assigned safely | `arr=($(cmd))` re-splits on `cmd` output | `SC2207` | `mapfile -t arr < <(cmd)` |
| Array indexed with braces | `$arr[@]` | `SC1087`, `SC2128` | `"${arr[@]}"` |

`SC2086` is ShellCheck's `info` severity, but the maintainer ranks an
unquoted expansion in a path/`rm`/`test` as HIGH — the tool's severity
reflects how often the pattern is harmless, not its worst case.

The one place unquoting is intentional is a deliberately-split flag list
(`cmd $FLAGS` where `$FLAGS` is `"-a -b -c"`). That is the legitimate
`SC2086` suppression — an array (`cmd "${flags[@]}"`) is the better fix,
and the suppression is only correct when an array genuinely cannot be
used. Document it inline; see [suppression-policy](suppression-policy.md).

## 4. Error propagation

A command whose failure is not observed is a silent failure. The two most
common are an unchecked `cd` and an exit code masked by a later command.

| Check | Defect | Code | Fix |
|---|---|---|---|
| `cd` is checked | `cd "$dir"` then work — if `cd` fails, work runs in the wrong directory | `SC2164` | `cd "$dir" \|\| exit 1` |
| Exit code read directly | `cmd; if [ $? -ne 0 ]` — fragile, and `$?` may be a later command's | `SC2181` | `if ! cmd; then …` |
| `read` preserves backslashes | `read line` mangles `\` | `SC2162` | `read -r line` |
| No looping over a listing | a `for` loop over a command-substituted directory listing breaks on spaces/newlines | `SC2045` | Glob: `for f in ./*` |
| No `for` over `find` | a `for` loop over command-substituted `find` output breaks on spaces | `SC2044` | `find … -exec …` or `while IFS= read -r -d ''` |

An unchecked `cd` in a script that then runs `rm` is the canonical
"cleaned the wrong directory" incident. `cd "$dir" || exit 1` costs three
tokens.

## 5. Cleanup and traps

A script that creates temp state must remove it on every exit path,
including signals. The trap must expand its variables **when it fires**,
not when it is set.

| Check | Defect | Code | Fix |
|---|---|---|---|
| Trap installed | No cleanup on exit → temp files leak | — | `trap cleanup EXIT` |
| Trap expands late | `trap "rm -f $tmp" EXIT` — `$tmp` is expanded NOW, at set time | `SC2064` | Single-quote it: `trap 'rm -f "$tmp"' EXIT` |
| Signals covered | Only `EXIT` — a `kill` mid-run skips cleanup on some shells | — | `trap cleanup EXIT INT TERM` |

`SC2064` is subtle and real: double quotes in a `trap` expand at the
moment the trap is registered, so if `$tmp` is empty then (it usually is)
the trap becomes `rm -f` with no argument. Single quotes defer expansion
to fire time, when `$tmp` holds the real path. The canonical shape:

```bash
cleanup() { rm -rf "${workdir:-}"; }
trap cleanup EXIT INT TERM
workdir="$(mktemp -d)"
```

Full template in [hardening-templates](hardening-templates.md).

## 6. Temp files

A predictable temp path (`/tmp/build.$$`, `/tmp/mytool`) is both a race
and a symlink-attack surface: an attacker who pre-creates the path
controls what the script writes to or reads from.

| Check | Defect | Fix |
|---|---|---|
| `mktemp` used | Hardcoded `/tmp/name` or `/tmp/$$` | `f="$(mktemp)"` (file) / `d="$(mktemp -d)"` (dir) |
| Cleanup wired | `mktemp` output never removed | Register the path in the `EXIT` trap (§5) |
| Template safe | `mktemp` with no `XXXXXX` on some platforms | Prefer a bare `mktemp` / `mktemp -d`; if a template is needed it must end in `XXXXXX` |

`mktemp` creates the file atomically with a random name and safe
permissions. `$$` (the PID) is guessable and reused, so it is not a
substitute.

## 7. Input handling and globs

| Check | Defect | Code | Fix |
|---|---|---|---|
| `read -r` | Backslash mangling | `SC2162` | `read -r` |
| Field splitting scoped | Relying on the default `IFS` for parsing | — | Set `IFS` locally for the one `read` |
| Empty glob handled | `for f in *.txt` runs once with the literal `*.txt` when nothing matches | — | `shopt -s nullglob` (bash) or test existence first |
| Glob not misread as flags | A file named `-rf` becomes an option | `SC2035` | `./*` or a `--` separator |

## 8. Injection sinks — the CRITICAL class

The finding here is: **a caller-controlled string reaches a
shell-execution sink.** The sinks are the `eval` builtin, an unquoted
expansion in a command position, and an argument passed through to
another shell (`bash -c`, `ssh host "$cmd"`, `find … -exec sh -c`).

This class is described in prose, not shown as a runnable line, because a
working example would itself be an exploit:

- **The `eval` builtin applied to data.** If the string handed to `eval`
  contains anything derived from a filename, an argument, an environment
  variable, or a network response, the caller can run arbitrary commands.
  The audit action is to determine whether the argument is a compile-time
  constant (acceptable) or reaches back to any external input
  (CRITICAL). The fix is almost always to remove `eval` entirely — arrays
  and parameter expansion cover nearly every legitimate use.
- **Unquoted expansion in command position.** `$cmd` unquoted where a
  command is expected splits on `IFS` and globs — an attacker who
  controls `$cmd` controls the argv. Quote it, or better, express the
  command as an array and expand `"${cmd[@]}"`.
- **Passing data to a nested shell.** `ssh host "do $thing"` and
  `sh -c "$built"` re-parse the string in a second shell. Keep data OUT
  of the code string: pass it as a positional argument to the inner
  shell and reference it as `"$1"` there, so it is never re-parsed.

| Sink | Audit question | Safe shape |
|---|---|---|
| `eval` builtin | Is its argument ever influenced by external input? | Remove it; use arrays / parameter expansion |
| Command-position expansion | Is `$cmd` quoted / an array? | `"${cmd[@]}"` |
| Nested shell (`sh -c`, `ssh`) | Is data interpolated into the code string? | Pass as a positional arg, reference `"$1"` inside |

The single most common "legitimate" reason a script reaches for the
`eval` builtin is a dynamic variable NAME (look up the variable whose name
is held in another variable). That does NOT need `eval`: bash's indirect
expansion `"${!name}"` reads the variable named by `$name` without ever
re-parsing a string as code. Removing the `eval` removes the sink.

Never install tools by fetching a script over the network and piping it
into an interpreter — that is untrusted-code execution, and it is the
exact defect this class audits. Install from the platform package manager
or the project's pinned toolchain.

## 9. Exit codes

A script's exit code is its contract with its caller (a hook, a CI step,
`make`). Conventions:

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | General failure |
| `2` | Misuse (bad arguments) |
| `126` | Found but not executable |
| `127` | Command not found |
| `128+N` | Killed by signal N (`130` = SIGINT) |

| Check | Defect | Fix |
|---|---|---|
| Failure returns non-zero | A script that fails but exits `0` | Let `set -e` propagate, or `exit 1` explicitly |
| Guard's refusal is non-zero | A guard that prints "refused" then exits `0` | The refusal path MUST `exit 1` — this is a correctness bug, not style |

The guard case is the one that matters most in this repo:
`.githooks/pre-push` exits `1` on refusal and `0` only after the
process-ancestry check passes. A refactor that let the refusal path fall
through to `exit 0` would disable the guard while leaving it looking
intact. When auditing any guard, trace every path to its exit code.

## 10. Portability

| Check | Defect | Code | Fix |
|---|---|---|---|
| No bashisms under `sh` | `[[`, arrays, `&>` in a `#!/bin/sh` file | `SC30xx` | Use POSIX equivalents or change the shebang |
| GNU flags gated | `sed -i` / `readlink -f` / `grep -P` differ on BSD/macOS | — | Detect the platform, or use portable equivalents |
| `echo` flags avoided | `echo -e` / `echo -n` are non-portable | — | Use `printf` |

macOS is BSD userland: `sed -i` needs a backup-suffix argument, `readlink
-f` does not exist, `grep -P` is absent. A script that must run on both
macOS and Linux either detects the platform or restricts itself to
portable flags. This repo's hooks run on the maintainer's machines, so
macOS portability is a real constraint, not a hypothetical.

The full bashism-to-POSIX catalogue, the GNU-vs-BSD flag table, POSIX
parameter expansion, the array-free rewrite, and the bashism detectors
(`shellcheck -s sh`, `checkbashisms`, running under `dash`) live in the
[portability](portability.md) reference.

## 11. Useless constructs and wrong-operator comparisons

Low-severity but high-frequency. None is a security bug; each is a signal
the author reached for the wrong tool, and clearing them makes the real
findings easier to see.

| Check | Defect | Code | Fix |
|---|---|---|---|
| No echo wrapping a command substitution | `x=$(echo "$val")` / `cmd $(echo foo)` | `SC2116` | Drop the echo: `x=$val` / `cmd foo` |
| No echo piping into a filter | `echo "$x" \| grep p` spawns a needless process | `SC2005` | Here-string: `grep p <<< "$x"` (bash) or `printf '%s\n' "$x" \| grep p` |
| No useless cat before a filter | `cat f \| grep p` | `SC2002` (OPTIONAL — the `useless-use-of-cat` check, off by default) | `grep p f` or `< f grep p` |
| Test membership with `grep -q` | `[ "$(grep p f)" ]` reads the whole file into a test | — | `if grep -q p f` — exits on the first match |
| Right test operator for the type | `[ "$ver" -gt "2.0" ]` uses a numeric operator on a version string | — | String `=`, or `sort -V` for real version ordering |

`SC2116`/`SC2005` are `note` (info) severity and `SC2002` is off by
default; they are report-and-fix-if-cheap, never a release gate. But an
`echo`-wrapped
command substitution sometimes HIDES a real quoting bug (the echo
re-splits the inner output), so read the surrounding line before deleting
the echo, not after.
