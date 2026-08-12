# ARU-SIPM-RUN-METADATA-COMPILED-CORE-SHA-001

Status: `VALIDATED` at bounded source-revision/software-provenance scope. Parent #977 and cross-dependency #1067 remain `OPEN/PARTIAL`.

Parents: #977, #1067. Reviewed base: protected `ccb-testbeam/main@896c6c0bca2fa0d5fdf50a5d33840e4b8ab75b60`. Reviewed core gitlink: `ccb-sipm-core@3627dc87137a9f33f511a755671414b11853c0a0`. Integrated by PR #1280 as protected `main@21de9a79cd32a2ecbc4005381c96322367ef3800`.

## Atomic contract

The metadata field `digitizer.ccb_sipm_core_commit` must identify the ccb-sipm-core revision compiled into the executable that produced `adc_*`, not a mutable caller label.

Let `H_link` be the superproject gitlink, `H_compiled` the revision encoded in the executable, and `H_meta` the serialized revision. The bounded source-provenance invariant is

`H_meta = H_compiled = H_link`.

This is necessary but not sufficient for binary/toolchain provenance or measured-electronics calibration authority.

## Evidence inspected

- `geant4/single_stave/src/RunAction.cc`: pre-repair sidecar obtained `ccb_sipm_core_commit` only from `getenv("CCB_SIPM_CORE_COMMIT")` and otherwise serialized `"unspecified"`; the same digitizer block hard-coded `validation_status="OK"`.
- `geant4/single_stave/slurm/submit_systematic.sh`: exports `CCB_GIT_COMMIT`, but not `CCB_SIPM_CORE_COMMIT`.
- `scripts/single_stave/sipm_sensitivity.py`: `load_sidecar()` accepts `validation_status=="OK"` plus nonempty `digitizer_config_sha256`; it does not require a bound core commit.
- `ccb-sipm-core@3627dc...`: `run_metadata()` hashes the exact cached history-complete effective kernel consumed by waveform convolution and keeps arbitrary sampled impulses `CUSTOM_UNVALIDATED`; configuration/runtime-kernel identity is scientifically distinct from source revision identity.
- #977 acceptance explicitly requires an exact pinned core commit; #977 had been closed despite the runtime path above and was reopened during this atom.

## Mechanism universe

H1: caller environment identifies the compiled core. Rejected: the variable is mutable, can be absent, and can be forged.

H2: `digitizer_config_sha256` identifies the source revision. Rejected: configuration identity and implementation identity are different state variables; two code revisions may share identical model metadata.

H3: derive current source-tree gitlink at launch. Incomplete: a stale executable can outlive a source checkout change.

H4: compile the reviewed gitlink identity into the executable and overwrite the legacy environment bridge before `main()`. Survives and is implemented as the bounded repair.

H5: full executable-byte/build-manifest identity. Stronger but not implemented here; retained as a child rather than conflated with H4.

## Implementation

PR #1280 added:

- `geant4/single_stave/include/SipmBuildProvenance.hh`: exact lowercase 40-hex gitlink literal.
- `geant4/single_stave/src/SipmBuildProvenance.cc`: translation unit included by the existing `src/*.cc` CMake glob. A pre-main static initializer overwrites `CCB_SIPM_CORE_COMMIT` from the compiled literal (`setenv(..., overwrite=1)`) and aborts if the binding cannot be installed.
- `tests/test_sipm_compiled_core_provenance.py`: exact gitlink/literal equality, hostile-environment compile/run discriminator, and CMake source-glob composition check.

## Experiments and exact execution

Local isolated C++ fixture, using the same header/translation-unit logic:

`c++ -std=c++17 -Wall -Wextra -Wpedantic ...`

with `CCB_SIPM_CORE_COMMIT=deadbeef` executed the probe and printed exactly

`3627dc87137a9f33f511a755671414b11853c0a0`.

No RNG, Geant4 transport, detector data, or production MC participated in that local fixture.

The final PR head was exact `9389bd4485ac2af5df0f6420606ea4be8e9ecb7f`. Protected branch push MC Validation run `31561698833` completed `SUCCESS`: recursive checkout materialized exact core `3627dc...`; core conflict-marker self-test/scan passed; CMake used GNU C++ 13.3.0; all 7 core CTests passed; curated ruff reported `All checks passed!`; full `pytest tests/ -q --ignore=tests/integration` reported `2118 passed, 2 skipped, 8 xfailed, 1 xpassed, 18 warnings in 125.18s`; the final enforcement step recorded SiPM-core, ruff and pytest statuses all `0`. Pull-request MC Validation run `31561716054` independently completed `SUCCESS` on the same final head.

Only after both exact-final-head contexts were green and protected main remained exact `896c6c0...` was PR #1280 marked ready and squash-merged with expected-head guard. GitHub returned merge SHA `21de9a79cd32a2ecbc4005381c96322367ef3800`; current protected main was then verified at that exact commit. Independent post-merge main-push run `31561985291` started on `21de9a79...` and was still in progress at the time of this addendum, so no post-merge-main PASS is claimed here.

## Four role-separated reviews

1. **Detector-response/provenance lead** — Evidence: root sidecar writer, launcher, core metadata contract, #977, exact protected CI. Counter-hypothesis: environment is sufficient build identity. Falsifier: missing/hostile environment. Residual: binary/toolchain identity. Vote: `ACCEPT bounded child VALIDATED / BLOCK #977 COMPLETE`.
2. **Adversarial mechanism reviewer** — Evidence: mutable env bridge, independent config digest, hostile control. Counter-hypothesis: config digest is equivalent to code provenance. Falsifier: implementation revision is not an input to that digest. Residual: stale/full build bytes. Vote: `REJECT env/config equivalence / ACCEPT compiled literal`.
3. **Independent validation reviewer** — Evidence: deterministic local probe, exact gitlink equality test, both final-head protected CI contexts. Counter-hypothesis: source inspection alone proves execution. Falsifier: explicit compiled probe and protected execution were required. Residual: the root workflow compiles/tests the core dependency and the small provenance fixture but does not perform a production Geant4 detector run. Vote: `ACCEPT software/source-revision closure / BLOCK detector inference`.
4. **Claims/provenance reviewer** — Evidence: #977/#1067 acceptance, downstream sensitivity gate and merge-close governance. Counter-hypothesis: hard-coded `validation_status=OK` makes source identity optional. Falsifier: consumer accepts `OK` while core identity can historically be absent. Residual: downstream admission, historical sidecar audit, calibration authority. Vote: `ACCEPT bounded repair / KEEP #977/#1067 OPEN and claims gated`.

## Cross-scale propagation

Micro/software: caller state can no longer override the compiled core revision for the reviewed build; gitlink drift without literal update is a protected-test failure.

Run metadata: the existing sidecar bridge receives executable-owned core source identity for future builds containing this repair.

Study: source identity alone is not yet an admission rule. `sipm_sensitivity.py` still needs an explicit exact-core-SHA gate, and historical sidecars need audit.

Claim: no detector-response, timing, pile-up, PID, efficiency, rate, or DATA/MC claim is promoted.

## Spawned children

- `ARU-SIPM-RUN-METADATA-BINARY-BUILD-MANIFEST-001`: compiler/linker/build-input/executable-byte identity.
- `ARU-ELEC-IMPULSE-HISTORICAL-OUTPUT-AUDIT-001`: locate/reject prior sidecars with `unspecified` or caller-forged core identity.
- `ARU-SIPM-SENSITIVITY-CORE-SHA-GATE-001`: make downstream sensitivity analysis require exact core SHA/provenance state.
- #1072 requested/effective operating-point closure.
- #1067 source-byte binding, calibration/resampling closure, and positive measured authorization.

No project-level completion is asserted.
