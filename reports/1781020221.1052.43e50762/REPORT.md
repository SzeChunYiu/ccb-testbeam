# S05d: two-ended-safe correlated timing floor

- **Ticket:** 1781020221.1052.43e50762
- **Worker:** testbeam-laptop-2
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT under `data/root/root`; no Monte Carlo
- **Config:** `configs/s05d_1781020221_1052_43e50762_correlated_timing_floor.json`

## Question

Estimate the timing floor that remains correlated between the two ends of a downstream B-stave after applying only per-end, single-stave waveform corrections.

## Raw-ROOT reproduction gate

The S00 selected-pulse count was rebuilt from raw `h101/HRDv` before any modeling. The gate uses physical even B channels B2/B4/B6/B8, median baseline samples 0-3, and amplitude >1000 ADC.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total_selected_pulses              |         640737 |       640737 |       0 |           0 | True   |
| sample_i_analysis_selected_pulses  |         252266 |       252266 |       0 |           0 | True   |
| sample_ii_analysis_selected_pulses |         125096 |       125096 |       0 |           0 | True   |

Two-ended downstream event counts after requiring B4/B6/B8 even pulses and odd duplicate-readout amplitudes above threshold:

| quantity                            |   value |
|:------------------------------------|--------:|
| analysis_runs                       |      21 |
| complete_three_stave_two_end_events |    4470 |
| endpoint_rows                       |   95448 |

## Methods

Each endpoint is modeled independently (`B4/B6/B8` x `even/odd`). Odd duplicate-readout waveforms are sign-inverted before timing. Fitted correction targets are `CFD20 - train-run template phase` for the same endpoint only.

Traditional method: train-run median template phase matching, evaluated leave-one-run-out. ML method: histogram gradient boosting on normalized samples, amplitude, CFD summaries, and endpoint one-hot columns. Features exclude run id, event id, event order, other-stave timing, other-end timing, and event residuals.

For each held-out event, the corrected even and odd endpoint times are averaged per stave. Pair residuals among B4/B6/B8 estimate the two-ended spread. The endpoint difference within each stave estimates the uncorrelated per-end contribution; subtracting that contribution from the two-ended pair variance gives the correlated floor.

## Held-out Results

Per-run details are in `per_run_floor_metrics.csv`; the report keeps the run-level spread compact.

| method                     |   runs |   median_floor_ns |   min_floor_ns |   max_floor_ns |   total_pair_residuals |
|:---------------------------|-------:|------------------:|---------------:|---------------:|-----------------------:|
| ml_single_endpoint_proxy   |     21 |         0         |              0 |       0.654573 |                  21528 |
| traditional_template_phase |     21 |         0.0883883 |              0 |       0.661438 |                  21528 |

Pooled CIs resample held-out runs, not rows.

| method                     |   correlated_floor_sigma_ns |   correlated_floor_sigma_ns_ci_low |   correlated_floor_sigma_ns_ci_high |   twoended_pair_sigma68_ns |   twoended_pair_sigma68_ns_ci_low |   twoended_pair_sigma68_ns_ci_high |   mean_enddiff_sigma68_ns |   n_pair_residuals |
|:---------------------------|----------------------------:|-----------------------------------:|------------------------------------:|---------------------------:|----------------------------------:|-----------------------------------:|--------------------------:|-------------------:|
| cfd20_base                 |                    0.742249 |                           0.677267 |                            0.881517 |                    2.92952 |                           2.84957 |                            3.01033 |                  2.25575  |              21528 |
| traditional_template_phase |                    0.583626 |                           0.465128 |                            0.717095 |                    2.35476 |                           2.06746 |                            2.48929 |                  0.579566 |              21528 |
| ml_single_endpoint_proxy   |                    0.542019 |                           0.368094 |                            0.59083  |                    2.27756 |                           2.14978 |                            2.37599 |                  1.02305  |              21528 |
| ml_shuffled_target_control |                    0.722514 |                           0.651306 |                            0.846395 |                    2.92534 |                           2.84394 |                            3.0003  |                  2.33797  |              21528 |

## Leakage Audit

| model    | split   |   mean_rmse_ns |   max_rmse_ns |   total_endpoint_rows |
|:---------|:--------|---------------:|--------------:|----------------------:|
| ml_proxy | heldout |       0.848919 |      1.12451  |                 95448 |
| ml_proxy | train   |       0.809182 |      0.845739 |               1908960 |

| check                                            |   min |   median |   max |
|:-------------------------------------------------|------:|---------:|------:|
| features_include_cross_stave_or_cross_end_timing |     0 |        0 |     0 |
| fit_targets_include_event_residuals              |     0 |        0 |     0 |
| n_single_endpoint_features                       |    41 |       41 |    41 |
| train_heldout_event_id_overlap                   |     0 |        0 |     0 |
| train_heldout_run_overlap                        |     0 |        0 |     0 |

The shuffled-target ML control gives a correlated floor of 0.723 ns, compared with 0.542 ns for the real ML proxy. All run/event overlap and feature-exclusion checks are zero.

## Finding

The strong traditional per-end template correction gives a correlated two-ended floor of **0.584 ns** with run-bootstrap CI [0.465, 0.717] ns.
The ML single-endpoint proxy gives **0.542 ns** with CI [0.368, 0.591] ns.

Conclusion: `correlated_floor_estimated_with_no_detected_leakage`.

## Reproducibility

```bash
/home/billy/.tb-workers/testbeam-laptop-2/.venv/bin/python scripts/s05d_1781020221_1052_43e50762_correlated_timing_floor.py --config configs/s05d_1781020221_1052_43e50762_correlated_timing_floor.json
```

Artifacts are in this folder: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `analysis_event_counts.csv`, `per_run_floor_metrics.csv`, `pooled_run_bootstrap.csv`, `pair_residuals.csv`, `enddiff_residuals.csv`, `proxy_fit_metrics.csv`, `leakage_checks.csv`, and figures.
