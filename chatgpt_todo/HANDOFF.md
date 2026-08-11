# Latest Handoff

## Runtime impulse identity now binds the exact kernel consumed by waveform synthesis

Selected atom: `ARU-ELEC-IMPULSE-DIGEST-RUNTIME-BINDING-001`, child of P0 #1067. The predecessor canonicalization atom supplied deterministic SHA-256 functions for parsed sample payloads and effective kernels but left a provenance gap: metadata could in principle hash a separately reconstructed kernel rather than the exact numerical object used by convolution.

That gap is now repaired in `ccb-sipm-core` PR #12. Exact core base was `8ecf6037de9f14cc073f5ed99299a8e78a5fadb3`; exact final PR head was `e50ead854430a41c02bf40c1bf1db8955a9fe10a`; exact merged core main is `66cc250f837be5bd30f8bec9bd67b8ec9ca9e7ed`.

### Contract

For validated waveform configuration,

`N_out = floor((window_end_ns-window_start_ns)/sample_dt_ns)+1`

`N_hist = ceil(max(0,window_start_ns-history_start_ns)/sample_dt_ns)`

`N_kernel = N_out + N_hist`.

A waveform-producing `ResponseSimulator` creates one private peak-normalised, history-complete kernel object `K`. Waveform convolution consumes `K` by const reference and `run_metadata()` hashes that same object with `CanonicalEffectiveKernelHash(sample_dt_ns,K)`. Caller-supplied effective-kernel hashes are overwritten. If waveform generation is disabled, no runtime waveform kernel is consumed and the field is empty.

The numerical waveform law remains `V_i=sum_a A_a h(t_i-t_a)` for causal `t_i>=t_a`, with the existing continuous fractional-delay interpolation. This change is object/provenance binding, not a new detector-response model.

Positive global scaling of a sampled source is intentionally collapsed after peak normalisation when it yields the same effective kernel; that source can still have a different source/sample identity. Shape, sampling interval and exact history-complete support length remain effective-identity variables.

### Exact execution

New C++ discriminator `tests/test_impulse_runtime_binding.cc` uses fixed run seed `0x72756e74696d65`; DCR, crosstalk, afterpulsing and electronics noise are disabled, PDE=1, gain=1 pe with zero spread, and SPTR=0. Controls bind known canonical hashes to exact unit-response waveform samples for `{0,1,0}` and history-extended `{0,1,0,0}`, inject a forged caller digest, collapse a positive global amplitude scale, detect a shape mutation, and require empty effective identity in no-waveform mode.

The first exact-head CI run `31530401219` / job `93908776119` exposed two stale predecessor oracles that still required an empty effective-kernel digest. The new runtime-binding test itself passed. Those older tests were repaired to distinguish **numerical runtime identity** from **measured-calibration authority**: an unbound sampled response can and should have an exact effective numerical hash while remaining `CUSTOM_UNVALIDATED` with no source-byte digest.

Final exact-head Core CI `31530628915` / job `93909520107` used Ubuntu 24.04 / GCC 13.3.0 and passed configure, build and all seven CTest targets (`7/7`, `0` failed, 0.25 s). PR #12 was then squash-merged with expected-head guard as `66cc250f...`. A local clone/build attempt was not evidence because the execution container could not resolve `github.com`; no local PASS is claimed.

### Four sequential AI reviews

**Electronics/calibration lead — ACCEPT bounded runtime-object binding / REVISE measured calibration.** Same-object hashing removes metadata/convolution drift, but no real CCB impulse source bytes or calibration observables are bound.

**Adversarial provenance reviewer — ACCEPT fail-closed binding / REJECT caller-hash authority.** A SHA-looking caller string is not content provenance; the hostile control verifies it is overwritten by the exact runtime object's digest.

**Independent validation reviewer — ACCEPT deterministic C++ oracle / BLOCK detector inference.** The final exact-head C++ suite is green after preserving and resolving the initial oracle contradiction. No detector sample or production MC participated.

**Claims/provenance reviewer — ACCEPT bounded provenance advance / BLOCK #1067 completion and measured-electronics/public claims.** An exact hash can identify a synthetic kernel perfectly; it cannot prove the kernel is a measured/calibrated electronics response.

### Testbeam integration and governance

Protected testbeam main at selection was `594bea0807e53d5f3e55a2b2e29bd85f82aa1f3e`; its SiPM gitlink was still `f0258f5020ba9c8b6b44b284bfcafaeb27528a2c`. Fresh branch `audit/impulse-runtime-binding-integration` was created from that exact main and advances only the gitlink to descendant core `66cc250f...` before coordination updates. Protected testbeam CI and final current-main ancestry are still required before integration can merge.

Existing draft #1233 integrates only predecessor canonicalization (`8ecf6037...`) from stale base `cf3106...`; do not merge it over the new descendant path. Close it as superseded once the descendant testbeam PR is established.

P0 #1067 was found auto-closed again after current-main #1087 carried historical squash-message text `fixes #1067`, despite explicit PARTIAL state and unresolved children. This session reopened #1067 and added the recurrence to open governance #1218 as a second live regression witness. Issue closure remains an administrative/platform state, not a sufficient scientific completion predicate.

### Surviving children / blockers

- `ARU-ELEC-IMPULSE-SOURCE-BYTE-BINDING-001`: exact external calibration bytes, byte digest, parser/version/locale grammar, bytes→sample closure and canonical sample identity.
- `ARU-ELEC-IMPULSE-CALIBRATION-CLOSURE-001`: physical units, polarity, baseline, time-zero, normalisation, bandwidth and resampling closure against a real CCB calibration object.
- typed positive `CUSTOM_UNVALIDATED -> MEASURED` promotion only after source, runtime and calibration gates pass.
- `ARU-ELEC-IMPULSE-HISTORICAL-OUTPUT-AUDIT-001` for outputs produced under older unbound provenance semantics.
- `ARU-SIPM-HISTORY-HORIZON-CONVERGENCE-001` under #1096 remains independent: runtime binding is complete only relative to the declared history interval, not proof that the declared history is physically sufficient.

Detailed immutable record: `chatgpt_todo/archive/2026-08-11T200100Z_ARU-ELEC-IMPULSE-DIGEST-RUNTIME-BINDING-001.md`.

### Next highest-value atom

After descendant testbeam integration passes protected CI and lands, take `ARU-ELEC-IMPULSE-SOURCE-BYTE-BINDING-001`. Treat external bytes, parsed numerical samples and effective runtime kernel as three different objects. Bind exact source bytes and parser behavior to the sample digest with malformed/ambiguous-input controls. If an immutable real CCB impulse calibration artifact is unavailable, record that dependency blocker and keep positive `MEASURED` authorization closed rather than substituting a synthetic fixture.

No beam data, production Geant4/MC population, measured CCB impulse, calibrated DCR, DATA/MC comparison, detector timing/baseline/pile-up/PID, rate, efficiency, ESS or p-value was generated or promoted by this atom.
