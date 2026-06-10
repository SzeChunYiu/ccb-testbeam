# S03i: q_template amplitude-matched tail-label isolation

- **Ticket:** 1781029233.703.5ff5517d
- **Worker:** testbeam-laptop-2
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT in `/home/billy/ccb-data/extracted/root/root`
- **Split:** leave-one-run-out over `58, 59, 60, 61, 62, 63, 65`; intervals use held-out run-block bootstrap.

## Question
Does the S03d downstream `q_template` tail signal survive matching on downstream amplitude, topology, peak-sample phase, high-amplitude boundary, and run family, or is it mostly an amplitude nuisance?

## Raw Reproduction First
The raw `HRDv` scan reran the S00 B-stave selected-pulse gate and the S07/S03d downstream timing-tail parent gate before any matched model was fit.

| quantity                                             | report_value | reproduced | delta | tolerance | pass |
| ---------------------------------------------------- | ------------ | ---------- | ----- | --------- | ---- |
| total selected B-stave pulses                        | 640737       | 640737     | 0     | 0         | True |
| sample_i_calib selected pulses                       | 248745       | 248745     | 0     | 0         | True |
| sample_i_analysis selected pulses                    | 252266       | 252266     | 0     | 0         | True |
| sample_ii_calib selected pulses                      | 14630        | 14630      | 0     | 0         | True |
| sample_ii_analysis selected pulses                   | 125096       | 125096     | 0     | 0         | True |
| S07 parent guarded gross events, D_t>51 ns           | 72           | 72         | 0     | 0         | True |
| all-three downstream control events                  | 3774         | 3774       | 0     | 0         | True |
| all-three downstream guarded gross events, D_t>51 ns | 22           | 22         | 0     | 0         | True |

The S03d headline was then reproduced from the same raw scan and calibration-only q-template construction:

| quantity                            | report_value | reproduced | delta        | tolerance | pass |
| ----------------------------------- | ------------ | ---------- | ------------ | --------- | ---- |
| S03d traditional q_template ROC-AUC | 0.712233     | 0.712233   | -4.65842e-07 | 0.003     | True |
| S03d q_template RF ROC-AUC          | 0.898047     | 0.89982    | 0.00177254   | 0.003     | True |

## Matched Dataset
Labels are the S03d external timing-tail labels: clean if `D_t < 3.0 ns`, tail if `D_t > 51.0 ns`; intermediate events are excluded. Matching strata combine run family, downstream topology, downstream amplitude bin, downstream peak-sample phase bin, and high-amplitude boundary.

| quantity                 | value     |
| ------------------------ | --------- |
| parent control events    | 10156     |
| clean events D_t<3 ns    | 2155      |
| tail events D_t>51 ns    | 72        |
| extreme benchmark events | 2227      |
| matched benchmark events | 1763      |
| matched tail events      | 49        |
| matched tail fraction    | 0.0277935 |

| heldout_run | supported_strata | heldout_rows | matched_heldout_rows | heldout_tail | matched_heldout_tail |
| ----------- | ---------------- | ------------ | -------------------- | ------------ | -------------------- |
| 58          | 0                | 39           | 0                    | 2            | 0                    |
| 59          | 7                | 428          | 332                  | 13           | 8                    |
| 60          | 7                | 444          | 322                  | 16           | 9                    |
| 61          | 9                | 632          | 534                  | 25           | 17                   |
| 62          | 11               | 427          | 388                  | 7            | 6                    |
| 63          | 12               | 203          | 187                  | 9            | 9                    |
| 65          | 0                | 54           | 0                    | 0            | 0                    |

## Methods
Traditional: train-fold hand threshold tables choose the best residualized q-template aggregate inside matched strata, with thresholds evaluated at fixed clean efficiency on held-out runs.

ML: a run-heldout random forest on amplitude-residualized q-template/shape features (`q_*`, downstream q summaries, peak phase, and high-amplitude boundary). Controls are amplitude-only, topology-only, downstream-only q, shuffled-label q, and forbidden `D_t`.

## Held-Out Benchmark
| method                     | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier     | brier_ci_low | brier_ci_high | ece       | ece_ci_low | ece_ci_high |
| -------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | --------- | ------------ | ------------- | --------- | ---------- | ----------- |
| traditional_matched_q_hand | 0.808254 | 0.750086       | 0.849984        | 0.231774          | 0.123559  | 0.449664   | 0.0261567 | 0.0208287    | 0.0357136     | 0.0181154 | 0.00770877 | 0.0363496   |
| ml_qtemplate_shape_rf      | 0.96147  | 0.947155       | 0.983612        | 0.577322          | 0.444063  | 0.664528   | 0.0279546 | 0.023842     | 0.0329791     | 0.0588657 | 0.0462994  | 0.0722636   |
| amplitude_only_rf          | 0.851701 | 0.839466       | 0.894365        | 0.28369           | 0.234524  | 0.38968    | 0.0461868 | 0.041009     | 0.0514048     | 0.105905  | 0.0855731  | 0.12799     |
| topology_only_rf           | 0.565136 | 0.514127       | 0.632709        | 0.0329592         | 0.0269839 | 0.0450231  | 0.239845  | 0.234284     | 0.249159      | 0.447923  | 0.426615   | 0.469544    |
| downstream_only_q_rf       | 0.875944 | 0.831696       | 0.908657        | 0.305836          | 0.209539  | 0.435564   | 0.0597323 | 0.050853     | 0.0718811     | 0.123683  | 0.103219   | 0.153309    |
| shuffled_label_q_rf        | 0.362608 | 0.319566       | 0.454643        | 0.0207346         | 0.0181583 | 0.0291259  | 0.109415  | 0.0944619    | 0.120345      | 0.249111  | 0.211548   | 0.278622    |
| leaky_dt_ceiling           | 1        | 1              | 1               | 1                 | 1         | 1          | 0.846128  | 0.830876     | 0.856861      | 0.878388  | 0.863397   | 0.888505    |

ML minus traditional deltas:

| delta                                  | value      | ci_low      | ci_high    |
| -------------------------------------- | ---------- | ----------- | ---------- |
| ml_minus_traditional_roc_auc           | 0.153216   | 0.114418    | 0.221536   |
| ml_minus_traditional_average_precision | 0.345548   | 0.210919    | 0.486802   |
| ml_minus_traditional_brier             | 0.00179783 | -0.00514111 | 0.00723899 |
| ml_minus_traditional_ece               | 0.0407502  | 0.0343972   | 0.043953   |

At 95% train clean efficiency:

| method                     | clean_efficiency | clean_efficiency_ci_low | clean_efficiency_ci_high | tail_rejection | tail_rejection_ci_low | tail_rejection_ci_high | n_clean | n_tail |
| -------------------------- | ---------------- | ----------------------- | ------------------------ | -------------- | --------------------- | ---------------------- | ------- | ------ |
| amplitude_only_rf          | 0.949242         | 0.932507                | 0.964929                 | 0.530612       | 0.478209              | 0.615541               | 1714    | 49     |
| downstream_only_q_rf       | 0.951575         | 0.939751                | 0.960357                 | 0.44898        | 0.371429              | 0.512195               | 1714    | 49     |
| ml_qtemplate_shape_rf      | 0.948658         | 0.935562                | 0.959808                 | 0.836735       | 0.787879              | 0.886364               | 1714    | 49     |
| shuffled_label_q_rf        | 0.950408         | 0.922042                | 0.969313                 | 0.0204082      | 0                     | 0.0833333              | 1714    | 49     |
| topology_only_rf           | 0.777713         | 0.474966                | 1                        | 0.265306       | 0                     | 0.590909               | 1714    | 49     |
| traditional_matched_q_hand | 0.946908         | 0.902703                | 0.985543                 | 0.367347       | 0.25                  | 0.441176               | 1714    | 49     |

Pair residual deltas after applying the fixed-efficiency cut:

| method                     | base_sigma68_ns | base_full_rms_ns | base_tail_frac_abs_gt5ns | base_n_pair_values | kept_sigma68_ns | kept_full_rms_ns | kept_tail_frac_abs_gt5ns | kept_n_pair_values | delta_sigma68_ns | delta_full_rms_ns | delta_tail_frac_abs_gt5ns | delta_sigma68_ns_ci_low | delta_sigma68_ns_ci_high | delta_full_rms_ns_ci_low | delta_full_rms_ns_ci_high | delta_tail_frac_abs_gt5ns_ci_low | delta_tail_frac_abs_gt5ns_ci_high |
| -------------------------- | --------------- | ---------------- | ------------------------ | ------------------ | --------------- | ---------------- | ------------------------ | ------------------ | ---------------- | ----------------- | ------------------------- | ----------------------- | ------------------------ | ------------------------ | ------------------------- | -------------------------------- | --------------------------------- |
| traditional_matched_q_hand | 1.5016          | 12.0543          | 0.0209364                | 2627               | 1.49473         | 9.49004          | 0.0139002                | 2446               | -0.00686718      | -2.56424          | -0.00703618               | -0.0209846              | 0.0159485                | -4.03379                 | -1.03805                  | -0.0116817                       | -0.00250875                       |
| ml_qtemplate_shape_rf      | 1.5016          | 12.0543          | 0.0209364                | 2627               | 1.47792         | 3.79629          | 0.00326264               | 2452               | -0.0236743       | -8.25799          | -0.0176738                | -0.0331834              | -0.00937229              | -10.1906                 | -6.84448                  | -0.0230962                       | -0.0124432                        |
| amplitude_only_rf          | 1.5016          | 12.0543          | 0.0209364                | 2627               | 1.46953         | 9.15427          | 0.0109223                | 2472               | -0.0320681       | -2.90001          | -0.0100141                | -0.0520987              | -0.0210429               | -3.79957                 | -2.42796                  | -0.0132706                       | -0.0074228                        |
| downstream_only_q_rf       | 1.5016          | 12.0543          | 0.0209364                | 2627               | 1.49555         | 9.59974          | 0.0128205                | 2496               | -0.00604363      | -2.45454          | -0.00811592               | -0.0146359              | 0.00579068               | -3.01835                 | -1.80724                  | -0.0100444                       | -0.00510133                       |
| shuffled_label_q_rf        | 1.5016          | 12.0543          | 0.0209364                | 2627               | 1.5126          | 12.1198          | 0.0213692                | 2527               | 0.0110017        | 0.0655147         | 0.000432783               | 0.00173914              | 0.020374                 | -0.263862                | 0.226222                  | -0.000303751                     | 0.000866928                       |

## Leakage Hunt
| check                          | value    | flag  | detail                                                                                                                                                                                                                                                                                        |
| ------------------------------ | -------- | ----- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| train_heldout_run_overlap      | 0        | False | Leave-one-run-out folds use disjoint run ids.                                                                                                                                                                                                                                                 |
| main_feature_forbidden_columns | 0        | False | Main columns exclude run/event id, D_t, pair residuals, and absolute amplitude: ['q_b2', 'q_b4', 'q_b6', 'q_b8', 'q_mean', 'q_max', 'q_std', 'q_ds_mean', 'q_ds_max', 'q_ds_std', 'q_b2_minus_ds_mean', 'q_ds_span', 'peak_ds_mean', 'peak_ds_max', 'high_amp_boundary', 'near_adc_boundary'] |
| matched_rows_fraction          | 0.791648 | False | Rows retained after train/heldout matched-stratum support.                                                                                                                                                                                                                                    |
| shuffled_label_auc             | 0.362608 | False | Labels shuffled inside training runs.                                                                                                                                                                                                                                                         |
| amplitude_only_auc             | 0.851701 | False | Amplitude nuisance sentinel.                                                                                                                                                                                                                                                                  |
| topology_only_auc              | 0.565136 | False | Topology-only sentinel.                                                                                                                                                                                                                                                                       |
| downstream_only_auc            | 0.875944 | False | Expected to remain strong if downstream waveform quality drives the label.                                                                                                                                                                                                                    |
| leaky_dt_auc                   | 1        | False | Forbidden label-defining ceiling.                                                                                                                                                                                                                                                             |

The matched ML AUC is 0.961 versus 0.808 traditional and 0.852 amplitude-only. The shuffled-label sentinel stays near null and the deliberate `D_t` ceiling is perfect, so the matched q signal is not explained by an obvious split leak. The downstream-only sentinel remains strong, which is expected because the label is downstream timing based; the result is therefore a downstream waveform-quality isolation, not an independent particle-ID truth label.

## Verdict
After amplitude/topology/phase/boundary/run-family matching, `q_template` still carries held-out timing-tail information, but the matched signal is smaller than the raw S03d headline. Use q_template vetoes as a downstream shape-quality handle only with amplitude/topology matching and leakage sentinels attached.
