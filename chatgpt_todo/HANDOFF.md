# Latest Handoff

## Kernel support now matches admitted SiPM history; #1096 remains partial

Protected `ccb-testbeam` main at selection was `a83d3b64b87d3781211a2db42d5375bea8d4ae41`, integrating `ccb-sipm-core@f009b0d6d0ccd4f54ef9be62b793934a56e518`. The selected child is `ARU-SIPM-PREWINDOW-KERNEL-COVERAGE-001`.

The prior #1096 repairs made avalanche scheduling and homogeneous dark-count generation start at `history_start_ns`. Source inspection exposed a remaining numerical mismatch: `ResponseSimulator::make_waveform()` still allocated `make_impulse_kernel(n_samples,dt)` where `n_samples` is only the recorded waveform count, and convolved only over those same kernel indices. Thus an avalanche could be admitted into detector history while a later recorded sample could not access the configured response at the required elapsed time.

The bounded contract is `V_i = sum_a A_a h(t_i-t_a)` for causal `t_i>=t_a`, with `N_out=floor((window_end-window_start)/dt)+1`, `H=max(0,window_start-history_start)`, and conservative uniform-grid coverage `N_kernel=N_out+ceil(H/dt)`. The limiting case `history_start==window_start` recovers the legacy kernel length exactly.

At the repository defaults (`history=-200 ns`, window `[-20,250] ns`, `dt=0.5 ns`) the output has 541 samples but full admitted-history-to-output coverage requires 901 elapsed-time kernel samples. An avalanche at `history_start` is 450 ns old at the final sample; the old kernel represented only 0--270 ns.

## Discriminating experiment

A deterministic known-answer C++ fixture uses one history-boundary photon avalanche with `history=-20 ns`, recorded window `[0,10] ns`, `dt=1 ns`, PDE=1, no dark/crosstalk/afterpulse, no gain/SPTR/noise fluctuations, and the generic CR-RC bi-exponential `h_raw(t)=exp(-t/25)-exp(-t/1)`.

The old algorithm has only 11 kernel points (ages 0--10 ns) while recorded samples require ages 20--30 ns, so it produces an all-zero waveform. The repaired 31-point grid closes every output sample against the analytic peak-normalised impulse to `1e-12`; expected first/last samples are approximately 0.5367471648 and 0.3597923859.

Negative controls require `history_start=window_start` to preserve prior convolution semantics and a measured finite-support impulse on `[0,10] ns` to remain exactly zero for an avalanche aged 20--30 ns. These are deterministic simulator-law checks, not measured electronics or detector data.

## Core implementation and execution

Core branch `audit/prewindow-kernel-coverage` was based exactly on `f009b0d6d0ccd4f54ef9be62b793934a56e518`. The bounded source change extends the impulse grid by `ceil((window_start-history_start)/dt)` and changes convolution to cover `h.size()` while leaving output waveform length unchanged. `tests/test_kernel_history.cc` contains analytic and negative-control discriminators and CMake runs it under CTest.

Exact PR head `454579870a8f1eb9b0f67e02df30486f778f7b67` passed Core CI run `31520345468`, job `93875571412`: checkout, Configure, Build, and Test all SUCCESS. Core PR #5 was marked ready and squash-merged with an expected-head guard as `ccb-sipm-core@68eadf3f6ac3a95b37e0d8c86843573736a5ea97`. Exact merged-main push Core CI run `31520555652`, job `93876260437`, independently passed checkout, Configure, Build, and Test.

The immutable execution record is `chatgpt_todo/archive/2026-08-11T180300Z_ARU-SIPM-PREWINDOW-KERNEL-COVERAGE-001_EXECUTION.md`.

## Testbeam integration state

Branch `fix/sipm-kernel-history-integration` was created from exact `main@a83d3b64b87d3781211a2db42d5375bea8d4ae41`. Commit `76e6c2bf02d4000ffeaa9b2c79b0dd362acd66ef` advances only `geant4/single_stave/sipm` to merged core `68eadf3f6ac3a95b37e0d8c86843573736a5ea97`; subsequent commits archive the atom and refresh coordination. Draft testbeam PR #1227 owns the protected integration gate; merge only after all exact-final-head MC Validation contexts pass.

Do not close #1096. The kernel child closes a numerical cross-atom incompatibility but does not establish the physical history horizon or calibrate the electronics response.

## Four sequential review passes

**SiPM/electronics lead — ACCEPT bounded numerical support / REVISE physical response+horizon.** The strongest counter-hypothesis was that recorded waveform length legitimately defines all electronics memory. The nonzero generic CR-RC response at required ages 20--30 ns falsifies that for the encoded model. Real CCB impulse response and sufficient prehistory remain uncalibrated.

**Adversarial mechanism reviewer — ACCEPT elapsed-time coverage / BLOCK sub-grid timing inference.** The strongest concern was that extending an array could create unphysical tails. The finite measured-support control stays exactly zero outside declared support, while the collapsed-history control preserves old semantics. Continuous avalanche phase is still rounded by `lround`; that is existing #1065, not a new child.

**Independent validation reviewer — ACCEPT deterministic software oracle / BLOCK detector inference.** The known answer is independently derived from the analytic CR-RC expression and chosen so old code is identically zero while the reference is nonzero. Exact PR-head and merged-main GitHub Actions both compiled and ran the C++ tests successfully. No production event distribution or measured bench data participates.

**Claims/provenance reviewer — ACCEPT child VALIDATED after testbeam integration / BLOCK #1096 COMPLETE and public detector claims.** History-horizon convergence, #1065 sub-grid timing, measured/generic electronics calibration, real DAQ sampling/aperture semantics and downstream reconstruction propagation remain independent gates.

## Equivalent-child collapse and coordination hazards

The provisional `ARU-SIPM-SAMPLING-APERTURE-001` label created while auditing the kernel is collapsed into existing open #1065 `ARU-SIPM-SUBGRID-001` for the internal pre-convolution timing quantisation. #1065 was updated with a regression requirement that any future fractional-delay/direct-evaluation repair retain the history-coverage invariant. Real DAQ aperture/clock sampling remains separately owned by #1009/#1014.

Open testbeam PR #1226 proposes a gitlink to `ccb-sipm-core@5c6bb0278be4246f3da9007b71a5d13024b968ca`, but that core commit is based on `2027b06e...` rather than current validated core main. It therefore omits dark-history merge `f009b0d...` and kernel-history merge `68eadf3f...`. Blocking comments were posted on #1226 and #1067. An attempted connector action to convert #1226 back to draft was blocked by the safety classifier, so its visible draft state was not changed.

The #1067 rework has an additional cross-atom requirement: measured-impulse support validation must use the actual history-extended elapsed-time kernel domain, not only the recorded waveform duration. Its source/effective-kernel provenance also still requires true content-derived digests; `LEN-<size>` placeholders cannot satisfy a field labelled SHA-256.

## Next atom

After testbeam PR #1227 passes protected CI and is integrated, continue with `ARU-SIPM-HISTORY-HORIZON-CONVERGENCE-001`: extend `history_start_ns` in controlled scans and require stability of in-window observables under further prehistory, with separate nuisance treatment for recovery time, fast/slow afterpulse time constants, delayed crosstalk, DCR, and electronics impulse tails. Existing #1065 should then be tackled before any sub-ns timing inference from this core.

No production Geant4 campaign, beam/production-MC ROOT data, measured SiPM/electronics calibration, detector baseline, timing, pile-up, PID, event-weight, ESS, p-value, rate, efficiency, or detector-performance claim was regenerated or promoted.
