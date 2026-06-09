# Study report: P03c - CNN versus MLP timing with analytic residual targets

- **Ticket:** 1781009029.1288.7e78286e
- **Author:** testbeam-laptop-3
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** train runs 58-63; held-out run 65
- **Config:** `configs/p03c_cnn_vs_mlp_analytic_residual.yaml`

## Question

Does a tiny 1D CNN add held-out timing information beyond the P03a MLP architecture when both see only normalized waveform samples and correct residuals left by the analytic timewalk baseline?

## Raw-ROOT reproduction gate

The S00 selected-pulse count gate was rerun from raw ROOT before timing work.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The prior P03a waveform-MLP number was then rebuilt before the P03c models.

| method            |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   n_pair_residuals |
|:------------------|-------------:|---------:|----------:|--------------:|-------------------:|
| analytic_timewalk |      1.49464 |  1.30661 |   1.66567 |       1.69913 |                198 |
| s02_ridge_cfd20   |      1.84611 |  1.45335 |   2.0251  |       1.7098  |                198 |
| p03a_mlp_waveform |      1.92723 |  1.60756 |   2.27724 |       1.97864 |                198 |

P03a MLP reproduction used hidden `32`, weight decay `0.001`, and `21` inputs.

## Methods

Traditional baseline: S03a analytic amplitude-timewalk correction on S02 template phase, trained only on runs 58-63.

ML methods: the P03a heteroskedastic MLP architecture and a tiny two-layer 1D CNN. Both use only the 18 same-pulse waveform samples divided by pulse amplitude, target analytic-timewalk residuals on train runs, and are selected by grouped run CV.

| model                 |   size |   weight_decay |   sigma68_ns |
|:----------------------|-------:|---------------:|-------------:|
| cnn_analytic_residual |      4 |          0.001 |      1.59065 |
| cnn_analytic_residual |      4 |          0.01  |      1.59124 |
| cnn_analytic_residual |      8 |          0.01  |      1.61313 |
| cnn_analytic_residual |      8 |          0.001 |      1.61368 |
| mlp_analytic_residual |     16 |          0.01  |      1.61055 |
| mlp_analytic_residual |     16 |          0.001 |      1.61072 |
| mlp_analytic_residual |     32 |          0.01  |      1.64785 |
| mlp_analytic_residual |     32 |          0.001 |      1.64898 |

## Held-out head-to-head

| method                |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   delta_vs_analytic_ns |   delta_ci_low |   delta_ci_high |   n_pair_residuals |
|:----------------------|-------------:|---------:|----------:|--------------:|-----------------------:|---------------:|----------------:|-------------------:|
| mlp_analytic_residual |      1.44836 |  1.32145 |   1.66882 |       1.71718 |            -0.046284   |    -0.10623    |      0.0538174  |                198 |
| analytic_timewalk     |      1.49464 |  1.30661 |   1.66567 |       1.69913 |             0          |     0          |      0          |                198 |
| cnn_analytic_residual |      1.49705 |  1.30734 |   1.66656 |       1.70009 |             0.00240521 |    -0.00238877 |      0.00740546 |                198 |
| s02_ridge_cfd20       |      1.84611 |  1.45335 |   2.0251  |       1.7098  |             0.351474   |    -0.0346031  |      0.605456   |                198 |
| p03a_mlp_waveform     |      1.92723 |  1.60756 |   2.27724 |       1.97864 |             0.432593   |     0.110413   |      0.857973   |                198 |

## Calibration and leakage checks

| model                 | scope                |   n |   pred_sigma_median_ns |   abs_error_median_ns |   pull_width_sigma68 |   pull_rms |
|:----------------------|:---------------------|----:|-----------------------:|----------------------:|---------------------:|-----------:|
| mlp_analytic_residual | heldout_pulse_target | 198 |                2.1469  |              1.13813  |             0.694148 |   0.771516 |
| mlp_analytic_residual | heldout_sigma_bin    |  50 |                1.97305 |              1.33444  |             0.759718 |   0.807851 |
| mlp_analytic_residual | heldout_sigma_bin    |  49 |                2.08369 |              1.23441  |             0.785796 |   0.838444 |
| mlp_analytic_residual | heldout_sigma_bin    |  49 |                2.29774 |              1.13327  |             0.715099 |   0.801381 |
| mlp_analytic_residual | heldout_sigma_bin    |  50 |                3.98476 |              0.863933 |             0.37557  |   0.346744 |
| cnn_analytic_residual | heldout_pulse_target | 198 |                2.33958 |              1.17923  |             0.638256 |   0.723853 |
| cnn_analytic_residual | heldout_sigma_bin    |  50 |                2.18994 |              1.24876  |             0.832382 |   0.877424 |
| cnn_analytic_residual | heldout_sigma_bin    |  49 |                2.27102 |              1.29307  |             0.761693 |   0.751258 |
| cnn_analytic_residual | heldout_sigma_bin    |  49 |                2.48915 |              1.0942   |             0.622386 |   0.716075 |
| cnn_analytic_residual | heldout_sigma_bin    |  50 |                2.91717 |              1.14111  |             0.558102 |   0.47061  |

| check                                       | model                 |   value | detail                                                                                                                                          |
|:--------------------------------------------|:----------------------|--------:|:------------------------------------------------------------------------------------------------------------------------------------------------|
| train_heldout_event_id_overlap              | all                   | 0       | must be zero                                                                                                                                    |
| feature_audit                               | all                   | 0       | 18 normalized same-pulse waveform samples only; no run, event id, event order, stave id, amplitude scalar, other-stave time, or held-out target |
| shuffled_target_negative_control_sigma68_ns | mlp_analytic_residual | 1.48706 | same architecture trained with shuffled train residual targets                                                                                  |
| nominal_sigma68_ns                          | mlp_analytic_residual | 1.44836 | held-out run metric for comparison to shuffled control                                                                                          |
| shuffled_target_negative_control_sigma68_ns | cnn_analytic_residual | 1.48098 | same architecture trained with shuffled train residual targets                                                                                  |
| nominal_sigma68_ns                          | cnn_analytic_residual | 1.49705 | held-out run metric for comparison to shuffled control                                                                                          |

The split is by run. The feature audit excludes run number, event identifier, event order, stave id, explicit amplitude scalars, other-stave timing, pair residuals, and held-out targets. Shuffled-target controls were run for both learned models.

## Verdict

`result.json` verdict: `cnn_does_not_add_to_mlp_or_analytic_baseline`. The CNN held-out sigma68 is `1.497 ns`, the P03c MLP is `1.448 ns`, and the analytic traditional baseline is `1.495 ns`.

## Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/p03c_cnn_vs_mlp_analytic_residual.py --config configs/p03c_cnn_vs_mlp_analytic_residual.yaml
```

Artifacts: `reproduction_match_table.csv`, `p03a_reproduction_benchmark.csv`, `p03c_cv_scan.csv`, `p03c_calibration.csv`, `head_to_head_benchmark.csv`, `heldout_pair_residuals.csv`, `leakage_checks.csv`, figures, `result.json`, and `manifest.json`.
