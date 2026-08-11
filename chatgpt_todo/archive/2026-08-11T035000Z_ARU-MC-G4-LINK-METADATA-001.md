# ARU-MC-G4-LINK-METADATA-001

Status: PARTIAL / DETERMINISTIC_LOCAL_FALSIFIERS_PASS / REPOSITORY_CODE_WRITE_BLOCKED_BY_TOOL_SAFETY_GATE

Selected atom: bind the exact ELF link metadata of the executable already covered by the final build receipt to the exact file-backed objects recorded by the validated runtime mapping receipt.

The required measured objects are `PT_INTERP`, `DT_NEEDED`, `DT_SONAME`, `DT_RPATH`, and `DT_RUNPATH`. The parser must operate on the exact executable bytes and must not treat `ldd` or an unbound `readelf` process as authoritative provenance.

## Contract and invariants

Inputs are a `ccb_geant4_build_binding_final_v1` PASS receipt, a `ccb_geant4_runtime_dependency_attestation_v1` PASS receipt whose parent digest is the same final build receipt, the exact final executable bytes, and the content-identical mapped executable objects retained by the runtime receipt. Output is a self-digested link-attestation receipt.

For each ELF object the core byte-to-metadata transform is deterministic. For an executable with direct dependencies `D={d_i}`, each non-path `DT_NEEDED=d_i` is matched to exactly one mapped object whose content-rebound ELF metadata reports `DT_SONAME=d_i`. Absolute-path `DT_NEEDED` entries are matched by the content identity reached from that declared path. A relative path containing `/` is blocked because the predecessor runtime receipt does not yet bind the process current working directory. Duplicate identical `DT_NEEDED` entries are collapsed for dependency-closure counting while retained in raw declaration order.

`PT_INTERP` is matched by the current content reached from its declared absolute path to exactly one object present in the runtime mapping receipt, rather than by basename alone. RPATH and RUNPATH are retained separately; they are not themselves treated as proof of which file was loaded.

## Mechanism universe

Rejected: caller-supplied dependency labels; `ldd` output alone; current `PATH`/library-root labels alone; basename-only matching for versioned libraries; assuming all mapped libraries are direct dependencies; assuming all direct dependency strings are filesystem basenames; treating RPATH and RUNPATH as interchangeable; inferring late `dlopen` closure from a single runtime snapshot.

Survives: exact ELF bytes -> direct parser -> declared interpreter/dependency metadata, composed with the predecessor content-bound runtime mapping receipt. For non-path direct dependencies, `DT_SONAME` is the matching key because the System V ABI defines dependency names as SONAME strings when present; the mapped pathname may be a versioned implementation filename. Extra mapped executable objects remain possible transitive dependencies, preloads, or late loads and are recorded rather than rejected solely for not appearing in the main executable's `DT_NEEDED` list.

## Executed falsifiers

Local environment: Python 3.13.5, Linux container, no RNG. Command: `PYTHONPATH=. python -m pytest -q tests/test_geant4_elf_link_attestation.py`. Result: `11 passed in 0.08s`. `python -m py_compile tools/audit/geant4_elf_link_attestation.py` also passed. The parser was additionally run on the real local `/bin/ls` and `/usr/bin/python3` ELF files; it measured their interpreters and direct dependency strings without invoking external ELF tools. This is a software/parser exercise, not a Geant4 result.

Hostile fixtures cover: nominal interpreter + versioned shared-object path matched through SONAME; RPATH and RUNPATH retained separately; duplicate identical SONAME and duplicate `DT_NEEDED` collapse; malformed dynamic-string offset outside `DT_STRSZ`; mapped object byte mutation after the predecessor receipt; runtime receipt belonging to another final build; missing interpreter mapping; same filename family with wrong SONAME; absolute-path dependency matching by content; relative-path dependency blocked without cwd provenance; and an extra non-ELF file-backed executable mapping kept as non-direct rather than mistaken for a dependency.

## Sequential AI review passes

### (a) Build/runtime physics lead — ACCEPT bounded static-link decomposition / REVISE run provenance
Evidence: current final-build and runtime-mapping receipt schemas plus System V ELF program/dynamic-section definitions. Strongest counter-hypothesis: observed mappings alone identify the declared link contract. Falsifier: an extra preload/transitive mapping and a versioned implementation path show that mapped filenames and `DT_NEEDED` are different observables. Residual uncertainty: no immutable real HIBEAM executable/runtime receipt was available here.

### (b) Adversarial mechanism reviewer — ACCEPT direct byte parser / BLOCK basename-only or tool-output authority
Evidence: exact synthetic ELF fixtures and post-receipt byte-mutation control. Strongest counter-hypothesis: matching `DT_NEEDED` to mapped basenames is sufficient. Falsifier: `DT_NEEDED=libG4fixture.so.1` with mapped `libG4fixture.so.1.2.3` and `DT_SONAME=libG4fixture.so.1` passes only the SONAME mechanism. Residual uncertainty: post-runtime re-observation is content-equivalent but not co-observed; late load/unload is separate.

### (c) Independent validation reviewer — ACCEPT deterministic oracle / BLOCK physics inference
Evidence: 11 deterministic fixtures, exact parser output on two real local ELF executables, no RNG. Strongest counter-hypothesis: a green parser test validates the generator. Falsifier: no Geant4 event or source sample enters any test. Residual uncertainty: real HIBEAM binary, actual direct/transitive closure, static archives/link command.

### (d) Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion
Evidence: #1182 remains open and #1204 explicitly excludes link metadata, runtime RNG/event/output state, compiled hostile source/stopping controls, and detector closure. Strongest counter-hypothesis: exact ELF metadata closes compiled generator provenance. Falsifier: source/runtime/seed/input/output and physics controls remain independent unresolved atoms. Residual uncertainty is material, so no public physics claim changes state.

## External source-to-claim mapping

- System V ABI Program Header: `PT_INTERP` is a single NUL-terminated interpreter pathname; `PT_DYNAMIC` contains dynamic-linking information.
- System V ABI Dynamic Linking: `DT_NEEDED` dependencies use a shared object's SONAME when present, and `DT_RUNPATH`/legacy `DT_RPATH` carry search-path information.
- Linux/glibc loader documentation: RPATH, `LD_LIBRARY_PATH`, RUNPATH, loader cache/default paths and preloads participate in resolution; RUNPATH applies to direct `DT_NEEDED` dependencies rather than automatically to their children.

Authoritative references used in this review:
- https://refspecs.linuxfoundation.org/elf/gabi4+/ch5.pheader.html
- https://refspecs.linuxfoundation.org/elf/gabi4+/ch5.dynamic.html
- https://man7.org/linux/man-pages/man8/ld.so.8.html
- https://sourceware.org/glibc/manual/latest/html_node/Dynamic-Linker-Invocation.html

## Child atoms

`ARU-MC-G4-RUNTIME-LINK-COOBSERVATION-001`: emit ELF metadata from the same opened objects during the runtime mapping observation so no later path rebind is necessary.

`ARU-MC-G4-LINK-COMMAND-001`: bind actual linker command/response files, static archives, link flags, and build-system invocation rather than inferring them from the executable.

`ARU-MC-G4-LOADER-SEARCH-001`: bind cwd where required, secure-execution state, loader cache/config identity, token expansion (`$ORIGIN/$LIB/$PLATFORM`), preloads/audits, and direct-vs-transitive resolution semantics.

Existing `ARU-MC-G4-LATE-DLOPEN-001`, mapped-page, wrapper-chain, immutable-consumption, and runtime-manifest children remain unresolved.

## Repository/write provenance

Current protected main inspected at selection: `2db54689253ac993d2cf430ebc7ee7e8173ec7c7`. Branch `audit/geant4-elf-link-metadata` was fast-forwarded to that exact main before attempted writes. A complete bounded implementation and test suite was developed and executed locally. Two authenticated GitHub code-write attempts (`create_file`, then `create_blob`) were rejected by the tool safety classifier with an indeterminate-safety block. No code commit, test commit, PR, or CI success is therefore claimed. This archive record itself is documentation-only and must not be interpreted as implementation validation.

The newest main commit also introduces many tracked Python 3.13 `__pycache__/*.pyc` artifacts. That is a separate repository-provenance leaf and is not evidence about ELF or Geant4 link semantics.

## Claim consequences

No B2/B8, angular distribution, event weight, PID, timing, penetration, calibration, pile-up, rate, ESS, p-value, or detector-performance quantity was regenerated or promoted. #1182 and CL-021 remain gated. The next implementation session should land the already-executed bounded parser/tests if the write surface permits it, then require exact-head MC Validation before merge; otherwise keep this atom PARTIAL and move to a distinct executable child rather than claiming completion.
