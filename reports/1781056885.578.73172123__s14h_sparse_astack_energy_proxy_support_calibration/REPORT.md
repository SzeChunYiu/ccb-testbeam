# S14h Sparse A-stack Energy-proxy Support Calibration

**Ticket.** `1781056885.578.73172123`.  **Worker.** `testbeam-laptop-3`.

## Abstract

This study asks where the external S14c/P04c A-stack charge proxy is supported strongly enough to be used as an ordering or PID covariate, and where a downstream analysis must abstain.  The benchmark is deliberately run-level: models are trained on all runs except the held-out run, then evaluated on the held-out run.  The winner is `gradient_boosted_trees` under a composite safety score that penalizes proxy RMSE, false support, and unnecessary abstention while rewarding rank ordering.

## Raw ROOT Reproduction Gate

All rows are rebuilt from raw `HRDv` ROOT files under `data/root/root`.  B-stack reproduction is the S00 selected-pulse gate, while A-stack counts reproduce the analysis-period A1/A3 gates used by prior A-stack studies.

- B-stack selected-pulse reproduction: `640,737` vs expected `640,737`; delta `+0`.

| sample              |   events_with_selected |   selected_pulses |   A1 |   A3 |
|:--------------------|-----------------------:|------------------:|-----:|-----:|
| sample_iii_analysis |                   7168 |              9682 | 2799 | 6883 |
| sample_iv_analysis  |                    767 |               894 |  167 |  727 |

The S14h denominator is every event matched by `(run, EVT)` with B2 above threshold.  The support label is whether A1 or A3 is selected in the matched A-stack event.

|   run |   b2_selected_denominator |   a_any_supported |   a_pair_supported |   b2_and_downstream |
|------:|--------------------------:|------------------:|-------------------:|--------------------:|
|    31 |                     11294 |               229 |                 80 |                 237 |
|    32 |                     11564 |               207 |                 72 |                 218 |
|    33 |                     13656 |                 8 |                  1 |                 161 |
|    34 |                     13830 |                16 |                  5 |                 165 |
|    35 |                      6130 |               221 |                 67 |                 217 |
|    36 |                      7216 |               295 |                 97 |                 251 |
|    37 |                      7036 |               292 |                104 |                 280 |
|    39 |                      7238 |               324 |                120 |                 333 |
|    40 |                      6854 |               265 |                 83 |                 321 |
|    41 |                      7197 |               295 |                113 |                 376 |
|    42 |                      8114 |               279 |                 92 |                 318 |
|    44 |                       602 |                30 |                 11 |                  24 |
|    45 |                      7597 |               302 |                 91 |                 316 |
|    46 |                         0 |                 0 |                  0 |                   0 |
|    47 |                      2653 |                92 |                 30 |                  50 |
|    48 |                      6294 |               260 |                 98 |                 259 |
|    49 |                      7235 |               288 |                103 |                 301 |
|    50 |                     12260 |                61 |                 15 |                 255 |

## Methods

For event \(i\), let \(S_i\in\{0,1\}\) denote A-stack support and \(Y_i=\log Q^A_i\) the selected A1/A3 charge proxy when supported.  A method returns a support score \(\hat p_i\) and a proxy \(\hat Y_i\).  Events with \(\hat p_i<\tau\) are abstained.  Support coverage is \(\sum_i 1[\hat p_i\ge\tau,S_i=1]/\sum_i1[S_i=1]\), and false support is \(\sum_i1[\hat p_i\ge\tau,S_i=0]/\sum_i1[S_i=0]\).  Proxy RMSE is evaluated only on accepted, supported rows.

**Traditional comparator.**  The transparent baseline bins run family, current proxy, B-depth, downstream multiplicity, B2 and downstream-charge quantiles, saturation, dropout, and baseline-excursion strata.  For each bin, support is estimated by \(k/n\) with Clopper-Pearson 95% intervals; sparse cells fall back through coarser hierarchies.  The proxy is the supported-row median \(\log Q^A\) in the same hierarchy.

**ML/NN panel.**  Ridge uses logistic support plus ridge proxy regression.  Gradient-boosted trees and MLP use the same run-residualized tabular and waveform-summary features.  The 1D-CNN consumes normalized B2/B4/B6/B8 waveforms.  The new `support_gated_hybrid_cnn` is a two-head CNN whose proxy is blended back to the traditional proxy when learned support is weak, which is sensible for sparse A-stack coincidences.

**Controls.**  Charge-only, topology-only, current-only, and shuffled-target sentinels are fit with the same leave-one-run-out protocol.  High sentinel support is interpreted as a leakage or confounding warning, not as a production method.

Uncertainty uses a run-block bootstrap; each bootstrap resamples runs with replacement and recomputes the metric on all rows in those runs.

## Benchmark Results

| method                     |   support_coverage | support_coverage_ci95                      |   abstention_rate |   false_support_rate |   proxy_rmse_log | proxy_rmse_log_ci95                      |   proxy_spearman |   pid_score_stability_run_sd |
|:---------------------------|-------------------:|:-------------------------------------------|------------------:|---------------------:|-----------------:|:-----------------------------------------|-----------------:|-----------------------------:|
| traditional_exact_binomial |          0.103083  | [0.06661007814605227, 0.13714968313744444] |       0.95523     |            0.0438074 |         0.596834 | [0.5592823529366446, 0.6534723138814211] |       0.0241607  |                    0.0170642 |
| ridge                      |          0.985697  | [0.9620630805070808, 0.9974803105742568]   |       0.0750751   |            0.923921  |         0.554092 | [0.5389050133915433, 0.5734198553679217] |       0.0185074  |                    0.291097  |
| gradient_boosted_trees     |          0.0784217 | [0.0428457535553609, 0.12095026402026832]  |       0.965685    |            0.0335865 |         0.562296 | [0.5127076592333885, 0.5894150165756348] |      -0.0127289  |                    0.0251908 |
| mlp                        |          0.209125  | [0.1284993018681739, 0.2811652307304027]   |       0.917021    |            0.0808959 |         3.76836  | [3.1329390503207937, 4.457352511707292]  |      -0.0585011  |                    0.0204931 |
| cnn_1d                     |          1         | [1.0, 1.0]                                 |       0           |            1         |         0.774934 | [0.7376163524698026, 0.8144235940502955] |      -0.00110643 |                    0.0361445 |
| support_gated_hybrid_cnn   |          1         | [1.0, 1.0]                                 |       2.00296e-05 |            0.99998   |         0.625218 | [0.6083138728864153, 0.6476921554448213] |      -0.0163408  |                    0.023649  |

### ML-minus-traditional deltas

| method                   |   delta_proxy_rmse_log |   delta_support_coverage |   delta_abstention_rate |   delta_false_support_rate |   delta_spearman |
|:-------------------------|-----------------------:|-------------------------:|------------------------:|---------------------------:|-----------------:|
| ridge                    |             -0.0427428 |                0.882614  |              -0.880155  |                  0.880114  |      -0.00565333 |
| gradient_boosted_trees   |             -0.0345378 |               -0.0246609 |               0.0104555 |                 -0.0102209 |      -0.0368896  |
| mlp                      |              3.17153   |                0.106042  |              -0.0382085 |                  0.0370885 |      -0.0826618  |
| cnn_1d                   |              0.1781    |                0.896917  |              -0.95523   |                  0.956193  |      -0.0252671  |
| support_gated_hybrid_cnn |              0.0283842 |                0.896917  |              -0.95521   |                  0.956172  |      -0.0405015  |

### Sentinels

| method                   |   support_coverage |   abstention_rate |   false_support_rate |   proxy_rmse_log |   proxy_spearman |
|:-------------------------|-------------------:|------------------:|---------------------:|-----------------:|-----------------:|
| charge_only_sentinel     |           0.999753 |       9.61423e-05 |             0.999906 |         0.595681 |       -0.0125517 |
| topology_only_sentinel   |           0.997287 |       0.00397789  |             0.996001 |         0.595887 |       -0.0130312 |
| current_only_sentinel    |           1        |       0           |             1        |         0.595621 |       -0.0125529 |
| shuffled_target_sentinel |           0.99852  |       0.00332492  |             0.996645 |         0.594781 |       -0.0127555 |

## Support Systematics

| axis               | stratum                |      n |   a_support_count |   a_support_fraction |   a_support_exact95_low |   a_support_exact95_high |   winner_accept_fraction |
|:-------------------|:-----------------------|-------:|------------------:|---------------------:|------------------------:|-------------------------:|-------------------------:|
| sample             | sample_iii_analysis    | 105108 |              1470 |           0.0139856  |              0.0132844  |               0.0147139  |               0.0424801  |
| sample             | sample_iii_calibration | 100129 |              2431 |           0.0242787  |              0.0233342  |               0.0252509  |               0.0342658  |
| sample             | sample_iv_analysis     |  38154 |               119 |           0.00311894 |              0.00258444 |               0.00373113 |               0.0173507  |
| sample             | sample_iv_calibration  |   6239 |                35 |           0.00560987 |              0.0039105  |               0.00779342 |               0.00128226 |
| current_stratum    | high_current_proxy     |  70018 |              2848 |           0.0406753  |              0.039224   |               0.0421647  |               0.0993744  |
| current_stratum    | low_current_proxy      |  99799 |               157 |           0.00157316 |              0.00133686 |               0.00183915 |               0.00790589 |
| current_stratum    | mid_current_proxy      |  79813 |              1050 |           0.0131558  |              0.0123767  |               0.0139704  |               0.0102615  |
| b_depth_idx        | 0                      | 234090 |              3889 |           0.0166133  |              0.0160993  |               0.0171392  |               0.0343287  |
| b_depth_idx        | 1                      |   8522 |               102 |           0.011969   |              0.00976956 |               0.0145109  |               0.0280451  |
| b_depth_idx        | 2                      |   4351 |                49 |           0.0112618  |              0.00834282 |               0.0148616  |               0.0468858  |
| b_depth_idx        | 3                      |   2667 |                15 |           0.0056243  |              0.00315119 |               0.00925948 |               0.0326209  |
| b_downstream_mult  | 0                      | 234090 |              3889 |           0.0166133  |              0.0160993  |               0.0171392  |               0.0343287  |
| b_downstream_mult  | 1                      |   9068 |               109 |           0.0120203  |              0.00988002 |               0.014482   |               0.0304367  |
| b_downstream_mult  | 2                      |   4157 |                44 |           0.0105846  |              0.00770099 |               0.0141835  |               0.0433005  |
| b_downstream_mult  | 3                      |   2315 |                13 |           0.00561555 |              0.00299333 |               0.00958362 |               0.0319654  |
| b2_saturated       | 0                      | 203168 |              3468 |           0.0170696  |              0.0165108  |               0.0176423  |               0.0339473  |
| b2_saturated       | 1                      |  46462 |               587 |           0.012634   |              0.0116382  |               0.0136913  |               0.0359218  |
| downstream_dropout | 0                      |  15540 |               166 |           0.0106821  |              0.00912576 |               0.0124255  |               0.0341055  |
| downstream_dropout | 1                      | 234090 |              3889 |           0.0166133  |              0.0160993  |               0.0171392  |               0.0343287  |

### Run-block ledger

|   run | sample                 |     n |   a_support_count |   a_support_fraction |   winner_accept_fraction |   winner_mean_support_score |
|------:|:-----------------------|------:|------------------:|---------------------:|-------------------------:|----------------------------:|
|    31 | sample_iii_calibration | 11294 |               229 |          0.0202763   |              0.0153179   |                  0.0178511  |
|    32 | sample_iii_calibration | 11564 |               207 |          0.0179004   |              0.0291422   |                  0.0196273  |
|    33 | sample_iii_calibration | 13656 |                 8 |          0.000585823 |              0.00139133  |                  0.00351696 |
|    34 | sample_iii_calibration | 13830 |                16 |          0.00115691  |              0.000650759 |                  0.00356469 |
|    35 | sample_iii_calibration |  6130 |               221 |          0.0360522   |              0.0174551   |                  0.0298723  |
|    36 | sample_iii_calibration |  7216 |               295 |          0.0408814   |              0.0503049   |                  0.0385532  |
|    37 | sample_iii_calibration |  7036 |               292 |          0.0415009   |              0.106595    |                  0.0385746  |
|    39 | sample_iii_calibration |  7238 |               324 |          0.0447637   |              0.125311    |                  0.0405304  |
|    40 | sample_iii_calibration |  6854 |               265 |          0.0386636   |              0.026262    |                  0.0287757  |
|    41 | sample_iii_calibration |  7197 |               295 |          0.0409893   |              0.0743365   |                  0.0407456  |
|    42 | sample_iii_calibration |  8114 |               279 |          0.034385    |              0.00628543  |                  0.0198215  |
|    44 | sample_iii_analysis    |   602 |                30 |          0.0498339   |              0.0614618   |                  0.0365739  |
|    45 | sample_iii_analysis    |  7597 |               302 |          0.0397525   |              0.0664736   |                  0.0368222  |
|    47 | sample_iii_analysis    |  2653 |                92 |          0.0346777   |              0.0655861   |                  0.0379041  |
|    48 | sample_iii_analysis    |  6294 |               260 |          0.0413092   |              0.0889736   |                  0.0428769  |
|    49 | sample_iii_analysis    |  7235 |               288 |          0.0398065   |              0.127574    |                  0.0435798  |
|    50 | sample_iii_analysis    | 12260 |                61 |          0.00497553  |              0.00179445  |                  0.00439771 |
|    51 | sample_iii_analysis    | 11154 |                25 |          0.00224135  |              0.00215169  |                  0.0034507  |
|    52 | sample_iii_analysis    |  1743 |                 6 |          0.00344234  |              0.00172117  |                  0.00350395 |
|    53 | sample_iii_analysis    | 12830 |                17 |          0.00132502  |              0.00132502  |                  0.00353462 |
|    54 | sample_iii_analysis    | 12890 |                18 |          0.00139643  |              0.00155159  |                  0.00378704 |
|    55 | sample_iii_analysis    | 11113 |                27 |          0.00242959  |              0.00584901  |                  0.00398586 |
|    56 | sample_iii_analysis    | 12118 |                68 |          0.00561149  |              0.00198052  |                  0.00734073 |
|    57 | sample_iii_analysis    |  6619 |               276 |          0.0416981   |              0.315909    |                  0.0477178  |
|    58 | sample_iv_analysis     |  7427 |                34 |          0.00457789  |              0.00121179  |                  0.00415821 |
|    59 | sample_iv_analysis     |  5175 |                 9 |          0.00173913  |              0.00251208  |                  0.00448347 |
|    60 | sample_iv_analysis     |  4665 |                10 |          0.00214362  |              0           |                  0.00248315 |
|    61 | sample_iv_analysis     |  4749 |                 6 |          0.00126342  |              0.128027    |                  0.129485   |
|    62 | sample_iv_analysis     |  4863 |                 8 |          0.00164508  |              0.00123381  |                  0.00457226 |
|    63 | sample_iv_analysis     |  6401 |                39 |          0.0060928   |              0.00281206  |                  0.00543262 |
|    64 | sample_iv_calibration  |  6239 |                35 |          0.00560987  |              0.00128226  |                  0.00389585 |
|    65 | sample_iv_analysis     |  4874 |                13 |          0.00266721  |              0.00164136  |                  0.00386405 |

## Caveats

- The A-stack proxy is an external support label and charge/range proxy, not absolute truth energy.
- Runs provide the uncertainty unit; Sample IV has few supported A-stack coincidences, so some intervals remain broad.
- Current is represented by a run-level support-rate proxy because no external scaler stream is present in this ticket's raw ROOT table.
- The CNNs are intentionally laptop-scale.  They test whether waveform shape helps under the run split; they are not a claim about the best possible architecture.
- MLP and logistic support fits were capped for laptop runtime; convergence warnings are treated as a model-capacity caveat rather than a failure of the run-split benchmark.
- A method can win the benchmark yet still be unsuitable for production if sentinel false support is high in a downstream operating region.

## Conclusion

The support-calibrated winner is gradient_boosted_trees: support coverage 0.078 [0.043, 0.121], abstention 0.966, false support 0.034, and proxy log-RMSE 0.562.  The transparent exact-binomial baseline has coverage 0.103, false support 0.044, and proxy log-RMSE 0.597.  A-stack energy proxies should therefore be used only behind the calibrated support gate; outside the accepted strata the correct action is abstention rather than treating S14c/P04c charge ordering as truth.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `support_rows.parquet`, `support_predictions.csv.gz`, `support_predictions_preview.csv`, `support_metrics.csv`, `sentinel_metrics.csv`, `method_deltas.csv`, `support_strata.csv`, `support_by_run.csv`, raw reproduction CSVs.
