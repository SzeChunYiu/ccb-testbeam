# P02g: timing-tail label-source split for morphology RF

- **Ticket:** `1781042380.620.56983544`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-06-11
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one Sample-II analysis run out over `[58, 59, 60, 61, 62, 63, 65]`
- **Common support:** events where B2, B4, B6, and B8 all satisfy `A > 1000 ADC`
- **Winner recorded in `result.json`:** `ridge_all_stave`
- **Git commit at run time:** `f2c619d9bb69959f00f27227c90926f50cb7d28d`

## 1. Scientific Question

P02d/P02f showed that morphology scores are useful diagnostics, but the ticket asks a stricter source-split question: can a morphology RF signal for timing tails be decomposed into upstream pulse-shape information versus downstream label-source self-reference?  This matters because a score that mainly rereads the same downstream waveform used to define `D_t` should not be promoted as independent input to pile-up, PID, energy, or timing decisions.

The primary target is a fold-local template-phase downstream timing-tail label on B4/B6/B8.  The independent target is the same downstream span with CFD20 times.  The former tests the exact label source; the latter asks whether any score transfers to a timing definition not using the template-matching residual.

## 2. Raw-ROOT Reproduction Gate

The script reads the `HRDv` branch from every configured B-stack ROOT file, subtracts the median of samples 0-3, and counts selected B-stave pulses with

\[
I_{e,s} = \mathbf{1}\left[\max_t(x_{e,s,t} - \mathrm{median}(x_{e,s,0:3})) > 1000\,\mathrm{ADC}\right].
\]

| quantity | report_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | yes |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | 0 | yes |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | 0 | yes |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | 0 | yes |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | 0 | yes |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | 0 | yes |

The input hash table records `33` ROOT files in `input_sha256.csv`.  The source-split support is intentionally smaller than the selected-pulse table because all four B staves must be selected in the same event:

| run | raw_events | events_downstream_all_selected | events_all_four_selected |
| --- | --- | --- | --- |
| 58 | 34141 | 73 | 72 |
| 59 | 42303 | 763 | 749 |
| 60 | 36074 | 808 | 802 |
| 61 | 36535 | 933 | 925 |
| 62 | 37584 | 807 | 798 |
| 63 | 37030 | 370 | 365 |
| 65 | 38424 | 66 | 63 |

## 3. Timing Labels

For each leave-one-run-out fold, templates are built only from the training runs.  For downstream stave `s`, the normalized pulse `u_{e,s}` is compared with shifted train templates `T_s(\tau)`, and the phase time is

\[
\hat t^{\mathrm{tpl}}_{e,s} = 10\,\mathrm{ns}\left[t_{0.2}(T_s) + \arg\min_{\tau\in[-1.5,1.5]} \sum_t \left(u_{e,s,t} - T_s(t-\tau)\right)^2\right].
\]

Geometry-corrected times subtract `0.078 ns/cm` times the stave position.  The primary label is

\[
y_e = \mathbf{1}\left[\max_s \tilde t^{\mathrm{tpl}}_{e,s} - \min_s \tilde t^{\mathrm{tpl}}_{e,s} > 3.0\,\mathrm{ns}\right],
\]

and the independent label replaces `template_phase` with CFD20.  No model receives either span, pair residual, event id, event number, run id, or label.

Held-out label support:

| run | n_events | template_tails | template_tail_fraction | cfd20_tails | cfd20_tail_fraction | early_atoms | anomaly_atoms |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 58.0 | 72.0 | 69.0 | 0.958 | 61.0 | 0.847 | 8.0 | 25.0 |
| 59.0 | 749.0 | 713.0 | 0.952 | 637.0 | 0.850 | 93.0 | 83.0 |
| 60.0 | 802.0 | 769.0 | 0.959 | 658.0 | 0.820 | 118.0 | 128.0 |
| 61.0 | 925.0 | 757.0 | 0.818 | 709.0 | 0.766 | 116.0 | 130.0 |
| 62.0 | 798.0 | 775.0 | 0.971 | 678.0 | 0.850 | 103.0 | 114.0 |
| 63.0 | 365.0 | 350.0 | 0.959 | 306.0 | 0.838 | 41.0 | 52.0 |
| 65.0 | 63.0 | 58.0 | 0.921 | 58.0 | 0.921 | 1.0 | 14.0 |

## 4. Methods

**Traditional comparators.**  Three transparent P02 scorecards use fixed morphology ingredients: template RMSE, early peak, positive tail fraction, secondary peak fraction, and width.  They differ only in information source: B2 upstream only, B4/B6/B8 downstream only, or all staves.  The raw score for stave `s` is

\[
r_s = \max\left(q_s/0.20,\ (5-p_s)_+/4,\ f^{tail}_s/0.50,\ f^{secondary}_s/0.35,\ w^{20}_s/10\right),
\]

and the event score is the maximum over the allowed staves.  It is calibrated to `[0,1]` with the train-run 1st and 99th percentiles only.

**ML and NN methods.**  The learned panel contains ridge-logistic regression, histogram gradient-boosted trees, an MLP, a 1D CNN over normalized waveforms, and ExtraTrees morphology variants.  The ExtraTrees source split is the new architecture for this ticket because it directly implements the RF/ExtraTrees upstream/downstream/all-stave/amplitude/phase-scrambled decomposition requested in the claim.  Phase-scrambled and shuffled-label arms are controls and are not eligible winners.

Every model is trained on six Sample-II runs and scored on the held-out run.  The fixed-efficiency operating point is set on train runs at 90% clean acceptance; held-out `tail_rejection_at_90_clean` is the fraction of true tails above that threshold.  Confidence intervals are run-block bootstrap intervals over held-out runs.

## 5. Results

Primary model summary:

| model | eligible | average_precision_ci | roc_auc_ci | independent_cfd20_average_precision_ci | tail_rejection_at_90_clean_ci | template_pair_sigma68_delta_ns_ci | early_peak_enrichment | anomaly_enrichment | support_drift_max_abs_run_flagged_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ridge_all_stave | True | 0.996 [0.991, 0.998] | 0.956 [0.941, 0.965] | 0.679 [0.649, 0.709] | 0.952 [0.930, 0.970] | -0.746 [-1.073, -0.500] | 1.10 | 1.08 | 0.116 |
| extra_trees_downstream_only | True | 0.992 [0.980, 0.998] | 0.912 [0.886, 0.955] | 0.701 [0.661, 0.741] | 1.000 [1.000, 1.000] | -1.628 [-1.857, -1.022] | 1.00 | 1.00 | 0.001 |
| gradient_boosted_trees_all_stave | True | 0.992 [0.981, 0.999] | 0.912 [0.890, 0.965] | 0.692 [0.653, 0.748] | 1.000 [1.000, 1.000] | -1.654 [-2.223, -1.502] | 1.00 | 1.00 | 0.004 |
| extra_trees_all_stave | True | 0.991 [0.980, 0.998] | 0.906 [0.879, 0.952] | 0.697 [0.660, 0.741] | 1.000 [1.000, 1.000] | n/a | 1.00 | 1.00 | 0.000 |
| cnn_all_stave | True | 0.989 [0.975, 0.997] | 0.893 [0.859, 0.930] | 0.686 [0.661, 0.711] | 0.829 [0.666, 0.937] | -0.341 [-0.626, -0.242] | 1.27 | 1.22 | 0.364 |
| mlp_all_stave | True | 0.969 [0.912, 0.997] | 0.698 [0.510, 0.934] | 0.726 [0.666, 0.764] | 0.630 [0.365, 0.881] | 0.158 [-0.303, 0.317] | 1.57 | 1.52 | 0.373 |
| extra_trees_upstream_only | True | 0.958 [0.932, 0.982] | 0.604 [0.597, 0.663] | 0.677 [0.636, 0.721] | 1.000 [0.999, 1.000] | 1.572 [1.423, 3.681] | 1.00 | 1.00 | 0.001 |
| traditional_downstream_p02_scorecard | True | 0.952 [0.904, 0.980] | 0.596 [0.550, 0.659] | 0.726 [0.704, 0.747] | 0.219 [0.189, 0.251] | 0.042 [0.000, 0.141] | 2.72 | 3.25 | 0.192 |
| traditional_all_stave_p02_scorecard | True | 0.946 [0.902, 0.980] | 0.574 [0.545, 0.659] | 0.722 [0.696, 0.752] | 0.211 [0.193, 0.241] | 0.042 [0.000, 0.149] | 2.86 | 3.37 | 0.186 |
| traditional_upstream_p02_scorecard | True | 0.942 [0.896, 0.981] | 0.550 [0.519, 0.665] | 0.731 [0.698, 0.780] | 0.228 [0.169, 0.275] | 0.103 [0.000, 0.170] | 2.41 | 2.53 | 0.078 |
| extra_trees_amplitude_only | True | 0.931 [0.886, 0.977] | 0.517 [0.483, 0.631] | 0.753 [0.717, 0.807] | 0.987 [0.974, 0.996] | -0.113 [-0.367, 0.304] | 1.00 | 1.00 | 0.020 |
| extra_trees_phase_scrambled_control | False | 0.991 [0.980, 0.998] | 0.901 [0.878, 0.949] | 0.694 [0.654, 0.743] | 1.000 [1.000, 1.000] | n/a | 1.00 | 1.00 | 0.000 |
| cnn_phase_scrambled_control | False | 0.985 [0.971, 0.993] | 0.845 [0.812, 0.864] | 0.670 [0.637, 0.701] | 0.674 [0.586, 0.756] | -0.069 [-0.160, 0.250] | 1.56 | 1.52 | 0.297 |
| extra_trees_shuffled_label_control | False | 0.916 [0.878, 0.965] | 0.422 [0.398, 0.526] | 0.786 [0.726, 0.872] | 0.059 [0.034, 0.081] | 0.028 [-0.006, 0.081] | 2.41 | 2.15 | 0.058 |

ML-minus-traditional deltas use `traditional_all_stave_p02_scorecard` as the strong transparent comparator:

| model | delta_average_precision_vs_traditional | delta_tail_rejection_vs_traditional | delta_sigma68_delta_ns_vs_traditional | is_control |
| --- | --- | --- | --- | --- |
| ridge_all_stave | 0.0499 | 0.7408 | -0.7884 | False |
| extra_trees_downstream_only | 0.0460 | 0.7886 | -1.6700 | False |
| gradient_boosted_trees_all_stave | 0.0456 | 0.7886 | -1.6958 | False |
| extra_trees_all_stave | 0.0455 | 0.7886 | n/a | False |
| extra_trees_phase_scrambled_control | 0.0450 | 0.7886 | n/a | True |
| cnn_all_stave | 0.0430 | 0.6179 | -0.3834 | False |
| cnn_phase_scrambled_control | 0.0393 | 0.4629 | -0.1114 | True |
| mlp_all_stave | 0.0233 | 0.4185 | 0.1159 | False |
| extra_trees_upstream_only | 0.0122 | 0.7883 | 1.5294 | False |
| traditional_downstream_p02_scorecard | 0.0064 | 0.0072 | 0.0000 | False |
| traditional_upstream_p02_scorecard | -0.0037 | 0.0169 | 0.0607 | False |
| extra_trees_amplitude_only | -0.0153 | 0.7754 | -0.1555 | False |

The winner `ridge_all_stave` has AP 0.996 [0.991, 0.998], independent CFD20 AP 0.679 [0.649, 0.709], and template-pair sigma68 delta -0.746 [-1.073, -0.500].  The all-stave traditional comparator has AP 0.946 [0.902, 0.980] and sigma68 delta 0.042 [0.000, 0.149].  Negative sigma68 deltas mean the accepted sample is narrower than the no-veto sample.

## 6. Source-Split Interpretation

Upstream-only performance estimates how much timing-tail information is available before reading the downstream waveform used to define the label.  Downstream-only and all-stave performance quantify the possible self-reference channel.  A model that wins only in the downstream/all-stave arms but fails to transfer to CFD20 is interpreted as a label-source diagnostic, not as an independent morphology correction.

Early-peak and anomaly preservation is tracked by enrichment among flagged events.  Values greater than one indicate that the score still concentrates the intended P02 atoms rather than only selecting high-amplitude or run-specific support.  Support drift is the maximum absolute run-level flagged-fraction shift from the pooled flagged fraction.

## 7. Leakage and Systematics

| check | value | pass |
| --- | --- | --- |
| claim_command_ran_once_for_this_thread | 1781042380.620.56983544 | yes |
| loro_train_heldout_run_overlap_zero | 0 | yes |
| feature_audit_forbidden_overlap_zero | 0 | yes |
| primary_label_fold_local_template_phase_only | D_t(template_phase)>3 ns on held-out run | yes |
| independent_cfd20_label_reported | 1 | yes |
| phase_scrambled_and_shuffled_controls_present | 1 | yes |
| all_models_have_oof_scores | 1 | yes |
| rounded_waveform_hash_cross_run_duplicates_reported | 0 | yes |

Main systematics:

1. **Common-support restriction.**  Requiring B2/B4/B6/B8 all selected removes many low-amplitude or missing-downstream events, so the result is a source-split stress test rather than a complete P02 production classifier.
2. **Timing-label self-reference.**  Template-phase tails are built from the same downstream waveforms supplied to downstream/all-stave models.  The upstream-only and CFD20-transfer columns are therefore essential for interpretation.
3. **Run-block uncertainty.**  Only seven Sample-II analysis runs exist.  Bootstrap CIs respect run grouping but cannot create missing current/support regimes.
4. **Scorecard thresholds.**  The traditional scorecard denominators are fixed morphology scales, not optimized thresholds.  Its role is transparency and leakage resistance, not maximal AP tuning.
5. **Control semantics.**  Phase scrambling preserves amplitude distributions and some marginal sample values; it is a negative control for pulse phase, not a proof of zero information.

## 8. Verdict

The benchmark winner is `ridge_all_stave`.  The physics-facing conclusion should be read through the source split: if downstream/all-stave methods dominate upstream-only and phase-scrambled controls, the morphology RF signal is mostly a downstream label-source diagnostic.  Independent promotion requires comparable upstream or CFD20-transfer performance with stable support drift.

Runtime: `318.66 s` on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid`.
