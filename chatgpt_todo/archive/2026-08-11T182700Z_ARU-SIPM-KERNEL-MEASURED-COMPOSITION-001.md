# ARU-SIPM-KERNEL-MEASURED-COMPOSITION-001

Status: PARTIAL at testbeam integration time; composed core implementation is merged and exact-head + merged-main Core CI are green. Parent #1096 remains PARTIAL. #1067 is reopened because exact digest provenance remains unresolved.

## Trigger and provenance

The selected atom for this session was `ARU-SIPM-PREWINDOW-KERNEL-COVERAGE-001`, starting from protected testbeam `main@a83d3b64b87d3781211a2db42d5375bea8d4ae41` with `ccb-sipm-core@f009b0d6d0ccdcd4f54ef9be62b793934a56e518`. While its integration was in progress, testbeam PR #1226 merged as `0800a0cece4dff733c82e024b4c764e85ce947d9` and moved the SiPM gitlink to non-descendant core `5c6bb0278be4246f3da9007b71a5d13024b968ca`. That target did not contain the validated DCR-history repair or the newly validated kernel-history repair. The session therefore spawned this cross-atom composition universe rather than selecting either conflicting branch.

## Local contracts being composed

### History-complete stochastic support

Dark primaries under the repository model use

`N_dark ~ Poisson(R * (window_end_ns-history_start_ns) * 1e-9)`

and conditional times uniform on `[history_start_ns,window_end_ns]`.

### History-complete analog convolution

For admitted avalanche `a` and recorded sample `i`,

`V_i = sum_a A_a h(t_i-t_a)` for `t_i >= t_a`.

For output count

`N_out = floor((window_end-window_start)/dt)+1`

and prehistory span

`H = max(0, window_start-history_start)`,

the conservative uniform-grid elapsed-time support is

`N_kernel = N_out + ceil(H/dt)`.

At defaults `history=-200 ns`, window `[-20,250] ns`, `dt=0.5 ns`, `N_out=541` and `N_kernel=901`; the oldest admitted avalanche is 450 ns old at the final sample.

### Measured-impulse fail-closed semantics

A supplied measured impulse must have matched lengths, at least two finite strictly increasing time points, nonzero peak magnitude, and positive trapezoidal integral. It may not silently collapse to an ideal delta. `IDEAL_DELTA_TEST_ONLY` is separately allowed only when `authorising=true`.

The support-overlap test must use the history-complete elapsed-time grid. A measured response lying after the recorded-window duration can still be relevant to an old admitted avalanche. Exact source/effective-kernel content digests are provenance obligations; placeholders such as `LEN-<size>` are not accepted as SHA-256 evidence.

## Mechanisms and discriminators

H1: recorded output duration is sufficient impulse support. Eliminated by a history-boundary generic CR-RC fixture for which the old output-length kernel is identically zero while the configured response is analytically nonzero.

H2: extend the elapsed-time kernel through all admitted history-to-output lags. Survives and is implemented.

H3: direct evaluation of `h(t_i-t_a)` instead of a precomputed elapsed-time kernel. Mathematically viable and observationally equivalent for the current uniform grid, but not required for the bounded repair.

H4: explicit physical finite-support/tolerance truncation. Viable only if separately declared and validated; the measured finite-support control verifies numerical extension does not invent support.

C1: resolve the concurrent gitlink by retaining core `5c6bb027...`. Rejected because this loses validated history/DCR/kernel descendants.

C2: resolve it by retaining history core only. Rejected because it loses the intended measured-impulse fail-closed semantics.

C3: compose the measured-impulse semantics onto descendant history-complete core and run joint regressions. Survives and is implemented in core PR #7.

C4: call `LEN-<size>` values exact hashes. Rejected; the composed core leaves the hash fields blank rather than making a false provenance claim.

## Executed experiments

Kernel-history PR #5 exact head `454579870a8f1eb9b0f67e02df30486f778f7b67` passed Core CI run `31520345468`, job `93875571412` (checkout/configure/build/test). It squash-merged as `68eadf3f6ac3a95b37e0d8c86843573736a5ea97`; merged-main run `31520555652`, job `93876260437`, independently passed.

The composition branch `fix/compose-history-measured-impulse` started from exact `68eadf3f...`. Its joint C++ regression covers valid measured response, all-zero rejection, negative-integral rejection, explicit ideal-delta authorisation, non-fabrication of digest placeholders, support `[20,25] ns` that lies outside a 10 ns recorded-window duration but inside a 30 ns history-complete kernel, and rejection of support wholly beyond that domain. Existing dark-history and kernel-history tests remain in CTest.

Core PR #7 exact head `0b18bc08c9e077eebe3e20c8bfd5005085de09f3` passed Core CI run `31522503501`, job `93882757978`: checkout/configure/build/test all SUCCESS. It squash-merged with an expected-head guard as core `main@e71fd26c915a402590931d2a7657157f04277235`. Its independent main-push Core CI run `31522658182` also completed SUCCESS.

No local C++ execution is claimed. No beam event, production Geant4/MC event, measured electronics waveform, detector calibration, or detector-performance observable participated.

## Four sequential AI review passes

### A. SiPM/electronics lead
Evidence: exact core source lineage, default time scales, analytic CR-RC contract, measured-impulse support semantics, PR #5/#7 exact CI.

Strongest counter-hypothesis: the recorded waveform duration defines all relevant electronics memory.

Falsifier: a history-boundary avalanche has configured nonzero response at elapsed ages beyond the recorded duration; the old kernel loses it completely in the known-answer fixture.

Residual uncertainty: real CCB impulse response, physical history horizon, electronics bandwidth and calibration.

Vote: ACCEPT bounded history-complete numerical/electronics composition / REVISE physical response and horizon.

### B. Adversarial mechanism reviewer
Evidence: non-descendant git history, finite-support control, measured support beyond recorded duration, placeholder-digest source.

Strongest counter-hypothesis: either side of the concurrent gitlink conflict can be selected independently without scientific loss.

Falsifier: core `5c6bb027...` loses DCR/kernel history repairs; history-only core lacks the fail-closed measured semantics. The only compatible bounded mechanism is a descendant composition with joint tests.

Residual uncertainty: continuous sub-grid avalanche phase remains quantized by `lround`; exact digest implementation is unresolved.

Vote: ACCEPT descendant composition / BLOCK #1065 sub-grid timing and exact-digest claims.

### C. Independent statistics/validation reviewer
Evidence: analytic known answers and deterministic negative controls; exact PR-head and merged-main C++ CI for both kernel and composed core.

Strongest counter-hypothesis: the regressions merely restate the implementation.

Falsifier: expected generic-tail samples are independently derived from the analytical impulse, and the measured-support cross-atom fixture distinguishes output-duration validation from history-domain validation.

Residual uncertainty: no measured waveform distribution or production detector sample participates.

Vote: ACCEPT deterministic software oracle / BLOCK detector-performance inference.

### D. Claims/provenance reviewer
Evidence: #1096, #1067, live gitlink transitions, CI identities, metadata implementation.

Strongest counter-hypothesis: merged #1226 completed #1067 and advanced the detector model monotonically.

Falsifier: its core target is non-descendant of validated history repairs; its fields labelled as hashes are populated with `LEN-*` placeholders; its measured-support validator uses the wrong domain. #1067 was reopened.

Residual uncertainty: exact source/effective-kernel digest provenance, history convergence, calibration and downstream DATA/MC propagation.

Vote: ACCEPT bounded composition repair / BLOCK #1096 COMPLETE, #1067 COMPLETE and public detector-claim promotion.

## Cross-scale propagation

Micro/stochastic: DCR history support is retained in composed core.

Meso/electronics: all admitted avalanche ages are available to the configured impulse, and measured kernels fail closed under bounded semantics.

Event/study/claim: not validated. No waveform population, baseline/timing/pile-up/PID study or DATA/MC comparison was regenerated.

## Surviving children

- `ARU-SIPM-HISTORY-HORIZON-CONVERGENCE-001` — choose sufficient physical prehistory by observable convergence.
- existing #1065 `ARU-SIPM-SUBGRID-001` — continuous avalanche phase versus rounded sample placement; the provisional sampling child from this audit is collapsed into it.
- #1067 exact measured-source/effective-kernel digest provenance and remaining acceptance leaves.
- #1010 measured/generic electronics calibration.
- #1009/#1014 real DAQ sampling/aperture semantics.
- downstream waveform→baseline/timing/pile-up/PID/DATA-MC propagation.

## Testbeam integration

Current protected testbeam main at repair start is `0800a0cece4dff733c82e024b4c764e85ce947d9`, whose gitlink is regressed to core `5c6bb027...`. Branch `fix/sipm-history-composition-integration` starts from that exact main and advances the gitlink to composed core `e71fd26c...`. Protected testbeam CI and final merge status must be recorded in the live handoff before this cross-atom regression is considered repaired on remote main.
