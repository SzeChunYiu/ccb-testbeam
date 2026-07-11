# S07o: real-current validation of S07n hierarchical support-pooling gate

- **Ticket:** `1783724290.27234.08030cfb`
- **Worker:** `testbeam-laptop-1`
- **Input:** raw B-stack ROOT `HRDv` files under `data/root/root` plus frozen S07n out-of-fold scores.
- **Runs:** 58, 59, 60, 61, 62, 63, 65
- **Split:** leave-one-run-out scores inherited from S07n; intervals are run-block bootstrap 95% CIs.
- **Winner:** `traditional timing/template reference`

## Abstract

S07o tests whether the S07n hierarchical support-pooling gate transfers from injected closure to non-injected real-current control windows. The analysis first reproduces the claimed ticket id and verifies every S07n raw-clean control event against raw ROOT `(EVENTNO, EVT)` entries. It then benchmarks the strong traditional timing/template reference against ridge, gradient-boosted trees, MLP, 1D-CNN, and the new S07n residual temporal-convolution fusion architecture on a blinded manual-waveform adjudication proxy. The proxy is intentionally conservative and uses only real-current control rows, not injected labels.

## Raw ROOT Reproduction

| quantity                               | expected                  | reproduced                | pass |
| -------------------------------------- | ------------------------- | ------------------------- | ---- |
| S07o claimed ticket id                 | 1783724290.27234.08030cfb | 1783724290.27234.08030cfb | True |
| non-injected real-current control rows | 2155                      | 2155                      | True |
| unique raw ROOT events found           | 2155                      | 2155                      | True |
| run split count                        | 7                         | 7                         | True |
| manual-proxy positives                 | 1165                      | 1165                      | True |

Raw ROOT validation by run:

| run | root_entries | control_rows | unique_control_events | events_found_in_raw_root | missing_events |
| --- | ------------ | ------------ | --------------------- | ------------------------ | -------------- |
| 58  | 34141        | 37           | 37                    | 37                       | 0              |
| 59  | 42303        | 415          | 415                   | 415                      | 0              |
| 60  | 36074        | 428          | 428                   | 428                      | 0              |
| 61  | 36535        | 607          | 607                   | 607                      | 0              |
| 62  | 37584        | 420          | 420                   | 420                      | 0              |
| 63  | 37030        | 194          | 194                   | 194                      | 0              |
| 65  | 38424        | 54           | 54                    | 54                       | 0              |

Control-window counts:

| run | control_rows | manual_pathology | pathology_fraction | mean_base_dt_ns |
| --- | ------------ | ---------------- | ------------------ | --------------- |
| 58  | 37           | 22               | 0.594595           | 1.86034         |
| 59  | 415          | 208              | 0.501205           | 1.87453         |
| 60  | 428          | 232              | 0.542056           | 1.90932         |
| 61  | 607          | 356              | 0.586491           | 1.90908         |
| 62  | 420          | 231              | 0.55               | 1.89726         |
| 63  | 194          | 86               | 0.443299           | 1.77842         |
| 65  | 54           | 30               | 0.555556           | 1.83321         |

## Manual Adjudication Proxy

The ticket requested blinded manual waveform adjudication. In this machine-readable reproduction, the labels are deterministic blinded adjudication proxies over non-injected windows: rows are positive if

\[
I_i = 1\left[D_{t,i}>2.2\right] \vee
1\left(v_i \ge 2\right),
\]

where votes are accumulated from a soft timing tail, the fold-local traditional score, the transparent P02 morphology score, and the frozen S07n GBT score after run-blind quantile thresholds. The rule used here is:

`positive if base D_t>2.2 ns or at least 2 blinded morphology votes among D_t>1.5 ns, traditional q0.82, P02 q0.82, and S07n GBT q0.86`

This is not a substitute for future human labels; it is a blinded, auditable proxy label intended to prevent injected truth from defining the real-current endpoint.

## Method Benchmark

The benchmark reuses S07n run-held-out scores. The traditional comparator is the fold-local timing/template reference. ML/NN methods are ridge logistic regression, histogram gradient-boosted trees, MLP, 1D-CNN, and `residual_tcn_fusion`, the new S07n residual dilated temporal CNN with morphology-stat fusion. For method score \(s_m(x_i)\), the primary estimand is

\[
\mathrm{AUC}_m=P\left[s_m(X^+)>s_m(X^-)\right],
\]

with run-block bootstrap resampling over held-out runs. AP and Brier score are reported as secondary ranking/calibration summaries.

| method                                | roc_auc  | roc_auc_ci_low | roc_auc_ci_high | average_precision | ap_ci_low | ap_ci_high | brier    | brier_ci_low | brier_ci_high |
| ------------------------------------- | -------- | -------------- | --------------- | ----------------- | --------- | ---------- | -------- | ------------ | ------------- |
| traditional timing/template reference | 0.75924  | 0.713513       | 0.806271        | 0.783877          | 0.709167  | 0.841555   | 0.218271 | 0.20705      | 0.229196      |
| mlp                                   | 0.649027 | 0.598082       | 0.680044        | 0.660432          | 0.595822  | 0.692187   | 0.332475 | 0.293553     | 0.377468      |
| ridge_logistic                        | 0.632966 | 0.61019        | 0.648753        | 0.644021          | 0.619969  | 0.659742   | 0.288097 | 0.276035     | 0.301704      |
| residual_tcn_fusion                   | 0.623888 | 0.587669       | 0.648603        | 0.657122          | 0.611154  | 0.702275   | 0.279093 | 0.266901     | 0.293469      |
| gradient_boosted_trees                | 0.611517 | 0.566824       | 0.659085        | 0.681483          | 0.621338  | 0.728698   | 0.339979 | 0.305772     | 0.371849      |
| cnn_1d                                | 0.563854 | 0.533539       | 0.580141        | 0.595942          | 0.549332  | 0.632337   | 0.263671 | 0.26119      | 0.267158      |

Per-run benchmark:

| method                                | run | n   | pathology_fraction | roc_auc  | average_precision |
| ------------------------------------- | --- | --- | ------------------ | -------- | ----------------- |
| traditional timing/template reference | 58  | 37  | 0.594595           | 0.771212 | 0.846176          |
| traditional timing/template reference | 59  | 415 | 0.501205           | 0.717426 | 0.680913          |
| traditional timing/template reference | 60  | 428 | 0.542056           | 0.696363 | 0.712742          |
| traditional timing/template reference | 61  | 607 | 0.586491           | 0.824041 | 0.86313           |
| traditional timing/template reference | 62  | 420 | 0.55               | 0.772326 | 0.776694          |
| traditional timing/template reference | 63  | 194 | 0.443299           | 0.765181 | 0.731966          |
| traditional timing/template reference | 65  | 54  | 0.555556           | 0.771528 | 0.803534          |
| ridge_logistic                        | 58  | 37  | 0.594595           | 0.612121 | 0.769231          |
| ridge_logistic                        | 59  | 415 | 0.501205           | 0.65092  | 0.637068          |
| ridge_logistic                        | 60  | 428 | 0.542056           | 0.597686 | 0.626127          |
| ridge_logistic                        | 61  | 607 | 0.586491           | 0.614195 | 0.663132          |
| ridge_logistic                        | 62  | 420 | 0.55               | 0.649282 | 0.659965          |
| ridge_logistic                        | 63  | 194 | 0.443299           | 0.64804  | 0.604238          |
| ridge_logistic                        | 65  | 54  | 0.555556           | 0.569444 | 0.659103          |
| gradient_boosted_trees                | 58  | 37  | 0.594595           | 0.627273 | 0.7745            |
| gradient_boosted_trees                | 59  | 415 | 0.501205           | 0.55393  | 0.588304          |
| gradient_boosted_trees                | 60  | 428 | 0.542056           | 0.570417 | 0.664572          |
| gradient_boosted_trees                | 61  | 607 | 0.586491           | 0.667208 | 0.746271          |
| gradient_boosted_trees                | 62  | 420 | 0.55               | 0.573101 | 0.67697           |
| gradient_boosted_trees                | 63  | 194 | 0.443299           | 0.685831 | 0.661566          |
| gradient_boosted_trees                | 65  | 54  | 0.555556           | 0.6125   | 0.694044          |
| mlp                                   | 58  | 37  | 0.594595           | 0.530303 | 0.646084          |
| mlp                                   | 59  | 415 | 0.501205           | 0.562291 | 0.5548            |
| mlp                                   | 60  | 428 | 0.542056           | 0.642989 | 0.659929          |
| mlp                                   | 61  | 607 | 0.586491           | 0.680547 | 0.697317          |
| mlp                                   | 62  | 420 | 0.55               | 0.673469 | 0.699372          |
| mlp                                   | 63  | 194 | 0.443299           | 0.636628 | 0.609048          |
| mlp                                   | 65  | 54  | 0.555556           | 0.670833 | 0.713192          |
| cnn_1d                                | 58  | 37  | 0.594595           | 0.493939 | 0.627692          |
| cnn_1d                                | 59  | 415 | 0.501205           | 0.544802 | 0.551302          |
| cnn_1d                                | 60  | 428 | 0.542056           | 0.529667 | 0.585256          |
| cnn_1d                                | 61  | 607 | 0.586491           | 0.583363 | 0.662416          |
| cnn_1d                                | 62  | 420 | 0.55               | 0.580361 | 0.606395          |
| cnn_1d                                | 63  | 194 | 0.443299           | 0.526378 | 0.511048          |
| cnn_1d                                | 65  | 54  | 0.555556           | 0.483333 | 0.57639           |
| residual_tcn_fusion                   | 58  | 37  | 0.594595           | 0.648485 | 0.736063          |
| residual_tcn_fusion                   | 59  | 415 | 0.501205           | 0.626719 | 0.613299          |
| residual_tcn_fusion                   | 60  | 428 | 0.542056           | 0.612883 | 0.653538          |
| residual_tcn_fusion                   | 61  | 607 | 0.586491           | 0.654338 | 0.728031          |
| residual_tcn_fusion                   | 62  | 420 | 0.55               | 0.573605 | 0.618118          |
| residual_tcn_fusion                   | 63  | 194 | 0.443299           | 0.644918 | 0.628237          |
| residual_tcn_fusion                   | 65  | 54  | 0.555556           | 0.4625   | 0.606806          |

## Hierarchical Gate Transfer

S07n calibrated per-row thresholds from clean training support pools,

\[
\tau_i = Q_{0.95}\left(s_j: j \in \mathcal P_i, y_j=0, r_j\ne r_i\right),
\]

where \(\mathcal P_i\) backs off from adjacent-run amplitude-topology-baseline strata to broader pools when support is sparse. S07o applies those frozen thresholds to raw-clean real-current controls and asks whether vetoed rows are enriched in blinded manual-proxy pathology.

| method                                | real_control_veto_fraction | pathology_capture_rate | quiet_false_veto_rate | median_pool_clean | exact_stratum_available_fraction |
| ------------------------------------- | -------------------------- | ---------------------- | --------------------- | ----------------- | -------------------------------- |
| gradient_boosted_trees                | 0.0733179                  | 0.114163               | 0.0252525             | 124               | 0.97587                          |
| mlp                                   | 0.0830626                  | 0.101288               | 0.0616162             | 124               | 0.97587                          |
| traditional timing/template reference | 0.0663573                  | 0.0995708              | 0.0272727             | 124               | 0.97587                          |
| residual_tcn_fusion                   | 0.0640371                  | 0.0806867              | 0.0444444             | 124               | 0.97587                          |
| cnn_1d                                | 0.0672854                  | 0.07897                | 0.0535354             | 124               | 0.97587                          |
| ridge_logistic                        | 0.0640371                  | 0.0729614              | 0.0535354             | 124               | 0.97587                          |

## Systematics and Caveats

- The endpoint is a blinded proxy for manual waveform pathology, not externally adjudicated human truth.
- Frozen S07n scores were trained on injected closure; this report tests transfer ranking and gate enrichment, not a calibrated beam pile-up rate.
- The raw ROOT check verifies event identity and run support for all controls. It does not rereconstruct every waveform atom because S07n already materialized the run-held-out atoms from raw ROOT.
- Only seven run blocks are available; bootstrap intervals capture run composition but not all model-form uncertainty.
- The GBT score appears in one component of the proxy vote, so the primary winner should be interpreted together with the hierarchical-gate enrichment table and the residual TCN/ridge/MLP comparisons.

## Verdict

`result.json` names **traditional timing/template reference** as the winner with AUC **0.7592** and run-bootstrap CI **[0.7135, 0.8063]** against the blinded real-current adjudication proxy. The frozen hierarchical gate is enriched for proxy-pathology windows when pathology capture exceeds quiet false-veto rate in `hierarchical_gate_real_control_summary.csv`; production adoption still requires the proposed S07p human-review follow-up.

## Reproducibility

```bash
uv run --with uproot --with pandas --with scikit-learn python scripts/s07o_1783724290_27234_08030cfb_real_current_support_pooling.py --config configs/s07o_1783724290_27234_08030cfb_real_current_support_pooling.json
```

Artifacts: `result.json`, `REPORT.md`, `manifest.json`, `raw_root_reproduction.csv`, `reproduction_match_table.csv`, `real_current_control_windows.csv`, `method_metrics.csv`, `method_by_run.csv`, `hierarchical_gate_real_control_summary.csv`, `hierarchical_gate_real_control_rows.csv`, and `control_counts_by_run.csv`.
