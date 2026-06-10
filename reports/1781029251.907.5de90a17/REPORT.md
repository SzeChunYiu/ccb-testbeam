# S16i: pretrigger-baseline live-time coupling audit

- **Ticket:** `1781029251.907.5de90a17`
- **Worker:** `testbeam-laptop-2`
- **Inputs:** raw B-stack ROOT runs 44-57; no Monte Carlo.
- **Split:** all ML predictions are leave-one-run-out; intervals use held-out run bootstrap CIs.
- **Leakage exclusions:** ML features are pretrigger mean/RMS/slope/max-excursion/ptp/asymmetry plus adaptive-lowering only; run/current/event identifiers, labels, and post-trigger samples are excluded.

## Reproduction first

Raw `h101/HRDv` was rescanned before modeling. The S10 selected-event topology numbers reproduce within the preregistered tolerance.

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

## Traditional method

Frozen train-run pretrigger bins stratify held-out events by RMS, slope, max excursion, and adaptive-lowering. The headline 20% tail shift is **-60.770 ns** [-63.164, -58.341], and the current downstream excess is **0.01899** [0.00890, 0.02969].

| method                        | metric                              |       value |       ci_low |     ci_high |   n_bootstrap | bootstrap_unit   |
|:------------------------------|:------------------------------------|------------:|-------------:|------------:|--------------:|:-----------------|
| traditional_pretrigger_strata | tau_eff_shift_5pct_ns               | -60.5456    | -63.1618     | -57.7277    |           500 | heldout_run      |
| traditional_pretrigger_strata | empirical_last_above_shift_5pct_ns  | -61.8849    | -64.7308     | -59.4306    |           500 | heldout_run      |
| traditional_pretrigger_strata | tau_eff_shift_10pct_ns              | -60.0999    | -62.4608     | -57.5535    |           500 | heldout_run      |
| traditional_pretrigger_strata | empirical_last_above_shift_10pct_ns | -63.3529    | -65.768      | -60.7442    |           500 | heldout_run      |
| traditional_pretrigger_strata | tau_eff_shift_20pct_ns              | -60.7696    | -63.1642     | -58.3408    |           500 | heldout_run      |
| traditional_pretrigger_strata | empirical_last_above_shift_20pct_ns | -65.9468    | -68.3759     | -63.5336    |           500 | heldout_run      |
| traditional_pretrigger_strata | two_pulse_time_rms_shift_ns         | -34.0789    | -39.7974     | -27.9237    |           500 | heldout_run      |
| traditional_pretrigger_strata | two_pulse_time_rms_ns               |  53.2729    |  47.7242     |  58.2797    |           500 | heldout_run      |
| traditional_pretrigger_strata | two_pulse_residual_shift            |  -0.210309  |  -0.2332     |  -0.188849  |           500 | heldout_run      |
| traditional_pretrigger_strata | charge_bias_shift_area_over_peak    |  -9.21097   |  -9.85295    |  -8.56355   |           500 | heldout_run      |
| traditional_pretrigger_strata | downstream_excess_high_minus_low    |   0.0189946 |   0.00889887 |   0.0296908 |           500 | heldout_run      |

## ML method

The pretrigger-only classifier/regressor targets the held-out 20% tail-risk label. Held-out AUC is **0.696** [0.675, 0.712] with calibration ECE **0.2076** [0.1448, 0.2744].

| method             | metric                                           |         value |      ci_low |      ci_high |   n_bootstrap | bootstrap_unit   |
|:-------------------|:-------------------------------------------------|--------------:|------------:|-------------:|--------------:|:-----------------|
| ml_pretrigger_only | traditional_tail_auc                             |   0.635343    |   0.616664  |   0.653188   |           500 | heldout_run      |
| ml_pretrigger_only | ml_tail_auc                                      |   0.695784    |   0.674883  |   0.71238    |           500 | heldout_run      |
| ml_pretrigger_only | ml_minus_traditional_auc                         |   0.0604408   |   0.0525263 |   0.0675154  |           500 | heldout_run      |
| ml_pretrigger_only | ml_calibration_ece                               |   0.207589    |   0.144788  |   0.274438   |           500 | heldout_run      |
| ml_pretrigger_only | traditional_calibration_ece                      |   0.127719    |   0.0957735 |   0.15568    |           500 | heldout_run      |
| ml_pretrigger_only | ml_minus_traditional_ece                         |   0.0798692   |  -0.0186236 |   0.174425   |           500 | heldout_run      |
| ml_pretrigger_only | mean_brier_improvement_vs_traditional            |  -0.029953    |  -0.0671466 |   0.0103132  |           500 | heldout_run      |
| ml_pretrigger_only | mean_log_loss_improvement_vs_traditional         |  -0.0640653   |  -0.1635    |   0.0357764  |           500 | heldout_run      |
| ml_pretrigger_only | ml_tail_resid_shift_ns                           | -11.7055      | -13.4934    |  -9.67368    |           500 | heldout_run      |
| ml_pretrigger_only | ml_predicted_tau_shift_ns                        | -54.2122      | -55.8502    | -52.2571     |           500 | heldout_run      |
| ml_pretrigger_only | ml_predicted_downstream_excess                   |  -0.0190504   |  -0.0315615 |  -0.00532117 |           500 | heldout_run      |
| ml_pretrigger_only | traditional_predicted_downstream_excess          |  -0.0182338   |  -0.0340155 |  -0.00219789 |           500 | heldout_run      |
| ml_pretrigger_only | ml_minus_traditional_predicted_downstream_excess |  -0.000816654 |  -0.0031486 |   0.001953   |           500 | heldout_run      |

## Leakage review

Shuffled-pretrigger controls and ML-minus-traditional AUC gates produced **0** flags. Any large pretrigger-only gains are treated as nuisance sensitivity, not physics truth.

|   heldout_run | check                       |     value | flag   | note                                                                               |
|--------------:|:----------------------------|----------:|:-------|:-----------------------------------------------------------------------------------|
|            44 | shuffled_pretrigger_control | 0.524432  | False  | pretrigger features independently permuted in training before scoring held-out run |
|            44 | ml_minus_traditional_auc    | 0.0240732 | False  | large pretrigger-only gain triggers leakage review                                 |
|            45 | shuffled_pretrigger_control | 0.492402  | False  | pretrigger features independently permuted in training before scoring held-out run |
|            45 | ml_minus_traditional_auc    | 0.0495101 | False  | large pretrigger-only gain triggers leakage review                                 |
|            46 | shuffled_pretrigger_control | 0.589535  | False  | pretrigger features independently permuted in training before scoring held-out run |
|            46 | ml_minus_traditional_auc    | 0.0853685 | False  | large pretrigger-only gain triggers leakage review                                 |
|            47 | shuffled_pretrigger_control | 0.606787  | False  | pretrigger features independently permuted in training before scoring held-out run |
|            47 | ml_minus_traditional_auc    | 0.0624949 | False  | large pretrigger-only gain triggers leakage review                                 |
|            48 | shuffled_pretrigger_control | 0.541993  | False  | pretrigger features independently permuted in training before scoring held-out run |
|            48 | ml_minus_traditional_auc    | 0.06121   | False  | large pretrigger-only gain triggers leakage review                                 |
|            49 | shuffled_pretrigger_control | 0.534976  | False  | pretrigger features independently permuted in training before scoring held-out run |
|            49 | ml_minus_traditional_auc    | 0.0601067 | False  | large pretrigger-only gain triggers leakage review                                 |
|            50 | shuffled_pretrigger_control | 0.538007  | False  | pretrigger features independently permuted in training before scoring held-out run |
|            50 | ml_minus_traditional_auc    | 0.0582014 | False  | large pretrigger-only gain triggers leakage review                                 |
|            51 | shuffled_pretrigger_control | 0.421352  | False  | pretrigger features independently permuted in training before scoring held-out run |
|            51 | ml_minus_traditional_auc    | 0.0569415 | False  | large pretrigger-only gain triggers leakage review                                 |
|            52 | shuffled_pretrigger_control | 0.449452  | False  | pretrigger features independently permuted in training before scoring held-out run |
|            52 | ml_minus_traditional_auc    | 0.083146  | False  | large pretrigger-only gain triggers leakage review                                 |
|            53 | shuffled_pretrigger_control | 0.343812  | False  | pretrigger features independently permuted in training before scoring held-out run |
|            53 | ml_minus_traditional_auc    | 0.0741879 | False  | large pretrigger-only gain triggers leakage review                                 |
|            54 | shuffled_pretrigger_control | 0.563611  | False  | pretrigger features independently permuted in training before scoring held-out run |
|            54 | ml_minus_traditional_auc    | 0.0557173 | False  | large pretrigger-only gain triggers leakage review                                 |
|            55 | shuffled_pretrigger_control | 0.67712   | False  | pretrigger features independently permuted in training before scoring held-out run |
|            55 | ml_minus_traditional_auc    | 0.0539415 | False  | large pretrigger-only gain triggers leakage review                                 |
|            56 | shuffled_pretrigger_control | 0.6231    | False  | pretrigger features independently permuted in training before scoring held-out run |
|            56 | ml_minus_traditional_auc    | 0.0681223 | False  | large pretrigger-only gain triggers leakage review                                 |
|            57 | shuffled_pretrigger_control | 0.517967  | False  | pretrigger features independently permuted in training before scoring held-out run |
|            57 | ml_minus_traditional_auc    | 0.0531498 | False  | large pretrigger-only gain triggers leakage review                                 |

## Conclusion

Pretrigger baseline spectra measurably couple to S10 live-time tail observables, but the coupling is nuisance-like: the high-pretrigger group has shorter tail and two-pulse proxies, while the raw current downstream excess remains positive. The pretrigger-only ML model predicts the opposite downstream-current sign and adds calibration diagnostics rather than a cleaner physical separation, so shuffled-pretrigger controls remain the limiting leakage guard.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16i_1781029251_907_5de90a17_pretrigger_livetime_coupling.py --config configs/s16i_1781029251_907_5de90a17_pretrigger_livetime_coupling.json
```

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `traditional_summary.csv`, `ml_summary.csv`, `ml_fold_diagnostics.csv`, and `leakage_checks.csv`.
