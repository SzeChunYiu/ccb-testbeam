# ARU-ELEC-IMPULSE-PROVENANCE-STATE-001

Status: **PARTIAL / CONFIRMED_PROVENANCE_OVERCLAIM / FAILING_EXACT_CI_DISCRIMINATOR / CORE_FIX_NOT_YET_VALIDATED**

Parent: ccb-testbeam #1067. Related integration: #1096, core PR #7, core draft PR #8, testbeam PR #1229.

## Atom contract

The numerical sampled impulse, its scientific provenance state, and the effective runtime kernel are distinct objects. A structurally valid vector is insufficient to authorize a measured/calibrated electronics claim.

Necessary authorization invariant:

`MEASURED_authorized => source_identity_bound && exact_source_digest_bound && exact_effective_kernel_digest_bound && calibration_resampling_validation_passed`.

The effective-kernel identity must describe the actual elapsed-time kernel used by waveform convolution, including the history extension `N_kernel = N_out + ceil(max(0, window_start-history_start)/dt)`.

## Evidence inspected

- Protected testbeam main `0800a0cece4dff733c82e024b4c764e85ce947d9` points the SiPM gitlink to non-descendant core `5c6bb027...`, which omits the validated dark-history and kernel-history lineage.
- Current core main `e71fd26c915a402590931d2a7657157f04277235` composes the fail-closed measured-impulse code onto history-complete `68eadf3...`.
- Core #7 exact-head CI run `31522503501`, job `93882757978`, passed configure/build/test.
- Core #7 nevertheless reconciles any valid sampled impulse to `impulse_model=MEASURED` and emits `impulse_response_status=MEASURED` even when exact source/effective-kernel digest fields are empty.
- Existing ccb-testbeam #1067 discussion already requires a custom kernel to remain `CUSTOM_UNVALIDATED` unless source identity/hash and calibration validation authorize `MEASURED`.

## Mechanisms / hypotheses

H1: sampled-vector presence is sufficient evidence of measured calibration. **Eliminated**: a synthetic vector can satisfy all numerical validators while having no bench provenance.

H2: a human-readable source id is sufficient. **Eliminated**: an arbitrary mutable string does not bind source bytes or effective runtime kernel.

H3: custom sampled vectors default to a non-authoritative state, with a typed promotion gate to `MEASURED` only after exact provenance and calibration validation. **Survives and preferred.**

H4: reserve `MEASURED` entirely until exact digest/calibration infrastructure exists. **Survives as stricter fail-closed limiting case.**

## Discriminating experiment executed

Core draft PR #8 was created from exact core `main@e71fd26...`, head `b0305fa0f1f5b22729ac944ea8f1def7b95ce5d6`.

`tests/test_impulse_provenance_state.cc` contains two deterministic hostile controls:

1. valid synthetic triangular sampled impulse, no source id, no source digest, no effective-kernel digest; require metadata status != `MEASURED`;
2. same vector plus only a human-readable source id; still require status != `MEASURED`.

Core CI run `31522917984`, job `93884187652`:

- checkout: PASS
- configure: PASS
- build: PASS
- CTest legacy/core/dark-history/kernel-history/measured-impulse tests: PASS
- provenance-state test: **FAIL as designed** with both hostile assertions failing
- aggregate: 4/5 tests pass; 1/5 fails; two provenance-state assertion failures.

This is deterministic software/provenance evidence only. No detector data or production MC participates.

## Four sequential AI review passes

### Electronics/calibration lead
Evidence: #1067 contract, core #7 code/tests, exact CI. Strongest counter-hypothesis: numerical validation is enough to call a response measured. Falsifier: synthetic triangle passes numerical checks with no calibration object. Residual uncertainty: exact promotion schema and digest implementation remain undecided. Vote: **BLOCK current MEASURED promotion / ACCEPT bounded diagnosis**.

### Adversarial mechanism reviewer
Evidence: source-id-only hostile fixture and blank digest state. Strongest counter-hypothesis: source label is adequate attribution. Falsifier: label does not bind bytes and can be copied independently. Residual uncertainty: whether authorization lives in core or an external validated provenance layer. Vote: **REJECT label/presence authorization / ACCEPT CUSTOM_UNVALIDATED class**.

### Independent validation reviewer
Evidence: exact PR-head GitHub Actions build and deterministic CTest. Strongest counter-hypothesis: existing green core #7 CI establishes correctness. Falsifier: the green suite encoded the wrong expectation; new orthogonal negative controls fail on the same merged behavior. Residual uncertainty: repaired exact-head CI not yet available. Vote: **ACCEPT falsifier / BLOCK merge of PR #8 until implementation turns it green**.

### Claims/provenance reviewer
Evidence: #1067 acceptance criteria and run-metadata fields. Strongest counter-hypothesis: blank digests are harmless because PR #7 says provenance is unresolved. Falsifier: emitted status itself is authoritative-looking `MEASURED` and therefore contradicts unresolved provenance. Residual uncertainty: historical outputs using this state have not been audited. Vote: **BLOCK #1067 completion and measured-electronics claim promotion**.

## Cross-scale compatibility

Core `e71fd26...` restores compatibility between explicit prehistory, DCR history, history-complete convolution, and fail-closed malformed-kernel behavior. The remaining provenance-state defect does not invalidate those numerical repairs, but it blocks scientific attribution of a sampled kernel as measured/calibrated. Downstream waveform timing, baseline, pile-up, PID and DATA/MC claims remain gated.

## Repository actions

- Added stable concern `CCB-1067-PROV-STATE-001` to existing #1067; no duplicate issue opened.
- Opened core draft PR #8 with exact failing discriminator.
- Opened testbeam draft PR #1229 from exact protected main to restore the gitlink from stale core `5c6bb027...` to composed history-complete core `e71fd26...` without claiming #1067 closure.

## Child atoms

- `ARU-ELEC-IMPULSE-PROVENANCE-PROMOTION-001`: typed `CUSTOM_UNVALIDATED -> MEASURED` authorization contract.
- `ARU-ELEC-IMPULSE-DIGEST-001`: exact source/effective-kernel content digest and canonical serialization.
- `ARU-ELEC-IMPULSE-CALIBRATION-CLOSURE-001`: source waveform units/polarity/baseline/time-zero/resampling/normalization validation.
- Historical-output audit for any run previously serialized as `MEASURED` without full provenance.

## Next highest-value action

Repair core PR #8 on the same history-complete lineage so custom sampled kernels remain non-authoritative by default, add incomplete-provenance and fully-authorized transition controls, then require exact-head Core CI. Separately, merge testbeam PR #1229 only after protected exact-head MC Validation passes; #1067 and #1096 remain open/PARTIAL.
