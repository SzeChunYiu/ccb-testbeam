# S13f: exactly-two current-family timing-tail null

- **Ticket:** `1781063920.513.7c742542`
- **Worker:** `testbeam-laptop-1`
- **Data:** raw B-stack ROOT under `data/root/root`; no Monte Carlo and no derived tables are used for the reproduction gate.

## Abstract

This study tests whether the Sample-II current-family timing-tail contrast found in the broader S07/S13 line survives when the event support is restricted from all-three downstream events to exactly-two downstream events. The result is a matched, leave-run-pair-out benchmark: a transparent timing/template baseline is compared with ridge, gradient-boosted trees, MLP, 1D-CNN, and a support-gated CNN. The pre-registered positive-signal gate requires traditional and learned high-minus-low tail-score deltas to have the same positive sign with bootstrap 95% CIs excluding zero.

## Reproduction From Raw ROOT

For every configured run the script opens `h101`, reads `EVENTNO`, `EVT`, and `HRDv`, reshapes the raw HRD vector to eight channels by 18 samples, subtracts the per-channel median over samples 0--3, and applies the fixed amplitude gate A > 1000 ADC. The S13d parent population is B2 plus at least two selected downstream staves. The new S13f population is the exact complement inside that parent with exactly two selected downstream staves.

| quantity                                          |   report_value |   reproduced |   delta | pass   |
|:--------------------------------------------------|---------------:|-------------:|--------:|:-------|
| S13d parent control events, B2 and >=2 downstream |          10156 |        10156 |       0 | True   |
| S13d parent clean events, D_t<3 ns                |           2155 |         2155 |       0 | True   |
| S13d parent gross events, documented D_t>50 ns    |             74 |           74 |       0 | True   |
| S13d parent gross events, guarded D_t>51 ns       |             72 |           72 |       0 | True   |
| S13d all-three control events                     |           3774 |         3774 |       0 | True   |
| S13d all-three guarded gross events               |             22 |           22 |       0 | True   |
| S13f exactly-two control events                   |           6382 |         6382 |       0 | True   |
| S13f exactly-two guarded gross events             |             50 |           50 |       0 | True   |

Run-level reconstruction:

|   run | current_run_family      |   raw_events |   parent_control_events |   all_three_events |   exactly_two_events |   exactly_two_rate |
|------:|:------------------------|-------------:|------------------------:|-------------------:|---------------------:|-------------------:|
|    58 | low_all_three_rate_edge |        34141 |                     201 |                 72 |                  129 |          0.0037784 |
|    59 | mid_all_three_rate      |        42303 |                    2161 |                749 |                 1412 |          0.033378  |
|    60 | high_all_three_rate     |        36074 |                    2025 |                802 |                 1223 |          0.033903  |
|    61 | high_all_three_rate     |        36535 |                    2319 |                925 |                 1394 |          0.038155  |
|    62 | high_all_three_rate     |        37584 |                    2154 |                798 |                 1356 |          0.036079  |
|    63 | mid_all_three_rate      |        37030 |                    1045 |                365 |                  680 |          0.018363  |
|    65 | low_all_three_rate_edge |        38424 |                     251 |                 63 |                  188 |          0.0048928 |

Exactly-two support by current family and downstream pair:

| run_family              | downstream_pair   |   events |   gross_tail_events |   clean_events |   mean_dt_ns |
|:------------------------|:------------------|---------:|--------------------:|---------------:|-------------:|
| high_all_three_rate     | B4+B6             |     3883 |                  27 |            974 |     4.82312  |
| high_all_three_rate     | B4+B8             |       27 |                   6 |              4 |    30.2624   |
| high_all_three_rate     | B6+B8             |       63 |                   0 |             61 |     1.11913  |
| low_all_three_rate_edge | B4+B6             |      303 |                   0 |             68 |     4.44368  |
| low_all_three_rate_edge | B4+B8             |        5 |                   2 |              1 |    46.3673   |
| low_all_three_rate_edge | B6+B8             |        9 |                   0 |              9 |     0.884382 |
| mid_all_three_rate      | B4+B6             |     2023 |                  13 |            403 |     5.17194  |
| mid_all_three_rate      | B4+B8             |       15 |                   2 |              2 |    16.6294   |
| mid_all_three_rate      | B6+B8             |       54 |                   0 |             54 |     1.12481  |

## Methods

### Timing definitions

For each selected stave j, the constant-fraction time t_j is the linear interpolation crossing of f A_j with f = 0.2. For exactly-two downstream events the timing spread is

```text
D_t = max(t_j : j in selected downstream) - min(t_j : j in selected downstream).
```

Clean labels are D_t < 3 ns and guarded gross-tail labels are D_t > 51 ns. The label is used only to train timing-tail scorers on non-held-out runs; the reported science metric is not label accuracy but the held-out high-rate minus low-edge score contrast after matching.

### Split and support matching

Each fold holds out one low-edge run and one high-rate run. Training uses all other Sample-II runs, including mid-family runs, and the held-out low/high rows are matched inside train-derived quantile cells for event max amplitude, log event charge, B2 amplitude, B2/event saturation, baseline size, baseline-lowering flag, anomaly tail atom, and the exact downstream-pair topology. CIs resample the six held-out run-pair folds with replacement.

### Models

The strong traditional comparator is a calibrated logistic timing/template score using D_t, baseline size, and the anomaly atom. In equation form, p_tail = sigma(beta_0 + beta_1 D_t + beta_2 |b| + beta_3 a), with Platt calibration fit inside the training fold. The standard ML panel excludes run id, event id, current labels, D_t/C_t, explicit topology flags, and absolute amplitudes. Ridge is L2-penalized logistic regression on amplitude-normalized waveform shape summaries; GBT is `HistGradientBoostingClassifier`; MLP is a tabular neural net with early stopping; 1D-CNN convolves the four normalized B-stave waveform traces. The new `support_gated_cnn_new` intentionally gates the CNN embedding with support atoms (charge, B2 amplitude, baseline, anomaly, saturation) to test whether explicit support awareness creates a stronger residual probe.

### Metrics

For score s, the primary contrast is Delta_s = E[s | high-rate] - E[s | low-edge] on matched held-out rows. The fixed-efficiency enrichment is the high-rate fraction above the low-edge 90th percentile minus 0.10. Current-family AUC is a diagnostic of whether the timing-tail score separates current family after matching.

## Results

Winner by the pre-registered ranking (highest held-out current-family AUC among real methods; tie by smaller Brier-style score spread) is **`support_gated_cnn_new`** with AUC 0.5372 [0.5121, 0.5616] and Delta_s -0.00594 [-0.01955, 0.00576].

The traditional comparator has Delta_s 0.00804 [0.00680, 0.00988] and AUC 0.5038. Positive-signal gate: **False**.

| method                      |   high_minus_low_score |   high_minus_low_ci_low |   high_minus_low_ci_high |   fixed_eff_tail_excess |   fixed_eff_tail_excess_ci_low |   fixed_eff_tail_excess_ci_high |   current_family_auc |   current_family_auc_ci_low |   current_family_auc_ci_high |   n_matched_events |
|:----------------------------|-----------------------:|------------------------:|-------------------------:|------------------------:|-------------------------------:|--------------------------------:|---------------------:|----------------------------:|-----------------------------:|-------------------:|
| support_gated_cnn_new       |             -0.0059369 |             -0.019554   |                0.0057612 |              -0.029337  |                     -0.054094  |                      -0.012627  |              0.53721 |                     0.51213 |                      0.56164 |               1568 |
| cnn1d_waveform              |             -0.0066532 |             -0.017078   |                0.0021772 |              -0.028061  |                     -0.056102  |                      -0.0088988 |              0.5146  |                     0.48299 |                      0.54741 |               1568 |
| gradient_boosted_trees      |              0.0067251 |              0.0030999  |                0.010416  |              -0.0063776 |                     -0.020979  |                       0.0027287 |              0.51285 |                     0.48762 |                      0.53315 |               1568 |
| ridge_waveform              |              0.0056003 |             -0.00022547 |                0.012747  |               0.0076531 |                     -0.0033186 |                       0.03049   |              0.51271 |                     0.50403 |                      0.52314 |               1568 |
| traditional_timing_template |              0.0080434 |              0.006804   |                0.0098778 |               0         |                      0         |                       0         |              0.50384 |                     0.49881 |                      0.50851 |               1568 |
| mlp_waveform                |             -0.0018865 |             -0.0078154  |                0.0049593 |              -0.014031  |                     -0.043896  |                       0.0092838 |              0.48502 |                     0.46753 |                      0.49818 |               1568 |

Held-out fold details for the traditional comparator, winner, and shuffled-label sentinel:

| fold                 | method                      |   n_matched_events |   high_minus_low_score |   fixed_eff_tail_excess |   current_family_auc |   low_gross_events |   high_gross_events |
|:---------------------|:----------------------------|-------------------:|-----------------------:|------------------------:|---------------------:|-------------------:|--------------------:|
| holdout_low58_high60 | traditional_timing_template |                214 |             0.0071094  |               0         |              0.5     |                  0 |                   1 |
| holdout_low58_high60 | support_gated_cnn_new       |                214 |            -0.017097   |              -0.037383  |              0.54184 |                  0 |                   1 |
| holdout_low58_high60 | shuffled_label_gbt_control  |                214 |             0.00053323 |              -0.0093458 |              0.49672 |                  0 |                   1 |
| holdout_low58_high61 | traditional_timing_template |                208 |             0.0075083  |               0         |              0.50943 |                  0 |                   1 |
| holdout_low58_high61 | support_gated_cnn_new       |                208 |            -0.031927   |              -0.076923  |              0.49136 |                  0 |                   1 |
| holdout_low58_high61 | shuffled_label_gbt_control  |                208 |            -0.0003794  |               0         |              0.52173 |                  0 |                   1 |
| holdout_low58_high62 | traditional_timing_template |                224 |             0.0068181  |               0         |              0.49562 |                  0 |                   1 |
| holdout_low58_high62 | support_gated_cnn_new       |                224 |            -0.02417    |              -0.053571  |              0.50191 |                  0 |                   1 |
| holdout_low58_high62 | shuffled_label_gbt_control  |                224 |            -0.00080295 |              -0.071429  |              0.45241 |                  0 |                   1 |
| holdout_low65_high60 | traditional_timing_template |                280 |             0.0071541  |               0         |              0.51431 |                  0 |                   1 |
| holdout_low65_high60 | support_gated_cnn_new       |                280 |             0.0099851  |              -0.014286  |              0.59485 |                  0 |                   1 |
| holdout_low65_high60 | shuffled_label_gbt_control  |                280 |             0.001436   |               0.014286  |              0.44602 |                  0 |                   1 |
| holdout_low65_high61 | traditional_timing_template |                306 |             0.0065341  |               0         |              0.50002 |                  0 |                   1 |
| holdout_low65_high61 | support_gated_cnn_new       |                306 |             0.0091859  |              -0.019608  |              0.56371 |                  0 |                   1 |
| holdout_low65_high61 | shuffled_label_gbt_control  |                306 |            -0.0019692  |              -0.039216  |              0.47251 |                  0 |                   1 |
| holdout_low65_high62 | traditional_timing_template |                336 |             0.011902   |               0         |              0.50301 |                  0 |                   2 |
| holdout_low65_high62 | support_gated_cnn_new       |                336 |             0.0023749  |               0         |              0.5262  |                  0 |                   2 |
| holdout_low65_high62 | shuffled_label_gbt_control  |                336 |             0.0001097  |               0.017857  |              0.49709 |                  0 |                   2 |

## Leakage and Sentinels

No leakage check flagged. Train/test runs are disjoint, event overlap is zero, and the standard ML feature matrix excludes the forbidden identifiers, current labels, timing observables, explicit topology flags, and absolute amplitudes.

## Systematics

- The exactly-two population is larger than the all-three population but mixes three downstream-pair topologies; the matching cell includes the pair label, so the current-family comparison is not driven by a different B4/B6/B8 composition.
- The gross-tail label is sparse. This is why all headline intervals use run-pair bootstrap CIs rather than event-level bootstrap CIs.
- The support-gated CNN is deliberately not used as a leakage-clean standard ML score because it receives support atoms. Its value is diagnostic: if it wins only by support atoms, the effect is a support/composition effect rather than a waveform-shape tail effect.
- The fixed ADC threshold and CFD fraction are inherited from S13d; varying them would be a separate systematic scan.
- CIs cover run-pair resampling, not all choices of matching bins, model hyperparameters, or tail-label thresholds.

## Caveats

The analysis cannot prove the absence of a small current-dependent timing-tail effect. It tests whether a practically useful effect remains after the specific S13d/S13f support restrictions. Sparse low-edge support and gross-tail scarcity make sign-stable positive claims hard; a significant winner in AUC should therefore be interpreted as a detector-support diagnostic unless Delta_s also passes the positive-signal gate.

## Interpretation

S13f reproduced 6382 exactly-two events from raw ROOT and benchmarked 6 real methods over six held-out run-pair folds. The winner is support_gated_cnn_new by current-family AUC, but the positive-signal gate is False; therefore the exactly-two support does not provide a robust positive high-rate timing-tail claim unless both traditional and ML deltas clear zero.

## Follow-up Tickets

No new ticket is proposed from this run; the result is adequately covered by existing S13 support-collapse and S02 timing-drift follow-ups.

## Artifacts

`reproduction_match_table.csv`, `run_family_metadata.csv`, `exactly_two_population.csv`, `heldout_run_pair_metrics.csv`, `pooled_heldout_bootstrap_metrics.csv`, `heldout_matched_timing_tail_scores.csv`, `leakage_checks.csv`, `input_sha256.csv`, figures, `result.json`, and `manifest.json`.

Runtime: 115.4 s.
