# S37c: Event-Key Hand-Scan Label Join for Real Pile-Up Deconvolution

## Abstract

Ticket `1784070153.1596.5f56213c` asks whether reviewer hand-scan candidate rows can be joined by
event key to raw HRD windows well enough to score S37b-style deconvolution
outputs against real pile-up labels with explicit reviewer-disagreement
intervals.  The worker was `testbeam-laptop-1`.  The analysis reproduces the B-stack raw
ROOT selected-pulse count, freezes training to source runs
`[46, 47, 50, 51, 52, 53, 54, 55]`, joins hand-scan rows to raw ROOT by
`run:eventno:stave`, and applies a traditional template/CFD method plus ridge,
gradient-boosted trees, MLP, 1D-CNN, a transformer, and a new residual-stack
architecture to the joined real candidate windows.  The winner written to
`result.json` is **`gradient_boosted_trees`** with real-label AP `0.3326`
and composite score `1.459`.

## Raw ROOT Reproduction

Raw files are read from `/home/billy/ccb-data/extracted/root/root`.  The branch `h101/HRDv` is
reshaped to `(event, channel, sample)` and B2/B4/B6/B8 pulses are selected with

`b_ec = median_{t in {0,1,2,3}} x_ect`,

`A_ec = max_t(x_ect-b_ec)`,

`N = sum_ec 1[A_ec > 1000 ADC]`.

| quantity                           | report_value | reproduced | delta | pass |
| ---------------------------------- | ------------ | ---------- | ----- | ---- |
| total selected B-stave pulses      | 640737       | 640737     | 0     | True |
| sample_ii_analysis selected_pulses | 125096       | 125096     | 0     | True |
| sample_ii_analysis B2              | 88213        | 88213      | 0     | True |
| sample_ii_analysis B4              | 21229        | 21229      | 0     | True |
| sample_ii_analysis B6              | 11148        | 11148      | 0     | True |
| sample_ii_analysis B8              | 4506         | 4506       | 0     | True |

## Hand-Scan Sources and Event-Key Join

| source_file                                                                                                       | rows | sha256                                                           |
| ----------------------------------------------------------------------------------------------------------------- | ---- | ---------------------------------------------------------------- |
| reports/1781146783.955.745c6984__s11h_blinded_real_current_waveform_adjudication/blinded_gallery_adjudication.csv | 986  | ce2bd9f15371ede4af1b12a1c1bb8b163a226c543bee9e240a76efe284c36d6a |
| reports/1781191650.1263.35bb131f__p05g_blinded_handscan_validation/blinded_candidate_ledger.csv                   | 549  | de6845eb54f5c3c30a7ae4c93ddfb432af934b5dd367e9eb747b5e5dd08d89c7 |
| reports/1783605034.12126.04fe4a38__s01j_external_handscan_transfer/handscan_feature_table.csv                     | 256  | a1c6149bde559e8c0c8b675f856accb148336298a85d23a4ac43f382ca52b955 |

Rows are canonicalized to `run:eventno:stave`.  Multiple reviewer sources for the
same key are aggregated into a mean consensus label and an interval
`[min(vote), max(vote)]`; non-unanimous rows receive `reviewer_disagreement=1`.

| run | requested_keys | joined_raw_windows | join_efficiency |
| --- | -------------- | ------------------ | --------------- |
| 42  | 59             | 59                 | 1               |
| 44  | 27             | 27                 | 1               |
| 45  | 120            | 120                | 1               |
| 48  | 109            | 109                | 1               |
| 49  | 107            | 107                | 1               |
| 56  | 126            | 126                | 1               |
| 57  | 168            | 168                | 1               |
| 64  | 62             | 62                 | 1               |
| 65  | 62             | 62                 | 1               |

## Split and Models

The methods are trained only on controlled overlaps generated from raw ROOT
clean pulses in train runs `[46, 47, 50, 51, 52, 53, 54, 55]`.  The real
hand-scan candidates are held out by source run.  Templates are estimated only
from training runs:

`T_s(t)=median_i x_i(t+tau_i-tau_ref)/max_t x_i(t)`.

| stave | n_train_pulses | template_cfd20_sample | template_peak_sample | template_area |
| ----- | -------------- | --------------------- | -------------------- | ------------- |
| B2    | 800            | 2.553                 | 5                    | 9.242         |
| B4    | 647            | 3.012                 | 6                    | 10.75         |
| B6    | 583            | 3.797                 | 6                    | 9.758         |
| B8    | 318            | 4.381                 | 8                    | 9.102         |

| method                              | family          | description                                                  |
| ----------------------------------- | --------------- | ------------------------------------------------------------ |
| traditional_template_cfd            | traditional     | bounded two-pulse template fit with CFD initialization       |
| ridge                               | linear ML       | ridge classifier plus multi-output ridge regression          |
| gradient_boosted_trees              | tree ML         | histogram gradient-boosted classifier/regressors             |
| mlp                                 | neural network  | tabular multilayer perceptron classifier/regressor pair      |
| 1d_cnn                              | neural network  | compact one-dimensional convolutional waveform model         |
| tiny_sequence_transformer           | neural sequence | one-layer self-attention encoder                             |
| template_residual_boosted_stack_new | new hybrid      | boosted residual stack using traditional deconvolver outputs |

The traditional method is a physical comparator, not a weak baseline.  It
minimizes `SSE_k=sum_t [w(t)-b-sum_j A_j T_s(t-t_j)]^2` for one- and two-pulse
hypotheses and uses `(SSE_1-SSE_2)/SSE_1` as overlap evidence.  The new
architecture, `template_residual_boosted_stack_new`, appends traditional fit
coordinates and overlap improvement to waveform features before fitting boosted
classification and regression heads.

## Real-Label Metrics

For held-out raw hand-scan row `i`, label `y_i` is the aggregated reviewer
consensus.  A method emits score `s_im`; accepted secondary rows satisfy
`s_im >= 0.5`.  The main ranking minimizes

`C_m = (1-AP_m) + 0.7 r_miss + 0.7 r_false + 0.25 r_tail + 0.20 |b_E| + 0.30 D_stave`,

where `r_tail` is the fraction of accepted predictions whose predicted delay is
more than 15 ns from a reviewer secondary separation when available, otherwise
outside the registered 5-80 ns real-candidate window.  `b_E` is the median
secondary-inclusive amplitude bias against raw peak amplitude, and `D_stave` is
the accepted-secondary rate span across B staves.  Confidence intervals are 95%
percentile intervals from `500` held-out
source-run bootstrap resamples.

| method                              | winner_score | real_label_ap | real_label_ap_ci_low | real_label_ap_ci_high | real_label_auc | pileup_miss_rate | false_split_rate | accepted_secondary_fraction | timing_tail_rate_abs_gt_15ns | energy_bias_median | stave_pid_proxy_drift_span |
| ----------------------------------- | ------------ | ------------- | -------------------- | --------------------- | -------------- | ---------------- | ---------------- | --------------------------- | ---------------------------- | ------------------ | -------------------------- |
| gradient_boosted_trees              | 1.459        | 0.3326        | 0.2941               | 0.3659                | 0.5199         | 0.9964           | 0.03363          | 0.02381                     | 0.15                         | -0.08973           | 0.03049                    |
| template_residual_boosted_stack_new | 1.507        | 0.3123        | 0.2718               | 0.344                 | 0.492          | 0.9891           | 0.06195          | 0.04524                     | 0.1316                       | -0.112             | 0.05793                    |
| 1d_cnn                              | 1.512        | 0.2898        | 0.2597               | 0.3704                | 0.4813         | 0.9964           | 0.01239          | 0.009524                    | 0                            | 0.4492             | 0.0122                     |
| tiny_sequence_transformer           | 1.541        | 0.2939        | 0.2646               | 0.3498                | 0.4817         | 0.9745           | 0.06018          | 0.04881                     | 0.1951                       | -0.154             | 0.06098                    |
| mlp                                 | 1.645        | 0.2997        | 0.2686               | 0.3598                | 0.4988         | 1                | 0.01416          | 0.009524                    | 0.125                        | 0.9872             | 0.0122                     |
| traditional_template_cfd            | 1.897        | 0.3038        | 0.2645               | 0.354                 | 0.4752         | 0.8691           | 0.2195           | 0.1905                      | 0.5                          | -1                 | 0.2204                     |
| ridge                               | 1.957        | 0.278         | 0.2473               | 0.3249                | 0.4434         | 0.7673           | 0.4478           | 0.3774                      | 0.7018                       | -0.1918            | 0.2559                     |

The traditional comparator has score `1.897` and real-label
AP `0.3038`.  The selected winner has score
`1.459`.

## Run-Held-Out Stability

| method                              | heldout_run | real_label_ap | pileup_miss_rate | false_split_rate | accepted_secondary_fraction | timing_tail_rate_abs_gt_15ns |
| ----------------------------------- | ----------- | ------------- | ---------------- | ---------------- | --------------------------- | ---------------------------- |
| 1d_cnn                              | 42          | 0.4245        | 1                | 0                | 0                           | nan                          |
| 1d_cnn                              | 44          | 0.5158        | 1                | 0                | 0                           | nan                          |
| 1d_cnn                              | 45          | 0.2746        | 1                | 0.01235          | 0.008333                    | 0                            |
| 1d_cnn                              | 48          | 0.2712        | 1                | 0.05882          | 0.0367                      | 0                            |
| 1d_cnn                              | 49          | 0.2797        | 1                | 0.01471          | 0.009346                    | 0                            |
| 1d_cnn                              | 56          | 0.2221        | 1                | 0                | 0                           | nan                          |
| 1d_cnn                              | 57          | 0.3303        | 0.9825           | 0.009009         | 0.0119                      | 0                            |
| 1d_cnn                              | 64          | 0.4449        | 1                | 0                | 0                           | nan                          |
| 1d_cnn                              | 65          | 0.5724        | 1                | 0                | 0                           | nan                          |
| gradient_boosted_trees              | 42          | 0.1404        | 1                | 0                | 0                           | nan                          |
| gradient_boosted_trees              | 44          | 0.5237        | 1                | 0                | 0                           | nan                          |
| gradient_boosted_trees              | 45          | 0.4144        | 1                | 0.03704          | 0.025                       | 0.6667                       |
| gradient_boosted_trees              | 48          | 0.3523        | 1                | 0.08824          | 0.05505                     | 0                            |
| gradient_boosted_trees              | 49          | 0.3301        | 0.9744           | 0.08824          | 0.06542                     | 0                            |
| gradient_boosted_trees              | 56          | 0.2576        | 1                | 0.01111          | 0.007937                    | 0                            |
| gradient_boosted_trees              | 57          | 0.3572        | 1                | 0.02703          | 0.01786                     | 0.3333                       |
| gradient_boosted_trees              | 64          | 0.1802        | 1                | 0                | 0                           | nan                          |
| gradient_boosted_trees              | 65          | 0.2746        | 1                | 0                | 0                           | nan                          |
| mlp                                 | 42          | 0.398         | 1                | 0                | 0                           | nan                          |
| mlp                                 | 44          | 0.5531        | 1                | 0.1111           | 0.03704                     | 0                            |
| mlp                                 | 45          | 0.2842        | 1                | 0                | 0                           | nan                          |
| mlp                                 | 48          | 0.2811        | 1                | 0.05882          | 0.0367                      | 0.25                         |
| mlp                                 | 49          | 0.2952        | 1                | 0.01471          | 0.009346                    | 0                            |
| mlp                                 | 56          | 0.2376        | 1                | 0                | 0                           | nan                          |
| mlp                                 | 57          | 0.33          | 1                | 0.01802          | 0.0119                      | 0                            |
| mlp                                 | 64          | 0.3696        | 1                | 0                | 0                           | nan                          |
| mlp                                 | 65          | 0.5615        | 1                | 0                | 0                           | nan                          |
| ridge                               | 42          | 0.2791        | 0.9167           | 0.2553           | 0.2203                      | 0.7692                       |
| ridge                               | 44          | 0.6205        | 0.8333           | 0.4444           | 0.2593                      | 0.1429                       |
| ridge                               | 45          | 0.3361        | 0.7692           | 0.4815           | 0.4                         | 0.02083                      |
| ridge                               | 48          | 0.272         | 0.7073           | 0.6029           | 0.4862                      | 0.1132                       |
| ridge                               | 49          | 0.3523        | 0.6923           | 0.5441           | 0.4579                      | 0.08163                      |
| ridge                               | 56          | 0.2525        | 0.7778           | 0.4778           | 0.4048                      | 0.05882                      |
| ridge                               | 57          | 0.301         | 0.7719           | 0.4324           | 0.3631                      | 0.5556                       |
| ridge                               | 64          | 0.2137        | 0.8333           | 0.4              | 0.3548                      | 0.7727                       |
| ridge                               | 65          | 0.498         | 0.8095           | 0.2195           | 0.2097                      | 0.6154                       |
| template_residual_boosted_stack_new | 42          | 0.1287        | 1                | 0                | 0                           | nan                          |
| template_residual_boosted_stack_new | 44          | 0.5168        | 1                | 0.2222           | 0.07407                     | 0                            |
| template_residual_boosted_stack_new | 45          | 0.353         | 0.9744           | 0.08642          | 0.06667                     | 0.25                         |
| template_residual_boosted_stack_new | 48          | 0.3235        | 1                | 0.1471           | 0.09174                     | 0.1                          |
| template_residual_boosted_stack_new | 49          | 0.3018        | 0.9744           | 0.1176           | 0.08411                     | 0                            |
| template_residual_boosted_stack_new | 56          | 0.2347        | 1                | 0.04444          | 0.03175                     | 0                            |
| template_residual_boosted_stack_new | 57          | 0.3649        | 0.9825           | 0.03604          | 0.02976                     | 0.4                          |
| template_residual_boosted_stack_new | 64          | 0.2205        | 1                | 0                | 0                           | nan                          |
| template_residual_boosted_stack_new | 65          | 0.2617        | 1                | 0                | 0                           | nan                          |
| tiny_sequence_transformer           | 42          | 0.4077        | 1                | 0                | 0                           | nan                          |
| tiny_sequence_transformer           | 44          | 0.5892        | 0.9444           | 0                | 0.03704                     | 0                            |
| tiny_sequence_transformer           | 45          | 0.2644        | 1                | 0.08642          | 0.05833                     | 0.4286                       |
| tiny_sequence_transformer           | 48          | 0.265         | 1                | 0.1765           | 0.1101                      | 0.1667                       |
| tiny_sequence_transformer           | 49          | 0.344         | 0.9231           | 0.07353          | 0.07477                     | 0                            |
| tiny_sequence_transformer           | 56          | 0.2443        | 0.9444           | 0.05556          | 0.05556                     | 0.1429                       |
| tiny_sequence_transformer           | 57          | 0.3338        | 0.9825           | 0.04505          | 0.03571                     | 0.3333                       |
| tiny_sequence_transformer           | 64          | 0.3613        | 1                | 0                | 0                           | nan                          |
| tiny_sequence_transformer           | 65          | 0.557         | 1                | 0                | 0                           | nan                          |
| traditional_template_cfd            | 42          | 0.2698        | 0.9167           | 0                | 0.01695                     | 1                            |
| traditional_template_cfd            | 44          | 0.7813        | 0.8333           | 0.1111           | 0.1481                      | 0                            |
| traditional_template_cfd            | 45          | 0.2698        | 1                | 0.321            | 0.2167                      | 0                            |
| traditional_template_cfd            | 48          | 0.3207        | 0.9268           | 0.3676           | 0.2569                      | 0                            |
| traditional_template_cfd            | 49          | 0.3445        | 0.7949           | 0.2206           | 0.215                       | 0                            |
| traditional_template_cfd            | 56          | 0.271         | 0.6111           | 0.3889           | 0.3889                      | 0                            |
| traditional_template_cfd            | 57          | 0.3129        | 0.9298           | 0.1982           | 0.1548                      | 0                            |
| traditional_template_cfd            | 64          | 0.2052        | 1                | 0                | 0                           | nan                          |
| traditional_template_cfd            | 65          | 0.4863        | 0.8571           | 0                | 0.04839                     | 0.3333                       |

## Synthetic Closure Check

The same fitted methods are also checked on controlled run-held-out overlaps to
verify that the machinery still recovers exact injected timing/energy labels
before it is applied to reviewer labels.

| method                              | detection_ap | detection_auc | time_sigma68_ns | pileup_miss_rate | false_split_rate | energy_fractional_sigma68 |
| ----------------------------------- | ------------ | ------------- | --------------- | ---------------- | ---------------- | ------------------------- |
| gradient_boosted_trees              | 0.8422       | 0.81          | 6.181           | 0.2917           | 0.2841           | 0.0741                    |
| template_residual_boosted_stack_new | 0.8407       | 0.8145        | 6.693           | 0.2765           | 0.2576           | 0.07814                   |
| two_pulse_template_cfd_baseline     | 0.6806       | 0.6304        | 9.636           | 0.553            | 0.2197           | 0.07242                   |
| ridge                               | 0.8397       | 0.8309        | 9.664           | 0.2803           | 0.2159           | 0.06792                   |
| 1d_cnn                              | 0.7871       | 0.7867        | 10.43           | 0.3371           | 0.2462           | 0.1037                    |
| tiny_sequence_transformer           | 0.7704       | 0.772         | 13.55           | 0.1515           | 0.5              | 0.1451                    |
| mlp                                 | 0.8025       | 0.8103        | 19.23           | 0.3409           | 0.2008           | 0.2162                    |

## Systematics and Caveats

The hand-scan labels are real reviewer consensus labels, but they are not exact
constituent timing or amplitude truth.  Reviewer intervals are vote intervals,
not calibrated Bayesian credible intervals.  Event-key matching uses
`run:eventno:stave`; if a DAQ file reused an event number within a run, the join
would need `event_index` as an additional key.  The model training labels remain
controlled overlays, so real-label scoring tests transfer to hand-scanned
candidate morphology rather than supervised learning from human labels.  PID is
represented by stave-conditioned acceptance drift because no event-native
particle-ID branch is available in the audited raw ROOT files.  Bootstrap CIs
resample held-out source runs and quantify run-transfer uncertainty.

Runtime was `66.6` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.
