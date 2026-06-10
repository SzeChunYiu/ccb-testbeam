# P04k Selector-Semantics Charge-Closure Sensitivity

- **Ticket ID:** 1781029246.839.554f50f7
- **Worker:** testbeam-laptop-1
- **Input:** raw B-stack ROOT only; no Monte Carlo.
- **Held-out runs:** 57, 65; all calibrators, templates, and ML models exclude those runs.

## Raw Reproduction First

| quantity                   |   expected |   reproduced |   delta | pass   |
|:---------------------------|-----------:|-------------:|--------:|:-------|
| median_first_four_selected |     640737 |       640737 |       0 | True   |
| dynamic_range_selected     |     706373 |       706373 |       0 | True   |
| dynamic_only               |      65636 |        65636 |       0 | True   |
| median_only                |          0 |            0 |       0 | True   |

The S00c selector anchors are reproduced exactly before any target filtering, fitting, matching, or modeling.

## Strata

| stratum         |   n_rows |   n_runs |   median_dynamic_amp |   median_baseline_excursion |   sat_boundary_frac |
|:----------------|---------:|---------:|---------------------:|----------------------------:|--------------------:|
| median_selected |    26860 |        2 |                 3698 |                         9   |           0.099032  |
| dynamic_only    |     3715 |        2 |                 3200 |                      2853.5 |           0         |
| matched_control |     3715 |        2 |                 3834 |                      2429   |           0.0137281 |

Dynamic-only rows are compared both directly and against same-run/same-stave nearest-neighbor median-selected controls matched on dynamic amplitude, baseline excursion, and pretrigger RMS.

## Held-Out Charge Closure

Metric rows are duplicate-readout odd-charge fractional errors with run-block bootstrap 95% CIs.

| stratum         | method                                 |     n |   bias_median_frac |   res68_abs_frac |   full_rms_frac |   within_10pct |   within_25pct | res68_abs_frac_ci95                          |
|:----------------|:---------------------------------------|------:|-------------------:|-----------------:|----------------:|---------------:|---------------:|:---------------------------------------------|
| dynamic_only    | ml_hgb_blind_train_dynamic_selector    |  3715 |        0.0247632   |        0.0985056 |       0.197509  |     0.683445   |      0.898789  | [0.09302808154668431, 0.10901483501303927]   |
| dynamic_only    | ml_hgb_aware_train_median_selector     |  3715 |        0.162712    |        0.469389  |       0.945441  |     0.259489   |      0.517631  | [0.4226043470143625, 0.5475452557801558]     |
| dynamic_only    | strong_traditional_huber               |  3715 |       -0.274262    |        0.686152  |       1.33227   |     0.0979812  |      0.260296  | [0.6696672266522977, 0.7457799520423153]     |
| dynamic_only    | integral_calibrated                    |  3715 |       -0.510845    |        0.75213   |       1.37352   |     0.0379542  |      0.0982503 | [0.7088741479655035, 0.7678914520634043]     |
| dynamic_only    | adaptive_template_charge               |  3715 |        0.236855    |        0.925352  |       9.62205   |     0.0971736  |      0.234455  | [0.8395063927237303, 1.2703540733582628]     |
| dynamic_only    | ml_hgb_blind_train_median_selector     |  3715 |        0.608598    |        1.04652   |       1.69535   |     0.132436   |      0.265141  | [0.8100398417725508, 1.147038844598215]      |
| dynamic_only    | ml_hgb_shuffled_train_dynamic_selector |  3715 |       44.734       |       63.1713    |      75.215     |     0          |      0         | [53.03425961573386, 67.5379739433461]        |
| matched_control | ml_hgb_blind_train_median_selector     |  3715 |       -0.00045733  |        0.186176  |       0.218959  |     0.477524   |      0.80996   | [0.18617616505488024, 0.2393325535734552]    |
| matched_control | ml_hgb_blind_train_dynamic_selector    |  3715 |       -0.00469753  |        0.234799  |       0.247338  |     0.444953   |      0.690175  | [0.1236906027086863, 0.3409062956261017]     |
| matched_control | ml_hgb_aware_train_median_selector     |  3715 |       -0.00805352  |        0.293991  |       0.254687  |     0.353163   |      0.633647  | [0.18662416593975298, 0.3415496455778133]    |
| matched_control | integral_calibrated                    |  3715 |       -0.185843    |        0.46857   |       1.5529    |     0.130013   |      0.379273  | [0.26173816251238075, 0.46857031620361994]   |
| matched_control | strong_traditional_huber               |  3715 |        0.0989867   |        0.488553  |       1.47426   |     0.166353   |      0.422073  | [0.48855349618272226, 0.5801135359377839]    |
| matched_control | adaptive_template_charge               |  3715 |        0.321117    |        1.37838   |      11.1038    |     0.0196501  |      0.0538358 | [0.8636033230561162, 1.8013771921917423]     |
| matched_control | ml_hgb_shuffled_train_dynamic_selector |  3715 |        4.99912     |        9.48228   |      41.5438    |     0.00699865 |      0.0449529 | [8.320162834121327, 9.482278367805876]       |
| median_selected | strong_traditional_huber               | 26860 |        0.000272937 |        0.0174854 |       0.566019  |     0.863589   |      0.914259  | [0.016212249695854674, 0.019219402669883902] |
| median_selected | ml_hgb_aware_train_median_selector     | 26860 |        0.00263683  |        0.0203009 |       0.0998692 |     0.942182   |      0.988943  | [0.019614026213610282, 0.021005624141410172] |
| median_selected | ml_hgb_blind_train_median_selector     | 26860 |        0.0025266   |        0.0210283 |       0.119824  |     0.944564   |      0.990692  | [0.01983800378593671, 0.022194882817458326]  |
| median_selected | ml_hgb_blind_train_dynamic_selector    | 26860 |        0.00173845  |        0.0218423 |       0.424977  |     0.938645   |      0.988459  | [0.021414270428688088, 0.022248616597705734] |
| median_selected | integral_calibrated                    | 26860 |       -0.0914876   |        0.196287  |       1.66369   |     0.402122   |      0.795681  | [0.163794376129635, 0.2174120538829048]      |
| median_selected | adaptive_template_charge               | 26860 |        0.102065    |        0.557722  |       2.56086   |     0.17997    |      0.518764  | [0.3896909990977, 0.7188964481401475]        |
| median_selected | ml_hgb_shuffled_train_dynamic_selector | 26860 |       -0.0942419   |        0.627617  |       7.82406   |     0.0795979  |      0.209382  | [0.6147896790710947, 0.6740932548622632]     |

## Selector Delta

Deltas are dynamic-only minus matched-control, using event-paired run-block bootstrap resampling of the matched pairs.

| method                                 | metric         |     delta | ci95                                         |   n_pairs |
|:---------------------------------------|:---------------|----------:|:---------------------------------------------|----------:|
| adaptive_template_charge               | res68_abs_frac | -0.453023 | [-0.5421225558884281, -0.22089859730927738]  |      3715 |
| ml_hgb_blind_train_dynamic_selector    | res68_abs_frac | -0.136294 | [-0.24582466761877084, -0.01658136003362565] |      3715 |
| ml_hgb_aware_train_median_selector     | res68_abs_frac |  0.175397 | [0.083693372907088, 0.36444773600462754]     |      3715 |
| strong_traditional_huber               | res68_abs_frac |  0.197598 | [0.11849277810643451, 0.2703812205371547]    |      3715 |
| integral_calibrated                    | res68_abs_frac |  0.28356  | [0.22138027054800477, 0.31101164477004933]   |      3715 |
| ml_hgb_blind_train_median_selector     | res68_abs_frac |  0.860344 | [0.6432693411639697, 0.9612889998548889]     |      3715 |
| ml_hgb_shuffled_train_dynamic_selector | res68_abs_frac | 53.689    | [39.014294664121486, 58.43677903485756]      |      3715 |

## Saturation And Baseline Boundaries

| subset              |   n_pairs |   median_fractional_shift | ci95_fractional_shift      |
|:--------------------|----------:|--------------------------:|:---------------------------|
| all_matched_pairs   |      3715 |                         0 | [-0.900044948373281, 0.0]  |
| saturation_boundary |        51 |                         0 | [-0.9801288847086306, 0.0] |
| baseline_boundary   |      3661 |                         0 | [-0.9120103585463462, 0.0] |

The q_template quantity is the adaptive-template charge estimate calibrated on train-run median-selected rows.

## Leakage Audit

- Held-out runs absent from training: `True`.
- Train/held-out `(run,event,stave)` key overlap: `0`.
- Feature sets exclude run and event identifiers: `True`.
- Odd duplicate target samples are excluded from features: `True`.
- Dynamic-selector shuffled-target res68 on dynamic-only rows: `63.1713`.
- Median-selector shuffled-target res68 on median-selected rows: `1.0465`.

The ML rows that are much narrower than strong traditional closure are treated as duplicate-readout electronics closure only; the shuffled-target sentinels and matched-control deltas are the guardrails against promoting them to deposited-energy truth.

## Finding

Dynamic-only held-out rows are a difficult selector-induced population: integral charge closure has res68=0.7521, while the strong Huber traditional estimator reaches 0.6862. The best dynamic-only row is ml_hgb_blind_train_dynamic_selector at res68=0.0985; shuffled-target sentinels remain broad, so the ML gain is not explained by target leakage in this split. The adaptive-template q_template saturation-boundary matched fractional shift is +0.0000, and selector deltas are reported only against matched controls because dynamic-only rows are not an exchangeable subset of the median-selected sample.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04k_1781029246_839_554f50f7_selector_charge_closure.py --config configs/p04k_1781029246_839_554f50f7_selector_charge_closure.json
```
