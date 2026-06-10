# P10f: same-pulse handle leakage stress test

- **Ticket ID:** `1781025380.1851.6eb61bde`
- **Worker:** `testbeam-laptop-3`
- **Input:** raw B-stack ROOT under `data/root/root`; no Monte Carlo.
- **Config:** `configs/p10f_1781025380_1851_6eb61bde_same_pulse_leakage_stress.json`

## Raw-ROOT reproduction first

| quantity                         |   expected |   reproduced |   delta | pass   |
|:---------------------------------|-----------:|-------------:|--------:|:-------|
| P10d/S00 selected B-stave pulses |     640737 |       640737 |       0 | True   |
| P10d analysis selected rows      |     377362 |       377362 |       0 | True   |

## Methods

Split is by run using the P10d/P10c family holdouts. The first fold trains on run 64 and holds out Sample-I analysis runs 44-57; the second trains on Sample-I calibration runs 31-42 and holds out Sample-II analysis runs 58-63 and 65. All CIs below bootstrap held-out runs.

Traditional comparators are the amplitude-bin empirical median template and a stronger CFD/rise/tail binned median template. The amplitude-only monotone ablation uses only `log(A)`, `log(A)^2`, `1/sqrt(A)`, and `1/A` plus stave terms. The CFD/shape arm adds CFD crossings and widths but omits tail summaries. The full aggressive arm restores CFD, width, area, and tail handles. Run number, event id, event order, other-stave observables, and held-out labels are excluded.

## Held-out run-bootstrap means

| fold              |   empirical_amp_template_mse |   traditional_cfd_tail_binned_template_mse |   ridge_amp_monotone_mse |   ridge_cfd_shape_no_tail_mse |   ridge_full_aggressive_mse |   et_amp_monotone_mse |   et_cfd_shape_no_tail_mse |   et_full_aggressive_mse |   et_full_aggressive_shuffled_mse |
|:------------------|-----------------------------:|-------------------------------------------:|-------------------------:|------------------------------:|----------------------------:|----------------------:|---------------------------:|-------------------------:|----------------------------------:|
| holdout_sample_i  |                    0.0477821 |                                  0.0597976 |                0.0627009 |                     0.0533092 |                   0.0251049 |             0.0608056 |                  0.0187313 |                0.0162924 |                         0.0786686 |
| holdout_sample_ii |                    0.0389922 |                                  0.0639939 |                0.068379  |                     0.0730432 |                   0.0522092 |             0.073156  |                  0.0338583 |                0.0322096 |                         0.0866299 |

## Key CIs

| fold              | delta_traditional_cfd_tail_binned_template_mse_minus_empirical_amp_template_ci   | delta_et_amp_monotone_mse_minus_empirical_amp_template_ci   | delta_et_cfd_shape_no_tail_mse_minus_empirical_amp_template_ci   | delta_et_full_aggressive_mse_minus_empirical_amp_template_ci   | delta_et_full_aggressive_mse_minus_shuffled_ci   |
|:------------------|:---------------------------------------------------------------------------------|:------------------------------------------------------------|:-----------------------------------------------------------------|:---------------------------------------------------------------|:-------------------------------------------------|
| holdout_sample_i  | [0.008890064709763463, 0.015058316326851806]                                     | [0.010502657269247819, 0.01569101397158097]                 | [-0.03977977056078769, -0.019001850920365184]                    | [-0.042458756520374716, -0.021032432316934368]                 | [-0.07736217193233282, -0.04878880067932689]     |
| holdout_sample_ii | [0.022606909283116188, 0.02823344193135535]                                      | [0.03068808222999423, 0.038642709383175385]                 | [-0.010208836029238463, 0.0024908514211976307]                   | [-0.012201975800368406, 0.0010218893783297798]                 | [-0.0636977520287962, -0.040792052288034834]     |

## Leakage checks

| fold              | train_eval_run_overlap   |   train_eval_key_overlap |   waveform_hash_overlap_count |   waveform_hash_overlap_frac_eval_unique |   nn_distance_min |   nn_distance_p01 |   nn_frac_dist_le_1e-06 |   nn_frac_dist_le_0.001 |   nn_frac_dist_le_0.01 |
|:------------------|:-------------------------|-------------------------:|------------------------------:|-----------------------------------------:|------------------:|------------------:|------------------------:|------------------------:|-----------------------:|
| holdout_sample_i  | []                       |                        0 |                             0 |                                        0 |        0.00751478 |         0.017713  |                       0 |                       0 |              0.0001875 |
| holdout_sample_ii | []                       |                        0 |                             0 |                                        0 |        0.00912419 |         0.0180773 |                       0 |                       0 |              0.000125  |

Waveform hashes are SHA256 values of normalized waveforms quantized at 1e-6. Nearest-neighbor distances are Euclidean distances in the 18-sample normalized waveform space from held-out sampled pulses to train sampled pulses.

## Finding

Full same-pulse CFD/shape/tail ExtraTrees is tested against the amplitude empirical baseline, shuffled targets, and waveform-neighbor leakage checks before any gain is promoted. Here full_beats_empirical=False, full_beats_shuffled=True, hash_overlap_flag=False, exact_nn_flag=False. The full model separates from shuffled controls, but the cross-family empirical-baseline gain is not CI-stable in every fold; the amplitude-only ablation is the conservative reference for showing that target-proximal CFD/shape handles are doing the work.

Artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `family_heldout_summary.csv`, `family_heldout_run_benchmark.csv`, and `leakage_checks.csv`.

## Reproduce

```bash
/home/billy/anaconda3/bin/python scripts/p10f_1781025380_1851_6eb61bde_same_pulse_leakage_stress.py --config configs/p10f_1781025380_1851_6eb61bde_same_pulse_leakage_stress.json
```
