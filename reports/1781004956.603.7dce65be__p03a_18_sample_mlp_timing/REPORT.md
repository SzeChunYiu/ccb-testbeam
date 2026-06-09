# Study report: P03a - 18-sample MLP timing versus S02 ridge-corrected CFD

- **Ticket:** 1781004956.603.7dce65be
- **Author:** testbeam-laptop-3
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** train runs 58-63; held-out run 65
- **Config:** `configs/p03a_18_sample_mlp_timing.yaml`

## Question

Can a tiny waveform-level MLP on the 18 normalized samples predict sub-sample timing better than the frozen S02 ridge-corrected CFD/template baseline without timing-label leakage?

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

The S02 held-out ridge-CFD number was then rebuilt from the same raw pass.

| method          |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   n_pair_residuals |
|:----------------|-------------:|---------:|----------:|--------------:|-------------------:|
| s02_ridge_cfd20 |      1.84611 |  1.45261 |   2.02735 |       1.7098  |                198 |
| template_phase  |      2.88915 |  2.63915 |   3.27718 |       2.57669 |                198 |
| cfd20_reference |      2.99339 |  2.65953 |   3.36005 |       2.74268 |                198 |

## Traditional frozen baseline

The strong traditional method is the previously reported S03a analytic amplitude-timewalk correction on S02 template phase, retrained only on runs 58-63 with the frozen candidate family.

| method            |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   n_pair_residuals |
|:------------------|-------------:|---------:|----------:|--------------:|-------------------:|
| analytic_timewalk |      1.49464 |  1.30186 |   1.66581 |       1.69913 |                198 |
| template_phase    |      2.88915 |  2.63915 |   3.27718 |       2.57669 |                198 |

## Waveform MLP

The selected MLP uses hidden width `32`, weight decay `0.001`, and `21` inputs: 18 normalized samples plus a stave one-hot intercept. It corrects `cfd20` residuals and predicts a per-pulse sigma through a Gaussian NLL head.

|   hidden |   weight_decay |   sigma68_ns |
|---------:|---------------:|-------------:|
|       32 |          0.001 |      1.80658 |
|       16 |          0.001 |      2.36439 |

## Held-out head-to-head

| method            |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   delta_vs_s02_ridge_ns |   delta_ci_low |   delta_ci_high |   n_pair_residuals |
|:------------------|-------------:|---------:|----------:|--------------:|------------------------:|---------------:|----------------:|-------------------:|
| analytic_timewalk |      1.49464 |  1.30186 |   1.66581 |       1.69913 |              -0.351474  |      -0.607594 |       0.0399996 |                198 |
| s02_ridge_cfd20   |      1.84611 |  1.45261 |   2.02735 |       1.7098  |               0         |       0        |       0         |                198 |
| mlp_waveform      |      1.92723 |  1.62267 |   2.26034 |       1.97864 |               0.0811193 |      -0.128773 |       0.44442   |                198 |
| template_phase    |      2.88915 |  2.63915 |   3.27718 |       2.57669 |               1.04304   |       0.702441 |       1.63137   |                198 |
| cfd20_reference   |      2.99339 |  2.65953 |   3.36005 |       2.74268 |               1.14727   |       0.72897  |       1.75378   |                198 |

## Sigma calibration and leakage checks

| scope                |   n |   pred_sigma_median_ns |   abs_error_median_ns |   pull_width_sigma68 |   pull_rms |
|:---------------------|----:|-----------------------:|----------------------:|---------------------:|-----------:|
| heldout_pulse_target | 198 |                2.01614 |              1.03227  |             0.497691 |   0.538937 |
| heldout_sigma_bin    |  50 |                1.68305 |              0.748292 |             0.628748 |   0.643075 |
| heldout_sigma_bin    |  49 |                1.93145 |              0.643942 |             0.691953 |   0.614443 |
| heldout_sigma_bin    |  49 |                2.20933 |              1.01462  |             0.535453 |   0.575208 |
| heldout_sigma_bin    |  50 |               20.0856  |              1.72032  |             0.110648 |   0.116769 |

| check                                       |   value | detail                                                                                                                             |
|:--------------------------------------------|--------:|:-----------------------------------------------------------------------------------------------------------------------------------|
| train_heldout_event_id_overlap              | 0       | must be zero                                                                                                                       |
| feature_audit                               | 0       | features are normalized 18-sample waveform plus stave one-hot; no run, event id, event order, other-stave time, or held-out target |
| shuffled_target_negative_control_sigma68_ns | 3.17379 | same architecture trained with shuffled train residual targets                                                                     |
| nominal_mlp_sigma68_ns                      | 1.92723 | held-out run metric for comparison to shuffled control                                                                             |

The split is by run. The MLP feature audit excludes run number, event identifier, event order, other-stave timing, pair residuals, and held-out targets. The shuffled-target negative control is included because the nominal MLP is competitive with the S02 ridge baseline.

## Verdict

`result.json` verdict: `mlp_does_not_beat_frozen_s02_ridge_or_analytic_baseline`. The MLP held-out sigma68 is `1.927 ns`; the frozen S02 ridge-CFD value is `1.846 ns`, and the strongest traditional analytic value is `1.495 ns`.

## Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/p03a_18_sample_mlp_timing.py --config configs/p03a_18_sample_mlp_timing.yaml
```

Artifacts: `reproduction_match_table.csv`, `frozen_s02_benchmark.csv`, `traditional_benchmark.csv`, `mlp_cv_scan.csv`, `head_to_head_benchmark.csv`, `mlp_sigma_calibration.csv`, `leakage_checks.csv`, figures, `result.json`, and `manifest.json`.
