# S13d: CWoLa topology calibration bridge

- **Study ID:** S13d
- **Ticket:** `1781036493.3324.58306cd1`
- **Author:** `testbeam-laptop-4`
- **Date:** 2026-06-10
- **Depends on:** S13b (`reports/1781000867.546938.20f0173c`)
- **Input checksums:** `input_sha256.csv` in this report directory pins all 14 raw ROOT files.
- **Config:** `configs/s13d_1781036493_3324_58306cd1_cwola_topology_calibration_bridge.json`

## 0. Question

Can the S13b weakly supervised CWoLa current score be calibrated onto the downstream-topology current handle, or is it mainly a morphology-sensitive nuisance score? The preregistered decision metric is held-out B2-event Brier score for downstream-topology probability, with ECE and high-minus-low downstream-excess error as secondary calibration tests.

## 1. Reproduction from raw ROOT

The gate was reproduced before calibration by rereading the raw B-stack ROOT files for runs 44-57. Baselines are the median of samples 0-3, selected pulses satisfy amplitude > 1000 ADC in B2/B4/B6/B8, and topology is the fraction of selected events with any downstream selected stave (B4/B6/B8).

| quantity                                |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S13b downstream-topology high/low ratio |        1.44497 |      1.44497 |       0 |       1e-12 | True   |
| S13b events with selected B-stack pulse |   243133       | 243133       |       0 |       0     | True   |
| S13b selected B-stack pulses            |   252266       | 252266       |       0 |       0     | True   |

## 2. Methods

Each event in the calibration dataset has a selected B2 pulse. The binary target is whether that same event also contains a selected downstream B-stack stave. Restricting to B2 avoids the trivial leakage that would occur if selected B4/B6/B8 pulses themselves were used to predict the downstream label. For pulse waveform \(x_i(t)\) with amplitude \(A_i=\max_t x_i(t)\), the normalized waveform is \(z_i(t)=x_i(t)/\max(A_i,1)\). Hand variables include \(\log A_i\), peak sample, area-over-peak, late and early fractions, negative-step count, and width above 10% and 20% of peak. A cross-fit CWoLa score \(s_i\) is trained only to distinguish high-current from low-current runs in the opposite run block, then frozen as a scalar calibration input.

The traditional method is a smoothed stratified estimator: training B2 events are binned in \(\log A\), area-over-peak, and width10, and each stratum probability is \(\hat p_g=(k_g+8\bar y)/(n_g+8)\). This is the strong non-ML baseline because it directly estimates topology rates in matched amplitude and shape strata without learning a black-box boundary.

ML/NN methods are ridge logistic regression, gradient-boosted trees, a tabular MLP, a 1D CNN over the normalized 18-sample waveform plus scalar variables, and a new hybrid CNN-score-gate architecture. The hybrid uses a scalar-dependent gate on convolutional waveform channels before concatenating the scalar tower, testing whether the CWoLa score is useful as a modulation variable rather than merely another feature. Controls are reported but excluded from winner selection: a topology-rate-only current-group control, a CWoLa-only ridge control, an amplitude-only ridge control, and a shuffled-current CWoLa control.

Run-block splits are S13b-compatible: `A_to_B` trains on low run 46 plus high runs 44,45,48-51 and tests on low run 47 plus high runs 52-57; `B_to_A` reverses that split. All reported intervals resample runs with replacement. Isotonic calibration is fit on training runs only. The 90% conformal residual width is also computed on training residuals and checked on held-out runs.

The main scoring equations are Brier score \(N^{-1}\sum_i (y_i-\hat p_i)^2\), calibration error \(\mathrm{ECE}=\sum_b n_b N^{-1}|\bar y_b-\bar p_b|\), and high-minus-low topology excess error \(|(\bar p_H-\bar p_L)-(\bar y_H-\bar y_L)|\).

## 3. Results

The candidate-method winner by preregistered Brier score is **gradient_boosted_trees** with Brier **0.0240** [0.0188, 0.0293], ECE **0.0175**, and high-minus-low excess error **0.0081**. The traditional stratified baseline has Brier **0.0274** [0.0220, 0.0334] and excess error **0.0150**.

| method                       |     brier |   brier_ci_low |   brier_ci_high |   ece_10bin |      auc |   calibration_slope |   pred_high_minus_low_downstream |   true_high_minus_low_downstream |   abs_delta_error |
|:-----------------------------|----------:|---------------:|----------------:|------------:|---------:|--------------------:|---------------------------------:|---------------------------------:|------------------:|
| gradient_boosted_trees       | 0.0240454 |      0.0188406 |       0.0292735 | 0.0174515   | 0.794174 |           0.539997  |                      0.0057069   |                        0.0138172 |        0.00811031 |
| hybrid_cnn_score_gate        | 0.0254933 |      0.0206225 |       0.0303887 | 0.00185341  | 0.694317 |           0.780403  |                      0.00317574  |                        0.0138172 |        0.0106415  |
| cnn1d                        | 0.0257471 |      0.0204751 |       0.0309991 | 0.00142091  | 0.669327 |           0.895261  |                      0.00350442  |                        0.0138172 |        0.0103128  |
| ridge                        | 0.0258787 |      0.020704  |       0.0315118 | 0.00560487  | 0.734684 |           0.839187  |                      0.00565582  |                        0.0138172 |        0.00816139 |
| amplitude_only_ridge_control | 0.0261242 |      0.0209663 |       0.0319442 | 0.00153142  | 0.624643 |           0.899996  |                      0.00262741  |                        0.0138172 |        0.0111898  |
| mlp                          | 0.0264983 |      0.021089  |       0.0320534 | 0.00732547  | 0.698798 |           0.622787  |                     -0.000755121 |                        0.0138172 |        0.0145723  |
| traditional_stratified       | 0.0274114 |      0.0219661 |       0.0333969 | 0.00128549  | 0.671124 |           0.723043  |                     -0.00117084  |                        0.0138172 |        0.0149881  |
| shuffled_current_control     | 0.0276363 |      0.0214968 |       0.0336162 | 0.00102698  | 0.530072 |          -0.0181638 |                     -0.00769562  |                        0.0138172 |        0.0215128  |
| topology_rate_only_control   | 0.0277316 |      0.0218298 |       0.0338122 | 0.000317225 | 0.49618  |           0.354852  |                      0.0171772   |                        0.0138172 |        0.00335995 |
| cwola_only_ridge_control     | 0.0279513 |      0.0218404 |       0.0340004 | 0.000546649 | 0.49483  |           0.0413168 |                      0.00151299  |                        0.0138172 |        0.0123042  |

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
| A_to_B | b2_only_topology_target |   17500 | False  | Only B2-selected events are modelled so selected downstream staves cannot trivially define the target. |
| B_to_A | train_test_run_overlap  |       0 | False  | Run split must be disjoint.                                                                            |
| B_to_A | forbidden_columns_used  |       0 | False  | Calibration features exclude run, event number, current labels, and downstream labels.                 |
| B_to_A | b2_only_topology_target |   15059 | False  | Only B2-selected events are modelled so selected downstream staves cannot trivially define the target. |

## 5. Interpretation

The benchmark does not promote the CWoLa score to a standalone pile-up probability. The best calibrated model is gradient_boosted_trees; if it beats the traditional baseline, the gain should be read as a topology-calibration improvement on B2 support only. If the gain is small or the excess-error CI overlaps the traditional estimator, topology remains the stronger production handle and CWoLa remains a diagnostic morphology/current score.

The working hypothesis after this study is that topology calibration is mostly carried by amplitude/support and broad waveform shape rather than by the frozen CWoLa current score alone: the CWoLa-only control is near-null, while the best candidate and amplitude control are close in Brier. The next high-information test is to expand low-current support or construct stricter quiet-run matched strata; this directly tests whether the present ranking is robust or an artifact of having only runs 46 and 47 at low current.

Queued follow-up proposed in `result.json`: `S13e: low-current support expansion for topology calibration`. Expected information gain: separates real topology-bridge performance from the dominant two-low-run support systematic.

## 6. Provenance manifest

`manifest.json` records the git commit, Python/platform versions, command, random seed, input hashes, and output hashes. The command below regenerates every table and figure in this directory.

## 7. Reproducibility

Regenerate with:

```bash
/home/billy/anaconda3/bin/python scripts/s13d_1781036493_3324_58306cd1_cwola_topology_calibration_bridge.py --config configs/s13d_1781036493_3324_58306cd1_cwola_topology_calibration_bridge.json
```

Artifacts include `reproduction_match_table.csv`, `topology_by_run.csv`, `b2_event_predictions.csv`, `method_metrics.csv`, `bootstrap_metric_samples.csv`, `leakage_checks.csv`, `result.json`, `manifest.json`, and calibration figures.

Runtime: 329.4 s.
