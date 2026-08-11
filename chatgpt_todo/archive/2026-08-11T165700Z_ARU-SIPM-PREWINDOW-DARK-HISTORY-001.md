# ARU-SIPM-PREWINDOW-DARK-HISTORY-001

Status: `PARTIAL / CONFIRMED_CONTROL_FLOW_GAP / CORE_FIX_NOT_YET_COMPILED`

## Selection and provenance

Protected base at selection: `ccb-testbeam main@fcb246a1442d8ab9aa5fee8bce2337f46749dd06`, merge of PR #1223.

Integrated dependency: `geant4/single_stave/sipm -> ccb-sipm-core@2027b06e0fb47b26da1b89e95b6901a5f8e6c200`.

Parent: #1096 `ARU-SIPM-PREWINDOW-TAIL-001`, reopened in this session because its acceptance criteria remain materially incomplete.

No beam data, production MC, detector calibration or hardware measurement entered this atom. All numerical scales below are analytical consequences of the currently declared simulator model.

## Atomic contract

The sampled waveform window and the physical avalanche-history interval are distinct state variables.

For homogeneous dark-count rate `lambda` and explicit history simulation, the dark-primary point process must cover the physical history interval if those avalanches may alter either the in-window analog signal or the microcell/correlated-noise state:

`N_dark ~ Poisson(lambda * (window_end_ns - history_start_ns) * 1e-9)`

with event times uniform on `[history_start_ns, window_end_ns]` conditional on `N_dark`.

The output is the set of dark-primary avalanche candidates and all induced state/descendants available to the same scheduler used by supplied photon candidates.

Units: time ns, dark-count rate Hz, avalanche count dimensionless, waveform signal PE in the core's current signal convention.

## Confirmed current-code split

`ccb-sipm-core@2027b06...` changed `schedule()` to accept candidates from `history_start_ns`, and added `history_start_ns=-200 ns` to config and run metadata.

However `ResponseSimulator::simulate()` still generates dark counts only over the sample interval:

```cpp
const double duration_s =
    (config_.window_end_ns - config_.window_start_ns) * 1.0e-9;
...
std::uniform_real_distribution<double> dark_time(
    config_.window_start_ns, config_.window_end_ns);
```

Therefore supplied photons can populate `[history_start_ns, window_start_ns)`, but dark primaries cannot.

Task-C tests C1-C5 do not cover this mechanism because `UnitConfig()` disables dark counts, prompt/delayed crosstalk and afterpulsing before the pre-window photon fixture is run.

## Mechanism universe

- H1 `SAMPLE_ONLY_DCR`: current implementation. Prehistory exists for supplied/correlated candidates but not for the spontaneous dark process.
- H2 `EXPLICIT_STATIONARY_DARK_HISTORY`: generate dark primaries from `history_start_ns`; preferred minimal repair under the current explicit-history state representation.
- H3 `SUFFICIENT_STATE_INITIALIZATION`: replace explicit remote prehistory with a validated stationary state at the sampling boundary. Survives in principle but is not implemented.
- H4 `PHYSICAL_PREWINDOW_GATE`: hardware suppresses dark activity before the sampled interval. Requires source-bound hardware evidence; the waveform file boundary is not itself such evidence.

H2 and H3 may be observationally equivalent only after a state-distribution closure test. They must not be counted as independent physical hypotheses if such equivalence is demonstrated.

## Equations, invariants and model-internal scale

Current defaults:

- `history_start=-200 ns`
- `window_start=-20 ns`
- `window_end=250 ns`
- `lambda=500000 s^-1`

Missing prehistory width: `H=180 ns`.

`E[N_missing] = lambda H = 0.09`.

`P(N_missing>=1) = 1-exp(-0.09) = 0.08606881472877181`.

Sample-window expectation: `500000 * 270 ns = 0.135`.

History-inclusive expectation: `500000 * 450 ns = 0.225`.

Thus the omitted interval is `0.09/0.225 = 0.40` of the history-inclusive dark-primary measure under the declared homogeneous DCR model.

For the default generic single-stage CR-RC impulse

`h(u) = [exp(-u/25)-exp(-u/1)] / h_peak`, `u>=0`,

`u_peak = ln(25)/(1 - 1/25) = 3.3529956509043757 ns`,

`h_peak = 0.8395058613323211`.

The expected signal at the window boundary from the omitted stationary dark primaries over 180 ns is

`lambda_ns * integral_0^180 h(u) du = 0.014283006503808966 PE`,

with `lambda_ns=0.0005 ns^-1`.

This is a model-internal expectation only. The integrated core labels the device profile manufacturer-representative/not calibrated and the generic electronics response unmeasured, so it cannot be promoted to a measured detector baseline.

## Eliminated and surviving hypotheses

Eliminated as a complete #1096 repair: changing only the scheduler lower bound. It fixes supplied-photon prehistory but leaves the spontaneous dark point process on the sample interval.

Eliminated as evidence of C++ integration: ccb-testbeam's MC Validation workflow does not initialize/build/test the submodule. The upstream PR reports `ccb_sipm_tests` passed; this session did not rerun that executable.

Surviving: H2, or H3 if a stationary sufficient-state initializer is derived and validated. H4 remains an unproven hardware hypothesis.

## Discriminating tests / implementation-ready fix

Minimal H2 repair in `ccb-sipm-core/src/ResponseSimulator.cc`:

- calculate DCR duration from `history_start_ns` to `window_end_ns`;
- sample dark times uniformly over that same interval;
- leave scheduler's history bound fail closed.

Regression requirements:

1. DCR enabled, crosstalk/afterpulse/noise disabled, explicit `[-200,-20,250] ns` bounds: pre-window dark candidates must be possible and all must satisfy `time>=history_start`.
2. Candidate before history remains rejected.
3. `history_start==window_start` exactly reduces to legacy sample-only DCR measure.
4. The expected Poisson mean used by the generator must scale with `window_end-history_start`.
5. A deliberately different hardware-gated model must use a separate explicit mode, not overload the history interval.

A high-rate seeded fixture can make pre-window occurrence practically certain, but a deterministic interval/helper test is preferable to avoid relying on implementation-specific random-distribution streams for the core contract.

## History-horizon child

Spawn `ARU-SIPM-HISTORY-HORIZON-CONVERGENCE-001`.

The comment that `history_start=-200 ns` covers approximately eight 25-ns decay constants is not sufficient. Relative to the actual sample start `-20 ns`, the explicit prehistory is 180 ns = 7.2 decay constants. More importantly, recovery (`30 ns`) and slow afterpulsing (`p=0.005`, `tau=80 ns`) carry memory independently of the direct analog tail. For an 80-ns exponential delay, `P(delay>180 ns)=0.10539922456186433`; multiplied by the configured 0.5% slow-afterpulse branch this is `5.269961228093217e-4` per eligible primary before recovery/other-state effects. A measured impulse or extra shaper stages can also change the analog memory scale.

History length must therefore be selected by a convergence criterion over declared in-window observables/state for every enabled mechanism, not by one decay constant alone.

## Four sequential AI reviews

### 1. SiPM/electronics lead — REVISE

Evidence: exact config defaults, scheduler and DCR-generation code. Strongest counter-hypothesis: waveform start is a physical DCR gate. Attempted falsifier: inspect the model for a gate; none exists, while photon history is now explicitly admitted. Residual uncertainty: actual CCB acquisition/trigger gating. Vote `REVISE` parent closure.

### 2. Adversarial stochastic-process/recovery reviewer — BLOCK

Evidence: Poisson support mismatch, per-cell `last_fire`, afterpulse/crosstalk scheduling. Strongest counter-hypothesis: only the direct analog tail matters. Falsifier: a pre-window avalanche may alter recovery or seed delayed descendants even when its direct waveform tail is negligible. Residual: sufficient history horizon and stationarity. Vote `BLOCK COMPLETE`.

### 3. Independent numerical/statistical validation reviewer — ACCEPT defect / BLOCK validation

Evidence: exact analytical Poisson expectations and code-level interval definitions. Strongest counter-hypothesis: existing Task-C tests cover prehistory generally. Falsifier: the fixture helper disables DCR and only supplies a photon. Residual: no C++ compile/test rerun in this session. Vote `ACCEPT control-flow diagnosis / BLOCK patched-core validation`.

### 4. Claims/provenance reviewer — BLOCK completion

Evidence: #1096 itself requires cross-window recovery/correlated-noise memory and history-length convergence. Strongest counter-hypothesis: merged submodule pointer implies acceptance closure. Falsifier: dependency contents and parent criteria disagree. Residual: downstream integrations/campaign regeneration. Vote `BLOCK #1096 COMPLETE`; no detector claim promotion.

## Cross-scale implications

The defect can affect model baselines, early timing, pile-up/recovery state and false-hit occupancy within the simulator. Magnitude in the real detector is unresolved because DCR/device/electronics state is not calibrated here. Any downstream S10/MV5 timing/pile-up or detector-response claim must remain gated until the corrected history process and horizon compose with the rest of the detector chain.

## Repository actions and handoff

- #1096 reopened and updated with this continuation atom rather than opening a duplicate issue.
- No ccb-sipm-core code commit or C++ test result is claimed in this session.
- This archive is a provenance/coordination artifact only.

Next bounded engineering action: patch the DCR interval in ccb-sipm-core, add deterministic history-support regressions, execute the exact core build/tests, then update the ccb-testbeam gitlink only after the core commit is validated. In parallel, keep `ARU-SIPM-HISTORY-HORIZON-CONVERGENCE-001` open until model-dependent prehistory convergence is demonstrated.