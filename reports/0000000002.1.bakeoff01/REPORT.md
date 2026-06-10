# Study report: BAKEOFF01 - systematic ML algorithm bake-off

- **Study ID:** BAKEOFF01
- **Ticket:** `0000000002.1.bakeoff01`
- **Author:** `testbeam-laptop-3`
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Config:** `configs/bakeoff01_0000000002_1_systematic_ml_bakeoff.yaml`
- **Git commit at run time:** `1fb7b41609dc2870f47b4abae5d74bdf8e985232`

## 0. Question

Which algorithm should be the recommended default for four canonical waveform tasks when all candidates use identical task features, run-held-out splits, run-split tuning, and bootstrap confidence intervals?

The four tasks are: (A) sub-sample timing residual regression; (B) duplicate-readout amplitude/charge closure; (C) injected two-pulse separation and time recovery; and (D) injected-truth tail/anomaly classification. The primary metrics are timing `sigma68` in ns, duplicate-readout fractional `res68`, two-pulse constituent-time RMS in ns, and anomaly ROC AUC.

## 1. Raw-ROOT reproduction gate

The S00 selected-pulse count was rebuilt directly from `HRDv` branches in the raw B-stack ROOT files before any architecture work.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

This reproduces the required `640,737` selected B-stave pulses exactly, including the Sample-II per-stave counts used by the downstream task splits.

## 2. Methods

### Timing task

For each selected event with B4, B6, and B8 pulses above threshold, a corrected time is formed as

`t'_{i,e,m}=t_{i,e,m}-x_i/v`,

where `x_i` is the downstream stave position and `v^{-1}=0.078 ns/cm`. The event-level residual target for an ML correction on pulse `i` is

`r_{i,e}=t'_{i,e,base} - (1/2) sum_{j != i} t'_{j,e,base}`.

The strong traditional baseline is the S03 analytic amplitude/timewalk correction on the template-phase pickoff. Ridge-on-CFD20 is included as the established ML reference. The fixed bake-off panel is ridge, ExtraTrees, HistGradientBoosting, MLP, 1D-CNN, plus small ResNet/TCN/attention/GRU exploratory architectures. New models predict only residuals left by the analytic baseline; no model receives run id, event id, event order, other-stave times, or the held-out target. Hyperparameters are selected by grouped run CV over runs 58-63, then evaluated once on run 65.

The analytic family selected `amp_only` with alpha `100.0`. The tabular feature vector has `26` same-pulse features.

The traditional timing pickoff scan reports robust width, full RMS, tail fraction, Gaussian core width, and `chi2/ndf`; these diagnostics guard against narrow-core-only claims.

| method         |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   core_sigma_ns |   chi2_ndf |
|:---------------|-------------:|--------------:|----------------------:|----------------:|-----------:|
| template_phase |      2.88915 |       2.57669 |             0.0505051 |        0.442691 |   3.21363  |
| cfd30          |      2.98823 |       2.76793 |             0.0808081 |        1.29089  |   1.0905   |
| cfd20          |      2.99339 |       2.74268 |             0.0656566 |        1.08025  |   0.915142 |
| cfd40          |      3.02634 |       2.92355 |             0.0909091 |        1.39293  |   1.13786  |
| cfd10          |      3.0629  |       2.86492 |             0.0353535 |        1.1495   |   1.54539  |
| cfd50          |      3.27331 |       3.10562 |             0.126263  |        1.54639  |   1.13066  |
| of_3_11        |      3.31858 |       2.98046 |             0.10101   |        1.51389  |   1.77231  |
| of_1_9         |      3.36225 |       3.15396 |             0.151515  |        2.508    |   1.54926  |
| of_2_10        |      3.54327 |       3.28412 |             0.151515  |        0.700111 |   1.35874  |
| le500          |      3.97263 |       4.01015 |             0.207071  |        2.09792  |   0.840647 |

### Amplitude/charge duplicate-readout task

For each selected even B-stave waveform `x_e` the independent target is the paired odd readout after sign inversion: amplitude `A_odd=max(-x_odd)` and charge `Q_odd=sum max(-x_odd,0)`. Models use only the even-channel waveform and even-channel shape summaries. The prediction target is fitted in log space and scored as fractional error

`epsilon=(hat y-y)/max(y,1)`,

with primary score `res68 = percentile_68(|epsilon|)`. Held-out runs are 57 and 65; all other configured runs are available for run-grouped CV and final training. The fixed panel is ridge, Huber, RandomForest, ExtraTrees, HistGradientBoosting, and MLP.

### Two-pulse task

Injected overlaps are constructed from empirical S01-style templates plus real residual pools. Train source runs are 58-61; held-out source runs are 63 and 65. The traditional method is the bounded two-pulse template fit: for each waveform it scans `t_1` shifts and discrete separations, solves amplitudes and baseline by least squares, and rejects solutions outside amplitude-ratio and baseline bounds.

ML/NN competitors are ridge/logistic, gradient-boosted trees, MLP, 1D-CNN, 1D-ResNet, TCN, attention, and GRU. Classifier heads estimate overlap probability; regression heads estimate `t1`, `t2`, `A1/max(A)`, and `A2/max(A)` on injected positives.

For the bounded template fit, the waveform noise covariance is not independently known, so an absolute `chi2/ndf` is not quoted as a calibrated goodness-of-fit. The comparable diagnostics are the one-pulse versus two-pulse SSE improvement, the constrained-fit failure rate, the full constituent-time error distribution, and the charge-error distribution.

### Tail/anomaly classification task

The injected-truth anomaly target reuses the same source-run split as the two-pulse task, but evaluates detection only: `y=1` for injected overlapping pulses and `y=0` for clean single-pulse controls. Features are waveform-shape summaries excluding injected delay, scale, run id, event id, and the truth label. The fixed panel is logistic regression, RandomForest, HistGradientBoosting, and MLP.

## 3. Architecture CV

Timing CV rows are grouped by run and score validation pairwise `sigma68`; the full table is `timing_architecture_cv.csv`.

| model                  |   sigma68_ns |
|:-----------------------|-------------:|
| extra_trees            |      1.13267 |
| gradient_boosted_trees |      1.15194 |
| tcn                    |      1.19255 |
| gradient_boosted_trees |      1.2047  |
| mlp                    |      1.21146 |
| mlp                    |      1.24091 |
| gru                    |      1.25828 |
| cnn                    |      1.25998 |
| resnet                 |      1.272   |
| attention              |      1.27625 |
| ridge                  |      1.33793 |
| ridge                  |      1.33999 |
| ridge                  |      1.34055 |

Two-pulse CV rows are grouped by source run and score detection/recovery on validation folds; the full table is `two_pulse_architecture_cv.csv`.

| model                  |   time_rms_ns |
|:-----------------------|--------------:|
| gradient_boosted_trees |       7.67647 |
| ridge                  |       9.25944 |
| mlp                    |      12.1062  |

Charge/duplicate-readout CV rows are grouped by run and score validation fractional `res68`; the full table is `charge_run_split_cv.csv`.

| target    | method                 |   res68_abs_frac |
|:----------|:-----------------------|-----------------:|
| amplitude | random_forest          |       0.00356552 |
| amplitude | extra_trees            |       0.00460505 |
| amplitude | huber                  |       0.00855713 |
| amplitude | hist_gradient_boosting |       0.00862321 |
| amplitude | ridge                  |       0.0323525  |
| amplitude | ridge                  |       0.0347814  |
| amplitude | ridge                  |       0.0350534  |
| amplitude | mlp                    |       0.0375329  |
| charge    | random_forest          |       0.00595357 |
| charge    | extra_trees            |       0.00680569 |
| charge    | hist_gradient_boosting |       0.0134798  |
| charge    | huber                  |       0.0155504  |
| charge    | mlp                    |       0.0403792  |
| charge    | ridge                  |       0.0543127  |
| charge    | ridge                  |       0.0557942  |
| charge    | ridge                  |       0.055992   |

Anomaly CV rows are grouped by source run and score validation ROC AUC; the full table is `anomaly_run_split_cv.csv`.

| method                 |   roc_auc |
|:-----------------------|----------:|
| random_forest          |  0.847869 |
| hist_gradient_boosting |  0.847869 |
| logistic               |  0.844683 |
| logistic               |  0.844028 |
| logistic               |  0.843085 |
| mlp                    |  0.82823  |

## 4. Held-out head-to-head

### Timing

| model                  |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   n_pair_residuals |   train_seconds |   n_parameters |
|:-----------------------|-------------:|---------:|----------:|--------------:|-------------------:|----------------:|---------------:|
| gradient_boosted_trees |      1.12663 | 0.834468 |   1.40617 |       1.19963 |                198 |       0.506745  |             26 |
| extra_trees            |      1.26276 | 0.958592 |   1.46318 |       1.2444  |                198 |       2.31598   |             26 |
| mlp                    |      1.26699 | 1.10125  |   1.56279 |       1.3247  |                198 |      48.6973    |           1664 |
| gru                    |      1.31381 | 1.05603  |   1.5677  |       1.36573 |                198 |       7.14896   |           1249 |
| attention              |      1.35081 | 1.06215  |   1.6217  |       1.39685 |                198 |       8.30515   |            425 |
| resnet                 |      1.35966 | 1.08504  |   1.63467 |       1.3825  |                198 |       2.89917   |            537 |
| cnn                    |      1.35966 | 1.06725  |   1.62386 |       1.39834 |                198 |       2.1533    |            337 |
| tcn                    |      1.36021 | 1.06517  |   1.62063 |       1.39764 |                198 |       2.46635   |            337 |
| ridge                  |      1.44284 | 1.18886  |   1.6448  |       1.41159 |                198 |       0.0362802 |             26 |
| analytic_timewalk      |      1.49464 | 1.29766  |   1.67284 |       1.69913 |                198 |     nan         |            nan |
| s02_ridge_cfd20        |      1.77781 | 1.46176  |   2.06093 |       1.71577 |                198 |     nan         |            nan |
| template_phase         |      2.88915 | 2.63915  |   3.27718 |       2.57669 |                198 |     nan         |            nan |
| cfd20                  |      2.99339 | 2.70997  |   3.41139 |       2.74268 |                198 |     nan         |            nan |

Winner by point estimate: `gradient_boosted_trees` with 1.127 [0.834, 1.406] ns. The analytic traditional baseline is 1.495 [1.298, 1.673] ns.

### Amplitude / charge closure

| target    | model                  |   res68_abs_frac |   res68_abs_frac_ci_low |   res68_abs_frac_ci_high |    rms_frac |   bias_median_frac |   within_10pct |   cv_res68_abs_frac |   train_seconds |
|:----------|:-----------------------|-----------------:|------------------------:|-------------------------:|------------:|-------------------:|---------------:|--------------------:|----------------:|
| amplitude | random_forest          |       0.00349561 |              0.00331238 |               0.00376629 |    0.16532  |       -2.21874e-05 |       0.961053 |          0.00356552 |       20.8328   |
| amplitude | extra_trees            |       0.00511687 |              0.00461756 |               0.00577515 |    0.154748 |       -0.000122207 |       0.964292 |          0.00460505 |        7.02597  |
| amplitude | hist_gradient_boosting |       0.0109725  |              0.0103217  |               0.0115583  |    0.142945 |        0.000338083 |       0.971702 |          0.00862321 |        8.49103  |
| amplitude | huber                  |       0.0178749  |              0.0175845  |               0.0180043  |   13.9929   |        1.98547e-05 |       0.910117 |          0.00855713 |        5.89623  |
| amplitude | mlp                    |       0.025896   |              0.0243666  |               0.0276797  |    0.167472 |        0.00296489  |       0.932941 |          0.0375329  |       71.4761   |
| amplitude | ridge                  |       0.0601874  |              0.0549602  |               0.0640574  |    0.997681 |        0.000861549 |       0.839334 |          0.0323525  |        0.393461 |
| charge    | random_forest          |       0.00710024 |              0.00673984 |               0.00752208 |    0.633288 |       -8.16845e-05 |       0.953867 |          0.00595357 |       20.6828   |
| charge    | extra_trees            |       0.00892688 |              0.00878401 |               0.00908285 |    0.576352 |        0.000525632 |       0.958223 |          0.00680569 |        6.66899  |
| charge    | hist_gradient_boosting |       0.0186796  |              0.0182552  |               0.0190729  |    0.555497 |        0.00113325  |       0.954165 |          0.0134798  |        8.67794  |
| charge    | huber                  |       0.0315371  |              0.0298417  |               0.0326725  | 2608.63     |        0.000257922 |       0.89001  |          0.0155504  |        2.17818  |
| charge    | mlp                    |       0.0389891  |              0.0380226  |               0.0398017  |    0.104867 |        0.0110088   |       0.905648 |          0.0403792  |       15.7957   |
| charge    | ridge                  |       0.09276    |              0.086901   |               0.0986928  |   25.6118   |       -0.00353446  |       0.704137 |          0.0543127  |        0.177838 |

Amplitude winner by point estimate: `random_forest` with fractional res68 0.003 [0.003, 0.004]. Charge winner by point estimate: `random_forest` with fractional res68 0.007 [0.007, 0.008].

### Two-pulse recovery

| model                    |   detection_ap |   time_rms_ns |   time_rms_ns_ci_low |   time_rms_ns_ci_high |   charge_fractional_bias |   charge_fractional_res68 |   failure_rate |   train_seconds |   n_parameters |
|:-------------------------|---------------:|--------------:|---------------------:|----------------------:|-------------------------:|--------------------------:|---------------:|----------------:|---------------:|
| gradient_boosted_trees   |       0.872367 |       6.99597 |              6.80059 |               7.17913 |              -0.00237585 |                 0.0709272 |       0.238095 |       1.0752    |            120 |
| ridge                    |       0.836695 |       9.48554 |              8.79211 |              10.2073  |              -0.0215198  |                 0.0805763 |       0.292857 |       0.0455506 |            125 |
| gru                      |       0.80427  |      11.4505  |             11.3485  |              11.5439  |              -0.0137027  |                 0.0879792 |       0.4      |       2.06995   |           1269 |
| mlp                      |       0.863795 |      11.5936  |             11.5301  |              11.6656  |              -0.0181685  |                 0.114898  |       0.27619  |       1.82115   |           2736 |
| resnet                   |       0.813117 |      11.595   |             11.151   |              12.0194  |              -0.0188777  |                 0.0962983 |       0.369048 |       0.980974  |            661 |
| constrained_template_fit |       0.75523  |      13.1524  |             12.9659  |              13.3352  |              -0.0149667  |                 0.0976382 |       0.169048 |     nan         |              0 |
| attention                |       0.728801 |      14.7231  |             14.4372  |              14.9991  |              -0.0056328  |                 0.108367  |       0.419048 |       1.59062   |            549 |
| cnn                      |       0.786477 |      14.8778  |             14.3311  |              15.4089  |              -0.0105459  |                 0.10448   |       0.330952 |       0.938689  |            461 |
| tcn                      |       0.798782 |      15.1528  |             14.8603  |              15.448   |              -0.00928969 |                 0.106522  |       0.328571 |       0.856694  |            461 |

Winner by point estimate: `gradient_boosted_trees` with 6.996 [6.801, 7.179] ns. The bounded template fit is 13.152 [12.966, 13.335] ns.

### Tail/anomaly classification

| model                  |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   average_precision_ci_low |   average_precision_ci_high |    brier |   cv_roc_auc |   train_seconds |
|:-----------------------|----------:|-----------------:|------------------:|--------------------:|---------------------------:|----------------------------:|---------:|-------------:|----------------:|
| hist_gradient_boosting |  0.868129 |         0.860884 |          0.87576  |            0.876477 |                   0.871844 |                    0.881875 | 0.156534 |     0.847869 |       0.295496  |
| random_forest          |  0.858243 |         0.847755 |          0.868617 |            0.872059 |                   0.860836 |                    0.883056 | 0.154411 |     0.847869 |       0.239525  |
| logistic               |  0.839076 |         0.833968 |          0.842766 |            0.839057 |                   0.839057 |                    0.842397 | 0.163839 |     0.844683 |       0.0258782 |
| mlp                    |  0.804065 |         0.79873  |          0.807982 |            0.806299 |                   0.797299 |                    0.817891 | 0.193815 |     0.82823  |       0.142653  |

Winner by point estimate: `hist_gradient_boosting` with ROC AUC 0.868 [0.861, 0.876].

## 5. Falsification and leakage controls

The result would have falsified a new-architecture claim if every non-MLP/CNN model had overlapped or underperformed the established MLP/CNN family and the analytic/template baselines by the preregistered metrics. The run split is the main leakage guard, and the feature audits below exclude identifiers and label-defining variables.

| check                            |   value | pass   | detail                                                                                                                               |
|:---------------------------------|--------:|:-------|:-------------------------------------------------------------------------------------------------------------------------------------|
| timing_train_heldout_run_overlap |       0 | True   | nan                                                                                                                                  |
| timing_feature_audit             |       0 | True   | same-pulse waveform, amplitude summaries, and stave one-hot only; no event id, run id, other-stave time, or held-out residual target |
| timing_target_base               |       0 | True   | ML models correct residuals left by the analytic_timewalk traditional baseline                                                       |

| check                            |   value | pass   | detail                                                                                                                 |
|:---------------------------------|--------:|:-------|:-----------------------------------------------------------------------------------------------------------------------|
| charge_train_heldout_run_overlap |       0 | True   | nan                                                                                                                    |
| charge_feature_audit             |       0 | True   | features are even-channel waveform and shape summaries only; odd-channel target samples, run id, and event id excluded |
| charge_raw_gate_total            |  640737 | True   | nan                                                                                                                    |

| check                               |   value | pass   | detail                                                                                      |
|:------------------------------------|--------:|:-------|:--------------------------------------------------------------------------------------------|
| two_pulse_train_heldout_run_overlap |       0 | True   | nan                                                                                         |
| two_pulse_truth_source              |       0 | True   | targets are injected from train/heldout source runs and do not use real beam pile-up labels |
| two_pulse_feature_audit             |       0 | True   | ML features are same-channel waveform summaries or normalized waveform samples only         |

| check                             |   value | pass   | detail                                                                                                       |
|:----------------------------------|--------:|:-------|:-------------------------------------------------------------------------------------------------------------|
| anomaly_train_heldout_run_overlap |     0   | True   | nan                                                                                                          |
| anomaly_feature_audit             |     0   | True   | features are normalized waveform shape summaries; label, injected delay/scale, run id, and event id excluded |
| anomaly_injected_truth_balance    |     0.5 | True   | nan                                                                                                          |

Multiple comparisons are handled conservatively in the conclusion: a method is named a point-estimate winner, but adoption is only claimed when the bootstrap interval and guard metrics are also favorable. This is an architecture screen, not a production calibration.

## 6. Systematics and caveats

- Timing labels are same-particle residual proxies, not external truth. A lower pairwise width can reflect better correction or residual coupling to the other staves.
- Duplicate-readout charge closure is an electronics cross-check, not an absolute deposited-energy calibration. Strong performance can partly reflect deterministic coupling between paired readout channels.
- Two-pulse labels are injected and template-like. Real high-current overlaps may contain baseline excursions, saturation, or topology not represented in this closure test.
- The anomaly-classification task shares the injected data generator with the two-pulse task, so its confidence intervals are not independent evidence for real beam pile-up.
- Bootstrap intervals resample held-out events or source runs, so they cover finite held-out statistics better than model-selection uncertainty.
- The ResNet/TCN/attention/GRU models are deliberately small laptop-safe architectures. A null result does not exclude larger models, but it does bound what a small architecture sweep can justify.

## 7. Verdict and hypothesis

Timing point-estimate winner is gradient_boosted_trees at 1.127 ns versus analytic_timewalk 1.495 ns. Duplicate-readout amplitude winner is random_forest at fractional res68 0.0035; charge winner is random_forest at 0.0071. Two-pulse point-estimate winner is gradient_boosted_trees at 6.996 ns versus constrained_template_fit 13.152 ns. Injected-truth anomaly winner is hist_gradient_boosting at ROC AUC 0.868. The winner named here is the held-out metric winner; adoption remains conditional on the failure-rate and leakage guards documented in REPORT.md.

Hypothesis: the dominant useful information for these 18-sample waveforms is local pulse-shape and amplitude structure already captured by strong analytic/template terms plus small tabular or convolutional models. Residual connections, attention, and recurrent memory add little because the waveform is short and phase-locked; they should only help if future tasks include longer windows or explicit pretrigger history.

## 8. Next experiment

A high-information follow-up is BAKEOFF02: run XGBoost/LightGBM and a compact transformer only on BAKEOFF01 tasks where the top tree/NN confidence intervals overlap. This directly tests whether the recommended default algorithm table is stable before it is cited by future studies.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/bakeoff01_0000000002_1_systematic_ml_bakeoff.py --config configs/bakeoff01_0000000002_1_systematic_ml_bakeoff.yaml
```

Runtime in this execution was `706.29` s. Machine-readable outputs include `result.json`, `manifest.json`, `timing_head_to_head.csv`, `charge_head_to_head.csv`, `two_pulse_head_to_head.csv`, `anomaly_head_to_head.csv`, and the matching run-split CV and prediction CSVs.
