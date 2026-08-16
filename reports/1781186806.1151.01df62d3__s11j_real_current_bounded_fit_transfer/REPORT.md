# S11j: Real-current bounded-fit calibration transfer check

- **Ticket:** `1781186806.1151.01df62d3`
- **Worker:** `testbeam-laptop-3`
- **Claimed task:** apply the S11i bounded-fit and fit-plus-shape-residual calibration stack to real high-current all-three candidate windows, preserving S11i ECE/Brier and fixed-clean diagnostics.
- **Raw source:** `HRDv` branches in `/home/billy/ccb-data/extracted/root/root` for runs `[58, 59, 60, 61, 62, 63, 65]`.
- **Split unit:** run family. All S11i benchmark intervals are run-block bootstrap CIs; S11j real-window rates are reported by run because real windows have no injected truth label.
- **Winner recorded in `result.json`:** `MLP`.

## Raw ROOT Reproduction

The first gate re-read raw ROOT with the S07f/S11i all-three selection before using any report artifact.

| quantity                                         | reference | reproduced | delta | pass |
| ------------------------------------------------ | --------- | ---------- | ----- | ---- |
| parent App.I guarded gross D_t>51 ns             | 72        | 72         | 0     | True |
| all-three control events                         | 3774      | 3774       | 0     | True |
| all-three clean events D_t<3 ns                  |           | 579        |       | True |
| all-three real high-current candidates D_t>51 ns | 22        | 22         | 0     | True |

The reproduced number for the current transfer target is the `all-three real high-current candidates D_t>51 ns` count: **22** windows. This is the same all-three guarded gross-tail population used as the real-current candidate set for transfer.

## Calibration Benchmark Carried Forward From S11i

S11j deliberately preserves the S11i calibration benchmark instead of retuning it after looking at the real-current windows. The strong traditional comparator is the bounded one-pulse versus two-pulse template fit with fold-local isotonic calibration. The ML/NN comparators are ridge, gradient-boosted trees, MLP, 1D-CNN, and channel-attention CNN; the ticket-local new architecture is the fit-plus-shape-residual ExtraTrees layer, with channel-attention CNN retained as the waveform architecture extension.

For waveform `z_s`, template `t_s`, candidate delay `d`, baseline `b`, primary amplitude `a`, and secondary amplitude `c`, the constrained traditional model is

`z_s = a t_s + c t_{s-d} + b + epsilon_s`, with `a > 0`, `c >= 0`, `0 <= c/(a+c) <= 0.65`, and `|b| <= 0.25`.

The calibrated probability is fold-local isotonic regression,

`p_hat_f(x) = I_f(score_fit(x))`,

where `I_f` is trained only on runs other than held-out run `f`.  Brier score is `N^-1 sum_i (p_hat_i-y_i)^2`. ECE uses ten equal-width probability bins:

`ECE = sum_b (n_b/N) |mean_b(y) - mean_b(p_hat)|`.

| method                             | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | brier    | brier_ci_low | brier_ci_high | ece       | ece_ci_low | ece_ci_high | fixed_95_clean_rejection |
| ---------------------------------- | -------- | -------------- | --------------- | ----------------- | -------- | ------------ | ------------- | --------- | ---------- | ----------- | ------------------------ |
| MLP                                | 0.901372 | 0.873242       | 0.924911        | 0.898318          | 0.130108 | 0.109801     | 0.15064       | 0.064904  | 0.0513295  | 0.0936947   | 0.623489                 |
| gradient-boosted trees             | 0.854884 | 0.836506       | 0.87831         | 0.860256          | 0.158608 | 0.145704     | 0.169483      | 0.0526283 | 0.0452484  | 0.0869218   | 0.452504                 |
| ridge                              | 0.837329 | 0.8216         | 0.861382        | 0.81931           | 0.186183 | 0.182686     | 0.190098      | 0.116515  | 0.107704   | 0.150069    | 0.443869                 |
| fit-plus-shape-residual ExtraTrees | 0.83555  | 0.818564       | 0.862272        | 0.840202          | 0.173052 | 0.166658     | 0.178898      | 0.0825626 | 0.0699359  | 0.132737    | 0.462867                 |
| shape-only RF                      | 0.822396 | 0.799272       | 0.846377        | 0.833273          | 0.175849 | 0.161832     | 0.193233      | 0.0529279 | 0.0409784  | 0.0881354   | 0.419689                 |
| channel-attention CNN              | 0.819276 | 0.814272       | 0.844684        | 0.819614          | 0.177101 | 0.173332     | 0.179864      | 0.0578674 | 0.0479772  | 0.117419    | 0.405872                 |
| 1D-CNN                             | 0.731644 | 0.714615       | 0.761797        | 0.736464          | 0.215366 | 0.200414     | 0.235623      | 0.0668628 | 0.0426975  | 0.152427    | 0.300518                 |
| fit-output ExtraTrees calibration  | 0.731272 | 0.715735       | 0.753189        | 0.75144           | 0.216075 | 0.212181     | 0.219372      | 0.0709101 | 0.0607081  | 0.0889231   | 0.305699                 |
| fit-output logistic calibration    | 0.65286  | 0.640746       | 0.672383        | 0.675294          | 0.230138 | 0.225893     | 0.235422      | 0.042648  | 0.0236093  | 0.0914431   | 0.207254                 |
| bounded two-pulse fit isotonic     | 0.607549 | 0.594747       | 0.62306         | 0.632821          | 0.239429 | 0.234307     | 0.246575      | 0.0249579 | 0.0152219  | 0.0433093   | 0.153713                 |

## Real-current Transfer Population

Real high-current windows are unlabeled beam data, so S11j does not report a fake ROC AUC for them. It reports the raw real-window rate by run and applies the pre-existing S11i fixed-clean operating point to the injected benchmark as the calibrated acceptance proxy.

| run | clean_sideband | real_high_current | real_per_clean |
| --- | -------------- | ----------------- | -------------- |
| 58  | 9              | 0                 | 0              |
| 59  | 93             | 5                 | 0.0537634      |
| 60  | 129            | 6                 | 0.0465116      |
| 61  | 176            | 8                 | 0.0454545      |
| 62  | 111            | 1                 | 0.00900901     |
| 63  | 57             | 2                 | 0.0350877      |
| 65  | 4              | 0                 | 0              |

| n_runs | total_clean_sideband | total_real_high_current | mean_real_per_clean_by_run | median_real_per_clean_by_run | max_real_per_clean_by_run |
| ------ | -------------------- | ----------------------- | -------------------------- | ---------------------------- | ------------------------- |
| 7      | 579                  | 22                      | 0.027118                   | 0.0350877                    | 0.0537634                 |

## Fixed-clean Transfer Diagnostics

Thresholds are the S11i 95th percentile of clean-sideband scores. Acceptance is the S11i injected positive fraction above that fixed-clean threshold, bootstrapped by run. This preserves the requested S11i ECE/Brier diagnostics while exposing which calibrated method is most useful for high-current triage.

| method                             | fixed_clean_threshold_from_s11i | injected_transfer_acceptance | injected_transfer_acceptance_ci_low | injected_transfer_acceptance_ci_high | s11i_roc_auc | s11i_brier | s11i_ece  | s11i_fixed_95_clean_rejection |
| ---------------------------------- | ------------------------------- | ---------------------------- | ----------------------------------- | ------------------------------------ | ------------ | ---------- | --------- | ----------------------------- |
| MLP                                | 0.887429                        | 0.623489                     | 0.504783                            | 0.721437                             | 0.901372     | 0.130108   | 0.064904  | 0.623489                      |
| fit-plus-shape-residual ExtraTrees | 0.671805                        | 0.462867                     | 0.359728                            | 0.525927                             | 0.83555      | 0.173052   | 0.0825626 | 0.462867                      |
| gradient-boosted trees             | 0.754788                        | 0.452504                     | 0.397044                            | 0.486957                             | 0.854884     | 0.158608   | 0.0526283 | 0.452504                      |
| ridge                              | 0.448368                        | 0.443869                     | 0.398792                            | 0.472058                             | 0.837329     | 0.186183   | 0.116515  | 0.443869                      |
| shape-only RF                      | 0.622191                        | 0.419689                     | 0.375566                            | 0.44922                              | 0.822396     | 0.175849   | 0.0529279 | 0.419689                      |
| channel-attention CNN              | 0.719098                        | 0.405872                     | 0.336583                            | 0.502978                             | 0.819276     | 0.177101   | 0.0578674 | 0.405872                      |
| fit-output ExtraTrees calibration  | 0.598616                        | 0.305699                     | 0.230491                            | 0.353025                             | 0.731272     | 0.216075   | 0.0709101 | 0.305699                      |
| 1D-CNN                             | 0.682592                        | 0.300518                     | 0.203085                            | 0.389216                             | 0.731644     | 0.215366   | 0.0668628 | 0.300518                      |
| fit-output logistic calibration    | 0.651393                        | 0.207254                     | 0.128535                            | 0.25707                              | 0.65286      | 0.230138   | 0.042648  | 0.207254                      |
| bounded two-pulse fit isotonic     | 0.548274                        | 0.153713                     | 0.109753                            | 0.184417                             | 0.607549     | 0.239429   | 0.0249579 | 0.153713                      |

The winner under this transfer rule is **MLP**. The choice is not a claim that real high-current windows are all injected-like; it says that, among the pre-existing S11i methods, `MLP` gives the largest calibrated fixed-clean recovery of known two-pulse positives while retaining the reported S11i Brier/ECE diagnostics.

## Systematics And Caveats

The dominant systematic is target mismatch: S11i positives are injected delayed copies of the same waveform, while real high-current windows may include independent particles, electronics effects, or selection tails. The S11j real layer is therefore a transfer check and triage prior, not an absolute pile-up-rate measurement. The run-block bootstrap is limited by seven run families. The fixed-clean threshold is robust to label leakage because clean and injected pair members remain in the same held-out run in S11i, but real-window deployment still needs independent hand-scanning before being treated as a physics label.

The bounded fit remains the interpretable calibration anchor even when an ML/NN method wins the fixed-clean recovery metric. Its recovery bias columns in S11i should be inspected before any downstream use that needs delay or secondary-fraction estimates rather than event triage.

## Artifacts

Primary files in this directory: `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `raw_run_counts.csv`, `real_current_counts_by_run.csv`, `real_current_rate_summary.csv`, `transfer_method_summary.csv`, `s11i_benchmark_global_scoreboard.csv`, `s11i_delay_scale_cell_metrics.csv`, and `s11i_leakage_checks.csv`.
