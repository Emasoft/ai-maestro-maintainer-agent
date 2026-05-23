# Changelog

All notable changes to this project will be documented in this file.
    ## [1.1.0] - 2026-05-23

### Bug Fixes

- Relocate per-agent state from \$HOME to AGENT_DIR (Phase D)    
- Drive plugin to CPV strict CRITICAL=0 MAJOR=0 MINOR=0 NIT=0    

### Documentation

- Backfill v1.0.0–v1.0.9 history via git-cliff    
- Document rate-limit, less-permission-prompts, claude agents --json    
- Explain why we keep `git tag -a` over `claude plugin tag`    
- Document maintainer-workflow-audit + zizmor integration    

### Features

- Adopt Claude Code 2.1.132/2.1.133 env vars    
- Scope tools and disallow web access (v2.1.119)    
- Handle gh rate-limit hint and xhigh effort tier    
- Add maintainer-workflow-audit (zizmor-powered)    
- Register maintainer-workflow-audit + chain from fix flow    
- Add workflow-scan (read-only zizmor + actionlint audit)    
- Add workflow-fix-safe (zizmor --fix=safe + hardening)    
- Add workflow-pin-actions (SHA-pin unpinned actions)    
- Add workflow-protect-branch (idempotent ruleset apply)    
- Add workflow-bootstrap + setup_marketplace_pat.py    
- Close article-vector gaps GAP-1/2/4 (Phase A)    
- Guardian core — proactive supply-chain sentinel (Phase B)    
- Wire Guardian into patrol/triage/fix (Phase C)    

### Miscellaneous

- Pin actions to SHAs and harden permissions (zizmor clean)    
- Dynamic tool surface + CPV Nixtla-strict cleanup    
- Embed reference TOCs + checklist phrasing nits    
- Integration audit — close 2 real gaps    

### Refactor

- Drop monolithic workflow-audit, fix CPV regressions    
- Progressive disclosure for 3 oversize maintainer-* skills    

### Security

- Add zizmor job (SARIF upload + fail-on-findings)    


