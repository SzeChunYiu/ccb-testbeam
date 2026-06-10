# P10e: run-family drift audit for explicit q-template handles

- **Ticket ID:** 1781025380.1773.0fb745c7
- **Worker:** testbeam-laptop-2
- **Input:** raw B-stack ROOT under `data/root/root`
- **Config:** `configs/p10e_1781025380_1773_0fb745c7_run_family_drift_audit.yaml`
- **Git commit:** 152ed196e72b90c02e8eb5a27b053d19f93caa5c

## Raw-ROOT reproduction gate

The selected B-stave pulse table was rebuilt from raw `HRDv` waveforms before any modeling: median baseline over samples 0-3, B2/B4/B6/B8, and `A > 1000` ADC.

| quantity                        |   expected |   reproduced |   delta | pass   |
|:--------------------------------|-----------:|-------------:|--------:|:-------|
| S00/S01 selected B-stave pulses |     640737 |       640737 |       0 | True   |
| analysis selected rows          |     377362 |       377362 |       0 | True   |

## Methods

Split: the P10c leave-one-run-family-out split, so Sample I analysis runs are held out after training on run 64 only, and Sample II analysis runs are held out after training on Sample I calibration runs 31-42.

Empirical-bin baseline: S01/P10c train-only median aligned templates per stave and amplitude bin.

Strong traditional method: empirical templates additionally binned by train-quantile rise-width and tail-summary handles, with hierarchical fallback to the amplitude-bin template when a cell has fewer than the configured training pulses.

ML method: multi-output ExtraTrees predicts the CFD20-aligned normalized waveform from same-pulse amplitude, train-centered CFD position, rise/width, tail summaries, monotonic amplitude/timewalk handles (`1/sqrt(A)`, `1/A`, log terms), stave one-hot terms, and interactions. Run number, event id, event order, other-stave observables, and held-out residual labels are excluded.

Extended ridge is included as a parametric diagnostic using the same handle matrix.

## Held-out q-template MSE

Values are means of per-run MSEs; 95% CIs bootstrap held-out runs.

| fold              |   empirical_mse | empirical_mse_ci                             |   handle_binned_mse | handle_binned_mse_ci                        |   ridge_handles_mse | ridge_handles_mse_ci                       |   extra_trees_mse | extra_trees_mse_ci                           |   shuffled_extra_trees_mse |   delta_extra_trees_mse_minus_empirical | delta_extra_trees_mse_minus_empirical_ci       |
|:------------------|----------------:|:---------------------------------------------|--------------------:|:--------------------------------------------|--------------------:|:-------------------------------------------|------------------:|:---------------------------------------------|---------------------------:|----------------------------------------:|:-----------------------------------------------|
| holdout_sample_i  |       0.0477821 | [0.033584337471470806, 0.062277572305694986] |           0.0597976 | [0.04833782590216384, 0.07141078434909606]  |           0.0251044 | [0.02070525229930668, 0.02965085941378238] |         0.016209  | [0.012550372123577846, 0.02013874494622243]  |                  0.0805686 |                             -0.0315731  | [-0.042755484381146666, -0.021086876501398448] |
| holdout_sample_ii |       0.0389922 | [0.028944669072985048, 0.045920379497486605] |           0.0639939 | [0.056928349692986636, 0.06937584279733153] |           0.0429427 | [0.03882555540282498, 0.04677982455125946] |         0.0319112 | [0.029364361710794925, 0.034277478039270705] |                  0.0868083 |                             -0.00708096 | [-0.012741511336757994, 0.0011747366592150584] |

## Leakage audit

| fold              | train_eval_run_overlap   |   train_eval_key_overlap | uses_run_or_event_features   | uses_other_stave_features   |   feature_count | extra_trees_beats_empirical_ci   | shuffled_beats_real_ci   |
|:------------------|:-------------------------|-------------------------:|:-----------------------------|:----------------------------|----------------:|:---------------------------------|:-------------------------|
| holdout_sample_i  | []                       |                        0 | False                        | False                       |              94 | True                             | False                    |
| holdout_sample_ii | []                       |                        0 | False                        | False                       |              94 | False                            | False                    |

The same-pulse handles are intentionally aggressive, so the shuffled-target ExtraTrees control is reported beside the real model. No result is treated as a rescue unless it beats the empirical-bin baseline under the run-bootstrap CI and also separates from the shuffled-target control.

## Family drift diagnostics

`feature_family_comparison.csv` compares Sample-I calibration against run 64 for every explicit handle using standardized mean difference and two-sample KS distance. `family_handle_quantiles.csv` records the train-only quantiles used by the family-specific handle bins, making the bin edges auditable separately for Sample-I calibration and run 64.

Largest train-family handle shifts:

| feature      |   sample_i_calib_n |   run64_n |   sample_i_calib_mean |   run64_mean |   standardized_mean_diff_sample_i_minus_run64 |   median_delta_sample_i_minus_run64 |   ks_distance |
|:-------------|-------------------:|----------:|----------------------:|-------------:|----------------------------------------------:|------------------------------------:|--------------:|
| cfd50        |             245983 |     14590 |           4.64558     |  5.35158     |                                     -0.390839 |                        -0.85272     |      0.485847 |
| cfd30        |             245983 |     14590 |           4.26771     |  4.90829     |                                     -0.36098  |                        -0.763254    |      0.480193 |
| cfd20        |             245983 |     14590 |           4.04422     |  4.65071     |                                     -0.345934 |                        -0.580846    |      0.471623 |
| peak_sample  |             248745 |     14630 |           6.14811     |  7.21224     |                                     -0.519001 |                        -1           |      0.466083 |
| cfd10        |             245983 |     14590 |           3.74031     |  4.31533     |                                     -0.33404  |                        -0.713197    |      0.451409 |
| inv_sqrt_amp |             248745 |     14630 |           0.0147634   |  0.0186389   |                                     -0.839205 |                        -0.00473803  |      0.436444 |
| inv_amp      |             248745 |     14630 |           0.000237828 |  0.000370192 |                                     -0.730169 |                        -0.000147037 |      0.436444 |
| log_amp2     |             248745 |     14630 |          72.6139      | 64.7116      |                                      0.950661 |                        10.2856      |      0.436444 |

## Finding

Strong traditional handle bins rescue q-space under both family holdouts: `False`.
ExtraTrees handle conditioning rescues q-space under both family holdouts: `False`.
P10d is reproduced: ExtraTrees is CI-clean for the Sample-I holdout but not for the Sample-II holdout. The answer is therefore based on held-out run CIs and the shuffled-target control, not row-level scores.

No Monte Carlo was used. `result.json`, `manifest.json`, `input_sha256.csv`, run-level CSVs, CV CSVs, leakage checks, handle-bin counts, family quantiles, and feature-drift diagnostics are in this report directory.

## Reproduce

```bash
/home/billy/anaconda3/bin/python scripts/p10e_1781025380_1773_0fb745c7_run_family_drift_audit.py --config configs/p10e_1781025380_1773_0fb745c7_run_family_drift_audit.yaml
```
