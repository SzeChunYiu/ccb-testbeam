# S13: Current-scaling and CWoLa weak-supervision bakeoff

- **Study ID:** S13
- **Ticket:** `2383`
- **Author:** `testbeam-laptop-1`
- **Date:** 2026-08-16
- **Depends on:** S00, S07, S10; cross-checks S13b (`reports/1781000867.546938.20f0173c`)
- **Input checksums:** `input_sha256.csv` in this report directory pins all 14 raw ROOT files.
- **Config:** `configs/ticket_2383_s13_current_scaling_cwola_bakeoff.json`

## 0. Question

Does weak supervision by beam-current runs add information beyond the raw current-dependent multi-stave rate comparison and a transparent current-scaling fit? The preregistered decision metric is held-out B2-event Brier score for downstream-topology probability, with ECE, AUC, and high-minus-low downstream-excess error as secondary calibration tests.

## 1. Reproduction from raw ROOT

The gate was reproduced before calibration by rereading the raw B-stack ROOT files for runs 44-57. Baselines are the median of samples 0-3, selected pulses satisfy amplitude > 1000 ADC in B2/B4/B6/B8, and topology is computed at event level. The ticket's raw current comparison is the fraction of selected events with at least two selected B-stack staves: low-current runs 46-47 reproduce 1.56%, high-current runs 44-45 and 48-57 reproduce 2.68%. The App. H weak-current classifier AUC is reproduced with the same two run-transfer folds used for the benchmark.

| quantity                                         |   report_value |    reproduced |        delta |   tolerance | pass   |
|:-------------------------------------------------|---------------:|--------------:|-------------:|------------:|:-------|
| App. H low-current raw multi-stave fraction (%)  |        1.56    |      1.55875  | -0.001247    |       0.015 | True   |
| App. H high-current raw multi-stave fraction (%) |        2.68    |      2.68063  |  0.000629596 |       0.015 | True   |
| S13b downstream-topology high/low ratio          |        1.44497 |      1.44497  |  0           |       1e-12 | True   |
| S13b events with selected B-stack pulse          |   243133       | 243133        |  0           |       0     | True   |
| S13b selected B-stack pulses                     |   252266       | 252266        |  0           |       0     | True   |
| App. H weak current classifier run-transfer AUC  |        0.676   |      0.662142 | -0.0138578   |       0.015 | True   |

## 2. Methods

Each event in the calibration dataset has a selected B2 pulse. The binary target is whether that same event also contains a selected downstream B-stack stave. Restricting to B2 avoids the trivial leakage that would occur if selected B4/B6/B8 pulses themselves were used to predict the downstream label. For pulse waveform \(x_i(t)\) with amplitude \(A_i=\max_t x_i(t)\), the normalized waveform is \(z_i(t)=x_i(t)/\max(A_i,1)\). Hand variables include \(\log A_i\), peak sample, area-over-peak, late and early fractions, negative-step count, and width above 10% and 20% of peak. A cross-fit CWoLa score \(s_i\) is trained only to distinguish high-current from low-current runs in the opposite run block, then frozen as a scalar calibration input.

The traditional method is a smoothed stratified estimator: training B2 events are binned in \(\log A\), area-over-peak, and width10, and each stratum probability is \(\hat p_g=(k_g+8\bar y)/(n_g+8)\). This is the strong non-ML baseline because it directly estimates topology rates in matched amplitude and shape strata without learning a black-box boundary.

The explicit current-scaling baseline fits the raw multi-stave fraction with \(f(I)=f_0+kI\), using binomial standard errors as WLS weights. With only the 2 nA and 20 nA current settings the fit has zero degrees of freedom, so it is a reproduction/calibration baseline rather than a goodness-of-fit test; it exactly encodes the reported 1.56% to 2.68% current rise.

|   current_nA |   events |   multi_stave_events |   fraction |       sigma |   fit_fraction |       f0 |    k_per_nA |       chi2 |   ndf |
|-------------:|---------:|---------------------:|-----------:|------------:|---------------:|---------:|------------:|-----------:|------:|
|            2 |     5838 |                   91 |  0.0155875 | 0.00162123  |      0.0155875 | 0.014341 | 0.000623265 | 2.7564e-27 |     0 |
|           20 |   237295 |                 6361 |  0.0268063 | 0.000331569 |      0.0268063 | 0.014341 | 0.000623265 | 2.7564e-27 |     0 |

ML/NN methods are ridge logistic regression, gradient-boosted trees, a tabular MLP, a 1D CNN over the normalized 18-sample waveform plus scalar variables, and a new hybrid CNN-score-gate architecture. The hybrid uses a scalar-dependent gate on convolutional waveform channels before concatenating the scalar tower, testing whether the CWoLa score is useful as a modulation variable rather than merely another feature. Controls are reported but excluded from winner selection: a topology-rate-only current-group control, a CWoLa-only ridge control, an amplitude-only ridge control, and a shuffled-current CWoLa control.

Run-block splits are S13b-compatible: `A_to_B` trains on low run 46 plus high runs 44,45,48-51 and tests on low run 47 plus high runs 52-57; `B_to_A` reverses that split. All reported intervals resample runs with replacement. Isotonic calibration is fit on training runs only. The 90% conformal residual width is also computed on training residuals and checked on held-out runs.

The main scoring equations are Brier score \(N^{-1}\sum_i (y_i-\hat p_i)^2\), calibration error \(\mathrm{ECE}=\sum_b n_b N^{-1}|\bar y_b-\bar p_b|\), and high-minus-low topology excess error \(|(\bar p_H-\bar p_L)-(\bar y_H-\bar y_L)|\).

## 3. Results

The candidate-method winner by preregistered Brier score is **traditional_stratified** with Brier **0.0249** [0.0175, 0.0307], ECE **0.0049**, and high-minus-low excess error **0.0161**. The traditional stratified baseline has Brier **0.0249** [0.0175, 0.0307] and excess error **0.0161**.

| method                       |     brier |   brier_ci_low |   brier_ci_high |   ece_10bin |      auc |   calibration_slope |   pred_high_minus_low_downstream |   true_high_minus_low_downstream |   abs_delta_error |
|:-----------------------------|----------:|---------------:|----------------:|------------:|---------:|--------------------:|---------------------------------:|---------------------------------:|------------------:|
| amplitude_only_ridge_control | 0.0246276 |      0.0185805 |       0.0312639 |  0.00657199 | 0.556549 |          0.549547   |                     -4.69979e-07 |                            0.018 |       0.0180005   |
| traditional_stratified       | 0.0248716 |      0.0174927 |       0.0307006 |  0.00489766 | 0.669964 |          0.315071   |                      0.00192563  |                            0.018 |       0.0160744   |
| topology_rate_only_control   | 0.0248842 |      0.0181882 |       0.0302452 |  0.00314286 | 0.493824 |          0.0839597  |                      0.0177778   |                            0.018 |       0.000222222 |
| ridge                        | 0.0249438 |      0.017422  |       0.0312545 |  0.00484358 | 0.57827  |          0.0854651  |                      0.00916     |                            0.018 |       0.00884     |
| cnn1d                        | 0.0249869 |      0.0182597 |       0.0301908 |  0.0043802  | 0.435969 |         -0.0291749  |                     -0.00117588  |                            0.018 |       0.0191759   |
| mlp                          | 0.0250302 |      0.0177973 |       0.0312878 |  0.00288565 | 0.417214 |         -0.200486   |                     -0.000525599 |                            0.018 |       0.0185256   |
| shuffled_current_control     | 0.0250613 |      0.0189349 |       0.0317542 |  0.00317869 | 0.461297 |          0.00644619 |                     -5.07143e-06 |                            0.018 |       0.0180051   |
| cwola_only_ridge_control     | 0.025244  |      0.0181651 |       0.0317337 |  0.00258947 | 0.473139 |         -0.0188255  |                      0.0059072   |                            0.018 |       0.0120928   |
| hybrid_cnn_score_gate        | 0.0255302 |      0.016965  |       0.0333818 |  0.00350776 | 0.434605 |         -0.120883   |                      0.000179838 |                            0.018 |       0.0178202   |
| gradient_boosted_trees       | 0.0304575 |      0.0238924 |       0.0371502 |  0.0296711  | 0.607343 |          0.173455   |                      0.00804187  |                            0.018 |       0.00995813  |

Control rows are diagnostic. The topology-rate-only control asks how much current-group topology prevalence alone can do; the amplitude-only control tests whether pulse height/support explains the bridge; the CWoLa-only control tests whether the frozen current score is sufficient; the shuffled-current control should not provide a stable bridge if the CWoLa current axis is meaningful.

## 4. Falsification and systematics

Pre-registration comes from the ticket: calibration slope/intercept, Brier/ECE to topology excess, high-over-low score ratio, downstream excess delta, stratum heterogeneity, and ML-minus-traditional calibration error with run-block bootstrap CIs. The falsifier is that a method whose CI fails to improve Brier or excess-error over the smoothed stratified estimator is not a useful calibration bridge, even if it has a higher AUC.

The dominant systematic is the two-run low-current support: each fold has only one low-current run, so the run bootstrap is intentionally conservative but cannot invent missing low-current diversity. A second systematic is weak-label semantics: downstream topology is a physics-facing rate handle, not truth for pile-up. Third, the CWoLa score is trained on current labels and can encode morphology drift; this study therefore treats it as an input to be calibrated, not as a probability.

No parametric physics fit is used, so a chi^2/ndf is not meaningful for the primary estimator; full score distributions are retained in `b2_event_predictions.csv`, and the reliability plot plus ECE table are the calibration diagnostics. The Brier-score CIs for the leading candidate methods overlap substantially, so the winner should be read as the best point-estimate calibration under this split, not as a decisive production prescription.

Threats to validity are: benchmark selection (the stratified estimator is intentionally strong but still has coarse bins), data leakage (guarded by run-disjoint folds and B2-only target construction), metric misuse (Brier/ECE measure topology-label calibration, not pile-up truth), and post-hoc selection (candidate methods are the preregistered family; controls are explicitly excluded from winner selection).

Leakage controls:

| fold   | check                   |   value | flag   | note                                                                                                   |
|:-------|:------------------------|--------:|:-------|:-------------------------------------------------------------------------------------------------------|
| A_to_B | train_test_run_overlap  |       0 | False  | Run split must be disjoint.                                                                            |
| A_to_B | forbidden_columns_used  |       0 | False  | Calibration features exclude run, event number, current labels, and downstream labels.                 |
| A_to_B | b2_only_topology_target |    1750 | False  | Only B2-selected events are modelled so selected downstream staves cannot trivially define the target. |
| B_to_A | train_test_run_overlap  |       0 | False  | Run split must be disjoint.                                                                            |
| B_to_A | forbidden_columns_used  |       0 | False  | Calibration features exclude run, event number, current labels, and downstream labels.                 |
| B_to_A | b2_only_topology_target |    1750 | False  | Only B2-selected events are modelled so selected downstream staves cannot trivially define the target. |

## 5. Interpretation

The benchmark does not promote the CWoLa score to a standalone pile-up probability. The best calibrated model is traditional_stratified; if it beats the traditional baseline, the gain should be read as a topology-calibration improvement on B2 support only. If the gain is small or the excess-error CI overlaps the traditional estimator, topology remains the stronger production handle and CWoLa remains a diagnostic morphology/current score.

The working hypothesis after this study is that topology calibration is mostly carried by amplitude/support and broad waveform shape rather than by the frozen CWoLa current score alone: the CWoLa-only control is near-null, while the best candidate and amplitude control are close in Brier. The next high-information test is to expand low-current support or construct stricter quiet-run matched strata; this directly tests whether the present ranking is robust or an artifact of having only runs 46 and 47 at low current.

Queued follow-up appended after completion: `#2422` `S13e: low-current support expansion for topology calibration`. Expected information gain: separates real topology-bridge performance from the dominant two-low-run support systematic.

## 6. Provenance manifest

`manifest.json` records the git commit, Python/platform versions, command, random seed, input hashes, and output hashes. The command below regenerates every table and figure in this directory.

## 7. Reproducibility

Regenerate with:

```bash
uv run --with uproot --with awkward --with numpy --with pandas --with scikit-learn --with tabulate --with matplotlib --with torch python scripts/ticket_2383_s13_current_scaling_cwola_bakeoff.py --config configs/ticket_2383_s13_current_scaling_cwola_bakeoff.json
```

Artifacts include `reproduction_match_table.csv`, `topology_by_run.csv`, `current_scaling_fit.csv`, `b2_event_predictions.csv`, `method_metrics.csv`, `bootstrap_metric_samples.csv`, `leakage_checks.csv`, `result.json`, `manifest.json`, and calibration figures.

Runtime: 18.9 s.
