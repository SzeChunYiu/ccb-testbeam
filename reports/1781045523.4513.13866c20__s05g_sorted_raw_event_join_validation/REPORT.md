# S05g: sorted raw-event join validation for A/B controls

## Abstract

S05g tests whether the sorted ROOT products used by A/B external-control consumers preserve the raw event identity and physical channel mapping required by the S05 covariance analyses.  The analysis first rebuilds the raw `HRDv` selected-pulse count gate on the configured S05 run universe (Sample I/II calibration and analysis runs, with run 43 excluded), then compares raw `EVENTNO`/`EVT` against sorted `hrdEvtNo` under three deterministic joins: entry order, `EVT` with occurrence rank, and a deliberately naive `EVENTNO` join.  It also benchmarks run-heldout leakage sentinels using Ridge/logistic, gradient-boosted trees, MLP, 1D-CNN, and a new agreement-gated CNN on deterministic bad-join controls.  No simulated Monte Carlo samples are used.

## Reproduction Gate

The B-stack raw pulse gate is

\[
A_{r,e,c} = \max_t H_{r,e,c,t} - \operatorname{median}_{t \in \{0,1,2,3\}} H_{r,e,c,t},
\quad c \in \{0,2,4,6\},
\quad A_{r,e,c} > 1000\,\mathrm{ADC} .
\]

The reproduced total is **640,737** selected B pulses; Sample-I analysis has **252,266**, and Sample-II analysis has **125,096**.  The expected anchors are 640,737, 252,266, and 125,096, respectively.  `result.json` records `reproduction_pass = True`.

## Deterministic Join Methods

For each stack and analysis run, the audit defines a raw record as `(EVENTNO, EVT, occurrence)` and a sorted record as `(hrdEvtNo, occurrence)`.  The principal join is

\[
J_{\mathrm{EVT}} = \{(i,j): EVT_i = hrdEvtNo_j,\; occ(EVT_i)=occ(hrdEvtNo_j)\},
\]

with entry-order and naive `EVENTNO` joins retained as stress controls.  The occurrence rank makes duplicate `EVT` handling explicit and prevents Cartesian expansion when a run contains repeated trigger counters.

### Event Identity

| stack   |   run |   raw_entries |   sorted_entries |   entry_count_delta |   raw_evt_duplicates |   sorted_hrdEvtNo_duplicates |   entry_order_evt_match_rate |
|:--------|------:|--------------:|-----------------:|--------------------:|---------------------:|-----------------------------:|-----------------------------:|
| A       |    44 |          4299 |             4299 |                   0 |                  209 |                          209 |                            1 |
| A       |    45 |         48208 |            48208 |                   0 |                31825 |                        31825 |                            1 |
| A       |    46 |          1444 |             1444 |                   0 |                   49 |                           49 |                            1 |
| A       |    47 |         10982 |            10982 |                   0 |                  494 |                          494 |                            1 |
| A       |    48 |         31671 |            31671 |                   0 |                15288 |                        15288 |                            1 |
| A       |    49 |         32325 |            32325 |                   0 |                15944 |                        15944 |                            1 |
| A       |    50 |         44824 |            44824 |                   0 |                28441 |                        28441 |                            1 |
| A       |    51 |         20566 |            20566 |                   0 |                 4232 |                         4232 |                            1 |
| A       |    52 |         10010 |            10010 |                   0 |                  484 |                          484 |                            1 |
| A       |    53 |         39621 |            39621 |                   0 |                23238 |                        23238 |                            1 |
| A       |    54 |         37385 |            37385 |                   0 |                21002 |                        21002 |                            1 |
| A       |    55 |         24409 |            24409 |                   0 |                 8093 |                         8093 |                            1 |

### Join Count Sensitivity

The table gives run-bootstrap means and 95% confidence intervals for the deterministic count observables.  Entry-order and occurrence-ranked `EVT` joins are expected to agree if sorted files preserve raw order; the naive `EVENTNO` join is expected to lose nearly all rows because `hrdEvtNo` stores raw `EVT`, not global `EVENTNO`.

| stack   | join_method    | metric                   |       value |      ci_low |      ci_high |   n_runs |
|:--------|:---------------|:-------------------------|------------:|------------:|-------------:|---------:|
| A       | entry_order    | joined_events            |   3.1e+04   |   2.5e+04   |    3.675e+04 |       21 |
| A       | entry_order    | raw_selected_pulses      | 503.6       | 231.9       |  849.3       |       21 |
| A       | entry_order    | sorted_any_clean_pulses  | 544         | 238.6       |  948.9       |       21 |
| A       | entry_order    | sorted_tr_clean_pulses   | 768         | 363.7       | 1205         |       21 |
| A       | entry_order    | event_join_loss_vs_entry |   0         |   0         |    0         |       21 |
| A       | entry_order    | joined_fraction_vs_entry |   1         |   1         |    1         |       21 |
| A       | eventno_naive  | joined_events            | 672.9       |   0         | 1931         |       21 |
| A       | eventno_naive  | raw_selected_pulses      |  33.81      |   0         |   90.29      |       21 |
| A       | eventno_naive  | sorted_any_clean_pulses  |  37.52      |   0         |   99.97      |       21 |
| A       | eventno_naive  | sorted_tr_clean_pulses   |  47.38      |   0         |  134.7       |       21 |
| A       | eventno_naive  | event_join_loss_vs_entry |   3.033e+04 |   2.435e+04 |    3.563e+04 |       21 |
| A       | eventno_naive  | joined_fraction_vs_entry |   0.03463   |   0         |    0.09199   |       21 |
| A       | evt_occurrence | joined_events            |   3.1e+04   |   2.5e+04   |    3.64e+04  |       21 |
| A       | evt_occurrence | raw_selected_pulses      | 503.6       | 204.1       |  866.8       |       21 |
| A       | evt_occurrence | sorted_any_clean_pulses  | 544         | 218         |  952.3       |       21 |
| A       | evt_occurrence | sorted_tr_clean_pulses   | 768         | 395.6       | 1201         |       21 |
| A       | evt_occurrence | event_join_loss_vs_entry |   0         |   0         |    0         |       21 |
| A       | evt_occurrence | joined_fraction_vs_entry |   1         |   1         |    1         |       21 |
| B       | entry_order    | joined_events            |   3.1e+04   |   2.504e+04 |    3.607e+04 |       21 |
| B       | entry_order    | raw_selected_pulses      |   1.797e+04 |   1.377e+04 |    2.247e+04 |       21 |
| B       | entry_order    | sorted_any_clean_pulses  |   1.797e+04 |   1.399e+04 |    2.174e+04 |       21 |
| B       | entry_order    | sorted_tr_clean_pulses   |   1.929e+04 |   1.485e+04 |    2.363e+04 |       21 |
| B       | entry_order    | event_join_loss_vs_entry |   0         |   0         |    0         |       21 |
| B       | entry_order    | joined_fraction_vs_entry |   1         |   1         |    1         |       21 |
| B       | eventno_naive  | joined_events            | 746.7       |   0         | 2073         |       21 |
| B       | eventno_naive  | raw_selected_pulses      | 357.5       |   0         | 1109         |       21 |
| B       | eventno_naive  | sorted_any_clean_pulses  | 353.3       |   0         |  941.1       |       21 |
| B       | eventno_naive  | sorted_tr_clean_pulses   | 385.2       |   0         |  985.7       |       21 |
| B       | eventno_naive  | event_join_loss_vs_entry |   3.025e+04 |   2.416e+04 |    3.567e+04 |       21 |
| B       | eventno_naive  | joined_fraction_vs_entry |   0.05181   |   0         |    0.1315    |       21 |

### Amplitude and Channel Mapping

Sorted `hrdMax` is compared both with the raw median-baseline amplitude and with the sorted waveform maximum from `hrd/hrd.sample`.  The former includes baseline-definition scatter; the latter tests exact sorted branch self-consistency and physical channel assignment.

| stack   | channel_name   | metric                 |   value |   ci_low |   ci_high |   n_runs |
|:--------|:---------------|:-----------------------|--------:|---------:|----------:|---------:|
| A       | A1             | corr_raw_amp_vs_hrdMax |  0.8605 |   0.841  |    0.8761 |       21 |
| A       | A3             | corr_raw_amp_vs_hrdMax |  0.9015 |   0.8824 |    0.921  |       21 |
| B       | B2             | corr_raw_amp_vs_hrdMax |  0.9345 |   0.9247 |    0.9451 |       21 |
| B       | B4             | corr_raw_amp_vs_hrdMax |  0.8989 |   0.8848 |    0.913  |       21 |
| B       | B6             | corr_raw_amp_vs_hrdMax |  0.9169 |   0.9007 |    0.9317 |       21 |
| B       | B8             | corr_raw_amp_vs_hrdMax |  0.913  |   0.8982 |    0.9315 |       21 |

| stack   | channel_name   | metric                                   |   value |   ci_low |   ci_high |   n_runs |
|:--------|:---------------|:-----------------------------------------|--------:|---------:|----------:|---------:|
| A       | A1             | sigma68_hrdMax_minus_sorted_wave_max_adc |       0 |        0 |         0 |       21 |
| A       | A3             | sigma68_hrdMax_minus_sorted_wave_max_adc |       0 |        0 |         0 |       21 |
| B       | B2             | sigma68_hrdMax_minus_sorted_wave_max_adc |       0 |        0 |         0 |       21 |
| B       | B4             | sigma68_hrdMax_minus_sorted_wave_max_adc |       0 |        0 |         0 |       21 |
| B       | B6             | sigma68_hrdMax_minus_sorted_wave_max_adc |       0 |        0 |         0 |       21 |
| B       | B8             | sigma68_hrdMax_minus_sorted_wave_max_adc |       0 |        0 |         0 |       21 |

## Leakage Sentinel Benchmark

The ML benchmark is a run-heldout binary sentinel.  Positive examples are correct occurrence-ranked `EVT` joins.  Negative controls are deterministic, data-derived failures: an entry shifted by one event and a physical-channel rotation.  Each example is represented as a four-channel sequence of sorted `hrdMax`, `hrdTrMax`, `hrdMaxTS`, joined raw amplitude, signed agreement residual, absolute residual, and stack code.  Identifiers (`run`, `EVENTNO`, `EVT`, entry index) are excluded from features.  The score is computed on held-out runs only:

\[
\widehat f_{-r} = \arg\min_f \sum_{r' \ne r} \ell\left(y_{r'}, f(x_{r'})\right),
\quad
s_r = \mathrm{AUC}\left(y_r, \widehat f_{-r}(x_r)\right).
\]

Run-bootstrap confidence intervals summarize held-out performance:

| method                  | metric            |   value |   ci_low |   ci_high |   n_runs |
|:------------------------|:------------------|--------:|---------:|----------:|---------:|
| gradient_boosted_trees  | accuracy          | 0.9349  |  0.9308  |   0.9393  |       21 |
| mlp                     | accuracy          | 0.8769  |  0.8709  |   0.8837  |       21 |
| ridge                   | accuracy          | 0.7772  |  0.7731  |   0.7818  |       21 |
| cnn_1d                  | accuracy          | 0.7658  |  0.7546  |   0.7748  |       21 |
| agreement_gated_cnn_new | accuracy          | 0.7597  |  0.7506  |   0.7688  |       21 |
| gradient_boosted_trees  | average_precision | 0.9654  |  0.9615  |   0.9685  |       21 |
| mlp                     | average_precision | 0.9011  |  0.8934  |   0.9092  |       21 |
| agreement_gated_cnn_new | average_precision | 0.7903  |  0.7734  |   0.8058  |       21 |
| cnn_1d                  | average_precision | 0.7814  |  0.763   |   0.7966  |       21 |
| ridge                   | average_precision | 0.7809  |  0.7711  |   0.7899  |       21 |
| cnn_1d                  | brier             | 0.1465  |  0.1412  |   0.1527  |       21 |
| agreement_gated_cnn_new | brier             | 0.1464  |  0.1412  |   0.1522  |       21 |
| ridge                   | brier             | 0.1409  |  0.1377  |   0.1449  |       21 |
| mlp                     | brier             | 0.08413 |  0.08062 |   0.08752 |       21 |
| gradient_boosted_trees  | brier             | 0.04778 |  0.04539 |   0.04976 |       21 |
| gradient_boosted_trees  | roc_auc           | 0.9839  |  0.9824  |   0.9854  |       21 |
| mlp                     | roc_auc           | 0.9515  |  0.947   |   0.9564  |       21 |
| agreement_gated_cnn_new | roc_auc           | 0.8904  |  0.8798  |   0.8994  |       21 |
| ridge                   | roc_auc           | 0.8858  |  0.879   |   0.8927  |       21 |
| cnn_1d                  | roc_auc           | 0.8833  |  0.8701  |   0.893   |       21 |

The sentinels are not used as corrections.  Their role is falsification: if a bad join or channel rotation were present, agreement residuals derived from sorted quality branches would make it detectable on held-out runs.  The actual deterministic audit selected `evt_occurrence` because it has complete event retention, explicit duplicate handling, and exact sorted-waveform/`hrdMax` agreement.

## Winner and Interpretation

The winner named in `result.json` is **deterministic_evt_occurrence_join**.  It is a traditional deterministic method, not a learned model: ML/NN sentinels successfully identify injected bad joins, but they do not supersede exact event-key agreement as the join authority.  The decisive observables are zero entry-count delta, equality of raw `EVT` and sorted `hrdEvtNo` under entry order, complete occurrence-ranked `EVT` retention, and zero-width `hrdMax - max(hrd/hrd.sample)` residuals.

## Systematics and Caveats

1. `hrdMax - raw HRDv median-baseline amplitude` is not expected to be identically zero because the sorted waveform baseline convention is not exactly the S00 median-of-first-four convention.  Therefore sorted-waveform self-consistency is the primary channel-mapping test, while raw-amplitude correlation is the cross-format sanity check.
2. The naive `EVENTNO` join is a stress control.  It should fail because sorted `hrdEvtNo` corresponds to raw `EVT`, while raw `EVENTNO` is a global counter range.
3. Duplicate `EVT` counters are handled by occurrence rank.  If future sorted production reorders duplicate events internally, this study should be rerun with a stronger waveform fingerprint key.
4. The neural models are CPU-budget sentinels trained on downsampled event controls.  They are sufficient to test detectability of deterministic bad joins, not to claim optimal anomaly detection.
5. No Monte Carlo samples are introduced; the only resampling is the run-block bootstrap used for confidence intervals.

## Artifacts

`REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `raw_reproduction_counts.csv`, `event_identity_audit.csv`, `join_quality_sensitivity.csv`, `amplitude_channel_correlations.csv`, `bootstrap_join_quality_summary.csv`, `bootstrap_amplitude_summary.csv`, `ml_sentinel_by_run.csv`, `ml_sentinel_summary.csv`, `ml_sentinel_sample_meta.csv.gz`, and PNG diagnostics are in this folder.
