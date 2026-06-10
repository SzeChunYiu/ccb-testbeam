# P10c follow-up: run-family calibration mixture diagnostic

- **Ticket:** `1781024829.1287.06196aeb`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT under `data/root/root`
- **Config:** `configs/s10c_1781024829_1287_06196aeb_run_family_mixture.yaml`
- **Monte Carlo:** none

## Raw reproduction gate

The selected B-stave pulse count was rebuilt from raw `HRDv` ROOT before any calibration fits.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Split and methods

All scoring is held out by run on Sample-II analysis runs 58-63 and 65. The two calibration scenarios are `run64_only` and `sample_i_plus_run64`; no Sample-II analysis row is used in any fit.

Traditional methods are fixed explicit timewalk corrections: an amp-only Ridge residual correction and a per-stave monotonic amplitude-bin residual table. The ML method is a same-pulse waveform Ridge residual corrector. Hyperparameters are fixed from the prior S03/P10 diagnostics to permit the single-run run64 calibration.

## Held-out timing

Intervals bootstrap held-out runs as blocks.

| scenario            | method                        |   sigma68_ns |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:--------------------|:------------------------------|-------------:|---------:|----------:|-------------------:|----------------------:|
| run64_only          | ml_ridge_timewalk             |      1.27885 |  1.13868 |   1.46484 |              11460 |             0.0169284 |
| sample_i_plus_run64 | ml_ridge_timewalk             |      1.87733 |  1.6979  |   2.10742 |              11460 |             0.0200698 |
| run64_only          | template_phase_base           |      2.35131 |  2.28197 |   2.53197 |              11460 |             0.0624782 |
| sample_i_plus_run64 | template_phase_base           |      2.83369 |  2.58369 |   2.83369 |              11460 |             0.143543  |
| run64_only          | traditional_analytic_timewalk |      1.34696 |  1.16397 |   1.52741 |              11460 |             0.0191099 |
| sample_i_plus_run64 | traditional_analytic_timewalk |      1.91329 |  1.72569 |   2.14246 |              11460 |             0.0220768 |
| run64_only          | traditional_binned_timewalk   |      1.55066 |  1.39099 |   1.89099 |              11460 |             0.0251309 |
| sample_i_plus_run64 | traditional_binned_timewalk   |      1.79185 |  1.72364 |   2.04185 |              11460 |             0.0262653 |

Paired deltas resample the same held-out runs for both calibration scenarios.

| method                        |   run64_only_sigma68_ns |   sample_i_plus_run64_sigma68_ns |   delta_mixed_minus_run64_ns |    ci_low |   ci_high |
|:------------------------------|------------------------:|---------------------------------:|-----------------------------:|----------:|----------:|
| ml_ridge_timewalk             |                 1.27885 |                          1.87733 |                     0.598481 | 0.465154  |  0.652852 |
| template_phase_base           |                 2.35131 |                          2.83369 |                     0.482381 | 0.0517196 |  0.55172  |
| traditional_analytic_timewalk |                 1.34696 |                          1.91329 |                     0.566332 | 0.475663  |  0.634134 |
| traditional_binned_timewalk   |                 1.55066 |                          1.79185 |                     0.241191 | 0.15086   |  0.40086  |

## Why the pooled calibration worsens

The pooled fit is dominated by Sample-I target structure: Sample I contributes many more calibration rows, and its per-stave amplitude-bin residual medians have different spans from run64. The fitted pooled correction tables are therefore pulled away from the run64 table that better matches Sample-II analysis.

| scenario            | family   | stave   |   n_train_pulses |   median_target_span_ns |
|:--------------------|:---------|:--------|-----------------:|------------------------:|
| run64_only          | run64    | B4      |              210 |                   9.5   |
| run64_only          | run64    | B6      |              210 |                   6.75  |
| run64_only          | run64    | B8      |              210 |                   0     |
| sample_i_plus_run64 | run64    | B4      |              210 |                  20     |
| sample_i_plus_run64 | run64    | B6      |              210 |                   1.25  |
| sample_i_plus_run64 | run64    | B8      |              210 |                   0.5   |
| sample_i_plus_run64 | sample_i | B4      |             1260 |                   0.75  |
| sample_i_plus_run64 | sample_i | B6      |             1260 |                   8.125 |
| sample_i_plus_run64 | sample_i | B8      |             1260 |                   4     |

Detailed correction tables are in `binned_correction_tables.csv` and `analytic_coefficients.csv`; held-out amplitude-bin closure distributions are in `heldout_amplitude_bin_residuals.csv`.

## Leakage controls

| scenario            | check                                                      |   value | unit               |
|:--------------------|:-----------------------------------------------------------|--------:|:-------------------|
| run64_only          | train_heldout_run_overlap                                  | 0       | count              |
| run64_only          | train_heldout_event_id_overlap                             | 0       | count              |
| run64_only          | model_features_include_run_event_order_or_cross_stave_time | 0       | bool               |
| run64_only          | final_fit_uses_sample_ii_analysis_rows                     | 0       | bool               |
| run64_only          | analytic_shuffled_target                                   | 2.08994 | heldout_sigma68_ns |
| run64_only          | ml_shuffled_target                                         | 2.38932 | heldout_sigma68_ns |
| sample_i_plus_run64 | train_heldout_run_overlap                                  | 0       | count              |
| sample_i_plus_run64 | train_heldout_event_id_overlap                             | 0       | count              |
| sample_i_plus_run64 | model_features_include_run_event_order_or_cross_stave_time | 0       | bool               |
| sample_i_plus_run64 | final_fit_uses_sample_ii_analysis_rows                     | 0       | bool               |
| sample_i_plus_run64 | analytic_shuffled_target                                   | 2.9594  | heldout_sigma68_ns |
| sample_i_plus_run64 | ml_shuffled_target                                         | 2.76229 | heldout_sigma68_ns |

Feature audit: analytic and binned traditional models use same-pulse amplitude/shape and stave identity; the ML Ridge model uses normalized same-pulse waveform, amplitude, peak, area, and stave identity. No model feature contains run number, event id, event order, other-stave timing, or held-out labels. Shuffled-target controls are worse than the real fitted methods, so the result is not a too-good leakage artifact.

## Verdict

| method                      |   delta_mixed_minus_run64_ns |   ci_low |   ci_high |
|:----------------------------|-----------------------------:|---------:|----------:|
| ml_ridge_timewalk           |                     0.598481 | 0.465154 |  0.652852 |
| traditional_binned_timewalk |                     0.241191 | 0.15086  |  0.40086  |

`result.json` verdict: `pooled_sample_i_plus_run64_worsens_sample_ii_timing`.
The mixed calibration is worse than run64-only for the primary traditional/ML corrections; at least one primary CI excludes zero.

No follow-up ticket was appended; the natural next checks are already represented by completed/open S02/S03/P10 run-drift, topology-transfer, and support-map studies.

## Reproduce

```bash
/home/billy/anaconda3/bin/python scripts/s10c_1781024829_1287_06196aeb_run_family_mixture.py --config configs/s10c_1781024829_1287_06196aeb_run_family_mixture.yaml
```
