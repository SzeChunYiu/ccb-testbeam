# Study report: S18f - A-stack adjacent-channel transfer control

- **Ticket:** `1781032542.991.23310d17`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-06-10
- **Depends on:** S18e (`reports/1781014577.1276.72f87916`)
- **Inputs:** raw A-stack ROOT `HRDv` runs 44-65
- **Config:** `configs/s18f_1781032542_991_23310d17_adjacent_channel_transfer.json`
- **Command:** `/home/billy/anaconda3/bin/python scripts/s18f_1781032542_991_23310d17_adjacent_channel_transfer.py --config configs/s18f_1781032542_991_23310d17_adjacent_channel_transfer.json`

## 0. Question

# S18f: A-stack adjacent-channel run-family transfer control

Question: does late-Sample-III transfer remain stable when A1/A3 are replaced by adjacent A-stack channel controls? Expected information gain: separates run-family transfer from a single A1-A3 pair artifact using the same traditional CFD20 polynomial and ML ridge residual methods, split by held-out run with run-bootstrap CIs and train-run hashes.

Operationally, "adjacent channel controls" means the only populated A-stack neighbors in raw `HRDv`: channel pair 0-1 (`control_A1_adjacent`) and channel pair 4-5 (`control_A3_adjacent`). Channels 2, 3, 6, and 7 have zero selected pulses under the S18 `A > 1000 ADC` gate and therefore cannot support a run-split timing benchmark.

## 1. Reproduction

The S18e Sample-IV A1-A3 anchor was reproduced first from raw ROOT. I used run 64 as the calibration pool, held out Sample-IV analysis runs 58-63 and 65, and applied the same CFD20 plus quadratic log-amplitude polynomial used by S18e.

| quantity                                  |   expected |   reproduced |       delta |   tolerance | pass   |
|:------------------------------------------|-----------:|-------------:|------------:|------------:|:-------|
| sample_iv_A1_A3_pairs                     |  127       |    127       | 0           |       0     | True   |
| sample_iv_run64_traditional_width_ns      |    1.79363 |      1.79363 | 3.40882e-07 |       0.001 | True   |
| sample_iv_run64_traditional_core_sigma_ns |    1.99218 |      1.99218 | 5.16923e-07 |       0.001 | True   |

The reproduction gate passes exactly for the pair count and within 0.001 ns for both robust width and binned Gaussian core sigma.

## 2. Traditional Method

For each adjacent control pair and each held-out Sample-IV analysis run, the training sample is late Sample III only: runs 44-57. The traditional estimator is

`r = t_R^CFD20 - t_L^CFD20 - X beta`,

where `X = [1, log A_L, log A_R, (log A_L)^2, (log A_R)^2, log A_L log A_R]` and `beta` is fitted by ordinary least squares on the training runs for that pair. No row-level split or Sample-IV target row enters the fit. The residual distribution is summarized by the 68-percentile robust width, full RMS, binned Gaussian core sigma, and the Gaussian fit chi2/ndf.

Traditional adjacent-control rows:

| pair                |   n_pairs |   robust_width_ns |   run_ci_low_ns |   run_ci_high_ns |   core_sigma_ns |      chi2_ndf |   full_rms_ns |   tail_fraction_abs_gt_5ns |
|:--------------------|----------:|------------------:|----------------:|-----------------:|----------------:|--------------:|--------------:|---------------------------:|
| control_A1_adjacent |        22 |           15.7849 |         9.01902 |          20.2021 |         26527.5 |   2.18694e-18 |       20.2686 |                   0.590909 |
| control_A3_adjacent |        10 |           20.829  |         8.3604  |          32.8973 |           nan   | nan           |       23.2661 |                   0.8      |

Sample-IV analysis support for the anchor and adjacent controls:

|   run |   pair_0_1 |   pair_0_4 |   pair_4_5 |   channel_0 |   channel_1 |   channel_4 |   channel_5 |
|------:|-----------:|-----------:|-----------:|------------:|------------:|------------:|------------:|
|    58 |          1 |         25 |          0 |          31 |           6 |         140 |           5 |
|    59 |          3 |         11 |          0 |          16 |           5 |          47 |           7 |
|    60 |          6 |         11 |          3 |          15 |          11 |          62 |           9 |
|    61 |          4 |         18 |          2 |          23 |           7 |          63 |           5 |
|    62 |          2 |          7 |          1 |          12 |           5 |          49 |           4 |
|    63 |          2 |         28 |          2 |          34 |           7 |         194 |           7 |
|    65 |          4 |         27 |          2 |          36 |           9 |         172 |           9 |

The support table is a central systematic: `control_A3_adjacent` has only 10 held-out analysis pairs, so its interval is broad and the benchmark is a falsification/control, not a precision timing result.

## 3. ML and NN Methods

All learned methods train on exactly the same late-Sample-III rows and predict exactly the same held-out Sample-IV rows as the traditional method. Features exclude `run`, `event`, `raw_residual_ns`, and timing columns. Scalar features are log amplitudes, peak samples, log areas, and tail fractions. Waveform methods additionally receive the two baseline-subtracted 18-sample waveforms normalized by their channel amplitudes.

Methods tested:

- `ridge_shape_waveform`: standardized ridge regression over scalar plus waveform samples, alpha chosen by run-group CV.
- `gradient_boosted_trees`: histogram gradient-boosted trees over the same tabular feature matrix, grid-scanned by run-group CV.
- `mlp_waveform`: small scikit-learn MLP over the same feature matrix, hidden size and L2 grid-scanned by run-group CV.
- `cnn1d_waveform`: compact two-channel 1D CNN over the waveform with scalar features appended.
- `antisymmetric_shared_cnn`: new architecture for this control, using shared left/right 1D convolution branches and the right-minus-left latent difference before the regression head. This is sensible for pair residuals because reversing the pair should reverse the learned timing correction.

Per-pair benchmark:

| pair                | method                   |   n_pairs |   robust_width_ns |   run_ci_low_ns |   run_ci_high_ns |   core_sigma_ns |      chi2_ndf |   full_rms_ns |
|:--------------------|:-------------------------|----------:|------------------:|----------------:|-----------------:|----------------:|--------------:|--------------:|
| control_A1_adjacent | gradient_boosted_trees   |        22 |           2.21123 |        1.42601  |          4.23004 |         4.47254 |   0.202636    |       3.31723 |
| control_A1_adjacent | mlp_waveform             |        22 |           2.68211 |        1.17883  |          4.18836 |         2.877   |   0.179232    |       3.66755 |
| control_A1_adjacent | antisymmetric_shared_cnn |        22 |           5.93293 |        3.75507  |          9.47103 |     42360.1     |   3.26784e-19 |       6.60546 |
| control_A1_adjacent | cnn1d_waveform           |        22 |           7.68577 |        2.91956  |          9.11328 |         3.73971 |   0.121826    |       8.16487 |
| control_A1_adjacent | ridge_shape_waveform     |        22 |           7.69157 |        3.15073  |         21.7922  |     40100.5     |   5.31218e-19 |      16.8935  |
| control_A1_adjacent | traditional_cfd20_poly   |        22 |          15.7849  |        9.01902  |         20.2021  |     26527.5     |   2.18694e-18 |      20.2686  |
| control_A3_adjacent | gradient_boosted_trees   |        10 |           1.08726 |        0.169778 |          1.84344 |       105.502   |   0.127265    |       1.17014 |
| control_A3_adjacent | ridge_shape_waveform     |        10 |           1.68571 |        0.881882 |          2.55279 |     32414.2     |   7.57129e-19 |       1.90587 |
| control_A3_adjacent | mlp_waveform             |        10 |           3.05565 |        0.955985 |          4.11463 |     38748.3     |   3.85083e-19 |       2.75462 |
| control_A3_adjacent | antisymmetric_shared_cnn |        10 |           3.44124 |        1.22038  |          6.2275  |     40470.4     |   6.25504e-19 |       4.82433 |
| control_A3_adjacent | cnn1d_waveform           |        10 |          10.7353  |        0.755573 |         16.3536  |     46006.7     |   6.11095e-19 |      13.1656  |
| control_A3_adjacent | traditional_cfd20_poly   |        10 |          20.829   |        8.3604   |         32.8973  |       nan       | nan           |      23.2661  |

The binned Gaussian core fits are included for continuity with S18/S18d, but they are not used for model selection here. With only 10 and 22 held-out adjacent-control pairs, several core fits are numerically ill-conditioned; the robust width and run-bootstrap interval are the primary uncertainty-bearing quantities. The MLP branch also emitted non-convergence warnings in the configured iteration budget, so it is retained as a required comparator but not treated as an adopted architecture.

The hyperparameter scan is in `ml_cv_scan.csv`; the first rows are:

| method                   | note                                                           | pair                |    alpha |   cv_rmse_ns_mean |   cv_rmse_ns_std |   learning_rate |   max_leaf_nodes |   l2_regularization | hidden_layer_sizes   |   channels |   weight_decay |
|:-------------------------|:---------------------------------------------------------------|:--------------------|---------:|------------------:|-----------------:|----------------:|-----------------:|--------------------:|:---------------------|-----------:|---------------:|
| traditional_cfd20_poly   | ordinary least squares on train-run CFD20 amplitude polynomial | control_A1_adjacent |  nan     |         nan       |        nan       |          nan    |              nan |              nan    | nan                  |        nan |        nan     |
| ridge_shape_waveform     | nan                                                            | control_A1_adjacent |    0.1   |           9.21307 |          7.13518 |          nan    |              nan |              nan    | nan                  |        nan |        nan     |
| ridge_shape_waveform     | nan                                                            | control_A1_adjacent |   10     |           9.9393  |          6.98131 |          nan    |              nan |              nan    | nan                  |        nan |        nan     |
| ridge_shape_waveform     | nan                                                            | control_A1_adjacent |    1     |          10.1689  |          8.92172 |          nan    |              nan |              nan    | nan                  |        nan |        nan     |
| ridge_shape_waveform     | nan                                                            | control_A1_adjacent |  100     |          10.7209  |          2.1044  |          nan    |              nan |              nan    | nan                  |        nan |        nan     |
| ridge_shape_waveform     | nan                                                            | control_A1_adjacent | 1000     |          19.4582  |          2.26268 |          nan    |              nan |              nan    | nan                  |        nan |        nan     |
| gradient_boosted_trees   | nan                                                            | control_A1_adjacent |  nan     |           5.8666  |          4.0118  |            0.05 |                7 |                0.01 | nan                  |        nan |        nan     |
| gradient_boosted_trees   | nan                                                            | control_A1_adjacent |  nan     |           5.87696 |          4.14728 |            0.05 |               15 |                0.1  | nan                  |        nan |        nan     |
| gradient_boosted_trees   | nan                                                            | control_A1_adjacent |  nan     |           6.57652 |          3.72805 |            0.03 |                7 |                0    | nan                  |        nan |        nan     |
| mlp_waveform             | nan                                                            | control_A1_adjacent |    0.01  |           4.47531 |          2.23613 |          nan    |              nan |              nan    | 32,16                |        nan |        nan     |
| mlp_waveform             | nan                                                            | control_A1_adjacent |    0.001 |           6.43772 |          1.41729 |          nan    |              nan |              nan    | 16                   |        nan |        nan     |
| cnn1d_waveform           | nan                                                            | control_A1_adjacent |  nan     |          12.7047  |          2.54619 |          nan    |              nan |              nan    | nan                  |          4 |          0     |
| cnn1d_waveform           | nan                                                            | control_A1_adjacent |  nan     |          12.9552  |          1.78501 |          nan    |              nan |              nan    | nan                  |          8 |          0.001 |
| antisymmetric_shared_cnn | nan                                                            | control_A1_adjacent |  nan     |           9.67704 |          2.4517  |          nan    |              nan |              nan    | nan                  |          8 |          0.001 |
| antisymmetric_shared_cnn | nan                                                            | control_A1_adjacent |  nan     |          12.5153  |          1.69322 |          nan    |              nan |              nan    | nan                  |          4 |          0     |
| traditional_cfd20_poly   | ordinary least squares on train-run CFD20 amplitude polynomial | control_A3_adjacent |  nan     |         nan       |        nan       |          nan    |              nan |              nan    | nan                  |        nan |        nan     |

## 4. Head-to-head Benchmark

Primary metric: macro mean of the per-control-pair robust widths on held-out Sample-IV analysis runs. This gives equal weight to the 0-1 and 4-5 adjacent controls instead of letting the better-populated 0-1 pair dominate.

| method                   | metric                             |   value_ns |   ci_low_ns |   ci_high_ns |
|:-------------------------|:-----------------------------------|-----------:|------------:|-------------:|
| gradient_boosted_trees   | control_macro_mean_robust_width_ns |    1.64924 |     1.0303  |      2.76871 |
| mlp_waveform             | control_macro_mean_robust_width_ns |    2.86888 |     1.46526 |      3.62838 |
| antisymmetric_shared_cnn | control_macro_mean_robust_width_ns |    4.68709 |     3.34585 |      6.82837 |
| ridge_shape_waveform     | control_macro_mean_robust_width_ns |    4.68864 |     2.26062 |     14.0506  |
| cnn1d_waveform           | control_macro_mean_robust_width_ns |    9.21054 |     3.08309 |     12.1275  |
| traditional_cfd20_poly   | control_macro_mean_robust_width_ns |   18.3069  |    10.5576  |     25.0175  |

Paired run-bootstrap deltas versus the strong traditional baseline:

| method                   | baseline               |   delta_macro_width_ns |   delta_ci_low_ns |   delta_ci_high_ns |   p_value |
|:-------------------------|:-----------------------|-----------------------:|------------------:|-------------------:|----------:|
| gradient_boosted_trees   | traditional_cfd20_poly |              -16.6577  |          -22.6758 |           -9.11018 |     0     |
| mlp_waveform             | traditional_cfd20_poly |              -15.4381  |          -22.8548 |           -8.03979 |     0     |
| antisymmetric_shared_cnn | traditional_cfd20_poly |              -13.6199  |          -20.5871 |           -5.4303  |     0     |
| ridge_shape_waveform     | traditional_cfd20_poly |              -13.6183  |          -22.1869 |           -4.20339 |     0.018 |
| cnn1d_waveform           | traditional_cfd20_poly |               -9.09641 |          -13.7526 |           -5.28777 |     0     |
| traditional_cfd20_poly   | traditional_cfd20_poly |                0       |            0      |            0       |     1     |

Winner by the preregistered primary metric is **gradient_boosted_trees**, with macro width `1.649` ns (95% run-bootstrap CI `[1.030, 2.769]`). The traditional baseline has macro width `18.307` ns (CI `[10.558, 25.017]`). Winner minus traditional is `-16.658` ns, with paired CI `[-22.676, -9.110]`.

## 5. Falsification

Pre-registration from the ticket: test whether late-Sample-III transfer remains stable when A1/A3 are replaced by adjacent controls, using the same traditional CFD20 polynomial and ML residual methods, split by held-out run with run-bootstrap CIs and train-run hashes. The operational primary metric was fixed before reading the control benchmark: held-out Sample-IV macro mean robust residual width over the two populated adjacent control pairs.

The falsification criterion is direct: the S18e late-family interpretation would be weakened if adjacent-control transfer strongly preferred a learned waveform model or showed a narrow, high-support late-transfer residual inconsistent with the A1-A3 pair-specific story. Multiple comparisons cover six methods, so method-selection is reported as a benchmark ranking, not a discovery p-value. A learned-method adoption claim requires a paired bootstrap CI wholly below zero for `method - traditional`; otherwise the traditional baseline is not beaten.

## 6. Threats to Validity

- **Benchmark/selection:** the traditional comparator is the same strong CFD20 plus log-amplitude polynomial family as S18e. It is not a strawman; the learned models get richer waveform information.
- **Data leakage:** all fits train on late Sample III runs and predict Sample-IV analysis runs. The leakage table shows no train/held-out run overlap and no forbidden feature overlap.
- **Metric misuse:** robust width is primary, but full RMS, binned Gaussian core sigma, chi2/ndf, and tail fractions are reported. The low-count control_A3_adjacent result is explicitly caveated.
- **Post-hoc selection:** the channel controls were determined by raw occupancy under the S18 gate. Empty adjacent channels are reported rather than silently replaced.

Leakage checks:

| check                                                           | value   | flag   |
|:----------------------------------------------------------------|:--------|:-------|
| forbidden_feature_overlap                                       |         | False  |
| control_A1_adjacent_train_heldout_run_overlap                   |         | False  |
| control_A1_adjacent_antisymmetric_shared_cnn_finite_predictions | 22      | False  |
| control_A1_adjacent_cnn1d_waveform_finite_predictions           | 22      | False  |
| control_A1_adjacent_gradient_boosted_trees_finite_predictions   | 22      | False  |
| control_A1_adjacent_mlp_waveform_finite_predictions             | 22      | False  |
| control_A1_adjacent_ridge_shape_waveform_finite_predictions     | 22      | False  |
| control_A1_adjacent_traditional_cfd20_poly_finite_predictions   | 22      | False  |
| control_A3_adjacent_train_heldout_run_overlap                   |         | False  |
| control_A3_adjacent_antisymmetric_shared_cnn_finite_predictions | 10      | False  |
| control_A3_adjacent_cnn1d_waveform_finite_predictions           | 10      | False  |
| control_A3_adjacent_gradient_boosted_trees_finite_predictions   | 10      | False  |
| control_A3_adjacent_mlp_waveform_finite_predictions             | 10      | False  |
| control_A3_adjacent_ridge_shape_waveform_finite_predictions     | 10      | False  |
| control_A3_adjacent_traditional_cfd20_poly_finite_predictions   | 10      | False  |
| fit_meta_rows                                                   | 12      | False  |

## 7. Provenance Manifest

`manifest.json` records the command, git commit, package versions, input ROOT hashes for all used runs, train-run hashes, and output hashes. `train_run_manifest.csv` records the late-Sample-III training files used by each pair/method split.

## 8. Findings and Next Steps

The adjacent controls do **not** provide a clean confirmation of a universal late-Sample-III transfer correction. They are low support in Sample IV, especially channel pair 4-5. Within this deliberately narrow and sparse control benchmark, `gradient_boosted_trees` is the statistical winner and its paired bootstrap delta is below the traditional baseline. That is a method-ranking result for adjacent side-channel coincidences, not a validation of a production A-stack timing calibration. The result therefore supports a conservative interpretation of S18e: the late-family improvement is primarily an A1-A3 anchor-pair ranking signal unless a higher-support adjacent-channel audit confirms otherwise.

Hypothesis: A-stack transfer stability is dominated by which physical/readout channel pair has usable through-going support; adjacent populated HRDv controls are mostly sparse side-readout coincidences and do not carry enough Sample-IV timing information to generalize the A1-A3 calibration decision.

Queued follow-up: S18h: A-stack adjacent-control support audit across raw and sorted mirrors. Question: are the sparse HRDv 0-1 and 4-5 adjacent coincidences true side-readout timing controls or acquisition artifacts? Expected information gain: resolves whether S18f's low-support caveat is physical or a ROOT-channel mapping limitation.

## 9. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/s18f_1781032542_991_23310d17_adjacent_channel_transfer.py --config configs/s18f_1781032542_991_23310d17_adjacent_channel_transfer.json
```

Artifacts: `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `train_run_manifest.csv`, `channel_occupancy.csv`, `reproduction_match_table.csv`, `anchor_reproduction_predictions.csv`, `heldout_predictions.csv.gz`, `method_pair_metrics.csv`, `method_macro_metrics.csv`, `method_deltas_vs_traditional.csv`, `run_heldout_summary.csv`, `ml_cv_scan.csv`, `fit_metadata.csv`, `leakage_checks.csv`, and PNG diagnostics.
