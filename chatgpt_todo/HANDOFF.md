# Latest Handoff

## Pre-window SiPM history: #1096 was closed too early

Protected `main` at selection is `fcb246a1442d8ab9aa5fee8bce2337f46749dd06`, merge of #1223. That merge updates `geant4/single_stave/sipm` from `ccb-sipm-core@b38e3d...` to `ccb-sipm-core@2027b06e0fb47b26da1b89e95b6901a5f8e6c200` and closed #1096.

The new core commit genuinely fixes one bounded mechanism: `schedule()` now accepts avalanche candidates from `history_start_ns` (default `-200 ns`) rather than starting at the sample window (`-20 ns`), so a supplied pre-window photon can produce an in-window analog tail. The core PR reports `ccb_sipm_tests` passed and adds C1-C5 for the photon/history boundary and metadata/env override.

A deeper source inspection shows the spontaneous dark-count process still starts at `window_start_ns`. `ResponseSimulator::simulate()` computes the Poisson duration from `window_end_ns-window_start_ns` and samples `dark_time` only on `[window_start_ns,window_end_ns]`. Thus the model has two incompatible history supports: supplied photons/correlated descendants may begin at `history_start_ns`, while dark primaries cannot exist before the sample boundary.

This is tracked as continuation atom `ARU-SIPM-PREWINDOW-DARK-HISTORY-001` under the same parent rather than as a duplicate issue. #1096 has been reopened. Archive: `chatgpt_todo/archive/2026-08-11T165700Z_ARU-SIPM-PREWINDOW-DARK-HISTORY-001.md`.

## Exact model scale

For current defaults `history_start=-200 ns`, `window_start=-20 ns`, `window_end=250 ns`, DCR `500000 Hz`, the omitted explicit-history interval is 180 ns. Under the simulator's own homogeneous Poisson model:

- missing expected dark primaries: `0.09` per sensor/event;
- probability of at least one missing pre-window dark primary: `0.08606881472877181`;
- sample-only expected count: `0.135`;
- history-inclusive expected count: `0.225`;
- omitted fraction of the history-inclusive primary measure: `40%`.

These are exact consequences of the declared simulator law, not measurements of the CCB detector. The integrated device profile is manufacturer-representative/not calibrated and the generic electronics response is unmeasured.

For the default peak-normalized CR-RC kernel (`tau_rise=1 ns`, `tau_decay=25 ns`), the expected model-internal signal at the sample boundary from omitted stationary dark primaries over the 180 ns prehistory is about `0.014283 PE`. That number must not be used as a detector baseline prediction.

## Why existing tests do not close the child

The Task-C fixture starts from `UnitConfig()`, which disables dark counts, prompt/delayed crosstalk, afterpulsing and electronics noise. C1/C2 therefore validate a supplied photon at `-21 ns`; they do not test the DCR support.

The ccb-testbeam protected MC Validation workflow triggers on `geant4/**`, but its checkout does not initialize submodules and the job runs Python ruff/pytest only. The successful #1223 run is repository integration/static evidence, not an independent compile/test of `ccb-sipm-core@2027b06...`.

## Four sequential AI reviews

- **SiPM/electronics lead — REVISE parent closure.** The waveform boundary is not represented as a physical DCR gate; admitting photon history while excluding spontaneous dark history is internally inconsistent under the explicit-history interpretation.
- **Adversarial stochastic-process/recovery reviewer — BLOCK COMPLETE.** Pre-window avalanches can change per-cell `last_fire` and seed delayed descendants, so direct analog-tail truncation is not the only memory mechanism.
- **Independent validation reviewer — ACCEPT code diagnosis / BLOCK patched-core validation.** The Poisson calculations and interval mismatch are exact, but no C++ build/test was rerun in this session.
- **Claims/provenance reviewer — BLOCK #1096 completion.** #1096 itself requires recovery/correlated-noise memory and history-length convergence. No baseline, timing, pile-up, rate or detector-performance claim advances.

## Implementation-ready repair

In `ccb-sipm-core/src/ResponseSimulator.cc`, if explicit stationary history remains the model, change the DCR Poisson duration and uniform dark-time support to `[history_start_ns,window_end_ns]`. Add a deterministic interval/helper regression where possible, plus a high-rate stochastic sanity control. Require `history_start==window_start` to reduce exactly to the legacy sample-only model and keep candidates before history rejected.

Do not merge an updated ccb-testbeam gitlink until the exact core commit compiles and its core tests run. There is no new core code/test PASS claimed here.

## Child atom: history-horizon convergence

Spawn `ARU-SIPM-HISTORY-HORIZON-CONVERGENCE-001`. The explicit prehistory from `-200` to the sample start `-20 ns` is 180 ns = 7.2 default decay constants, not eight relative to the actual sample boundary. More importantly, recovery is 30 ns and the configured slow-afterpulse branch has `tau=80 ns`; exponential delayed-state laws have no finite exact memory cutoff. Measured impulse responses or extra shaper stages can also lengthen the analog memory.

The correct horizon is therefore the smallest tested history length for which declared in-window observables/state converge under every enabled mechanism to a preregistered tolerance. Scan analog-only, recovery, prompt/delayed crosstalk, fast/slow afterpulse and measured/generic impulse variants separately before composing them.

## Immediate next action

First patch and execute the DCR-history support regression in `ccb-sipm-core`. If that passes, open/merge a focused core PR and then update the testbeam gitlink through normal protected CI. Afterward run the history-length convergence child rather than re-closing #1096 from a single near-boundary fixture.

The Geant4 provenance lane from merged #1222 remains separately unfinished at actual relative-input file-open/content binding. #1057 remains open/PARTIAL for compiled source-phi and accepted-observable closure. No production Geant4, beam/production-MC ROOT, event-weight, detector-response, ESS, p-value or performance result was generated in this session.
