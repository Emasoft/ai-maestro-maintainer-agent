# Portability — bashisms, POSIX equivalents, and dialect testing

The deep companion to [shell-findings](shell-findings.md) §10. A
`#!/bin/sh` script is a promise that the file uses ONLY POSIX shell — and
`/bin/sh` is `dash` on Debian/Ubuntu, `ash` on Alpine, and a very old
`bash` in POSIX mode on macOS. A bash-only construct under that shebang is
a latent bug that only fires on the machine whose `/bin/sh` is not bash.
The audit action is always the same: either replace the construct with its
POSIX form, or change the shebang to `#!/usr/bin/env bash` and accept the
bash dependency deliberately.

Every ShellCheck code below (`SC3014`, `SC2166`) was confirmed to fire
against ShellCheck 0.11.0. The `SC30xx` family as a whole is ShellCheck's
POSIX-compliance detector — force it on any suspect file with `-s sh`.

## Table of Contents

- [1. Bashisms and their POSIX equivalents](#1-bashisms-and-their-posix-equivalents)
- [2. Test-and-comparison portability](#2-test-and-comparison-portability)
- [3. POSIX parameter expansion](#3-posix-parameter-expansion)
- [4. The array-free rewrite](#4-the-array-free-rewrite)
- [5. GNU vs BSD userland](#5-gnu-vs-bsd-userland)
- [6. Detecting bashisms mechanically](#6-detecting-bashisms-mechanically)

## 1. Bashisms and their POSIX equivalents

Each row is a construct that works in bash and fails (or is undefined) in
strict POSIX `sh`. The ShellCheck `SC30xx` code fires when the construct
appears under a `sh` shebang or `-s sh`.

| Bash-only construct | POSIX equivalent | Note |
|---|---|---|
| `array=(a b c)` / `${arr[0]}` | positional params `set -- a b c` then `$1`, or a delimited string split on `IFS` | POSIX has no arrays |
| `[[ … ]]` | `[ … ]` (the `test` builtin) | `[[` is bash/ksh only |
| `[ "$a" == "$b" ]` | `[ "$a" = "$b" ]` | `==` is undefined in `[ ]` under `sh` (`SC3014`) |
| `diff <(a) <(b)` (process substitution) | write to temp files, then `diff f1 f2` | no `<( )` in POSIX |
| `echo {1..10}` (brace expansion) | a `seq`/`while` loop, or list the items | no brace expansion |
| `function name { … }` | `name() { … }` | the `function` keyword is non-POSIX |
| `local var=…` | naming convention (`_fn_var`) or careful scoping | `local` is near-universal but not in the POSIX standard |
| `source file` | `. file` | `.` is the POSIX spelling |
| `$RANDOM`, `$SECONDS`, `$BASH_SOURCE`, `$FUNCNAME` | none — avoid, or gate on bash | bash-only special variables |
| `(( i++ ))`, `let i=i+1` | `i=$(( i + 1 ))` | arithmetic-command syntax is bash-only; `$(( ))` is POSIX |
| `read -p`, `read -a`, `read -t` | prompt with `printf` then `read`; loop for the rest | those `read` flags are bash-only |
| `${var,,}` / `${var^^}` (case change) | `tr '[:upper:]' '[:lower:]'` | case-modification expansion is bash 4+ |
| `${var/old/new}` (substitution) | `sed`, or `${var%old}new`-style expansion | pattern-substitution expansion is bash-only |
| `shopt -s extglob` patterns `?( )`, `+( )`, `!( )` | `case` with alternation, or a helper | extended globs are bash-only |
| `&> file` redirect | `> file 2>&1` (`SC3020`) | `&>` is bash-only |
| `echo -e` / `echo -n` | `printf` | `echo` flag behaviour varies across shells |

`#!/usr/bin/env bash` is the honest fix when the script genuinely needs
any of the left column — it finds bash on `PATH` (correct on macOS, where
the modern bash is under a package manager, not the `/bin/bash` 3.2). Use
`#!/bin/sh` only when the file is disciplined to the right column; this
repo's `.githooks/pre-push` is deliberately POSIX for exactly that reason.

## 2. Test-and-comparison portability

| Check | Defect | Code | Fix |
|---|---|---|---|
| `=` not `==` in `[ ]` | `[ "$a" == "$b" ]` under `sh` | `SC3014` | `[ "$a" = "$b" ]` |
| Separate tests, not `-a`/`-o` | `[ p -a q ]` / `[ p -o q ]` — `-a`/`-o` are not well defined | `SC2166` | Two `[ … ]` joined by `&&` (or the OR operator for `-o`) |
| Right operator for the type | `[ "$ver" -gt "2.0" ]` — `-gt` is a NUMERIC operator applied to a version STRING; it errors or misjudges | — | Use string comparison (`=`), or a real version-compare (`sort -V`) |
| Emptiness tested explicitly | `[ $var ]` — unquoted, and ambiguous when empty | — | `[ -n "$var" ]` / `[ -z "$var" ]`, always quoted |

`[ "$a" = x -a "$b" = y ]` is doubly wrong: `-a` is deprecated
(`SC2166`), and the unquoted-operand form can misparse when a value looks
like an operator. Two separate `[ … ] && [ … ]` tests are unambiguous.

## 3. POSIX parameter expansion

These forms are POSIX and work in every shell, so they are the portable
substitute for bash-only string operations — and several are load-bearing
for the strict header (a `${1-}` default is what keeps `set -u` from
tripping on a missing argument).

| Expansion | Meaning |
|---|---|
| `${var:-default}` | use `default` if `var` is unset or null (does not assign) |
| `${var:=default}` | assign `default` if `var` is unset or null |
| `${var:?message}` | error out with `message` if `var` is unset or null — the guard behind `SC2115`'s `"${dir:?}"` fix |
| `${var:+alt}` | use `alt` only if `var` IS set and non-null |
| `${#var}` | length of `var` |
| `${var#pat}` / `${var##pat}` | strip shortest / longest `pat` from the FRONT |
| `${var%pat}` / `${var%%pat}` | strip shortest / longest `pat` from the END |

The `${var:?}` form is the portable way to make a script refuse to run a
dangerous command on an empty variable — it is why `rm -rf "${dir:?}"/`
(shell-findings §3) is safe where `rm -rf "$dir"/` is not.

## 4. The array-free rewrite

When a `#!/bin/sh` script needs a list, the two portable substitutes:

```sh
# 1. positional parameters — the closest thing to an array
set -- one two three
printf '%s\n' "$1"          # one
shift; printf '%s\n' "$1"   # two

# 2. a delimited string split on a scoped IFS
items="one:two:three"
OLD_IFS=$IFS; IFS=:
for item in $items; do printf '%s\n' "$item"; done
IFS=$OLD_IFS                # restore — a leaked IFS breaks later splitting
```

Save and restore `IFS` around the loop; a permanently-changed `IFS` is a
classic "later command splits wrong" bug.

## 5. GNU vs BSD userland

macOS ships a BSD userland; a Linux CI runner ships GNU coreutils. A
script that must run on both either detects the platform or restricts
itself to the intersection.

| Command | GNU (Linux) | BSD (macOS) | Portable approach |
|---|---|---|---|
| `sed -i` | in-place, no suffix | in-place REQUIRES a suffix arg (`-i ''`) | write to a temp file and move it, or branch on platform |
| `readlink -f` | resolves the full path | absent | a `cd`/`pwd -P` helper, or `realpath` where available |
| `grep -P` (PCRE) | present | absent | use `-E` (ERE) instead |
| `date -d` / `date +%s%N` | present | different syntax / no nanoseconds | avoid, or branch |
| `find -printf` | present | absent | `-exec` a formatter |
| `xargs -r` | `--no-run-if-empty` | absent (empty input already skips) | drop `-r` on BSD, or feed a guaranteed non-empty stream |

macOS also ships **GNU Make 3.81** as the system `make`. That predates
`.ONESHELL` and `.SHELLFLAGS` (added in GNU Make 3.82) and the `!=`
shell-assignment operator (GNU Make 4.0). The modern Make preamble in
[hardening-templates](hardening-templates.md) is a GNU Make 4.0+ header;
on a repo that must build with the macOS system `make`, treat those as
unavailable and audit for a simpler, version-safe header. See
[makefile-findings](makefile-findings.md) §5.

## 6. Detecting bashisms mechanically

Two tools turn "read every line for a bashism" into a scan:

- **`shellcheck -s sh <file>`** forces the POSIX dialect regardless of the
  shebang, so the whole `SC30xx` family reports. This is the first pass —
  it is already installed wherever the audit runs.
- **`checkbashisms`** (from the Debian `devscripts` package; documented
  from upstream, not installed on this host) is a dedicated bashism
  detector for `#!/bin/sh` scripts. Run it only when the entrusted repo
  already targets POSIX `sh` and wants a second opinion — it overlaps
  ShellCheck's `SC30xx` and adds a few dpkg-maintainer-specific rules.

And confirm behaviour by RUNNING the script under a genuinely-POSIX shell,
not just linting it: `dash <file>` (the Debian/Ubuntu `/bin/sh`) surfaces
a bashism the linters missed. Never install either tool by piping a
network script into a shell — use the platform package manager.
