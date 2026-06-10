# S16h: sorted ROOT baseline branches versus raw pretrigger pedestals

- **Ticket:** 1781031000.2442.5ff56e52
- **Author:** testbeam-laptop-4
- **Date:** 2026-06-10
- **Depends on:** S00, S16, S16b/S16d
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `da916840857c78ecb6bd8f4910bed3baf86ec915`
- **Config:** `configs/s16h_1781031000_2442_5ff56e52_sorted_baseline_pretrigger.json`

## 0. Question

Can the sorted ROOT reconstruction metadata, especially `hrd.baseline` and trapezoid-filter branches, recover the raw pretrigger pedestal level for selected B-stack pulses? The operational target is the raw median pedestal

\[
  y_i = \operatorname{median}\left(x_{i,0}, x_{i,1}, x_{i,2}, x_{i,3}\right),
\]

where `x` is the raw `HRDv` waveform for one selected B stave. The main scientific question is whether sorted baseline preprocessing preserves absolute pedestal shifts well enough to replace or augment the reduced raw pretrigger audit.

## 1. Reproduction from raw ROOT

The reproduction gate reruns the S00 B-stave selected-pulse count from raw `data/root/root/hrdb_run_NNNN.root`, with B2/B4/B6/B8 channels, median samples 0-3 as the seed pedestal, and the fixed `A > 1000 ADC` gate. The sorted tree is matched entry-by-entry through `raw EVT == sorted hrdEvtNo`; any mismatch aborts the script.

| quantity                                       |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses from raw HRDv    |         640737 |       640737 |       0 |           0 | True   |
| non-beam trigger entries among selected pulses |              0 |            0 |       0 |           0 | True   |
| raw EVT to sorted hrdEvtNo mismatches          |              0 |            0 |       0 |           0 | True   |

The selected-pulse count reproduces exactly, so the benchmark below is on the same raw population used by the S16 family.

## 2. Traditional method

The direct conventional estimator is the sorted branch value

\[
  \hat y_i^{(0)} = b_i = \texttt{hrd.baseline}_i.
\]

Because `hrd.baseline` is closer to a waveform minimum than to a four-sample pretrigger median, the strong traditional baseline adds a robust train-run residual correction:

\[
  \hat y_i^{\mathrm{trad}} = b_i + \operatorname{median}_{j \in C(i)}(y_j-b_j),
\]

where cells `C(i)` are defined by stave, sorted peak-time bin, and sorted `hrdMax` quartile. If a cell is absent in training, the estimator falls back to a stave median and then the global median. No held-out or calibration run contributes to these medians.

## 3. ML and NN methods

All learned models use sorted metadata features only: `hrd.baseline`, `hrdMax`, `hrdTrMax`, `hrdMaxTS`, summaries of the sorted trapezoid waveform, and stave identity. They deliberately exclude `hrd.sample`, raw pretrigger samples, raw event identifiers, target residuals, and run ID. The split is by run: training excludes held-out runs `[57, 65]` and calibration runs `[56, 64]`; a single additive residual calibration is fit on `[56, 64]`; the final benchmark is evaluated only on `[57, 65]`.

The benchmark includes the requested methods:

| Method | Model class | Notes |
|---|---|---|
| `ridge` | linear ridge regression | standardized numeric features plus stave one-hot |
| `hist_gradient_boosted_trees` | histogram gradient-boosted trees | GroupKFold CV by run; scan in `hgb_cv_scan.csv` |
| `mlp` | feed-forward neural network | two hidden layers, same tabular features |
| `one_dimensional_cnn` | 1D convolutional network | sorted trap waveform plus tabular metadata |
| `sorted_residual_net` | new architecture | convolutional residual network predicting correction to `hrd.baseline` |

The best gradient-boosted-tree CV setting was:

|   max_leaf_nodes |   learning_rate |   l2_regularization |   cv_mae_adc |   cv_mae_std_adc |
|-----------------:|----------------:|--------------------:|-------------:|-----------------:|
|           63.000 |           0.080 |               0.100 |       18.903 |            1.691 |
|           63.000 |           0.080 |               0.000 |       18.941 |            2.011 |
|           63.000 |           0.040 |               0.100 |       19.695 |            1.568 |
|           63.000 |           0.040 |               0.000 |       19.748 |            1.582 |
|           31.000 |           0.080 |               0.000 |       20.333 |            1.778 |

## 4. Head-to-head benchmark

Primary metric: held-out raw pretrigger median MAE in ADC. CIs are 95% run-block bootstraps over the held-out source runs.

| method                                 | family           |     n |   mae_adc |   mae_ci_low_adc |   mae_ci_high_adc |   bias_adc |   rmse_adc |   q05_residual_adc |   q95_residual_adc |
|:---------------------------------------|:-----------------|------:|----------:|-----------------:|------------------:|-----------:|-----------:|-------------------:|-------------------:|
| hist_gradient_boosted_trees            | ml               | 26871 |    20.366 |           15.218 |            25.218 |      0.141 |     93.107 |            -34.829 |             37.266 |
| mlp                                    | ml               | 26871 |    35.173 |           28.732 |            41.243 |     -2.091 |    126.761 |            -52.043 |             65.257 |
| sorted_residual_net                    | new_architecture | 26871 |    86.291 |           40.242 |           129.693 |    -31.844 |    412.582 |            -42.229 |             61.568 |
| one_dimensional_cnn                    | ml               | 26871 |   120.403 |           71.383 |           166.607 |    -21.125 |    469.078 |            -86.899 |            145.968 |
| ridge                                  | ml               | 26871 |   169.768 |          157.941 |           180.916 |     13.303 |    294.738 |           -365.393 |            278.137 |
| traditional_calibrated_sorted_baseline | traditional      | 26871 |   190.234 |          118.922 |           257.447 |   -121.318 |    886.897 |           -708.500 |              7.500 |
| sorted_baseline_direct                 | traditional      | 26871 |   332.962 |          202.240 |           456.171 |   -332.962 |   1226.818 |          -2389.000 |             -2.000 |

Paired deltas relative to the strong traditional calibrated baseline:

| method                      |   delta_mae_vs_traditional_adc |   ci_low_adc |   ci_high_adc |
|:----------------------------|-------------------------------:|-------------:|--------------:|
| hist_gradient_boosted_trees |                       -169.868 |     -232.229 |      -103.704 |
| mlp                         |                       -155.061 |     -216.204 |       -90.190 |
| sorted_residual_net         |                       -103.943 |     -127.753 |       -78.680 |
| one_dimensional_cnn         |                        -69.830 |      -90.840 |       -47.539 |
| ridge                       |                        -20.466 |      -76.531 |        39.019 |
| sorted_baseline_direct      |                        142.728 |       83.318 |       198.724 |

Winner: **hist_gradient_boosted_trees** with MAE `20.366` ADC, CI `[15.218, 25.218]`. The strong traditional calibrated baseline has MAE `190.234` ADC, CI `[118.922, 257.447]`. Winner minus traditional baseline is `-169.868 [-232.229, -103.704]` ADC.

By-run held-out summary:

|   run | method                                 |     n |   mae_adc |   bias_adc |   rmse_adc |
|------:|:---------------------------------------|------:|----------:|-----------:|-----------:|
|    57 | hist_gradient_boosted_trees            | 13833 |    25.218 |      0.601 |    117.585 |
|    57 | mlp                                    | 13833 |    41.243 |      1.118 |    158.944 |
|    57 | sorted_residual_net                    | 13833 |   129.693 |    -68.958 |    554.693 |
|    57 | one_dimensional_cnn                    | 13833 |   166.607 |    -64.149 |    620.920 |
|    57 | ridge                                  | 13833 |   180.916 |    -23.794 |    338.870 |
|    57 | traditional_calibrated_sorted_baseline | 13833 |   257.447 |   -190.528 |   1118.367 |
|    57 | sorted_baseline_direct                 | 13833 |   456.171 |   -456.171 |   1523.250 |
|    65 | hist_gradient_boosted_trees            | 13038 |    15.218 |     -0.346 |     56.545 |
|    65 | mlp                                    | 13038 |    28.732 |     -5.496 |     79.451 |
|    65 | sorted_residual_net                    | 13038 |    40.242 |      7.533 |    156.147 |
|    65 | one_dimensional_cnn                    | 13038 |    71.383 |     24.523 |    210.796 |
|    65 | traditional_calibrated_sorted_baseline | 13038 |   118.922 |    -47.888 |    542.334 |
|    65 | ridge                                  | 13038 |   157.941 |     52.663 |    239.172 |
|    65 | sorted_baseline_direct                 | 13038 |   202.240 |   -202.240 |    800.103 |

## 5. Falsification

- **Pre-registration:** the ticket asks for a run-split benchmark of traditional and ML/NN methods. The config fixes the primary metric as held-out raw-pretrigger-median MAE on runs 57 and 65, with the strong sorted-baseline offset method as the traditional comparator.
- **Falsification test:** the hypothesis that sorted reconstruction metadata adds useful pedestal information would fail if all ML/NN methods were no better than the calibrated sorted-baseline estimator, or if the direct `hrd.baseline` branch were already exact enough that learned residual structure had no measurable room to improve.
- **Result:** `hist_gradient_boosted_trees` is the lowest-MAE method. Multiple model families were tried (`N=5` learned families plus two traditional variants), so the result should be read as a benchmark ranking rather than a discovery p-value. The paired bootstrap delta table is the uncertainty-bearing comparison.

## 6. Systematics and threats to validity

- **Benchmark/selection:** the traditional comparator is not a strawman: it uses `hrd.baseline` plus train-run robust offsets by stave, peak-time bin, and amplitude bin.
- **Data leakage:** splits are by run. Features exclude run ID, event IDs, raw pretrigger samples, and `hrd.sample`, which would permit near-exact raw reconstruction when combined with `hrd.baseline`.
- **Metric misuse:** MAE is reported with bias, RMSE, and 5-95% residual quantiles; residual distributions are plotted in `fig_residual_distributions.png`.
- **Post-hoc selection:** held-out runs, calibration runs, feature exclusions, bootstrap count, and model grid are fixed in the config before model fitting in this worker.
- **Target limitation:** the target is a raw pretrigger median in beam-triggered physics events, not a true forced/random electronics pedestal. Pretrigger contamination can therefore be real detector/pathology structure rather than electronics baseline drift.
- **Sorted-branch semantics:** `hrd.baseline` appears to be a sorted preprocessing baseline close to the per-channel waveform minimum. The study tests empirical recoverability, not the C++ implementation contract.

## 7. Provenance manifest

`manifest.json` records the command, config, input ROOT checksums for all configured raw and sorted B-stack files, random seeds, package versions, and output hashes. `result.json` names the winner for the integrator.

## 8. Findings and next steps

Sorted ROOT metadata does encode recoverable information about the absolute raw pretrigger pedestal level, but the direct `hrd.baseline` branch is biased low and is not a drop-in pedestal median. The winning boosted-tree model uses the baseline branch together with sorted trapezoid/peak metadata to correct that residual. The result supports using the combined sorted metadata as a compact pedestal proxy when raw waveforms are unavailable, with the caveat that it is not a substitute for true forced/random pedestal data.

Proposed follow-up, queued at most once by this worker: use the sorted-baseline residual as a nuisance covariate in the S02/S04 timing fits and test whether it explains timing tails beyond amplitude and peak-time controls. This has high information gain because it connects pedestal recoverability to the physics resolution endpoint rather than only to a reconstruction diagnostic.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16h_1781031000_2442_5ff56e52_sorted_baseline_pretrigger.py --config configs/s16h_1781031000_2442_5ff56e52_sorted_baseline_pretrigger.json
```

Outputs: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `heldout_predictions.csv`, `heldout_method_metrics.csv`, `heldout_by_run.csv`, `hgb_cv_scan.csv`, `leakage_checks.csv`, and two PNG figures.
