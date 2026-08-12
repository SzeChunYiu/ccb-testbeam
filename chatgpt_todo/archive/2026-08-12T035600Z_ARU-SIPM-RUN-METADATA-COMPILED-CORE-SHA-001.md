# ARU-SIPM-RUN-METADATA-COMPILED-CORE-SHA-001

Status: `PARTIAL` pending protected exact-final-head root CI and integration.

Parents: #977, #1067. Base: protected `ccb-testbeam/main@896c6c0bca2fa0d5fdf50a5d33840e4b8ab75b60`. Reviewed core gitlink: `ccb-sipm-core@3627dc87137a9f33f511a755671414b11853c0a0`.

## Atomic contract

The metadata field `digitizer.ccb_sipm_core_commit` must identify the ccb-sipm-core revision compiled into the executable that produced `adc_*`, not a mutable caller label.

Let `H_link` be the superproject gitlink, `H_compiled` the revision encoded in the executable, and `H_meta` the serialized revision. The bounded source-provenance invariant is

`H_meta = H_compiled = H_link`.

This is necessary but not sufficient for binary/toolchain provenance or measured-electronics calibration authority.

## Evidence inspected

- `geant4/single_stave/src/RunAction.cc`: sidecar obtains `ccb_sipm_core_commit` only from `getenv("CCB_SIPM_CORE_COMMIT")` and otherwise serializes `"unspecified"`; the same digitizer block hard-codes `validation_status="OK"`.
- `geant4/single_stave/slurm/submit_systematic.sh`: exports `CCB_GIT_COMMIT`, but not `CCB_SIPM_CORE_COMMIT`.
- `scripts/single_stave/sipm_sensitivity.py`: `load_sidecar()` accepts `validation_status=="OK"` plus nonempty `digitizer_config_sha256`; it does not require a bound core commit.
- `ccb-sipm-core@3627dc...`: `run_metadata()` already hashes the exact cached history-complete effective kernel consumed by waveform convolution and keeps arbitrary sampled impulses `CUSTOM_UNVALIDATED`; configuration/runtime-kernel identity therefore exists but is scientifically distinct from source revision identity.
- #977 acceptance explicitly requires an exact pinned core commit; #977 had been closed despite the runtime path above.

## Mechanism universe

H1: caller environment identifies the compiled core. Rejected: the variable is mutable, can be absent, and can be forged.

H2: `digitizer_config_sha256` identifies the source revision. Rejected: configuration identity and implementation identity are different state variables; two code revisions may share identical model metadata.

H3: derive current source-tree gitlink at launch. Incomplete: a stale executable can outlive a source checkout change.

H4: compile the reviewed gitlink identity into the executable and overwrite the legacy environment bridge before `main()`. Survives as the bounded repair.

H5: full executable-byte/build-manifest identity. Stronger but not yet implemented; spawned as a child rather than conflated with H4.

## Implementation

Branch `audit/sipm-compiled-core-sha-binding-v1` adds:

- `geant4/single_stave/include/SipmBuildProvenance.hh`: exact lowercase 40-hex gitlink literal.
- `geant4/single_stave/src/SipmBuildProvenance.cc`: translation unit included by the existing `src/*.cc` CMake glob. A pre-main static initializer overwrites `CCB_SIPM_CORE_COMMIT` from the compiled literal (`setenv(..., overwrite=1)`) and aborts if the binding cannot be installed.
- `tests/test_sipm_compiled_core_provenance.py`: exact gitlink/literal equality, hostile-environment compile/run discriminator, and CMake source-glob composition check.

## Experiments

Local isolated C++ fixture, using the same header/translation-unit logic:

`c++ -std=c++17 -Wall -Wextra -Wpedantic ...`

with `CCB_SIPM_CORE_COMMIT=deadbeef` executed the probe and printed exactly

`3627dc87137a9f33f511a755671414b11853c0a0`.

No RNG, Geant4 transport, detector data, or production MC participated. Protected root CI is the integration authority and is still required on the final branch head.

## Four role-separated reviews

1. **Detector-response/provenance lead** — Evidence: root sidecar writer, launcher, core metadata contract, #977. Counter-hypothesis: environment is sufficient build identity. Falsifier: missing/hostile environment. Residual: binary/toolchain identity. Vote: `ACCEPT bounded compiled-source binding / BLOCK #977 COMPLETE`.
2. **Adversarial mechanism reviewer** — Evidence: mutable env bridge and independent config digest. Counter-hypothesis: config digest is equivalent to code provenance. Falsifier: implementation revision is not an input to that digest. Residual: stale build/toolchain. Vote: `REJECT env/config equivalence / ACCEPT H4`.
3. **Independent validation reviewer** — Evidence: deterministic compile/run hostile control and gitlink equality test. Counter-hypothesis: source inspection alone proves execution. Falsifier: explicit compiled probe required. Residual: full Geant4 executable not locally built. Vote: `ACCEPT software discriminator / BLOCK detector inference`.
4. **Claims/provenance reviewer** — Evidence: #977/#1067 acceptance and downstream sensitivity gate. Counter-hypothesis: hard-coded `validation_status=OK` makes source identity optional. Falsifier: consumer accepts `OK` while commit may be `unspecified`. Residual: historical-output audit and calibration authority. Vote: `REOPEN #977/#1067 / BLOCK waveform and measured-electronics claim promotion`.

## Cross-scale propagation

Micro/software: compiled source revision becomes immutable executable state for this gitlink.

Run metadata: legacy sidecar bridge receives the compiled revision instead of caller state.

Study: new campaign outputs can carry a real core source SHA, but downstream acceptance still needs explicit checks and historical sidecars remain suspect.

Claim: no detector-response, timing, pile-up, PID, efficiency, or DATA/MC claim is promoted.

## Spawned children

- `ARU-SIPM-RUN-METADATA-BINARY-BUILD-MANIFEST-001`: compiler/linker/build-input/executable-byte identity.
- `ARU-ELEC-IMPULSE-HISTORICAL-OUTPUT-AUDIT-001`: locate/reject prior sidecars with `unspecified` or caller-forged core identity.
- `ARU-SIPM-SENSITIVITY-CORE-SHA-GATE-001`: make downstream sensitivity analysis require exact core SHA/provenance state.
- #1072 requested/effective operating-point closure.
- #1067 source-byte binding, calibration/resampling closure, and positive measured authorization.

No project-level completion is asserted.
