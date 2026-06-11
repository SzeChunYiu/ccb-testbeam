# P08d: PID weak-label action-band stability

**Ticket:** `1781054026.1934.7d3f4015`  
**Worker:** `testbeam-laptop-3`  
**Date:** 2026-06-11  
**Raw ROOT directory:** `data/root/root`  
**Config:** `configs/p08d_1781054026_1934_7d3f4015_pid_action_band_stability.json`  
**Git commit:** `28bcfad5e8a5779a85e2286e402476011eab650a`

## Abstract

This study tests whether the current transparent action bands preserve P08b/P08c-style
PID weak labels or create apparent PID separation by support loss.  The result is not
a truth-PID measurement.  I rebuild the calibrated P08b weak labels directly from raw
B-stack ROOT, merge the existing out-of-fold S14g veto-ladder and P07j saturation
action-band decisions, and benchmark a frozen traditional calibrated charge/depth
score against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new action-gated
residual waveform ensemble.  Controls include charge-only, depth/topology-only,
action-only, run-family-only, and shuffled-label waveform probes.

The `result.json` winner is **NN_action_gated_residual_ensemble_new** on the pre-action benchmark:
ROC AUC 0.9955 [0.9923, 0.9980], AP 0.9957,
ECE 0.0081.  The deployment conclusion is conservative: no PID adoption
without truth, and action-mask support shifts are treated as systematics rather than
as evidence for a particle-ID improvement.

## 1. Raw-ROOT Reproduction Gate

The selected-pulse count was recomputed from raw `h101/HRDv`.  For event `i`,
channel `c`, sample `t`,

`x_ict = HRDv_ict - median(HRDv_ic0, ..., HRDv_ic3)`,

and a B-stave pulse is selected when `max_t x_ict > 1000 ADC` for B2/B4/B6/B8
even channels.

| quantity                           |   report_value |   reproduced |   tolerance |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |           0 |       0 | True   |
| sample_i_calib selected pulses     |         248745 |       248745 |           0 |       0 | True   |
| sample_i_analysis selected pulses  |         252266 |       252266 |           0 |       0 | True   |
| sample_ii_calib selected pulses    |          14630 |        14630 |           0 |       0 | True   |
| sample_ii_analysis selected pulses |         125096 |       125096 |           0 |       0 | True   |

## 2. Weak Labels

The weak label is inherited from P08b and rebuilt here.  Let `d_i` be the deepest
selected B stave and `E_d` the monotonic PSTAR range-energy anchor.  A train-frozen
depth-wise quantile calibrator maps odd duplicate charge `Q_odd` to
`Ehat_odd(Q_odd, d)`.  The residual is

`r_i = (Ehat_odd(Q_odd,i, d_i) - E_d_i) / E_d_i`.

Within each run/depth atom, the lower and upper quartiles define balanced weak labels:
low residual is class 0 and high residual is class 1.  This is a charge/depth
weak label, not truth PID.

Labeled support: **289,626** B2 rows across **122** run/depth atoms.
The balanced run-held-out benchmark evaluates **29,134** rows.

## 3. Action-Band Merge

S14g decisions are complete-run-held-out selector decisions keyed by `(run,eventno,B2)`.
P07j decisions are leave-one-run-held-out natural-B2 saturation correction decisions.
P04s was requested by the ticket but no tracked P04s action-band artifact exists in
this checkout; it is therefore recorded as an unavailable systematic rather than
silently substituted.

| source   | available   |   rows_loaded | note                                                                                                           |
|:---------|:------------|--------------:|:---------------------------------------------------------------------------------------------------------------|
| S14g     | True        |        329548 | nan                                                                                                            |
| P07j     | True        |        177508 | nan                                                                                                            |
| P04s     | False       |             0 | No tracked P04s action-band artifact was available in this checkout; treated as an explicit systematic caveat. |

## 4. Methods

The traditional score is a logistic model using calibrated even-readout charge/depth,
topology, saturation, and range-energy variables:

`logit p(y=1|z) = beta0 + beta^T z`.

The ML/NN scores use complete runs held out.  Ridge uses an L2 linear waveform score
calibrated to probability; GBT uses histogram gradient boosting on normalized B2 samples
and hand-shape variables; MLP is a two-layer ReLU classifier; the 1D-CNN convolves the
18-sample B2 waveform.  The new architecture concatenates waveform shape summaries,
calibrated charge residuals, and action-band indicators in a residual HGB gate:

`s_new = f_HGB([x_wave, z_shape, z_charge, a_action])`.

Control probes intentionally expose single nuisance families: charge only, depth/topology
only, action only, run family only, and shuffled labels.

## 5. Metrics

For method score `s`, mask `m`, and label `y`, the primary metrics are ROC AUC, average
precision, expected calibration error,

`ECE = sum_b n_b/N | mean(y_b) - mean(p_b) |`,

and purity at fixed 80% high-residual-label efficiency.  Confidence intervals resample
complete held-out runs with replacement.  For each action mask I also report support loss
`1 - N_m/N`, median log-charge drift, mean depth drift, and induced label shift
`mean(y|m) - mean(y)`.

## 6. Action-Mask Composition

| action_mask                       |     n |   support_fraction |   support_loss |   positive_fraction |   action_band_label_shift |   charge_log_median_shift |   depth_mean_shift |   runs |
|:----------------------------------|------:|-------------------:|---------------:|--------------------:|--------------------------:|--------------------------:|-------------------:|-------:|
| all_pre_action                    | 29134 |         1          |       0        |            0.5      |                  0        |                  0        |         0          |     33 |
| s14g_traditional_accept           |  7651 |         0.262614   |       0.737386 |            0.215397 |                 -0.284603 |                 -0.875127 |        -0.0802741  |     21 |
| s14g_new_residual_accept          |  7483 |         0.256848   |       0.743152 |            0.220901 |                 -0.279099 |                 -0.810689 |        -0.0849406  |     21 |
| p07j_traditional_correct          |    67 |         0.00229972 |       0.9977   |            0.970149 |                  0.470149 |                  0.252198 |        -0.00896936 |     11 |
| s14g_traditional_and_p07j_correct |     0 |         0          |       1        |          nan        |                nan        |                nan        |       nan          |      0 |

## 7. Main Benchmark

| action_mask                       | method                                |     n |    roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   purity_at_80pct_eff |          ece |
|:----------------------------------|:--------------------------------------|------:|-----------:|-----------------:|------------------:|--------------------:|----------------------:|-------------:|
| all_pre_action                    | NN_action_gated_residual_ensemble_new | 29134 |   0.995532 |         0.992285 |          0.998039 |            0.995741 |              1        |   0.00810263 |
| all_pre_action                    | ML_mlp                                | 29134 |   0.988974 |         0.982614 |          0.994701 |            0.98941  |              0.997432 |   0.00505181 |
| all_pre_action                    | ML_gradient_boosted_trees             | 29134 |   0.988837 |         0.98202  |          0.994382 |            0.989899 |              0.997688 |   0.00662376 |
| all_pre_action                    | traditional_charge_depth_logistic     | 29134 |   0.984796 |         0.976282 |          0.991852 |            0.980892 |              0.98771  |   0.0286081  |
| all_pre_action                    | ML_ridge_waveform                     | 29134 |   0.958112 |         0.942511 |          0.973895 |            0.928991 |              0.969387 |   0.0398766  |
| all_pre_action                    | NN_1d_cnn                             | 29134 |   0.795654 |         0.733112 |          0.853479 |            0.710098 |              0.710679 |   0.112212   |
| p07j_traditional_correct          | traditional_charge_depth_logistic     |    67 |   1        |         1        |          1        |            1        |              1        |   0.0326757  |
| p07j_traditional_correct          | ML_gradient_boosted_trees             |    67 |   1        |         1        |          1        |            1        |              1        |   0.0144153  |
| p07j_traditional_correct          | ML_mlp                                |    67 |   1        |         1        |          1        |            1        |              1        |   0.00501181 |
| p07j_traditional_correct          | NN_action_gated_residual_ensemble_new |    67 |   1        |         1        |          1        |            1        |              1        |   0.0182425  |
| p07j_traditional_correct          | ML_ridge_waveform                     |    67 |   0.976923 |         0.915691 |          1        |            0.99929  |              1        |   0.0431291  |
| p07j_traditional_correct          | NN_1d_cnn                             |    67 |   0.969231 |         0.860294 |          1        |            0.999046 |              1        |   0.426828   |
| s14g_traditional_accept           | NN_action_gated_residual_ensemble_new |  7651 |   0.977713 |         0.960238 |          0.992602 |            0.936941 |              0.899045 |   0.0181119  |
| s14g_traditional_accept           | traditional_charge_depth_logistic     |  7651 |   0.962426 |         0.919543 |          0.987796 |            0.896908 |              0.66768  |   0.0628571  |
| s14g_traditional_accept           | ML_gradient_boosted_trees             |  7651 |   0.95724  |         0.922672 |          0.981342 |            0.885735 |              0.742117 |   0.0161868  |
| s14g_traditional_accept           | ML_mlp                                |  7651 |   0.953534 |         0.919781 |          0.984043 |            0.880747 |              0.746742 |   0.0158979  |
| s14g_traditional_accept           | ML_ridge_waveform                     |  7651 |   0.924954 |         0.866478 |          0.973251 |            0.770945 |              0.545756 |   0.0738624  |
| s14g_traditional_accept           | NN_1d_cnn                             |  7651 |   0.77297  |         0.653048 |          0.891766 |            0.36853  |              0.374964 |   0.305956   |
| s14g_traditional_and_p07j_correct | traditional_charge_depth_logistic     |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan          |
| s14g_traditional_and_p07j_correct | ML_ridge_waveform                     |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan          |
| s14g_traditional_and_p07j_correct | ML_gradient_boosted_trees             |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan          |
| s14g_traditional_and_p07j_correct | ML_mlp                                |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan          |
| s14g_traditional_and_p07j_correct | NN_1d_cnn                             |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan          |
| s14g_traditional_and_p07j_correct | NN_action_gated_residual_ensemble_new |     0 | nan        |       nan        |        nan        |          nan        |            nan        | nan          |

## 8. ML Minus Traditional

| action_mask                       | method                                |   roc_auc_minus_traditional |   average_precision_minus_traditional |   purity_at_80pct_eff_minus_traditional |   ece_minus_traditional |
|:----------------------------------|:--------------------------------------|----------------------------:|--------------------------------------:|----------------------------------------:|------------------------:|
| all_pre_action                    | NN_action_gated_residual_ensemble_new |                  0.0107352  |                           0.0148493   |                             0.0122902   |            -0.0205055   |
| all_pre_action                    | ML_mlp                                |                  0.00417815 |                           0.00851794  |                             0.00972239  |            -0.0235563   |
| all_pre_action                    | ML_gradient_boosted_trees             |                  0.00404088 |                           0.00900716  |                             0.00997857  |            -0.0219843   |
| all_pre_action                    | control_charge_only                   |                 -0.00039221 |                          -0.00119841  |                             0.000586377 |             0.0022312   |
| all_pre_action                    | ML_ridge_waveform                     |                 -0.0266841  |                          -0.0519016   |                            -0.0183229   |             0.0112685   |
| all_pre_action                    | control_depth_only                    |                 -0.175099   |                          -0.240826    |                            -0.244012    |             0.121588    |
| all_pre_action                    | NN_1d_cnn                             |                 -0.189142   |                          -0.270794    |                            -0.277031    |             0.0836036   |
| all_pre_action                    | control_action_only                   |                 -0.416598   |                          -0.449676    |                            -0.397908    |             0.0704245   |
| all_pre_action                    | control_run_family_only               |                 -0.484796   |                          -0.480892    |                            -0.48771     |            -0.0286081   |
| all_pre_action                    | control_shuffled_label_hgb            |                 -0.49679    |                          -0.505685    |                            -0.475722    |            -0.00797208  |
| p07j_traditional_correct          | ML_gradient_boosted_trees             |                  0          |                           0           |                             0           |            -0.0182604   |
| p07j_traditional_correct          | ML_mlp                                |                  0          |                           0           |                             0           |            -0.0276639   |
| p07j_traditional_correct          | NN_action_gated_residual_ensemble_new |                  0          |                           0           |                             0           |            -0.0144333   |
| p07j_traditional_correct          | control_charge_only                   |                  0          |                           0           |                             0           |            -0.00821534  |
| p07j_traditional_correct          | ML_ridge_waveform                     |                 -0.0230769  |                          -0.000710171 |                             0           |             0.0104534   |
| p07j_traditional_correct          | NN_1d_cnn                             |                 -0.0307692  |                          -0.000954371 |                             0           |             0.394153    |
| p07j_traditional_correct          | control_shuffled_label_hgb            |                 -0.0692308  |                          -0.00222069  |                             0           |             0.437794    |
| p07j_traditional_correct          | control_depth_only                    |                 -0.184615   |                          -0.00606314  |                            -0.0188679   |             0.334669    |
| p07j_traditional_correct          | control_run_family_only               |                 -0.5        |                          -0.0298507   |                            -0.0298507   |             0.437474    |
| p07j_traditional_correct          | control_action_only                   |                 -0.865385   |                          -0.0631817   |                            -0.0322581   |            -0.0326562   |
| s14g_new_residual_accept          | NN_action_gated_residual_ensemble_new |                  0.0170372  |                           0.04022     |                             0.234993    |            -0.0460734   |
| s14g_new_residual_accept          | control_charge_only                   |                 -0.00116343 |                          -0.00504877  |                            -0.00431523  |            -0.00205798  |
| s14g_new_residual_accept          | ML_gradient_boosted_trees             |                 -0.00583439 |                          -0.0142678   |                             0.0645628   |            -0.0466172   |
| s14g_new_residual_accept          | ML_mlp                                |                 -0.00960839 |                          -0.0200526   |                             0.0795397   |            -0.0476295   |
| s14g_new_residual_accept          | ML_ridge_waveform                     |                 -0.0402701  |                          -0.124577    |                            -0.119005    |             0.0103527   |
| s14g_new_residual_accept          | NN_1d_cnn                             |                 -0.19483    |                          -0.526092    |                            -0.268529    |             0.232235    |
| s14g_new_residual_accept          | control_depth_only                    |                 -0.258588   |                          -0.514689    |                            -0.296323    |             0.216869    |
| s14g_new_residual_accept          | control_run_family_only               |                 -0.45681    |                          -0.669083    |                            -0.419603    |             0.208269    |
| s14g_new_residual_accept          | control_shuffled_label_hgb            |                 -0.491815   |                          -0.684244    |                            -0.423248    |             0.208191    |
| s14g_new_residual_accept          | control_action_only                   |                 -0.687204   |                          -0.716254    |                            -0.444104    |             0.00277712  |
| s14g_traditional_accept           | NN_action_gated_residual_ensemble_new |                  0.0152872  |                           0.0400331   |                             0.231365    |            -0.0447452   |
| s14g_traditional_accept           | control_charge_only                   |                 -0.0010744  |                          -0.00531364  |                            -0.00336532  |            -0.000686353 |
| s14g_traditional_accept           | ML_gradient_boosted_trees             |                 -0.00518541 |                          -0.0111726   |                             0.0744373   |            -0.0466703   |
| s14g_traditional_accept           | ML_mlp                                |                 -0.00889179 |                          -0.0161612   |                             0.0790624   |            -0.0469593   |
| s14g_traditional_accept           | ML_ridge_waveform                     |                 -0.037472   |                          -0.125962    |                            -0.121924    |             0.0110053   |
| s14g_traditional_accept           | NN_1d_cnn                             |                 -0.189456   |                          -0.528378    |                            -0.292715    |             0.243099    |
| s14g_traditional_accept           | control_depth_only                    |                 -0.254936   |                          -0.515113    |                            -0.321566    |             0.224648    |
| s14g_traditional_accept           | control_run_family_only               |                 -0.462426   |                          -0.681511    |                            -0.452283    |             0.221746    |
| s14g_traditional_accept           | control_shuffled_label_hgb            |                 -0.483483   |                          -0.690793    |                            -0.45172     |             0.221747    |
| s14g_traditional_accept           | control_action_only                   |                 -0.701149   |                          -0.738385    |                            -0.476707    |             0.00542988  |
| s14g_traditional_and_p07j_correct | ML_ridge_waveform                     |                nan          |                         nan           |                           nan           |           nan           |
| s14g_traditional_and_p07j_correct | ML_gradient_boosted_trees             |                nan          |                         nan           |                           nan           |           nan           |
| s14g_traditional_and_p07j_correct | ML_mlp                                |                nan          |                         nan           |                           nan           |           nan           |
| s14g_traditional_and_p07j_correct | NN_1d_cnn                             |                nan          |                         nan           |                           nan           |           nan           |
| s14g_traditional_and_p07j_correct | NN_action_gated_residual_ensemble_new |                nan          |                         nan           |                           nan           |           nan           |
| s14g_traditional_and_p07j_correct | control_charge_only                   |                nan          |                         nan           |                           nan           |           nan           |
| s14g_traditional_and_p07j_correct | control_depth_only                    |                nan          |                         nan           |                           nan           |           nan           |
| s14g_traditional_and_p07j_correct | control_action_only                   |                nan          |                         nan           |                           nan           |           nan           |
| s14g_traditional_and_p07j_correct | control_run_family_only               |                nan          |                         nan           |                           nan           |           nan           |
| s14g_traditional_and_p07j_correct | control_shuffled_label_hgb            |                nan          |                         nan           |                           nan           |           nan           |

## 9. Systematics And Caveats

- The positive label is a duplicate-readout range-energy residual.  It is useful for
  stress-testing stability but is not a particle truth label.
- S14g covers analysis runs; missing calibration-run merges are treated as rejected
  for S14g action masks, which makes support-loss estimates conservative.
- P07j correction rows are a saturation-candidate subset.  A zero in the P07j mask
  means no traditional correction action was accepted, not necessarily a physics veto.
- P04s was not available as a tracked artifact.  The result should not be read as a
  final combined P07j/S14g/P04s deployment gate.
- Charge-only and forbidden weak-label relatives can score highly because the weak label
  itself is charge/depth-derived.  The action-only and run-family controls are the key
  guardrails against action-band manufactured separation.

## 10. Verdict

The best pre-action weak-label score is NN_action_gated_residual_ensemble_new (AUC 0.9955), while the traditional calibrated charge/depth baseline has AUC 0.9848.  The action-only control has AUC 0.5682; therefore action bands alone do not explain the primary weak-label separation.  However S14g/P07j masks induce non-negligible support and composition shifts, and the label is charge/depth-derived, so the result remains a stability diagnostic rather than a PID adoption claim.

Proposed follow-up ticket:

P08e truth-anchored PID action-band closure -- repeat the P08d action-mask stability
test on an externally anchored PID/truth subset or beamline-calibrated proxy, including
the missing P04s dropout-phase action band, before any PID adoption claim.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p08d_1781054026_1934_7d3f4015_pid_action_band_stability.py --config configs/p08d_1781054026_1934_7d3f4015_pid_action_band_stability.json
```

Artifacts: `result.json`, `manifest.json`, `reproduction_match_table.csv`,
`calibrated_label_support.csv`, `weak_label_counts_by_run.csv`,
`action_source_audit.csv`, `action_mask_composition.csv`, `scoreboard_by_mask.csv`,
`ml_minus_traditional.csv`, `fold_summary.csv`, and `oof_pid_scores.csv.gz`.
