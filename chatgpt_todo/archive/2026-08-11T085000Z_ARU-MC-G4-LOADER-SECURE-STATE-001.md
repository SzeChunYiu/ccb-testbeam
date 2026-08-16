# ARU-MC-G4-LOADER-SECURE-STATE-001

Status: PARTIAL — deterministic software/provenance mechanism implemented; exact-head repository CI and real HIBEAM runtime evidence required.

Parent: `ARU-MC-G4-LOADER-SEARCH-001` under #1182. Protected main at branch creation: `4122dc6d71e64fd35697868afa6057e11377138a`.

## Atom definition and scientific meaning

The existing runtime receipt captures loader-control environment variables and content-bound executable mappings, while the runtime/link co-observation binds ELF metadata from the same opened mapped-object descriptors. Neither establishes whether the Linux dynamic loader was operating in secure-execution mode. That state changes whether variables such as `LD_LIBRARY_PATH`, `LD_PRELOAD`, and `LD_AUDIT` can be treated as eligible loader-search inputs.

Inputs: PASS `ccb_geant4_runtime_dependency_attestation_v1`; PASS child `ccb_geant4_runtime_link_coobservation_v1`; `/proc/<pid>/stat`; `/proc/<pid>/auxv` for the exact `(pid,starttime_ticks)` already named by both receipts.

Output: PASS/BLOCKED `ccb_geant4_loader_secure_state_attestation_v1` recording exact auxv byte count/SHA-256, `AT_SECURE`, launch `AT_UID/AT_EUID/AT_GID/AT_EGID`, receipt ancestry, and conservative interpretation of captured loader environment variables. Units: none. Statistical unit: none; this is a deterministic process-state contract.

## Invariants and descriptions

For runtime receipt `R`, co-observation receipt `C`, and live process `P`:

`C.parent_runtime_dependency_receipt_sha256 = R.receipt_sha256`

`(pid_R,start_R) = (pid_C,start_C) = (pid_P,start_P_before) = (pid_P,start_P_after)`.

For the already-attested ELF64 little-endian x86-64 execution domain, `/proc/PID/auxv` is parsed as ordered 16-byte `<uint64 type,uint64 value>` entries. Require one `AT_NULL=(0,0)` terminator, no duplicate non-null type, exactly one `AT_SECURE`, and `AT_SECURE in {0,1}`.

If `AT_SECURE=1`, the recorded loader-control environment must not be used as authoritative evidence that the loader searched or loaded from those values. If `AT_SECURE=0`, those values are only `ELIGIBLE_SEARCH_INPUT_NOT_YET_PROVEN_EFFECTIVE`; RPATH/RUNPATH, loader cache/configuration, token expansion, hwcaps, preloads/audits, cwd, and direct/transitive search remain separate atoms.

GNU libc additionally exposes `glibc.rtld.enable_secure=1`, which can request secure-mode behavior even when kernel `AT_SECURE=0`. Until exact glibc-version semantics are bound, that combination BLOCKS rather than being collapsed into the kernel bit.

## Mechanism universe

H1: captured `LD_LIBRARY_PATH` is always authoritative. Rejected: secure execution changes/ignores loader environment controls.

H2: equal real/effective UID/GID proves non-secure execution. Rejected: capabilities and Linux Security Modules can also cause `AT_SECURE`.

H3: directly bind `AT_SECURE` from the same live process auxiliary vector while process identity is stable. Survives as the bounded kernel secure-execution input.

H4: `AT_SECURE` alone reconstructs the complete loader decision. Rejected: it does not bind RPATH/RUNPATH choice, cwd, cache/config, tokens/hwcaps, explicit loader invocation, preload/audit content, or later `dlopen`.

H5: `AT_SECURE=0` always means libc secure behavior is off. Rejected for current generic provenance because `glibc.rtld.enable_secure=1` exists; the implementation blocks that unresolved combination.

Equivalent UID/GID heuristics were collapsed because they are observationally weaker than direct auxiliary-vector evidence.

## Authoritative external evidence

Linux `getauxval(3)` documents `AT_SECURE` as the executable-secure flag, including set-ID, file capabilities, or LSM mechanisms; `ld.so(8)` documents secure-execution effects on loader variables. GNU libc documents `glibc.rtld.enable_secure=1` as running as if setuid and as a one-way enabling tunable. System V dynamic-linking documentation distinguishes `DT_RPATH`, `LD_LIBRARY_PATH`, `DT_RUNPATH`, path-containing dependencies, and direct-dependency search semantics.

## Repository evidence inspected

- `geant4/setup_and_run.sh`: historical front door explicitly constructs `LD_LIBRARY_PATH` from VGM and the conda prefix before `./hibeam_g4`.
- `tools/audit/geant4_runtime_dependency_attestation.py`: captures initial loader-control environment and mapped executable objects.
- `tools/audit/geant4_runtime_link_coobservation.py`: binds mapped-object bytes + ELF metadata but explicitly leaves historical loader search unresolved.
- #1182 and its latest provenance comments: loader search remains an open child; CL-021 remains gated.

## Implementation and exact execution

Branch: `audit/geant4-loader-secure-state`, created from exact main `4122dc6d71e64fd35697868afa6057e11377138a`.

Implementation commit: `ae86fd58c81400fe98e6336a6cf4eca0c9e71eef` (`tools/audit/geant4_loader_secure_state_attestation.py`).

Hostile-test commit: `875ac55234d7c35177109d1379c8df7a58a8ceff` (`tests/test_geant4_loader_secure_state_attestation.py`).

Curated-CI inclusion commit: `972e95e1b9a3c2f8d2dc25d1cec913b8416989ea`.

Local exact committed-code reconstruction, Python 3.13/Linux/no RNG:

`PYTHONPATH=/tmp/ccb_loader_exact python -m pytest -q /tmp/ccb_loader_exact/tests/test_geant4_loader_secure_state_attestation.py`

Result: `10 passed in 0.04s`.

Exact content identities checked against GitHub branch blobs:

- tool: 11833 bytes; SHA-256 `fc4802ea4f4e6db7fe50732f772d03f6744f28f1e4fa892012e2693f300c3c64`; Git blob SHA-1 `2aa3e3dfed76204d51dbfd2b718dc4393870a052` (matches GitHub).
- tests after repository import adaptation: 6996 bytes; SHA-256 `3fe7b3695ee37351dfb95a61fd3d17c61376b39de20a2d2d08ee25db1ceae176`; Git blob SHA-1 `192348cee7c5fcf09209bea42f1778860e6388fc` (matches GitHub).

Discarded evidence: the pre-publication test copy used `import geant4_loader_secure_state_attestation as loader`; its 6984-byte hash therefore does not identify the repository test and is not used. The repository-adapted bytes above were reconstructed and rerun before recording evidence.

Hostile controls: nonsecure `AT_SECURE=0`; secure `AT_SECURE=1`; duplicate/missing/nonboolean `AT_SECURE`; malformed auxv length; wrong receipt ancestry; process-identity mismatch; `glibc.rtld.enable_secure=1` with `AT_SECURE=0`; nonzero auxiliary data after `AT_NULL`.

No local ruff executable was available; no local ruff PASS is claimed. Exact-head GitHub MC Validation is required.

## Four sequential AI review passes

### (a) Runtime/physics integration lead — ACCEPT bounded mechanism / REVISE full loader provenance
Evidence: setup script, runtime receipt schema, co-observation receipt, Linux/glibc loader semantics. Strongest counter-hypothesis: historical `LD_LIBRARY_PATH` assignment already identifies effective library selection. Falsifier: secure execution can suppress that authority. Residual uncertainty: no immutable real HIBEAM auxv/runtime receipt, cwd, cache/config, or glibc build identity.

### (b) Adversarial systems reviewer — ACCEPT direct auxv measurement / BLOCK complete loader-decision claim
Evidence: hostile auxv fixtures and receipt ancestry. Strongest counter-hypothesis: UID/GID equality is an adequate non-secure proxy. Falsifier: capabilities/LSM can independently set `AT_SECURE`. Residual: `glibc.rtld.enable_secure`, explicit loader invocation, token/hwcaps/cache semantics, preload/audit content/order, later loads.

### (c) Independent validation reviewer — ACCEPT deterministic oracle / BLOCK physics inference
Evidence: ten exact committed-code fixtures; no RNG. Strongest counter-hypothesis: a PASS receipt validates a generator population. Falsifier: no Geant4 event, source sample, detector response, weight, or statistical estimator participates. Residual: exact-head CI and real runtime exercise.

### (d) Claims/provenance reviewer — ACCEPT provenance child / BLOCK CL-021 promotion
Evidence: #1182 acceptance contract and current claim-gating lineage. Strongest counter-hypothesis: stronger runtime loader provenance closes the historical source claim. Falsifier: linker command/static inputs, loader decision, late load/unload, wrapper/descendant, immutable consumption, runtime manifest, compiled hostile source/stopping controls, event weights, and detector chain remain unresolved.

## Stable concerns / children

- `PROV-G4-LOADER-SECURE-001`: exact `AT_SECURE` process-state binding — implemented, pending exact-head CI and real HIBEAM exercise.
- `PROV-G4-LOADER-GLIBC-TUNABLE-001`: exact glibc identity and `glibc.rtld.enable_secure` semantics.
- `ARU-MC-G4-LOADER-INITIAL-CWD-001`: initial cwd, including empty path components and relative slash-containing dependencies.
- `ARU-MC-G4-LOADER-CACHE-CONFIG-001`: `/etc/ld.so.cache`, `ld.so.conf`/includes, default dirs.
- `ARU-MC-G4-LOADER-TOKEN-HWCAPS-001`: `$ORIGIN/$LIB/$PLATFORM`, hardware-capability subdirectories and platform state.
- `ARU-MC-G4-PRELOAD-AUDIT-001`: `LD_PRELOAD`, `/etc/ld.so.preload`, `LD_AUDIT`, explicit loader options, content/order.
- Existing `ARU-MC-G4-LINK-COMMAND-001`, late-`dlopen`, non-executable relocation/GOT/PLT, wrapper/descendant, immutable-consumption, runtime-manifest, compiled source/stopping, event-weight, and detector-response atoms remain open.

## Claim/wiki consequence

No public physics claim changes state. #1182 and CL-021 remain GATED/BLOCKED for generator-runtime inference. No production Geant4, beam ROOT, production-MC ROOT, B2/B8, PID, timing, calibration, pile-up, ESS, p-value, rate, or detector-performance result was regenerated.
