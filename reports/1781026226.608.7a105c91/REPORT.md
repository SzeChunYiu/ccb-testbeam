# S04d: Timing-Tail Pathology Interaction Audit

- **Ticket:** `1781026226.608.7a105c91`
- **Worker:** `testbeam-laptop-2`
- **Input:** raw B-stack ROOT `h101/HRDv` under `data/root/root`; no Monte Carlo
- **Split:** grouped by run; held-out OOF predictions plus run/event bootstrap CIs
- **Config:** `configs/s04d_1781026226_608_7a105c91.json`

## Reproduction First

The first executable analysis step rescanned raw ROOT and reproduced the S00/S04 B-stave selected-pulse counts.

| quantity                            |   report_value |   reproduced |   delta |   tolerance | pass   |
|:------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses       |         640737 |       640737 |       0 |           0 | True   |
| adaptive post-correction violations |              0 |            0 |       0 |           0 | True   |
| sample_i_analysis selected_pulses   |         252266 |       252266 |       0 |           0 | True   |
| sample_i_analysis B2                |         241422 |       241422 |       0 |           0 | True   |
| sample_i_analysis B4                |           6451 |         6451 |       0 |           0 | True   |
| sample_i_analysis B6                |           3094 |         3094 |       0 |           0 | True   |
| sample_i_analysis B8                |           1299 |         1299 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses  |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2               |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4               |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6               |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8               |           4506 |         4506 |       0 |           0 | True   |

## Methods

Traditional: frozen CFD20 pair residuals, matched binary pathology interaction tables, additive-only logistic tail risk, and an additive Ridge residual stress test. The interaction table preserves run and pair composition by reporting the run/event bootstrap and a run-composition shift for the double-positive cell.

ML: a sparse L1 interaction logistic model and a calibrated constrained-depth random-forest tail-risk model using only frozen waveform/pathology summaries; the RF residual model is included as a head-to-head timing stress test.

## Residual Head-To-Head

| method                     |   n_pair_residuals |   sigma68_ns |   sigma68_ci_low |   sigma68_ci_high |   full_rms_ns |   full_rms_ci_low |   full_rms_ci_high |   tail_frac_abs_gt5ns |   tail_ci_low |   tail_ci_high |
|:---------------------------|-------------------:|-------------:|-----------------:|------------------:|--------------:|------------------:|-------------------:|----------------------:|--------------:|---------------:|
| raw_cfd20_pair_centered    |              13410 |      1.68164 |          1.63321 |           1.72985 |       5.78949 |           4.23403 |            7.00848 |             0.0152871 |     0.0119752 |      0.0191996 |
| traditional_additive_ridge |              13410 |      2.15781 |          2.08559 |           2.25932 |       5.2978  |           3.98382 |            6.39143 |             0.0508576 |     0.0456974 |      0.05707   |
| ml_rf_interaction_residual |              13410 |      1.36654 |          1.32047 |           1.42362 |       5.22797 |           3.78809 |            6.56302 |             0.0228188 |     0.0173362 |      0.0286307 |

## Tail-Risk Classifiers

| method                       |      auc |   average_precision |     brier |        ece |   mean_probability |
|:-----------------------------|---------:|--------------------:|----------:|-----------:|-------------------:|
| traditional_additive_logit   | 0.892407 |           0.358273  | 0.0754914 | 0.185381   |          0.200668  |
| ml_sparse_interaction_logit  | 0.897064 |           0.379704  | 0.068173  | 0.161496   |          0.176783  |
| ml_calibrated_tree           | 0.895255 |           0.329538  | 0.0121381 | 0.00304293 |          0.0149312 |
| shuffled_target_tree_control | 0.327875 |           0.0105404 | 0.17101   | 0.378558   |          0.393845  |
| axis_shuffled_control        | 0.753473 |           0.248237  | 0.0833994 | 0.176076   |          0.191363  |

## Strongest Interactions

| axis_a              | axis_b              |   min_cell_n | low_support   |   tail_rate00 |   tail_rate10 |   tail_rate01 |   tail_rate11 |   additive_expected11 |   interaction_delta |   interaction_delta_ci_low |   interaction_delta_ci_high |   interaction_odds_ratio |   log_interaction_or_ci_low |   log_interaction_or_ci_high |   composition_shift |
|:--------------------|:--------------------|-------------:|:--------------|--------------:|--------------:|--------------:|--------------:|----------------------:|--------------------:|---------------------------:|----------------------------:|-------------------------:|----------------------------:|-----------------------------:|--------------------:|
| s16_lowering_axis   | dropout_jagged_axis |           73 | False         |    0.00944681 |     0.256881  |    0.0547945  |     0.0419486 |             0.302228  |          -0.26028   |               -0.488599    |                  -0.116359  |                0.0186676 |                   -6.13652  |                    -1.26156  |           0.0687927 |
| s16_lowering_axis   | p07_saturation_axis |          288 | False         |    0.00514933 |     0.0423403 |    0.0226978  |     0.121528  |             0.0598887 |           0.0616391 |                0.00755359  |                   0.149035  |                0.70266   |                   -1.49257  |                     0.538453 |           0.158874  |
| pretrigger_axis     | peak_phase_axis     |          222 | False         |    0.0045045  |     0.0161828 |    0.00849066 |     0.0789963 |             0.0201689 |           0.0588274 |                0.0309418   |                   0.100028  |                4.06301   |                   -0.375012 |                     3.46819  |           0.0511061 |
| pretrigger_axis     | p07_saturation_axis |          989 | False         |    0.00535032 |     0.0265082 |    0.0184641  |     0.0616785 |             0.039622  |           0.0220564 |                5.75345e-05 |                   0.0587423 |                0.690245  |                   -1.22261  |                     0.481327 |           0.0885406 |
| s16_lowering_axis   | peak_phase_axis     |          761 | False         |    0.00400802 |     0.035109  |    0.0105559  |     0.0801577 |             0.0416568 |           0.0385009 |               -0.00593652  |                   0.0938003 |                0.965153  |                   -1.94355  |                     1.293    |           0.0714752 |
| dropout_jagged_axis | peak_phase_axis     |          724 | False         |    0.0100267  |     0.0241838 |    0.0119656  |     0.0635359 |             0.0261227 |           0.0374132 |               -0.0018101   |                   0.0801656 |                2.3229    |                   -0.618794 |                     2.60881  |           0.0756171 |
| p07_saturation_axis | s10_two_pulse_axis  |          400 | False         |    0.0079929  |     0.045     |    0.0171614  |     0.0292732 |             0.0541685 |          -0.0248953 |               -0.0628444   |                   0.0171681 |                0.287769  |                   -1.99655  |                     0.881453 |           0.0908121 |
| s16_lowering_axis   | s10_two_pulse_axis  |          434 | False         |    0.00392762 |     0.045967  |    0.0185343  |     0.0852535 |             0.0605737 |           0.0246797 |               -0.0050882   |                   0.0773204 |                0.410093  |                   -1.66817  |                     0.180132 |           0.119987  |

## Leakage Checks

| check                                    |          value | pass   |
|:-----------------------------------------|---------------:|:-------|
| all_rows_have_run_heldout_predictions    | 13410          | True   |
| features_exclude_identifiers_and_labels  |                | True   |
| shuffled_target_auc_near_random          |     0.327875   | True   |
| axis_shuffled_control_weaker_than_tree   |     0.141782   | True   |
| row_cv_not_materially_better_than_run_cv |     0.0336763  | True   |
| ml_residual_gain_under_one_ns            |     0.3151     | True   |
| tree_calibration_ece_under_0p03          |     0.00304293 | True   |

Run-vs-row sentinel: additive logit run-CV AUC `0.888`, row-CV AUC `0.922`. Tree shuffled-target AUC `0.336` and axis-shuffled AUC `0.748`.

## Verdict

Single pathology axes miss measurable interaction structure, but the interactions are not a hidden timing-correction shortcut. The strongest pair is s16_lowering_axis x dropout_jagged_axis: observed double-positive tail fraction 0.0419 versus additive expectation 0.3022, delta -0.2603 with 95% CI [-0.4886, -0.1164]. Additive traditional tail AUC is 0.892; sparse-interaction ML AUC is 0.897; calibrated tree AUC is 0.895 with ECE 0.0030. Residual sigma68 is 1.682 ns raw, 2.158 ns additive traditional, and 1.367 ns ML. Use the pairwise interaction ledger for veto composition and uncertainty inflation rather than replacing the S04 timing baseline.

The largest double-positive interaction is `s16_lowering_axis` with `dropout_jagged_axis`. Its observed double-positive tail fraction is `0.0419` versus additive expectation `0.3022`; the bootstrap delta CI is `[-0.4886, -0.1164]`.

## Reproducibility

```bash
/home/billy/.tb-workers/testbeam-laptop-2/.venv/bin/python scripts/s04d_1781026226_608_7a105c91_timing_tail_interactions.py --config configs/s04d_1781026226_608_7a105c91.json
```

Artifacts: `reproduction_match_table.csv`, `pair_residuals_oof.csv.gz`, `residual_benchmark.csv`, `tail_classifier_benchmark.csv`, `pairwise_interaction_table.csv`, `ml_fold_diagnostics.csv`, `leakage_checks.csv`, `input_sha256.csv`, `result.json`, `manifest.json`, and figures.
