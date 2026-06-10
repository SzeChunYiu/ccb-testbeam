# Study report: P03c - waveform-only CNN versus P03b MLP LORO

- **Ticket:** 1781015093.889.4aa141a8
- **Author:** testbeam-laptop-2
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one run out across runs 58, 59, 60, 61, 62, 63, and 65
- **Config:** `configs/p03c_1781015093_889_4aa141a8_cnn_vs_mlp_loro.yaml`

## Question

Does a small waveform-only 1D CNN improve on the P03b waveform MLP when both are trained with the same leave-one-run-out gates and only normalized same-pulse waveform samples plus stave identity?

## Raw-ROOT reproduction gate

The selected-pulse count gate was rerun from raw ROOT before model training.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Methods

Traditional baseline: S03a analytic amplitude-timewalk correction on S02 template phase, refit inside each training-run fold.

ML baselines: the P03b heteroskedastic MLP and a two-layer 1D CNN. Both correct CFD20 residual targets, use only 18 normalized samples plus downstream stave one-hot, and select hyperparameters by grouped run CV inside each training split.

|   heldout_run | traditional_base_method   | analytic_candidate   |   analytic_alpha |   mlp_hidden |   mlp_weight_decay |   mlp_n_features |   cnn_channels |   cnn_weight_decay |   cnn_n_features |
|--------------:|:--------------------------|:---------------------|-----------------:|-------------:|-------------------:|-----------------:|---------------:|-------------------:|-----------------:|
|            58 | template_phase            | amp_only             |              100 |           32 |              0.001 |               21 |              8 |              0.001 |               21 |
|            59 | template_phase            | amp_only             |              100 |           32 |              0.001 |               21 |              8 |              0.001 |               21 |
|            60 | template_phase            | amp_only             |              100 |           32 |              0.001 |               21 |              8 |              0.001 |               21 |
|            61 | template_phase            | amp_only             |              100 |           32 |              0.001 |               21 |              8 |              0.001 |               21 |
|            62 | template_phase            | amp_only             |              100 |           32 |              0.001 |               21 |              8 |              0.001 |               21 |
|            63 | template_phase            | amp_only             |              100 |           32 |              0.001 |               21 |              8 |              0.001 |               21 |
|            65 | template_phase            | amp_only             |              100 |           32 |              0.001 |               21 |              8 |              0.001 |               21 |

## Held-out head-to-head

|   heldout_run | method            |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   delta_vs_baseline_ns |   delta_ci_low |   delta_ci_high |   n_pair_residuals |
|--------------:|:------------------|-------------:|---------:|----------:|--------------:|-----------------------:|---------------:|----------------:|-------------------:|
|            58 | analytic_timewalk |      1.18748 |  1.13497 |   1.40746 |       2.67793 |              0         |     0          |       0         |                219 |
|            58 | mlp_waveform      |      1.88783 |  1.58906 |   2.21722 |       4.64524 |              0.700342  |     0.328208   |       1.03461   |                219 |
|            58 | s02_ridge_cfd20   |      1.91964 |  1.6472  |   2.14777 |       4.81256 |              0.732152  |     0.407507   |       0.967283  |                219 |
|            58 | cnn_waveform      |      2.33071 |  1.9973  |   2.56387 |       4.4056  |              1.14322   |     0.790022   |       1.35351   |                219 |
|            58 | cfd20_reference   |      3.11542 |  2.89913 |   3.35767 |       4.8861  |              1.92794   |     1.6346     |       2.15604   |                219 |
|            59 | analytic_timewalk |      1.45871 |  1.38881 |   1.5303  |       2.54019 |              0         |     0          |       0         |               2289 |
|            59 | mlp_waveform      |      1.71108 |  1.64268 |   1.77556 |       5.4455  |              0.252373  |     0.169313   |       0.335678  |               2289 |
|            59 | s02_ridge_cfd20   |      1.88049 |  1.81335 |   1.96379 |       5.38597 |              0.421779  |     0.327123   |       0.527842  |               2289 |
|            59 | cnn_waveform      |      2.25456 |  2.18083 |   2.3719  |       5.49253 |              0.795849  |     0.683102   |       0.935691  |               2289 |
|            59 | cfd20_reference   |      3.19039 |  3.09366 |   3.27072 |       5.79544 |              1.73169   |     1.59856    |       1.84349   |               2289 |
|            60 | analytic_timewalk |      1.3437  |  1.27872 |   1.40735 |       2.39529 |              0         |     0          |       0         |               2424 |
|            60 | mlp_waveform      |      1.60696 |  1.53092 |   1.6737  |       6.62785 |              0.263251  |     0.173952   |       0.333912  |               2424 |
|            60 | s02_ridge_cfd20   |      1.81993 |  1.74446 |   1.9126  |       6.47156 |              0.476224  |     0.368235   |       0.597742  |               2424 |
|            60 | cnn_waveform      |      2.13291 |  2.05806 |   2.23689 |       6.98903 |              0.789209  |     0.690018   |       0.91552   |               2424 |
|            60 | cfd20_reference   |      3.13862 |  3.0572  |   3.22642 |       7.26201 |              1.79491   |     1.70059    |       1.90693   |               2424 |
|            61 | cnn_waveform      |      2.03459 |  1.96562 |   2.12715 |       6.36089 |             -0.0953764 |    -0.20907    |       0.0962689 |               2799 |
|            61 | mlp_waveform      |      2.11367 |  2.04264 |   2.18708 |       6.24534 |             -0.0162905 |    -0.111109   |       0.133852  |               2799 |
|            61 | analytic_timewalk |      2.12996 |  1.98455 |   2.21051 |       3.00806 |              0         |     0          |       0         |               2799 |
|            61 | s02_ridge_cfd20   |      2.24243 |  2.15143 |   2.33072 |       6.15879 |              0.112469  |    -0.00770844 |       0.301254  |               2799 |
|            61 | cfd20_reference   |      2.91408 |  2.8428  |   2.99328 |       6.59866 |              0.784119  |     0.673066   |       0.968073  |               2799 |
|            62 | analytic_timewalk |      1.469   |  1.40577 |   1.51714 |       2.58419 |              0         |     0          |       0         |               2421 |
|            62 | mlp_waveform      |      1.74331 |  1.676   |   1.81461 |       4.51535 |              0.274307  |     0.20698    |       0.358953  |               2421 |
|            62 | s02_ridge_cfd20   |      1.86001 |  1.78242 |   1.95734 |       4.61606 |              0.391008  |     0.294736   |       0.493701  |               2421 |
|            62 | cnn_waveform      |      2.49083 |  2.3857  |   2.57689 |       4.60693 |              1.02182   |     0.918316   |       1.1287    |               2421 |
|            62 | cfd20_reference   |      3.23169 |  3.14072 |   3.32347 |       4.95545 |              1.76268   |     1.6567     |       1.86888   |               2421 |
|            63 | analytic_timewalk |      1.39132 |  1.28795 |   1.46912 |       2.62807 |              0         |     0          |       0         |               1110 |
|            63 | mlp_waveform      |      1.6482  |  1.52865 |   1.75777 |       6.00255 |              0.256875  |     0.126381   |       0.389968  |               1110 |
|            63 | s02_ridge_cfd20   |      1.76984 |  1.6117  |   1.91402 |       5.83286 |              0.378518  |     0.213255   |       0.547067  |               1110 |
|            63 | cnn_waveform      |      2.52819 |  2.41202 |   2.62576 |       6.32527 |              1.13687   |     0.996911   |       1.27314   |               1110 |
|            63 | cfd20_reference   |      3.40351 |  3.29508 |   3.52455 |       6.58303 |              2.01219   |     1.87818    |       2.18438   |               1110 |
|            65 | analytic_timewalk |      1.49464 |  1.32219 |   1.66053 |       1.69913 |              0         |     0          |       0         |                198 |
|            65 | s02_ridge_cfd20   |      1.84611 |  1.44371 |   2.03472 |       1.7098  |              0.351474  |     0.0191753  |       0.562536  |                198 |
|            65 | mlp_waveform      |      1.92723 |  1.60242 |   2.28897 |       1.97864 |              0.432593  |     0.0956382  |       0.795593  |                198 |
|            65 | cnn_waveform      |      2.14967 |  1.77597 |   2.44781 |       2.00954 |              0.655034  |     0.237114   |       0.990406  |                198 |
|            65 | cfd20_reference   |      2.99339 |  2.67687 |   3.38387 |       2.74268 |              1.49875   |     1.17452    |       1.96493   |                198 |

## Stability summary

| method            |   mean_sigma68_ns |   median_sigma68_ns |   min_sigma68_ns |   max_sigma68_ns |   n_heldout_runs |
|:------------------|------------------:|--------------------:|-----------------:|-----------------:|-----------------:|
| analytic_timewalk |           1.4964  |             1.45871 |          1.18748 |          2.12996 |                7 |
| mlp_waveform      |           1.80547 |             1.74331 |          1.60696 |          2.11367 |                7 |
| s02_ridge_cfd20   |           1.90549 |             1.86001 |          1.76984 |          2.24243 |                7 |
| cnn_waveform      |           2.27449 |             2.25456 |          2.03459 |          2.52819 |                7 |
| cfd20_reference   |           3.14101 |             3.13862 |          2.91408 |          3.40351 |                7 |

|   heldout_run | best_method       |   best_sigma68_ns |   cnn_minus_mlp_ns |   cnn_minus_analytic_ns |   mlp_minus_analytic_ns |
|--------------:|:------------------|------------------:|-------------------:|------------------------:|------------------------:|
|            58 | analytic_timewalk |           1.18748 |          0.442881  |               1.14322   |               0.700342  |
|            59 | analytic_timewalk |           1.45871 |          0.543476  |               0.795849  |               0.252373  |
|            60 | analytic_timewalk |           1.3437  |          0.525958  |               0.789209  |               0.263251  |
|            61 | cnn_waveform      |           2.03459 |         -0.0790859 |              -0.0953764 |              -0.0162905 |
|            62 | analytic_timewalk |           1.469   |          0.747513  |               1.02182   |               0.274307  |
|            63 | analytic_timewalk |           1.39132 |          0.879993  |               1.13687   |               0.256875  |
|            65 | analytic_timewalk |           1.49464 |          0.222441  |               0.655034  |               0.432593  |

## Leakage checks

| model        | check                                       |   value | detail                                                                                                                                                                             |   heldout_run |
|:-------------|:--------------------------------------------|--------:|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------:|
| all          | feature_audit                               | 0       | inputs are normalized same-pulse 18-sample waveform plus downstream stave one-hot only; no run id, event id, event order, amplitude scalar, other-stave timing, or held-out target |            58 |
| all          | train_heldout_event_id_overlap              | 0       | must be zero                                                                                                                                                                       |            58 |
| cnn_waveform | nominal_cnn_sigma68_ns                      | 2.33071 | held-out run metric for comparison to shuffled control                                                                                                                             |            58 |
| cnn_waveform | shuffled_target_negative_control_sigma68_ns | 3.0793  | same CNN trained with shuffled train residual targets                                                                                                                              |            58 |
| mlp_waveform | nominal_mlp_sigma68_ns                      | 1.88783 | held-out run metric for comparison to shuffled control                                                                                                                             |            58 |
| mlp_waveform | shuffled_target_negative_control_sigma68_ns | 3.19475 | same architecture trained with shuffled train residual targets                                                                                                                     |            58 |
| all          | feature_audit                               | 0       | inputs are normalized same-pulse 18-sample waveform plus downstream stave one-hot only; no run id, event id, event order, amplitude scalar, other-stave timing, or held-out target |            59 |
| all          | train_heldout_event_id_overlap              | 0       | must be zero                                                                                                                                                                       |            59 |
| cnn_waveform | nominal_cnn_sigma68_ns                      | 2.25456 | held-out run metric for comparison to shuffled control                                                                                                                             |            59 |
| cnn_waveform | shuffled_target_negative_control_sigma68_ns | 3.13817 | same CNN trained with shuffled train residual targets                                                                                                                              |            59 |
| mlp_waveform | nominal_mlp_sigma68_ns                      | 1.71108 | held-out run metric for comparison to shuffled control                                                                                                                             |            59 |
| mlp_waveform | shuffled_target_negative_control_sigma68_ns | 3.16297 | same architecture trained with shuffled train residual targets                                                                                                                     |            59 |
| all          | feature_audit                               | 0       | inputs are normalized same-pulse 18-sample waveform plus downstream stave one-hot only; no run id, event id, event order, amplitude scalar, other-stave timing, or held-out target |            60 |
| all          | train_heldout_event_id_overlap              | 0       | must be zero                                                                                                                                                                       |            60 |
| cnn_waveform | nominal_cnn_sigma68_ns                      | 2.13291 | held-out run metric for comparison to shuffled control                                                                                                                             |            60 |
| cnn_waveform | shuffled_target_negative_control_sigma68_ns | 3.11657 | same CNN trained with shuffled train residual targets                                                                                                                              |            60 |
| mlp_waveform | nominal_mlp_sigma68_ns                      | 1.60696 | held-out run metric for comparison to shuffled control                                                                                                                             |            60 |
| mlp_waveform | shuffled_target_negative_control_sigma68_ns | 3.14377 | same architecture trained with shuffled train residual targets                                                                                                                     |            60 |
| all          | feature_audit                               | 0       | inputs are normalized same-pulse 18-sample waveform plus downstream stave one-hot only; no run id, event id, event order, amplitude scalar, other-stave timing, or held-out target |            61 |
| all          | train_heldout_event_id_overlap              | 0       | must be zero                                                                                                                                                                       |            61 |
| cnn_waveform | nominal_cnn_sigma68_ns                      | 2.03459 | held-out run metric for comparison to shuffled control                                                                                                                             |            61 |
| cnn_waveform | shuffled_target_negative_control_sigma68_ns | 2.90113 | same CNN trained with shuffled train residual targets                                                                                                                              |            61 |
| mlp_waveform | nominal_mlp_sigma68_ns                      | 2.11367 | held-out run metric for comparison to shuffled control                                                                                                                             |            61 |
| mlp_waveform | shuffled_target_negative_control_sigma68_ns | 2.91149 | same architecture trained with shuffled train residual targets                                                                                                                     |            61 |
| all          | feature_audit                               | 0       | inputs are normalized same-pulse 18-sample waveform plus downstream stave one-hot only; no run id, event id, event order, amplitude scalar, other-stave timing, or held-out target |            62 |
| all          | train_heldout_event_id_overlap              | 0       | must be zero                                                                                                                                                                       |            62 |
| cnn_waveform | nominal_cnn_sigma68_ns                      | 2.49083 | held-out run metric for comparison to shuffled control                                                                                                                             |            62 |
| cnn_waveform | shuffled_target_negative_control_sigma68_ns | 3.20597 | same CNN trained with shuffled train residual targets                                                                                                                              |            62 |
| mlp_waveform | nominal_mlp_sigma68_ns                      | 1.74331 | held-out run metric for comparison to shuffled control                                                                                                                             |            62 |
| mlp_waveform | shuffled_target_negative_control_sigma68_ns | 3.23319 | same architecture trained with shuffled train residual targets                                                                                                                     |            62 |
| all          | feature_audit                               | 0       | inputs are normalized same-pulse 18-sample waveform plus downstream stave one-hot only; no run id, event id, event order, amplitude scalar, other-stave timing, or held-out target |            63 |
| all          | train_heldout_event_id_overlap              | 0       | must be zero                                                                                                                                                                       |            63 |
| cnn_waveform | nominal_cnn_sigma68_ns                      | 2.52819 | held-out run metric for comparison to shuffled control                                                                                                                             |            63 |
| cnn_waveform | shuffled_target_negative_control_sigma68_ns | 3.37003 | same CNN trained with shuffled train residual targets                                                                                                                              |            63 |
| mlp_waveform | nominal_mlp_sigma68_ns                      | 1.6482  | held-out run metric for comparison to shuffled control                                                                                                                             |            63 |
| mlp_waveform | shuffled_target_negative_control_sigma68_ns | 3.48094 | same architecture trained with shuffled train residual targets                                                                                                                     |            63 |
| all          | feature_audit                               | 0       | inputs are normalized same-pulse 18-sample waveform plus downstream stave one-hot only; no run id, event id, event order, amplitude scalar, other-stave timing, or held-out target |            65 |
| all          | train_heldout_event_id_overlap              | 0       | must be zero                                                                                                                                                                       |            65 |
| cnn_waveform | nominal_cnn_sigma68_ns                      | 2.14967 | held-out run metric for comparison to shuffled control                                                                                                                             |            65 |
| cnn_waveform | shuffled_target_negative_control_sigma68_ns | 2.97974 | same CNN trained with shuffled train residual targets                                                                                                                              |            65 |
| mlp_waveform | nominal_mlp_sigma68_ns                      | 1.92723 | held-out run metric for comparison to shuffled control                                                                                                                             |            65 |
| mlp_waveform | shuffled_target_negative_control_sigma68_ns | 3.17379 | same architecture trained with shuffled train residual targets                                                                                                                     |            65 |

No run id, event id, event order, amplitude scalar, other-stave timing feature, pair residual, or held-out target enters either learned model. Shuffled-target controls are worse than nominal for both learned models in every fold.

## Verdict

`result.json` verdict: `cnn_does_not_beat_p03b_mlp_or_analytic_timewalk`. Mean sigma68 is `2.274 ns` for CNN, `1.805 ns` for P03b MLP, and `1.496 ns` for the analytic traditional baseline.

## Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/p03c_1781015093_889_4aa141a8_cnn_vs_mlp_loro.py --config configs/p03c_1781015093_889_4aa141a8_cnn_vs_mlp_loro.yaml
```

Artifacts: `reproduction_match_table.csv`, `heldout_run_summary.csv`, `heldout_pair_residuals.csv`, `pooled_summary.csv`, `winner_by_run.csv`, `leakage_checks.csv`, CV/calibration tables, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.
