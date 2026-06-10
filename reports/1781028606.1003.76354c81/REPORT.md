# S10i: real high-current candidate pair operational tau calibration

- **Ticket:** `1781028606.1003.76354c81`
- **Worker:** `testbeam-laptop-4`
- **Inputs:** raw B-stack HRD ROOT runs 44-57 plus S10b/S10d reproduction runs; no Monte Carlo.
- **Split:** every waveform score is produced with its source run held out; CIs resample source runs within current group.

## Reproduction first

The raw S10 topology gate is reproduced before the tau calibration:

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

The S10b live-time and S10d resolvability numbers are rerun from raw ROOT before scoring real candidates:

| quantity                              |   report_value |   reproduced |        delta |   tolerance | pass   |
|:--------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| S10 assumed tau_eff combined Rmax MHz |        4.22222 |      4.22222 |  0           |        0.05 | True   |
| S10b measured traditional live10 ns   |      124.79    |    124.79    |  0.000183943 |        1    | True   |
| S10b measured-tau rescaled Rmax MHz   |        3.05    |      3.04511 | -0.00488869  |        0.05 | True   |

| quantity                                                  |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S10d constrained_template_fit resolvable delay ns         |             60 |           60 |       0 |       1e-09 | True   |
| S10d compact_mlp_classifier_regressor resolvable delay ns |             20 |           20 |       0 |       1e-09 | True   |

## Quiet-pretrigger candidate sample

Quiet windows require corrected pretrigger absmax <= 80 ADC and ptp <= 120 ADC. Matched strata are recomputed after this cut.

| group     |   n_quiet_selected_events |   quiet_fraction_of_selected_events |   downstream_fraction |   median_pretrigger_absmax_adc |   median_pretrigger_ptp_adc |
|:----------|--------------------------:|------------------------------------:|----------------------:|-------------------------------:|----------------------------:|
| high_20nA |                    153340 |                            0.6462   |             0.0326529 |                             13 |                          19 |
| low_2nA   |                      3675 |                            0.629496 |             0.022585  |                             13 |                          19 |

## Methods

Traditional: the bounded two-pulse template fit from S10e, rebuilt run-by-run with the scored run held out.

ML: the S10e random-forest residual classifier/regressor trained on raw-pulse overlays from training runs only. It is used only as a diagnostic scorer on real quiet-pretrigger events.

Score-only real candidate rates before applying any tau threshold:

| method      |   high_value |   low_value |   high_minus_low |     ci_low |   ci_high |
|:------------|-------------:|------------:|-----------------:|-----------:|----------:|
| traditional |     0.849642 |   0.84637   |       0.00327147 | -0.0188922 | 0.0251674 |
| ml          |     0.054994 |   0.0304147 |       0.0245793  |  0.0135218 | 0.036737  |

## Tau scan

Tau definitions compared against real candidate separability:

| tau_definition                 |   tau_ns | source                                                          | reproduced_anchor   |   rmax_mhz |
|:-------------------------------|---------:|:----------------------------------------------------------------|:--------------------|-----------:|
| s10d_ml_resolvable_delay       |    20    | S10d raw-pulse injected benchmark headline                      | True                |  nan       |
| s10d_template_resolvable_delay |    60    | S10d raw-pulse injected benchmark headline                      | True                |  nan       |
| s10_assumed_tau_eff            |    90    | S10 assumed live window used for combined Rmax                  | True                |    4.22222 |
| s10b_measured_live10           |   124.79 | S10b measured 10pct template live-time reproduced from raw ROOT | True                |    3.04511 |

| method      | tau_definition                 |   tau_ns |   high_value |   low_value |   high_minus_low |       ci_low |    ci_high |   candidate_survival_given_candidate_high |   candidate_survival_given_candidate_low |
|:------------|:-------------------------------|---------:|-------------:|------------:|-----------------:|-------------:|-----------:|------------------------------------------:|-----------------------------------------:|
| traditional | s10d_ml_resolvable_delay       |    20    |   0.814802   |  0.828438   |      -0.0136355  | -0.0404495   | 0.0122093  |                                0.955941   |                               0.977175   |
| traditional | s10d_template_resolvable_delay |    60    |   0.00340124 |  0.00170021 |       0.00170103 | -0.00142684  | 0.00493998 |                                0.00378282 |                               0.00142653 |
| traditional | s10_assumed_tau_eff            |    90    |   0          |  0          |       0          |  0           | 0          |                                0          |                               0          |
| traditional | s10b_measured_live10           |   124.79 |   0          |  0          |       0          |  0           | 0          |                                0          |                               0          |
| ml          | s10d_ml_resolvable_delay       |    20    |   0.0238749  |  0.0046063  |       0.0192686  |  0.0142951   | 0.0249064  |                                0.47479    |                               0.157895   |
| ml          | s10d_template_resolvable_delay |    60    |   0.00161782 |  0          |       0.00161782 |  0.000566737 | 0.00287195 |                                0.0252101  |                               0          |
| ml          | s10_assumed_tau_eff            |    90    |   0          |  0          |       0          |  0           | 0          |                                0          |                               0          |
| ml          | s10b_measured_live10           |   124.79 |   0          |  0          |       0          |  0           | 0          |                                0          |                               0          |

Grouped run stability:

| method      | group     |   n_runs |   mean_candidate_rate |   median_candidate_delay_ns |   min_candidate_delay_ns |   max_candidate_delay_ns |
|:------------|:----------|---------:|----------------------:|----------------------------:|-------------------------:|-------------------------:|
| ml          | high_20nA |       12 |             0.0472222 |                     19.3548 |                 11.0596  |                  30.0567 |
| ml          | low_2nA   |        2 |             0.0242691 |                     10.4621 |                  7.94445 |                  12.9797 |
| traditional | high_20nA |       12 |             0.891667  |                     20      |                 20       |                  30      |
| traditional | low_2nA   |        2 |             0.883576  |                     20      |                 20       |                  20      |

## Leakage review

| check                                              |      value | flag   | note                                                                                                       |
|:---------------------------------------------------|-----------:|:-------|:-----------------------------------------------------------------------------------------------------------|
| heldout_run_excluded_from_template_and_ml_training |   1        | False  | Every scored quiet-pretrigger row is from the held-out source run for both templates and ML.               |
| identifier_features_excluded                       |   1        | False  | Imported S10e ML features exclude run, eventno, current/group, downstream, and stratum labels.             |
| synthetic_train_source_runs_exclude_heldout        |   1        | False  | Fold diagnostics list source runs used for synthetic overlays.                                             |
| mean_synthetic_holdout_auc                         |   0.985558 | False  | Flag near-perfect synthetic classification.                                                                |
| mean_shuffled_label_synthetic_auc                  |   0.516977 | False  | Shuffled labels should not classify held-out synthetic overlays.                                           |
| traditional_current_auc_from_score                 |   0.498551 | False  | Flag if a candidate score almost directly identifies beam current.                                         |
| ml_current_auc_from_score                          |   0.532425 | False  | Flag if a candidate score almost directly identifies beam current.                                         |
| s10_assumed_tau_eff_above_fit_support              |  90        | False  | Not leakage: this tau is above the real two-pulse fit grid, so zero survival is an extrapolation boundary. |
| s10b_measured_live10_above_fit_support             | 124.79     | False  | Not leakage: this tau is above the real two-pulse fit grid, so zero survival is an extrapolation boundary. |

## Conclusion

On real quiet-pretrigger candidate windows, the best traditional separability is at s10d_template_resolvable_delay (60.0 ns): high-minus-low 0.00170 [-0.00143, 0.00494]. The best ML separability is at s10d_ml_resolvable_delay (20.0 ns): 0.01927 [0.01430, 0.02491]. The reproduced S10b live10 definition is 124.79 ns, and tau definitions at or above 90 ns leave at most 0.00000 matched high-current pass rate in this real-pair fit grid. Thus the real-candidate operational calibration supports a short separability threshold near the S10d ML resolvability scale, not the longer live-time tau_eff used for rate extrapolation. Leakage flags: 0.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, tau scan tables, run summaries, leakage diagnostics, and PNG figures are in this folder.
