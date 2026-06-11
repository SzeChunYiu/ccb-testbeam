# P04x Retained-Support Charge-Interval Calibration

- **Ticket:** `1781069576.790.606924bd`
- **Worker:** `testbeam-laptop-3`
- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo truth.
- **Split:** leave-one-run-out by run; bootstrap intervals resample complete held-out run blocks.
- **Target:** event-matched selected A1/A3 positive-lobe charge predicted from B-stack waveforms and support variables.
- **Predecessor:** P04w out-of-fold predictions are used as the fixed method panel; P04x independently rebuilds raw gates and event rows before interval calibration.

## 0. Question

After P04w/P04j indicated broad but nominally calibrated external charge behavior, is there any retained raw-HRD support cell in which fractional charge residual width, conformal interval coverage, interval width, and real-minus-sentinel separation are simultaneously acceptable?

## 1. Reproduction From Raw ROOT

The gate is rebuilt from raw `HRDv` samples. For each channel, the median of samples 0--3 is subtracted; a pulse is selected when the corrected peak exceeds 1000 ADC. The P04x event table is then rebuilt from `(run, EVT)` matches with selected B2 and selected A1 or A3.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|:---|
| B-stack selected pulse records | 640,737 | 640,737 | +0 | 0 | true |

| sample              |   events_with_selected |   selected_pulses |   A1 |   A3 |
|:--------------------|-----------------------:|------------------:|-----:|-----:|
| sample_iii_analysis |                   7168 |              9682 | 2799 | 6883 |
| sample_iv_analysis  |                    767 |               894 |  167 |  727 |

The ticket-local P04c charge-transfer reproduction on the same raw-derived rows is:

| method                      |    n |   bias_median_frac |   res68_abs_frac | res68_ci95                               |   full_rms_frac |   within_25pct |
|:----------------------------|-----:|-------------------:|-----------------:|:-----------------------------------------|----------------:|---------------:|
| b2_loglinear                | 4055 |         -0.0476348 |         0.520285 | [0.5050079956375032, 0.5379825525266126] |        0.84526  |       0.344513 |
| charge_transfer_ridge       | 4055 |         -0.0474201 |         0.519271 | [0.5082263564688714, 0.538176712751181]  |        0.842762 |       0.343527 |
| b_waveform_extra_trees      | 4055 |         -0.0485242 |         0.520686 | [0.5089987529973548, 0.5365021923478254] |        0.844806 |       0.345006 |
| shuffled_target_extra_trees | 4055 |         -0.0476479 |         0.52197  | [0.5075308869097516, 0.5384575037253061] |        0.845615 |       0.348952 |

## 2. Methods

For event \(i\), the external charge target is

`Q_i^A = I(A1_i) sum_t max(A1_it, 0) + I(A3_i) sum_t max(A3_it, 0)`,

where each indicator requires the raw-ROOT A-stack amplitude gate. Each method predicts `log(max(Q_i^A,1))` using B-stack waveform/support information only; run, event number, A-stack flags, and A-stack charge are excluded from predictor features.

The benchmark residual is

`r_i(m) = (hat Q_i(m) - Q_i^A) / max(Q_i^A, 1)`,

with primary width `res68_m = quantile_0.68(|r_i(m)|)`. The strong traditional methods are topology/support-cell median and Huber log-charge transfer. The ML/NN panel contains ridge, gradient-boosted trees, MLP, 1D-CNN, and the new support-gated residual CNN. The new architecture is included because P04x is explicitly a support-cell question: it gates convolutional B-waveform residual channels by scalar support features before regression.

For intervals, P04x uses split conformal residual calibration. For held-out run `h`, only rows from runs `!= h` estimate `q_alpha(c,m)`, the alpha quantile of `|r_i(m)|` in the most specific support cell with enough training support. The evaluated interval is the fractional band

`[hat Q_i(m) (1 - q_alpha), hat Q_i(m) (1 + q_alpha)]`,

clipped only by reporting denominators; coverage is tested by `|r_i(m)| <= q_alpha`. The hierarchy is full support cell, mid support cell, topology/amplitude cell, then global training-run fallback.

## 3. Head-To-Head Benchmark

| method                     | family           |    n |   bias_median_frac |   res68_abs_frac | res68_ci95                                 |   full_rms_frac |   coverage68 | coverage68_ci95                          |   coverage90 |   mean_width68_frac |
|:---------------------------|:-----------------|-----:|-------------------:|-----------------:|:-------------------------------------------|----------------:|-------------:|:-----------------------------------------|-------------:|--------------------:|
| topology_median            | traditional      | 4055 |        -0.00193406 |         0.381402 | [0.36620244607189895, 0.39461711223871165] |        0.6699   |     0.670037 | [0.6483448949487701, 0.6885681776765249] |     0.895931 |            0.85927  |
| strong_huber_transfer      | traditional      | 4055 |        -0.0143204  |         0.354272 | [0.34421660813423216, 0.36485864053001665] |        0.588912 |     0.681134 | [0.6646113894730619, 0.6955478818900607] |     0.899137 |            0.805475 |
| ridge                      | ml               | 4055 |        -0.039456   |         0.35907  | [0.34945383016488496, 0.37010854024719286] |        0.563354 |     0.683354 | [0.6661954598268327, 0.6987464740534489] |     0.898644 |            0.790388 |
| gradient_boosted_trees     | ml               | 4055 |        -0.0463165  |         0.360203 | [0.34867887973866474, 0.37189984979433094] |        0.570509 |     0.680641 | [0.6652483036471586, 0.6956470953989882] |     0.899877 |            0.794298 |
| mlp                        | ml               | 4055 |        -0.042221   |         0.385088 | [0.3750353541318712, 0.3983913384365704]   |        0.600078 |     0.677189 | [0.6579488239033694, 0.6921494765180185] |     0.895931 |            0.842285 |
| 1d_cnn                     | nn               | 4055 |        -0.00697367 |         0.366955 | [0.353332735248099, 0.38269945108521325]   |        0.645082 |     0.679162 | [0.6519341392997406, 0.7023780161489594] |     0.895684 |            0.893794 |
| support_gated_residual_cnn | new_architecture | 4055 |        -0.00408348 |         0.363855 | [0.34995694798063637, 0.3790038897118964]  |        0.62813  |     0.680148 | [0.6557343604579666, 0.7015935728017317] |     0.897411 |            0.852931 |
| topology_only_sentinel     | negative_control | 4055 |        -0.042667   |         0.351925 | [0.3415394314019964, 0.3659253107552014]   |        0.559756 |     0.683354 | [0.663802837222452, 0.6988994479785154]  |     0.89815  |            0.779179 |
| shuffled_target_hgb        | negative_control | 4055 |        -0.0424156  |         0.526496 | [0.5114309061249449, 0.5418553104062943]   |        0.836595 |     0.679408 | [0.6606531675364011, 0.6960387973606023] |     0.897164 |            1.27413  |

Point-estimate winner among real methods: `strong_huber_transfer` with res68 `0.3543`. Best traditional method: `strong_huber_transfer` at `0.3543`. Best ML/NN method: `ridge` at `0.3591`. Winner recorded in `result.json`: `none_no_retained_support_cell_passed`.

The benchmark plot is `head_to_head_res68_ci.png`.

## 4. Retained-Support Interval Frontier

A support cell is accepted only if it has at least 150 rows, at least 5 runs, retained fraction >= 0.25, res68 <= 0.40, mean 68% interval width <= 0.90, coverage68 in [0.60, 0.76], coverage90 in [0.84, 0.96], and both real-minus-shuffled and real-minus-topology res68 <= -0.03. These thresholds were copied into the config before reading P04x results.

| method                     | support_cell                                                                                 |   n |   n_runs |   retained_fraction |   res68_abs_frac |   coverage68 |   coverage90 |   mean_width68_frac |   shuffled_res68_abs_frac |   topology_only_res68_abs_frac |   real_minus_shuffled_res68 |   real_minus_topology_res68 | accepted_support_cell   |
|:---------------------------|:---------------------------------------------------------------------------------------------|----:|---------:|--------------------:|-----------------:|-------------:|-------------:|--------------------:|--------------------------:|-------------------------------:|----------------------------:|----------------------------:|:------------------------|
| support_gated_residual_cnn | A1_A3_pair|B2_only|7000_inf|any_B_amp_ge7000|late_tail_high|quiet|rising_6_8|extreme         |  70 |       19 |           0.0172626 |         0.217536 |     0.742857 |     0.857143 |            0.610955 |                  0.486863 |                       0.247604 |                   -0.269327 |                 -0.0300682  | False                   |
| strong_huber_transfer      | A1_A3_pair|B2_only|3000_5000|all_B_amp_lt7000|broad_saturation_like|quiet|rising_6_8|extreme | 169 |       20 |           0.0416769 |         0.233684 |     0.680473 |     0.905325 |            0.501109 |                  0.509564 |                       0.256681 |                   -0.27588  |                 -0.0229972  | False                   |
| support_gated_residual_cnn | A1_A3_pair|B2_only|5000_7000|all_B_amp_lt7000|broad_saturation_like|large|early_le5|extreme  |  80 |       15 |           0.0197287 |         0.235313 |     0.725    |     0.9375   |            0.543737 |                  0.479002 |                       0.236954 |                   -0.243689 |                 -0.00164046 | False                   |
| gradient_boosted_trees     | A1_A3_pair|B2_only|5000_7000|all_B_amp_lt7000|broad_saturation_like|large|early_le5|extreme  |  80 |       15 |           0.0197287 |         0.23863  |     0.7      |     0.9      |            0.530957 |                  0.479002 |                       0.236954 |                   -0.240373 |                  0.00167602 | False                   |
| gradient_boosted_trees     | A1_A3_pair|B2_only|7000_inf|any_B_amp_ge7000|late_tail_high|large|early_le5|extreme          |  53 |       15 |           0.0130703 |         0.242959 |     0.735849 |     0.943396 |            0.528236 |                  0.529494 |                       0.27794  |                   -0.286535 |                 -0.0349812  | False                   |
| topology_median            | A1_A3_pair|B2_only|7000_inf|any_B_amp_ge7000|late_tail_high|quiet|rising_6_8|extreme         |  70 |       19 |           0.0172626 |         0.24777  |     0.742857 |     0.871429 |            0.691591 |                  0.486863 |                       0.247604 |                   -0.239093 |                  0.00016565 | False                   |
| strong_huber_transfer      | A1_A3_pair|B2_only|5000_7000|all_B_amp_lt7000|broad_saturation_like|large|early_le5|extreme  |  80 |       15 |           0.0197287 |         0.248023 |     0.725    |     0.9125   |            0.552957 |                  0.479002 |                       0.236954 |                   -0.23098  |                  0.011069   | False                   |
| ridge                      | A1_A3_pair|B2_only|3000_5000|all_B_amp_lt7000|broad_saturation_like|quiet|rising_6_8|extreme | 169 |       20 |           0.0416769 |         0.250381 |     0.680473 |     0.899408 |            0.522062 |                  0.509564 |                       0.256681 |                   -0.259182 |                 -0.00629967 | False                   |
| topology_median            | A1_A3_pair|B2_only|5000_7000|all_B_amp_lt7000|broad_saturation_like|large|early_le5|extreme  |  80 |       15 |           0.0197287 |         0.25136  |     0.75     |     0.9375   |            0.55368  |                  0.479002 |                       0.236954 |                   -0.227642 |                  0.0144066  | False                   |
| support_gated_residual_cnn | A1_A3_pair|B2_only|3000_5000|all_B_amp_lt7000|broad_saturation_like|quiet|rising_6_8|extreme | 169 |       20 |           0.0416769 |         0.252958 |     0.686391 |     0.899408 |            0.552459 |                  0.509564 |                       0.256681 |                   -0.256606 |                 -0.00372307 | False                   |
| ridge                      | A1_A3_pair|B2_only|7000_inf|any_B_amp_ge7000|late_tail_high|quiet|rising_6_8|extreme         |  70 |       19 |           0.0172626 |         0.254034 |     0.714286 |     0.885714 |            0.639119 |                  0.486863 |                       0.247604 |                   -0.232829 |                  0.00642952 | False                   |
| strong_huber_transfer      | A1_A3_pair|B2_only|7000_inf|any_B_amp_ge7000|late_tail_high|quiet|rising_6_8|extreme         |  70 |       19 |           0.0172626 |         0.254875 |     0.7      |     0.871429 |            0.645077 |                  0.486863 |                       0.247604 |                   -0.231988 |                  0.00727093 | False                   |
| ridge                      | A1_A3_pair|B2_only|5000_7000|all_B_amp_lt7000|broad_saturation_like|large|early_le5|extreme  |  80 |       15 |           0.0197287 |         0.254964 |     0.7125   |     0.9375   |            0.56173  |                  0.479002 |                       0.236954 |                   -0.224038 |                  0.0180107  | False                   |
| 1d_cnn                     | A1_A3_pair|B2_only|3000_5000|all_B_amp_lt7000|broad_saturation_like|quiet|rising_6_8|extreme | 169 |       20 |           0.0416769 |         0.256223 |     0.686391 |     0.899408 |            0.529807 |                  0.509564 |                       0.256681 |                   -0.25334  |                 -0.00045784 | False                   |
| gradient_boosted_trees     | A1_A3_pair|B2_only|7000_inf|any_B_amp_ge7000|late_tail_high|quiet|rising_6_8|extreme         |  70 |       19 |           0.0172626 |         0.25805  |     0.7      |     0.871429 |            0.638915 |                  0.486863 |                       0.247604 |                   -0.228814 |                  0.0104453  | False                   |
| topology_median            | A1_A3_pair|B2_only|3000_5000|all_B_amp_lt7000|broad_saturation_like|quiet|rising_6_8|extreme | 169 |       20 |           0.0416769 |         0.258212 |     0.686391 |     0.899408 |            0.550574 |                  0.509564 |                       0.256681 |                   -0.251352 |                  0.00153089 | False                   |
| support_gated_residual_cnn | A1_A3_pair|B2_only|7000_inf|any_B_amp_ge7000|late_tail_high|large|early_le5|extreme          |  53 |       15 |           0.0130703 |         0.263022 |     0.698113 |     0.962264 |            0.522277 |                  0.529494 |                       0.27794  |                   -0.266471 |                 -0.0149179  | False                   |
| topology_median            | A1_A3_pair|B2_only|7000_inf|any_B_amp_ge7000|late_tail_high|large|early_le5|extreme          |  53 |       15 |           0.0130703 |         0.263591 |     0.754717 |     0.962264 |            0.591747 |                  0.529494 |                       0.27794  |                   -0.265903 |                 -0.0143492  | False                   |
| gradient_boosted_trees     | A1_A3_pair|B2_only|3000_5000|all_B_amp_lt7000|broad_saturation_like|quiet|rising_6_8|extreme | 169 |       20 |           0.0416769 |         0.264656 |     0.674556 |     0.899408 |            0.550066 |                  0.509564 |                       0.256681 |                   -0.244908 |                  0.00797481 | False                   |
| mlp                        | A1_A3_pair|B2_only|5000_7000|all_B_amp_lt7000|broad_saturation_like|large|early_le5|extreme  |  80 |       15 |           0.0197287 |         0.267299 |     0.75     |     0.95     |            0.60839  |                  0.479002 |                       0.236954 |                   -0.211703 |                  0.0303453  | False                   |

Risk-ranked retained fractions by model:

| method                     |   accepted_fraction |    n |   res68_abs_frac |   coverage68 |   coverage90 |   mean_width68_frac |
|:---------------------------|--------------------:|-----:|-----------------:|-------------:|-------------:|--------------------:|
| 1d_cnn                     |            1        | 4055 |         0.366955 |     0.679162 |     0.895684 |            0.893794 |
| 1d_cnn                     |            0.749938 | 3041 |         0.353353 |     0.670174 |     0.890497 |            0.817594 |
| 1d_cnn                     |            0.500123 | 2028 |         0.334993 |     0.667653 |     0.89497  |            0.73306  |
| 1d_cnn                     |            0.250062 | 1014 |         0.306753 |     0.654832 |     0.892505 |            0.608582 |
| gradient_boosted_trees     |            1        | 4055 |         0.360203 |     0.680641 |     0.899877 |            0.794298 |
| gradient_boosted_trees     |            0.749938 | 3041 |         0.337893 |     0.679053 |     0.900033 |            0.747219 |
| gradient_boosted_trees     |            0.500123 | 2028 |         0.312542 |     0.674063 |     0.897929 |            0.698037 |
| gradient_boosted_trees     |            0.250062 | 1014 |         0.276145 |     0.674556 |     0.899408 |            0.591342 |
| mlp                        |            1        | 4055 |         0.385088 |     0.677189 |     0.895931 |            0.842285 |
| mlp                        |            0.749938 | 3041 |         0.375095 |     0.669188 |     0.890497 |            0.81154  |
| mlp                        |            0.500123 | 2028 |         0.35334  |     0.671598 |     0.889546 |            0.76768  |
| mlp                        |            0.250062 | 1014 |         0.323332 |     0.667653 |     0.890533 |            0.67486  |
| ridge                      |            1        | 4055 |         0.35907  |     0.683354 |     0.898644 |            0.790388 |
| ridge                      |            0.749938 | 3041 |         0.342536 |     0.682012 |     0.898718 |            0.746369 |
| ridge                      |            0.500123 | 2028 |         0.316763 |     0.680966 |     0.900394 |            0.694771 |
| ridge                      |            0.250062 | 1014 |         0.279561 |     0.677515 |     0.900394 |            0.592474 |
| strong_huber_transfer      |            1        | 4055 |         0.354272 |     0.681134 |     0.899137 |            0.805475 |
| strong_huber_transfer      |            0.749938 | 3041 |         0.335436 |     0.679711 |     0.899375 |            0.755103 |
| strong_huber_transfer      |            0.500123 | 2028 |         0.311807 |     0.671598 |     0.90286  |            0.69614  |
| strong_huber_transfer      |            0.250062 | 1014 |         0.273027 |     0.677515 |     0.903353 |            0.57998  |
| support_gated_residual_cnn |            1        | 4055 |         0.363855 |     0.680148 |     0.897411 |            0.852931 |
| support_gated_residual_cnn |            0.749938 | 3041 |         0.345431 |     0.673134 |     0.894771 |            0.796034 |
| support_gated_residual_cnn |            0.500123 | 2028 |         0.31867  |     0.677022 |     0.897436 |            0.728852 |
| support_gated_residual_cnn |            0.250062 | 1014 |         0.28239  |     0.675542 |     0.904339 |            0.594529 |
| topology_median            |            1        | 4055 |         0.381402 |     0.670037 |     0.895931 |            0.85927  |
| topology_median            |            0.749938 | 3041 |         0.364852 |     0.662611 |     0.892798 |            0.82187  |
| topology_median            |            0.500123 | 2028 |         0.344815 |     0.653353 |     0.891519 |            0.762928 |
| topology_median            |            0.250062 | 1014 |         0.290673 |     0.670611 |     0.904339 |            0.626435 |

## 5. Falsification

Pre-registered metric: res68, full RMS, within-10/25%, coverage68/90, mean interval width, retained support fraction, real-minus-shuffled delta, and ML-minus-best-traditional deltas with run-block bootstrap 95% CIs. The decisive falsification test is whether a retained support cell beats both shuffled-target HGB and topology-only sentinels while maintaining calibrated interval coverage and nontrivial retained support.

Result: `none_no_retained_support_cell_passed`. Accepted retained support cells: `0`. The best real point-estimate method minus shuffled-target res68 is `-0.1722` and minus topology-only res68 is `0.0023`. Because the retained-cell acceptance gate considers 7 real model families, the report treats isolated cell wins as descriptive unless they pass all preconfigured gates.

## 6. Systematics And Caveats

- The target is selected A-stack charge, not deposited energy, particle ID, or Geant4 truth.
- P04x inherits the P04w fixed out-of-fold predictions; it does not re-tune model hyperparameters after looking at interval results.
- Run-block bootstrap intervals cover the observed run family, not unobserved detector configurations.
- Conformal residuals are exchangeability approximations inside support cells; drift within a support cell can produce nominal coverage with unusably broad intervals.
- The topology-only sentinel is a strong control. If a waveform method ties it, the result is not an independent charge-transfer measurement even when shuffled-target separation looks favorable.
- The largest support cells are dominated by B2-only topologies; retained fractions below 25% are not treated as operationally useful.

## 7. Findings And Next Steps

No retained support cell passes the preconfigured interval gate. The point-estimate winner is strong_huber_transfer (res68 0.3543), but the topology-only sentinel is 0.3519; best-minus-topology is 0.0023. Interval calibration can produce nominal coverage, but acceptable width, support fraction, and real-minus-sentinel separation do not coexist.

No follow-up ticket is appended. The conclusion is a negative operational gate: without new external truth or a changed detector acceptance definition, another charge-interval refinement would mostly retest the same topology-control limitation.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04x_1781069576_790_606924bd_retained_support_charge_interval_calibration.py --config configs/p04x_1781069576_790_606924bd_retained_support_charge_interval_calibration.yaml
```

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `raw_reproduction_counts.csv`, `astack_gate_counts.csv`, `ab_topology_counts_by_run.csv`, `p04c_reproduction_summary.csv`, `joined_predictions.csv`, `method_interval_summary.csv`, `retained_support_cells.csv`, `retention_frontier.csv`, `leakage_checks.csv`, and `head_to_head_res68_ci.png`.
