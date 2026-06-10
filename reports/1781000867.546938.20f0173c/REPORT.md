# S13b: run-transfer CWoLa current classifier

- **Ticket:** `1781000867.546938.20f0173c`
- **Worker:** `testbeam-laptop-2`
- **Data:** raw B-stack ROOT under `data/root/root`

## Question

Is the S10 high/low ML pile-up-score ratio stable when a weak current classifier is trained and tested across independent run blocks, rather than relying only on the two-low-run reference?

## Reproduction first

The S10 low-current-trained injection score was rerun from raw ROOT before the new analysis. The reproduced high/low mean-score ratio is **1.297**; the reproduced low and high score means are **0.1213** and **0.1574**.

| quantity                                             |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| S10 low-current-trained ML score high/low mean ratio |         1.297  |     1.29708  |  7.57958e-05 |       0.005 | True   |
| S10 low-current ML score mean                        |         0.1213 |     0.121349 |  4.91622e-05 |       0.002 | True   |
| S10 high-current ML score mean                       |         0.1574 |     0.157399 | -9.38868e-07 |       0.002 | True   |

## Methods

Traditional baselines are (1) the downstream-topology high/low rate ratio per selected event and (2) a train-only single waveform-shape feature selected inside each run block and calibrated with a one-feature logistic model. The ML method is a CWoLa random forest trained to distinguish high-current from low-current selected pulses using normalized waveform samples plus pulse-shape summaries. All models exclude run, event number, current label columns, and downstream/topology labels.

The split is by run block: `A_to_B` trains on low run 46 plus high runs 44,45,48-51 and tests on low run 47 plus high runs 52-57; `B_to_A` reverses that split. Intervals resample held-out runs within current group. Because there are only two low-current runs, each fold has one low run, so fold-level low-current variability is necessarily limited; the pooled out-of-block CI resamples both low runs.

## Results

Pooled out-of-block CWoLa RF high/low score ratio: **1.220** [1.193, 1.257], held-out current AUC **0.668** [0.656, 0.682].

The one-feature traditional shape score gives ratio **1.064** [0.982, 1.095] and AUC **0.633**. The downstream-topology rate ratio is **1.445** [1.220, 2.542]. The shuffled-label RF ratio is **1.020** and AUC **0.559**.

| fold   | method                          |   score_high_over_low |   score_high_over_low_ci_low |   score_high_over_low_ci_high |   heldout_current_auc |
|:-------|:--------------------------------|----------------------:|-----------------------------:|------------------------------:|----------------------:|
| A_to_B | traditional_single_shape        |              1.07825  |                      1.04301 |                      1.10821  |              0.55451  |
| A_to_B | cwola_rf_shape                  |              1.22328  |                      1.1745  |                      1.25856  |              0.668561 |
| A_to_B | shuffled_label_rf               |              1.01149  |                      1.00561 |                      1.01807  |              0.534134 |
| A_to_B | traditional_downstream_topology |              1.18824  |                      1.01879 |                      1.39858  |            nan        |
| B_to_A | traditional_single_shape        |              0.998651 |                      0.99751 |                      0.999776 |              0.5887   |
| B_to_A | cwola_rf_shape                  |              1.23359  |                      1.2014  |                      1.2605   |              0.673697 |
| B_to_A | shuffled_label_rf               |              1.03352  |                      1.02239 |                      1.04571  |              0.591975 |
| B_to_A | traditional_downstream_topology |              2.68851  |                      2.19278 |                      3.56535  |            nan        |

## Leakage checks

No leakage check flagged. Train/test runs are disjoint, train/test event overlap is zero, forbidden identifier/topology columns are excluded, shuffled-label RF is near chance, and no CWoLa held-out AUC is suspiciously close to one.

## Interpretation

The CWoLa score transfers, but its high/low ratio is not a stable reproduction of the S10 1.297 pile-up-score ratio. The transparent downstream-topology ratio is larger and remains the stronger current-rate handle. CWoLa adds a modest waveform-shape current discriminator, not a clean calibrated beam pile-up fraction.

## Artifacts

`reproduction_match_table.csv`, `s10_reproduction_ml_score_by_group.csv`, `heldout_run_block_metrics.csv`, `pooled_run_bootstrap_metrics.csv`, `traditional_feature_choices.csv`, `leakage_checks.csv`, `topology_by_run.csv`, `selected_pulse_counts.csv`, `heldout_scores_by_pulse.csv`, `input_sha256.csv`, figures, `result.json`, and `manifest.json`.

Runtime: 118.8 s.
