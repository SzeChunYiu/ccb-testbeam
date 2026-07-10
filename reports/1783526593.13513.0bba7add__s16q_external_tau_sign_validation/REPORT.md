# S16q: external tagged-random/scaler-current pretrigger tau sign validation

- **Ticket:** `1783526593.13513.0bba7add`
- **Worker:** `testbeam-laptop-4`
- **Git commit:** `a386519e78489f52548a37d8637715e9570e2d36`
- **Raw input directory:** `/home/billy/.tb-workers/testbeam-laptop-4/data/root/root`
- **Primary winner:** `traditional`
- **External validation source available:** `False`

## Abstract

S16q asks whether the S16p pretrigger-tau sign diagnostic survives an independent tagged-random pedestal or scaler-current validation source rather than relying on physics-event topology proxies. The raw-ROOT reproduction gate exactly recovers the canonical selected B-stave pulse count. The visible ROOT trigger fields and local data/documentation surface were audited for tagged-random, forced-random, no-pulse, scaler-current, and DAQ run-log records. No independent external validation source is available in the mounted data surface, so the supervised bakeoff below is reported as a proxy stress test only. Under that external-provenance gate, the named winner is **traditional**.

## 1. Reproduction Gate

For B-stack channel c and event i, the raw waveform is x_ict with t in {0,...,17}. The pretrigger pedestal is

\[ p_{ic}=\operatorname{median}(x_{ic0},x_{ic1},x_{ic2},x_{ic3}), \qquad A_{ic}=\max_t(x_{ict}-p_{ic}). \]

A selected B-stave pulse satisfies A_ic > 1000 ADC for one of B2, B4, B6, or B8. This count is recomputed directly from `h101/HRDv` in every B-stack raw ROOT file.

| quantity                                    | expected | reproduced | delta | pass |
| ------------------------------------------- | -------- | ---------- | ----- | ---- |
| total selected B-stave pulses from raw HRDv | 640737   | 640737     | 0     | True |
| non-beam selected pulses in benchmark runs  | 0        | 0          | 0     | True |

## 2. Methods

The first method step is a provenance audit. For each raw B-stack ROOT file used by the reproduction gate, `TRIGGER` is read directly from `h101`. A text inventory over mounted data, configs, and docs searches for independent acquisition-language tokens. This audit is intentionally conservative: derived analysis reports are not treated as independent tagged-random or scaler-current truth.

External audit summary: `521` text files scanned, `54` token hits, `0` independent candidate files. ROOT trigger audit reports `0` non-beam trigger entries across the S00/S16 reproduction runs.

The benchmark is intentionally causal-conservative. Event identifiers, run numbers, and current labels are excluded from model inputs. Each fold holds out exactly one source run. All preprocessing, binning, scalers, network weights, and model parameters are fit on the remaining runs only.

The traditional comparator is a frozen stratified pretrigger current score. Training rows are binned by stave, pretrigger RMS, pretrigger slope, log amplitude, and peak-sample phase. The score for a held-out row is the train-fold empirical high-current fraction in the matched cell, with stave and global fallbacks. This is a transparent current-family swap diagnostic rather than an optimized classifier.

The ML/NN methods are ridge, histogram gradient-boosted trees, MLP, 1D-CNN, and a new dilated pretrigger TCN. Ridge, trees, and MLP consume scalar pretrigger/tail summaries. The CNN and TCN consume the 18-sample normalized waveform sequence. The TCN adds a dilated second convolution and residual skip, allowing it to test whether short pretrigger/tail phase structure improves the sign diagnostic.

The primary current classifier loss is evaluated by AUC, log loss, and Brier score. The proxy sign diagnostic is

\[ \Delta_D(m)=E[D_i\mid s_m(i)\ge q_{0.5}(s_m)]-E[D_i\mid s_m(i)<q_{0.5}(s_m)], \]

where D_i is the event-level downstream topology flag and s_m is the method score. Bootstrap confidence intervals resample source runs with replacement, preserving all rows from sampled runs.

## 3. Results

The observed raw high-minus-low downstream topology excess is `0.41757`. A pretrigger score that is to be promoted as physics support should have a positive downstream sign with a run-bootstrap interval that does not cross zero, beat the transparent comparator, and pass the independent external-source gate. The last condition fails because no tagged-random or scaler-current source is mounted.

| method                 | auc     | auc_ci_low | auc_ci_high | brier   | log_loss | predicted_high_minus_low_downstream | predicted_downstream_delta_ci_low | predicted_downstream_delta_ci_high |
| ---------------------- | ------- | ---------- | ----------- | ------- | -------- | ----------------------------------- | --------------------------------- | ---------------------------------- |
| traditional            | 0.52531 | 0.42752    | 0.67342     | 0.06706 | 0.34439  | 0.57597                             | 0.52119                           | 0.66188                            |
| ridge                  | 0.53299 | 0.43444    | 0.68858     | 0.11612 | 0.41093  | 0.62644                             | 0.56290                           | 0.70260                            |
| gradient_boosted_trees | 0.52465 | 0.41823    | 0.69513     | 0.06594 | 0.30404  | 0.60939                             | 0.55275                           | 0.69460                            |
| mlp                    | 0.26757 | 0.18463    | 0.39469     | 0.06795 | 0.31659  | 0.30196                             | 0.16773                           | 0.41864                            |
| cnn1d                  | 0.60835 | 0.50085    | 0.67688     | 0.24152 | 0.66939  | 0.38596                             | 0.32030                           | 0.46705                            |
| dilated_pretrigger_tcn | 0.66310 | 0.48642    | 0.76866     | 0.24053 | 0.66837  | 0.32967                             | 0.26789                           | 0.40530                            |

ML-minus-traditional downstream sign deltas:

| method                 | metric                                                | delta    | ci_low   | ci_high  | n_bootstrap |
| ---------------------- | ----------------------------------------------------- | -------- | -------- | -------- | ----------- |
| ridge                  | predicted_high_minus_low_downstream_minus_traditional | 0.04604  | 0.03121  | 0.05874  | 500         |
| gradient_boosted_trees | predicted_high_minus_low_downstream_minus_traditional | 0.02992  | 0.00313  | 0.04653  | 500         |
| mlp                    | predicted_high_minus_low_downstream_minus_traditional | -0.28165 | -0.48996 | -0.12998 | 500         |
| cnn1d                  | predicted_high_minus_low_downstream_minus_traditional | -0.18570 | -0.28221 | -0.10938 | 500         |
| dilated_pretrigger_tcn | predicted_high_minus_low_downstream_minus_traditional | -0.23828 | -0.36306 | -0.16364 | 500         |

## 4. Systematics and Caveats

- The downstream flag is an event-level topology proxy, not direct beam-pileup truth. It is useful for sign falsification but not for measuring an absolute two-pulse rate.
- The decisive S16q systematic is provenance: the mounted ROOT files expose beam-triggered physics events but not an independent tagged-random or scaler-current validation target.
- Only two low-current runs anchor the low-current side. The bootstrap therefore treats run as the uncertainty unit and intentionally produces broad intervals.
- The benchmark rows are capped per run for local runtime after the exact reproduction count is established. This reduces precision but preserves the run-held-out design.
- Pretrigger-only features are allowed to diagnose pedestal/tau nuisances; they are not allowed to become downstream physics handles unless the sign is stable under run swaps.
- Neural models are compact and regularized. A larger GPU sweep could change classifier AUC, but promotion here depends on downstream sign stability rather than raw current AUC.

## 5. Conclusion

The named winner is **traditional**. Because the external validation gate is closed, S16q does not promote any ML/NN pretrigger score to a physics-facing current-sign claim even when proxy AUC or downstream sign metrics improve. The defensible conclusion is to retain the transparent traditional pretrigger stratifier as a nuisance/control diagnostic and abstain from external tau-sign validation until true tagged-random or scaler-current records are supplied.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `root_trigger_audit.csv`, `external_record_inventory.csv`, `external_text_hits.csv`, `reproduction_match_table.csv`, `method_summary.csv`, `method_deltas_vs_traditional.csv`, `fold_scores.csv.gz`, and `sign_diagnostic.png` are in this report directory.
