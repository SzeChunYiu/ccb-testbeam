# ARU-SIPM-PREWINDOW-DARK-HISTORY-001 — execution/repair continuation

Status: `VALIDATED` for the bounded simulator-law repair in `ccb-sipm-core`; parent #1096 remains `PARTIAL` because history-horizon, kernel-coverage, correlated-noise/recovery, and detector-level closure remain unresolved.

## Exact repository state

- ccb-testbeam protected main at integration selection: `0a2e46355c5c5060bbbcad9347b525857fdf40da` (merged #1224).
- integrated pre-repair gitlink: `ccb-sipm-core@2027b06e0fb47b26da1b89e95b6901a5f8e6c200`.
- repaired core main: `ccb-sipm-core@f009b0d6d0ccdcd4f54ef9be62b793934a56e518`, squash merge of core PR #4.
- ccb-testbeam integration branch: `fix/sipm-dcr-history-integration`.
- first integration commit: `4186b9a3c569fc33d8b46180de66883b3b4c646f`.

## Atomic input/output contract

Inputs/state:

- `history_start_ns <= window_start_ns < window_end_ns`, times in ns;
- homogeneous model dark-count rate `R = dark_count_rate_hz`, units s^-1;
- deterministic event RNG seed derived from `(run_seed,event_id,sensor_id,stream=0)`;
- explicit-history state representation, not an implicit sufficient-state boundary condition.

Required dark-primary law:

`N_dark ~ Poisson(mu)`, with

`mu = R * (window_end_ns - history_start_ns) * 1e-9`,

and, conditional on `N_dark`, each primary time

`t_dark ~ Uniform(history_start_ns, window_end_ns)`.

Outputs:

- `n_dark_candidates` counts the generated primary candidates on the declared history support;
- accepted dark avalanches may occur before `window_start_ns` and can alter microcell state or produce causal in-window consequences;
- waveform sample times remain restricted to `[window_start_ns,window_end_ns]`.

Scientific meaning: this closes an internal stochastic-process/support inconsistency. It does not measure the real sensor DCR and does not prove that `history_start_ns=-200 ns` is physically sufficient.

## Competing mechanisms/descriptions

1. **Explicit stationary prehistory**: generate DCR on the full declared history interval. Survives and is implemented.
2. **Physical dark-process gate at sample start**: would justify window-only DCR only if a source-bound device/electronics mechanism suppresses spontaneous avalanches before acquisition. No such mechanism is encoded or evidenced here; eliminated as an explanation of the current software semantics.
3. **Sufficient-state initialization at `window_start_ns`**: may be observationally equivalent to explicit prehistory if it reproduces the joint distribution of cell recovery, correlated-noise ancestry, and analog state. Survives as a future alternative, not implemented.
4. **Window-only generation plus weighting**: rejected because absent pre-window dark histories have zero proposal probability and influence nonlinear recovery/correlated-noise state; event weights cannot reconstruct missing histories.

Equivalent descriptions were collapsed by observable state: any alternative is acceptable only if it reproduces the in-window joint state/observable law, not merely the mean number of dark pulses.

## Invariants, limiting cases, dimensional checks

- `R [s^-1] * Delta t [ns] * 1e-9 [s/ns]` is dimensionless Poisson mean.
- If `history_start_ns == window_start_ns`, the repaired law reduces exactly to the old sample-only interval.
- If `R == 0` or DCR is disabled, no dark candidates are generated.
- Every generated dark time must satisfy `history_start_ns <= t <= window_end_ns`.
- For default testbeam model values (`history=-200 ns`, `window_start=-20 ns`, `window_end=250 ns`, `R=500 kHz`), the formerly omitted duration is 180 ns, `E[N_missing]=0.09`, `P(N_missing>=1)=1-exp(-0.09)=0.08606881472877181`, and the omitted primary-measure fraction is `180/450 = 0.4`. These are model-law quantities, not detector measurements.

## Repair

Core PR #4 changes exactly two stochastic-support expressions in `src/ResponseSimulator.cc`:

- DCR exposure lower bound: `window_start_ns -> history_start_ns`;
- DCR uniform-time lower bound: `window_start_ns -> history_start_ns`.

A dedicated C++ regression `tests/test_dark_history.cc` was added, wired into CMake, and the previously workflow-less core repository gained minimal CMake/build/ctest GitHub Actions coverage.

## Discriminating experiment

Fixed run seed: `0x5a17d4c3`.

Paired deterministic event IDs: 4000 per configuration, 8000 simulator calls total.

History-inclusive fixture:

- `history_start=-200 ns`, `window_start=0 ns`, `window_end=100 ns`;
- `R=5 MHz`;
- theoretical `mu_history = 1.5` candidates/event.

Window-only control:

- identical except `history_start=window_start=0 ns`;
- theoretical `mu_window = 0.5` candidates/event.

The expected aggregate candidate-count ratio is exactly 3. The regression accepts the intentionally broad deterministic band `2 < N_history/N_window < 4`, requires at least one accepted pre-window dark avalanche, and rejects any dark avalanche outside declared support. Prompt/delayed crosstalk and afterpulsing are disabled; waveform generation is disabled; 10,000 cells and `recovery_time_ns=1e-6` minimize cell-collision/recovery confounding. This is a stochastic-process software falsifier, not detector validation.

## Executed evidence

A direct local clone/build attempt failed before source acquisition because the execution container could not resolve `github.com`; no local compile result is claimed.

The exact PR head `22d5122a28cebd94e5981c9b31eeb74689978c41` was compiled and tested by GitHub Actions Core CI run `31517705149`, job `93866882189`: checkout, configure, build, and test all completed successfully.

After squash merge, the exact core main commit `f009b0d6d0ccdcd4f54ef9be62b793934a56e518` was independently rebuilt/retested by push Core CI run `31517804015`, job `93867201585`: configure PASS, build PASS, test PASS.

No failure was suppressed or bypassed. The main-push rerun is the authoritative exact-merged-commit C++ validation.

## Four role-separated sequential reviews

### (a) SiPM/electronics lead

Evidence inspected: old/new DCR generation bounds, scheduler history bound, ModelConfig defaults/provenance, C++ regression, both exact-head CI executions.

Strongest counter-hypothesis: a real acquisition gate makes spontaneous avalanches before `window_start_ns` physically irrelevant.

Attempted falsifier: searched the current model contract for a distinct hardware dark-process gate; none exists, while supplied photons and correlated descendants are explicitly accepted from `history_start_ns`.

Residual uncertainty: real device DCR, acquisition timing, and physical history horizon are uncalibrated.

Vote: **ACCEPT bounded repair / REVISE parent #1096**.

### (b) Adversarial mechanism reviewer

Evidence inspected: support equations, zero-support weighting failure, nonlinear recovery/correlated-noise dependencies, kernel-length child.

Strongest counter-hypothesis: sample-only DCR can be corrected afterward by a rate weight.

Attempted falsifier: missing pre-window histories alter state and ancestry, so a scalar weight cannot create histories with proposal probability zero.

Residual uncertainty: an explicitly validated sufficient-state representation could replace explicit history.

Vote: **ACCEPT explicit-history support / BLOCK sufficiency and full-history claims**.

### (c) Independent statistics/validation reviewer

Evidence inspected: fixed seed, 4000 paired event IDs per configuration, theoretical 3:1 exposure ratio, support assertions, PR-head and merged-main CI.

Strongest counter-hypothesis: a passing stochastic test is an accidental seed-specific fluctuation.

Attempted falsifier: use a very wide law-based ratio band whose old implementation has expectation ratio 1 and repaired implementation expectation ratio 3, plus an independent support assertion. The distinction is many standard deviations at the selected event count.

Residual uncertainty: this validates software semantics only; no measured DCR distribution or production-MC chain participates.

Vote: **ACCEPT software/statistical oracle / BLOCK detector inference**.

### (d) Claims/provenance reviewer

Evidence inspected: reopened #1096 acceptance criteria, merged #1224 handoff, core PR #4, exact core main CI, integration gitlink commit.

Strongest counter-hypothesis: because the DCR-history child is fixed, #1096 can return to COMPLETE.

Attempted falsifier: #1096 still requires recovery/correlated-noise memory and history-length convergence; kernel coverage is independently unresolved.

Residual uncertainty: downstream waveform/timing/pile-up studies have not been rerun with a converged history model.

Vote: **ACCEPT child VALIDATED / BLOCK #1096 COMPLETE and all detector-claim promotion**.

## Cross-scale propagation

Micro: spontaneous dark-primary support now matches declared explicit history.

Meso: pre-window dark primaries can now participate in microcell recovery and correlated-noise scheduling, subject to the still-open history horizon.

Waveform: influence remains limited by the separate convolution-kernel coverage child; therefore the repaired primary process does not by itself guarantee full analog-history propagation.

Study/claim: no production waveform, timing, baseline, pile-up, PID, or performance study was regenerated. No claim-ledger row may be promoted from this repair alone.

## Child atoms spawned/carried

- `ARU-SIPM-HISTORY-HORIZON-CONVERGENCE-001` — choose/validate history horizon by observable convergence across analog/recovery/afterpulse mechanisms.
- `ARU-SIPM-PREWINDOW-KERNEL-COVERAGE-001` — ensure every admitted avalanche is convolved through every recorded sample for which the configured impulse remains nonzero, or validate an explicit truncation rule.
- `ARU-SIPM-SUFFICIENT-STATE-001` — only if replacing explicit prehistory with boundary-state initialization.

## Handoff

Integrate `ccb-sipm-core@f009b0d6d0ccdcd4f54ef9be62b793934a56e518` into ccb-testbeam through normal PR/CI. Do not close #1096. Next highest-value scientific atom is `ARU-SIPM-PREWINDOW-KERNEL-COVERAGE-001`, because the scheduler/DCR support can now admit a `history_start` avalanche while the current kernel is still only as long as the recorded sample window.
