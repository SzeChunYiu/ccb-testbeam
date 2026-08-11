# Latest Handoff

## DCR explicit-history support is repaired and compiled; #1096 remains partial

Protected `ccb-testbeam` main at this integration step is `0a2e46355c5c5060bbbcad9347b525857fdf40da`, the squash merge of #1224. #1096 is open/reopened. The integrated gitlink on that main still points to pre-repair `ccb-sipm-core@2027b06e0fb47b26da1b89e95b6901a5f8e6c200`.

The selected child is `ARU-SIPM-PREWINDOW-DARK-HISTORY-001`. The old core scheduler accepted candidates from `history_start_ns`, but spontaneous dark counts still used `window_start_ns` as both the Poisson-exposure and uniform-time lower bound. Under the explicit-history model this made dark-primary support inconsistent with photon/correlated-candidate support.

For a homogeneous DCR model with rate `R`, the repaired contract is

`N_dark ~ Poisson(R * (window_end_ns-history_start_ns) * 1e-9)`

with conditional dark times uniform on `[history_start_ns,window_end_ns]`. If `history_start_ns == window_start_ns`, this reduces exactly to the legacy sample-only support.

At the testbeam defaults (`history=-200 ns`, sample window `[-20,250] ns`, DCR `500000 Hz`), the old implementation omitted 180 ns of declared history: model expectation `E[N_missing]=0.09`, `P(N_missing>=1)=0.08606881472877181`, and 40% of the history-inclusive primary measure. These are consequences of the simulator law, not measurements of the detector or a calibrated sensor.

## Core engineering and exact execution

`SzeChunYiu/ccb-sipm-core` PR #4, `fix(sipm): extend dark-count process through explicit history`, was developed from exact parent `2027b06e...`. The production source change is intentionally small: the DCR exposure and uniform-time lower bounds are changed from `window_start_ns` to `history_start_ns`.

A dedicated C++ regression uses fixed run seed `0x5a17d4c3` and 4000 deterministic event IDs in each of two configurations. The history-inclusive fixture covers `[-200,100] ns` at 5 MHz (`mu=1.5` per event); the control has `history_start=window_start=0 ns` and `window_end=100 ns` (`mu=0.5`). Expected aggregate candidate-count ratio is exactly 3. The test requires `2 < ratio < 4`, at least one accepted pre-window dark avalanche, and no dark avalanche outside declared support. Prompt/delayed crosstalk, afterpulsing and waveform generation are disabled; 10,000 cells and negligible recovery time minimize collision/recovery confounding.

A local clone/build attempt could not start because the execution container failed DNS resolution for `github.com`; no local build result is claimed. Instead, the exact repository bytes were compiled and tested through newly added Core CI:

- PR head `22d5122a28cebd94e5981c9b31eeb74689978c41`: Core CI run `31517705149`, job `93866882189`, checkout/configure/build/test all PASS.
- Squash-merged core main `f009b0d6d0ccdcd4f54ef9be62b793934a56e518`: push Core CI run `31517804015`, job `93867201585`, configure/build/test all PASS again.

The second run is the authoritative exact-merged-commit C++ execution. Core PR #4 is merged.

## Testbeam integration

Branch `fix/sipm-dcr-history-integration` was created from exact `main@0a2e463...`. Commit `4186b9a3c569fc33d8b46180de66883b3b4c646f` updates only the `geant4/single_stave/sipm` gitlink to `ccb-sipm-core@f009b0d6d0ccdcd4f54ef9be62b793934a56e518`. The execution record is `chatgpt_todo/archive/2026-08-11T172900Z_ARU-SIPM-PREWINDOW-DARK-HISTORY-001_EXECUTION.md`.

The bounded child may be marked `VALIDATED` as software/stochastic-process semantics. #1096 must **not** be closed: its own acceptance criteria still require cross-window recovery/correlated-noise memory and history-length convergence, and source inspection exposed a separate convolution-support child.

## Four role-separated review state

- **SiPM/electronics lead — ACCEPT bounded DCR-history repair / REVISE #1096.** Strongest counter-hypothesis was a physical DCR gate at the sample boundary; no such gate exists in the encoded model, while other candidates already use explicit prehistory. Real DCR and acquisition timing remain uncalibrated.
- **Adversarial stochastic-process reviewer — ACCEPT explicit-history support / BLOCK sufficiency/full-history claims.** Window-only generation plus reweighting cannot create histories with zero proposal probability or recover their nonlinear cell-state/correlated-noise effects. A separately validated sufficient-state representation remains possible.
- **Independent validation reviewer — ACCEPT software/statistical oracle / BLOCK detector inference.** The law-based 3:1 exposure discriminator and support assertion passed on exact PR and merged-main C++ builds. No beam sample or measured DCR distribution participates.
- **Claims/provenance reviewer — ACCEPT child VALIDATED / BLOCK #1096 COMPLETE and claim promotion.** No downstream waveform/timing/baseline/pile-up/PID/performance study has been regenerated under a converged history model.

## Next atomic universe: convolution support

`ARU-SIPM-PREWINDOW-KERNEL-COVERAGE-001` is now the highest-value child. `make_waveform()` sets `n_samples` from the sample window and passes exactly that length to `make_impulse_kernel(n_samples,dt)`. The convolution then loops only over those kernel samples. At defaults the recorded window spans 270 ns, but an admitted avalanche at `history_start=-200 ns` is 450 ns old at the final `+250 ns` sample. Therefore the current numerical representation can stop propagating an early avalanche around output time `+70 ns` even if the configured analytical/extra-stage/measured impulse remains nonzero at larger relative time.

The child contract should require, for every admitted avalanche `t_a` and recorded sample `t_i`, that whenever `t_i>=t_a` and the declared impulse is nonzero at `tau=t_i-t_a`, the waveform includes `A*h(tau)`. Either the relative kernel must cover at least `window_end_ns-history_start_ns`, or a finite-support/truncation rule must be explicit and validated. This is separate from `ARU-SIPM-HISTORY-HORIZON-CONVERGENCE-001`, which chooses how far back physical history needs to begin.

No production Geant4 campaign, beam/production-MC ROOT data, measured DCR calibration, detector baseline, timing, pile-up, PID, event-weight, ESS, p-value, rate, or detector-performance result was produced or promoted. The Geant4 provenance lane also remains independently open at actual relative-input file-open/content binding, and #1057 remains partial for compiled source-phi and accepted-observable closure.
