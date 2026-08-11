# Latest Handoff

## Active atom: Linux dynamic-loader secure-execution state

Protected `main@4122dc6d71e64fd35697868afa6057e11377138a` is the current parent. It contains the validated repository content-transfer primitive from PR #1209. Exact-head MC Validation run `31471219915` reported curated ruff clean and `1554 passed, 1 skipped, 8 xfailed, 1 xpassed`; #1209 was independently reviewed, marked ready, and squash-merged. That merge changes repository-provenance mechanics only and does not close #1182 or CL-021.

The selected child is `ARU-MC-G4-LOADER-SECURE-STATE-001` on branch `audit/geant4-loader-secure-state`, under the broader `ARU-MC-G4-LOADER-SEARCH-001` dependency.

### Why this atom exists

`geant4/setup_and_run.sh` historically builds `LD_LIBRARY_PATH` from VGM and the conda prefix before launching `./hibeam_g4`. The validated runtime-dependency receipt captures loader-control environment values, and the validated runtime/link co-observation binds mapped-object bytes and ELF declarations. Those facts still do not establish whether the loader was in secure-execution mode. In secure mode, loader environment controls are ignored or restricted, so recorded strings cannot automatically be interpreted as effective search inputs.

Linux exposes the secure-execution request directly as `AT_SECURE` in the auxiliary vector. Equal real/effective UID/GID is not an equivalent measurement because file capabilities or a Linux Security Module can also trigger secure execution. GNU libc additionally supports `glibc.rtld.enable_secure=1`, so kernel `AT_SECURE=0` plus that tunable is blocked pending exact glibc-version semantics rather than silently called non-secure.

### Exact bounded contract

Inputs are PASS `ccb_geant4_runtime_dependency_attestation_v1` and PASS child `ccb_geant4_runtime_link_coobservation_v1`, both naming the same `(pid,starttime_ticks)`, plus `/proc/<pid>/stat` and `/proc/<pid>/auxv`.

For the already-attested ELF64 little-endian x86-64 execution domain, parse auxv as 16-byte `<uint64 type,uint64 value>` records. Require exact receipt ancestry; equal process identity in both receipts; live start time equal before and after auxv read; `AT_NULL=(0,0)` termination; no duplicate non-null keys; exactly one `AT_SECURE`; and `AT_SECURE in {0,1}`.

`AT_SECURE=1` => captured `LD_LIBRARY_PATH`, `LD_PRELOAD`, and `LD_AUDIT` are `RESTRICTED_OR_IGNORED_DO_NOT_USE_AS_LOADER_SEARCH_AUTHORITY`.

`AT_SECURE=0` => those values are only `ELIGIBLE_SEARCH_INPUT_NOT_YET_PROVEN_EFFECTIVE`; RPATH/RUNPATH, cwd, loader cache/config, token/hwcaps expansion, preload/audit content/order and later dynamic loading still need independent evidence.

### Implemented evidence

- tool commit `ae86fd58c81400fe98e6336a6cf4eca0c9e71eef`: `tools/audit/geant4_loader_secure_state_attestation.py`;
- test commit `875ac55234d7c35177109d1379c8df7a58a8ceff`: `tests/test_geant4_loader_secure_state_attestation.py`;
- curated-CI inclusion `972e95e1b9a3c2f8d2dc25d1cec913b8416989ea`;
- immutable ARU archive `b7d3f511a0c3d06bfed434d64ea1ac6001f069f4`;
- active-task transition `e9511d8b74c1e921b00d7364afa8290561de6930`.

Python 3.13/Linux/no-RNG exact committed-code reconstruction:

`PYTHONPATH=/tmp/ccb_loader_exact python -m pytest -q /tmp/ccb_loader_exact/tests/test_geant4_loader_secure_state_attestation.py` -> `10 passed in 0.04s`.

The hostile matrix covers nonsecure/secure states; duplicate/missing/nonboolean `AT_SECURE`; malformed auxv length; wrong receipt ancestry; process mismatch; `glibc.rtld.enable_secure=1` with `AT_SECURE=0`; and invalid data after `AT_NULL`.

Repository-content cross-check:
- tool: 11833 bytes; SHA-256 `fc4802ea4f4e6db7fe50732f772d03f6744f28f1e4fa892012e2693f300c3c64`; Git blob SHA-1 `2aa3e3dfed76204d51dbfd2b718dc4393870a052`;
- tests: 6996 bytes; SHA-256 `3fe7b3695ee37351dfb95a61fd3d17c61376b39de20a2d2d08ee25db1ceae176`; Git blob SHA-1 `192348cee7c5fcf09209bea42f1778860e6388fc`.

Both Git blob IDs match GitHub branch reads. An earlier 6984-byte local test copy used a non-repository import path and is discarded as transfer evidence; the repository-adapted exact bytes were reconstructed and rerun.

No local ruff executable was available, so no local ruff PASS is claimed.

### Four sequential AI reviews

- **Runtime/physics integration lead — ACCEPT bounded mechanism / REVISE full loader provenance.** Strongest counter: assigned `LD_LIBRARY_PATH` already identifies effective library selection. Secure-execution semantics falsify that implication. Residual: no real HIBEAM auxv/runtime receipt, cwd, cache/config or exact glibc build identity.
- **Adversarial systems reviewer — ACCEPT direct auxv measurement / BLOCK complete loader decision.** Strongest counter: matching real/effective IDs proves non-secure. Capabilities/LSM are counterexamples. Residual: glibc enable-secure tunable, explicit loader invocation, token/hwcaps/cache state, preload/audit content/order, later `dlopen`/unload.
- **Independent validation reviewer — ACCEPT deterministic oracle / BLOCK physics inference.** Ten exact committed-code fixtures pass, but no event population or detector chain participates.
- **Claims/provenance reviewer — ACCEPT provenance child / BLOCK CL-021 promotion.** Link command/static archives, remaining loader decision, immutable consumption, runtime manifest, compiled hostile source/stopping controls, weights and detector-response closure remain open.

### Children and next handoff

Stable children: `PROV-G4-LOADER-GLIBC-TUNABLE-001`, `ARU-MC-G4-LOADER-INITIAL-CWD-001`, `ARU-MC-G4-LOADER-CACHE-CONFIG-001`, `ARU-MC-G4-LOADER-TOKEN-HWCAPS-001`, `ARU-MC-G4-PRELOAD-AUDIT-001`. Existing linker-command/static-input, late-dlopen, non-executable relocation/GOT/PLT, wrapper/descendant, immutable-consumption, runtime-manifest, compiled source/stopping, event-weight and detector-response children remain open.

Next repository action: open a focused PR for the branch and require exact-final-head MC Validation. Merge only if curated ruff, full non-integration pytest, and current-base ancestry pass. A green Python CI authorizes only this deterministic provenance primitive.

Next scientific atom after this gate: `ARU-MC-G4-LOADER-INITIAL-CWD-001` is the smallest independent input needed to resolve empty path components and relative slash-containing `DT_NEEDED`; alternatively `ARU-MC-G4-LOADER-CACHE-CONFIG-001` is the next high-value loader-resolution state if cwd is unavailable.

No production Geant4 campaign was run, no beam or production-MC ROOT bytes were opened, and no angular distribution, event weight, B2/B8, PID, penetration, timing, calibration, pile-up, ESS, p-value, rate, or detector-performance quantity was regenerated or promoted. #1182 and CL-021 remain gated.
