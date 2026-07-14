# Makefile findings — check → defect → fix

There is no Makefile in this repo. This catalogue is for the entrusted
downstream repos that have one. It is organised the same way as the shell
catalogue: *what to check, what is wrong, how to fix it.*

`make` semantics are unusual in two ways that account for most Makefile
bugs, so read these two facts first:

1. **Every recipe line runs in its own shell.** `cd build` on one line
   does not affect the next line — the next line starts a fresh shell in
   the original directory.
2. **The default recipe shell is `/bin/sh` with no `-e`.** A command that
   fails in the middle of a recipe is ignored unless it happens to be the
   last command on its line.

Both are fixed by the preamble in
[hardening-templates](hardening-templates.md).

## Table of Contents

- [1. Structure — the five findings that matter most](#1-structure--the-five-findings-that-matter-most)
- [2. Variable expansion — `=` vs `:=` vs `?=` vs `+=`](#2-variable-expansion---vs--vs--vs-)
- [3. Recipe-shell semantics](#3-recipe-shell-semantics)
- [4. Parallelism and ordering](#4-parallelism-and-ordering)
- [5. Portability](#5-portability)
- [6. Security findings](#6-security-findings)
- [7. The verification pass](#7-the-verification-pass)
- [8. Special targets and automatic variables](#8-special-targets-and-automatic-variables)

## 1. Structure — the five findings that matter most

| Check | Defect | Why it bites | Fix |
|---|---|---|---|
| `.DELETE_ON_ERROR:` present | Absent | A failed recipe leaves a half-written target whose mtime is fresh; the next `make` treats it as up to date and skips it | Add `.DELETE_ON_ERROR:` near the top |
| `SHELL` + `.SHELLFLAGS` set | Default `/bin/sh` | A failing command mid-recipe is silently ignored | `SHELL := bash` and `.SHELLFLAGS := -eu -o pipefail -c` |
| Every non-file target `.PHONY` | Missing `.PHONY` | Once a file named `test` exists, `make test` sees it as up to date and stops running | Declare `.PHONY: all build test clean …` |
| Recipe lines start with a TAB | Spaces | `*** missing separator. Stop.` — nothing parses | Convert the leading spaces to a literal tab |
| Multi-line logic joined | One command per line | `cd x` then `run` fails because `run` is in a fresh shell | Join with ` && \` or use `.ONESHELL:` |
| Built-in suffix rules cleared | `.SUFFIXES:` absent | Make scans ~90 built-in implicit rules on every target — slower resolution | Add an empty `.SUFFIXES:` near the top (drops all built-in suffix rules) |

Find the tab-vs-space error before anything else, because until it is
fixed nothing else in the file parses:

```bash
grep -nP '^ +\S' Makefile   # recipe lines that begin with spaces, not a tab
```

`.ONESHELL:` makes an entire recipe run in ONE shell, which fixes the
`cd`-does-not-persist problem — at the cost that a `-` error-ignoring
prefix then applies to the whole recipe, not one line. Prefer `&& \`
joins unless the recipe is long. (`.ONESHELL:` and `.SHELLFLAGS` are GNU
Make 3.82+; see §5 for the version caveat.)

`*** missing separator. Stop.` has TWO causes, not one. The common cause
is a recipe line indented with spaces instead of a tab (the grep above).
The second is a **rule line missing its colon** — `build $(SOURCES)` with
no `:` after the target reads as a malformed line, not a target. If the
grep finds no space-indented recipe lines, look for a target line that
lost its `:`.

`.SUFFIXES:` with no value clears every built-in suffix rule; on a large
tree that is a measurable speed-up, and it makes the Makefile's behaviour
explicit (only the pattern rules you wrote apply). Note the `mbake`
formatter does not understand `.SUFFIXES:` — see
[tool-matrix](tool-matrix.md).

## 2. Variable expansion — `=` vs `:=` vs `?=` vs `+=`

This is the second-biggest source of Makefile surprise. The assignment
operator decides *when* the right-hand side is evaluated.

| Operator | Name | Evaluated | Trap |
|---|---|---|---|
| `=` | Recursive | Every time the variable is USED | `FILES = $(shell find . -type f)` re-runs the command on every reference |
| `:=` | Simple | Once, at definition | The right, predictable default for most variables |
| `?=` | Conditional | Once, only if not already set | For values a caller may override |
| `+=` | Append | Inherits the flavour of the first assignment | Appends recursively if the base was `=` |
| `!=` | Shell | Once, at definition (runs the RHS in a shell) | `SRC != find src -name '*.c'` — but it is GNU Make 4.0+ (and BSD make); ABSENT in GNU Make 3.81, the macOS system make (§5) |

| Check | Defect | Fix |
|---|---|---|
| Deterministic vars use `:=` | `VERSION = $(shell git describe)` re-runs git on every use | `VERSION := $(shell git describe)` |
| Overridable vars use `?=` | `CC = gcc` cannot be overridden cleanly | `CC ?= gcc` |
| No undefined variables | A typo'd variable expands to empty in silence | Run `make --warn-undefined-variables` |

`make --warn-undefined-variables` is the single most valuable audit flag:
Make expands an undefined variable to the empty string without complaint,
so a typo turns `rm -rf $(BUILDIR)/*` into `rm -rf /*`. Only this flag
speaks up.

One more variable trap: **do not reassign Make's own reserved variables.**
Setting `MAKEFLAGS` clobbers the flags Make passes to sub-makes; setting
`MAKE` breaks recursive invocation; `CURDIR`, `.VARIABLES`, `SHELL`, and
`MAKECMDGOALS` are special. Use a distinct name (`BUILD_FLAGS`, not
`MAKEFLAGS`) for your own values, and only append (`MAKEFLAGS +=`) when you
genuinely mean to add a global flag like `--warn-undefined-variables`.

## 3. Recipe-shell semantics

| Check | Defect | Fix |
|---|---|---|
| `$$` for shell variables | `$HOME` in a recipe is Make-expanded (to empty), not shell-expanded | Write `$$HOME` so Make passes a literal `$HOME` to the shell |
| `$(shell …)` timing understood | `$(shell …)` runs at PARSE time, for every reference if the var is `=` | Assign with `:=`, or run the command in the recipe body instead |
| `@` used deliberately | `@` hides the command from output — fine for `echo`, hiding for real work | Keep real build steps visible; `@` only on `echo`/`printf` |
| `-` not hiding failures | `-cmd` swallows the command's failure | Remove the `-` unless the failure is genuinely expected (e.g. `-rm` of a maybe-absent file) |

The `$$` rule catches people constantly: a recipe line `echo $PATH`
prints nothing, because Make consumed `$P` as an (empty) Make variable and
left `ATH`. `echo $$PATH` is what reaches the shell.

## 4. Parallelism and ordering

| Check | Defect | Fix |
|---|---|---|
| Parallel-safe | `make -j` races when targets share an unstated output | Declare the real dependencies, or mark a serial section `.NOTPARALLEL:` |
| Order-only prereqs used | A directory prereq forces rebuilds because its mtime changes | Use an order-only prereq: `target: src \| builddir` |
| No assumed build order | A recipe reads a file another target writes, without declaring the dependency | Add the missing prerequisite so Make sequences them |
| No circular chain | `A: B` and `B: A` — Make prints `*** Circular A <- B dependency dropped.` and silently drops one edge, so the build is subtly wrong | Break the cycle into a linear chain |
| No phony prereq on a file target | A file target lists a `.PHONY` target as a prerequisite — the phony is always "out of date", so the file target rebuilds EVERY run | Depend on the real file the phony produces, not the phony |
| Header/generated deps declared | `%.o: %.c` with no header prereqs — editing a header does NOT rebuild the objects that include it, giving a stale binary | List the headers, or auto-generate deps (below) |

A `-j` race is invisible until CI runs on a many-core machine and fails
one build in twenty. The audit reads every target's recipe for outputs it
touches but does not declare as its own target.

The C/C++ "stale object after a header edit" bug is best fixed not by hand
but by letting the compiler emit the dependency list, which Make then
includes:

```make
DEPDIR := .deps
DEPFLAGS = -MT $@ -MMD -MP -MF $(DEPDIR)/$*.d

%.o: %.c | $(DEPDIR)
	$(CC) $(DEPFLAGS) $(CFLAGS) -c $< -o $@

$(DEPDIR):
	mkdir -p $@

-include $(wildcard $(DEPDIR)/*.d)
```

`-MMD -MP -MF` makes the compiler write a `.d` fragment listing every
header the object depends on; `-include` folds those fragments back in so
the next `make` rebuilds exactly the objects whose headers changed. The
leading `-` on `-include` tolerates the fragments not existing on the
first build.

## 5. Portability

| Check | Defect | Fix |
|---|---|---|
| GNU-only features gated | `$(shell …)`, pattern-specific vars, `:=` are GNU Make | Note the GNU dependency, or restrict to POSIX Make |
| Tools not hardcoded | A compiler or interpreter referenced by a full absolute path instead of by name | `CC ?= gcc` and let `PATH` resolve it |
| Platform commands guarded | `sed -i` / `readlink -f` differ on macOS | Detect the platform or use portable equivalents |
| Make version gated | `.ONESHELL:`, `.SHELLFLAGS`, `!=` on a repo that must build with old make | Those need GNU Make 3.82+ (`.ONESHELL`/`.SHELLFLAGS`) or 4.0+ (`!=`); use a simpler header, or require modern make explicitly |

macOS ships **GNU Make 3.81** as its system `make` — verified on this
host. That version predates `.ONESHELL:` and `.SHELLFLAGS` (GNU Make 3.82)
and the `!=` shell-assignment operator (GNU Make 4.0). The modern strict
preamble in [hardening-templates](hardening-templates.md) is therefore a
GNU Make 4.0+ header: correct on a Linux CI runner or a Homebrew `make`,
but silently ineffective on the macOS system `make`. When a repo must
build with whatever `make` is on the machine, either (a) require a modern
make and document it, or (b) fall back to a `SHELL := bash` line without
`.SHELLFLAGS` and put `set -e` at the top of each multi-line recipe.
Detect the version with `make --version` before assuming a 4.0+ feature.

## 6. Security findings

Described as hazards in prose — never as a runnable dangerous line.

| Check | Defect | Why it bites |
|---|---|---|
| No secrets in variables | A token or password assigned to a Make variable | It lands in the Makefile (often committed) and in any target that echoes the environment |
| No sensitive echo | A debug/`print-env` target that dumps the environment | Prints secrets to CI logs where they are retained |
| Variables quoted in recipes | An unquoted Make variable interpolated into a recipe command | A value containing shell metacharacters is re-parsed by the recipe shell — the Makefile equivalent of the shell injection-sink class |
| Command substitution reviewed | `$(shell …)` whose argument is built from a caller-supplied variable | The caller's value is executed at parse time |
| No network-fetch installs | A target that downloads a script and pipes it into an interpreter | Runs untrusted remote code as part of the build |
| Artifact permissions sane | A recipe that makes an output world-writable | Any local user can tamper with the build product |
| `PATH` not caller-trusting | A recipe that runs a bare tool name with an attacker-influenced `PATH` | A planted binary earlier in `PATH` is executed instead of the real tool |

The injection concern mirrors the shell catalogue's sink class: a Make
variable interpolated unquoted into a recipe is re-parsed by the recipe
shell, so a value carrying shell metacharacters can change what the
recipe runs. Quote every variable used in a recipe command, and treat any
`$(shell …)` whose argument derives from an overridable variable as the
Make analogue of an execution sink — audit where its input comes from.

Install tools inside a recipe only from the platform package manager or a
pinned, checksummed artifact — never by fetching a script from the
network into an interpreter.

**Two safe remediations for the two most common Make security findings.**
Both are shown as the HARDENED shape; the dangerous form is described, not
run.

An overridable variable interpolated into a remote command (the shape is
`ssh host "… git pull origin $(BRANCH)"` where `BRANCH` comes from the
caller) lets a crafted value carrying shell metacharacters change what
runs on the far side. Validate against an allow-list before use:

```make
ALLOWED_BRANCHES := main develop staging
BRANCH ?= main
deploy:
	@echo "$(ALLOWED_BRANCHES)" | grep -wq "$(BRANCH)" || { echo "bad BRANCH=$(BRANCH)" >&2; exit 1; }
	ssh host "cd /app && git pull origin '$(BRANCH)'"
```

A `clean` recipe of the shape "remove everything under a build variable"
becomes catastrophic when that variable is empty or `/`. Guard it — the
same defence as the shell `SC2115` case — and give it a never-empty
default:

```make
BUILD_DIR := build
clean:
	@if [ -z "$(BUILD_DIR)" ] || [ "$(BUILD_DIR)" = "/" ]; then echo "bad BUILD_DIR" >&2; exit 1; fi
	rm -rf "$(BUILD_DIR)"/*
```

For a secret, refuse to run when it is unset rather than hardcoding it,
and never echo it: `@[ -n "$$API_TOKEN" ] || { echo "API_TOKEN unset" >&2;
exit 1; }` reads the token from the environment (`$$` passes it to the
shell), and a leading `@` keeps the command itself off the build log.

## 7. The verification pass

Because `checkmake` is often absent, `make` itself is the fallback
auditor:

```bash
make --dry-run --warn-undefined-variables   # parse + undefined-variable audit
make -n <target>                             # dry-run one target: see the commands, run nothing
make -p --dry-run                            # dump the rule database (every variable, every rule)
```

`make -n` (dry run) is the safe way to see exactly what a recipe would
execute without executing it — the first thing to run on an inherited
Makefile whose targets you do not yet trust. When `checkmake` IS present,
its `minphony` and `phonydeclared` rules mechanise findings §1
(`.PHONY` coverage); see [tool-matrix](tool-matrix.md).

## 8. Special targets and automatic variables

Beyond the five structural findings (§1), GNU Make defines other special
targets an audit should recognise — several change whether a failed or
interrupted build leaves correct state.

| Special target | What it does | When it is a finding |
|---|---|---|
| `.DELETE_ON_ERROR:` | Deletes a target whose recipe failed | Absent → the §1 half-written-output bug |
| `.SUFFIXES:` (empty) | Clears all built-in suffix rules | Absent on a large tree → slower resolution (§1) |
| `.PRECIOUS: <t>` | Protects `<t>` from deletion on error or interrupt | A genuinely expensive-to-rebuild target left unprotected while `.DELETE_ON_ERROR:` is on |
| `.INTERMEDIATE: <t>` | Marks `<t>` as intermediate — auto-deleted after the build | Object files never cleaned up (cosmetic) |
| `.SECONDARY: <t>` | Like intermediate, but KEPT (not auto-deleted) | Use to stop Make deleting a wanted intermediate |
| `.NOTPARALLEL:` / `.NOTPARALLEL: <t>` | Serialises the whole file, or one target's prereqs | The §4 `-j` race fix when real deps cannot be expressed |

`.PRECIOUS` is the deliberate exception to `.DELETE_ON_ERROR:`: keep both,
and list only the targets that are genuinely costly to reproduce.

**Automatic variables** — read every inherited recipe with these in mind;
misreading `$@`/`$<`/`$^` is a common source of "the recipe compiles the
wrong file" bugs:

| Var | Expands to |
|---|---|
| `$@` | The target name |
| `$<` | The FIRST prerequisite |
| `$^` | ALL prerequisites (duplicates removed) |
| `$?` | Prerequisites NEWER than the target |
| `$*` | The stem that matched a pattern rule's `%` |

`$(CC) -c $< -o $@` compiles the first prerequisite to the target;
`$(CC) -o $@ $^` links all prerequisites. A recipe that writes `$@` where
it means `$<` (or `$^` where it means `$<`) usually still runs — it just
builds the wrong thing — so trace these when a build produces a
surprising artifact.
