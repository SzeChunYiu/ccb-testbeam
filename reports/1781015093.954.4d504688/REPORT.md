# Study report: P03d - per-stave waveform MLP calibration failure analysis

- **Ticket:** 1781015093.954.4d504688
- **Author:** testbeam-laptop-3
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT files under `data/root/root`; P03b held-out residual artifacts
- **Split:** leave one run out across sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65
- **Config:** `configs/p03d_1781015093_954_4d504688.yaml`

## Question

Do B4/B6/B8 per-stave MLP calibration asymmetries explain the P03b residual instability and the folds where the MLP is weak against the analytic timewalk baseline?

## Raw-ROOT reproduction gate

This gate was run before reading the P03b output tables.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

P03b's raw-gate table was also checked for agreement with this run.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## P03b run-split benchmark used

|   heldout_run | method            |   sigma68_ns |   ci_low |   ci_high |   n_pair_residuals |
|--------------:|:------------------|-------------:|---------:|----------:|-------------------:|
|            58 | analytic_timewalk |      1.18748 |  1.13775 |   1.40035 |                219 |
|            58 | mlp_waveform      |      1.88783 |  1.6007  |   2.22393 |                219 |
|            58 | s02_ridge_cfd20   |      1.91964 |  1.65636 |   2.17185 |                219 |
|            59 | analytic_timewalk |      1.45871 |  1.38233 |   1.52694 |               2289 |
|            59 | mlp_waveform      |      1.71108 |  1.64366 |   1.77743 |               2289 |
|            59 | s02_ridge_cfd20   |      1.88049 |  1.81022 |   1.97038 |               2289 |
|            60 | analytic_timewalk |      1.3437  |  1.28298 |   1.40768 |               2424 |
|            60 | mlp_waveform      |      1.60696 |  1.53316 |   1.66854 |               2424 |
|            60 | s02_ridge_cfd20   |      1.81993 |  1.73914 |   1.91795 |               2424 |
|            61 | analytic_timewalk |      2.12996 |  1.98436 |   2.20935 |               2799 |
|            61 | mlp_waveform      |      2.11367 |  2.04088 |   2.18039 |               2799 |
|            61 | s02_ridge_cfd20   |      2.24243 |  2.14793 |   2.32966 |               2799 |
|            62 | analytic_timewalk |      1.469   |  1.40916 |   1.51558 |               2421 |
|            62 | mlp_waveform      |      1.74331 |  1.67694 |   1.81987 |               2421 |
|            62 | s02_ridge_cfd20   |      1.86001 |  1.77626 |   1.94181 |               2421 |
|            63 | analytic_timewalk |      1.39132 |  1.29008 |   1.46871 |               1110 |
|            63 | mlp_waveform      |      1.6482  |  1.53176 |   1.76934 |               1110 |
|            63 | s02_ridge_cfd20   |      1.76984 |  1.61604 |   1.8982  |               1110 |
|            65 | analytic_timewalk |      1.49464 |  1.30186 |   1.66581 |                198 |
|            65 | mlp_waveform      |      1.92723 |  1.62267 |   2.26034 |                198 |
|            65 | s02_ridge_cfd20   |      1.84611 |  1.45261 |   2.02735 |                198 |

## Per-stave MLP calibration

|   heldout_run | stave   |   n_events |   pred_sigma_median_ns |   abs_error_median_ns |   error_sigma68_ns |   error_sigma68_ci_low |   error_sigma68_ci_high |   pull_width_sigma68 |
|--------------:|:--------|-----------:|-----------------------:|----------------------:|-------------------:|-----------------------:|------------------------:|---------------------:|
|            58 | B4      |         73 |                2.93402 |              0.969664 |            1.33202 |               1.10125  |                 1.87886 |             0.292088 |
|            58 | B6      |         73 |                2.01803 |              1.14358  |            2.05597 |               1.70941  |                 2.49455 |             0.291523 |
|            58 | B8      |         73 |                2.41974 |              0.962341 |            1.42615 |               1.0953   |                 1.65597 |             0.419574 |
|            59 | B4      |        763 |                2.0262  |              0.866363 |            1.29516 |               1.21152  |                 1.379   |             0.568444 |
|            59 | B6      |        763 |                1.71896 |              0.701637 |            1.06471 |               0.992446 |                 1.15131 |             0.562877 |
|            59 | B8      |        763 |                1.60012 |              0.702081 |            1.0036  |               0.925174 |                 1.06683 |             0.57569  |
|            60 | B4      |        808 |                1.99863 |              0.892286 |            1.3104  |               1.22415  |                 1.41049 |             0.564661 |
|            60 | B6      |        808 |                1.93371 |              0.80028  |            1.03288 |               0.948125 |                 1.12282 |             0.476038 |
|            60 | B8      |        808 |                1.87688 |              0.764054 |            1.10887 |               1.02652  |                 1.2303  |             0.555665 |
|            61 | B4      |        933 |                2.14288 |              1.08002  |            1.29022 |               1.2175   |                 1.39328 |             0.542213 |
|            61 | B6      |        933 |                1.69871 |              0.729657 |            1.11077 |               1.04773  |                 1.18794 |             0.536683 |
|            61 | B8      |        933 |                1.69193 |              0.728175 |            1.09117 |               1.03651  |                 1.15814 |             0.576806 |
|            62 | B4      |        807 |                2.12208 |              0.905199 |            1.31129 |               1.23355  |                 1.4278  |             0.567767 |
|            62 | B6      |        807 |                1.71074 |              0.746906 |            1.11749 |               1.02868  |                 1.21513 |             0.559365 |
|            62 | B8      |        807 |                1.86048 |              0.703019 |            1.11428 |               1.04385  |                 1.20337 |             0.530732 |
|            63 | B4      |        370 |                2.05516 |              1.10454  |            1.48826 |               1.33963  |                 1.59473 |             0.6218   |
|            63 | B6      |        370 |                1.76207 |              0.790889 |            1.19887 |               0.99968  |                 1.33536 |             0.530287 |
|            63 | B8      |        370 |                1.81617 |              0.677243 |            1.03303 |               0.900617 |                 1.14347 |             0.454227 |
|            65 | B4      |         66 |                2.14908 |              1.36129  |            1.38745 |               1.0529   |                 1.72011 |             0.561773 |
|            65 | B6      |         66 |                1.90698 |              1.16106  |            1.65538 |               1.30139  |                 2.42869 |             0.485786 |
|            65 | B8      |         66 |                1.8376  |              0.707592 |            1.04434 |               0.814035 |                 1.30971 |             0.377288 |

## Pair residual asymmetry

|   heldout_run | pair   | method            |   sigma68_ns |   sigma68_ci_low |   sigma68_ci_high |   median_residual_ns |
|--------------:|:-------|:------------------|-------------:|-----------------:|------------------:|---------------------:|
|            58 | B4-B6  | analytic_timewalk |     0.514032 |         0.243102 |          0.981183 |            2.08329   |
|            58 | B4-B8  | analytic_timewalk |     0.563535 |         0.420643 |          0.78608  |            1.93566   |
|            58 | B6-B8  | analytic_timewalk |     0.752592 |         0.437283 |          1.11231  |           -0.119214  |
|            58 | B4-B6  | mlp_waveform      |     2.39667  |         1.81946  |          2.79227  |            0.709103  |
|            58 | B4-B8  | mlp_waveform      |     1.88995  |         1.31554  |          2.22769  |            1.40118   |
|            58 | B6-B8  | mlp_waveform      |     1.49103  |         1.30287  |          1.76166  |            0.674592  |
|            59 | B4-B6  | analytic_timewalk |     1.05676  |         1.00042  |          1.21524  |            2.04638   |
|            59 | B4-B8  | analytic_timewalk |     1.16318  |         1.03564  |          1.27123  |            1.68212   |
|            59 | B6-B8  | analytic_timewalk |     0.96709  |         0.84031  |          1.09344  |           -0.259815  |
|            59 | B4-B6  | mlp_waveform      |     1.49841  |         1.36647  |          1.60056  |            1.91624   |
|            59 | B4-B8  | mlp_waveform      |     1.38666  |         1.30144  |          1.46897  |            1.7295    |
|            59 | B6-B8  | mlp_waveform      |     0.980004 |         0.902857 |          1.05953  |           -0.141883  |
|            60 | B4-B6  | analytic_timewalk |     0.96824  |         0.795523 |          1.14746  |            1.93104   |
|            60 | B4-B8  | analytic_timewalk |     0.936695 |         0.852667 |          1.05469  |            1.65039   |
|            60 | B6-B8  | analytic_timewalk |     0.973746 |         0.87357  |          1.0965   |           -0.201945  |
|            60 | B4-B6  | mlp_waveform      |     1.50663  |         1.41005  |          1.59127  |            1.57674   |
|            60 | B4-B8  | mlp_waveform      |     1.43875  |         1.35623  |          1.54627  |            1.44713   |
|            60 | B6-B8  | mlp_waveform      |     1.00942  |         0.940536 |          1.11307  |           -0.0814656 |
|            61 | B4-B6  | analytic_timewalk |     1.26742  |         1.18906  |          1.30672  |            2.68685   |
|            61 | B4-B8  | analytic_timewalk |     1.33023  |         1.239    |          1.47579  |            2.36591   |
|            61 | B6-B8  | analytic_timewalk |     1.06247  |         0.962515 |          1.1888   |           -0.159499  |
|            61 | B4-B6  | mlp_waveform      |     1.5568   |         1.45101  |          1.64422  |            2.81626   |
|            61 | B4-B8  | mlp_waveform      |     1.41042  |         1.32962  |          1.51702  |            2.48519   |
|            61 | B6-B8  | mlp_waveform      |     1.0879   |         1.01566  |          1.16563  |           -0.173068  |
|            62 | B4-B6  | analytic_timewalk |     1.08449  |         0.864385 |          1.21931  |            2.01877   |
|            62 | B4-B8  | analytic_timewalk |     1.09411  |         1.02233  |          1.2073   |            1.76149   |
|            62 | B6-B8  | analytic_timewalk |     1.04968  |         0.943083 |          1.15393  |           -0.201229  |
|            62 | B4-B6  | mlp_waveform      |     1.51734  |         1.45224  |          1.60613  |            1.77032   |
|            62 | B4-B8  | mlp_waveform      |     1.55306  |         1.44945  |          1.64316  |            1.61028   |
|            62 | B6-B8  | mlp_waveform      |     1.04351  |         0.969747 |          1.16925  |           -0.148519  |
|            63 | B4-B6  | analytic_timewalk |     1.15522  |         0.884967 |          1.27891  |            1.94576   |
|            63 | B4-B8  | analytic_timewalk |     1.06153  |         0.923821 |          1.23131  |            1.66168   |
|            63 | B6-B8  | analytic_timewalk |     1.02488  |         0.778002 |          1.21977  |           -0.20664   |
|            63 | B4-B6  | mlp_waveform      |     1.69081  |         1.50248  |          1.86225  |            1.56891   |
|            63 | B4-B8  | mlp_waveform      |     1.46982  |         1.34519  |          1.61806  |            1.45548   |
|            63 | B6-B8  | mlp_waveform      |     1.02907  |         0.87639  |          1.21049  |           -0.0964533 |
|            65 | B4-B6  | analytic_timewalk |     1.0854   |         0.547555 |          1.57986  |            2.07158   |
|            65 | B4-B8  | analytic_timewalk |     1.2331   |         0.87773  |          1.51156  |            1.90516   |
|            65 | B6-B8  | analytic_timewalk |     0.889703 |         0.566266 |          1.39803  |           -0.294974  |
|            65 | B4-B6  | mlp_waveform      |     2.52724  |         1.67702  |          3.11061  |            1.30177   |
|            65 | B4-B8  | mlp_waveform      |     1.59423  |         1.19551  |          2.14847  |            1.04383   |
|            65 | B6-B8  | mlp_waveform      |     1.16736  |         0.85301  |          1.75399  |           -0.218963  |

## Diagnosis

|   heldout_run |   mlp_sigma68_ns |   analytic_sigma68_ns |   mlp_minus_analytic_ns |   p03b_pred_sigma_median_ns |   stave_error_sigma68_range_ns | worst_stave_by_error_sigma68   |   mlp_pair_sigma68_range_ns | worst_mlp_pair   |
|--------------:|-----------------:|----------------------:|------------------------:|----------------------------:|-------------------------------:|:-------------------------------|----------------------------:|:-----------------|
|            58 |          1.88783 |               1.18748 |               0.700342  |                     2.5306  |                       0.723949 | B6                             |                    0.905647 | B4-B6            |
|            59 |          1.71108 |               1.45871 |               0.252373  |                     1.80809 |                       0.291564 | B4                             |                    0.518401 | B4-B6            |
|            60 |          1.60696 |               1.3437  |               0.263251  |                     1.94918 |                       0.277519 | B4                             |                    0.497214 | B4-B6            |
|            61 |          2.11367 |               2.12996 |              -0.0162905 |                     1.87941 |                       0.199057 | B4                             |                    0.468897 | B4-B6            |
|            62 |          1.74331 |               1.469   |               0.274307  |                     1.98092 |                       0.197008 | B4                             |                    0.509555 | B4-B8            |
|            63 |          1.6482  |               1.39132 |               0.256875  |                     1.95666 |                       0.45523  | B4                             |                    0.661742 | B4-B6            |
|            65 |          1.92723 |               1.49464 |               0.432593  |                     2.01614 |                       0.611033 | B6                             |                    1.35987  | B4-B6            |

Worst MLP residual instability is held-out run `61` with MLP sigma68 `2.114` ns. The largest weak-analytic fold is run `58` with MLP minus analytic `0.700` ns. The highest P03b median predicted sigma is run `58` at `2.531` ns.

Across seven held-out runs, the Pearson correlation between MLP sigma68 and the B4/B6/B8 stave error-sigma range is `0.129`; the correlation with MLP pair-sigma range is `0.287`. This is the quantitative test for the asymmetry explanation.

## Leakage controls

| check                                       |   value | detail                                                                                                                             |   heldout_run |
|:--------------------------------------------|--------:|:-----------------------------------------------------------------------------------------------------------------------------------|--------------:|
| feature_audit                               | 0       | features are normalized 18-sample waveform plus stave one-hot; no run, event id, event order, other-stave time, or held-out target |            58 |
| nominal_mlp_sigma68_ns                      | 1.88783 | held-out run metric for comparison to shuffled control                                                                             |            58 |
| shuffled_target_negative_control_sigma68_ns | 3.19475 | same architecture trained with shuffled train residual targets                                                                     |            58 |
| train_heldout_event_id_overlap              | 0       | must be zero                                                                                                                       |            58 |
| feature_audit                               | 0       | features are normalized 18-sample waveform plus stave one-hot; no run, event id, event order, other-stave time, or held-out target |            59 |
| nominal_mlp_sigma68_ns                      | 1.71108 | held-out run metric for comparison to shuffled control                                                                             |            59 |
| shuffled_target_negative_control_sigma68_ns | 3.16297 | same architecture trained with shuffled train residual targets                                                                     |            59 |
| train_heldout_event_id_overlap              | 0       | must be zero                                                                                                                       |            59 |
| feature_audit                               | 0       | features are normalized 18-sample waveform plus stave one-hot; no run, event id, event order, other-stave time, or held-out target |            60 |
| nominal_mlp_sigma68_ns                      | 1.60696 | held-out run metric for comparison to shuffled control                                                                             |            60 |
| shuffled_target_negative_control_sigma68_ns | 3.14377 | same architecture trained with shuffled train residual targets                                                                     |            60 |
| train_heldout_event_id_overlap              | 0       | must be zero                                                                                                                       |            60 |
| feature_audit                               | 0       | features are normalized 18-sample waveform plus stave one-hot; no run, event id, event order, other-stave time, or held-out target |            61 |
| nominal_mlp_sigma68_ns                      | 2.11367 | held-out run metric for comparison to shuffled control                                                                             |            61 |
| shuffled_target_negative_control_sigma68_ns | 2.91149 | same architecture trained with shuffled train residual targets                                                                     |            61 |
| train_heldout_event_id_overlap              | 0       | must be zero                                                                                                                       |            61 |
| feature_audit                               | 0       | features are normalized 18-sample waveform plus stave one-hot; no run, event id, event order, other-stave time, or held-out target |            62 |
| nominal_mlp_sigma68_ns                      | 1.74331 | held-out run metric for comparison to shuffled control                                                                             |            62 |
| shuffled_target_negative_control_sigma68_ns | 3.23319 | same architecture trained with shuffled train residual targets                                                                     |            62 |
| train_heldout_event_id_overlap              | 0       | must be zero                                                                                                                       |            62 |
| feature_audit                               | 0       | features are normalized 18-sample waveform plus stave one-hot; no run, event id, event order, other-stave time, or held-out target |            63 |
| nominal_mlp_sigma68_ns                      | 1.6482  | held-out run metric for comparison to shuffled control                                                                             |            63 |
| shuffled_target_negative_control_sigma68_ns | 3.48094 | same architecture trained with shuffled train residual targets                                                                     |            63 |
| train_heldout_event_id_overlap              | 0       | must be zero                                                                                                                       |            63 |
| feature_audit                               | 0       | features are normalized 18-sample waveform plus stave one-hot; no run, event id, event order, other-stave time, or held-out target |            65 |
| nominal_mlp_sigma68_ns                      | 1.92723 | held-out run metric for comparison to shuffled control                                                                             |            65 |
| shuffled_target_negative_control_sigma68_ns | 3.17379 | same architecture trained with shuffled train residual targets                                                                     |            65 |
| train_heldout_event_id_overlap              | 0       | must be zero                                                                                                                       |            65 |

Features used for the retrained diagnostic MLP are normalized same-pulse 18-sample waveform values plus stave one-hot. There is no run number, event id, event order, other-stave time, or held-out target in the feature matrix. P03b shuffled-target controls remain worse than the nominal MLP in every fold.

## Verdict

`result.json` verdict: `stave_asymmetry_does_not_explain_mlp_instability`.

The per-stave calibration asymmetry is real but only a partial explanation. It tracks pair instability better than it tracks the overall MLP sigma68; the dominant P03b failure remains run-dependent distribution shift in the waveform residual target, with B4/B6/B8 imbalance changing which pair is worst rather than producing a single persistent bad stave.

## Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/p03d_1781015093_954_4d504688_per_stave_mlp_failure.py --config configs/p03d_1781015093_954_4d504688.yaml
```

Artifacts: `reproduction_match_table.csv`, `p03b_reproduction_match_table.csv`, `heldout_run_summary.csv`, `per_stave_mlp_calibration.csv`, `per_run_mlp_calibration.csv`, `pair_method_summary.csv`, `asymmetry_diagnosis.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.
