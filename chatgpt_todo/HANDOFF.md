# Latest Handoff

## Active atom: ELF link metadata composed with runtime mappings

Protected `main@2db54689253ac993d2cf430ebc7ee7e8173ec7c7` was inspected after the validated #1204 runtime-mapping predecessor and #1205 handoff. `ARU-MC-G4-LINK-METADATA-001` is now **PARTIAL**: its mathematical/software contract and hostile fixtures have been executed locally, and the immutable review is committed on branch `audit/geant4-elf-link-metadata`, but the bounded implementation/test files could not be written through the connected GitHub tool because its safety classifier blocked both code-write methods as indeterminate. No PR CI pass or merge is claimed.

The local implementation parses the exact already-hashed ELF64 little-endian x86-64 bytes directly, records `PT_INTERP`, ordered `DT_NEEDED`, collapsed unique dependencies, `DT_SONAME`, `DT_RPATH`, `DT_RUNPATH`, and the dynamic string-table identity fields. It verifies parent final-build/runtime-receipt digests and executable identity, rebinds each runtime-mapped object's bytes to the predecessor receipt, parses content-identical ELF metadata, matches non-path direct dependencies by `DT_SONAME`, and matches absolute-path dependencies/interpreter by content identity. Relative dependency paths are blocked until runtime cwd provenance exists.

The mechanism intentionally does **not** equate mapped pathnames with `DT_NEEDED`: a dependency can be declared by SONAME while `/proc/<pid>/maps` shows a versioned implementation filename. It also does not reject extra mapped objects merely because the main executable did not declare them directly; they may be transitive dependencies, preloads, or later loads. RPATH and RUNPATH are retained separately and are not treated as proof of actual resolution.

### Executed deterministic evidence

Local environment: Python 3.13.5 on Linux, no RNG. `PYTHONPATH=. python -m pytest -q tests/test_geant4_elf_link_attestation.py` returned `11 passed in 0.08s`; `python -m py_compile tools/audit/geant4_elf_link_attestation.py` passed. The direct parser also successfully measured interpreter and `DT_NEEDED` metadata from local `/bin/ls` and `/usr/bin/python3`. These checks validate only the parser/contract mechanics; no HIBEAM/Geant4 binary or event population was exercised.

Hostile fixtures discriminate versioned pathname versus SONAME matching, RPATH/RUNPATH retention, duplicate declarations, malformed string offsets, post-runtime-receipt mapped-file mutation, wrong parent receipt, absent interpreter mapping, wrong SONAME, absolute versus relative path dependencies, and extra non-ELF executable mappings.

### Four sequential AI reviews

- **Build/runtime physics lead — ACCEPT bounded static-link decomposition / REVISE run provenance.** Evidence: #1199/#1204 schemas plus System V ELF definitions. Strongest counter-hypothesis: observed mappings already identify declared linkage. Falsifier: extra mapped objects and versioned implementation paths separate these observables. Residual: no real immutable HIBEAM executable/runtime receipt.
- **Adversarial systems reviewer — ACCEPT direct byte parser / BLOCK basename-only and external-tool authority.** Strongest counter-hypothesis: matching dependency basenames is enough. Falsifier: `DT_NEEDED=libG4fixture.so.1` against mapped `libG4fixture.so.1.2.3` closes only through `DT_SONAME`. Residual: post-runtime content rebind is not same-instant co-observation; late load/unload remains open.
- **Independent validation reviewer — ACCEPT deterministic software oracle / BLOCK physics inference.** Eleven deterministic fixtures plus two real local ELF parser smokes passed; no Geant4 transport, source sample, detector response, or statistical estimator was exercised.
- **Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion.** Link metadata does not bind linker command/static archives, runtime RNG/thread/event/input/output state, compiled source/stopping hostile controls, mapped in-memory page contents, weights, or detector DATA/MC closure.

## Repository state and next work

The immutable atom record is `chatgpt_todo/archive/2026-08-11T035000Z_ARU-MC-G4-LINK-METADATA-001.md` on branch commit `d49e34f0dbfb9e5f24e035b2a5740ed9950327a6`; `ACTIVE_TASK.md` was updated afterward. Parent #1182 should remain open. New children are `ARU-MC-G4-RUNTIME-LINK-COOBSERVATION-001`, `ARU-MC-G4-LINK-COMMAND-001`, and `ARU-MC-G4-LOADER-SEARCH-001`, alongside the existing late-`dlopen`, mapped-page, wrapper-chain, immutable-consumption, and runtime-manifest children.

The next session should first land the already-executed parser/tests if the code-write surface permits it, add them to curated ruff, run exact-head repository CI, and only then consider the atom software-validated. If the same write blocker persists, move to a different executable provenance child rather than marking completion.

A separate current-main hygiene defect is visible: the newest merge introduced many tracked Python 3.13 `__pycache__/*.pyc` artifacts. That requires its own solve-first provenance cleanup and should not be conflated with the ELF atom.

No production Geant4 campaign, beam ROOT, production MC ROOT, angular distribution, event weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate, or detector-performance result was regenerated or promoted. #1182, #1178, #1179, #1058, #1053/#880 and CL-021 remain open/gated.
