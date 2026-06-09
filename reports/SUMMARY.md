# Rolling summary / scoreboard

Maintained by the orchestrator/Integrator. One row per study as results land.

| Study | Status | Reproduced? | Traditional | ML | ML beats baseline? | Report/PR |
|---|---|---|---|---|---|---|
| S00 | ✅ done | ✅ 640,737 exact | per-stave counts | run-split sanity | — (foundation) | reports/S00_… (PR #1) |
| S00a | ✅ done | ✅ corrected sorted gate delta = 0 | raw HRDv gate: 1.000 held-out accuracy | sorted-waveform classifier: 0.99984 | No; deterministic gate wins | reports/1780997954.15097.28a25ecb__s00a_sorted_hrdmax_semantics |
| S00b | ✅ done | ✅ median 640,737 and dynamic 706,373 exact | selector shift changes downstream fraction by 0.0152; sigma68 by 0.0067 ns | shape-only selector classifier AUC 0.994, leakage-stress failed | No adoption; treat as selector/baseline systematic | reports/1781000826.539603.1a5d04dd |
| S01 | ✅ report landed | ✅ 640,737 selected pulses | median amplitude-bin template MSE 0.0444 | AE/PCA basis MSE 0.00208 | **Yes** (Δ=-0.0423, CI [-0.0524,-0.0324]) | reports/1780997954.15037.36463764__s01_full_dataset_templates |
| S01b | ✅ merged | ✅ raw-ROOT re-deriv | selection rule | run-split check | — | reports/…s01b… (PR #2) |
| S02 | ✅ done | ✅ S00 selection | template phase sigma68 2.889 ns | ridge-on-CFD20 sigma68 1.846 ns | **Yes** (Δ≈1.04 ns) | reports/1780997954.15157.07ef03cf__s02_timing_pickoff |
| S02b | ✅ done | ✅ exact S02 reproduction | global template + train-only timewalk 1.635 ns | ridge-on-CFD20 1.846 ns | No; strong traditional closure wins on run 65 | reports/1781000705.514762.105c186b__s02b_template_timewalk_closure |
| S03a | ✅ done | ✅ exact S02 reproduction | analytic amp-only timewalk 1.495 ns | ridge residual corrector 1.392 ns | Marginal; CIs overlap, needs leave-one-run-out stability | reports/1781000705.514827.50025402__s03a_analytic_timewalk_correction |
| S07 | ✅ done | ✅ S00 selection | low-current AUC 0.504 | calibrated RF AUC 0.768 | **Yes** (Δ=0.264, CI [0.250,0.280]) | reports/1780997954.15217.702122ea__s07_ml_rigour_scoreboard |
| S07b | ✅ done | ✅ guarded gross D_t count match | D_t/curvature AUC 1.000 | shape-only RF AUC 0.9987 | No; D_t is label-defining | reports/1781000790.531071.5a66741c__s07b_timing_control_classifier |
| S07c | ✅ done | ✅ S00 counts; App.A count mismatch | q_template-only AUC 0.717; span+q AUC 0.912 | clean-timing RF AUC 0.993 | **Yes** vs q_template-only, but weak-label drift remains | reports/1781000790.531136.203130b0__s07c_clean_timing_rf |
| S10 | ✅ done | ✅ Rmax/current excess reproduced | downstream high-low excess 0.0103/event | injection score Δ=0.036 diagnostic | No; ML is monitoring only | reports/1780997954.15277.548b01a3__s10_pileup_rate_model |
| S10b | ✅ done | ✅ Rmax=4.222 MHz assumption and 6/6 topology checks | template tail live10 124.79 ns, CI [123.33,126.36] | ridge live10 123.19 ns, CI [120.72,125.55] | No adoption claim; 90 ns is an assumption, measured window implies Rmax≈3.05 MHz | reports/1781000867.546870.5c124aaf |
| S16 | ✅ done | ✅ S00 selection | pretrigger median MAE 341 ADC | adaptive/learned MAE 48.9 ADC | **Yes**, but adaptive remains biased | reports/1780997954.15337.77205a71__s16_pedestal_baseline_validation |
| S16b closure | ✅ done | ✅ 640,737 exact | line3 early-sample predictor MAE 169.34 ADC | ridge closure MAE 173.71 ADC | No; traditional remains preferred, ML is contamination diagnostic | reports/1781000826.539659.030b7796__s16b_independent_pedestal_estimator_closure |
| S16b forced/proxy | ✅ done | ✅ 640,737 exact; 0 forced/random-tagged entries | adaptive proxy MAE 17.18 ADC | HGBR proxy MAE 15.64 ADC | Proxy only; true forced/random pedestal data absent | reports/1781001221.625922.5a564a7e__s16b_forced_trigger_pedestal_validation |
| S16c | ✅ done | ✅ S00/Sample-II counts and zero post-correction violations | lowering-nuisance ridge sigma68 3.251 ns | RF residual correction sigma68 2.921 ns | Weak/diagnostic; high-lowering events do not carry the timing tails | reports/1781001221.625989.53423f03__s16c_pedestal_timing_nuisance |
| S18 | ✅ done | ✅ Sample III/IV A-stack | A1-A3 robust width 1.389 ns | ridge correction 1.383 ns | No; CIs overlap | reports/1780997954.15397.168324f2__s18_astack_independent_reproduction |
| S18b | ✅ done | ✅ Sample-IV robust width 1.794 ns | LORO CFD20 period-polynomial width 1.471 ns | ridge residual correction width 1.935 ns | No; ML worse, broadening is calibration/low-stat sensitivity | reports/1781001480.695946.490c69d3 |
| P01 | ✅ done | ✅ 640,737 selected pulses | PCA-4 recon MSE 0.0134; hand-shape probe bal-acc 0.353 | masked AE-4 recon MSE 0.0143; probe bal-acc 0.364 | Mixed: PCA wins recon, AE only slight probe gain | reports/1780997954.15517.0cbc248c__p01_self_supervised_waveform_representation |
| P02 | ✅ merged | selection=S00 | PCA (lin) | autoencoder | **AE 40–51% better @ dim≤4; PCA better @ dim8** | reports/P02_pulse_representation_discovery |
| P03a | ✅ done | ✅ frozen S02 baseline reproduced | analytic amp-only timewalk sigma68 1.495 ns | tiny 18-sample MLP sigma68 1.927 ns | No; waveform MLP loses to analytic and frozen S02 baselines | reports/1781004956.603.7dce65be__p03a_18_sample_mlp_timing |
| P04 | ✅ done | ✅ 640,737 exact | peak amp res68 0.1238; integral charge res68 0.1954 | HGB amp res68 0.0091; charge res68 0.0151 | **Yes** for duplicate-readout closure; not absolute energy | reports/1780997954.15577.6c203777 |
| P07 | ✅ merged | self-truth (clip) | template scale | GBR | **ML ~4% vs template 10–29% (3–7× better)** | reports/P07_saturation_recovery |
| P10a | ✅ done | ✅ 640,737 exact | empirical template q MSE 0.0444; timing 3.831 ns | conditional MLP q MSE 0.0781; timing 3.579 ns | Mixed; ML improves timing but loses primary q-template metric | reports/1781000612.495978.66c00082__p10a_conditional_template |

## Current steering notes

- Queue health: `tn-ticket list --project testbeam` reports `open=35 claimed=2 done=26 failed=8`;
  no tickets were appended in this cycle because the ready queue is above the 18-ticket floor.
  The legacy positional command `tn-ticket list testbeam` still reports the default queue
  (`open=5 claimed=0 done=0 failed=6`), so use `--project testbeam` for steering.
- Newest reports sharpen the next claims: S00b turns selector/baseline semantics into a small but
  real systematic; S02b shows a strong traditional timewalk closure can beat the S02 ridge
  baseline on run 65; S03a lowers sigma68 further but needs leave-one-run-out stability; S07b
  proves D_t labels are self-referential; S07c shows shape RF can beat q_template-only on weak
  clean-timing labels, but the historical App.A table must be recovered or retired; P10a says
  conditional templates need explicit timewalk terms; S10b shows the 90 ns pile-up live-time is
  not a measured detector window for the present waveform definition; S16b shows early-sample
  baseline closure is still not true no-pulse pedestal validation because forced/random tags are
  absent; P04 is a strong duplicate-readout closure, not an energy calibration; P03a shows
  18-sample waveform-deep timing needs run-stability and residual-target tests before adoption;
  S18b says A-stack broadening is low-stat/calibration-definition sensitivity, not a clean
  period shift; S16c says adaptive-lowering features are not the primary S02 timing-tail source.
- Active ready follow-ups already cover the requested atomic pulse axes: P01c/P02b/P03b/P03c for
  shape and timing, P04b/P04c/P07b/P10b/P10c for amplitude, charge, saturation, and template
  phase, S10c/S10d/S11a for pile-up and live-time, S00c/S16d/S16e/S04b for selector, baseline,
  dropout, true-pedestal sourcing, and timing-tail propagation, and S05b/S05c/S07d/S07e/S18c/S18d
  for covariance, control labels, and external timing checks.
- Near-term physics risk: ML wins only when the traditional comparator is genuinely weaker on
  the same held-out data. Keep every new claim paired, run-held-out, leakage-audited, and
  bootstrap-CI based before feeding PID or energy studies.
