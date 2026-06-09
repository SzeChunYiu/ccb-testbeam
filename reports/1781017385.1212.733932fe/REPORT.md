# P01e: control-stratum permutation null for P01b latents

**Ticket:** `1781017385.1212.733932fe`

## Reproduction first
The script scanned raw B-stack ROOT from `data/root/root` before fitting any probe. The P01b/S00
selected-pulse count reproduced **640,737** rows versus **640,737** expected, and the
released latent artifact key hash matched the raw `(run,event_index,stave_index)` scan.

## Null construction
The released P01b latent table was joined to raw ROOT-derived waveform controls by row key. For
each null replicate, the latent rows were permuted only within `(run, topology_mask, amplitude_bin,
stave)` strata. This preserves the held-out run mix, topology, amplitude, and stave controls while
breaking row-level latent-to-waveform alignment. The benchmark sample is capped at
400 pulses per `(run,stave)` cell; downstream probes train on non-held-out runs and
evaluate only runs `42, 57, 64, 65`. CIs are held-out run/event bootstraps.

## Held-out probe lift over control-stratum null
| method      | target      | observed_balanced_accuracy | observed_ci_low | observed_ci_high | null_median | null_p95 | lift   | lift_ci_low | lift_ci_high |
| ----------- | ----------- | -------------------------- | --------------- | ---------------- | ----------- | -------- | ------ | ----------- | ------------ |
| traditional | manual_flag | 0.8154                     | 0.7783          | 0.8531           | 0.3936      | 0.4058   | 0.4217 | 0.3631      | 0.4888       |
| traditional | peak_group  | 0.8134                     | 0.7747          | 0.8402           | 0.4818      | 0.4864   | 0.3316 | 0.3003      | 0.3586       |
| ml          | manual_flag | 0.9676                     | 0.9435          | 0.9797           | 0.5109      | 0.5282   | 0.4567 | 0.4149      | 0.5114       |
| ml          | peak_group  | 0.9517                     | 0.9318          | 0.9672           | 0.4882      | 0.4962   | 0.4635 | 0.4258      | 0.5012       |

The primary ML/manual morphology probe scores **0.9676** balanced accuracy, while its
stratum-permuted null median is **0.5109**. The observed-minus-null lift is
**0.4567** with a held-out bootstrap CI of **[0.4149, 0.5114]**.

## Leakage checks
| check                                                   | value               | pass | note                                                               |
| ------------------------------------------------------- | ------------------- | ---- | ------------------------------------------------------------------ |
| train_heldout_run_overlap                               | 0                   | True | must be zero for split-by-run                                      |
| heldout_runs_match_config                               | 42,57,64,65         | True | all benchmark rows are from configured held-out runs               |
| p01b_key_order_matches_raw_scan                         | True                | True | prevents latent/waveform row offset leakage                        |
| permutation_changed_latent_fraction                     | 0.9948652879418545  | True | should move almost all rows within control strata                  |
| traditional_manual_flag_controls_only_vs_observed_delta | 0.4279875614082439  | True | large negative values would mean controls-only explains the result |
| traditional_peak_group_controls_only_vs_observed_delta  | 0.3399879398477038  | True | large negative values would mean controls-only explains the result |
| ml_manual_flag_controls_only_vs_observed_delta          | 0.4441029573511489  | True | large negative values would mean controls-only explains the result |
| ml_peak_group_controls_only_vs_observed_delta           | 0.4729187085240747  | True | large negative values would mean controls-only explains the result |
| traditional_manual_flag_train_label_shuffle_score       | 0.23351738179334633 | True | near-chance sanity check for too-good scores                       |
| traditional_peak_group_train_label_shuffle_score        | 0.16831603092836583 | True | near-chance sanity check for too-good scores                       |
| ml_manual_flag_train_label_shuffle_score                | 0.19954566136552496 | True | near-chance sanity check for too-good scores                       |
| ml_peak_group_train_label_shuffle_score                 | 0.20677296961518257 | True | near-chance sanity check for too-good scores                       |

The score is high because the target labels are direct waveform morphology summaries and P01b is a
waveform embedding. The controls-only and train-label-shuffle sentinels remain below the observed
latent probes, and the strict within-run/topology/amplitude/stave null removes the coarse-control
explanation.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p01e_1781017385_1212_733932fe_control_stratum_permutation_null.py --config configs/p01e_1781017385_1212_733932fe_control_stratum_permutation_null.json
```
