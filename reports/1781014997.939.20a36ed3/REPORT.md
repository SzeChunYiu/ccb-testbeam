# Study report: P03e - stave-blind versus stave-aware waveform residual ablation

- **Ticket:** 1781014997.939.20a36ed3
- **Author:** testbeam-laptop-4
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** train runs 58-63; held-out run 65; grouped-run CV inside training
- **Config:** `configs/p03e_1781014997_939_20a36ed3.yaml`

## Question

After the P03c analytic timewalk correction, does explicit detector identity or scalar amplitude/shape information improve a waveform residual MLP, or does it mainly expose run/detector-label leakage risk?

## Raw-ROOT reproduction gate

The S00 selected-pulse count gate was rerun from raw ROOT before the ablation.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The P03c strict waveform residual number was then rebuilt before new variants were scored.

| quantity                                 |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| P03c strict waveform residual sigma68_ns |        1.44836 |      1.44836 |       0 |       1e-06 | True   |

## Methods

Traditional baseline: S03a analytic amplitude-timewalk correction on S02 template phase, trained only on runs 58-63.

ML variants: heteroskedastic MLPs trained on analytic residual targets. The strict variant uses only 18 normalized waveform samples; the other variants append stave one-hot, amplitude/shape scalars, or both. Hyperparameters are selected by grouped-run CV.

| variant                  |   hidden |   weight_decay |   sigma68_ns |   n_features |
|:-------------------------|---------:|---------------:|-------------:|-------------:|
| waveform_amp_shape       |       32 |          0.001 |      1.44451 |           29 |
| waveform_amp_shape       |       32 |          0.01  |      1.44485 |           29 |
| waveform_amp_shape       |       16 |          0.001 |      1.57288 |           29 |
| waveform_amp_shape       |       16 |          0.01  |      1.57421 |           29 |
| waveform_amp_shape_stave |       32 |          0.001 |      1.16593 |           32 |
| waveform_amp_shape_stave |       32 |          0.01  |      1.16625 |           32 |
| waveform_amp_shape_stave |       16 |          0.01  |      1.21172 |           32 |
| waveform_amp_shape_stave |       16 |          0.001 |      1.21342 |           32 |
| waveform_only            |       16 |          0.01  |      1.61055 |           18 |
| waveform_only            |       16 |          0.001 |      1.61072 |           18 |
| waveform_only            |       32 |          0.01  |      1.64785 |           18 |
| waveform_only            |       32 |          0.001 |      1.64898 |           18 |
| waveform_stave_onehot    |       32 |          0.001 |      1.20666 |           21 |
| waveform_stave_onehot    |       32 |          0.01  |      1.20914 |           21 |
| waveform_stave_onehot    |       16 |          0.01  |      1.27943 |           21 |
| waveform_stave_onehot    |       16 |          0.001 |      1.28983 |           21 |

## Held-out head-to-head

| method                        |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   delta_vs_analytic_ns |   delta_ci_low |   delta_ci_high |   n_pair_residuals |
|:------------------------------|-------------:|---------:|----------:|--------------:|-----------------------:|---------------:|----------------:|-------------------:|
| p03e_waveform_amp_shape_stave |      1.13024 | 0.921582 |   1.31011 |       1.22133 |             -0.364398  |      -0.603938 |      -0.124186  |                198 |
| p03e_waveform_stave_onehot    |      1.34808 | 1.19931  |   1.56692 |       1.33366 |             -0.146564  |      -0.352859 |       0.181483  |                198 |
| p03e_stave_offset_only        |      1.3543  | 1.01752  |   1.58987 |       1.39524 |             -0.140337  |      -0.503994 |       0.159163  |                198 |
| p03e_waveform_amp_shape       |      1.39683 | 1.2552   |   1.57424 |       1.40634 |             -0.0978052 |      -0.280683 |       0.108358  |                198 |
| p03e_waveform_only            |      1.44836 | 1.32145  |   1.66882 |       1.71718 |             -0.046284  |      -0.10623  |       0.0538174 |                198 |
| analytic_timewalk             |      1.49464 | 1.30661  |   1.66567 |       1.69913 |              0         |       0        |       0         |                198 |

## Calibration and leakage checks

| variant                  | scope                |   n |   pred_sigma_median_ns |   abs_error_median_ns |   pull_width_sigma68 |   pull_rms |
|:-------------------------|:---------------------|----:|-----------------------:|----------------------:|---------------------:|-----------:|
| waveform_only            | heldout_pulse_target | 198 |                2.1469  |              1.13813  |             0.694148 |   0.771516 |
| waveform_only            | heldout_sigma_bin    |  50 |                1.97305 |              1.33444  |             0.759718 |   0.807851 |
| waveform_only            | heldout_sigma_bin    |  49 |                2.08369 |              1.23441  |             0.785796 |   0.838444 |
| waveform_only            | heldout_sigma_bin    |  49 |                2.29774 |              1.13327  |             0.715099 |   0.801381 |
| waveform_only            | heldout_sigma_bin    |  50 |                3.98476 |              0.863933 |             0.37557  |   0.346744 |
| waveform_stave_onehot    | heldout_pulse_target | 198 |                1.43627 |              0.645503 |             0.693732 |   0.807392 |
| waveform_amp_shape       | heldout_pulse_target | 198 |                1.92469 |              1.19965  |             0.684658 |   0.753574 |
| waveform_amp_shape_stave | heldout_pulse_target | 198 |                1.4866  |              0.626401 |             0.558694 |   0.742275 |

| check                                       | variant                  |      value | detail                                                                                                                                          |
|:--------------------------------------------|:-------------------------|-----------:|:------------------------------------------------------------------------------------------------------------------------------------------------|
| train_heldout_event_id_overlap              | all                      |  0         | must be zero                                                                                                                                    |
| detector_label_only_guardrail_sigma68_ns    | stave_offset_only        |  1.3543    | train-run mean analytic residual per stave, applied to held-out run with no waveform samples                                                    |
| split_policy                                | all                      |  1         | all CV, tuning, and final scoring are grouped or split by run; held-out run is 65                                                               |
| feature_audit                               | waveform_only            | 18         | 18 normalized same-pulse waveform samples only; no run, event id, event order, stave id, amplitude scalar, other-stave time, or held-out target |
| too_good_trigger_delta_vs_analytic_ns       | waveform_only            | -0.046284  | negative values improve on analytic; shuffled-target control is required for every variant                                                      |
| shuffled_target_negative_control_sigma68_ns | waveform_only            |  1.48706   | same selected architecture trained with train residual targets shuffled within the run-split training pool                                      |
| feature_audit                               | waveform_stave_onehot    | 21         | same as blind variants, except explicit downstream stave one-hot is intentionally included                                                      |
| too_good_trigger_delta_vs_analytic_ns       | waveform_stave_onehot    | -0.146564  | negative values improve on analytic; shuffled-target control is required for every variant                                                      |
| shuffled_target_negative_control_sigma68_ns | waveform_stave_onehot    |  1.47905   | same selected architecture trained with train residual targets shuffled within the run-split training pool                                      |
| feature_audit                               | waveform_amp_shape       | 29         | no run, event id, event order, stave id, other-stave time, or held-out target                                                                   |
| too_good_trigger_delta_vs_analytic_ns       | waveform_amp_shape       | -0.0978052 | negative values improve on analytic; shuffled-target control is required for every variant                                                      |
| shuffled_target_negative_control_sigma68_ns | waveform_amp_shape       |  1.45802   | same selected architecture trained with train residual targets shuffled within the run-split training pool                                      |
| feature_audit                               | waveform_amp_shape_stave | 32         | same as blind variants, except explicit downstream stave one-hot is intentionally included                                                      |
| too_good_trigger_delta_vs_analytic_ns       | waveform_amp_shape_stave | -0.364398  | negative values improve on analytic; shuffled-target control is required for every variant                                                      |
| shuffled_target_negative_control_sigma68_ns | waveform_amp_shape_stave |  1.50205   | same selected architecture trained with train residual targets shuffled within the run-split training pool                                      |

## Verdict

`result.json` verdict: `large_ml_gain_requires_followup_even_after_negative_controls`. Best held-out ML variant is `waveform_amp_shape_stave` at `1.130 ns`; analytic baseline is `1.495 ns`.

## Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/p03e_stave_blind_residual_ablation.py --config configs/p03e_1781014997_939_20a36ed3.yaml
```

Artifacts: `reproduction_match_table.csv`, `p03c_reproduction_benchmark.csv`, `p03e_cv_scan.csv`, `p03e_calibration.csv`, `head_to_head_benchmark.csv`, `heldout_pair_residuals.csv`, `leakage_checks.csv`, `input_sha256.csv`, `result.json`, and `manifest.json`.
