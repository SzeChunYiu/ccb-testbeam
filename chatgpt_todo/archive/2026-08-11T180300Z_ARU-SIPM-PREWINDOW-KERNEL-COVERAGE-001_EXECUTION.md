# ARU-SIPM-PREWINDOW-KERNEL-COVERAGE-001 — execution record

Status: VALIDATED at bounded numerical/software semantics after exact-head core CI; testbeam integration pending protected CI/merge at time of this record. Parent #1096 remains PARTIAL.

## Atom and contract

Input state: accepted SiPM avalanches with `time_ns` in `[history_start_ns, window_end_ns]`, amplitude in PE, a declared causal electronics impulse `h(tau)`, sample spacing `dt` in ns, and recorded sample interval `[window_start_ns, window_end_ns]`.

Output: `Waveform.signal_pe[i]` on the recorded grid. Scientific meaning is simulated analog single-photoelectron-equivalent response before electronics noise and ADC quantisation. This is simulator output, not measured detector voltage/current.

For each accepted avalanche `a` and recorded sample `i`,

`V_i = sum_a A_a h(t_i-t_a)` for `t_i >= t_a`, with zero contribution for negative elapsed time.

Therefore every elapsed time `tau=t_i-t_a` reachable from admitted history must be representable whenever the declared impulse is nonzero. Let

`N_out = floor((window_end-window_start)/dt)+1`,
`H = max(0, window_start-history_start)`,
`N_kernel = N_out + ceil(H/dt)`.

`history_start == window_start` is the limiting case and exactly recovers the old kernel length.

## Evidence inspected

Exact core main before repair: `ccb-sipm-core@f009b0d6d0ccdcd4f54ef9be62b793934a56e518`.

`ResponseSimulator::simulate()` already admits candidates from `history_start_ns`; DCR was also repaired to generate through that interval. But `make_waveform()` allocated `make_impulse_kernel(n_samples,dt)` where `n_samples` is only the recorded waveform count, and convolution iterated only `k<n_samples`. Thus an old accepted avalanche could have a nonzero physical/model impulse at a recorded sample while its elapsed-time kernel index did not exist.

Representative config defaults are `history_start=-200 ns`, `window_start=-20 ns`, `window_end=250 ns`, `dt=0.5 ns`, so `N_out=541`, prehistory adds 360 samples, and grid-complete `N_kernel=901`. The earliest accepted avalanche is 450 ns old at the final sample, while the old kernel ended at 270 ns elapsed time.

## Competing mechanisms

H1: recorded waveform length also defines sufficient impulse support. REJECTED by explicit-history counterexample.

H2: extend the elapsed-time kernel through the maximum admitted history-to-sample lag. SURVIVES and is implemented.

H3: evaluate `h(t_i-t_a)` directly for every avalanche/sample pair. SURVIVES mathematically; on the uniform grid it is observationally equivalent to H2 for this model but less bounded as a minimal repair.

H4: impose a physically declared finite impulse support/tolerance shorter than the maximum history lag. SURVIVES only when that support/truncation law is explicit and validated. A finite measured-impulse fixture is used as the negative control; numerical extension must not invent support.

## Deterministic falsifier

Analytical fixture: `history=-20 ns`, sample window `[0,10] ns`, `dt=1 ns`, one accepted photon avalanche at `-20 ns`, generic CR-RC bi-exponential `h_raw(t)=exp(-t/25)-exp(-t/1)`, all stochastic detector/electronics mechanisms disabled and PDE=1.

Old code: 11 kernel points cover elapsed ages 0--10 ns. Recorded samples require ages 20--30 ns, therefore the old convolution yields an all-zero signal waveform despite nonzero `h_raw` throughout those ages.

Corrected grid: 31 kernel points cover elapsed ages 0--30 ns. Peak-normalised analytic expected signal is approximately 0.5367471648 at the first recorded sample and 0.3597923859 at the last. The regression checks every recorded sample against the closed-form impulse to `1e-12`.

Negative controls: (1) set `history_start=window_start`, which must retain exact legacy convolution semantics; (2) measured impulse with declared support `[0,10] ns` and amplitudes `{0,1,0}` must remain exactly zero for samples 20--30 ns after the old avalanche, proving longer numerical allocation does not create physical support.

The C++ test uses fixed `run_seed=0x6b65726e656c`; no stochastic estimator, production event sample, beam data, or Geant4 transport is involved.

## Implementation and execution

Core branch `audit/prewindow-kernel-coverage` was created from exact `f009b0d...`.

Commits before squash merge:
- `000c0b25a0610b6e812e7335173b66fa18df787d`: extend elapsed-time kernel and convolve over its actual size.
- `af93bb9a7fa89e594543de86e76774d1e65e7c6b`: add `tests/test_kernel_history.cc`.
- `454579870a8f1eb9b0f67e02df30486f778f7b67`: wire test into CMake; exact PR head.

Core PR #5 passed Core CI run `31520345468`, job `93875571412`: checkout, Configure, Build, and Test all SUCCESS on exact head `454579870a8f1eb9b0f67e02df30486f778f7b67`. PR #5 then squash-merged with expected-head guard as core main `68eadf3f6ac3a95b37e0d8c86843573736a5ea97`. Post-merge push Core CI run `31520555652` was queued at the first integration checkpoint and must be consumed before treating the merged-main rerun as additional evidence.

A local GitHub clone was not available in the execution container in the preceding SiPM lane because GitHub DNS resolution failed; no local C++ build result is claimed here. The authoritative compile/test evidence for the PR head is GitHub Actions.

Testbeam integration branch `fix/sipm-kernel-history-integration` was created from exact protected `main@a83d3b64b87d3781211a2db42d5375bea8d4ae41`. Commit `76e6c2bf02d4000ffeaa9b2c79b0dd362acd66ef` advances only `geant4/single_stave/sipm` to core `68eadf3f...`; coordination commits follow this record.

## Four sequential AI review passes

### A. SiPM/electronics lead
Evidence inspected: exact core source/config, default time scales, analytical CR-RC law, regression design and exact-head build/test CI.

Strongest counter-hypothesis: the recorded waveform duration legitimately defines all electronics memory.

Attempted falsifier: an admitted avalanche at `-20 ns` with a nonzero configured CR-RC response at elapsed ages 20--30 ns is completely suppressed by the old 11-sample kernel.

Residual uncertainty: the real CCB impulse response and the correct physical history horizon remain uncalibrated.

Vote: ACCEPT bounded numerical support repair / REVISE physical response and horizon.

### B. Adversarial mechanism reviewer
Evidence inspected: old indexing semantics, extended indexing, finite-support measured control and collapsed-history control.

Strongest counter-hypothesis: merely extending the array creates unphysical long tails.

Attempted falsifier: finite measured impulse support remains exactly zero outside its declared source support because interpolation is zero beyond that support.

Residual uncertainty: non-grid-aligned avalanche rounding and digitizer sampling/aperture semantics remain separate atoms.

Vote: ACCEPT elapsed-time coverage / BLOCK sampling-aperture inference.

### C. Independent statistics/validation reviewer
Evidence inspected: closed-form known answer, deterministic negative controls, fixed API seed, exact-head Core CI compile/test execution.

Strongest counter-hypothesis: the test merely restates implementation behavior.

Attempted falsifier: expected samples are derived independently from the analytic CR-RC expression; the fixture is specifically chosen so old code is identically zero while the reference is nonzero, and two limiting controls constrain over-fixing.

Residual uncertainty: no production waveform population, detector noise sample, or bench impulse participates.

Vote: ACCEPT deterministic software oracle / BLOCK detector-performance inference.

### D. Claims/provenance reviewer
Evidence inspected: #1096 scope, current testbeam gitlink, core PR #5, CI identity and surviving detector/electronics children.

Strongest counter-hypothesis: this child repair is sufficient to close #1096.

Attempted falsifier: #1096 still lacks history-horizon convergence, measured/generic electronics calibration, sampling/aperture closure and downstream reconstruction/claim propagation.

Residual uncertainty: cross-scale DATA↔MC consequences remain untested.

Vote: ACCEPT child VALIDATED after integration / BLOCK #1096 COMPLETE and public detector claim promotion.

## Cross-scale propagation and child atoms

Micro/numerical: elapsed-time support is repaired for all admitted avalanches on the uniform sample grid.

Meso/electronics state: older avalanche tails can now reach every recorded sample when the configured impulse says they should. This composes with the prior scheduling and DCR-history repairs.

Event/study: not validated. No detector waveform distribution, baseline, trigger timing, pile-up, PID, rate, efficiency or production simulation is regenerated.

Children retained/spawned: `ARU-SIPM-HISTORY-HORIZON-CONVERGENCE-001`; `ARU-SIPM-SAMPLING-APERTURE-001` for off-grid arrival/rounding versus real digitizer aperture; measured/generic electronics impulse calibration; downstream waveform→timing/baseline/pile-up propagation. Parent #1096 remains PARTIAL.

## Coordination conflict discovered

Testbeam PR #1226 proposes a gitlink to `ccb-sipm-core@5c6bb027...`, whose parent is `2027b06...`; it does not descend from validated dark-history core main `f009b0d...` nor from this kernel-history merge. Its existing gitlink must not be merged as-is because that would regress already validated history support. The measured-impulse work should be rebased/cherry-picked onto the then-current core main and revalidated before a new testbeam gitlink is proposed.

No measured data, production MC, Geant4 detector transport, claim-ledger physics status, or wiki detector-performance statement is promoted by this atom.
