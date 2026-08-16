# S16h: sorted ROOT baseline branches versus raw pretrigger pedestals

- **Ticket:** 2394
- **Author:** testbeam-laptop-1
- **Date:** 2026-08-16
- **Depends on:** S00, S16, S16b/S16d
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `e911cfc59b772e150beb5dd2c080b020066a3bd4`
- **Config:** `configs/ticket_2394_s16_pedestal_baseline_validation.json`

## 0. Question

Can the sorted ROOT reconstruction metadata, especially `hrd.baseline` and trapezoid-filter branches, recover the raw pretrigger pedestal level for selected B-stack pulses? The operational target is the raw median pedestal

\[
  y_i = \operatorname{median}\left(x_{i,0}, x_{i,1}, x_{i,2}, x_{i,3}\right),
\]

where `x` is the raw `HRDv` waveform for one selected B stave. The main scientific question is whether sorted baseline preprocessing preserves absolute pedestal shifts well enough to replace or augment the reduced raw pretrigger audit.

## 1. Reproduction from raw ROOT

The reproduction gate reruns the S00 B-stave selected-pulse count from raw `/home/billy/ccb-data/data/extracted/root/root/hrdb_run_NNNN.root`, with B2/B4/B6/B8 channels, median samples 0-3 as the seed pedestal, and the fixed `A > 1000 ADC` gate. The sorted tree is matched entry-by-entry through `raw EVT == sorted hrdEvtNo`; any mismatch aborts the script.

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
|           63.000 |           0.080 |               0.000 |       18.536 |            1.622 |
|           63.000 |           0.080 |               0.100 |       18.568 |            1.453 |
|           63.000 |           0.040 |               0.100 |       19.024 |            1.522 |
|           63.000 |           0.040 |               0.000 |       19.091 |            1.491 |
|           31.000 |           0.080 |               0.000 |       19.897 |            1.669 |

## 4. Head-to-head benchmark

Primary metric: held-out raw pretrigger median MAE in ADC. CIs are 95% run-block bootstraps over the held-out source runs.

| method                                 | family           |     n |   mae_adc |   mae_ci_low_adc |   mae_ci_high_adc |   bias_adc |   rmse_adc |   q05_residual_adc |   q95_residual_adc |
|:---------------------------------------|:-----------------|------:|----------:|-----------------:|------------------:|-----------:|-----------:|-------------------:|-------------------:|
| hist_gradient_boosted_trees            | ml               | 26871 |    21.031 |           15.813 |            25.948 |     -0.122 |    107.200 |            -35.630 |             37.471 |
| mlp                                    | ml               | 26871 |    32.560 |           28.039 |            36.821 |      6.053 |    130.567 |            -42.637 |             67.262 |
| sorted_residual_net                    | new_architecture | 26871 |    90.284 |           47.571 |           130.543 |    -23.937 |    420.107 |            -51.929 |             79.848 |
| one_dimensional_cnn                    | ml               | 26871 |   126.704 |           74.835 |           175.593 |    -22.355 |    492.434 |           -110.828 |            157.799 |
| ridge                                  | ml               | 26871 |   165.939 |          153.043 |           178.094 |     11.306 |    292.997 |           -356.811 |            268.770 |
| traditional_calibrated_sorted_baseline | traditional      | 26871 |   189.995 |          119.331 |           256.597 |   -119.609 |    886.030 |           -697.500 |              7.500 |
| sorted_baseline_direct                 | traditional      | 26871 |   332.962 |          202.240 |           456.171 |   -332.962 |   1226.818 |          -2389.000 |             -2.000 |

Paired deltas relative to the strong traditional calibrated baseline:

| method                      |   delta_mae_vs_traditional_adc |   ci_low_adc |   ci_high_adc |
|:----------------------------|-------------------------------:|-------------:|--------------:|
| hist_gradient_boosted_trees |                       -168.964 |     -230.649 |      -103.518 |
| mlp                         |                       -157.435 |     -219.776 |       -91.292 |
| sorted_residual_net         |                        -99.710 |     -126.054 |       -71.761 |
| one_dimensional_cnn         |                        -63.290 |      -81.004 |       -44.497 |
| ridge                       |                        -24.055 |      -78.503 |        33.712 |
| sorted_baseline_direct      |                        142.967 |       82.909 |       199.574 |

Winner: **hist_gradient_boosted_trees** with MAE `21.031` ADC, CI `[15.813, 25.948]`. The strong traditional calibrated baseline has MAE `189.995` ADC, CI `[119.331, 256.597]`. Winner minus traditional baseline is `-168.964 [-230.649, -103.518]` ADC.

By-run held-out summary:

|   run | method                                 |     n |   mae_adc |   bias_adc |   rmse_adc |
|------:|:---------------------------------------|------:|----------:|-----------:|-----------:|
|    57 | hist_gradient_boosted_trees            | 13833 |    25.948 |     -0.126 |    136.241 |
|    57 | mlp                                    | 13833 |    36.821 |      3.289 |    155.634 |
|    57 | sorted_residual_net                    | 13833 |   130.543 |    -59.577 |    561.017 |
|    57 | one_dimensional_cnn                    | 13833 |   175.593 |    -68.925 |    650.333 |
|    57 | ridge                                  | 13833 |   178.094 |    -24.946 |    338.105 |
|    57 | traditional_calibrated_sorted_baseline | 13833 |   256.597 |   -188.622 |   1116.343 |
|    57 | sorted_baseline_direct                 | 13833 |   456.171 |   -456.171 |   1523.250 |
|    65 | hist_gradient_boosted_trees            | 13038 |    15.813 |     -0.117 |     63.176 |
|    65 | mlp                                    | 13038 |    28.039 |      8.985 |     97.139 |
|    65 | sorted_residual_net                    | 13038 |    47.571 |     13.876 |    172.652 |
|    65 | one_dimensional_cnn                    | 13038 |    74.835 |     27.054 |    225.934 |
|    65 | traditional_calibrated_sorted_baseline | 13038 |   119.331 |    -46.388 |    543.835 |
|    65 | ridge                                  | 13038 |   153.043 |     49.769 |    235.889 |
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

Queued follow-up `#2438`: use the sorted-baseline residual as a nuisance covariate in the S02/S04 timing fits and test whether it explains timing tails beyond amplitude and peak-time controls. This has high information gain because it connects pedestal recoverability to the physics resolution endpoint rather than only to a reconstruction diagnostic.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16h_1781031000_2442_5ff56e52_sorted_baseline_pretrigger.py --config configs/ticket_2394_s16_pedestal_baseline_validation.json
```

Outputs: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `heldout_predictions.csv`, `heldout_method_metrics.csv`, `heldout_by_run.csv`, `hgb_cv_scan.csv`, `leakage_checks.csv`, and two PNG figures.
