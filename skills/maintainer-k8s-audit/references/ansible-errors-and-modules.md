# Ansible — error signatures, module migrations, extra findings

The companion to [ansible-audit.md](ansible-audit.md). That file is the
finding catalogue (secrets, idempotency, privilege, pinning); this one is
the triage layer — the exact failing-output SIGNATURES an auditor reads
off `ansible-playbook` / `ansible-lint`, the deprecated-module → collection
moves that turn a "module not found" into a fix, and the security findings
the base catalogue does not carry.

## Table of Contents

- [Error signatures — output → cause → fix](#error-signatures--output--cause--fix)
- [Deprecated modules — collection moves and removal timeline](#deprecated-modules--collection-moves-and-removal-timeline)
- [Scanner IDs, tool floors, molecule and inventory](#scanner-ids-tool-floors-molecule-and-inventory)
- [Additional security findings and remediations](#additional-security-findings-and-remediations)

## Error signatures — output → cause → fix

An auditing pass reads failing output as often as it reads the source.
Each row is a verbatim signature the tool emits, the real cause, and the
fix. Present these as the diagnosis when a run fails — do not re-derive
them.

### YAML / parse

| Signature (verbatim) | Cause | Fix |
|---|---|---|
| `mapping values are not allowed here` | an unquoted `:` inside a value (`db_host: localhost:5432`) | quote the whole value |
| `could not find expected ':'` | a key with no colon, or bad indentation | add the colon; fix indentation |
| `found undefined alias 'anchor'` | a YAML `*alias` used before its `&anchor` is defined | define the anchor above its first use |
| `Unable to parse <src> as an inventory source` | INI and YAML inventory styles mixed in one file | one style per inventory file |

### Module / task

| Signature (verbatim) | Cause | Fix |
|---|---|---|
| `Unsupported parameters for (<module>) module: <name>` | a wrong or misspelled parameter | confirm the real params with `ansible-doc <module>` |
| `missing required arguments: <name>` | a required module parameter omitted | supply the argument |
| `MODULE FAILURE ... module_stderr` | no Python on the target, wrong interpreter, or SELinux blocking | set `ansible_python_interpreter` to the target's python3 |
| `This module does not support check mode` | a task that cannot dry-run was run under `--check` | set `check_mode: no` on that one task |
| `The requested handler '<name>' was not found` | a `notify:` string that does not match a handler name (exact, case-sensitive) | make the `notify:` string byte-identical to the handler `name:` |

### Templating / variables

| Signature (verbatim) | Cause | Fix |
|---|---|---|
| `template error while templating string` / `unhandled exception occurred while templating` | an undefined var, a bad filter, or Jinja2 syntax | guard with `default()`, `required()`, or `when: x is defined` |
| `The task includes an option with an undefined variable` | a variable referenced before it is set | same guards as above |
| `Unexpected templating type error` | a value used as the wrong type | coerce with `\| int` / `\| string` / `\| bool` |
| `Invalid data passed to 'loop', it requires a list` | a `loop:` fed a string instead of a list | wrap in a list, or split the string |
| `with_items is deprecated, use loop instead` | the deprecated loop keyword | rewrite to `loop:` (a MEDIUM finding, `ansible-lint --fix` does not do this one) |

### Connection / privilege

| Signature (verbatim) | Cause | Fix |
|---|---|---|
| `UNREACHABLE! ... Failed to connect to the host via ssh` | host down, wrong user/key, or SSH unreachable | probe with `ansible <host> -m ping` first |
| `Permission denied (publickey)` | the control key is not on the target | `ssh-copy-id`, or set `ansible_ssh_private_key_file` |
| `Missing sudo password` / `Authentication or permission failure` | become needs a password not supplied | `--ask-become-pass` (or a scoped NOPASSWD sudoers rule); vault the creds |

### Includes / collections / inventory

| Signature (verbatim) | Cause | Fix |
|---|---|---|
| `Unable to retrieve file contents. Could not find or access '<file>'` | an include/import path wrong (it is relative to the playbook) | correct the path |
| `Recursively included/imported file is causing infinite loop` | a circular include (A imports B imports A) | break the cycle |
| `couldn't resolve module/action '<fqcn>'` | the collection providing that FQCN is not installed | `ansible-galaxy collection install <ns.coll>` |
| `Requirement already satisfied by a different version` | a collection version conflict | pin `name: <ns.coll>` + `version:`, or reinstall with `--force` |
| `Invalid characters were found in group names` | a hyphen or space in an inventory group name | use underscores (`[web_servers]`) |
| `Could not match supplied host pattern` | the host group named on the CLI is not defined in the inventory | define the group, or correct the pattern |

## Deprecated modules — collection moves and removal timeline

Two views of the same shift: which FQCN a bare module becomes, and which
core version removed the bare name so a "module not found" maps to a fix.

### Deprecated module → collection replacement

Since Ansible 2.10 most modules moved out of core into collections. A
playbook calling the short, in-core name still "works" until the core
version that removed it — then it fails with `couldn't resolve
module/action`. The audit flags the bare name and names the FQCN it must
become. `ansible-lint` reports these under its `fqcn` rules; the moves
themselves:

| Bare / deprecated module | FQCN replacement |
|---|---|
| `easy_install` | `ansible.builtin.pip` (easy_install is dead in modern Python) |
| `sysvinit` | `ansible.builtin.service` |
| `yum` (RHEL/CentOS 8+) | `ansible.builtin.dnf` (keep `yum` only for RHEL/CentOS 7) |
| `synchronize`, `acl`, `authorized_key`, `firewalld` | `ansible.posix.*` |
| `homebrew`, `zypper`, `apk`, `ufw`, `nagios` | `community.general.*` |
| `docker_container`, `docker_image` | `community.docker.*` |
| `mysql_db` / `mysql_user` | `community.mysql.*` |
| `postgresql_db` / `postgresql_user` | `community.postgresql.*` |
| `mongodb_*` | `community.mongodb.*` |
| `zabbix_*` | `community.zabbix.*` |
| `ec2`, `ec2_ami`, `ec2_vpc` | `amazon.aws.ec2_instance` / `ec2_ami` / `ec2_vpc_net` |
| `azure_rm_*` | `azure.azcollection.*` |
| `gcp_*` | `google.cloud.*` |

Enumerate every deprecated-module rule the installed linter knows with
`ansible-lint -L | grep deprecated`. When a module is flagged, the fix is
the FQCN AND a `requirements.yml` entry pinning the collection that
provides it (see the pinning table in ansible-audit.md).

### Module removal timeline

Tie a "module not found" to the core version, so the fix is "install the
collection" and not "guess":

| Ansible core | State |
|---|---|
| 2.9 | last release with most modules IN `ansible.builtin` |
| 2.10+ | collections split out of core; bare names still resolve via the `community.general` bridge |
| **2.12+** | many deprecated modules **removed from core** — the bare name now fails |
| 2.14+ | FQCN strongly recommended; `ansible-lint --profile production` requires it |

## Scanner IDs, tool floors, molecule and inventory

Extra checks the base chain does not surface — the scanner IDs and version
floors, plus the molecule, check-mode and inventory audit.

### Extra scanner IDs, tool floors and flags

- **Checkov beyond the core Ansible IDs.** `CKV2_ANSIBLE_3` fires on a
  `block:` with no `rescue:` (unhandled error path). When a playbook
  *provisions cloud resources*, `checkov --framework ansible` also raises
  the provider resource checks — e.g. `CKV_AWS_88` (an EC2 instance with a
  public IP) and `CKV_AWS_135` (EC2 not EBS-optimized) — because the
  rendered resource, not just the task, is graded. Suppress one ID with
  `checkov -d . --framework ansible --skip-check CKV_ANSIBLE_1` (only with
  a WHY, per the suppression rule in scanner-toolchain.md).
- **Tool-version floors.** Audit with `ansible-lint` >= 6.0.0 (the profile
  model and rule-tag syntax below only exist from 6), `yamllint` >= 1.26.0,
  and `molecule` >= 3.4.0. An older `ansible-lint` silently lacks rules —
  record the version in the report so a green result is interpretable.
- **Rule-scoped skips and tag filters.** `ansible-lint -x yaml[line-length]`
  skips ONE sub-rule (the bracketed `[sub-id]`) rather than the whole
  `yaml` rule — the precise, documented way to silence a single noisy
  check. `ansible-lint -t yaml,syntax` restricts the run to those rule
  tags. Both beat disabling a rule wholesale.

### Molecule, check-mode and inventory audit

- **Molecule exit-code contract.** A molecule test wrapper distinguishes
  `2` = BLOCKED (the environment could not run it — container runtime down,
  no driver) from `1` = FAIL (the role/test genuinely failed) and "no
  `molecule/` directory" = SKIPPED. Do not read a BLOCKED as a PASS or as a
  role failure — it means the audit could not run, the same trap as
  `ansible-lint` exit `1` vs `2`.
- **`idempotence` is a named molecule stage.** Molecule's default test
  sequence converges twice and asserts the second `converge` reports zero
  `changed` — the two-run idempotency proof from ansible-audit.md as a
  built-in gate. A role that ships a `molecule/` scenario already has this
  check; a role without one is relying on manual proof.
- **`ansible_check_mode` magic variable.** Force a read-only task to run
  even under `--check` with `check_mode: no`; skip a task in dry-run with
  `when: not ansible_check_mode`. Useful when a `--check --diff` audit run
  stalls on a task that cannot dry-run.
- **Inventory-file audit.** The inventory is source too: flag a plaintext
  password in any inventory file (CRITICAL, same as a vars-file credential),
  and flag `localhost` reached without `ansible_connection=local` (it
  round-trips through SSH to itself). Verify host/group resolution with
  `ansible-inventory --list` / `ansible-inventory --graph` before trusting
  a `hosts:` pattern.

## Additional security findings and remediations

Findings the base catalogue in ansible-audit.md does not carry, each a
proposed change (they alter behaviour), not an auto-fix:

| Finding | Sev | Why / fix |
|---|---|---|
| a config write (`copy`/`template`) of a critical file with no `validate:` and no `backup:` | MEDIUM | a bad render is deployed with no syntax gate and no rollback copy. Add `validate: 'nginx -t -c %s'`-style validation and `backup: true` |
| a service bound to `0.0.0.0` where a loopback or private range would do | MEDIUM | exposes the service on every interface; bind `127.0.0.1` or scope the firewall `src:` to a private CIDR |
| SELinux left `permissive` or `disabled` by a task | MEDIUM | drops a mandatory-access-control layer; keep `state: enforcing` and set contexts with `sefcontext` + `restorecon` |
| a user password stored as a plaintext hash input | HIGH | hash it: `password: "{{ 'secret' \| password_hash('sha512') }}"` — never a literal |

**Injection guard (enhances the shell-injection note in ansible-audit.md).**
`| quote` escapes shell metacharacters, but a whitelist is stronger than
escaping alone: gate the task on the variable matching an allowed pattern,
so a hostile value never reaches the shell at all —

```yaml
  when: user_input is match('^[a-zA-Z0-9._-]+$')   # whitelist, not blacklist
```

**External secret managers (beyond ansible-vault).** Where the deploy has
a secrets backend, read the value at run time instead of committing even a
vaulted copy — and mark the task `no_log: true`:

```yaml
  db_password: "{{ lookup('community.hashi_vault.hashi_vault', 'secret/data/db:password') }}"
```

`community.aws.aws_secret` and `azure.azcollection.azure_keyvault_secret`
are the AWS / Azure equivalents. The value never lands in the repo at all —
the strongest form of the "rotate then vault" remediation.
