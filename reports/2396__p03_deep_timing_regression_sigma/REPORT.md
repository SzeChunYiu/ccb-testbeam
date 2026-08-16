# Study report: P03-2396 - Deep timing regression and per-pulse sigma

- **Ticket:** #2396 `P03: Deep timing regression + per-pulse sigma`
- **Author:** testbeam-laptop-3
- **Date:** 2026-08-16
- **Git commit:** e911cfc59b772e150beb5dd2c080b020066a3bd4
- **Config:** `configs/p03_2396_deep_timing_regression_sigma.json`
- **Raw input:** `/home/billy/ccb-data/data/extracted/root/root`

## 0. Question

Does a waveform regressor improve same-particle downstream B-stack timing resolution over a strong non-ML pickoff baseline, and are the learned per-pulse sigmas calibrated enough to be scientifically useful?

The pre-registered primary metric is held-out-run pairwise `sigma68` of time-of-flight corrected residuals for B4-B6, B4-B8, and B6-B8 pairs. Lower is better. The secondary calibration metric is pair-pull full RMS using the predicted per-pulse sigma.

## 1. Reproduction from raw ROOT

The gate reproduces the S00 selected-pulse counts directly from `HRDv` branches in raw ROOT files using the median of samples 0-3 as baseline and `A > 1000 ADC` for the four B-stack channels.

| quantity                           | report_value | reproduced | delta | tolerance | pass |
| ---------------------------------- | ------------ | ---------- | ----- | --------- | ---- |
| total selected B-stave pulses      | 640737       | 640737     | 0     | 0         | True |
| sample_ii_analysis selected_pulses | 125096       | 125096     | 0     | 0         | True |
| sample_ii_analysis B2              | 88213        | 88213      | 0     | 0         | True |
| sample_ii_analysis B4              | 21229        | 21229      | 0     | 0         | True |
| sample_ii_analysis B6              | 11148        | 11148      | 0     | 0         | True |
| sample_ii_analysis B8              | 4506         | 4506       | 0     | 0         | True |

All rows pass exactly with zero tolerance, so the P03 benchmark proceeds.

## 2. Methods

For each run-held-out fold, the train set is the other six Sample-II analysis runs from `{58,59,60,61,62,63,65}`. Templates, model selection, scalers, and regressors are fit only on the training runs. Held-out events are never used for choosing hyperparameters.

Corrected times are compared after subtracting the nominal longitudinal time of flight,

`t'_{i,e,m} = t_{i,e,m} - x_i v^{-1}`, with `v^{-1}=0.078 ns cm^-1` and `x_i = {0,2,4} cm` for B4, B6, and B8.

The resolution estimator is

`sigma68(r) = (Q_84(r) - Q_16(r))/2`, where `r` is the pooled corrected pair residual. Full RMS, median bias, Gaussian-core sigma, chi2/ndf, and tail fraction beyond 5 ns are also reported.

Traditional methods: leading edge at 500 ADC, CFD fractions 0.10-0.50, template phase fit on a sub-sample grid, and optimal-filter linearized phase fits over windows [1,9], [2,10], [3,11], [4,12]. The strongest traditional method is selected inside each fold by the training-run `sigma68`.

ML/NN methods all correct the same CFD20 base time. The target for one pulse is its corrected base-time residual relative to the mean corrected base time of the two other downstream staves in the same event:

`y_{i,e} = (t_{i,e,base} - x_i v^{-1}) - mean_{j != i}(t_{j,e,base} - x_j v^{-1})`.

The fitted residual `f_theta(w_i, a_i, s_i)` is subtracted from CFD20. Ridge and gradient-boosted trees use normalized waveform samples plus log-amplitude, peak sample, area/peak, and stave one-hot features. MLP uses the same tabular feature vector. The 1D-CNN surrogate uses local three-sample convolutional filters, rectified filter maps, and pooled filter responses followed by a nonlinear MLP head; this keeps the convolutional inductive bias without a heavyweight GPU framework. The new architecture, `attention_pulse`, uses softmax attention moments over sample amplitude and position at three temperatures plus derivative samples; it is sensible here because the waveform has a short ordered sequence and timing should be represented by sample-position weighting rather than only pooled scalar features.

The neural estimators minimize squared residual loss through `MLPRegressor`; per-pulse sigma is estimated as the training-fold robust residual scale for each neural family,

`sigma_hat_m = max(sigma68(y - f_m(x)), 0.05 ns)`. This is weaker than a fully heteroskedastic neural head and is treated as a calibration diagnostic, not an adopted absolute uncertainty model.

## 3. Head-to-head benchmark

| method                 | family      | mean_sigma68_ns | fold_boot_ci_low_ns | fold_boot_ci_high_ns | mean_full_rms_ns | mean_pull_width |
| ---------------------- | ----------- | --------------- | ------------------- | -------------------- | ---------------- | --------------- |
| gradient_boosted_trees | ml_nn       | 1.73002         | 1.60144             | 1.88121              | 4.82182          |                 |
| ridge                  | ml_nn       | 1.97671         | 1.87815             | 2.12625              | 4.6421           |                 |
| mlp                    | ml_nn       | 2.06672         | 1.8703              | 2.25875              | 4.68177          | 2.78171         |
| attention_pulse        | ml_nn       | 2.09036         | 1.85209             | 2.38134              | 4.92771          | 2.87737         |
| cnn_1d                 | ml_nn       | 2.13474         | 1.88335             | 2.41253              | 5.08182          | 2.92415         |
| template_phase         | traditional | 2.82742         | 2.7019              | 2.92199              | 3.23895          |                 |
| cfd20                  | traditional | 3.13998         | 3.03738             | 3.24619              | 5.41508          |                 |

Per-fold primary metric:

| heldout_run | attention_pulse | cfd20   | cnn_1d  | gradient_boosted_trees | mlp     | ridge   | template_phase |
| ----------- | --------------- | ------- | ------- | ---------------------- | ------- | ------- | -------------- |
| 58          | 2.77313         | 3.11542 | 2.97937 | 1.71096                | 2.43215 | 1.96842 | 2.6428         |
| 59          | 1.97184         | 3.1882  | 1.87321 | 1.55794                | 1.77571 | 1.90405 | 3.00999        |
| 60          | 1.94634         | 3.13862 | 1.84547 | 1.61177                | 1.83077 | 1.85063 | 2.64458        |
| 61          | 2.13772         | 2.91217 | 2.36981 | 1.99652                | 2.42176 | 2.42339 | 2.70351        |
| 62          | 1.71482         | 3.22857 | 1.86113 | 1.71568                | 1.85531 | 1.9342  | 2.93245        |
| 63          | 1.74832         | 3.40351 | 1.74082 | 1.50005                | 1.73893 | 1.84806 | 2.96306        |
| 65          | 2.34032         | 2.99339 | 2.27339 | 2.01722                | 2.41245 | 1.9082  | 2.89555        |

Winner: `gradient_boosted_trees` with mean held-out sigma68 1.7300 ns (run-bootstrap 95% CI 1.6014-1.8812 ns). The best traditional baseline is `template_phase` at 2.8274 ns.

## 4. Systematics and falsification

Statistical uncertainty is estimated by nonparametric bootstrap within each held-out run for residual-level CIs and by bootstrap over the seven held-out runs for the method-level mean. The dominant systematics are the nominal 2 cm stave spacing, the fixed 0.078 ns/cm time-of-flight correction, amplitude-threshold selection, and target self-referencing through same-event residual labels. A spacing alternative of 4 cm is not used for the primary metric because the P03 ticket inherits the downstream single-stave timing convention used in S02/P03 prior work; changing it would shift all methods coherently but not validate the learned residual target.

The falsification rule was: the ML winner must improve over the best traditional method on the run-held-out mean `sigma68`, and the improvement must be larger than the bootstrap uncertainty of the method difference. If not, the conclusion is that waveform ML is not adopted for this timing observable.

Observed difference winner minus best traditional: -1.0974 ns. Multiple comparisons were controlled operationally by selecting hyperparameters inside each training fold and reporting all five ML/NN families plus all traditional candidates, not only the best neural result.

## 5. Caveats

The learned sigma is an internal residual uncertainty, not detector truth. Pull widths different from unity indicate that the heteroskedastic head is not yet an absolute per-pulse resolution model. The target is derived from other staves, so common-mode electronics jitter and event-level correlations are suppressed rather than measured. ROOT access is read-only, and no event-level random split is used.

## 6. Provenance

- Manifest: `reports/2396__p03_deep_timing_regression_sigma/manifest.json`
- Metrics: `reports/2396__p03_deep_timing_regression_sigma/method_summary.csv` and `reports/2396__p03_deep_timing_regression_sigma/fold_metrics.csv`
- Figures: `reports/2396__p03_deep_timing_regression_sigma/fig_runheldout_sigma68.png`, `reports/2396__p03_deep_timing_regression_sigma/fig_method_summary.png`
- Command: `uv run --extra root python scripts/p03_2396_deep_timing_regression_sigma.py --config configs/p03_2396_deep_timing_regression_sigma.json`

## 7. Findings and next step

The adopted result is `gradient_boosted_trees` if and only if `result.json` names it as winner and the raw reproduction gate passes. A useful follow-up is to calibrate the per-pulse sigma head against an independent two-ended timing residual or simulation truth, because the current pull-width test can diagnose miscalibration but cannot assign an absolute truth resolution to a single pulse.
