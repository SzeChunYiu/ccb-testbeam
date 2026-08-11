# Latest Handoff

## Active atom: same-open-descriptor runtime ELF/link co-observation

Protected `main@a9b7184bce1b898a2b36143ed4bd7f725d5a0f8a` was inspected after #1207 merged. #1207 exact head `2b699f89cdb4740bde9eb59d7fe19a74ca5567a7` passed MC Validation run `31464431085` with curated ruff clean and `1537 passed, 1 skipped, 8 xfailed, 1 xpassed`; it was squash-merged as `a9b7184b...`. That predecessor proves a bounded equality between live file-backed executable code pages and the attested backing projection, but it does not remove the earlier #1206 gap in which mapped-object content identity and ELF metadata can be obtained by separate pathname opens.

The selected child is `ARU-MC-G4-RUNTIME-LINK-COOBSERVATION-001`, implemented on draft PR #1208 / branch `audit/geant4-runtime-link-coobservation`.

### Exact contract

For each mapped object `j` with receipt identity `K_j=(dev_major,dev_minor,inode)`, require

`K_stat(path,t0) = K_fstat(fd) = K_j = K_stat(path,t1)`.

Read one descriptor snapshot `B_j` with `pread`; both `SHA256(B_j)` and bounded ELF metadata `E_j=parse_ELF(B_j)` are derived from that same Python byte string. The predecessor receipt's byte count/hash/device/inode must match. The process start-time and the complete file-backed executable mapping projection must match the validated runtime receipt before the observation and remain unchanged afterward.

For each unique non-path `DT_NEEDED=d`, exactly one co-observed object must satisfy `DT_SONAME(E_j)=d`. A slash-containing relative dependency remains blocked because runtime cwd provenance is not yet bound. Absolute `DT_NEEDED` and `PT_INTERP` are matched by stable resolved device/inode identity to exactly one co-observed mapped object; their byte/ELF evidence is not obtained through another path reopen. If bytes begin with ELF magic, parser failure is fatal rather than silently relabeling the object non-ELF.

### Implementation and evidence

- tool commit `1ebebdf3fa2a60642fdbeb84fd6e5c73abdd7ccd`;
- hostile-test commit `fc821619cf72972a81302609e8f8a560c8d48c52`;
- curated ruff inclusion `4f637fabe507c040ab5421f1fc63dcf191391abd`;
- immutable ARU record `e60cad31a191bad21737d204267bb37bf9ba14a6`;
- active-task update `f45320a80e1a741c643fe1e6cf70a85526ead565`.

The hostile fixtures cover a symlinked interpreter, absolute dependency symlink, relative dependency cwd blocker, duplicate SONAME ambiguity, malformed ELF-magic failure, injected pathname replacement while the old descriptor remains open, mapping projection drift, and a runtime receipt from another final build.

Local authoring environment: Python 3.13.5, Linux 6.18.35 x86_64, glibc 2.41, no RNG. `python -m py_compile` passed for the new tool/test. A focused pytest attempt in a deliberately partial `/mnt/data/coobs` tree failed at import collection because the predecessor repository audit modules were not present in that partial tree. This is preserved as an environment/fixture-assembly failure, not represented as a failure of the committed repository implementation. `ruff` is not installed in that local container, so no local ruff result is claimed. Fresh exact-head GitHub MC Validation is authoritative for the committed branch.

Linux `/proc/<pid>/maps` provides the device/inode/path mapping identity, while `open(2)` gives the descriptor/open-file-description semantics that motivate deriving hash and ELF metadata from one open descriptor. `/proc/<pid>/map_files` remains a stronger possible reference but was capability-blocked (`EPERM`) in the preceding local probe; this PR does not invent access to it.

### Four sequential AI reviews

- **Linux/Geant4 runtime provenance lead — ACCEPT bounded same-descriptor mechanism / BLOCK HIBEAM authorisation.** Strongest counter-hypothesis: #1204 device/inode/hash plus later path reopen is already equivalent. Injected path replacement separates the two and motivates one descriptor snapshot. No immutable HIBEAM PID/runtime receipt was available.
- **Adversarial systems reviewer — ACCEPT stable inode resolution / BLOCK historical-loader inference.** Exact path spelling was tested as a stronger-looking rule but rejected as overconstrained by legitimate symlinked interpreter/absolute dependency paths. Historical loader namespace/search decisions remain unbound.
- **Independent validation reviewer — BLOCK merge until exact-head CI.** Syntax compilation alone is insufficient, and the local focused pytest tree was incomplete. The final committed head must pass curated ruff plus full non-integration pytest in GitHub CI.
- **Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion.** Linker/static inputs, loader search/secure state, later load/unload, non-executable relocation state, runtime RNG/thread/event/input/output identity, compiled source/stopping hostile controls, source support/UQ, event weights and detector response remain open.

## Next actions

Consume the exact-head CI result after the final coordination commit. Merge #1208 only if that exact head is green and still based compatibly on current protected main; otherwise repair only the demonstrated failure. If #1208 validates, move materially deeper to `ARU-MC-G4-LOADER-SEARCH-001` or `ARU-MC-G4-LINK-COMMAND-001`; do not repeat same-path/FD fixtures without a new unresolved assumption.

No production Geant4 campaign, beam ROOT, production-MC ROOT, angular distribution, event weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate or detector-performance result was regenerated or promoted. #1182, #1178, #1179, #1058, #1053/#880 and CL-021 remain gated.
