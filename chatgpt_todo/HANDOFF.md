# Latest Handoff

## Production SiPM sidecar core revision was not executable-bound

Selected atom: `ARU-SIPM-RUN-METADATA-COMPILED-CORE-SHA-001`.

Protected `ccb-testbeam/main@896c6c0bca2fa0d5fdf50a5d33840e4b8ab75b60` now has an executable/tested SiPM gitlink after #1276, but the run-metadata layer still had a separate provenance gap. `RunAction::WriteMetadataSidecar()` obtains `digitizer.ccb_sipm_core_commit` only from environment variable `CCB_SIPM_CORE_COMMIT` and otherwise serializes `unspecified`. The systematic campaign launcher exports `CCB_GIT_COMMIT` but not this core variable. Nevertheless the sidecar sets `digitizer.validation_status=OK`, and `scripts/single_stave/sipm_sensitivity.py` accepts `OK` plus a nonempty config digest without requiring exact core source identity.

The contract is `H_meta = H_compiled = H_link`: the SHA in a produced sidecar must equal both the ccb-sipm-core revision encoded in that executable and the reviewed superproject gitlink. The existing `digitizer_config_sha256` and core effective-kernel digest remain necessary identities of numerical state; they cannot identify the implementation revision because code revision is not an input to those digests.

Mechanism review rejected caller environment as provenance because it is mutable/unset/forgeable, and rejected deriving only the current checkout at launch because a stale executable may not have been rebuilt. The bounded surviving repair compiles the reviewed gitlink literal into the executable itself. Full executable-byte/compiler/linker provenance remains a separate child.

Branch `audit/sipm-compiled-core-sha-binding-v1` starts from exact protected main and adds `SipmBuildProvenance.hh` with exact gitlink `3627dc87137a9f33f511a755671414b11853c0a0`; `SipmBuildProvenance.cc`, automatically included by the existing `src/*.cc` CMake glob, overwrites `CCB_SIPM_CORE_COMMIT` from that compiled constant before `main()` and aborts if the binding cannot be installed; and `tests/test_sipm_compiled_core_provenance.py` requires the literal to equal `git ls-tree HEAD geant4/single_stave/sipm`, compiles/runs the binding translation unit against a hostile pre-set `deadbeef` environment, and guards the CMake composition assumption.

An isolated local C++17 fixture using the exact same binding logic compiled with `-Wall -Wextra -Wpedantic` and, under hostile `CCB_SIPM_CORE_COMMIT=deadbeef`, printed exactly `3627dc87137a9f33f511a755671414b11853c0a0`. This is deterministic software evidence only; no local GitHub clone or Geant4 detector execution was possible because external DNS remained unavailable.

#977 was reopened because its acceptance explicitly requires the exact core commit and the prior closure was based on #1248 before this execution-identity defect was inspected. Stable concern `CCB-977-COMPILED-CORE-SHA-001` records the mechanism, falsifier, implementation, roles and residuals. #1067 was also reopened because source-byte binding, calibration/resampling validation, positive measured authorization and historical-output audit remain material.

### Sequential AI review votes

**Detector-response/provenance lead:** `ACCEPT bounded compiled-source binding / BLOCK #977 COMPLETE`. Strongest counter-hypothesis was that an environment label identifies the executable; missing/hostile environment falsifies it. Residual is binary/toolchain identity.

**Adversarial mechanism reviewer:** `REJECT caller-env and config-digest equivalence / ACCEPT compiled literal`. A numerical config digest can remain identical across distinct code revisions; source identity is an independent variable.

**Independent validation reviewer:** `ACCEPT deterministic compile/run probe / BLOCK detector inference`. Protected exact-final-head root CI remains the integration gate; no detector population participates.

**Claims/provenance reviewer:** `REOPEN #977/#1067 / BLOCK waveform, measured-electronics and detector-performance promotion`. Exact core SHA, effective config/kernel identity and calibration authority are separate gates.

Archive: `chatgpt_todo/archive/2026-08-12T035600Z_ARU-SIPM-RUN-METADATA-COMPILED-CORE-SHA-001.md`.

Next immediate gate: exact-final-head protected MC Validation on the bounded branch/PR; merge only if all required contexts pass and current-main ancestry remains clean. Highest-value subsequent children are historical sidecar audit and a downstream sensitivity gate that refuses missing/non-exact core identity. A stronger `ARU-SIPM-RUN-METADATA-BINARY-BUILD-MANIFEST-001` must bind compiler/linker/build inputs or executable digest.

No beam bytes, production Geant4 population, measured electronics waveform, DATA↔MC result, timing/PID metric, pile-up efficiency, rate, ESS, p-value, or detector-performance quantity was generated or promoted.
