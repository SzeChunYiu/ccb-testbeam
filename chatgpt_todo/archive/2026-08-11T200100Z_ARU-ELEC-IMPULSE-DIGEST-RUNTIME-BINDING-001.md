# ARU-ELEC-IMPULSE-DIGEST-RUNTIME-BINDING-001

Status: `VALIDATED` at bounded software/provenance-object level after exact Core CI and core merge; testbeam integration remains branch/CI-gated until the corresponding testbeam PR lands.

Parent: #1067 (`ARU-ELEC-IMPULSE-FAILCLOSED-001`), which remains OPEN/PARTIAL.

## Selection and global placement

The predecessor `ARU-ELEC-IMPULSE-DIGEST-CANONICALIZATION-001` created canonical SHA-256 identities for parsed numerical impulse samples and effective numerical kernels, but explicitly did not bind the effective digest to the exact kernel object consumed by waveform synthesis. This atom closes only that object-identity gap. It does not establish exact external source bytes, calibration authority, physical history-horizon sufficiency, or detector performance.

Protected testbeam main at selection: `594bea0807e53d5f3e55a2b2e29bd85f82aa1f3e`, whose live SiPM gitlink was `ccb-sipm-core@f0258f5020ba9c8b6b44b284bfcafaeb27528a2c`. Current core main at selection was `8ecf6037de9f14cc073f5ed99299a8e78a5fadb3` after canonical digest PR #11.

## Exact input/output contract

Inputs are validated `ModelConfig` fields: `window_start_ns`, `window_end_ns`, `history_start_ns`, `sample_dt_ns`, the sampled impulse or generic shaping parameters, and the `generate_waveform` switch. Time units are ns. The measurand is the exact peak-normalised numerical impulse kernel available to waveform convolution for a particular simulator instance.

Define

`N_out = floor((window_end_ns - window_start_ns) / sample_dt_ns) + 1`

`N_hist = ceil(max(0, window_start_ns - history_start_ns) / sample_dt_ns)`

`N_kernel = N_out + N_hist`.

For waveform-producing instances the simulator constructs exactly one private `waveform_kernel_ = K` with `|K| = N_kernel`. `make_waveform()` consumes `K` by const reference, and `run_metadata()` serializes

`H_kernel = CanonicalEffectiveKernelHash(sample_dt_ns, K)`.

A caller-provided `electronics.effective_kernel_hash` is not evidence and is overwritten. When `generate_waveform=false`, no waveform kernel is consumed and the serialized effective-kernel hash is empty.

The waveform law remains

`V_i = sum_a A_a h(t_i - t_a)` for `t_i >= t_a`,

with the existing continuous fractional-delay linear interpolation on `K`.

## Competing mechanisms and equivalence collapse

H1 — independently reconstruct a mathematically equivalent kernel for metadata. Rejected as a provenance contract: two separate code paths may later drift while each remains locally plausible.

H2 — trust a caller-populated SHA-looking effective hash. Rejected because it need not bind the runtime numerical object.

H3 — cache one history-complete kernel object and use that object for both waveform convolution and hashing. Survives and is implemented.

H4 — hash a kernel even when waveform generation is disabled. Rejected for this atom because no runtime waveform kernel is consumed in that state.

A positive global scale of sampled source amplitudes is intentionally collapsed at this layer when peak normalisation maps the source to the same effective `K`. Such sources can have different source/sample identities but the same effective-kernel identity. Shape changes, sample spacing and exact history-complete length remain identity-bearing.

## Equations, invariants, limiting cases, identifiability

- `metadata.effective_kernel_hash == CanonicalEffectiveKernelHash(dt, K_consumed)` when waveform generation is active.
- `K_consumed` is the same private object referenced by the convolution loop; no independent metadata reconstruction exists.
- `generate_waveform=false => effective_kernel_hash==""`.
- `history_start_ns == window_start_ns => N_hist=0`, recovering the output-window-only limiting length.
- Extending declared history by one sample changes `N_kernel` and therefore the canonical effective identity even if the extra tail sample is zero; support length is part of the numerical contract.
- The effective digest identifies numerical behavior after resampling/normalisation, not external file bytes or calibration provenance.

## Executed discriminators

Branch: `audit/impulse-digest-runtime-binding`, exact base `ccb-sipm-core@8ecf6037de9f14cc073f5ed99299a8e78a5fadb3`.

Final source head: `e50ead854430a41c02bf40c1bf1db8955a9fe10a`.

New deterministic/seeded C++ test: `tests/test_impulse_runtime_binding.cc` with fixed run seed `0x72756e74696d65`. Detector stochastic nuisances are disabled: DCR, prompt/delayed crosstalk, afterpulsing and electronics noise off; PDE=1; gain=1 pe with zero spread; SPTR=0.

Controls:

1. Collapsed history with source/effective kernel `{0,1,0}` at 1 ns: exact known effective digest `sha256:aa049b621977903cb9c4cb0423dd1bf6844f59a667c593a906b725531b79e29a`; unit avalanche waveform closes exactly to `{0,1,0}`.
2. One-sample prehistory: exact history-complete kernel `{0,1,0,0}` and digest `sha256:d943f8002a50b1f2c83de80aa50495e7511e541563033d2801e6351edb5c08f6`; a history-boundary avalanche consumes ages 1,2,3 as output `{1,0,0}`.
3. A forged caller effective hash is overwritten by the computed runtime identity.
4. Source amplitudes `{0,2,0,0}` collapse after peak normalisation to the same effective hash.
5. Shape mutation `{0,1,0.25,0}` changes the effective hash.
6. `generate_waveform=false` clears the hash and produces no waveform.

Initial exact-head Core CI run `31530401219`, job `93908776119`, configured and built successfully. The new runtime-binding test passed, while two older tests failed because they still asserted that `effective_kernel_hash` must remain empty. This was a semantic-oracle conflict, not a runtime-binding implementation failure: those old assertions encoded the predecessor state in which no exact runtime digest was computed.

The repair did not weaken the new control. `test_measured_impulse_failclosed.cc` now requires a canonical `sha256:` effective identity while preserving empty source hash and `CUSTOM_UNVALIDATED`; `test_impulse_provenance_state.cc` now explicitly distinguishes numerical runtime identity from calibration authority and verifies that a forged caller effective hash is overwritten.

Final exact-head Core CI run `31530628915`, job `93909520107`, on the PR merge ref used Ubuntu 24.04 / GCC 13.3.0; configure and build succeeded; CTest reported `7/7` passed, `0` failed, total test time 0.25 s. No random detector population, beam data, measured calibration, production MC, event weights, detector efficiency or performance observable participated.

Core PR #12 was marked ready only after that exact-head pass and squash-merged with expected-head guard. Exact merged core main: `66cc250f837be5bd30f8bec9bd67b8ec9ca9e7ed`.

A local clone/build was attempted before GitHub CI but the execution container could not resolve `github.com`; therefore no local-build PASS is claimed.

## Four sequential AI review passes

### A. Electronics/calibration lead
Background: SiPM single-photoelectron response, front-end shaping, waveform calibration and detector electronics.

Evidence inspected: canonical digest primitive from core #11, history-complete kernel support, exact pre/post object lifetime paths, source and waveform tests, final CI.

Strongest counter-hypothesis: an independently reconstructed mathematically equivalent kernel is sufficient provenance.

Attempted falsifier: require the provenance identity to be generated from the exact object consumed by convolution; eliminate the second reconstruction path and close unit-avalanche waveforms against known kernel samples.

Residual uncertainty: no exact calibration source bytes or real CCB electronics calibration observables are bound.

Vote: **ACCEPT bounded runtime-object binding / REVISE measured-calibration authority**.

### B. Adversarial mechanism/provenance reviewer
Background: software state machines, content-addressed provenance, hostile fault injection.

Evidence inspected: caller-populated provenance fields, existing hash canonicalization, new cached object, hostile forged digest.

Strongest counter-hypothesis: a trusted caller string in a field named `effective_kernel_hash` is sufficient.

Attempted falsifier: inject `sha256:caller-supplied-placeholder` / forged digest and require serialized metadata to replace it with the canonical hash of the runtime object.

Residual uncertainty: exact source-byte-to-parser binding remains absent.

Vote: **ACCEPT fail-closed runtime binding / REJECT caller-hash authority**.

### C. Independent statistics/validation reviewer
Background: reproducible numerical validation, deterministic oracles, negative controls.

Evidence inspected: known-answer SHA-256 identities from predecessor #11, exact waveform controls, history extension, scale-equivalence and shape-tamper controls, failed-first/successful-final CI sequence.

Strongest counter-hypothesis: a metadata hash test could pass while waveform synthesis consumes a different kernel.

Attempted falsifier: implementation stores one private cached `waveform_kernel_`; both metadata hashing and convolution take that exact member object by const reference. Unit-response waveform expectations independently constrain the consumed samples. The first CI contradiction was preserved and repaired at stale legacy oracles rather than hiding it.

Residual uncertainty: software CI is not physical detector validation.

Vote: **ACCEPT deterministic software oracle / BLOCK detector inference**.

### D. Claims/provenance reviewer
Background: claim-evidence mapping, calibration provenance and publication gating.

Evidence inspected: #1067 acceptance criteria, `CUSTOM_UNVALIDATED` serialization, open child atoms, core merge message and exact CI.

Strongest counter-hypothesis: an exact effective-runtime hash is enough to promote the electronics response to `MEASURED`.

Attempted falsifier: a synthetic numerical vector has a perfectly exact effective hash but no measured source/calibration identity. The same numerical payload can be synthetic or bench-derived.

Residual uncertainty: source bytes, physical calibration, positive authorization and historical-output audit remain unresolved.

Vote: **ACCEPT bounded provenance advance / BLOCK #1067 COMPLETE and all measured-electronics/public detector claims**.

## Cross-scale propagation

Micro/numerical: the exact effective kernel object is now content-addressed by canonical identity.

Meso/waveform: the same object is used for continuous-delay convolution, preventing metadata/convolution drift within one simulator instance.

Event/study: no production event set was regenerated; no weighting/statistical-unit issue arises here.

Claim: no detector or measured-electronics claim is promoted. Exact object identity is a necessary provenance gate, not calibration evidence.

## Child atoms spawned/carried

- `ARU-ELEC-IMPULSE-SOURCE-BYTE-BINDING-001`: exact external calibration bytes -> parser input -> canonical sampled numerical payload.
- `ARU-ELEC-IMPULSE-CALIBRATION-CLOSURE-001`: units, polarity, baseline, time zero, normalization, bandwidth and resampling closure against a real calibration object.
- typed positive `CUSTOM_UNVALIDATED -> MEASURED` authorization only after source/runtime/calibration gates pass.
- `ARU-ELEC-IMPULSE-HISTORICAL-OUTPUT-AUDIT-001`: identify outputs previously serialized with unbound measured/effective provenance.
- `ARU-SIPM-HISTORY-HORIZON-CONVERGENCE-001` under #1096 remains distinct: this atom is complete only with respect to the declared history interval, not its physical sufficiency.
- Governance #1218 remains open after #1067 was again auto-closed by carried close-keyword text in #1087; #1067 was reopened during this session.

## Integration state at archive creation

Fresh testbeam branch `audit/impulse-runtime-binding-integration` was created from exact protected `main@594bea0807e53d5f3e55a2b2e29bd85f82aa1f3e` and its SiPM gitlink advanced from `f0258f5020ba9c8b6b44b284bfcafaeb27528a2c` to exact merged core `66cc250f837be5bd30f8bec9bd67b8ec9ca9e7ed`. Testbeam protected CI and current-main ancestry remain the integration gate; this archive does not claim the branch is already on remote main.

## Next highest-value atom

After the testbeam integration lands, select `ARU-ELEC-IMPULSE-SOURCE-BYTE-BINDING-001`: define exact external byte object/hash, parser version and locale/number grammar, byte->numerical sample closure, malformed/ambiguous input controls, and bind the parsed sample hash to exactly those bytes. If no real CCB calibration artifact is available, document that dependency and do not promote `MEASURED`; the later calibration-closure atom remains separately blocked on physical calibration evidence.
