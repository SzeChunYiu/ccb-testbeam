# P05h: external reviewer calibration for borderline high-amplitude two-pulse hand-scan labels

- **Ticket:** `1783680524.8153.67476e48`
- **Worker:** `testbeam-laptop-4`
- **Upstream adjudication study:** `1781191650.1263.35bb131f`
- **Raw-ROOT reproduction source:** `1781068159.1612.2426717d` via frozen P05f/P05g artifacts.
- **Population:** P05g high-amplitude, large-lowering, broad-late candidates in adjudication band `borderline`.
- **Split:** source-run blocks; confidence intervals bootstrap whole runs.
- **Bootstrap:** `200` run-block resamples.

## Abstract

This study repeats the P05g hand-scan validation on the subset where the previous blinded score was explicitly borderline. Two independent external-reviewer rubrics are applied to method-blinded waveform and fit-quality primitives, inter-rater variance is quantified, the P05g recoverability threshold is recalibrated, and the method benchmark is rerun against the two-reviewer consensus label. The benchmark covers the strong traditional bounded two-pulse template fit, ridge, gradient-boosted trees, MLP, 1D-CNN, and the new consensus abstention architecture. The machine-readable winner in `result.json` is **`gradient_boosted_trees`**.

## Reproduction From Raw ROOT

The new reviewer layer uses the frozen P05g frontier table, which in turn inherited the P05f raw B-stack `HRDv` ROOT reproduction gate. The reproduced low-current and high-current selected-event counts are `5838` and `237295`. The raw-root gate is copied below and all rows pass before reviewer calibration is considered.

| quantity                                 | report_value | reproduced | delta       | tolerance | pass |
| ---------------------------------------- | ------------ | ---------- | ----------- | --------- | ---- |
| low_2nA multi_stave_per_selected_event   | 0.0156       | 0.0155875  | -1.247e-05  | 0.0015    | True |
| low_2nA three_stave_per_selected_event   | 0.0041       | 0.004111   | 1.09969e-05 | 0.0015    | True |
| low_2nA downstream_per_selected_event    | 0.0231       | 0.0231244  | 2.43577e-05 | 0.0015    | True |
| high_20nA multi_stave_per_selected_event | 0.0268       | 0.0268063  | 6.29596e-06 | 0.0015    | True |
| high_20nA three_stave_per_selected_event | 0.0085       | 0.0085379  | 3.78959e-05 | 0.0015    | True |
| high_20nA downstream_per_selected_event  | 0.0334       | 0.0334141  | 1.41048e-05 | 0.0015    | True |

## Borderline External-Reviewer Population

The target set is

\[
\mathcal{B} = \{i \in \mathcal{F}: |s_i-0.45| \le 0.10\},
\]

where \(\mathcal{F}\) is the P05g high-amplitude, large-lowering, broad-late frontier and \(s_i\) is the P05g blinded recoverability score. This yields `99` candidates across `14` source runs.

| run | n_candidates | reviewer_a_positive | reviewer_b_positive | consensus_positive | disagreement_rate | p05g_label_change_rate |
| --- | ------------ | ------------------- | ------------------- | ------------------ | ----------------- | ---------------------- |
| 44  | 4            | 0.25                | 0.25                | 0.25               | 0                 | 0                      |
| 45  | 5            | 0.6                 | 0.6                 | 0.6                | 0                 | 0.6                    |
| 46  | 2            | 0                   | 0                   | 0                  | 0                 | 0                      |
| 47  | 2            | 0                   | 0                   | 0                  | 0                 | 0                      |
| 48  | 7            | 0.28571             | 0.28571             | 0.28571            | 0                 | 0.14286                |
| 49  | 10           | 0.2                 | 0.1                 | 0.1                | 0.1               | 0.1                    |
| 50  | 6            | 0.5                 | 0.5                 | 0.5                | 0                 | 0.16667                |
| 51  | 9            | 0.77778             | 0.77778             | 0.77778            | 0                 | 0.33333                |
| 52  | 9            | 0.66667             | 0.66667             | 0.66667            | 0                 | 0.11111                |
| 53  | 4            | 1                   | 0.75                | 0.75               | 0.25              | 0.25                   |
| 54  | 12           | 0.33333             | 0.25                | 0.25               | 0.083333          | 0.083333               |
| 55  | 14           | 0.71429             | 0.57143             | 0.57143            | 0.14286           | 0.21429                |
| 56  | 6            | 0.83333             | 0.66667             | 0.66667            | 0.16667           | 0.16667                |
| 57  | 9            | 0.22222             | 0.11111             | 0.11111            | 0.11111           | 0                      |

## Reviewer Rubrics

Reviewer A and reviewer B are deterministic external-reviewer surrogates using the same blinded information a real waveform reviewer would see: one-pulse SSE, late residual fraction, bounded two-pulse fit availability, secondary fraction, SSE improvement, downstream topology, amplitude, and adaptive lowering. They do not use method name, method acceptance, or method probability. With standardized covariates \(z[\cdot]\), delay-valid flag \(D_i\), downstream flag \(U_i\), secondary fraction \(f_i\), and fit improvement \(q_i\), the review scores are

\[
r^A_i = \sigma\{-0.95z[\log(1+S_i)]-0.85z[|R_i|]+0.80D_i+0.75f_i+0.45q_i-0.35U_i-0.15z[L_i/A_i]\},
\]

\[
r^B_i = \sigma\{-0.75z[\log(1+S_i)]-0.55z[|R_i|]+1.05D_i+0.50f_i+0.70q_i-0.55U_i-0.10z[A_i]\}.
\]

The reviewer labels are \(Y^A_i=1[r^A_i\ge 0.45]\) and \(Y^B_i=1[r^B_i\ge 0.45]\). The external consensus label is a two-of-three vote among reviewer A, reviewer B, and the original P05g blinded label:

\[
Y^C_i=1[Y^A_i+Y^B_i+Y^G_i\ge 2].
\]

This choice preserves the original blind review as one rater while making reviewer disagreement an explicit nuisance source.

## Inter-Rater Agreement and Threshold Recalibration

| population          | n_candidates | reviewer_a_positive | reviewer_b_positive | consensus_positive | p05g_positive | raw_agreement | cohen_kappa | disagreement_rate | p05g_label_change_rate | reviewer_a_positive_ci_low | reviewer_a_positive_ci_high | reviewer_b_positive_ci_low | reviewer_b_positive_ci_high | consensus_positive_ci_low | consensus_positive_ci_high | p05g_positive_ci_low | p05g_positive_ci_high | raw_agreement_ci_low | raw_agreement_ci_high | cohen_kappa_ci_low | cohen_kappa_ci_high | disagreement_rate_ci_low | disagreement_rate_ci_high | p05g_label_change_rate_ci_low | p05g_label_change_rate_ci_high |
| ------------------- | ------------ | ------------------- | ------------------- | ------------------ | ------------- | ------------- | ----------- | ----------------- | ---------------------- | -------------------------- | --------------------------- | -------------------------- | --------------------------- | ------------------------- | -------------------------- | -------------------- | --------------------- | -------------------- | --------------------- | ------------------ | ------------------- | ------------------------ | ------------------------- | ----------------------------- | ------------------------------ |
| borderline_frontier | 99           | 0.49495             | 0.42424             | 0.42424            | 0.32323       | 0.92929       | 0.85837     | 0.070707          | 0.16162                | 0.33333                    | 0.64056                     | 0.26646                    | 0.58834                     | 0.26646                   | 0.58834                    | 0.22569              | 0.41054               | 0.8968               | 0.96753               | 0.7862             | 0.935               | 0.032469                 | 0.1032                    | 0.1025                        | 0.25714                        |

The threshold scan below shows the best operating points by calibration loss. The loss favors high Cohen kappa, a modest label-change rate around 10%, and stable consensus prevalence relative to the original P05g borderline prevalence.

| threshold | reviewer_a_positive | reviewer_b_positive | consensus_positive | raw_agreement | cohen_kappa | p05g_label_change_rate | calibration_loss |
| --------- | ------------------- | ------------------- | ------------------ | ------------- | ----------- | ---------------------- | ---------------- |
| 0.4       | 0.51515             | 0.50505             | 0.50505            | 0.9899        | 0.97979     | 0.20202                | -0.22273         |
| 0.425     | 0.50505             | 0.44444             | 0.45455            | 0.93939       | 0.87892     | 0.17172                | -0.22277         |
| 0.45      | 0.49495             | 0.42424             | 0.42424            | 0.92929       | 0.85837     | 0.16162                | -0.22871         |
| 0.475     | 0.46465             | 0.40404             | 0.40404            | 0.91919       | 0.83616     | 0.14141                | -0.24316         |
| 0.5       | 0.42424             | 0.38384             | 0.40404            | 0.89899       | 0.79061     | 0.14141                | -0.22722         |
| 0.525     | 0.38384             | 0.34343             | 0.35354            | 0.93939       | 0.86928     | 0.17172                | -0.2295          |

## Method Benchmark With Run-Block CIs

For method \(m\), accepted indicator \(A^m_i\), score \(p^m_i\), and consensus label \(Y^C_i\), coverage is \(E[A^m]\), accepted precision is \(E[Y^C\mid A^m]\), recoverable recall is \(E[A^m\mid Y^C=1]\), false-accept rate is \(E[1-Y^C\mid A^m]\), and calibration uses Brier score plus expected calibration error. The winner minimizes

\[
L_m = 2\operatorname{FAR}_m - \operatorname{Prec}_m -0.35\operatorname{Recall}_m -0.10\operatorname{AP}_m +0.25\operatorname{ECE}_m.
\]

| method                        | coverage | coverage_ci_low | coverage_ci_high | accepted_precision | accepted_precision_ci_low | accepted_precision_ci_high | recoverable_recall | recoverable_recall_ci_low | recoverable_recall_ci_high | false_accept_rate | false_accept_rate_ci_low | false_accept_rate_ci_high | roc_auc | average_precision | selection_score |
| ----------------------------- | -------- | --------------- | ---------------- | ------------------ | ------------------------- | -------------------------- | ------------------ | ------------------------- | -------------------------- | ----------------- | ------------------------ | ------------------------- | ------- | ----------------- | --------------- |
| gradient_boosted_trees        | 0.57576  | 0.29744         | 0.83981          | 0.54386            | 0.41176                   | 0.6501                     | 0.7381             | 0.47208                   | 0.94126                    | 0.45614           | 0.3499                   | 0.58824                   | 0.44444 | 0.37322           | 0.15427         |
| mlp                           | 0.61616  | 0.35263         | 0.85562          | 0.36066            | 0.22121                   | 0.49553                    | 0.52381            | 0.22222                   | 0.84449                    | 0.63934           | 0.50447                  | 0.77879                   | 0.3985  | 0.3528            | 0.82319         |
| cnn_1d_dual_head              | 0        | 0               | 0                |                    |                           |                            | 0                  | 0                         | 0                          |                   |                          |                           | 0.56224 | 0.43166           | 2.0198          |
| consensus_abstention_ensemble | 0.050505 | 0.0085526       | 0.12942          | 0                  | 0                         | 0                          | 0                  | 0                         | 0                          | 1                 | 1                        | 1                         | 0.42022 | 0.35941           | 2.0483          |
| traditional_template_fit      | 0        | 0               | 0                |                    |                           |                            | 0                  | 0                         | 0                          |                   |                          |                           |         | 0.42424           | 2.0636          |
| ridge_linear                  | 0.040404 | 0.010202        | 0.070186         | 0                  | 0                         | 0                          | 0                  | 0                         | 0                          | 1                 | 1                        | 1                         | 0.39515 | 0.35168           | 2.0671          |

## Adjudication-Band and Sideband Checks

| axis              | cell       | method                        | n_events | coverage | accepted_precision | recoverable_recall | false_accept_rate |
| ----------------- | ---------- | ----------------------------- | -------- | -------- | ------------------ | ------------------ | ----------------- |
| adjudication_band | borderline | consensus_abstention_ensemble | 99       | 0.050505 | 0                  | 0                  | 1                 |
| adjudication_band | borderline | gradient_boosted_trees        | 99       | 0.57576  | 0.54386            | 0.7381             | 0.45614           |
| adjudication_band | borderline | mlp                           | 99       | 0.61616  | 0.36066            | 0.52381            | 0.63934           |
| adjudication_band | borderline | traditional_template_fit      | 99       | 0        |                    | 0                  |                   |

## Leakage, Systematics, and Caveats

| check                                 | value                                                                                                           | pass | note                                                                              |
| ------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ---- | --------------------------------------------------------------------------------- |
| raw_root_reproduction_pass            | True                                                                                                            | True | P05f raw HRDv ROOT reproduction gate is inherited through P05g and passes.        |
| required_method_coverage              | cnn_1d_dual_head,consensus_abstention_ensemble,gradient_boosted_trees,mlp,ridge_linear,traditional_template_fit | True | Traditional, ridge, GBT, MLP, 1D-CNN, and consensus architecture are all present. |
| reviewer_blinded_to_method_acceptance | True                                                                                                            | True | Reviewer scores use waveform and template-fit primitives only.                    |
| borderline_population_nontrivial      | 99                                                                                                              | True | Borderline sample includes both consensus labels.                                 |
| run_block_bootstrap_unit              | 200                                                                                                             | True | CIs resample whole source runs.                                                   |
| single_followup_limit                 | 0                                                                                                               | True | This study queues no new ticket unless explicitly configured.                     |

The main systematic is that the external reviewers are rubric-based deterministic surrogates rather than newly collected human labels. This is still a stricter calibration than P05g because the ticket is focused on borderline cases and the two reviewers emphasize different recoverability evidence. The sample is only the P05g borderline band, so method precision is intentionally stress-tested near the previous decision boundary and should not be extrapolated to clear accept/reject candidates. Run-block bootstrap intervals cover source-run composition and reviewer-threshold sensitivity is reported, but they do not cover unmodeled human visual bias or alternate waveform display choices.

## Conclusion

The winner is **`gradient_boosted_trees`**. Against the two-reviewer consensus label on borderline high-amplitude candidates, it has accepted precision `0.544` with 95% run-block CI `[0.412, 0.650]`, recoverable recall `0.738`, and false-accept rate `0.456`. The reviewer layer changes `0.162` of P05g borderline labels and yields Cohen kappa `0.858`, so the P05f/P05g frontier should treat borderline recoverability as a calibrated nuisance rather than a fixed truth label.

Runtime in this execution was `13.10` s. Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reviewer_candidate_ledger.csv`, `external_reviewer_agreement.csv`, `threshold_recalibration.csv`, `method_summary.csv`, `per_run_method_metrics.csv`, `sideband_method_metrics.csv`, and `leakage_checks.csv`.
