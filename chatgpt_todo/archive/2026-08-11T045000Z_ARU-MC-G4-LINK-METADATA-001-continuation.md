# ARU-MC-G4-LINK-METADATA-001 — continuation

Status: ACTIVE / IMPLEMENTATION_ON_BRANCH / LOCAL_FALSIFIERS_PASS / EXACT_HEAD_CI_PENDING

Parent: #1182. Predecessor: validated `ARU-MC-G4-RUNTIME-MAPS-001` / PR #1204. Protected main at selection remained `2db54689253ac993d2cf430ebc7ee7e8173ec7c7`.

## Exact contract

Inputs are a PASS `ccb_geant4_build_binding_final_v1` receipt, a PASS `ccb_geant4_runtime_dependency_attestation_v1` receipt whose `parent_final_build_receipt_sha256` equals the final receipt digest, the exact final executable bytes, and every current path named by the runtime receipt's content-bound `mapped_executable_objects`.

The parser measures `PT_INTERP`, ordered `DT_NEEDED`, `DT_SONAME`, `DT_RPATH`, and `DT_RUNPATH` directly from ELF64 little-endian x86-64 bytes. For a non-path dependency `d`, closure requires exactly one runtime object whose content-rebound parsed `DT_SONAME == d`. For an absolute-path dependency or `PT_INTERP`, closure requires exactly one runtime object with the same byte count and SHA-256 as the current declared path. A dependency containing `/` but not beginning with `/` is blocked because the predecessor runtime receipt does not bind cwd. Duplicate identical `DT_NEEDED` strings remain in the raw declaration but collapse to one closure obligation.

The output is self-digested schema `ccb_geant4_elf_link_attestation_v1` and explicitly limits scientific scope to ELF-link declaration versus runtime file identity.

## Mechanisms considered

Rejected: `ldd` output as an authority; unattested `readelf` output; matching `DT_NEEDED` to mapped basenames; treating all mapped executable files as direct dependencies; equating `DT_RPATH` and `DT_RUNPATH`; accepting relative dependency paths without cwd provenance; treating the link receipt as proof of linker command/static inputs or Geant4 physics.

Surviving bounded mechanism: exact bytes -> direct ELF parser -> declaration metadata, composed with exact final-build/runtime receipt digests and content-rebound mapped objects. A versioned implementation filename can correctly satisfy a dependency only through its parsed SONAME.

## Executed discriminating tests

Local environment: Python 3.13.5, Linux, no RNG. On the exact implementation later written to the PR branch:

`python -m pytest -q tests/test_geant4_elf_link_attestation.py` -> `11 passed in 0.07s`.

`python -m py_compile tools/audit/geant4_elf_link_attestation.py tests/test_geant4_elf_link_attestation.py` -> success.

Hostile fixtures cover:

1. nominal interpreter plus versioned shared-object path matched through SONAME, with RPATH and RUNPATH retained separately;
2. duplicate identical `DT_NEEDED` retained raw but collapsed for closure;
3. dynamic-string offset beyond `DT_STRSZ`;
4. mapped-object bytes changed after runtime receipt creation;
5. runtime receipt bound to another final build receipt;
6. missing interpreter mapping;
7. same filename family but wrong SONAME;
8. absolute-path dependency matched by content identity;
9. relative dependency path blocked without cwd;
10. extra non-ELF file-backed executable mapping retained as non-direct;
11. duplicate runtime objects with the same SONAME rejected as ambiguous.

Earlier local direct parser smokes on `/bin/ls` and `/usr/bin/python3` recovered interpreter/direct dependency metadata without external ELF tooling. Those are parser checks, not HIBEAM or detector validation.

## Four sequential AI review passes

### (a) Build/runtime physics lead — ACCEPT bounded static-link decomposition / REVISE run provenance
Evidence: final-build and runtime receipt schemas, direct ELF parser, authoritative ELF/loader semantics. Strongest counter-hypothesis: observed mappings alone identify the declared linkage. Falsifier: a mapped versioned filename and extra mapped objects separate declaration and observation. Residual uncertainty: no immutable production HIBEAM executable/runtime receipt has been exercised here.

### (b) Adversarial mechanism reviewer — ACCEPT parser mechanism / BLOCK broader authorisation
Evidence: malformed string offset, wrong-parent, wrong-SONAME, duplicate-SONAME, relative-path, and post-receipt mutation controls. Strongest counter-hypothesis: basename matching is sufficient. Falsifier: `DT_NEEDED=libG4fixture.so.1` with mapped `libG4fixture.so.1.2.3` closes only via `DT_SONAME`. Residual uncertainty: current path rebinding occurs after the predecessor runtime snapshot rather than from the same opened file descriptions; late load/unload remains separate.

### (c) Independent validation reviewer — ACCEPT deterministic software oracle / BLOCK physics inference
Evidence: 11 deterministic tests, no RNG, py_compile success. Strongest counter-hypothesis: green parser tests validate the generator. Falsifier: no Geant4 event, source distribution, detector response, event weight, or data comparison enters these tests. Residual uncertainty: real executable and runtime population, static inputs, loader-state closure.

### (d) Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion
Evidence: #1182 acceptance criteria and predecessor limitations. Strongest counter-hypothesis: exact ELF metadata closes compiled generator provenance. Falsifier: linker command/static archives, immutable compiler consumption, loader search state, RNG/thread/event/input/output manifest, compiled hostile source/stopping controls, and detector chain remain unbound. No public physics claim changes status.

## External source-to-claim mapping

System V ELF defines `PT_INTERP` as the interpreter pathname and the dynamic table as the carrier of runtime link declarations; Linux loader documentation distinguishes slash-containing dependency paths from searched dependency names and distinguishes RPATH/RUNPATH/environment/cache/default resolution mechanisms. These facts motivate retaining declarations separately from observed mapped paths; they do not establish any CCB detector result.

Authoritative references:
- https://refspecs.linuxfoundation.org/elf/gabi4+/ch5.pheader.html
- https://refspecs.linuxfoundation.org/elf/gabi4+/ch5.dynamic.html
- https://man7.org/linux/man-pages/man8/ld.so.8.html

## Repository actions

The prior session's code-write safety block was transient. This continuation successfully wrote the bounded implementation and tests to existing draft PR #1206:

- `f293b4e01404cc2959c41578a658747347a52377` — `tools/audit/geant4_elf_link_attestation.py`
- `e2081c8a3a5114967df6035c21e8036a3680226f` — hostile fixtures
- `34035f10b192de727b3eaaccaaa9f1f7d68d5a31` — curated ruff coverage

PR #1206 was retitled to `audit(mc): attest ELF link metadata against runtime mappings` and remains draft until fresh exact-head MC Validation succeeds. No merge or exact-head CI success is claimed in this record.

## Children and cross-scale propagation

`ARU-MC-G4-RUNTIME-LINK-COOBSERVATION-001`: parse ELF metadata from the same opened runtime objects rather than later pathname rebinding.

`ARU-MC-G4-LINK-COMMAND-001`: bind actual linker command, response files, static archives, flags, and build-system invocation.

`ARU-MC-G4-LOADER-SEARCH-001`: bind cwd where relevant, secure-execution mode, loader cache/config identity, `$ORIGIN/$LIB/$PLATFORM` expansion, preload/audit state, and direct-versus-transitive search semantics.

Existing late-`dlopen`, mapped-page, wrapper-chain, immutable-consumption, runtime-manifest, source/stopping compiled-control, and detector response atoms remain unresolved. Therefore the local micro-level link contract cannot promote generator-, event-, study-, or claim-level physics.

## Claim consequences

No production Geant4 campaign was run. No beam or production-MC ROOT bytes were opened. No angular distribution, event weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate, or detector-performance quantity was regenerated or promoted. #1182 and CL-021 remain gated.
