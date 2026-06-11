# P06e: dropout-phase timing irrecoverability frontier

- **Study ID:** P06e
- **Ticket:** `1781070978.431.052370d7`
- **Author:** testbeam-laptop-2
- **Date:** 2026-06-11
- **Depends on:** S00 raw selected-pulse gate; P04g dropout injection closure; P06d peak-phase coupling atlas
- **Input checksum(s):** see `input_sha256.csv` (33 raw ROOT files)
- **Git commit:** 129326a38be2e936b0fb3a710e5b4da5b066aace
- **Config:** `configs/p06e_1781070978_431_052370d7_dropout_phase_timing_frontier.json`

## 0. Question

At which 18-sample phase locations does an injected dropout make CFD20 timing unrecoverable, and does any learned waveform model beat a strong conventional interpolation/template repair on the same held-out runs?

## 1. Reproduction

Raw `h101/HRDv` B-stack files are read directly. For every configured run I subtract the median of samples 0-3, select physical B channels `B2/B4/B6/B8 = 0/2/4/6`, and count pulses with baseline-subtracted amplitude `A > 1000 ADC`.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|:---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | 0 | True |

## 2. Traditional Method

For pulse waveform \(x_i(t)\), clean CFD20 time is

\[
\hat t_i = t_0 + \frac{0.2 A_i - x_i(t_0)}{x_i(t_0+1)-x_i(t_0)}, \quad A_i=\max_t x_i(t),
\]

where \(t_0\) is the sample before first threshold crossing. A dropout mask \(m_i(t)\) sets selected samples to zero. The conventional candidate repairs are (i) local linear interpolation over masked samples and (ii) an amplitude/stave/peak-region template refit. The selected traditional baseline is not a strawman: for each dropout case the train-run sigma68 chooses the better conventional candidate, then run 64 supplies only a scalar median calibration offset.

Case-wise traditional choices from train runs:

| dropout_case | traditional_candidate |
| --- | --- |
| cfd_crossing_single | interpolation_cfd |
| early_tail_pair | interpolation_cfd |
| late_tail_pair | interpolation_cfd |
| leading_edge_pair | interpolation_cfd |
| peak_contiguous | template_refit_cfd |
| peak_single | interpolation_cfd |

## 3. ML Method

All ML methods receive only the corrupted waveform, the binary mask, and pre-registered scalar morphology available after corruption: observed amplitude/charge, observed peak, mask count/center, stave, and dropout case. The target is the clean CFD20 time in samples; reported errors multiply by the 10 ns sample period. No model receives event id, clean waveform samples, clean amplitude, held-out run labels, or clean timing residuals.

Models: ridge with grouped alpha CV; histogram gradient-boosted trees with grouped hyperparameter CV; an MLP with grouped hidden-size CV; a 1D-CNN over `[corrupted normalized waveform, mask]`; and a new phase-gated CNN whose convolutional latent is multiplicatively gated by dropout phase coordinates `(case, mask_count, mask_center)`. CNNs are deliberately small because this is a laptop-scale raw-data study.

Split: train groups are Sample I runs, run 64 is used only for scalar offset calibration, and held-out test groups are Sample II analysis runs 58-63 and 65. Bootstrap intervals resample whole held-out runs.

Grouped CV audit:

| method | alpha | max_leaf_nodes | learning_rate | l2_regularization | hidden | group_cv_mae_sample |
| --- | --- | --- | --- | --- | --- | --- |
| hist_gradient_boosted_trees | nan | 63 | 0.08 | 0.05 | nan | 0.08163 |
| hist_gradient_boosted_trees | nan | 63 | 0.08 | 0 | nan | 0.08166 |
| hist_gradient_boosted_trees | nan | 63 | 0.04 | 0.05 | nan | 0.08356 |
| hist_gradient_boosted_trees | nan | 63 | 0.04 | 0 | nan | 0.08379 |
| hist_gradient_boosted_trees | nan | 31 | 0.08 | 0.05 | nan | 0.09144 |
| hist_gradient_boosted_trees | nan | 31 | 0.08 | 0 | nan | 0.09166 |
| hist_gradient_boosted_trees | nan | 31 | 0.04 | 0.05 | nan | 0.09994 |
| hist_gradient_boosted_trees | nan | 31 | 0.04 | 0 | nan | 0.1 |
| hist_gradient_boosted_trees | nan | 15 | 0.08 | 0 | nan | 0.1109 |
| hist_gradient_boosted_trees | nan | 15 | 0.08 | 0.05 | nan | 0.1111 |
| hist_gradient_boosted_trees | nan | 15 | 0.04 | 0.05 | nan | 0.1261 |
| hist_gradient_boosted_trees | nan | 15 | 0.04 | 0 | nan | 0.1264 |
| mlp | nan | nan | nan | nan | (96, 48) | 0.1548 |
| mlp | nan | nan | nan | nan | (64,) | 0.2251 |
| ridge | 100 | nan | nan | nan | nan | 0.3626 |
| ridge | 10 | nan | nan | nan | nan | 0.3628 |
| ridge | 1 | nan | nan | nan | nan | 0.3635 |
| ridge | 0.1 | nan | nan | nan | nan | 0.3636 |

## 4. Head-to-head Benchmark

Primary metric is timing sigma68 on identical held-out injected rows. The table also reports full RMS and the fraction with `|error| > 10 ns`.

| method | family | n | sigma68_ns | ci_low | ci_high | full_rms_ns | bad_tail_frac |
| --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_phase_selected_template_interp | traditional | 16656 | 0.218 | 0.2021 | 0.2377 | 7.79 | 0.008646 |
| corrupted_cfd | sentinel | 16656 | 0.3004 | 0.2749 | 0.3211 | 9.043 | 0.09036 |
| hist_gradient_boosted_trees | ml | 16656 | 0.3535 | 0.3442 | 0.3604 | 3.842 | 0.01105 |
| phase_gated_cnn | new_architecture | 16656 | 0.9988 | 0.9654 | 1.033 | 5.419 | 0.02221 |
| one_dimensional_cnn | ml | 16656 | 1.081 | 1.039 | 1.117 | 5.688 | 0.0251 |
| mlp | ml | 16656 | 1.625 | 1.587 | 1.655 | 4.512 | 0.01813 |
| ridge | ml | 16656 | 3.628 | 3.524 | 3.717 | 6.78 | 0.04629 |
| mask_phase_only_ridge | sentinel | 16656 | 12.02 | 11.75 | 12.27 | 16.15 | 0.402 |
| shuffled_target_hgb | sentinel | 16656 | 30.32 | 29.15 | 31.55 | 41.78 | 0.6775 |

Winner by held-out sigma68 is **traditional_phase_selected_template_interp**: 0.218 ns with 95% CI [0.202, 0.238] versus traditional 0.218 ns. ML-minus-traditional phase harm example: not applicable.

Per-phase frontier for the traditional baseline, corrupted CFD sentinel, and winner:

| dropout_phase | dropout_case | method | n | sigma68_ns | full_rms_ns | bad_tail_frac |
| --- | --- | --- | --- | --- | --- | --- |
| leading_edge | cfd_crossing_single | traditional_phase_selected_template_interp | 2776 | 0.07574 | 0.9828 | 0 |
| leading_edge | cfd_crossing_single | corrupted_cfd | 2776 | 0.1657 | 4.927 | 0.1261 |
| leading_edge | leading_edge_pair | traditional_phase_selected_template_interp | 2776 | 0.8049 | 3.494 | 0.02378 |
| leading_edge | leading_edge_pair | corrupted_cfd | 2776 | 5.765 | 10.35 | 0.3862 |
| peak | peak_contiguous | traditional_phase_selected_template_interp | 2776 | 0.3391 | 9.223 | 0.007925 |
| peak | peak_contiguous | corrupted_cfd | 2776 | 0.4147 | 9.654 | 0.009006 |
| peak | peak_single | corrupted_cfd | 2776 | 0.1964 | 9.488 | 0.008646 |
| peak | peak_single | traditional_phase_selected_template_interp | 2776 | 0.1964 | 9.483 | 0.007925 |
| tail | early_tail_pair | corrupted_cfd | 2776 | 0 | 9.379 | 0.006124 |
| tail | early_tail_pair | traditional_phase_selected_template_interp | 2776 | 0 | 9.379 | 0.006124 |
| tail | late_tail_pair | corrupted_cfd | 2776 | 0 | 9.379 | 0.006124 |
| tail | late_tail_pair | traditional_phase_selected_template_interp | 2776 | 0 | 9.379 | 0.006124 |

ML-minus-traditional timing harm by dropout phase. Positive values mean the learned method is wider than the strong conventional baseline; negative values mean a learned method improves sigma68. The intervals are held-out-run bootstrap CIs.

| dropout_phase | dropout_case | method | delta_sigma68_vs_traditional_ns | ci_low | ci_high |
| --- | --- | --- | --- | --- | --- |
| leading_edge | cfd_crossing_single | hist_gradient_boosted_trees | 0.2551 | 0.207 | 0.2832 |
| leading_edge | cfd_crossing_single | phase_gated_cnn | 0.8621 | 0.835 | 0.8906 |
| leading_edge | cfd_crossing_single | one_dimensional_cnn | 0.9026 | 0.8907 | 0.9399 |
| leading_edge | cfd_crossing_single | mlp | 1.457 | 1.393 | 1.509 |
| leading_edge | cfd_crossing_single | ridge | 3.246 | 3.123 | 3.332 |
| leading_edge | leading_edge_pair | hist_gradient_boosted_trees | -0.1875 | -0.2449 | -0.1382 |
| leading_edge | leading_edge_pair | phase_gated_cnn | 1.021 | 0.868 | 1.124 |
| leading_edge | leading_edge_pair | one_dimensional_cnn | 1.202 | 1.109 | 1.295 |
| leading_edge | leading_edge_pair | mlp | 1.426 | 1.315 | 1.55 |
| leading_edge | leading_edge_pair | ridge | 3.843 | 3.738 | 3.955 |
| peak | peak_contiguous | hist_gradient_boosted_trees | 0.01789 | -0.01038 | 0.04989 |
| peak | peak_contiguous | phase_gated_cnn | 0.7316 | 0.6891 | 0.7782 |
| peak | peak_contiguous | one_dimensional_cnn | 0.8939 | 0.8425 | 0.9438 |
| peak | peak_contiguous | mlp | 1.215 | 1.19 | 1.253 |
| peak | peak_contiguous | ridge | 3.083 | 2.93 | 3.214 |
| peak | peak_single | hist_gradient_boosted_trees | 0.1237 | 0.1048 | 0.1457 |
| peak | peak_single | phase_gated_cnn | 0.7819 | 0.7212 | 0.8268 |
| peak | peak_single | one_dimensional_cnn | 0.9415 | 0.8656 | 0.988 |
| peak | peak_single | mlp | 1.417 | 1.329 | 1.504 |
| peak | peak_single | ridge | 3.294 | 3.098 | 3.41 |
| tail | early_tail_pair | hist_gradient_boosted_trees | 0.2955 | 0.2841 | 0.3089 |
| tail | early_tail_pair | phase_gated_cnn | 0.7502 | 0.7174 | 0.7887 |
| tail | early_tail_pair | one_dimensional_cnn | 0.8357 | 0.7833 | 0.88 |
| tail | early_tail_pair | mlp | 1.272 | 1.223 | 1.334 |
| tail | early_tail_pair | ridge | 3.427 | 3.317 | 3.513 |
| tail | late_tail_pair | hist_gradient_boosted_trees | 0.3146 | 0.3001 | 0.3237 |
| tail | late_tail_pair | phase_gated_cnn | 0.7372 | 0.6997 | 0.7703 |
| tail | late_tail_pair | one_dimensional_cnn | 0.7823 | 0.7395 | 0.8296 |
| tail | late_tail_pair | mlp | 1.557 | 1.502 | 1.642 |
| tail | late_tail_pair | ridge | 3.404 | 3.29 | 3.539 |

## 5. Falsification

Pre-registration copied from the ticket/config: primary metric is `held-out Sample-II analysis timing sigma68 of predicted clean CFD20 time after injected dropout, in ns`; significance level is `0.05`; the ML adoption rule requires a paired run-bootstrap delta versus traditional with a 95% CI below zero.

Falsification tests: shuffled-target HGB must not win; mask/phase-only ridge must not match the full waveform models; corrupted-CFD sentinel quantifies the no-repair baseline. Multiple comparisons cover five eligible learned/traditional model families and six dropout cases; phase claims are therefore interpreted as frontier diagnostics unless their uncertainty is separated from the traditional baseline.

| method | sigma68_ns | full_rms_ns | bad_tail_frac |
| --- | --- | --- | --- |
| corrupted_cfd | 0.3004 | 9.043 | 0.09036 |
| mask_phase_only_ridge | 12.02 | 16.15 | 0.402 |
| shuffled_target_hgb | 30.32 | 41.78 | 0.6775 |

## 6. Threats to Validity

- **Benchmark/selection:** the conventional baseline is case-wise train-selected between interpolation and template refit, so ML is not compared against a deliberately weak repair.
- **Data leakage:** the split is by run; calibration run 64 contributes only median offsets; event ids and clean targets are excluded from features; rows are injected after selecting clean raw pulses.
- **Metric misuse:** sigma68, full RMS, signed bias, and bad-tail fraction are all reported. There is no fitted Gaussian core or chi-square fit in this study, so chi-square/ndf is not applicable.
- **Post-hoc selection:** dropout cases, metrics, model families, and win rule are fixed in the config before running the benchmark. HGB/ridge/MLP tuning uses GroupKFold on training runs only.

Systematics: the dropout truth is injected, not observed electronics dropout; samples 0-3 are protected because they define the baseline; the CFD20 timing target is a software timing endpoint, not an external time-of-flight truth; low-support high-amplitude/late-peak strata can broaden run-bootstrap CIs.

## 7. Provenance Manifest

A machine-readable `manifest.json` records the command, commit, environment, seeds, input ROOT hashes, and output hashes. `input_sha256.csv` pins every raw ROOT input.

## 8. Findings & Next Steps

The raw S00 selected-pulse count is reproduced exactly from ROOT. The held-out winner is traditional_phase_selected_template_interp with sigma68 0.218 ns versus traditional 0.218 ns; delta 0 ns. Dropout recoverability is phase-conditioned: the per-case table separates leading-edge, peak, and tail masks and the abstention policy reports which cases remain below the configured 10 ns / 25% bad-tail irrecoverability frontier.

Recover-vs-veto phase policy using the configured irrecoverability thresholds:

| method | accepted_cases | abstention_coverage | post_abstention_sigma68_ns | post_abstention_bad_tail_frac |
| --- | --- | --- | --- | --- |
| traditional_phase_selected_template_interp | cfd_crossing_single,early_tail_pair,late_tail_pair,leading_edge_pair,peak_contiguous,peak_single | 1 | 0.218 | 0.008646 |
| hist_gradient_boosted_trees | cfd_crossing_single,early_tail_pair,late_tail_pair,leading_edge_pair,peak_contiguous,peak_single | 1 | 0.3535 | 0.01105 |
| phase_gated_cnn | cfd_crossing_single,early_tail_pair,late_tail_pair,leading_edge_pair,peak_contiguous,peak_single | 1 | 0.9988 | 0.02221 |
| one_dimensional_cnn | cfd_crossing_single,early_tail_pair,late_tail_pair,leading_edge_pair,peak_contiguous,peak_single | 1 | 1.081 | 0.0251 |
| mlp | cfd_crossing_single,early_tail_pair,late_tail_pair,leading_edge_pair,peak_contiguous,peak_single | 1 | 1.625 | 0.01813 |
| ridge | cfd_crossing_single,early_tail_pair,late_tail_pair,leading_edge_pair,peak_contiguous,peak_single | 1 | 3.628 | 0.04629 |
| corrupted_cfd | cfd_crossing_single,early_tail_pair,late_tail_pair,peak_contiguous,peak_single | 0.8333 | 0.2148 | 0.0312 |
| mask_phase_only_ridge | peak_single | 0.1667 | 7.739 | 0.2295 |
| shuffled_target_hgb |  | 0 | nan | nan |

Hypothesis: leading-edge and peak-adjacent dropouts remove threshold-crossing information, so recovery is only reliable where the mask leaves enough monotonic rising-edge support or the model can infer phase from amplitude/stave-specific shape priors. A consumer should therefore treat recovery as a phase-conditioned action, not as a universal waveform correction.

Proposed follow-up ticket: **P06f consumer-specific dropout veto utility**. Question: do P06e recoverable/unrecoverable phase bands improve downstream timing, charge, and pile-up consumers when the action is recover versus veto rather than always-correct? Expected information gain: converts the dropout-phase frontier into a consumer-specific decision rule and tests whether a phase-gated CNN correction harms any downstream metric under run-held-out bootstrap CIs.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p06e_1781070978_431_052370d7_dropout_phase_timing_frontier.py --config configs/p06e_1781070978_431_052370d7_dropout_phase_timing_frontier.json
```

Artifacts: `counts_by_run.csv`, `injection_counts.csv`, `method_metrics.csv`, `method_metrics_bootstrap_ci.csv`, `method_phase_metrics.csv`, `method_phase_delta_vs_traditional.csv`, `abstention_policy.csv`, figures, `result.json`, and `manifest.json`.
