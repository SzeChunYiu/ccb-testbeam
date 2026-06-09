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
| S02c selector | ✅ done | ✅ median 640,737; dynamic 706,373 | dynamic gate worsens run-65 sigma68 by 0.170 ns | ridge residual model shifts by 0.027 ns | ML is less selector-sensitive, but gate semantics remain a systematic | reports/1781006678.1312.2d7d140a |
| S03a | ✅ done | ✅ exact S02 reproduction | analytic amp-only timewalk 1.495 ns | ridge residual corrector 1.392 ns | Marginal; CIs overlap, needs leave-one-run-out stability | reports/1781000705.514827.50025402__s03a_analytic_timewalk_correction |
| S03b | ✅ done | ✅ S03a baselines exactly reproduced | monotonic amplitude-binned timewalk 1.570 ns | ridge residual corrector 1.392 ns | No for binned traditional vs S03a amp-only; ML remains better on run 65 | reports/1781005627.1825.6e067067 |
| S03b q-template | ✅ done | ✅ S00 gate | q_template-only AUC 0.741; 13.7% tail rejection at 95% clean retention | q_template RF AUC 0.843; AP 0.304 | **Yes** for weak tail labels; requires pair-residual validation | reports/1781006575.2877.41492e09 |
| S03c | ✅ done | ✅ S00 and S03a run-65 reproduction | LORO analytic timewalk 1.551 ns | LORO ridge residual 1.537 ns | Tie; analytic closure is stable across Sample-II runs | reports/1781005627.1877.378c7a87 |
| S03d | ✅ done | ✅ S03a/S03b LORO baselines reproduced | amp-only 1.551 ns; monotone-binned 1.645 ns | HGB residual 1.394 ns | ML gain is real in-fold; needs monotonicity/transfer audit before adoption | reports/1781010985.923.35c141ac |
| S05a | ✅ done | ✅ A-stack/B-stack external-control inputs | CFD20 pair-median residual width 2.082 ns | ExtraTrees B+A width 1.664 ns | No secure A-control gain; shuffled-A control is similar | reports/1781001480.696013.4ac50583__s05a_astack_external_control |
| S05c | ✅ done | ✅ S05-style B-stack residual inputs | pair-median/hierarchical covariance sigma68 2.082 ns; B2 off-diagonal dominates | ExtraTrees waveform residual sigma68 1.449 ns | ML reduces residual width, but covariance remains B2/topology dominated | reports/1781009478.9969.16fe02b4 |
| S07 | ✅ done | ✅ S00 selection | low-current AUC 0.504 | calibrated RF AUC 0.768 | **Yes** (Δ=0.264, CI [0.250,0.280]) | reports/1780997954.15217.702122ea__s07_ml_rigour_scoreboard |
| S07b | ✅ done | ✅ guarded gross D_t count match | D_t/curvature AUC 1.000 | shape-only RF AUC 0.9987 | No; D_t is label-defining | reports/1781000790.531071.5a66741c__s07b_timing_control_classifier |
| S07c | ✅ done | ✅ S00 counts; App.A count mismatch | q_template-only AUC 0.717; span+q AUC 0.912 | clean-timing RF AUC 0.993 | **Yes** vs q_template-only, but weak-label drift remains | reports/1781000790.531136.203130b0__s07c_clean_timing_rf |
| S07e | ✅ done | ✅ guarded parent App.I count match | all-three curvature-only AUC 1.000 | shape-only RF AUC 0.993 | No; curvature/D_t target remains self-referential | reports/1781006037.1500.1d8044e2__s07e_all_three_downstream_curvature_rf |
| S07f | ✅ done | ✅ all-three App.I counts and S07e RF reproduced | injected timing/template AUC 0.606 | shape-only RF AUC 0.822 | **Yes** for injected waveform-corruption truth; not yet a measured beam pile-up rate | reports/1781012109.1290.18206042 |
| S07g | ✅ done | ✅ parent 72 gross and all-three 22 gross events | curvature-only AUC 1.000 | shape-only RF AUC 0.993; amplitude-only AUC 0.779 | No; D_t/curvature remains the label ceiling, shape is diagnostic by stratum | reports/1781012109.1288.14a764a8__s07g_appi_amplitude_current_stratification |
| S10 | ✅ done | ✅ Rmax/current excess reproduced | downstream high-low excess 0.0103/event | injection score Δ=0.036 diagnostic | No; ML is monitoring only | reports/1780997954.15277.548b01a3__s10_pileup_rate_model |
| S10b | ✅ done | ✅ Rmax=4.222 MHz assumption and 6/6 topology checks | template tail live10 124.79 ns, CI [123.33,126.36] | ridge live10 123.19 ns, CI [120.72,125.55] | No adoption claim; 90 ns is an assumption, measured window implies Rmax≈3.05 MHz | reports/1781000867.546870.5c124aaf |
| S10c | ✅ done | ✅ S10 topology fractions within 0.0015 | matched-stratified excess 0.02025/event | current-score Δ=0.02975, AUC 0.640 | ML diagnostic; excess is heterogeneous after matching | reports/1781004956.733.387f428e |
| S10c threshold | ✅ done | ✅ live10 anchor exact | template tail 10% live time 124.79 ns; all thresholds above 90 ns | ridge live-time R²≈0.884 at 10% | No adoption claim; threshold scan confirms 90 ns is not measured waveform live-time | reports/1781007337.1308.7dc86005 |
| S10d | ✅ done | ✅ S10b Rmax/live10 reproduced | bounded two-pulse resolvable delay 60 ns; time RMS 13.83 ns | compact MLP delay 20 ns; time RMS 9.41 ns | **Yes**, but failure rate rises 0.172→0.323 | reports/1781007337.1325.2241031c |
| S10d amplitude | ✅ done | ✅ S10c topology fractions within 0.0015 | matched two-pulse secondary fraction high-low 0.0316, CI [0.0189,0.0440] | RF secondary fraction Δ=0.0073; overlap score Δ=0.0245 | Diagnostic; largest excess is high-amp/large-lowering/broad-late | reports/1781010419.1206.6d667357 |
| S10e | ✅ done | ✅ S10/S10c topology fractions within 0.0015 | charge-stratified downstream excess 0.00676/event; P04 log-charge shift 0.0476 | current/pile-up scores positive; charge-residual score negative | Traditional matched excess remains physics-facing; ML is pathology diagnostic | reports/1781010955.636.68b17313 |
| S11a | ✅ done | ✅ S01/S02 injection benchmark | bounded two-pulse fit time RMS 13.30 ns | compact MLP time RMS 10.67 ns | **Yes**, but ML failure rate is higher (0.295 vs 0.168) | reports/1781005319.561.508a188d |
| S11b | ✅ done | ✅ S10c topology fractions within 0.0015 | real high-current secondary fraction Δ=0.0181, CI [-0.0168,0.0541] | RF secondary fraction Δ=0.00437, CI [-0.00138,0.0121] | Diagnostic; largest traditional excess is high-amp/large-lowering/broad-late | reports/1781010611.1197.028b141a |
| S11c | ✅ done | ✅ S11a anchor reproduced | amplitude-binned asymmetric template time RMS 17.83 ns | compact MLP time RMS 10.67 ns | **Yes**, but ML failure rate remains high (0.295) | reports/1781010611.1262.2e354bed |
| S16 | ✅ done | ✅ S00 selection | pretrigger median MAE 341 ADC | adaptive/learned MAE 48.9 ADC | **Yes**, but adaptive remains biased | reports/1780997954.15337.77205a71__s16_pedestal_baseline_validation |
| S16b closure | ✅ done | ✅ 640,737 exact | line3 early-sample predictor MAE 169.34 ADC | ridge closure MAE 173.71 ADC | No; traditional remains preferred, ML is contamination diagnostic | reports/1781000826.539659.030b7796__s16b_independent_pedestal_estimator_closure |
| S16b forced/proxy | ✅ done | ✅ 640,737 exact; 0 forced/random-tagged entries | adaptive proxy MAE 17.18 ADC | HGBR proxy MAE 15.64 ADC | Proxy only; true forced/random pedestal data absent | reports/1781001221.625922.5a564a7e__s16b_forced_trigger_pedestal_validation |
| S16c | ✅ done | ✅ S00/Sample-II counts and zero post-correction violations | lowering-nuisance ridge sigma68 3.251 ns | RF residual correction sigma68 2.921 ns | Weak/diagnostic; high-lowering events do not carry the timing tails | reports/1781001221.625989.53423f03__s16c_pedestal_timing_nuisance |
| S16d | ✅ done | ✅ 640,737 exact; 0 forced/random entries | metadata + quiet-run scan finds no true forced/random source | pretrigger quiet-proxy AUC 0.646 | No true pedestal sample; use only as pseudo-pedestal diagnostic | reports/1781007587.2596.601c7510__s16d_forced_random_pedestal_run_search |
| S16d strata | ✅ done | ✅ 640,737 exact; 0 forced/random entries | large-lowering selected-pulse MAE 2363 ADC; quiet proxy large-lowering rare | pretrigger logistic AUC 0.997 for large-lowering stratum | Diagnostic; large lowering is contamination/pathology, not true pedestal truth | reports/1781010419.1274.000b7be0 |
| S16e | ✅ done | ✅ S02b baseline reproduced | pretrigger proxy correction sigma68 1.445 ns | waveform+pretrigger ridge sigma68 1.387 ns | Weak ML gain; both improve S02b but tail CIs overlap | reports/1781007910.1647.505b465f |
| S16e tagged-random | ✅ done | ✅ 640,737 exact; 0 tagged-random B-stack entries | fallback mean3 MAE 241.6 ADC | fallback calibrated ridge MAE 197.3 ADC | No validation claim; primary tagged-random gate failed | reports/1781007587.2616.535e78de |
| S16d Sample-I | ✅ done | ✅ 252,266 Sample-I pulses | lowering correction sigma68 3.060 ns | lowering ML sigma68 2.930 ns | Diagnostic; high-lowering tail is 13.0% vs 1.24%, but sigma68 gain is small | reports/1781009378.1771.3b9145b2__s16d_sample_i_bstack_pedestal_timing |
| S18 | ✅ done | ✅ Sample III/IV A-stack | A1-A3 robust width 1.389 ns | ridge correction 1.383 ns | No; CIs overlap | reports/1780997954.15397.168324f2__s18_astack_independent_reproduction |
| S18b | ✅ done | ✅ Sample-IV robust width 1.794 ns | LORO CFD20 period-polynomial width 1.471 ns | ridge residual correction width 1.935 ns | No; ML worse, broadening is calibration/low-stat sensitivity | reports/1781001480.695946.490c69d3 |
| S18c | ✅ done | ✅ Sample-IV width reproduced | calibration-pool robust width 1.49-1.79 ns | ridge varies by pool | Mixed; Sample-IV broadening is calibration-pool sensitive | reports/1781008255.1458.3732667d |
| S18d | ✅ done | ✅ historical A-stack numbers | Student-t scale 1.240 ns; binned sigma 2.077 ns | ridge cross-check only | No adoption; fit window/core estimator explains much of the excess | reports/1781008255.1472.46fb0e58 |
| P01 | ✅ done | ✅ 640,737 selected pulses | PCA-4 recon MSE 0.0134; hand-shape probe bal-acc 0.353 | masked AE-4 recon MSE 0.0143; probe bal-acc 0.364 | Mixed: PCA wins recon, AE only slight probe gain | reports/1780997954.15517.0cbc248c__p01_self_supervised_waveform_representation |
| P01a | ✅ done | ✅ 640,737 exact | residual hand-shape bal-acc 0.292 | residual AE bal-acc 0.276 | No; topology sentinels dominate, shape probes need stricter leakage controls | reports/1781005204.1227.36547733__p01a_controlled_waveform_probes |
| P01b | ✅ done | ✅ 640,737 exact | PCA-4 recon MSE 0.01337 | masked AE-4 recon MSE 0.01428; artifact released | Mixed; artifact useful, no benchmark claim for all-data release | reports/1781005204.1292.46e43fb0__p01b_full_data_embedding_artifact |
| P01b downstream | ✅ done | ✅ 640,737 exact | hand/PCA sample-epoch probe bal-acc 0.602/0.649 | AE-4 sample-epoch probe bal-acc 0.634 | No adoption; latent/domain drift needs residualization before downstream use | reports/1781010192.1206.019d7d9e__p01b_downstream_waveform_probes |
| P01c | ✅ done | ✅ 640,737 exact | sample/window ablations: samples 3-5 dominate timing | AE occlusion/permutation probes find sample 5 highest | Diagnostic; use sample map to constrain P07e/P03c rather than claim ML adoption | reports/1781005319.562.584259c9__p01c_pulse_shape_importance_map |
| P01c artifact | ✅ done | ✅ 640,737 exact recount | publish/verify non-git P01b latent artifact | artifact hashes and metadata verified | Infrastructure; enables downstream consumers, not a physics benchmark | reports/1781010024.910.7fbe14e8__p01c_publish_p01b_latent_artifact |
| P01c sentinels | ✅ done | ✅ 640,737 exact | residual PCA+hand bal-acc 0.331 | residual AE-4 bal-acc 0.235 | No; repeated shuffle sentinels reject the ML representation claim | reports/1781010192.1271.5e804d02__p01c_repeated_leakage_sentinels |
| P01d | ✅ done | ✅ 640,737 exact | train-chosen OF(5-13) sigma68 2.693 ns | ridge residual sigma68 1.974 ns; target shuffle 3.329 ns | Diagnostic; sample 5 is CFD artifact, sample 6 smoothing is robust | reports/1781010798.954.0e922a2d |
| P01e | ✅ done | ✅ prior P01c CFD20/latent reproduced | strict hand-shape ridge sigma68 1.962 ns | strict AE latent ridge sigma68 1.965 ns; shuffled target 2.056 ns | No; latent does not beat hand-shape and null controls remain strong | reports/1781010798.1019.19c63d1a__p01e_strict_latent_timing_audit |
| P02 | ✅ merged | selection=S00 | PCA (lin) | autoencoder | **AE 40–51% better @ dim≤4; PCA better @ dim8** | reports/P02_pulse_representation_discovery |
| P02b | ✅ done | ✅ P02 early-peak rate 0.04388 vs ≈0.044 | hand/PCA GMM run-heldout AMI 0.357 on q_template bins | AE GMM AMI 0.377 | Small ML gain only for q_template-bin morphology; not broadly superior | reports/1781004956.538.5fc10cd7 |
| P02c q-template | ✅ done | ✅ S01 q_template row semantics exact | hand/PCA GMM manual-flag AMI 0.674; q-template AMI 0.154 | AE/P01-style morphology is target-specific | Mixed; learned morphology is not a universal cluster win | reports/1781009575.1631.563755ca |
| P02c embedding | ✅ done | ✅ 640,737 exact; P01b artifact regenerated if missing | hand+PCA manual-flag AMI 0.497; purity 0.915 | train-only AE AMI 0.479; purity 0.912 | No; all-data embedding is forbidden diagnostic for claims | reports/1781010024.975.3e06183e__p02c_p01b_embedding_consumer |
| P02d | ✅ done | ✅ early-peak rate and S07 gross-tail count | early-peak/topology AUC 0.692 on D_t tails | shape-only RF AUC 0.999 | Diagnostic only; downstream shape is label-source self-reference risk | reports/1781009575.1697.2f57332a |
| P03a | ✅ done | ✅ frozen S02 baseline reproduced | analytic amp-only timewalk sigma68 1.495 ns | tiny 18-sample MLP sigma68 1.927 ns | No; waveform MLP loses to analytic and frozen S02 baselines | reports/1781004956.603.7dce65be__p03a_18_sample_mlp_timing |
| P03b | ✅ done | ✅ P03a run-65 reproduction | LORO analytic timewalk mean sigma68 1.496 ns | waveform MLP mean sigma68 1.805 ns | No; ML beats S02 ridge on 6/7 runs but not analytic baseline | reports/1781009029.1279.4d6e17f9 |
| P03c | ✅ done | ✅ P03a reproduced first | analytic sigma68 1.495 ns | MLP residual 1.448 ns; CNN residual 1.497 ns | CNN adds nothing; MLP gain is small and control-sensitive | reports/1781009029.1288.7e78286e |
| P04 | ✅ done | ✅ 640,737 exact | peak amp res68 0.1238; integral charge res68 0.1954 | HGB amp res68 0.0091; charge res68 0.0151 | **Yes** for duplicate-readout closure; not absolute energy | reports/1780997954.15577.6c203777 |
| P04b | ✅ done | ✅ 640,737 exact; 640,482 valid duplicate rows | downstream charge-proxy res68 0.225 | external ML res68 0.212; duplicate-transfer ML 0.247 | Weak external gain only; duplicate closure does not transfer cleanly to energy proxy | reports/1781005862.2131.4dbf3cf0 |
| P04c | ✅ done | ✅ 640,737 exact; held-out runs 57/65 | adaptive-template ridge amp res68 0.0858; direct template scale worse | HGB amp res68 0.0091 | **Yes** for duplicate-readout closure; traditional template pathology needs diagnosis | reports/1781005862.2197.53fd45c8__p04c_amplitude_adaptive_template |
| P04d | ✅ done | ✅ 640,737 exact; held-out runs 57/65 | strong Huber duplicate closure res68 0.0203; direct template scale 0.577 | ExtraTrees duplicate closure res68 0.00270 | **Yes** for duplicate-readout waveform closure; still not external energy truth | reports/1781011912.1215.01fb264f |
| P05a | ✅ done | ✅ S11a injection anchor reproduced | bounded two-pulse fit time RMS 13.90 ns; failure 0.168 | compact CNN time RMS 10.01 ns; failure 0.228 | No adoption; CNN improves RMS but failure-rate regression is clear | reports/1781010938.498.6bd050f4 |
| P07 | ✅ merged | self-truth (clip) | template scale | GBR | **ML ~4% vs template 10–29% (3–7× better)** | reports/P07_saturation_recovery |
| P07b | ✅ done | ✅ P07 clip result exactly reproduced | artificial clip res68 0.148; natural timing tail 0.0384 | artificial clip res68 0.0298; natural tail 0.0329 but q_template shift -0.0897 | ML wins artificial closure; natural transfer needs boundary/systematic audits | reports/1781004956.668.7d00443a |
| P07c | ✅ done | ✅ P07/P07b anchors reproduced | template-family artificial res68 0.148 | ratio-transfer res68 0.0393; boundary timing-tail delta ≈ -0.006 | ML wins artificial closure; boundary q_template/timing shifts require leakage controls | reports/1781010522.1275.6b5664c7 |
| P07d | ✅ done | ✅ Sample-II B2 count reproduced | template pseudo-saturation res68 0.200 | ratio-transfer res68 0.0541; max tail envelope 0.0769 on run 65 | Diagnostic; saturation correction has a run-dependent timing-tail envelope | reports/1781010522.1343.1dda69d0 |
| P07e | ✅ done | ✅ Sample-II B2 count and saturation proxy reproduced | retained-window/template ablations | best GBR window w2-8 res68 0.0812, bias 0.0292 | Not adoptable yet; needs calibrated accept/veto rule | reports/1781010945.568.060f508b |
| P09a | ✅ done | ✅ 640,737 exact | robust-template top-128 curated precision 0.898 | PCA/AE/isolation precision 0.883; higher novel precision 0.766 | Mixed; ML better for novel taxa, traditional slightly better curated precision | reports/1781005319.615.15053b04__p09a_rare_waveform_anomaly_taxonomy |
| P10a | ✅ done | ✅ 640,737 exact | empirical template q MSE 0.0444; timing 3.831 ns | conditional MLP q MSE 0.0781; timing 3.579 ns | Mixed; ML improves timing but loses primary q-template metric | reports/1781000612.495978.66c00082__p10a_conditional_template |
| P10b | ✅ done | ✅ 640,737 exact | explicit timewalk q MSE 0.0444; timing 2.756 ns | conditional MLP q MSE 0.0781; timing 3.579 ns | No; explicit traditional timewalk beats conditional template | reports/1781006250.1276.49814de9 |

## Current steering notes

- Queue health: the exact requested command `tn-ticket list testbeam` reports
  `open=9 claimed=0 done=0 failed=7`, below the 18-ticket floor, because the shim treats
  `testbeam` as a positional argument for the default queue. The required append path was followed
  again with `--project testbeam`; the project-aware testbeam queue remains deep
  (`queue=130` before this append pass; `queue=136` on the post-append audit, with concurrent
  worker movement),
  but the mission trigger still required new ready work. This pass appended three ready
  non-duplicate tickets:
  S07i S07f score transfer from injected corruption to real high-current strata
  (`1781024786.1471.167d1f38`), P04i duplicate-readout charge closure sample-causality map
  (`1781024791.1539.3ba15c1d`), and S03h HGB timewalk gain support map by amplitude and shape
  atoms (`1781024797.1607.4a1b6480`). The previous pass appended:
  P04h A-stack charge-transfer support map by B-stack topology
  (`1781023326.470.61534f82`), S02h binned-timewalk shuffled-target failure autopsy
  (`1781023333.541.66a8325e`), and P12a pulse-axis covariance atom table across pathology flags
  (`1781023340.632.43377364`).
- Newest reports sharpen the next claims: S00b/S02c turn selector/baseline semantics into a small but
  real systematic; S02b shows a strong traditional timewalk closure can beat the S02 ridge
  baseline on run 65; S02c says per-run drift terms do not rescue binned timewalk and selector
  semantics can move timing closure; S03c says analytic timewalk closure is stable across
  Sample-II leave-one-run-out splits; S03b says monotonic amplitude-binned timewalk does not beat
  S03a amp-only on run 65, while q_template-only tail cuts need pair-residual validation; P01c maps
  timing and saturation sensitivity to samples 3-6; S07b/S07e
  proves D_t labels are self-referential; S07c shows shape RF can beat q_template-only on weak
  clean-timing labels, but the historical App.A table must be recovered or retired; P10a says
  conditional templates need explicit timewalk terms and P10b shows those explicit terms beat the
  conditional template; S10b shows the 90 ns pile-up live-time is not a measured detector window
  for the present waveform definition; P09a adds rare baseline/early/delayed anomaly taxa that
  now need propagation into timing, pile-up, and charge; S16b shows early-sample
  baseline closure is still not true no-pulse pedestal validation because forced/random tags are
  absent; P04/P04c are strong duplicate-readout closures, while P04b warns that transfer to an
  external charge-energy proxy is much weaker; S10d shows ML can improve injected two-pulse
  resolution only if its higher failure rate is controlled; S16d confirms no true forced/random
  pedestal sample is present in the current mirror, and S16e says pre-trigger proxies improve
  timing closure but do not remove the need for leave-one-run-out tail validation; the tagged-random
  S16e gate also fails with zero B-stack entries. P03b/P03c show waveform ML can beat the weaker
  S02 ridge comparator but not the strong analytic timewalk baseline, and CNN structure adds no
  clear residual gain. S18c/S18d say A-stack broadening is calibration-pool and core-estimator
  sensitivity, not a clean period shift; S16d Sample-I says high adaptive-lowering events are
  tail-enriched, but lowering corrections barely move sigma68. The newest P01b/P02c/P02d reports
  show representation work is still dominated by domain, topology, and label-source sentinels:
  P01b-downstream separates Sample I/II better with PCA than AE on balanced accuracy, P02c says
  train-only AE embeddings do not beat hand+PCA morphology for manual flags, and P02d's impressive
  RF timing-tail AUC is largely downstream D_t self-reference. S05c finds a real B-stack covariance
  opportunity, but its decomposition remains B2/topology dominated even when ML reduces residual
  width. P01c/P01e now show that strict waveform-latent timing probes fail repeated shuffle and
  event-shuffled controls, so hand-shape and null floors must accompany any latent timing claim.
  P01d narrows the sample-importance interpretation: sample 5's sign flip is a CFD interpolation
  artifact, while sample 6 smoothing is robust across template/OF timing. P07c/P07d keep
  saturation recovery useful but expose boundary q_template shifts and a run-65 timing-tail
  envelope. P05a/S11b/S11c confirm that two-pulse ML improves time RMS but still needs
  failure-aware operation, and real high-current signatures concentrate in
  high-amplitude/large-lowering/broad-late strata while amplitude-binned asymmetric templates do
  not close the ML gap. The newer S10d amplitude-stratified result moves pile-up from a binary
  occupancy excess into a high-amp/large-lowering/broad-late secondary-fraction diagnostic, and
  S16d strata show large adaptive lowering is strongly predictable from pre-trigger
  contamination/pathology while true forced/random pedestal data remain absent. The freshest S03d
  HGB result improves held-out timewalk residuals but now needs monotonicity and transfer
  falsification; S10e shows the current excess survives charge-energy stratification; P07e keeps
  saturation recovery non-adoptable until acceptance rules bound bias and timing-tail risk. The
  freshest P04c A/B transfer report says external A-stack charge prediction is broad and
  topology-limited (best res68 0.519 vs shuffled 0.521), so energy/PID consumers need support maps
  before treating charge transfer as truth. The latest S02d/S02e drift reports say global timewalk
  remains stable, current/rate drift adds no gain, and the binned branch can lose to shuffled-target
  controls. The latest S02d anomaly-tail report shows a generic ML high-risk cut can reduce tails
  only while removing about 24% of pairs and shifting composition, so tail cuts must be support- and
  composition-preserving. The newest S07f report makes the all-three RF useful again by validating
  it on injected two-pulse truth (AUC 0.822 vs 0.606 traditional), but it must now be calibrated
  against real high-current strata before it is interpreted as measured beam pile-up. The newest
  S07g stratification keeps curvature as the D_t label ceiling while showing amplitude-only
  nuisance is non-negligible. The newest P04d report repairs the direct-template duplicate closure
  with a strong Huber traditional model (res68 0.0203) and an even stronger waveform ML closure
  (res68 0.00270), but the A/B transfer reports still block any external energy claim.
- Active ready follow-ups cover the requested atomic pulse axes: P03d/P03e/P03f/P03g for shape
  and timing, P04b/P04c/P07e/P10b/P10c for amplitude, charge, saturation, and template phase,
  S10d/S10e/P05a for pile-up and live-time, S00c/S16d/S16e/S04b for selector, baseline, dropout,
  true-pedestal sourcing, and timing-tail propagation, S05b/S05c/S05f/S07d/S07e/S18c/S18d for
  covariance, control labels, and external timing checks, S14b for the smallest viable
  energy-scale preflight, plus P04f/S10f/P08a/P05b/S16g/S00d/P09c/S14c for anomaly-to-charge,
  anomaly-to-pile-up, weak-label PID leakage, failure-aware pile-up recovery, pseudo-pedestals,
  selector taxonomy, delayed-peak/dropout propagation, and saturation-aware energy ordering. This
  pass adds S06a for charge-proxy timing monotonicity, P10f for tail-shape/live-time transfer
  across saturation and current, S13c for charge-matched current weak-supervision nulls, and P11a
  for pretrigger baseline spectra before they feed dropout, pile-up, PID, or energy consumers.
  This pass adds P04h for external charge-transfer support limits, S02h for binned-timewalk
  null-control failure analysis, and P12a for a compact covariance atom table tying saturation,
  pile-up, baseline, dropout/anomaly, timing-tail, and charge-error axes together before PID or
  energy consumers reuse them. This pass adds S07i for injection-to-real high-current score
  transfer, P04i for sample-causal charge-closure ablations, and S03h for an amplitude/shape
  support map of the S03d HGB timewalk gain.
- Near-term physics risk: ML wins only when the traditional comparator is genuinely weaker on
  the same held-out data. Keep every new claim paired, run-held-out, leakage-audited, and
  bootstrap-CI based before feeding PID or energy studies.
