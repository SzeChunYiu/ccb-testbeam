# Latest Handoff

## Custom sampled SiPM impulses can still be mislabeled `MEASURED`; history lineage also needs reintegration

Protected `ccb-testbeam` main at selection is `0800a0cece4dff733c82e024b4c764e85ce947d9`. Its `geant4/single_stave/sipm` gitlink points to core `5c6bb0278be4246f3da9007b71a5d13024b968ca`, a sibling of the validated history line rather than its descendant. That main therefore contains the measured-impulse fail-closed change but drops the previously validated dark-history and history-complete convolution changes.

Current `ccb-sipm-core` main is `e71fd26c915a402590931d2a7657157f04277235`, merged from core #7 onto `68eadf3f6ac3a95b37e0d8c86843573736a5ea97`. It composes scheduling/DCR history, history-complete kernel support, and malformed measured-impulse fail-closed behavior. Core #7 exact-head CI run `31522503501`, job `93882757978`, passed checkout, configure, build and CTest.

The selected child is `ARU-ELEC-IMPULSE-PROVENANCE-STATE-001` under open #1067. The numerical kernel and the scientific provenance state are separate observables. Necessary authorization condition:

`MEASURED_authorized => source_identity_bound && exact_source_digest_bound && exact_effective_kernel_digest_bound && calibration_resampling_validation_passed`.

Core `e71fd26...` does not yet satisfy this. `ModelConfig::validate()` converts any structurally valid sampled impulse to `impulse_model=MEASURED`; `ResponseSimulator::run_metadata()` then emits `impulse_response_status=MEASURED`. The same implementation deliberately leaves exact source/effective-kernel digest fields blank unless an external validated layer supplies them. Thus an arbitrary synthetic vector can be advertised as a measured electronics response without a content-bound calibration object.

## Executed discriminating experiment

Draft core PR #8 was opened from exact `core main@e71fd26...`; current head `b0305fa0f1f5b22729ac944ea8f1def7b95ce5d6`. `tests/test_impulse_provenance_state.cc` adds two deterministic hostile controls:

1. a valid synthetic triangular impulse with no source identity and no exact digests must not emit `MEASURED`;
2. the same synthetic impulse with only a human-readable source id must still not emit `MEASURED`.

Core CI run `31522917984`, job `93884187652`, on the PR merge ref configured and built successfully. Four existing tests passed: core, dark-history, kernel-history, and measured-impulse fail-closed. The new provenance-state test failed exactly the two intended assertions:

- `synthetic sampled kernel without provenance must not claim MEASURED`
- `source label without exact digests/validation must not authorize MEASURED`

CTest summary was 4/5 tests passed, 1/5 failed, with two assertion failures. This is a successful falsification of the current authorization semantics, **not** a green implementation result. PR #8 must remain draft/red until the production state model is repaired.

## Mechanism review

Vector presence cannot establish bench provenance; a synthetic fixture provides the counterexample. A human-readable source label alone also cannot bind the calibration bytes or the effective runtime kernel. Two surviving fail-closed designs remain: represent sampled kernels as `CUSTOM_UNVALIDATED` until an explicit typed promotion gate has exact content/provenance + calibration evidence, or reserve `MEASURED` entirely until that infrastructure exists.

The exact effective-kernel identity must refer to the history-complete kernel used by convolution, not merely the output-window length. For `N_out=floor((window_end-window_start)/dt)+1` and `H=max(0,window_start-history_start)`, the current numerical convolution requires `N_kernel=N_out+ceil(H/dt)`.

## Four sequential AI review state

- **Electronics/calibration lead — BLOCK current MEASURED promotion / ACCEPT bounded diagnosis.** Strongest counter-hypothesis: numerical validity proves measured response. Synthetic triangle falsifies it. Exact promotion schema remains unresolved.
- **Adversarial mechanism reviewer — REJECT vector/source-label authorization / ACCEPT non-authoritative custom state.** A copied label does not bind bytes; exact digest and validation are nuisance/dependency variables.
- **Independent validation reviewer — ACCEPT exact failing falsifier / BLOCK authority until repaired CI.** Existing green #7 CI encoded the wrong expected provenance state; the orthogonal negative control fails while all other composed tests stay green.
- **Claims/provenance reviewer — BLOCK #1067 completion and measured-electronics promotion.** Blank exact digests and an authoritative-looking `MEASURED` status are incompatible states.

## Testbeam integration repair

Draft testbeam PR #1229 was created from exact protected `main@0800a0ce...`. Its first commit changes only the SiPM gitlink to `ccb-sipm-core@e71fd26c915a402590931d2a7657157f04277235`, restoring the validated dark-history/kernel-history lineage while retaining fail-closed malformed-impulse semantics. The PR also carries this archive and coordination state. Do not merge it without exact-head protected MC Validation.

This integration does **not** close #1067 or #1096. #1067 retains the provenance-promotion, exact-digest, calibration/resampling and historical-output-audit leaves. #1096 retains physical history-horizon convergence and downstream waveform compatibility. #1065 remains the sub-grid timing atom.

## Claims boundary and next handoff

No beam data, production Geant4/MC sample, measured single-PE calibration, detector timing, baseline, pile-up, PID, efficiency, rate, ESS, p-value or detector-performance quantity was regenerated or promoted. The failing core PR #8 is software/provenance evidence only.

Next highest-value action: repair core PR #8 on the same history-complete lineage so a custom sampled kernel defaults to a non-authoritative provenance state. Add hostile incomplete-provenance states and a separately specified fully authorized transition; then require exact-head Core CI to turn the discriminator green. In parallel, consume exact-head testbeam #1229 MC Validation and merge only if the protected check succeeds. Archive: `chatgpt_todo/archive/2026-08-11T183100Z_ARU-ELEC-IMPULSE-PROVENANCE-STATE-001.md`.
