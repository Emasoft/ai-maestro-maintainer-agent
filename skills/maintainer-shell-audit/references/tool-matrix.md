# Tool matrix — shellcheck, shfmt, checkmake, bashate

Every flag below was verified against the binary named, not recalled.
Versions verified: **shellcheck 0.11.0**, **shfmt 3.13.1**. `checkmake`
and `bashate` are not installed on this host — their surface is
documented from their upstream projects and marked as such.

## Table of Contents

- [shellcheck](#shellcheck)
- [shfmt](#shfmt)
- [checkmake](#checkmake)
- [mbake](#mbake)
- [bashate](#bashate)
- [checkbashisms](#checkbashisms)
- [Error handling — when a tool is missing or misbehaves](#error-handling--when-a-tool-is-missing-or-misbehaves)

| Tool | Job | Hard requirement | Verified |
|---|---|---|---|
| shellcheck | Correctness — the defect catalogue | YES | 0.11.0 |
| shfmt | Formatting only — never semantics | no | 3.13.1 |
| checkmake | Makefile structure lint | no | upstream docs |
| mbake | Makefile formatter + syntax validator | no | upstream docs |
| bashate | OpenStack shell style rules | no | upstream docs |
| checkbashisms | POSIX bashism detector for `#!/bin/sh` | no | upstream docs |

They do not overlap by accident. shellcheck asserts *correctness*, shfmt
asserts *shape*. A shfmt-clean script can still delete your home
directory. Run shellcheck first, always; treat shfmt as cosmetic and
never let it reformat a security guard in the same commit as a fix.

## shellcheck

**The invocation the maintainer uses**

```bash
shellcheck -S style -x -f gcc -- path/to/script
```

- `-S style` — the lowest severity, so nothing is hidden. Ranking happens
  in the report, not by suppressing at the tool.
- `-x` — follow `source`d files. Without it, a script that sources a
  helper is audited half-blind.
- `-f gcc` — one finding per line, `file:line:col: level: message [SCxxxx]`.
  Greppable, diffable, and the format CI wants.
- `--` — end of options, so a filename beginning with `-` is a filename.

**Verified flag surface (`shellcheck --help`, 0.11.0)**

| Flag | Long form | What it does |
|---|---|---|
| `-a` | `--check-sourced` | Include warnings from sourced files (not just follow them) |
| `-C[WHEN]` | `--color[=WHEN]` | `auto`, `always`, `never` |
| `-i CODES` | `--include=CODES` | Consider ONLY these codes |
| `-e CODES` | `--exclude=CODES` | Exclude these codes |
| — | `--extended-analysis=bool` | Dataflow analysis (default `true`) |
| `-f FORMAT` | `--format=FORMAT` | `checkstyle`, `diff`, `gcc`, `json`, `json1`, `quiet`, `tty` |
| — | `--list-optional` | List the checks that are OFF by default |
| — | `--norc` | Ignore every `.shellcheckrc` |
| — | `--rcfile=FILE` | Use this rc file instead of searching |
| `-o CHECKS` | `--enable=CHECKS` | Enable optional checks (or `all`) |
| `-P PATHS` | `--source-path=PATHS` | Where to look for sourced files (`SCRIPTDIR` = the script's own dir) |
| `-s SHELL` | `--shell=SHELL` | Force a dialect: `sh`, `bash`, `dash`, `ksh`, `busybox` |
| `-S SEVERITY` | `--severity=SEVERITY` | Minimum reported: `error`, `warning`, `info`, `style` |
| `-x` | `--external-sources` | Allow following `source` outside the given FILES |
| `-W NUM` | `--wiki-link-count=NUM` | How many wiki links to print |

`-f diff` is worth knowing: it emits a unified diff of the fixes
ShellCheck is confident about, which can be piped into `git apply`.
Review it — it is confident, not infallible.

**Severity ladder**

`error` > `warning` > `info` > `style`. The maintainer's gate:

| Severity | Gate behaviour |
|---|---|
| `error` | Blocks. The script is likely broken as written. |
| `warning` | Blocks. Real defect with a real failure mode. |
| `info` | Report, fix in the same pass if cheap (`SC2086` lives here). |
| `style` | Report only. Never gate a release on style. |

`SC2086` (unquoted expansion) being `info` is a ShellCheck editorial
choice, not a statement about its blast radius. The maintainer treats an
unquoted expansion in a path, a `rm` argument, or a `test` as HIGH
regardless of the severity the tool prints.

**The 11 optional checks (`shellcheck --list-optional`, verified)**

Off by default. Enable with `-o name1,name2` or `enable=` in `.shellcheckrc`.

| Name | What it adds |
|---|---|
| `add-default-case` | Suggest a default case in `case` statements |
| `avoid-negated-conditions` | Suggest removing unnecessary negations |
| `avoid-nullary-conditions` | Suggest explicit `-n` in `[ $var ]` |
| `check-extra-masked-returns` | More places where an exit code is silently masked |
| `check-set-e-suppressed` | Notify when `set -e` is suppressed during a call |
| `check-unassigned-uppercase` | Warn when uppercase variables are unassigned |
| `deprecate-which` | Suggest `command -v` instead of `which` |
| `quote-safe-variables` | Suggest quoting even metacharacter-free variables |
| `require-double-brackets` | Require `[[` in bash/ksh |
| `require-variable-braces` | Suggest braces on every variable reference |
| `useless-use-of-cat` | Flag UUOC |

Two of these are load-bearing for an audit and worth enabling on any
repo that runs guards or release automation:

- **`check-set-e-suppressed`** — directly detects pitfall 1 of the strict
  header (a helper invoked in a tested context runs with `-e` disabled).
  It is the only mechanical check for the single most common "the script
  reported success" bug.
- **`check-extra-masked-returns`** — catches exit codes swallowed beyond
  the `SC2155` case.

Enable them per-repo, not globally, and only after reading what they
report — `require-double-brackets` on a POSIX-`sh` codebase is noise.

**`.shellcheckrc`**

Searched upward from each script's directory. Real directives:

```
# .shellcheckrc — repo root
shell=bash
severity=style
enable=check-set-e-suppressed,check-extra-masked-returns,deprecate-which
external-sources=true
source-path=SCRIPTDIR
disable=SC2312
```

| Directive | Meaning |
|---|---|
| `shell=` | Default dialect when there is no shebang |
| `severity=` | Minimum severity |
| `enable=` | Optional checks to turn on |
| `disable=` | Codes to turn off **repo-wide** |
| `external-sources=true` | Same as `-x` |
| `source-path=` | Where to resolve `source` from; `SCRIPTDIR` is the script's own directory |

`disable=` in `.shellcheckrc` is repo-wide and therefore the most
dangerous line in the file. It is legitimate for exactly one class of
code: one the project has consciously and permanently opted out of across
every file. It is NOT the place to silence a finding in one script — that
belongs at the call site. See
[suppression-policy](suppression-policy.md).

**Inline directives**

```bash
# shellcheck disable=SC2086  # word-splitting is intended: $FLAGS is a flag list
cmd $FLAGS

# shellcheck source=lib/common.sh
. "$(dirname -- "$0")/lib/common.sh"

# shellcheck shell=bash
```

A `disable` directive applies to the **next command**, not the rest of
the file — except at the top of the file (before any command), where it
applies file-wide. That asymmetry is a trap: a `disable` line drifting to
the top of a file during a refactor silently widens from one line to the
whole script.

**Exit codes**

| Code | Meaning |
|---|---|
| `0` | No findings at or above the chosen severity |
| `1` | Findings were reported |
| `2` | Bad usage / could not parse the file |
| `3`/`4` | Fatal internal error |

CI must distinguish `1` (found defects — fail the build) from `2` (could
not run — fail the build LOUDLY, and never as a pass).

**CI wiring**

```yaml
- name: ShellCheck
  run: |
    shellcheck --version
    git ls-files -z | while IFS= read -r -d '' f; do
      case "$f" in *.sh|*.bash) printf '%s\0' "$f" ;; esac
    done | xargs -0 --no-run-if-empty shellcheck -S warning -x -f gcc --
```

Gate CI at `-S warning` (blocking) and run `-S style` locally
(informational). Do not gate a build on style; do not let a `warning`
through.

## shfmt

**Verified flag surface (`shfmt --help`, 3.13.1)**

| Flag | Long form | What it does |
|---|---|---|
| `-l` | `--list` | List files whose formatting differs |
| `-w` | `--write` | Rewrite the file in place |
| `-d` | `--diff` | Print a diff and exit non-zero if it differs |
| `-ln` | `--language-dialect` | `bash`, `posix`, `mksh`, `bats`, `zsh` (default `auto`) |
| `-p` | `--posix` | Shorthand for `-ln=posix` |
| `-s` | `--simplify` | Simplify the code |
| `-i N` | `--indent` | `0` = tabs (default), `>0` = that many spaces |
| `-bn` | `--binary-next-line` | `&&`/`\|` may start a line |
| `-ci` | `--case-indent` | Indent `case` branches |
| `-sr` | `--space-redirects` | Space after redirect operators |
| `-kp` | `--keep-padding` | Keep column alignment |
| `-fn` | `--func-next-line` | Opening brace on its own line |
| `-mn` | `--minify` | Minify (implies `-s`) |

Audit mode is `-d` (diff, non-zero on drift), never `-w`:

```bash
shfmt -d -i 4 -- path/to/script
```

`-s` (simplify) rewrites code, not just whitespace. It is safe in the
common case and still a semantic change — never run it on a guard, and
never in the same commit as a fix.

Settings come from `.editorconfig` when present, which is the right place
for them (one file, every tool).

## checkmake

Not installed here. Upstream: `checkmake/checkmake`. Install from the
platform package manager or the project's pinned Go toolchain (`go install
github.com/checkmake/checkmake/cmd/checkmake@latest`, Go 1.16+) — never by
fetching a script from the network into a shell.

```bash
checkmake Makefile
checkmake --output json Makefile
checkmake --config checkmake.ini Makefile
checkmake list-rules
```

Its rules are structural, and they map directly onto the catalogue:

| Rule | What it asserts |
|---|---|
| `minphony` | A minimum set of phony targets exists (default `all`, `clean`, `test`) |
| `phonydeclared` | Every target that is not a file is declared `.PHONY` |
| `maxbodylength` | A recipe body is not longer than N lines |
| `timestampexpanded` | Timestamps are not expanded at parse time |

When it is absent, `make` itself covers the structural ground:

```bash
make --dry-run --warn-undefined-variables   # parse + undefined-variable audit
make -p --dry-run                            # dump the full rule database
```

`--warn-undefined-variables` is the single highest-value Make flag for an
audit: a typo'd variable in Make expands to the empty string in silence,
and this is the only thing that speaks up.

## mbake

Not installed here. Upstream: `EbodShojaei/bake` (a Python tool,
`pip install mbake`, Python 3.9+). It is the Makefile analogue of shfmt —
a formatter — PLUS a thin syntax validator; the first real Makefile
formatter, so it fills a gap `checkmake` (a structure linter) does not.
Documented from upstream, not verified on this host.

| Command | What it does | Audit use |
|---|---|---|
| `mbake format --check <f>` | Reports whether the file is formatted; does NOT modify | The non-mutating audit pass (exit 0 formatted, 1 needs formatting) |
| `mbake format --diff <f>` | Shows the changes it WOULD make | Review before applying |
| `mbake format <f>` | Rewrites in place (add `--backup` for a `.bak`) | The fix, never in the same commit as a semantic change |
| `mbake validate <f>` | Syntax check via `make --dry-run` | Parse audit; the same ground as §7 of makefile-findings |
| `mbake init` / `mbake config` | Create / show `~/.bake.toml` (or per-project `.bake.toml`) | Configure formatting policy |

Its formatter fixes exactly the mechanical §1 findings: converting
space-indented recipes to tabs (`fix_missing_recipe_tabs`), normalising
assignment/colon spacing, trailing-whitespace, line continuations, and it
can auto-insert and group `.PHONY` declarations
(`auto_insert_phony_declarations`, `group_phony_declarations`). A
`# bake-format off` / `# bake-format on` pair exempts a section.

Two limitations to respect (from upstream): mbake targets GNU Make, so it
may misread POSIX-make syntax, and it does NOT understand `.SUFFIXES:` —
do not let it "fix" a file that relies on either. As with shfmt on a guard,
run the formatter only in a commit that changes nothing else, and treat
`mbake` and `checkmake` as complementary (formatter + structure linter),
not substitutes.

## bashate

Not installed here. Upstream: the OpenStack project. Rules are `E0xx`
(whitespace/indent) and `E04x` (syntax). It overlaps shellcheck heavily
and adds mostly style. Run it ONLY when the entrusted repo already has it
wired — adding a second, overlapping style linter to a repo that did not
ask for one produces churn, not safety.

## checkbashisms

Not installed here. Upstream: the Debian `devscripts` package
(`apt-get install devscripts`). It scans a `#!/bin/sh` script for
bash-only constructs — the `SC30xx` ground plus a few Debian-maintainer
rules. `shellcheck -s sh <file>` already reports the whole `SC30xx`
family, so reach for `checkbashisms` only when the entrusted repo targets
POSIX `sh` and wants an independent second opinion; the deep bashism
catalogue and the cross-shell (`dash`) test are in the
[portability](portability.md) reference.

## Error handling — when a tool is missing or misbehaves

| Error | Action |
|-------|--------|
| `shellcheck` not on PATH | Install it from the platform package manager (Homebrew, apt, dnf) or the project's pinned toolchain. Never fetch a script from the network and pipe it into a shell — that is the very defect this skill audits. Until it is present, the audit is a READ-ONLY review against the catalogue, and the report is `PARTIAL`. |
| `shellcheck` cannot follow a `source` | It resolves paths statically. Add `-x` and, if the path is computed, a `# shellcheck source=…` directive. Do NOT rewrite the script to please the resolver. |
| A code fires only under `-S style` | It is real but LOW. Record it; do not gate the release on it. |
| shfmt wants to reformat a git hook | Formatting a security guard is a diff that hides semantics. Format it only in a commit that changes nothing else, and re-exercise the guard afterwards. |
| `checkmake` not installed | Skip it, note it, and fall back to `make --dry-run` + `make --warn-undefined-variables` plus the catalogue. |
| `mbake` not installed | Skip it, note it; `make --dry-run` covers parse-validation and the catalogue covers structure. Never make the audit depend on it. Do NOT let its formatter touch a `.SUFFIXES:`-reliant or POSIX-make file. |
| `make` reports `*** missing separator` | A recipe line begins with spaces, not a tab. Check with `grep -nP '^ +[^[:space:]]' Makefile` before touching anything else — nothing else in the file parses until this is fixed. |
| A finding fires inside a fixture / intentionally-bad example | Fixtures are excluded from lint by design. Confirm the path is fixture-scoped, then leave it alone. |
| Fixing a finding changes a guard's accept/reject set | STOP. This is rule 3. Report it, propose the semantics-preserving alternative, and never land it silently. |
