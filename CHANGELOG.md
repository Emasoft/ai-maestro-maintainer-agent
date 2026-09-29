# Changelog

All notable changes to this project will be documented in this file.

## [1.15.0] — 2026-09-29

### Bug Fixes

- **test:** Match the wildcard-before-subcommand CLASS, not the changelog example (eca35f0)
- **test:** Narrow the wildcard detector to the shape it can actually define (2b30b55)
- **test:** Point the BOM detector at the file 2.1.246 actually names (566cb76)
- **test:** Change the BOM question instead of guessing its file set again (6705d5b)
- **test:** BOM scan skips without git instead of erroring (0e90803)
- **test:** Put the BOM floor in the test that scans, not beside it (e5aa2a6)
- **worktree:** Refuse to remove a LOCKED worktree, per CC 2.1.248 (d690c91)
- **governance:** Type compare() with Mapping so its own tests type-check (e807159)
- **trdd:** Name the two ways RO44YZDP's box 3 could PASS unearned (TRDD-RO44YZDP) (b5d8e44)
- **ci:** Validate manifest non-strict (drop the || true no-op); fix card over-claim (TRDD-RO44YZDP) (4503c9e)
- **skill:** Validate must accept the status-less cards the v2 rule permits; drop dead SLUG arg (follow-up to 9ffa21b) (0ecccd0)
- **ci:** Devitalize the installer curl-pipe shape; complete the trdd-template TOC (CPV --strict) (7fbb421)
- **ci:** Route the installer through $RUNNER_TEMP env indirection (de69026)

### Documentation

- Qualify stale trdd-approval-tiers.md pointers (janitor#286) (2ba0116)
- Record never-touch-AgentlensPro directive on TRDD-RO44YZDP (f2d181b)
- **test:** Record the 2.1.247 audit, and why it gets no detector (025e887)
- **test:** Make the 2.1.247 paragraph true about its own method (a47cc57)
- **memory:** Record the publish-globally field memgrep normalized in (6b64607)
- Tick RO44YZDP acceptance box 4, record why box 3 cannot be ticked (TRDD-RO44YZDP) (5e9dde2)
- Say what was measured about issue #18, not what it implies (TRDD-RO44YZDP) (f8c59e7)
- Park RO44YZDP to 2026-09-08; box 3 is falsified, not just un-elapsed (TRDD-RO44YZDP) (71f3edb)
- Withdraw the disk-rate claim from RO44YZDP; box 3 is NOT EVALUABLE (TRDD-RO44YZDP) (6d53757)
- RO44YZDP → blocked on AgentlensPro#18; du figure restated as a lower bound (TRDD-RO44YZDP) (a590d30)
- Revert RO44YZDP to human_review; issue ref belongs in external-refs (TRDD-RO44YZDP) (0c88c6f)
- Cite the ratified sources for RO44YZDP's column, not the card itself (TRDD-RO44YZDP) (e36a003)
- Replace RO44YZDP's two second-hand facts with first-hand measurements (TRDD-RO44YZDP) (1a0d915)
- Withdraw the in-scope claim for the AgentlensPro issue query (TRDD-RO44YZDP) (396798d)
- Recover the verbatim AgentlensPro directive; the gh call was a VIOLATION (TRDD-RO44YZDP) (8fcda71)
- Earn the "sole directive" absence claim by enumeration (TRDD-RO44YZDP) (ca328be)
- Settle the absence claim on FULL text, not 230-char previews (TRDD-RO44YZDP) (f568cbe)
- **trdd:** Record RO44YZDP box 3 FAILED on breach and missing series (TRDD-RO44YZDP) (d01c1b9)
- **ci:** State the gate's real coverage; docs(trdd): restore box-3 endpoints (TRDD-RO44YZDP) (2e2921e)
- **trdd:** Replace endpoint-span with honest discovery-gap wording (TRDD-RO44YZDP); docs(ci): name the non-warning class (dfb6276)
- **memory:** Repair architecture.md page shape (janitor#250 splice defect) (4a3ba59)
- **readme:** Managed-site permission note for CC 2.1.282/2.1.284 (changelog sweep) (8f7329e)
- **trdd:** Track proposal V4Z2MTT2 (WFSEC-004 installer curl-pipe) with maintainer analysis (820ae4d)
- **ci:** Reword the installer comment without the pipe shape in prose (4470b40)
- **trdd:** Restore V4Z2MTT2 to proposals/ (owner ruling: no refused/ folder) + supersession note (7b963aa)
- **trdd:** Record V4Z2MTT2 withdrawal — the WFSEC-004 finding was fixed by hand (10fe3ee)
- **trdd:** Abolish design/refused/ zone — cards stay in proposals/ with column refused (df03ff8)
- **trdd:** Record refused/README.md removal from the zone abolition (df03ff8) (1521603)
- **trdd:** Settle review-fork findings on the refused-zone abolition (0332c5f)

### Features

- **trdd:** Set RO44YZDP's free-space floor and make box 3 agent-evaluable (TRDD-RO44YZDP) (ec75e0e)
- **ci:** Add native `claude plugin validate` step to the Validate job (0dc682e)
- **skill:** Align TRDD teaching files with 3-pillars 3.0.0 and route writes through trddgrep (PRRD G12.1) (528f471)
- **persona:** Adopt R41 approval-vs-mandate semantics, cited by number ([#41](https://github.com/Emasoft/ai-maestro-maintainer-agent/issues/41)) (8a91f37)

### Miscellaneous Tasks

- **validate:** Reject UTF-8 BOMs — install fails (2.1.246) / components silently dropped (2.1.239) (7500490)
- Bump version to 1.15.0 (a8aae33)
- Sync uv.lock self-version to 1.15.0 (d99dd97)
- Bump version to 1.15.0 (927338a)

### Revert

- **test:** Drop the wildcard-before-subcommand detector, keep the finding (c4e79bd)

### Testing

- Align the Claude Code surface ledger to 2.1.246 (5f80d2c)
- Give the BOM set a non-empty floor (b0c1f95)

### Build

- Scope bare `pytest` to tests/, so a no-args run stops dying on _corpus_dev (569f0e9)
---
*Generated by [git-cliff](https://git-cliff.org)*
