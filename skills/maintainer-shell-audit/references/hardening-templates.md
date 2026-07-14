# Hardening templates — copy-paste remediations

These are *remediation templates*: the shape a hardened script or
Makefile takes AFTER an audit fixes a finding. The target is always a
file that already exists — apply the smallest piece that removes the
finding, never a wholesale rewrite. None of these fetch anything from the
network or run untrusted input.

## Table of Contents

- [The strict preamble (standalone scripts)](#the-strict-preamble-standalone-scripts)
- [Cleanup with a trap and mktemp](#cleanup-with-a-trap-and-mktemp)
- [Checked directory change](#checked-directory-change)
- [Declare-then-assign (unmask the exit code)](#declare-then-assign-unmask-the-exit-code)
- [Safe argument parsing with getopts](#safe-argument-parsing-with-getopts)
- [Safe file iteration](#safe-file-iteration)
- [Array for a command with variable arguments](#array-for-a-command-with-variable-arguments)
- [Makefile preamble](#makefile-preamble)
- [Multi-line recipe that needs one shell](#multi-line-recipe-that-needs-one-shell)
- [Re-scan proof (paste into the report)](#re-scan-proof-paste-into-the-report)

## The strict preamble (standalone scripts)

```bash
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'
```

Apply to a standalone script that lacks it. Do NOT apply to a sourced
helper library — it would mutate the caller's shell (see
[shell-findings](shell-findings.md) §2). For a script that must run on
macOS's system bash 3.2, guard `"$@"` uses with `${1-}` defaults so
`set -u` does not trip on zero arguments.

## Cleanup with a trap and mktemp

Fixes the temp-file class (§6) and the trap class (§5) together. The trap
is single-quoted so it expands at fire time, not set time (`SC2064`), and
it covers signals, not just a clean exit.

```bash
#!/usr/bin/env bash
set -euo pipefail

workdir=""
cleanup() { [ -n "$workdir" ] && rm -rf "$workdir"; }
trap cleanup EXIT INT TERM

workdir="$(mktemp -d)"
# … use "$workdir" …
```

`cleanup` reads `$workdir` when it FIRES, so declaring the variable empty
first means an early signal (before `mktemp` ran) cleans up nothing
rather than erroring.

## Checked directory change

Fixes `SC2164`. An unchecked `cd` that fails leaves the script running in
the wrong directory — with `rm` or `git` in the recipe, that is a real
incident.

```bash
cd "$target_dir" || exit 1
# subshell form when the change should be local:
( cd "$target_dir" && do_work )
```

## Declare-then-assign (unmask the exit code)

Fixes `SC2155`. `local`/`export`/`readonly` on the same line as a command
substitution swallow the command's exit status.

```bash
# before:  local out="$(may_fail)"     # failure hidden
local out
out="$(may_fail)"                       # failure now propagates under -e
```

## Safe argument parsing with getopts

`getopts` handles bundled flags and `--` correctly, unlike a hand-rolled
`case` over `$1`.

```bash
usage() { printf 'usage: %s [-v] [-o FILE] ARG\n' "$0" >&2; exit 2; }

verbose=0
outfile=""
while getopts ':vo:' opt; do
  case "$opt" in
    v) verbose=1 ;;
    o) outfile="$OPTARG" ;;
    :) printf 'option -%s needs an argument\n' "$OPTARG" >&2; usage ;;
    \?) printf 'unknown option -%s\n' "$OPTARG" >&2; usage ;;
  esac
done
shift "$((OPTIND - 1))"
[ "$#" -ge 1 ] || usage
```

## Safe file iteration

Never loop over a directory listing (`SC2045`) or over command-substituted
`find` output (`SC2044`) — both break on spaces and newlines. Two safe
forms:

```bash
# glob (bash) — nullglob so an empty match yields zero iterations, not the literal
shopt -s nullglob
for f in ./*.txt; do
  process "$f"
done

# find + read, null-delimited — survives any filename
find . -type f -name '*.txt' -print0 |
while IFS= read -r -d '' f; do
  process "$f"
done
```

## Array for a command with variable arguments

The correct fix for the "intentional word-splitting" `SC2086` case: build
an array, expand it quoted.

```bash
args=()
[ "$verbose" -eq 1 ] && args+=(--verbose)
args+=(--output "$outfile")
mytool "${args[@]}"          # each element stays one argument
```

## Makefile preamble

Fixes findings §1 (structure) in one block at the top of the Makefile.
The recipe shell becomes bash with the strict flags, a failed recipe
deletes its half-written target, and undefined variables warn.

```make
SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables --no-builtin-rules
.DEFAULT_GOAL := help

.PHONY: all build test clean help
```

- `SHELL`/`.SHELLFLAGS` — every recipe runs under bash with `-e`, so a
  mid-recipe failure aborts the target.
- `.DELETE_ON_ERROR:` — a failed target is removed, so the next `make`
  rebuilds it instead of trusting a half-written file.
- `--warn-undefined-variables` — a typo'd variable is announced, not
  silently expanded to empty.
- `--no-builtin-rules` — drops Make's implicit rules, so behaviour is
  explicit and parsing is faster.
- `.PHONY` — every target that is not a real file, so none is skipped
  when a like-named file appears.

## Multi-line recipe that needs one shell

Because each recipe line is its own shell, a `cd` does not persist. Two
fixes:

```make
# join with && and a line-continuation — one shell for the whole thing
release:
	cd build && \
	./package.sh && \
	./upload.sh

# or opt the whole recipe into a single shell
.ONESHELL:
release:
	cd build
	./package.sh
	./upload.sh
```

## Re-scan proof (paste into the report)

A fix is not done until the scanner that failed now passes.

```bash
shellcheck -S style -x -f gcc -- path/to/script     # expect: no output, exit 0
shfmt -d -i 4 -- path/to/script                     # expect: no diff, exit 0
make --dry-run --warn-undefined-variables           # expect: no undefined-variable warnings
```

For any script with behaviour — a hook, a guard — a clean lint is not
proof it still works. Re-exercise the contract: for a push guard, confirm
a direct push is still refused after the edit. See
[suppression-policy](suppression-policy.md) for why that step is
non-negotiable on a guard.
