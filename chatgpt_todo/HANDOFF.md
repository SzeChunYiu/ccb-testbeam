# Latest Handoff

## Active atom: same-open-descriptor runtime ELF/link co-observation — repaired after exact-head CI falsifier

Protected `main@a9b7184bce1b898a2b36143ed4bd7f725d5a0f8a` was inspected after #1207 merged. #1207 exact head `2b699f89cdb4740bde9eb59d7fe19a74ca5567a7` passed MC Validation run `31464431085` with curated ruff clean and `1537 passed, 1 skipped, 8 xfailed, 1 xpassed`; it was squash-merged as `a9b7184b...`. That predecessor proves a bounded equality between live file-backed executable code pages and the attested backing projection, but it does not remove the earlier #1206 gap in which mapped-object content identity and ELF metadata can be obtained by separate pathname opens.

The selected child is `ARU-MC-G4-RUNTIME-LINK-COOBSERVATION-001`, implemented on draft PR #1208 / branch `audit/geant4-runtime-link-coobservation`.

### Exact contract

For each mapped object `j` with receipt identity `K_j=(dev_major,dev_minor,inode)`, require

`K_stat(path,t0) = K_fstat(fd) = K_j = K_stat(path,t1)`.

Read one descriptor snapshot `B_j` with `pread`; both `SHA256(B_j)` and bounded ELF metadata `E_j=parse_ELF(B_j)` are derived from that same Python byte string. The predecessor receipt's byte count/hash/device/inode must match. The process start-time and the complete file-backed executable mapping projection must match the validated runtime receipt before the observation and remain unchanged afterward.

For each unique non-path `DT_NEEDED=d`, exactly one co-observed object must satisfy `DT_SONAME(E_j)=d`. A slash-containing relative dependency remains blocked because runtime cwd provenance is not yet bound. Absolute `DT_NEEDED` and `PT_INTERP` are matched by stable resolved device/inode identity to exactly one co-observed mapped object; their byte/ELF evidence is not obtained through another path reopen. If bytes begin with ELF magic, parser failure is fatal rather than silently relabeling the object non-ELF.

### Exact-head failure that must remain in provenance

MC Validation run `31466409401` on PR head `965ba13719ce711d47f88941be2e8a471837345e` failed. Curated ruff returned status 1 with an `IndentationError` at lines 204-205; full non-integration pytest returned status 2 because test collection hit the same syntax error. Exact Git-blob inspection then established that the tool had been truncated in the middle of `attest_runtime_link_coobservation()` and also contained two latent defects: `_fd_snapshot` checked undefined `bloc` rather than `block`, and `_runtime_object_key` used `(device_major,inode,inode)` rather than `(device_major,device_minor,inode)`.

This result falsifies the earlier implication that a local authoring-copy `py_compile` PASS applied to the committed branch source. The failed head is preserved as evidence rather than erased from the narrative.

### Repair and current branch state

- original tool commit `1ebebdf3fa2a60642fdbeb84fd6e5c73abdd7ccd`;
- hostile-test commit `fc821619cf72972a81302609e8f8a560c8d48c52`;
- curated ruff inclusion `4f637fabe507c040ab5421f1fc63dcf191391abd`;
- initial immutable ARU record `e60cad31a191bad21737d204267bb37bf9ba14a6`;
- complete source repair `fb6df0e528b5a98351b179a82d78612cca80b3ce`;
- exact CI-failure/repair archive `chatgpt_todo/archive/2026-08-11T071000Z_ARU-MC-G4-RUNTIME-LINK-COOBSERVATION-001-ci-repair.md`, commit `be24b8dfbdf0f332116f5bfb7ab2c1c48201475f`;
- active-task correction commit `0c8e9decd03194cca17a8a6d710544ac747b020c`.

The repaired source restores the complete receipt/process/projection checks, correct three-component device/inode identity, same-FD stable snapshot/hash/ELF parsing, process-executable identification, direct-dependency/interpreter matching, final maps/starttime rechecks, content-digested receipt, and CLI.

Post-repair local evidence is deliberately narrow: Python 3.13.5 `py_compile` passed for the repaired authoring file and a small stubbed core-logic smoke returned `1 passed`. Neither replaces full repository tests. A fresh exact-head CI was started on the code repair, but archive/coordination commits have since advanced the branch; therefore only CI on the **final coordination head** may authorize merge.

The committed hostile fixtures still cover a symlinked interpreter, absolute dependency symlink, relative dependency cwd blocker, duplicate SONAME ambiguity, malformed ELF-magic failure, injected pathname replacement while the old descriptor remains open, mapping projection drift, and a runtime receipt from another final build.

### Four sequential AI reviews

- **Linux/Geant4 runtime provenance lead — REVISE / ACCEPT repaired bounded mechanism / BLOCK HIBEAM authorisation.** Strongest counter-hypothesis: the failed source was only cosmetically malformed. Exact truncation and identity/read defects falsify that; the complete repaired head must be evaluated independently. Residual uncertainty: full repo tests and immutable HIBEAM runtime.
- **Adversarial systems reviewer — REVISE / BLOCK until repaired exact-head CI.** Strongest counter-hypothesis: fixing the indentation is sufficient. The independent `bloc` and device-minor defects falsify that simplification. Residual uncertainty: additional repository integration failures may remain.
- **Independent validation reviewer — BLOCK merge until final exact-head curated ruff + full non-integration pytest.** Strongest counter-hypothesis: local repaired py_compile/stub smoke is enough. It is not a full exact-checkout repository execution. Residual uncertainty: final exact-head CI.
- **Claims/provenance reviewer — ACCEPT transparent failure correction / BLOCK CL-021 promotion.** The failed head and incorrect applicability of the earlier local check are now explicitly recorded. Linker/static inputs, loader search/secure state, later load/unload, non-executable relocation state, runtime RNG/thread/event/input/output identity, compiled source/stopping controls, source support/UQ, event weights and detector response remain open.

### New child exposed by the failure

`ARU-REPO-CONTENT-TRANSFER-001`: if local validation is used as evidence for a repository change, explicitly bind the locally checked bytes/hash to the exact committed GitHub blob, or execute the validation in the exact committed checkout. Do not infer source identity from a shared filename or intended edit.

## Next actions

1. Consume fresh MC Validation only for the final #1208 head after all coordination changes.
2. If ruff/full pytest fail, repair only the demonstrated exact-head failure and preserve the failed evidence.
3. If exact-head CI passes and `main` ancestry remains current, mark #1208 ready and merge through normal protected workflow; otherwise reconcile base without force-push and revalidate.
4. After #1208 lands, move materially deeper to `ARU-MC-G4-LOADER-SEARCH-001` or `ARU-MC-G4-LINK-COMMAND-001`; the new content-transfer child should also be encoded as a reusable repository publication gate rather than merely remembered.

No production Geant4 campaign, beam ROOT, production-MC ROOT, angular distribution, event weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate or detector-performance result was regenerated or promoted. #1182, #1178, #1179, #1058, #1053/#880 and CL-021 remain gated.
