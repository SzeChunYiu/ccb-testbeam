# S16p: pretrigger tau sign-inversion falsifier

- **Ticket:** `1781081181.768.455d705f`
- **Worker:** `testbeam-laptop-3`
- **Git commit:** `b8934e5358c09125709ede8039e9775b0a3dd972`
- **Raw input directory:** `/home/billy/.tb-workers/testbeam-laptop-3/data/root/root`
- **Primary winner:** `ridge`

## Abstract

S16p tests whether a pretrigger-only handle that tracks live-time and tail structure also carries the same sign as the real current/downstream topology excess, or whether the handle is a sign-flipped nuisance. The raw-ROOT reproduction gate exactly recovers the canonical selected B-stave pulse count. The benchmark uses run-held-out current-family folds over the S10 current convention: low-current runs 46 and 47 versus high-current runs 44, 45, and 48-57. The operational winner is **ridge** under the predeclared sign rule: it is the learned method whose downstream-sign improvement over the transparent comparator is positive under run-block bootstrap. This is a diagnostic victory, not a promotion of pretrigger current scores as standalone pile-up physics.

## 1. Reproduction Gate

For B-stack channel c and event i, the raw waveform is x_ict with t in {0,...,17}. The pretrigger pedestal is

\[ p_{ic}=\operatorname{median}(x_{ic0},x_{ic1},x_{ic2},x_{ic3}), \qquad A_{ic}=\max_t(x_{ict}-p_{ic}). \]

A selected B-stave pulse satisfies A_ic > 1000 ADC for one of B2, B4, B6, or B8. This count is recomputed directly from `h101/HRDv` in every B-stack raw ROOT file.

| quantity                                    | expected | reproduced | delta | pass |
| ------------------------------------------- | -------- | ---------- | ----- | ---- |
| total selected B-stave pulses from raw HRDv | 640737   | 640737     | 0     | True |
| non-beam selected pulses in benchmark runs  | 0        | 0          | 0     | True |

## 2. Methods

The benchmark is intentionally causal-conservative. Event identifiers, run numbers, and current labels are excluded from model inputs. Each fold holds out exactly one source run. All preprocessing, binning, scalers, network weights, and model parameters are fit on the remaining runs only.

The traditional comparator is a frozen stratified pretrigger current score. Training rows are binned by stave, pretrigger RMS, pretrigger slope, log amplitude, and peak-sample phase. The score for a held-out row is the train-fold empirical high-current fraction in the matched cell, with stave and global fallbacks. This is a transparent current-family swap diagnostic rather than an optimized classifier.

The ML/NN methods are ridge, histogram gradient-boosted trees, MLP, 1D-CNN, and a new dilated pretrigger TCN. Ridge, trees, and MLP consume scalar pretrigger/tail summaries. The CNN and TCN consume the 18-sample normalized waveform sequence. The TCN adds a dilated second convolution and residual skip, allowing it to test whether short pretrigger/tail phase structure improves the sign diagnostic.

The primary current classifier loss is evaluated by AUC, log loss, and Brier score. The physics sign diagnostic is

\[ \Delta_D(m)=E[D_i\mid s_m(i)\ge q_{0.5}(s_m)]-E[D_i\mid s_m(i)<q_{0.5}(s_m)], \]

where D_i is the event-level downstream topology flag and s_m is the method score. Bootstrap confidence intervals resample source runs with replacement, preserving all rows from sampled runs.

## 3. Results

The observed raw high-minus-low downstream topology excess is `0.41941`. A pretrigger score that is to be promoted as physics support should have a positive downstream sign with a run-bootstrap interval that does not cross zero and should beat the transparent comparator without a leakage warning.

| method                 | auc     | auc_ci_low | auc_ci_high | brier   | log_loss | predicted_high_minus_low_downstream | predicted_downstream_delta_ci_low | predicted_downstream_delta_ci_high |
| ---------------------- | ------- | ---------- | ----------- | ------- | -------- | ----------------------------------- | --------------------------------- | ---------------------------------- |
| traditional            | 0.50839 | 0.41326    | 0.65596     | 0.06761 | 0.34585  | 0.59384                             | 0.53878                           | 0.68064                            |
| ridge                  | 0.52249 | 0.41448    | 0.69016     | 0.11623 | 0.41124  | 0.63071                             | 0.56990                           | 0.74061                            |
| gradient_boosted_trees | 0.49712 | 0.37738    | 0.69181     | 0.06708 | 0.30980  | 0.62743                             | 0.56298                           | 0.71238                            |
| mlp                    | 0.33158 | 0.19919    | 0.55383     | 0.06786 | 0.30617  | 0.43030                             | 0.31238                           | 0.53115                            |
| cnn1d                  | 0.69597 | 0.60371    | 0.83009     | 0.23960 | 0.66618  | 0.44395                             | 0.35546                           | 0.53403                            |
| dilated_pretrigger_tcn | 0.63247 | 0.54298    | 0.74401     | 0.24254 | 0.67286  | 0.37444                             | 0.31347                           | 0.46551                            |

ML-minus-traditional downstream sign deltas:

| method                 | metric                                                | delta    | ci_low   | ci_high  | n_bootstrap |
| ---------------------- | ----------------------------------------------------- | -------- | -------- | -------- | ----------- |
| ridge                  | predicted_high_minus_low_downstream_minus_traditional | 0.03592  | 0.01365  | 0.06292  | 500         |
| gradient_boosted_trees | predicted_high_minus_low_downstream_minus_traditional | 0.03128  | 0.01795  | 0.04241  | 500         |
| mlp                    | predicted_high_minus_low_downstream_minus_traditional | -0.16524 | -0.31596 | -0.04706 | 500         |
| cnn1d                  | predicted_high_minus_low_downstream_minus_traditional | -0.15202 | -0.22083 | -0.07828 | 500         |
| dilated_pretrigger_tcn | predicted_high_minus_low_downstream_minus_traditional | -0.21278 | -0.26636 | -0.14767 | 500         |

## 4. Systematics and Caveats

- The downstream flag is an event-level topology proxy, not direct beam-pileup truth. It is useful for sign falsification but not for measuring an absolute two-pulse rate.
- Only two low-current runs anchor the low-current side. The bootstrap therefore treats run as the uncertainty unit and intentionally produces broad intervals.
- The benchmark rows are capped per run for local runtime after the exact reproduction count is established. This reduces precision but preserves the run-held-out design.
- Pretrigger-only features are allowed to diagnose pedestal/tau nuisances; they are not allowed to become downstream physics handles unless the sign is stable under run swaps.
- Neural models are compact and regularized. A larger GPU sweep could change classifier AUC, but promotion here depends on downstream sign stability rather than raw current AUC.

## 5. Conclusion

The named winner is **ridge**. Ridge gives the strongest accepted sign-stable improvement over the transparent pretrigger stratifier in this capped run-held-out benchmark. The result does not license a pretrigger score as direct pile-up truth: it should be carried as a nuisance/control axis for tau and live-time studies, with external tagged-random or scaler-current validation before physics promotion.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_summary.csv`, `method_deltas_vs_traditional.csv`, `fold_scores.csv.gz`, and `sign_diagnostic.png` are in this report directory.
