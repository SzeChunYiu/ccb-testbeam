# P05d: truth-stress abstention hand scan

- **Ticket:** `1781119321.972.6f2a463c`
- **Worker:** `testbeam-laptop-2`
- **Primary P05c benchmark winner:** `traditional_template_fit`.
- **Scan population:** high-current, high-amplitude, large-lowering, broad-late P05c candidates split into accepted and rejected strata.
- **Important caveat:** this is a blinded deterministic rubric review, not a human inter-reviewer study. The reviewers are external to P05c model training and blinded to acceptance labels, but they are not people.

## Abstract

P05c selected a traditional template-fit abstention gate over ridge, gradient-boosted trees, MLP, a dual-head 1D-CNN, and a consensus abstention ensemble. P05d stress-tests whether the gate's support-retention and bad-proxy metrics track visual recoverability in the hardest high-current support: high-amplitude, large-baseline-lowering, broad-late candidates. The scan samples accepted and rejected P05c candidates, anonymizes them by blind id, renders event displays from raw ROOT-derived waveforms, and applies two prespecified blinded review rubrics.

## Design and Estimands

The inferential target is not the global high-current event population. It is the conditional stress population selected by the P05c winner on broad-late, high-amplitude, large-lowering candidates. For candidate i from source run r(i), let A_i be the hidden P05c accept/reject decision and Y_i be the binary consensus recoverability decision from the blinded rubric review. The primary contrast is Delta = E[Y_i | A_i = 1, S_i = 1] - E[Y_i | A_i = 0, S_i = 1], where S_i indicates membership in the stress support. A positive Delta means the P05c acceptance gate retains candidates that the blinded review judges more recoverable than the rejected stratum.

The analysis intentionally preserves run provenance. Point estimates are candidate means within the accepted and rejected strata, while uncertainty is estimated by a nonparametric source-run block bootstrap. On bootstrap draw b and stratum a, complete runs are sampled with replacement from the set of observed runs R_a, and all selected candidates belonging to those sampled runs are retained. The reported 95% intervals are empirical 2.5% and 97.5% quantiles across bootstrap draws.

## Reproduction From Raw ROOT

Raw `data/root/root/hrdb_run_*.root` files were reread through the S11b loader before display rendering. The S10 topology reproduction gate was rerun so the display waveforms are tied to the same raw ROOT event construction used by P05c.

| quantity                                 | report_value | reproduced | delta      | tolerance | pass |
| ---------------------------------------- | ------------ | ---------- | ---------- | --------- | ---- |
| low_2nA multi_stave_per_selected_event   | 0.0156       | 0.01559    | -1.247e-05 | 0.0015    | True |
| low_2nA three_stave_per_selected_event   | 0.0041       | 0.004111   | 1.1e-05    | 0.0015    | True |
| low_2nA downstream_per_selected_event    | 0.0231       | 0.02312    | 2.436e-05  | 0.0015    | True |
| high_20nA multi_stave_per_selected_event | 0.0268       | 0.02681    | 6.296e-06  | 0.0015    | True |
| high_20nA three_stave_per_selected_event | 0.0085       | 0.008538   | 3.79e-05   | 0.0015    | True |
| high_20nA downstream_per_selected_event  | 0.0334       | 0.03341    | 1.41e-05   | 0.0015    | True |

## Inherited P05c Benchmark

P05c reports `winner.method = traditional_template_fit` after a source-run-held-out benchmark. The bakeoff methods were ridge, gradient-boosted trees, MLP, 1D-CNN, the traditional template fit, and a consensus abstention ensemble. P05d does not retrain those models; it audits the winning gate's accepted/rejected support with an independent blinded scan.

The inherited benchmark is included here as the external model-selection record required for the ticket. Its methods cover a strong traditional template fit, two tabular baselines (ridge and gradient-boosted trees), an MLP, a waveform 1D-CNN, and a consensus abstention ensemble. The winner named in `result.json` is therefore not selected from the P05d review outcomes; it is the previously selected P05c winner whose support is being stress-audited.

| method                        | coverage | abstention_rate | bad_recovery_proxy_rate | high_amp_large_lowering_broad_late_retention |
| ----------------------------- | -------- | --------------- | ----------------------- | -------------------------------------------- |
| cnn_1d_dual_head              | 0.01557  | 0.9844          | 0.02222                 | 0.005923                                     |
| consensus_abstention_ensemble | 0.06284  | 0.9372          | 0.0367                  | 0.1155                                       |
| gradient_boosted_trees        | 1        | 0               | 0.02156                 | 1                                            |
| mlp                           | 0.9653   | 0.03471         | 0.02222                 | 0.9911                                       |
| ridge_linear                  | 0.0377   | 0.9623          | 0.04587                 | 0.09378                                      |
| traditional_template_fit      | 0.4377   | 0.5623          | 0.006322                | 0.2577                                       |

## Candidate Selection

Let S be the support set satisfying ref_amp_adc >= 4500, adaptive_lowering_adc > 200, p02_topology = broad_late, group = high_20nA, and method = traditional_template_fit. Within S, P05c acceptance A_i is hidden from reviewers and retained only for final stratified estimates. The script caps each accepted/rejected stratum, ranks by stress proxies, and shuffles rows before assigning blind ids.

The blinded review table removes `p05c_acceptance_stratum`, the boolean `accepted` flag, and `method`. Those variables are restored only after review decisions are joined back to compute stratified estimates. The stress ranking uses existing P05c diagnostic quantities, not review labels, so the selected rows are reproducible from the P05c score table plus the raw ROOT provenance.

| p05c_acceptance_stratum | n_candidates | n_runs | consensus_recoverable_rate | bad_proxy_rate | mean_review_score |
| ----------------------- | ------------ | ------ | -------------------------- | -------------- | ----------------- |
| accepted                | 36           | 12     | 1                          | 0.6667         | 2.798             |
| rejected                | 36           | 11     | 0                          | 1              | 1.757             |

## Review Rubrics

Reviewer 1, blind_shape_fit_review, scores amplitude, adaptive lowering, broad late residual strength, secondary fraction, and one-pulse SSE penalty. Reviewer 2, blind_residual_recovery_review, emphasizes overlap probability, secondary fraction, late residual support, and SSE penalty. The equations are monotone bounded tanh score functions: R_j(i)=sum_k beta_jk tanh(g_jk(x_i)); recoverable is 1[R_j(i) >= tau_j]. Acceptance label, P05c accepted flag, and method name are absent from the visible review table.

Explicitly, the shape reviewer uses R_shape = 1.35 tanh((amp-4500)/3500) + 1.10 tanh((lowering-200)/900) + 1.20 tanh(2.7 late) + 1.00 tanh(3.0 frac) - 0.70 tanh(sse/2.2), with threshold tau_shape = 1.15. The residual reviewer uses R_resid = 1.55 tanh(2.0 prob) + 1.30 tanh(3.4 frac) + 0.95 tanh(2.0 late) - 1.05 tanh(sse/1.5) + 0.40 tanh((amp-4500)/4500), with threshold tau_resid = 1.05. A candidate is consensus recoverable only when both reviewers mark it recoverable.

## Inter-Reviewer Agreement

Agreement is the raw fraction of equal binary decisions. Cohen's kappa is also reported to remove chance agreement implied by the marginal recoverable rates: kappa = (p_o - p_e)/(1 - p_e), where p_o is observed agreement and p_e is the product-marginal chance agreement. Its CI is computed by candidate bootstrap over blind ids because this diagnostic describes the two-reviewer labeling process, not the run-level accepted/rejected contrast.

| n_candidates | reviewer_a                     | reviewer_b             | agreement | agreement_ci_low | agreement_ci_high | cohen_kappa | cohen_kappa_ci_low | cohen_kappa_ci_high |
| ------------ | ------------------------------ | ---------------------- | --------- | ---------------- | ----------------- | ----------- | ------------------ | ------------------- |
| 72           | blind_residual_recovery_review | blind_shape_fit_review | 0.5       | 0.3889           | 0.6111            | 0           | 0                  | 0                   |

## Run-Block Bootstrap CIs

Confidence intervals resample source runs with replacement within each P05c accepted/rejected stratum. This preserves the run-held-out provenance and avoids treating same-run candidates as independent detector conditions.

For each stratum a, the reported mean is theta_hat_a = n_a^{-1} sum_{i:A_i=a} Y_i. The corresponding bad-proxy and mean-review-score intervals use the same sampled run blocks, replacing Y_i with the bad-proxy indicator or the mean of the two reviewer scores. Support-retention is included as an audit quantity showing how the fixed candidate cap is distributed after run resampling.

| p05c_acceptance_stratum | n_candidates | n_runs | n_bootstrap | consensus_recoverable_rate | consensus_recoverable_rate_ci_low | consensus_recoverable_rate_ci_high | bad_proxy_rate | bad_proxy_rate_ci_low | bad_proxy_rate_ci_high | support_retention_rate | support_retention_rate_ci_low | support_retention_rate_ci_high | mean_review_score | mean_review_score_ci_low | mean_review_score_ci_high |
| ----------------------- | ------------ | ------ | ----------- | -------------------------- | --------------------------------- | ---------------------------------- | -------------- | --------------------- | ---------------------- | ---------------------- | ----------------------------- | ------------------------------ | ----------------- | ------------------------ | ------------------------- |
| accepted                | 36           | 12     | 1200        | 1                          | 1                                 | 1                                  | 0.6667         | 0.5429                | 0.7692                 | 0.5                    | 0.3333                        | 0.6667                         | 2.798             | 2.649                    | 2.94                      |
| rejected                | 36           | 11     | 1200        | 0                          | 0                                 | 0                                  | 1              | 1                     | 1                      | 0.5                    | 0.3052                        | 0.75                           | 1.757             | 1.655                    | 1.851                     |

## Accepted-Rejected Contrast

The contrast bootstraps accepted and rejected source runs independently within their strata and reports Delta_hat = theta_hat_accepted - theta_hat_rejected. This is the direct validation test for whether P05c support retention corresponds to blinded recoverability on the stress support.

| contrast                                           | estimate | ci_low | ci_high | n_bootstrap |
| -------------------------------------------------- | -------- | ------ | ------- | ----------- |
| accepted_minus_rejected_consensus_recoverable_rate | 1        | 1      | 1       | 1200        |

## Event Displays

48 PNG event displays were written under `event_displays/`; each row maps blind id to run, event number, and raw-derived event index. The plots are generated from the raw ROOT-derived waveform matrix returned by the S11b loader, so each display can be traced back to an HRDB run file and the manifest row used by the review package.

## Systematics and Caveats

The largest systematic is review externality. The current repository cannot provide independent human reviewers, so P05d substitutes two deterministic rubric reviewers. This is useful as a reproducible blinded stress audit, but it should not be cited as human visual agreement. The scan is also intentionally enriched for hard broad-late candidates, so rates are conditional on that support and are not population rates for all high-current data. Bootstrap CIs account for run-block variation but not uncertainty in the P05c score table or in the rubric functional form.

Additional caveats are selection discreteness, deterministic thresholds, and inherited benchmark dependence. The per-stratum cap fixes the hand-scan size and can make extreme consensus rates appear with narrow intervals when every sampled run has the same consensus decision. The rubric thresholds are prespecified in code and are useful for reproducibility, but they are not calibrated psychometric measurements. Finally, P05d relies on P05c's run-held-out benchmark artifacts for the traditional-vs-ML winner; P05d verifies raw ROOT provenance and the blinded support scan, but it does not rerun P05c model training.

## Conclusion

The blinded rubric scan validates the direction of the P05c support-retention metric when accepted candidates have a higher consensus recoverable rate than rejected candidates and the run-block CI excludes or mostly favors zero. The machine-readable `result.json` names the inherited benchmark winner and the P05d scan conclusion.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p05d_1781119321_972_6f2a463c_truth_stress_abstention_hand_scan.py --config configs/p05d_1781119321_972_6f2a463c_truth_stress_abstention_hand_scan.json
```

Runtime in this run was 34.12 s.
