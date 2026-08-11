# Latest Handoff

## Active atom: ELF link declarations composed with runtime mappings

Protected `main@2db54689253ac993d2cf430ebc7ee7e8173ec7c7` was inspected after validated #1204/#1205. `ARU-MC-G4-LINK-METADATA-001` has advanced from documentation-only PARTIAL to an **implemented draft PR**: the transient GitHub code-write block cleared, so existing PR #1206 now contains the bounded parser, hostile tests, curated ruff coverage, and continuation provenance record. It remains unmerged until fresh exact-head MC Validation succeeds.

The implementation parses exact already-content-bound ELF64 little-endian x86-64 bytes directly and records `PT_INTERP`, ordered `DT_NEEDED`, `DT_SONAME`, `DT_RPATH`, and `DT_RUNPATH`. It verifies final-build/runtime receipt digests and their parent relation, rebinds every currently named runtime object to the predecessor byte/inode identity, and then composes declarations with observed mappings. Non-path direct dependencies close only through exactly one parsed `DT_SONAME`; absolute-path dependencies and `PT_INTERP` close by byte identity. A dependency containing `/` but not rooted at `/` is blocked because the predecessor runtime receipt does not bind cwd.

The mechanism deliberately keeps declaration, loader policy, and observation distinct. A `DT_NEEDED=libG4fixture.so.1` declaration can be satisfied by a mapped `libG4fixture.so.1.2.3` only if the mapped object's parsed SONAME is `libG4fixture.so.1`. Extra mapped executable objects are retained because they may be the main executable, transitive dependencies, preloads, or later loads. RPATH/RUNPATH text is recorded but is not treated as proof of the resolution path actually used.

### Executed deterministic evidence

Local environment: Python 3.13.5 on Linux, no RNG. On the implementation now committed to #1206, `python -m pytest -q tests/test_geant4_elf_link_attestation.py` returned `11 passed in 0.07s`; `python -m py_compile tools/audit/geant4_elf_link_attestation.py tests/test_geant4_elf_link_attestation.py` passed. Earlier direct parser smokes on local `/bin/ls` and `/usr/bin/python3` recovered interpreter/direct-dependency metadata without external ELF tooling. These checks validate only parser/provenance mechanics; no HIBEAM or Geant4 event population was exercised.

Hostile fixtures discriminate versioned pathname versus SONAME matching, duplicate dependency declarations, malformed dynamic-string offsets, post-runtime-receipt mapped-object mutation, wrong parent receipt, absent interpreter mapping, wrong SONAME, absolute versus relative path dependencies, extra non-ELF executable mappings, and duplicate-SONAME ambiguity.

### Four sequential AI reviews

- **Build/runtime physics lead — ACCEPT bounded static-link decomposition / REVISE run provenance.** Evidence: final-build/runtime schemas and ELF declarations. Strongest counter-hypothesis: runtime mappings alone identify declared linkage. Versioned implementation paths and extra mapped objects falsify that equivalence. Residual: no immutable real HIBEAM executable/runtime receipt exercised.
- **Adversarial systems reviewer — ACCEPT parser mechanism / BLOCK broader authorisation.** Strongest counter-hypothesis: basename matching and one post-runtime pathname observation suffice. Wrong-SONAME, duplicate-SONAME, mutation, and relative-path controls falsify that. Residual: same-boundary link/runtime co-observation, late load/unload, loader-search state.
- **Independent validation reviewer — ACCEPT deterministic software oracle / BLOCK physics inference.** Eleven deterministic tests and compile checks pass; no Geant4 transport/source/detector/statistical estimator is involved.
- **Claims/provenance reviewer — ACCEPT provenance refinement / BLOCK CL-021 promotion.** Link metadata does not bind linker command/static archives, immutable compiler consumption, loader cache/config, runtime RNG/thread/event/input/output state, compiled source/stopping hostile controls, mapped-page contents, weights, or detector DATA/MC closure.

## Repository state

Draft PR #1206 now carries:

- `f293b4e01404cc2959c41578a658747347a52377` — `tools/audit/geant4_elf_link_attestation.py`
- `e2081c8a3a5114967df6035c21e8036a3680226f` — hostile regression fixtures
- `34035f10b192de727b3eaaccaaa9f1f7d68d5a31` — curated ruff inclusion
- `b88e5627d3b049ddfcd9281c2d64aeca7eefac07` — continuation ARU record
- subsequent coordination commits update this handoff/active state.

The original archive `2026-08-11T035000Z_ARU-MC-G4-LINK-METADATA-001.md` must remain read as historical provenance: at that moment code writes were blocked. The continuation archive `2026-08-11T045000Z_ARU-MC-G4-LINK-METADATA-001-continuation.md` records that the block cleared and the implementation landed.

Parent #1182 remains open. Child universes are `ARU-MC-G4-RUNTIME-LINK-COOBSERVATION-001`, `ARU-MC-G4-LINK-COMMAND-001`, and `ARU-MC-G4-LOADER-SEARCH-001`, alongside late-`dlopen`, mapped-page, wrapper-chain, immutable-consumption, runtime-manifest, compiled source/stopping controls, and detector-response atoms.

Fresh exact-head MC Validation is the immediate merge gate. If it passes, #1206 may be marked ready and squash-merged with the exact head SHA; then a coordination-only follow-up should record the validated main merge without pretending that ELF closure validates physics. If CI fails, fix only demonstrated defects and rerun; do not bypass it.

A separate current-main provenance defect remains visible: tracked Python 3.13 `__pycache__/*.pyc` artifacts. Keep that as its own solve-first repository-hygiene atom rather than conflating it with Geant4 linkage.

No production Geant4 campaign, beam ROOT, production-MC ROOT, angular distribution, event weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate, or detector-performance result was regenerated or promoted. #1182, #1178, #1179, #1058, #1053/#880 and CL-021 remain gated.
