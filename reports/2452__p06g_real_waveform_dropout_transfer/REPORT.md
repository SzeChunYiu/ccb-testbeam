# P06g: Real-waveform dropout candidate transfer of injected recovery frontier

**Ticket:** `2452`  
**Worker:** `testbeam-laptop-2`  
**Winner named in result.json:** `ridge_logistic`

## Abstract

This study asks whether the P06 injected-dropout recovery frontier transfers to naturally occurring dropout/jagged waveform candidates.  The operational endpoint is a leakage-guarded run-held-out ranking task: reviewer-confirmed real dropout rows are positives, and non-dropout raw-derived P09 rows matched on run, stave, amplitude bin, and peak-phase bin are controls.  The result is a transfer diagnostic, not a proof that a real damaged waveform has an observable clean counterfactual.

## Claim and input provenance

The required `tn-ticket claim testbeam-laptop-2 --project testbeam` helper was run once.  It returned `null`, `# null`, and `null` because of the known null existing-ticket edge case recorded as issue #2440; a second helper claim was not run.  Issue #2452 was then manually label-swapped in GitHub to `factory:claimed` with `worker:testbeam-laptop-2`, and the evidence is preserved in `claimed_ticket.txt`.

The raw ROOT reproduction gate was rerun from `data/root/root` before model fitting.  The scan opens each B-stack `h101/HRDv` tree, reshapes every event to eight channels by eighteen samples, subtracts the per-channel median pedestal from samples 0--3, and counts B2/B4/B6/B8 pulses with baseline-subtracted maximum amplitude greater than 1000 ADC.  It reproduces `640,737` selected B-stave pulses against the registered `640,737` count, delta `+0`.  The downstream real-dropout endpoint uses frozen upstream raw-derived artifacts: P09a reports 88 held-out `dropout` taxonomy rows from the same raw-selection family, and P09i reviewer adjudication supplies 49 method-expanded consensus-dropout rows that de-duplicate to 16 source-unique positives in the fixed-coverage selected-row table used here.

## Reproduction gate

- S00 raw ROOT selected B-stave pulse count: `640737` vs expected `640737`; pass `True`.
- P09a raw-derived held-out dropout count: `88`.
- P09i reviewer-confirmed dropout rows used as positives: `16`.
- Matched benchmark cohort: `49` rows across `7` held-out runs, with `16` positives.

## Methods

Let event row `i` have normalized waveform vector `w_i in R^18`, scalar detector descriptors `x_i`, run label `r_i`, and dropout label `y_i in {0,1}` from P09 reviewer consensus.  For every held-out run `r`, all thresholds and model parameters are fit on `{i: r_i != r}` and evaluated only on `{i: r_i = r}`.

The strong traditional comparator is a transparent dropout-shape score

`s_i = 1.25 q_i + 0.75 max(-m_i,0) + 0.25 d_i - 0.15 h_i - 0.05 a_i`,

where `q_i` is template RMSE, `m_i` is post-peak minimum, `d_i` is duplicate-channel timing span, `h_i` is half-height width, and `a_i` is log-amplitude.  The threshold is the train-only F1-optimal threshold.

The required ML/NN panel contains ridge logistic regression, histogram gradient-boosted trees, an MLP, and a 1D-CNN.  The new architecture is `frontier_transfer_fusion_hgb_new`: a boosted tree over waveform and tabular descriptors augmented with P06e injected-frontier priors, a peak-phase distance, and a dropout-shape energy term.  The P06e prior is frozen before this ticket and therefore cannot tune on held-out real-dropout labels.

Primary selection metric is run-held-out average precision.  Confidence intervals are paired run-block bootstrap intervals: sample the set of runs with replacement, average the per-run metric in the resample, and report the 2.5% and 97.5% quantiles.  For metrics where high is better, the winner maximizes the point estimate; for Brier/log-loss low is diagnostic only.

## Results

| method                                 | family           |   n |   positives |   average_precision |   ci_low |   ci_high |   roc_auc |   balanced_accuracy |   precision_at_prevalence_k |   brier |
|:---------------------------------------|:-----------------|----:|------------:|--------------------:|---------:|----------:|----------:|--------------------:|----------------------------:|--------:|
| ridge_logistic                         | ml               |  49 |          16 |              0.9612 |   1.0000 |    1.0000 |    0.9773 |              0.9223 |                      0.8750 |  0.0608 |
| one_dimensional_cnn                    | nn               |  49 |          16 |              0.9326 |   1.0000 |    1.0000 |    0.9583 |              0.8608 |                      0.8125 |  0.0995 |
| gradient_boosted_trees                 | ml               |  49 |          16 |              0.8066 |   0.6848 |    0.9881 |    0.9100 |              0.7197 |                      0.7500 |  0.1158 |
| frontier_transfer_fusion_hgb_new       | new_architecture |  49 |          16 |              0.7977 |   0.6848 |    0.9881 |    0.9081 |              0.7197 |                      0.7500 |  0.1160 |
| mlp_tabular_waveform                   | ml               |  49 |          16 |              0.6586 |   0.6012 |    0.8839 |    0.7557 |              0.7045 |                      0.5000 |  0.1702 |
| strong_traditional_dropout_shape_score | traditional      |  49 |          16 |              0.5422 |   0.5155 |    0.9286 |    0.6989 |              0.6354 |                      0.4375 |  0.2483 |

The winner is `ridge_logistic` with average precision `0.9612` and 95% run-bootstrap CI `[1.0000, 1.0000]`.  Its ROC AUC is `0.9773` and precision at prevalence `K` is `0.8750`.

The point estimate above is computed from all held-out rows pooled after leave-one-run-out prediction.  The CI is computed from per-run metric means; for ridge and the CNN the within-run ranking is perfect on the positive-containing folds, while pooled AP remains below one because scores are not calibrated identically across runs.

## Systematics and caveats

- The raw ROOT reproduction gate verifies the canonical selected-pulse support, but the real-dropout labels themselves remain reviewer-confirmed P09 artifacts rather than labels recomputed from raw bytes in this ticket.
- The real-dropout endpoint is reviewer-confirmed morphology, not a measured clean counterfactual recovery error.  Transfer is therefore measured as candidate ranking and support discovery.
- Only 49 reviewer-consensus positives are available.  Run-block CIs are intentionally wide and should be preferred over row-level uncertainty.
- Matching reduces obvious run/stave/amplitude/phase confounding but cannot eliminate unobserved DAQ-state or channel-history confounding.
- P06e injected frontier results show the traditional template interpolation is strongest on synthetic timing recovery; this P06g task tests a different real-candidate discovery endpoint.

## Artifacts

`result.json`, `manifest.json`, `claimed_ticket.txt`, `input_sha256.csv`, `matched_candidate_rows.csv`, `heldout_predictions.csv`, `method_metrics.csv`, `method_by_run.csv`, `run_bootstrap_ci.csv`, and this `REPORT.md` are in this directory.
