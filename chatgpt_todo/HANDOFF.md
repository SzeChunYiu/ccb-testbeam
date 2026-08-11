# Latest Handoff

## Active atom: one-sided Linux loader secure-state attestation

Protected parent is `main@4122dc6d71e64fd35697868afa6057e11377138a`; draft PR #1210 is on `audit/geant4-loader-secure-state` under #1182 / `ARU-MC-G4-LOADER-SEARCH-001`.

The atom composes the PASS runtime-dependency receipt with its PASS same-process runtime/link co-observation child and then measures `/proc/<pid>/auxv` while `(pid,starttime_ticks)` stays stable. For the already-attested ELF64 little-endian x86-64 domain, auxv is parsed as 16-byte `<uint64 type,uint64 value>` records with exact `AT_NULL=(0,0)` termination, no duplicate non-null types, exactly one `AT_SECURE`, and `AT_SECURE in {0,1}`.

### Adversarial correction that must be preserved

The first branch implementation was too strong for `AT_SECURE=0`: it tried to use the existing post-start `GLIBC_TUNABLES` observation to decide whether libc's `glibc.rtld.enable_secure=1` had been requested. GNU libc's own implementation/tests show that this tunable can enable secure-mode behavior while kernel `AT_SECURE` remains zero, and secure processing skips/removes `GLIBC_TUNABLES` from the environment. Therefore a post-start absence cannot establish launch-time absence.

The implementation is now deliberately one-sided:

- `AT_SECURE=1` -> `SECURE_CONFIRMED_BY_KERNEL_AT_SECURE`; captured `LD_LIBRARY_PATH`, `LD_PRELOAD`, `LD_AUDIT` are non-authorising loader-search evidence.
- `AT_SECURE=0` -> `UNRESOLVED_KERNEL_AT_SECURE_ZERO`; the same post-start environment values remain non-authorising until exact pre-exec environment/loader invocation and exact libc/loader identity are bound.

This preserves a useful direct kernel observable without falsely turning it into a complete effective glibc secure-mode Boolean.

### Exact repository implementation

Lineage retained for provenance:
- initial tool `ae86fd58c81400fe98e6336a6cf4eca0c9e71eef`;
- initial tests `875ac55234d7c35177109d1379c8df7a58a8ceff`;
- curated CI inclusion `972e95e1b9a3c2f8d2dc25d1cec913b8416989ea`;
- first archive `b7d3f511a0c3d06bfed434d64ea1ac6001f069f4`;
- corrected tool `8dbec7cdc8332d77c232e45a544943052a3fcf36`;
- corrected tests `5a726711382e4164d52f7897f6a01bc05f469469`;
- correction archive `8443ac2613963384e42b79ead603d2e12ce15241`;
- corrected active-task transition `9a8c5c8e0f566e19ce7e3ddc31743a1d0cd207ca`.

Corrected exact GitHub-blob-bound local execution, Python 3.13/Linux/no RNG:

`PYTHONPATH=/tmp/ccb_loader_exact python -m pytest -q /tmp/ccb_loader_exact/tests/test_geant4_loader_secure_state_attestation.py` -> `10 passed in 0.04s`; `py_compile` passed.

Content identities:
- tool: 11540 bytes; SHA-256 `b6821361ab5a7e13f71906accecbad3a7e7f9fc130432af262413413e69e7748`; Git blob SHA-1 `3102596db172b9f6f901d6768b7ad16042e7254c`;
- tests: 7343 bytes; SHA-256 `af65d252ce7a5d57d71651144f60a9098b7c3ce672353a87f75c11b628465257`; Git blob SHA-1 `da51b78d275c4192636e5e4de6c7fece9fedb8b8`.

The hostile matrix covers secure/nonsecure kernel bits, duplicate/missing/nonboolean `AT_SECURE`, malformed auxv, wrong receipt ancestry, process mismatch, invalid data after `AT_NULL`, and the key negative control that a post-start `GLIBC_TUNABLES=glibc.rtld.enable_secure=1` observation does not upgrade the kernel-zero case into a reconstructed effective loader state.

No local ruff executable was available. The earlier PR CI run on head `79823035bc244727f9205f5bfdaf7a18d7295121` is superseded by the correction and must not authorize merge. Require fresh exact-final-head MC Validation.

### Four sequential AI review passes

- **Runtime/physics integration lead — REVISE earlier zero-case / ACCEPT one-sided kernel measurement.** Strongest counter-hypothesis was that post-start environment plus `AT_SECURE=0` proves non-secure loading; glibc environment sanitization falsifies it. Residual: pre-exec state, exact libc/loader build, full search decision and real HIBEAM runtime.
- **Adversarial systems reviewer — ACCEPT correction / BLOCK effective non-secure claim.** UID/GID equality is also insufficient because capabilities/LSM can set `AT_SECURE`. Residual: explicit-loader invocation and sanitized launch state.
- **Independent validation reviewer — ACCEPT corrected deterministic oracle / BLOCK runtime generalisation and physics inference.** Ten exact committed-code fixtures pass; no real HIBEAM process or event was exercised.
- **Claims/provenance reviewer — ACCEPT provenance child / BLOCK CL-021 promotion.** Link command/static archives, full loader decision, immutable consumption, runtime manifest, compiled hostile source/stopping controls, weights and detector response remain separate gates.

### Spawned children

New highest-priority child: `ARU-MC-G4-LOADER-PREEXEC-ENV-001` — bind the exact environment and loader invocation at the exec boundary before dynamic-loader sanitization, together with exact loader/libc identity.

Other loader children remain `ARU-MC-G4-LOADER-INITIAL-CWD-001`, `ARU-MC-G4-LOADER-CACHE-CONFIG-001`, `ARU-MC-G4-LOADER-TOKEN-HWCAPS-001`, and `ARU-MC-G4-PRELOAD-AUDIT-001`; linker-command/static-input, late-dlopen, non-executable relocation/GOT/PLT, wrapper/descendant, immutable-consumption, runtime-manifest, compiled source/stopping, event-weight and detector-response atoms remain open.

No production Geant4 campaign was run, no beam or production-MC ROOT bytes were opened, and no angular distribution, event weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate, or detector-performance quantity was regenerated or promoted. #1182 and CL-021 remain gated.
