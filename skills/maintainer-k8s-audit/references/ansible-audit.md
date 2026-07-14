# Ansible audit

The maintainer audits playbooks, roles, inventories and vars files that
already exist. Two failure classes dominate: **secrets in the clear**
and **non-idempotent tasks that lie about what they changed**. Both are
findable statically; the second also needs a two-run proof.

## Table of Contents

- [The tool chain and the real profiles](#the-tool-chain-and-the-real-profiles)
- [Secrets, Vault and no_log](#secrets-vault-and-no_log)
- [Shell, modules and idempotency](#shell-modules-and-idempotency)
- [Privilege, file modes, pinning and remediation](#privilege-file-modes-pinning-and-remediation)

## The tool chain and the real profiles

```bash
yamllint -f parsable playbooks/ roles/
ansible-playbook --syntax-check -i inventory playbook.yml
ansible-lint --profile production          # the strictest built-in profile
ansible-lint --profile production --offline # no galaxy fetch; deterministic in CI
ansible-lint -f pep8 playbook.yml           # parseable output for the report
ansible-lint -L                             # every rule id + description
checkov -d playbooks/ --framework ansible --output sarif
```

- ansible-lint profiles escalate: `min` → `basic` → `moderate` →
  `safety` → `shared` → `production`. **There is no `security`
  profile** — the security-adjacent rules live in `safety`, which
  `production` already includes. Audit at `production`; it is the
  superset.
- `--offline` skips the galaxy metadata fetch so a CI run is
  deterministic and network-independent. Use it in `gate` mode.
- Exit codes are NOT interchangeable: `2` = violations were found (the
  audit ran, the code has issues); `1` = ansible-lint itself failed to
  run (bad config, missing collection). A `1` means you have no result,
  not a clean result.

## Secrets, Vault and no_log

| Finding | Sev | Why |
|---|---|---|
| a plaintext credential in `vars/`, `group_vars/`, `host_vars/`, or inline `vars:` | CRITICAL | committed secret; rotate then vault — removal alone does not un-leak it |
| a task that sets/reads a secret with no `no_log: true` | HIGH | the secret is printed to stdout, to the retry file, and to any CI log on `-v` |
| `debug:` printing a variable that holds a secret | HIGH | echoes the secret to the console |
| `validate_certs: false` on `uri`/`get_url` | HIGH | disables TLS verification — MITM on the fetched artifact (Checkov `CKV_ANSIBLE_1`/`CKV_ANSIBLE_2`) |
| a `get_url`/`uri` on plain `http://` | HIGH | unauthenticated, unencrypted transport (`CKV2_ANSIBLE_1`/`CKV2_ANSIBLE_2`) |
| a package install with GPG checking disabled / `force` | HIGH | installs unsigned packages (`CKV_ANSIBLE_5`/`CKV_ANSIBLE_6`) |

`no_log: true` is deploy-neutral — it only suppresses output, it cannot
change what a task does — so it is the one secrets-related fix the audit
may auto-apply on a task the heuristic flags. Vault the value and mark
the task:

```yaml
- name: Set the database password
  ansible.builtin.set_fact:
    db_password: "{{ vault_db_password }}"   # from an ansible-vault-encrypted file
  no_log: true
```

```bash
ansible-vault encrypt group_vars/prod/secrets.yml
ansible-vault encrypt_string 's3cr3t' --name 'db_password'   # inline encrypted var
ansible-playbook site.yml --vault-password-file .vault-pass  # .vault-pass is gitignored
```

## Shell, modules and idempotency

### Command and shell vs modules

| Finding | Sev | Why |
|---|---|---|
| `shell:`/`command:` where a module exists (`apt`, `copy`, `file`, `git`, `get_url`, `user`) | MEDIUM | the module is idempotent and check-mode-safe; the shell call is neither |
| a bare module name (`apt:` instead of `ansible.builtin.apt:`) | MEDIUM | ambiguous which collection provides it; breaks when modules move between collections. `ansible-lint --fix` rewrites these |
| a user-controlled variable interpolated into `shell:` | HIGH | template injection — an attacker-influenced value reaches the shell. Use a module, or `\| quote` and a whitelist `when:` |

Never build a working injection payload in the audit; describe the shape
(untrusted variable reaching a shell string) and the fix (a module, or
`{{ var | quote }}` guarded by a whitelist `when:`), then move on. The
FQCN rewrite is semantically identical and verified by re-running
`--syntax-check`, so it is auto-fixable via `ansible-lint --fix`:

```yaml
- name: Install nginx                     # after --fix
  ansible.builtin.apt:
    name: nginx
    state: present
```

### Idempotency — how to prove it

Static checks find the *likely* non-idempotent tasks; only a second run
proves it. A playbook is idempotent iff its second consecutive run
reports `changed=0`.

| Finding | Sev | Why |
|---|---|---|
| `command:`/`shell:` with no `changed_when` | MEDIUM | reports `changed` on every run — pollutes the change count and hides real drift |
| `command:`/`shell:` with no `creates:`/`removes:` guard | MEDIUM | re-executes every run even when the effect is already present |
| `state: latest` on a package | MEDIUM | non-deterministic — the installed version changes as the upstream repo moves; pin `state: present` + a version |
| `ignore_errors: true` | MEDIUM | swallows a real failure; a failing task reports success |
| a `with_items` loop | LOW | deprecated spelling of `loop:` |

Prove it with a second run or check mode:

```bash
ansible-playbook -i inventory site.yml            # run 1 — some changed
ansible-playbook -i inventory site.yml            # run 2 — MUST be changed=0
ansible-playbook -i inventory site.yml --check --diff   # dry-run, shows would-change
molecule test                                      # includes an idempotence assertion
```

Some modules are inherently non-idempotent (`command`, `shell`, `raw`,
`script`, `uri` with side effects) — they need `changed_when` /
`creates` to behave. A task reporting `changed` on run 2 is the finding;
the fix is a `changed_when` that matches the real success signal:

```yaml
- name: Render the migration
  ansible.builtin.command: /usr/local/bin/migrate --check
  register: migrate
  changed_when: "'applied' in migrate.stdout"   # changed only when it really changed
  failed_when: migrate.rc not in [0, 2]
```

## Privilege, file modes, pinning and remediation

### Privilege escalation and file modes

| Finding | Sev | Why |
|---|---|---|
| play-wide `become: yes` for read-only tasks | MEDIUM | escalates where it is not needed — least privilege violated; scope `become` per task |
| `mode: '0777'` or `'0666'` | HIGH | world-writable file or script — anyone on the host can alter it |
| a private key / secret written `mode: '0644'` | HIGH | world-readable credential |
| no `mode:` on a file/template task | MEDIUM | permissions fall to the umask — non-deterministic and often too open |
| `host_key_checking = False` in `ansible.cfg`, or `StrictHostKeyChecking=no` | HIGH | disables SSH host verification — MITM on the control channel |

Escalate per-task; set an explicit, minimal `mode`:

```yaml
- name: Write the app config
  ansible.builtin.template:
    src: app.conf.j2
    dest: /etc/app/app.conf
    owner: app
    group: app
    mode: '0640'          # not world-readable; explicit, not umask-dependent
  become: true            # only this task escalates
```

Reference modes: private keys `0600`, sensitive config `0640`,
executables `0755`, sensitive directories `0750`.

### Collection and role pinning

| Finding | Sev | Why |
|---|---|---|
| an unpinned collection/role in `requirements.yml` | HIGH | `ansible-galaxy install -r` pulls the latest — a compromised release lands silently |
| no `requirements.yml` while playbooks use non-builtin FQCNs | MEDIUM | the dependency set is implicit and unreproducible |

```yaml
# requirements.yml
collections:
- name: community.general
  version: "==8.6.1"        # exact, not ">=" — reproducible
- name: ansible.posix
  version: "==1.5.4"
```

```bash
ansible-galaxy collection install -r requirements.yml
```

Pinning to the version already installed is deploy-neutral and
auto-applicable; bumping to a newer one is a proposed change.

### Remediation templates

`.ansible-lint` pinning the strict profile, with any suppression
carrying a WHY:

```yaml
# .ansible-lint
profile: production
exclude_paths:
  - .cache/
  - molecule/
skip_list:
  # WHY: the vendor installer is a signed blob with no module equivalent;
  # guarded by `creates:` so it stays idempotent. Reviewed 2026-07-13.
  - command-instead-of-module
```

A hardened, idempotent, secret-safe task combines the patterns above:

```yaml
- name: Deploy the signed release
  ansible.builtin.get_url:
    url: "https://releases.example.com/app-{{ app_version }}.tar.gz"
    dest: "/opt/app/app-{{ app_version }}.tar.gz"
    checksum: "sha256:{{ app_sha256 }}"     # verify the artifact
    validate_certs: true                     # never false
    mode: '0644'
  no_log: true                               # url may embed a token
```
