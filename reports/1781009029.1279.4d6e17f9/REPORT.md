# Study report: P03b - leave-one-run-out waveform MLP timing stability

- **Ticket:** 1781009029.1279.4d6e17f9
- **Author:** testbeam-laptop-2
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one run out across runs 58, 59, 60, 61, 62, 63, and 65
- **Config:** `configs/p03b_leave_one_run_waveform_mlp_timing.yaml`

## Question

Is the P03a negative MLP result a run-65 artifact, or does it persist when each sample-II analysis run is held out in turn?

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

Before the leave-one-run-out scan, the P03a run-65 benchmark number was reproduced from the same raw pass and split.

| method            |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   n_pair_residuals |
|:------------------|-------------:|---------:|----------:|--------------:|-------------------:|
| analytic_timewalk |      1.49464 |  1.30186 |   1.66581 |       1.69913 |                198 |
| s02_ridge_cfd20   |      1.84611 |  1.45261 |   2.02735 |       1.7098  |                198 |
| mlp_waveform      |      1.92723 |  1.62267 |   2.26034 |       1.97864 |                198 |
| template_phase    |      2.88915 |  2.63915 |   3.27718 |       2.57669 |                198 |
| cfd20_reference   |      2.99339 |  2.65953 |   3.36005 |       2.74268 |                198 |

## Leave-one-run-out head-to-head

|   heldout_run | method            |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   delta_vs_s02_ridge_ns |   delta_ci_low |   delta_ci_high |   n_pair_residuals |
|--------------:|:------------------|-------------:|---------:|----------:|--------------:|------------------------:|---------------:|----------------:|-------------------:|
|            58 | analytic_timewalk |      1.18748 |  1.13775 |   1.40035 |       2.67793 |              -0.732152  |      -1.00096  |      -0.413092  |                219 |
|            58 | mlp_waveform      |      1.88783 |  1.6007  |   2.22393 |       4.64524 |              -0.0318095 |      -0.431683 |       0.357014  |                219 |
|            58 | s02_ridge_cfd20   |      1.91964 |  1.65636 |   2.17185 |       4.81256 |               0         |       0        |       0         |                219 |
|            58 | template_phase    |      2.6428  |  2.6428  |   2.77317 |       3.54397 |               0.723168  |       0.470955 |       1.04213   |                219 |
|            58 | cfd20_reference   |      3.11542 |  2.88547 |   3.3665  |       4.8861  |               1.19579   |       0.787754 |       1.64143   |                219 |
|            59 | analytic_timewalk |      1.45871 |  1.38233 |   1.52694 |       2.54019 |              -0.421779  |      -0.529811 |      -0.327926  |               2289 |
|            59 | mlp_waveform      |      1.71108 |  1.64366 |   1.77743 |       5.4455  |              -0.169406  |      -0.261088 |      -0.0947427 |               2289 |
|            59 | s02_ridge_cfd20   |      1.88049 |  1.81022 |   1.97038 |       5.38597 |               0         |       0        |       0         |               2289 |
|            59 | template_phase    |      2.99232 |  2.87333 |   3.12333 |       3.34278 |               1.11183   |       0.990802 |       1.27615   |               2289 |
|            59 | cfd20_reference   |      3.19039 |  3.09525 |   3.26785 |       5.79544 |               1.30991   |       1.16989  |       1.41287   |               2289 |
|            60 | analytic_timewalk |      1.3437  |  1.28298 |   1.40768 |       2.39529 |              -0.476224  |      -0.597156 |      -0.372421  |               2424 |
|            60 | mlp_waveform      |      1.60696 |  1.53316 |   1.66854 |       6.62785 |              -0.212973  |      -0.33623  |      -0.126011  |               2424 |
|            60 | s02_ridge_cfd20   |      1.81993 |  1.73914 |   1.91795 |       6.47156 |               0         |       0        |       0         |               2424 |
|            60 | template_phase    |      2.66393 |  2.66393 |   2.7113  |       3.279   |               0.844     |       0.72997  |       0.963865  |               2424 |
|            60 | cfd20_reference   |      3.13862 |  3.06295 |   3.22729 |       7.26201 |               1.31869   |       1.19268  |       1.44299   |               2424 |
|            61 | mlp_waveform      |      2.11367 |  2.04088 |   2.18039 |       6.24534 |              -0.128759  |      -0.231462 |      -0.02874   |               2799 |
|            61 | analytic_timewalk |      2.12996 |  1.98436 |   2.20935 |       3.00806 |              -0.112469  |      -0.301959 |       0.0162831 |               2799 |
|            61 | s02_ridge_cfd20   |      2.24243 |  2.14793 |   2.32966 |       6.15879 |               0         |       0        |       0         |               2799 |
|            61 | template_phase    |      2.70351 |  2.70351 |   2.70351 |       3.20716 |               0.46108   |       0.373855 |       0.555585  |               2799 |
|            61 | cfd20_reference   |      2.91408 |  2.83923 |   2.99836 |       6.59866 |               0.67165   |       0.540441 |       0.812619  |               2799 |
|            62 | analytic_timewalk |      1.469   |  1.40916 |   1.51558 |       2.58419 |              -0.391008  |      -0.482822 |      -0.293937  |               2421 |
|            62 | mlp_waveform      |      1.74331 |  1.67694 |   1.81987 |       4.51535 |              -0.1167    |      -0.211761 |      -0.0180536 |               2421 |
|            62 | s02_ridge_cfd20   |      1.86001 |  1.77626 |   1.94181 |       4.61606 |               0         |       0        |       0         |               2421 |
|            62 | template_phase    |      2.90117 |  2.90117 |   3.02631 |       3.35891 |               1.04116   |       0.938446 |       1.22613   |               2421 |
|            62 | cfd20_reference   |      3.23169 |  3.14319 |   3.32206 |       4.95545 |               1.37167   |       1.24578  |       1.49559   |               2421 |
|            63 | analytic_timewalk |      1.39132 |  1.29008 |   1.46871 |       2.62807 |              -0.378518  |      -0.540357 |      -0.211653  |               1110 |
|            63 | mlp_waveform      |      1.6482  |  1.53176 |   1.76934 |       6.00255 |              -0.121643  |      -0.256491 |       0.0338589 |               1110 |
|            63 | s02_ridge_cfd20   |      1.76984 |  1.61604 |   1.8982  |       5.83286 |               0         |       0        |       0         |               1110 |
|            63 | template_phase    |      2.87872 |  2.85187 |   3.01249 |       3.38179 |               1.10888   |       0.980136 |       1.37042   |               1110 |
|            63 | cfd20_reference   |      3.40351 |  3.29776 |   3.51698 |       6.58303 |               1.63367   |       1.4497   |       1.84138   |               1110 |
|            65 | analytic_timewalk |      1.49464 |  1.30186 |   1.66581 |       1.69913 |              -0.351474  |      -0.607594 |       0.0399996 |                198 |
|            65 | s02_ridge_cfd20   |      1.84611 |  1.45261 |   2.02735 |       1.7098  |               0         |       0        |       0         |                198 |
|            65 | mlp_waveform      |      1.92723 |  1.62267 |   2.26034 |       1.97864 |               0.0811193 |      -0.128773 |       0.44442   |                198 |
|            65 | template_phase    |      2.88915 |  2.63915 |   3.27718 |       2.57669 |               1.04304   |       0.702441 |       1.63137   |                198 |
|            65 | cfd20_reference   |      2.99339 |  2.65953 |   3.36005 |       2.74268 |               1.14727   |       0.72897  |       1.75378   |                198 |

## Stability summary

| method            |   mean_sigma68_ns |   median_sigma68_ns |   min_sigma68_ns |   max_sigma68_ns |   n_heldout_runs |
|:------------------|------------------:|--------------------:|-----------------:|-----------------:|-----------------:|
| analytic_timewalk |           1.4964  |             1.45871 |          1.18748 |          2.12996 |                7 |
| mlp_waveform      |           1.80547 |             1.74331 |          1.60696 |          2.11367 |                7 |
| s02_ridge_cfd20   |           1.90549 |             1.86001 |          1.76984 |          2.24243 |                7 |
| template_phase    |           2.81023 |             2.87872 |          2.6428  |          2.99232 |                7 |
| cfd20_reference   |           3.14101 |             3.13862 |          2.91408 |          3.40351 |                7 |

|   heldout_run | best_method       |   best_sigma68_ns |   mlp_minus_s02_ridge_ns |   mlp_minus_analytic_ns |
|--------------:|:------------------|------------------:|-------------------------:|------------------------:|
|            58 | analytic_timewalk |           1.18748 |               -0.0318095 |               0.700342  |
|            59 | analytic_timewalk |           1.45871 |               -0.169406  |               0.252373  |
|            60 | analytic_timewalk |           1.3437  |               -0.212973  |               0.263251  |
|            61 | mlp_waveform      |           2.11367 |               -0.128759  |              -0.0162905 |
|            62 | analytic_timewalk |           1.469   |               -0.1167    |               0.274307  |
|            63 | analytic_timewalk |           1.39132 |               -0.121643  |               0.256875  |
|            65 | analytic_timewalk |           1.49464 |                0.0811193 |               0.432593  |

## Leakage checks

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

The MLP features are still only the 18 same-pulse samples normalized by amplitude plus stave one-hot. The split is by run for every fold; event-id overlap is zero in all folds; shuffled-target controls are reported for each held-out run.

## Verdict

`result.json` verdict: `mlp_often_beats_s02_ridge_but_not_traditional_baseline`. The MLP is best on `1` of `7` held-out runs and its mean sigma68 is `1.805 ns` versus `1.905 ns` for S02 ridge and `1.496 ns` for analytic timewalk.

## Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/p03b_leave_one_run_waveform_mlp_timing.py --config configs/p03b_leave_one_run_waveform_mlp_timing.yaml
```

Artifacts: `reproduction_match_table.csv`, `p03a_run65_reproduction.csv`, `heldout_run_summary.csv`, `pooled_summary.csv`, `winner_by_run.csv`, `leakage_checks.csv`, `mlp_cv_scan.csv`, `analytic_cv_scan.csv`, figures, `result.json`, and `manifest.json`.
