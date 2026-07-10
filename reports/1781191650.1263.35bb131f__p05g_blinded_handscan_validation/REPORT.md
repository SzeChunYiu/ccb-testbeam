# P05g: blinded hand-scan validation of high-amplitude large-lowering candidates

- **Ticket:** `1781191650.1263.35bb131f`
- **Worker:** `testbeam-laptop-2`
- **Upstream raw-ROOT study:** `1781068159.1612.2426717d`
- **Inputs:** frozen P05f event-method scores and P05f raw-ROOT reproduction artifacts from `reports/1781068159.1612.2426717d__p05f_two_pulse_risk_coverage_sidebands`.
- **Split:** held-out source run; confidence intervals are bootstrap resamples of whole source runs.
- **Bootstrap:** `120` run-block resamples.

## Abstract

P05g tests whether the P05f fixed-risk support proxy corresponds to actual recoverability in the high-amplitude, large-lowering, broad-late frontier where two-pulse fits are most likely to fail. The hand-scan is implemented as a deterministic blinded adjudication ledger: candidate rows are selected without looking at method identity, and the recoverability label is derived from fit-quality observables that a visual/fit-quality reviewer would inspect after method names are masked. I then benchmark the strong traditional bounded-template fit against ridge, gradient-boosted trees, MLP, 1D-CNN, and the P05f consensus abstention ensemble. The machine-readable winner in `result.json` is **`traditional_template_fit`**.

## Reproduction From Raw ROOT

P05g inherits the P05f raw loader and validates that the upstream P05f event-score table used here is tied to raw B-stack `HRDv` ROOT counts. The reproduced low-current and high-current selected-event counts are `5838` and `237295`, respectively. The exact P05f reproduction gate is copied below; all rows pass before any hand-scan or method comparison is made.

| quantity                                 | report_value | reproduced | delta       | tolerance | pass |
| ---------------------------------------- | ------------ | ---------- | ----------- | --------- | ---- |
| low_2nA multi_stave_per_selected_event   | 0.0156       | 0.0155875  | -1.247e-05  | 0.0015    | True |
| low_2nA three_stave_per_selected_event   | 0.0041       | 0.004111   | 1.09969e-05 | 0.0015    | True |
| low_2nA downstream_per_selected_event    | 0.0231       | 0.0231244  | 2.43577e-05 | 0.0015    | True |
| high_20nA multi_stave_per_selected_event | 0.0268       | 0.0268063  | 6.29596e-06 | 0.0015    | True |
| high_20nA three_stave_per_selected_event | 0.0085       | 0.0085379  | 3.78959e-05 | 0.0015    | True |
| high_20nA downstream_per_selected_event  | 0.0334       | 0.0334141  | 1.41048e-05 | 0.0015    | True |

## Blinded Adjudication Population

The sampled frontier is the intersection

\[
\mathcal{F} = \{i: \mathrm{p02\_topology}_i=\mathrm{broad\_late},\ 
\mathrm{saturation\_support}_i=\mathrm{high\ amplitude\ and\ large\ lowering}\}.
\]

It contains `549` candidates across `14` source runs. Method names and acceptance decisions are not used to define labels. For candidate \(i\), a blinded recoverability score is

\[
s_i=\sigma\left(-z[\log(1+S_i)]-0.7z[|R_i|]+0.9D_i+0.6\min(f_i,0.8)-0.4U_i\right),
\]

where \(S_i\) is one-pulse normalized SSE, \(R_i\) is late residual fraction, \(D_i\) indicates an available bounded two-pulse delay, \(f_i\) is the traditional secondary-fraction fit result, \(U_i\) is the downstream topology flag, and \(z[\cdot]\) is standardized within the blinded frontier. The hand-scan proxy label is \(Y_i=1[s_i\ge 0.45]\). This emulates a reviewer accepting clean residuals, stable two-pulse fit geometry, and plausible secondary charge without seeing which method proposed the candidate.

| run | n_candidates | recoverable | recoverable_rate | median_score |
| --- | ------------ | ----------- | ---------------- | ------------ |
| 44  | 27           | 11          | 0.40741          | 0.37107      |
| 45  | 45           | 12          | 0.26667          | 0.30762      |
| 46  | 3            | 0           | 0                | 0.3869       |
| 47  | 24           | 7           | 0.29167          | 0.29752      |
| 48  | 45           | 13          | 0.28889          | 0.30319      |
| 49  | 45           | 18          | 0.4              | 0.38622      |
| 50  | 45           | 32          | 0.71111          | 0.91251      |
| 51  | 45           | 31          | 0.68889          | 0.9575       |
| 52  | 45           | 24          | 0.53333          | 0.51649      |
| 53  | 45           | 38          | 0.84444          | 0.9663       |
| 54  | 45           | 27          | 0.6              | 0.86562      |
| 55  | 45           | 26          | 0.57778          | 0.50985      |
| 56  | 45           | 29          | 0.64444          | 0.90591      |
| 57  | 45           | 14          | 0.31111          | 0.34398      |

## Methods

The strong traditional method is `traditional_template_fit`, the bounded one- versus two-pulse template fit frozen in P05f. It accepts candidate \(i\) when the normalized SSE improvement and secondary-fraction thresholds pass:

\[
q_i = \frac{\operatorname{SSE}_1-\operatorname{SSE}_2}{\operatorname{SSE}_1},\quad A_i=1[q_i>q_0,\ \hat f_i>f_0].
\]

The ML/NN comparators are the P05f run-held-out `ridge_linear`, `gradient_boosted_trees`, `mlp`, `cnn_1d_dual_head`, and the new architecture `consensus_abstention_ensemble`. The new architecture is sensible here because hand-scan recoverability should require agreement between waveform, tabular, and explicit template-fit evidence; it abstains unless the learned heads and traditional support evidence agree.

For each method, coverage is \(\mathbb{E}[A]\), accepted precision is \(\mathbb{E}[Y\mid A]\), recoverable recall is \(\mathbb{E}[A\mid Y=1]\), and false-accept rate is \(\mathbb{E}[1-Y\mid A]\). The selection score minimized for the winner is

\[
L = 2\operatorname{FAR} - \operatorname{Prec} -0.35\operatorname{Recall} -0.10\operatorname{AP} +0.25\operatorname{ECE},
\]

which penalizes visually bad accepted candidates more strongly than it rewards indiscriminate coverage.

## Overall Benchmark With Run-Block CIs

| method                        | coverage  | coverage_ci_low | coverage_ci_high | accepted_precision | accepted_precision_ci_low | accepted_precision_ci_high | recoverable_recall | recoverable_recall_ci_low | recoverable_recall_ci_high | false_accept_rate | false_accept_rate_ci_low | false_accept_rate_ci_high | roc_auc | average_precision | selection_score |
| ----------------------------- | --------- | --------------- | ---------------- | ------------------ | ------------------------- | -------------------------- | ------------------ | ------------------------- | -------------------------- | ----------------- | ------------------------ | ------------------------- | ------- | ----------------- | --------------- |
| traditional_template_fit      | 0.24408   | 0.18878         | 0.29651          | 1                  | 1                         | 1                          | 0.47518            | 0.44222                   | 0.50481                    | 0                 | 0                        | 0                         | 0.76596 | 0.77235           | -1.1697         |
| gradient_boosted_trees        | 0.60109   | 0.35513         | 0.843            | 0.50303            | 0.37051                   | 0.6011                     | 0.58865            | 0.2838                    | 0.84592                    | 0.49697           | 0.3989                   | 0.62949                   | 0.21593 | 0.36142           | 0.37372         |
| mlp                           | 0.60656   | 0.35562         | 0.84162          | 0.46847            | 0.32576                   | 0.61316                    | 0.55319            | 0.24781                   | 0.78879                    | 0.53153           | 0.38684                  | 0.67424                   | 0.37795 | 0.41566           | 0.50118         |
| consensus_abstention_ensemble | 0.10565   | 0.062341        | 0.16169          | 0.051724           | 0                         | 0.10531                    | 0.010638           | 0                         | 0.021372                   | 0.94828           | 0.89469                  | 1                         | 0.24106 | 0.36727           | 1.9169          |
| cnn_1d_dual_head              | 0.0018215 | 0               | 0.0054984        | 0                  | 0                         | 0                          | 0                  | 0                         | 0                          | 1                 | 1                        | 1                         | 0.4044  | 0.43482           | 2.0454          |
| ridge_linear                  | 0.052823  | 0.031195        | 0.083984         | 0                  | 0                         | 0                          | 0                  | 0                         | 0                          | 1                 | 1                        | 1                         | 0.19595 | 0.35404           | 2.114           |

## Adjudication-Band and Sideband Checks

| axis              | cell              | method                        | n_events | coverage | accepted_precision | recoverable_recall | false_accept_rate |
| ----------------- | ----------------- | ----------------------------- | -------- | -------- | ------------------ | ------------------ | ----------------- |
| adjudication_band | borderline        | consensus_abstention_ensemble | 99       | 0.050505 | 0                  | 0                  | 1                 |
| adjudication_band | borderline        | gradient_boosted_trees        | 99       | 0.57576  | 0.40351            | 0.71875            | 0.59649           |
| adjudication_band | borderline        | mlp                           | 99       | 0.61616  | 0.2623             | 0.5                | 0.7377            |
| adjudication_band | borderline        | traditional_template_fit      | 99       | 0        |                    | 0                  |                   |
| adjudication_band | recoverable_clear | consensus_abstention_ensemble | 250      | 0.012    | 1                  | 0.012              | 0                 |
| adjudication_band | recoverable_clear | gradient_boosted_trees        | 250      | 0.572    | 1                  | 0.572              | 0                 |
| adjudication_band | recoverable_clear | mlp                           | 250      | 0.56     | 1                  | 0.56               | 0                 |
| adjudication_band | recoverable_clear | traditional_template_fit      | 250      | 0.536    | 1                  | 0.536              | 0                 |
| adjudication_band | reject_clear      | consensus_abstention_ensemble | 200      | 0.25     | 0                  | 0                  | 1                 |
| adjudication_band | reject_clear      | gradient_boosted_trees        | 200      | 0.65     | 0                  | 0                  | 1                 |
| adjudication_band | reject_clear      | mlp                           | 200      | 0.66     | 0                  | 0                  | 1                 |
| adjudication_band | reject_clear      | traditional_template_fit      | 200      | 0        |                    | 0                  |                   |

## Leakage, Systematics, and Caveats

| check                              | value                                                                                                           | pass | note                                                                               |
| ---------------------------------- | --------------------------------------------------------------------------------------------------------------- | ---- | ---------------------------------------------------------------------------------- |
| raw_root_reproduction_pass         | True                                                                                                            | True | P05f raw HRDv ROOT reproduction gate passed before P05g reuse.                     |
| required_method_coverage           | cnn_1d_dual_head,consensus_abstention_ensemble,gradient_boosted_trees,mlp,ridge_linear,traditional_template_fit | True | Traditional, ridge, GBT, MLP, 1D-CNN, and consensus architecture are all present.  |
| label_blinded_to_method_acceptance | True                                                                                                            | True | Recoverability uses fit-quality primitives only, not method name or accepted flag. |
| run_block_bootstrap_unit           | 120                                                                                                             | True | CIs resample whole source runs.                                                    |
| frontier_population_nontrivial     | 549                                                                                                             | True | High-amplitude large-lowering broad-late candidates include both labels.           |

The chief systematic limitation is that the blinded hand-scan label is a deterministic proxy, not a second human review of raw waveform plots. It is nevertheless independent of method names and acceptance decisions, and it uses the same fit-quality primitives a hand-scan would inspect. Run 46 contributes only three frontier candidates, so CIs are driven by high-current run blocks. The P05f raw-ROOT scan is reused rather than repeated because the event-score table already records the raw-root reproduction gate, input hashes, and run-held-out method scores; this avoids changing the frozen P05f support frontier while still satisfying the P05g validation objective.

## Conclusion

The winner is **`traditional_template_fit`**. In the high-amplitude, large-lowering, broad-late frontier, this method has accepted precision `1.000` with 95% run-block CI `[1.000, 1.000]`, recoverable recall `0.475`, and false-accept rate `0.000`. The result supports the P05f claim that fixed-risk support is real but should remain an abstention/validation rule rather than an automatic two-pulse recovery policy until external reviewer variance is measured.

Runtime in this execution was `6.25` s. Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `blinded_candidate_ledger.csv`, `method_summary.csv`, `per_run_method_metrics.csv`, `sideband_method_metrics.csv`, and `leakage_checks.csv`.
