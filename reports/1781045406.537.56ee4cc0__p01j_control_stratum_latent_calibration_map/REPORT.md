# P01j: control-stratum latent calibration map

**Study ID:** P01j  
**Ticket:** `1781045406.537.56ee4cc0`  
**Author:** `testbeam-laptop-4`  
**Date:** 2026-06-11  
**Depends on:** S00/S01/P01b/P01e/P01h/P01i  
**Git commit:** `7665c39cbd9fd4a336934f6f1ee2182f8df80088`  
**Config:** `configs/p01j_1781045406_537_56ee4cc0_control_stratum_latent_calibration_map.json`

## 0. Question
Does the P01b latent lift for manual morphology flags and peak groups survive identical run, topology, amplitude, and stave controls, or is it residual domain leakage? The atomic steps are: reproduce the raw ROOT selected-pulse count, join the frozen latent artifact by raw keys, freeze the control strata, compare a strong traditional hand/PCA/q-template ridge baseline to several ML/NN probes, estimate run-block confidence intervals, and map timing/charge-risk deltas for the predicted non-nominal regions.

## 1. Reproduction
Raw B-stack ROOT was scanned from `data/root/root` before modelling. The selection is the standing S00/P01 gate: B2/B4/B6/B8 even channels, median baseline over samples 0--3, and baseline-subtracted maximum amplitude greater than 1000 ADC.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| Selected B-stave pulses | 640737 | 640737 | 0 | 0 | True |
| P01b latent rows | 640737 | 640737 | 0 | 0 | True |

The P01b artifact SHA-256 is `9dcffdb123a8c091781771ba9f1c6667a65af91cfabbfb64328427dfd7f865be` and its key hash is `605aa0fb0161573bf4afd95df232307823a4e7fd50a580455b0d53ee81121193`. The raw recount key hash is `605aa0fb0161573bf4afd95df232307823a4e7fd50a580455b0d53ee81121193`.

## 2. Traditional Method
The traditional comparator is a train-only ridge classifier on non-neural pulse-shape variables. For pulse \(i\), the feature vector is

`x_i = [h_i, p_i, q_i]`,

where \(h_i\) contains peak sample, normalized area, early/late/tail fractions, width20, width50, maximum down step, and asymmetry; \(p_i\) is a six-component PCA summary fit only on train-run normalized waveforms; and \(q_i\) contains q-template RMSE, autoencoder RMSE, and q-template peak sample from the frozen S01 table. The classifier minimizes

`||Y - X beta||_2^2 + alpha ||beta||_2^2`, with `alpha = 1.0`,

using class-balanced ridge classification. The controls-only comparator uses log amplitude, topology multiplicity, topology mask, amplitude bin, stave, and run-family indicators. It is not allowed to see waveform shape or latent variables.

## 3. ML And NN Methods
Every method uses the same held-out runs `42, 57, 64, 65` and the same capped control-stratum sample. The benchmark includes:

| Method | Input | Estimator |
|---|---|---|
| `latent_ridge` | P01b latent coordinates | class-balanced ridge classifier |
| `latent_gbt` | P01b latent coordinates | histogram gradient-boosted trees |
| `latent_mlp` | P01b latent coordinates | two-layer MLP |
| `waveform_1d_cnn` | normalized raw 18-sample waveform | small 1D convolutional net |
| `stratum_gated_fusion_new_arch` | hand/PCA/q-template, latent, and controls | gated fusion neural net |
| `latent_stratum_permuted_ridge` | within-stratum permuted P01b latents | negative-control ridge |

For a K-class task, balanced accuracy is the mean class recall, macro-F1 is the unweighted class-F1 mean, multiclass Brier is the mean squared probability error across classes, and ECE is a 10-bin expected calibration error from maximum predicted probability. Ridge decision scores are softmax-normalized for diagnostic Brier/ECE; they are not externally calibrated probabilities.

Target support:

| target      |   train_rows |   heldout_rows | heldout_distribution                                                                                     |
|:------------|-------------:|---------------:|:---------------------------------------------------------------------------------------------------------|
| manual_flag |        33784 |           5126 | {"early_low_area": 192, "early_peak": 47, "large_negative_step": 100, "late_peak": 792, "nominal": 3995} |
| peak_group  |        33784 |           5126 | {"early_0_3": 231, "late_10_17": 1085, "nominal_6_9": 3117, "prepeak_4_5": 693}                          |

## 4. Head-To-Head Benchmark
Primary target `manual_flag`:

| method                               |   balanced_accuracy |   balanced_accuracy_ci_low |   balanced_accuracy_ci_high |   macro_f1 |   brier |    ece |   lift_vs_controls |   lift_ci_low |   lift_ci_high |
|:-------------------------------------|--------------------:|---------------------------:|----------------------------:|-----------:|--------:|-------:|-------------------:|--------------:|---------------:|
| latent_gbt                           |              0.9598 |                     0.9412 |                      0.972  |     0.9231 |  0.0349 | 0.0079 |             0.4805 |        0.4378 |         0.5458 |
| latent_mlp                           |              0.923  |                     0.8986 |                      0.9523 |     0.8969 |  0.0549 | 0.0124 |             0.4437 |        0.3902 |         0.5074 |
| traditional_hand_pca_qtemplate_ridge |              0.9171 |                     0.8837 |                      0.9384 |     0.7552 |  0.2971 | 0.3642 |             0.4378 |        0.3975 |         0.4735 |
| stratum_gated_fusion_new_arch        |              0.9118 |                     0.8954 |                      0.9342 |     0.8592 |  0.0518 | 0.0026 |             0.4325 |        0.3805 |         0.5117 |
| latent_ridge                         |              0.7561 |                     0.7346 |                      0.7865 |     0.7366 |  0.4898 | 0.5485 |             0.2768 |        0.2327 |         0.3563 |
| waveform_1d_cnn                      |              0.5699 |                     0.5332 |                      0.6101 |     0.6199 |  0.2438 | 0.2275 |             0.0906 |        0.048  |         0.1834 |
| controls_only_ridge                  |              0.4793 |                     0.4089 |                      0.5274 |     0.2384 |  0.7676 | 0.0585 |             0      |        0      |         0      |
| latent_stratum_permuted_ridge        |              0.3344 |                     0.2722 |                      0.3572 |     0.2686 |  0.7805 | 0.2951 |            -0.1449 |       -0.1965 |        -0.1009 |

Method-level lift over controls-only:

| method                               |   mean_balanced_accuracy |   mean_macro_f1 |   mean_lift_vs_controls |   mean_brier |   mean_ece |
|:-------------------------------------|-------------------------:|----------------:|------------------------:|-------------:|-----------:|
| latent_gbt                           |                   0.9583 |          0.9273 |                  0.4862 |       0.0591 |     0.0072 |
| stratum_gated_fusion_new_arch        |                   0.9449 |          0.9137 |                  0.4728 |       0.0427 |     0.0114 |
| latent_mlp                           |                   0.9383 |          0.914  |                  0.4662 |       0.0766 |     0.0213 |
| traditional_hand_pca_qtemplate_ridge |                   0.9287 |          0.8292 |                  0.4567 |       0.2839 |     0.3501 |
| latent_ridge                         |                   0.7603 |          0.7386 |                  0.2882 |       0.4813 |     0.4829 |
| waveform_1d_cnn                      |                   0.6118 |          0.6482 |                  0.1397 |       0.3384 |     0.2557 |
| controls_only_ridge                  |                   0.4721 |          0.2728 |                  0      |       0.746  |     0.0563 |
| latent_stratum_permuted_ridge        |                   0.3596 |          0.3151 |                 -0.1125 |       0.7549 |     0.2466 |

Pairwise deltas against the strong traditional baseline:

| method                        | target      |   delta_vs_traditional |   ci_low |   ci_high |
|:------------------------------|:------------|-----------------------:|---------:|----------:|
| controls_only_ridge           | manual_flag |                -0.4378 |  -0.4735 |   -0.4062 |
| latent_ridge                  | manual_flag |                -0.161  |  -0.1942 |   -0.1022 |
| latent_gbt                    | manual_flag |                 0.0427 |   0.0222 |    0.0702 |
| latent_mlp                    | manual_flag |                 0.0059 |  -0.019  |    0.0334 |
| latent_stratum_permuted_ridge | manual_flag |                -0.5827 |  -0.6174 |   -0.5662 |
| waveform_1d_cnn               | manual_flag |                -0.3472 |  -0.4051 |   -0.259  |
| stratum_gated_fusion_new_arch | manual_flag |                -0.0053 |  -0.033  |    0.0345 |
| controls_only_ridge           | peak_group  |                -0.4755 |  -0.5497 |   -0.422  |
| latent_ridge                  | peak_group  |                -0.1758 |  -0.1905 |   -0.1648 |
| latent_gbt                    | peak_group  |                 0.0165 |   0.0064 |    0.0308 |
| latent_mlp                    | peak_group  |                 0.0132 |   0.008  |    0.0178 |
| latent_stratum_permuted_ridge | peak_group  |                -0.5556 |  -0.5858 |   -0.5312 |
| waveform_1d_cnn               | peak_group  |                -0.2867 |  -0.2979 |   -0.2758 |
| stratum_gated_fusion_new_arch | peak_group  |                 0.0376 |   0.0314 |    0.05   |

Winner: **latent_gbt** with mean lift over controls-only `0.4862` and mean balanced accuracy `0.9583`. The strong traditional baseline has mean lift `0.4567` and mean balanced accuracy `0.9287`. The winner's score delta versus traditional is `0.0296`.

## 4.1 Timing And Charge Risk Deltas
The risk map is descriptive. It asks whether the model-predicted non-nominal region has different downstream timing residuals or pulse charge proxy than the model-predicted nominal region on the same held-out rows. Timing is median absolute pair residual from the frozen timing table when available; charge is `log10(amplitude_adc)`.

| method                               | target      |   timing_risk_delta_ns |   timing_ci_low |   timing_ci_high |   charge_log10_delta |   charge_ci_low |   charge_ci_high |
|:-------------------------------------|:------------|-----------------------:|----------------:|-----------------:|---------------------:|----------------:|-----------------:|
| controls_only_ridge                  | manual_flag |                 0.4347 |         -0.0471 |           0.9596 |              -0.2003 |         -0.2291 |          -0.1737 |
| traditional_hand_pca_qtemplate_ridge | manual_flag |                -0.806  |         -1.4128 |           0.1698 |              -0.0884 |         -0.1286 |          -0.0619 |
| latent_ridge                         | manual_flag |                -0.5763 |         -0.9817 |           0.1137 |              -0.1119 |         -0.1561 |          -0.0856 |
| latent_gbt                           | manual_flag |                -0.0796 |         -0.3638 |           0.245  |              -0.1072 |         -0.1458 |          -0.0884 |
| latent_mlp                           | manual_flag |                -0.3969 |         -0.7351 |           0.209  |              -0.1074 |         -0.1434 |          -0.0928 |
| latent_stratum_permuted_ridge        | manual_flag |                 0.215  |         -0.0627 |           0.4481 |              -0.0437 |         -0.0607 |          -0.0227 |
| waveform_1d_cnn                      | manual_flag |                -0.6688 |         -1.2558 |           0.0108 |              -0.1637 |         -0.1957 |          -0.142  |
| stratum_gated_fusion_new_arch        | manual_flag |                -0.2216 |         -0.4447 |           0.1905 |              -0.1073 |         -0.1452 |          -0.0878 |
| controls_only_ridge                  | peak_group  |                -0.0637 |         -0.5683 |           0.1287 |              -0.0715 |         -0.1167 |          -0.0535 |
| traditional_hand_pca_qtemplate_ridge | peak_group  |                -0.8466 |         -1.0683 |          -0.3182 |              -0.0301 |         -0.0529 |          -0.0164 |
| latent_ridge                         | peak_group  |                -0.5379 |         -0.7449 |           0.0762 |              -0.0702 |         -0.1004 |          -0.0509 |
| latent_gbt                           | peak_group  |                -0.766  |         -0.982  |          -0.2014 |              -0.0413 |         -0.0805 |          -0.0175 |
| latent_mlp                           | peak_group  |                -0.7684 |         -0.9554 |          -0.2497 |              -0.0436 |         -0.0824 |          -0.0197 |
| latent_stratum_permuted_ridge        | peak_group  |                 0.1325 |         -0.1039 |           0.4022 |               0.01   |         -0.0216 |           0.0332 |
| waveform_1d_cnn                      | peak_group  |                -0.6617 |         -1.1584 |           0.1094 |              -0.1257 |         -0.1685 |          -0.1006 |
| stratum_gated_fusion_new_arch        | peak_group  |                -0.6964 |         -0.916  |          -0.1694 |              -0.0465 |         -0.0783 |          -0.0265 |

## 5. Falsification
Pre-registration comes from the ticket: latent morphology must beat controls-only and train-label/permuted-latent controls for manual flags and peak groups under run-heldout splitting. The explicit falsifier is a zero or negative run-block lift over controls-only, or a lift no better than the within-stratum permuted latent control. The method search contains eight named methods, so the result is treated as a descriptive benchmark map rather than an inferential discovery claim; no p-value is promoted.

Observed falsification status: controls-only is not the winner; the within-stratum permuted latent ridge remains below the unpermuted latent ridge/fusion methods; label-shuffle sentinels are low. The bootstrap intervals are run-block intervals over only four held-out runs, so lack of overlap should not be overread.

## 6. Threats To Validity
**Benchmark/selection.** The traditional baseline is strong: it receives hand-shape variables, train-fit PCA, and q-template summaries. The new architecture is only one predeclared gated fusion net, not a post-hoc architecture sweep.

**Data leakage.** Splitting is by run. PCA, model fitting, and label thresholds use train-run information only where fitted. Exact run identifiers are not classifier features; exact run enters only the permutation strata and bootstrap blocks. P01b latents are checked against raw `(run,event_index,stave_index)` order before use.

**Metric misuse.** Balanced accuracy and macro-F1 are used because manual morphology labels are imbalanced. Brier/ECE are calibration diagnostics, not truth-probability claims. The downstream timing/charge deltas are risk maps, not causal timing corrections.

**Post-hoc selection.** The targets, held-out runs, method families, bootstrap unit, and winner metric are fixed in the config. The report names the point-estimate winner but recommends freezing it before any production use.

## 7. Provenance Manifest
`manifest.json` records input file hashes, the command, git commit, platform, random seed, and output hashes. `input_sha256.csv` pins the raw ROOT files, P01b latent artifact, q-template table, timing residual table, config, and script.

## 8. Findings And Next Steps
The control-stratum result supports a real waveform-morphology component in P01b latents: unpermuted latent and fusion methods outperform controls-only and the within-stratum permuted latent negative control. The safest interpretation is not that the latent is a truth label, but that it carries useful pulse-shape information after coarse run/topology/amplitude/stave controls.

Queued follow-up: `P01k frozen control-stratum morphology transfer: freeze the P01j winner and test pair-timing sigma68 plus amplitude-bias deltas on untouched run-family folds`. Expected information gain: it freezes the P01j winner and tests whether the same control-stratum morphology map predicts independent timing and charge-bias deltas on untouched run-family folds.

## 9. Reproducibility
Regenerate with:

```bash
MPLCONFIGDIR=reports/1781045406.537.56ee4cc0__p01j_control_stratum_latent_calibration_map/mplconfig /home/billy/anaconda3/bin/python scripts/p01j_1781045406_537_56ee4cc0_control_stratum_latent_calibration_map.py --config configs/p01j_1781045406_537_56ee4cc0_control_stratum_latent_calibration_map.json
```

Artifacts include `benchmark_metrics.csv`, `method_summary.csv`, `method_delta_bootstrap.csv`, `risk_delta_metrics.csv`, `target_support.csv`, `leakage_checks.csv`, `reproduction_match_table.csv`, `input_sha256.csv`, two PNG figures, `result.json`, and `manifest.json`.
