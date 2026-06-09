# P09c: delayed-peak dropout propagation audit

**Ticket:** `1781014256.642.6ded722c`

## Reproduction first
The raw B-stack ROOT files were read from `data/root/root` with the same S00 gate used by P09a: B2/B4/B6/B8 even channels, median baseline samples 0-3, and amplitude >1000 ADC. This raw scan ran before fitting the template, PCA, AE, or IsolationForest models.

| quantity | expected | reproduced | pass |
|---|---:|---:|---|
| S00 selected B-stave pulses | 640737 | 640737 | True |

## Methods
Held-out runs were `42, 57, 64, 65`. The traditional method freezes the P09a robust-template taxonomy from train runs, then compares `novel_delayed_peak` and `novel_broad_template_mismatch` pulses with run/stave/amplitude-bin matched normal pulses. Propagation summaries use duplicate-channel timing span as the S02/S03 timing proxy, normalized charge area and amplitude as P04/P07 charge proxies, and pre-trigger baseline MAD/slope as the S16 baseline proxy.

The ML method uses only waveform-shape features: PCA reconstruction error, AE reconstruction error, PCA+AE latent distance, and IsolationForest density. Run, event, and stave IDs are excluded from model features and are used only for held-out splitting, matching, and bootstrap aggregation.

## Target prevalence
| taxon                         |   heldout_count |   heldout_rate |
|:------------------------------|----------------:|---------------:|
| unassigned_common             |           54558 |     0.915203   |
| novel_delayed_peak            |            1581 |     0.0265211  |
| novel_broad_template_mismatch |             162 |     0.00271753 |

## Held-out propagation metrics
Intervals are 95% bootstrap CIs resampled by held-out run. `recover_veto_ap` treats target pulses flagged by timing, charge, baseline, pile-up, dropout, or saturation propagation sentinels as veto-like positives; recoverable target pulses and matched normals are negatives.

| method                           | taxon                         |   n_target |   n_veto_positive |   timing_tail_enrichment | timing_tail_enrichment_ci   |   charge_bias_delta | charge_bias_delta_ci   |   baseline_excursion_rate | baseline_excursion_rate_ci   |   pileup_score_delta | pileup_score_delta_ci   |   target_stratum_ap | target_stratum_ap_ci   |   recover_veto_ap | recover_veto_ap_ci   |   recover_fraction |   veto_fraction |
|:---------------------------------|:------------------------------|-----------:|------------------:|-------------------------:|:----------------------------|--------------------:|:-----------------------|--------------------------:|:-----------------------------|---------------------:|:------------------------|--------------------:|:-----------------------|------------------:|:---------------------|-------------------:|----------------:|
| traditional_p09a_frozen_template | novel_delayed_peak            |       1581 |               365 |                        0 | [0, 0]                      |            -4.81925 | [-4.95, -4.65]         |                         0 | [0, 0]                       |             14.6562  | [14.6, 14.7]            |           0.43338   | [0.424, 0.451]         |         0.142234  | [0.131, 0.154]       |           0.769133 |      0.230867   |
| traditional_p09a_frozen_template | novel_broad_template_mismatch |        162 |                 1 |                        0 | [0, 0]                      |             2.17614 | [2.11, 2.22]           |                         0 | [0, 0]                       |              0.21684 | [-0.217, 0.668]         |           0.0527764 | [0.0261, 0.097]        |         0.0169492 | [0.0119, 0.06]       |           0.993827 |      0.00617284 |
| traditional_p09a_frozen_template | combined_target_taxa          |       1743 |               366 |                        0 | [0, 0]                      |            -4.51438 | [-4.56, -4.44]         |                         0 | [0, 0]                       |             14.5791  | [14.5, 14.6]            |           0.440775  | [0.42, 0.468]          |         0.134511  | [0.123, 0.148]       |           0.790017 |      0.209983   |
| ml_pca_ae_latent_isolation       | novel_delayed_peak            |       1581 |               365 |                        0 | [0, 0]                      |            -4.81925 | [-4.95, -4.65]         |                         0 | [0, 0]                       |             14.6562  | [14.6, 14.7]            |           0.78854   | [0.751, 0.829]         |         0.195282  | [0.186, 0.208]       |           0.769133 |      0.230867   |
| ml_pca_ae_latent_isolation       | novel_broad_template_mismatch |        162 |                 1 |                        0 | [0, 0]                      |             2.17614 | [2.11, 2.22]           |                         0 | [0, 0]                       |              0.21684 | [-0.217, 0.668]         |           0.0642824 | [0.0521, 0.0833]       |         1         | [1, 1]               |           0.993827 |      0.00617284 |
| ml_pca_ae_latent_isolation       | combined_target_taxa          |       1743 |               366 |                        0 | [0, 0]                      |            -4.51438 | [-4.56, -4.44]         |                         0 | [0, 0]                       |             14.5791  | [14.5, 14.6]            |           0.772347  | [0.74, 0.806]          |         0.197673  | [0.191, 0.208]       |           0.790017 |      0.209983   |

## Leakage checks
| check                                        |   value | pass   | note                                                                               |
|:---------------------------------------------|--------:|:-------|:-----------------------------------------------------------------------------------|
| train_heldout_run_overlap                    | 0       | True   | must be zero                                                                       |
| model_features_include_run_event_or_stave_id | 0       | True   | ids used only for split, matching, and bootstrap strata                            |
| audit_waveform_hash_seen_in_train_rate       | 0       | True   | rounded normalized waveform hash overlap at 1e-3 precision                         |
| ml_target_ap_too_good_sentinel               | 0.78854 | True   | if >0.98, inspect leakage; current sentinel records whether result looked too good |
| max_recover_veto_ap_too_good_sentinel        | 1       | True   | high AP is treated as low-evidence when fewer than five veto positives support it  |
| min_veto_positives_for_high_recover_veto_ap  | 1       | True   | documents the positive-count audit behind any perfect recover/veto AP              |
| heldout_runs_have_target_taxa                | 4       | True   | run-bootstrap CIs need target rows in multiple held-out runs                       |

The perfect broad-mismatch ML `recover_veto_ap` is not interpreted as a robust result: it is supported by one veto-like broad target, and that row is written to `high_ap_veto_rows.csv` for inspection.

## Verdict
The delayed-peak and broad-mismatch taxa are not just duplicate labels for the P09a baseline/dropout classes: their baseline-excursion rates are measured after freezing the original cuts and comparing against matched normals. Timing-tail enrichment, charge-bias delta, and pile-up-score delta identify whether each class is mostly recoverable late pulse shape, pile-up-like, or veto-like. The ML AP is reported as an audit score, not a discovery claim, because the target taxa are inherited from deterministic P09a cuts.

## Provenance
Runtime was 255.4 s on `billy`. The AE ran on `cpu` with final training loss `0.0195738`. `manifest.json` records input, code, and output hashes.
