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
| S02c | ✅ done | ✅ S02/S03 inputs reproduced | no-drift global timewalk 1.635 ns; binned drift model 3.404 ns | ridge-on-CFD20 1.846 ns | No; drift nuisance does not improve run-65 closure | reports/1781005800.1736.6e8916b8 |
| S03a | ✅ done | ✅ exact S02 reproduction | analytic amp-only timewalk 1.495 ns | ridge residual corrector 1.392 ns | Marginal; CIs overlap, needs leave-one-run-out stability | reports/1781000705.514827.50025402__s03a_analytic_timewalk_correction |
| S03b | ✅ done | ✅ S03a baselines exactly reproduced | monotonic amplitude-binned timewalk 1.570 ns | ridge residual corrector 1.392 ns | No for binned traditional vs S03a amp-only; ML remains better on run 65 | reports/1781005627.1825.6e067067 |
| S03c | ✅ done | ✅ S00 and S03a run-65 reproduction | LORO analytic timewalk 1.551 ns | LORO ridge residual 1.537 ns | Tie; analytic closure is stable across Sample-II runs | reports/1781005627.1877.378c7a87 |
| S05a | ✅ done | ✅ A-stack/B-stack external-control inputs | CFD20 pair-median residual width 2.082 ns | ExtraTrees B+A width 1.664 ns | No secure A-control gain; shuffled-A control is similar | reports/1781001480.696013.4ac50583__s05a_astack_external_control |
| S07 | ✅ done | ✅ S00 selection | low-current AUC 0.504 | calibrated RF AUC 0.768 | **Yes** (Δ=0.264, CI [0.250,0.280]) | reports/1780997954.15217.702122ea__s07_ml_rigour_scoreboard |
| S07b | ✅ done | ✅ guarded gross D_t count match | D_t/curvature AUC 1.000 | shape-only RF AUC 0.9987 | No; D_t is label-defining | reports/1781000790.531071.5a66741c__s07b_timing_control_classifier |
| S07c | ✅ done | ✅ S00 counts; App.A count mismatch | q_template-only AUC 0.717; span+q AUC 0.912 | clean-timing RF AUC 0.993 | **Yes** vs q_template-only, but weak-label drift remains | reports/1781000790.531136.203130b0__s07c_clean_timing_rf |
| S07e | ✅ done | ✅ guarded parent App.I count match | all-three curvature-only AUC 1.000 | shape-only RF AUC 0.993 | No; curvature/D_t target remains self-referential | reports/1781006037.1500.1d8044e2__s07e_all_three_downstream_curvature_rf |
| S10 | ✅ done | ✅ Rmax/current excess reproduced | downstream high-low excess 0.0103/event | injection score Δ=0.036 diagnostic | No; ML is monitoring only | reports/1780997954.15277.548b01a3__s10_pileup_rate_model |
| S10b | ✅ done | ✅ Rmax=4.222 MHz assumption and 6/6 topology checks | template tail live10 124.79 ns, CI [123.33,126.36] | ridge live10 123.19 ns, CI [120.72,125.55] | No adoption claim; 90 ns is an assumption, measured window implies Rmax≈3.05 MHz | reports/1781000867.546870.5c124aaf |
| S10c | ✅ done | ✅ S10 topology fractions within 0.0015 | matched-stratified excess 0.02025/event | current-score Δ=0.02975, AUC 0.640 | ML diagnostic; excess is heterogeneous after matching | reports/1781004956.733.387f428e |
| S11a | ✅ done | ✅ S01/S02 injection benchmark | bounded two-pulse fit time RMS 13.30 ns | compact MLP time RMS 10.67 ns | **Yes**, but ML failure rate is higher (0.295 vs 0.168) | reports/1781005319.561.508a188d |
| S16 | ✅ done | ✅ S00 selection | pretrigger median MAE 341 ADC | adaptive/learned MAE 48.9 ADC | **Yes**, but adaptive remains biased | reports/1780997954.15337.77205a71__s16_pedestal_baseline_validation |
| S16b closure | ✅ done | ✅ 640,737 exact | line3 early-sample predictor MAE 169.34 ADC | ridge closure MAE 173.71 ADC | No; traditional remains preferred, ML is contamination diagnostic | reports/1781000826.539659.030b7796__s16b_independent_pedestal_estimator_closure |
| S16b forced/proxy | ✅ done | ✅ 640,737 exact; 0 forced/random-tagged entries | adaptive proxy MAE 17.18 ADC | HGBR proxy MAE 15.64 ADC | Proxy only; true forced/random pedestal data absent | reports/1781001221.625922.5a564a7e__s16b_forced_trigger_pedestal_validation |
| S16c | ✅ done | ✅ S00/Sample-II counts and zero post-correction violations | lowering-nuisance ridge sigma68 3.251 ns | RF residual correction sigma68 2.921 ns | Weak/diagnostic; high-lowering events do not carry the timing tails | reports/1781001221.625989.53423f03__s16c_pedestal_timing_nuisance |
| S18 | ✅ done | ✅ Sample III/IV A-stack | A1-A3 robust width 1.389 ns | ridge correction 1.383 ns | No; CIs overlap | reports/1780997954.15397.168324f2__s18_astack_independent_reproduction |
| S18b | ✅ done | ✅ Sample-IV robust width 1.794 ns | LORO CFD20 period-polynomial width 1.471 ns | ridge residual correction width 1.935 ns | No; ML worse, broadening is calibration/low-stat sensitivity | reports/1781001480.695946.490c69d3 |
| P01 | ✅ done | ✅ 640,737 selected pulses | PCA-4 recon MSE 0.0134; hand-shape probe bal-acc 0.353 | masked AE-4 recon MSE 0.0143; probe bal-acc 0.364 | Mixed: PCA wins recon, AE only slight probe gain | reports/1780997954.15517.0cbc248c__p01_self_supervised_waveform_representation |
| P01a | ✅ done | ✅ 640,737 exact | residual hand-shape bal-acc 0.292 | residual AE bal-acc 0.276 | No; topology sentinels dominate, shape probes need stricter leakage controls | reports/1781005204.1227.36547733__p01a_controlled_waveform_probes |
| P01b | ✅ done | ✅ 640,737 exact | PCA-4 recon MSE 0.01337 | masked AE-4 recon MSE 0.01428; artifact released | Mixed; artifact useful, no benchmark claim for all-data release | reports/1781005204.1292.46e43fb0__p01b_full_data_embedding_artifact |
| P01c | ✅ done | ✅ 640,737 exact | sample/window ablations: samples 3-5 dominate timing | AE occlusion/permutation probes find sample 5 highest | Diagnostic; use sample map to constrain P07e/P03c rather than claim ML adoption | reports/1781005319.562.584259c9__p01c_pulse_shape_importance_map |
| P02 | ✅ merged | selection=S00 | PCA (lin) | autoencoder | **AE 40–51% better @ dim≤4; PCA better @ dim8** | reports/P02_pulse_representation_discovery |
| P02b | ✅ done | ✅ P02 early-peak rate 0.04388 vs ≈0.044 | hand/PCA GMM run-heldout AMI 0.357 on q_template bins | AE GMM AMI 0.377 | Small ML gain only for q_template-bin morphology; not broadly superior | reports/1781004956.538.5fc10cd7 |
| P03a | ✅ done | ✅ frozen S02 baseline reproduced | analytic amp-only timewalk sigma68 1.495 ns | tiny 18-sample MLP sigma68 1.927 ns | No; waveform MLP loses to analytic and frozen S02 baselines | reports/1781004956.603.7dce65be__p03a_18_sample_mlp_timing |
| P04 | ✅ done | ✅ 640,737 exact | peak amp res68 0.1238; integral charge res68 0.1954 | HGB amp res68 0.0091; charge res68 0.0151 | **Yes** for duplicate-readout closure; not absolute energy | reports/1780997954.15577.6c203777 |
| P04b | ✅ done | ✅ 640,737 exact; 640,482 valid duplicate rows | downstream charge-proxy res68 0.225 | external ML res68 0.212; duplicate-transfer ML 0.247 | Weak external gain only; duplicate closure does not transfer cleanly to energy proxy | reports/1781005862.2131.4dbf3cf0 |
| P04c | ✅ done | ✅ 640,737 exact; held-out runs 57/65 | adaptive-template ridge amp res68 0.0858; direct template scale worse | HGB amp res68 0.0091 | **Yes** for duplicate-readout closure; traditional template pathology needs diagnosis | reports/1781005862.2197.53fd45c8__p04c_amplitude_adaptive_template |
| P07 | ✅ merged | self-truth (clip) | template scale | GBR | **ML ~4% vs template 10–29% (3–7× better)** | reports/P07_saturation_recovery |
| P07b | ✅ done | ✅ P07 clip result exactly reproduced | artificial clip res68 0.148; natural timing tail 0.0384 | artificial clip res68 0.0298; natural tail 0.0329 but q_template shift -0.0897 | ML wins artificial closure; natural transfer needs boundary/systematic audits | reports/1781004956.668.7d00443a |
| P09a | ✅ done | ✅ 640,737 exact | robust-template top-128 curated precision 0.898 | PCA/AE/isolation precision 0.883; higher novel precision 0.766 | Mixed; ML better for novel taxa, traditional slightly better curated precision | reports/1781005319.615.15053b04__p09a_rare_waveform_anomaly_taxonomy |
| P10a | ✅ done | ✅ 640,737 exact | empirical template q MSE 0.0444; timing 3.831 ns | conditional MLP q MSE 0.0781; timing 3.579 ns | Mixed; ML improves timing but loses primary q-template metric | reports/1781000612.495978.66c00082__p10a_conditional_template |
| P10b | ✅ done | ✅ 640,737 exact | explicit timewalk q MSE 0.0444; timing 2.756 ns | conditional MLP q MSE 0.0781; timing 3.579 ns | No; explicit traditional timewalk beats conditional template | reports/1781006250.1276.49814de9 |

## Current steering notes

- Queue health: the exact requested command `tn-ticket list testbeam` now reports
  `open=6 claimed=0 done=0 failed=6`, below the 18-ticket floor, because the shim treats
  `testbeam` as a positional default-queue argument. A project-queue check during this steering
  pass reported
  `tn-ticket list --project testbeam` = `open=56 claimed=3 done=44 failed=11` after this pass
  appended three ready tickets under `project:testbeam`: P04f baseline-excursion charge-bias
  closure, S10f anomaly-stratified pile-up excess closure, and P08a penetration-depth weak-label
  PID null test.
- Newest reports sharpen the next claims: S00b turns selector/baseline semantics into a small but
  real systematic; S02b shows a strong traditional timewalk closure can beat the S02 ridge
  baseline on run 65; S02c says per-run drift terms do not rescue binned timewalk; S03c says
  analytic timewalk closure is stable across Sample-II leave-one-run-out splits; S03b says
  monotonic amplitude-binned timewalk does not beat S03a amp-only on run 65; P01c maps
  timing and saturation sensitivity to samples 3-6; S07b/S07e
  proves D_t labels are self-referential; S07c shows shape RF can beat q_template-only on weak
  clean-timing labels, but the historical App.A table must be recovered or retired; P10a says
  conditional templates need explicit timewalk terms and P10b shows those explicit terms beat the
  conditional template; S10b shows the 90 ns pile-up live-time is not a measured detector window
  for the present waveform definition; P09a adds rare baseline/early/delayed anomaly taxa that
  now need propagation into timing, pile-up, and charge; S16b shows early-sample
  baseline closure is still not true no-pulse pedestal validation because forced/random tags are
  absent; P04/P04c are strong duplicate-readout closures, while P04b warns that transfer to an
  external charge-energy proxy is much weaker; P03a shows
  18-sample waveform-deep timing needs run-stability and residual-target tests before adoption;
  S18b says A-stack broadening is low-stat/calibration-definition sensitivity, not a clean
  period shift; S16c says adaptive-lowering features are not the primary S02 timing-tail source.
- Active ready follow-ups cover the requested atomic pulse axes: P03b/P03c for shape and
  timing, P04b/P04c/P07e/P10b/P10c for amplitude, charge, saturation, and template phase,
  S10d/S10e/P05a for pile-up and live-time, S00c/S16d/S16e/S04b for selector, baseline, dropout,
  true-pedestal sourcing, and timing-tail propagation, S05b/S05c/S07d/S07e/S18c/S18d for
  covariance, control labels, and external timing checks, S14b for the smallest viable
  energy-scale preflight, plus P04f/S10f/P08a for anomaly-to-charge, anomaly-to-pile-up, and
  weak-label PID leakage audits.
- Near-term physics risk: ML wins only when the traditional comparator is genuinely weaker on
  the same held-out data. Keep every new claim paired, run-held-out, leakage-audited, and
  bootstrap-CI based before feeding PID or energy studies.
