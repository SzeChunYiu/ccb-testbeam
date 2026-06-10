# Study report: S19a - neural architecture sweep for waveform timing and two-pulse recovery

- **Study ID:** S19a
- **Ticket:** `0000000006.1.nnarch`
- **Author:** `testbeam-laptop-4`
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Config:** `configs/s19a_0000000006_1_nnarch_sweep.yaml`
- **Git commit at run time:** `878ce92758857e3bb1f49867c10133dd8651d6bc`

## 0. Question

Do architectures beyond the established MLP/CNN baselines improve two waveform tasks when evaluated by run-held-out bootstrap intervals: downstream same-particle timing residual correction and injected two-pulse decomposition?

The pre-registered primary timing metric is held-out run-65 pairwise corrected residual `sigma68` in ns. The pre-registered primary two-pulse metric is held-out constituent time RMS in ns, with failure rate and detection AP as adoption guards.

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

The strong traditional baseline is the S03 analytic amplitude/timewalk correction on the template-phase pickoff. Ridge-on-CFD20 is included as the established ML reference. New models predict only residuals left by the analytic baseline; no model receives run id, event id, event order, other-stave times, or the held-out target. Hyperparameters are selected by grouped run CV over runs 58-63, then evaluated once on run 65.

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

### Two-pulse task

Injected overlaps are constructed from empirical S01-style templates plus real residual pools. Train source runs are 58-61; held-out source runs are 63 and 65. The traditional method is the bounded two-pulse template fit: for each waveform it scans `t_1` shifts and discrete separations, solves amplitudes and baseline by least squares, and rejects solutions outside amplitude-ratio and baseline bounds.

ML/NN competitors are ridge/logistic, gradient-boosted trees, MLP, 1D-CNN, 1D-ResNet, TCN, attention, and GRU. Classifier heads estimate overlap probability; regression heads estimate `t1`, `t2`, `A1/max(A)`, and `A2/max(A)` on injected positives.

For the bounded template fit, the waveform noise covariance is not independently known, so an absolute `chi2/ndf` is not quoted as a calibrated goodness-of-fit. The comparable diagnostics are the one-pulse versus two-pulse SSE improvement, the constrained-fit failure rate, the full constituent-time error distribution, and the charge-error distribution.

## 3. Architecture CV

Timing CV rows are grouped by run and score validation pairwise `sigma68`; the full table is `timing_architecture_cv.csv`.

| model                  |   sigma68_ns |
|:-----------------------|-------------:|
| gradient_boosted_trees |      1.15194 |
| resnet                 |      1.19508 |
| gradient_boosted_trees |      1.2047  |
| gru                    |      1.21346 |
| mlp                    |      1.25917 |
| mlp                    |      1.26431 |
| tcn                    |      1.28628 |
| cnn                    |      1.29597 |
| attention              |      1.31115 |
| ridge                  |      1.33793 |
| ridge                  |      1.33999 |
| ridge                  |      1.34055 |

Two-pulse CV rows are grouped by source run and score detection/recovery on validation folds; the full table is `two_pulse_architecture_cv.csv`.

| model                  |   time_rms_ns |
|:-----------------------|--------------:|
| gradient_boosted_trees |       7.94713 |
| ridge                  |       9.25836 |
| mlp                    |      11.7446  |

## 4. Held-out head-to-head

### Timing

| model                  |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   n_pair_residuals |   train_seconds |   n_parameters |
|:-----------------------|-------------:|---------:|----------:|--------------:|-------------------:|----------------:|---------------:|
| mlp                    |      1.1761  |  1.02427 |   1.38588 |       1.30354 |                198 |      4.67844    |            832 |
| gru                    |      1.22467 |  1.01397 |   1.46165 |       1.30827 |                198 |      8.83888    |           1249 |
| gradient_boosted_trees |      1.25584 |  1.01215 |   1.43806 |       1.24164 |                198 |      0.632073   |             26 |
| resnet                 |      1.29893 |  1.08684 |   1.49713 |       1.3456  |                198 |      3.78053    |            537 |
| tcn                    |      1.3413  |  1.05389 |   1.56004 |       1.38084 |                198 |      3.06345    |            337 |
| cnn                    |      1.36263 |  1.0303  |   1.58158 |       1.3877  |                198 |      2.611      |            337 |
| attention              |      1.4349  |  1.07866 |   1.63244 |       1.42292 |                198 |     10.6471     |            425 |
| ridge                  |      1.44284 |  1.19553 |   1.63516 |       1.41159 |                198 |      0.00663328 |             26 |
| analytic_timewalk      |      1.49464 |  1.29865 |   1.66622 |       1.69913 |                198 |    nan          |            nan |
| s02_ridge_cfd20        |      1.77781 |  1.49266 |   2.07031 |       1.71577 |                198 |    nan          |            nan |
| template_phase         |      2.88915 |  2.63915 |   3.27718 |       2.57669 |                198 |    nan          |            nan |
| cfd20                  |      2.99339 |  2.6884  |   3.38857 |       2.74268 |                198 |    nan          |            nan |

Winner by point estimate: `mlp` with 1.176 [1.024, 1.386] ns. The analytic traditional baseline is 1.495 [1.299, 1.666] ns.

### Two-pulse recovery

| model                    |   detection_ap |   time_rms_ns |   time_rms_ns_ci_low |   time_rms_ns_ci_high |   charge_fractional_bias |   charge_fractional_res68 |   failure_rate |   train_seconds |   n_parameters |
|:-------------------------|---------------:|--------------:|---------------------:|----------------------:|-------------------------:|--------------------------:|---------------:|----------------:|---------------:|
| gradient_boosted_trees   |       0.853992 |       7.42493 |              7.4019  |               7.44758 |              -0.0102621  |                 0.0627639 |       0.304762 |       1.19652   |            120 |
| ridge                    |       0.839375 |       8.6596  |              7.88606 |               9.31395 |              -0.0222078  |                 0.0738297 |       0.32381  |       0.0931702 |            125 |
| mlp                      |       0.813625 |      10.4346  |             10.1885  |              10.6619  |              -0.0360515  |                 0.106251  |       0.32381  |       1.43139   |           2736 |
| gru                      |       0.760614 |      11.0588  |             10.5809  |              11.4826  |              -0.0257643  |                 0.0922996 |       0.340476 |       2.91216   |           1269 |
| cnn                      |       0.778702 |      13.2178  |             12.7041  |              13.7026  |               0.00371981 |                 0.0995785 |       0.288095 |       1.11622   |            461 |
| tcn                      |       0.725689 |      13.2479  |             12.7862  |              13.6646  |               0.0202778  |                 0.105404  |       0.314286 |       1.02579   |            461 |
| constrained_template_fit |       0.77469  |      13.8741  |             13.5149  |              14.2222  |              -0.0202215  |                 0.0958775 |       0.154762 |     nan         |              0 |
| attention                |       0.707497 |      13.985   |             13.5802  |              14.3428  |              -0.0169062  |                 0.103432  |       0.354762 |       1.84445   |            549 |
| resnet                   |       0.718764 |      14.4359  |             13.5498  |              15.1615  |              -0.052481   |                 0.100698  |       0.502381 |       1.13819   |            661 |

Winner by point estimate: `gradient_boosted_trees` with 7.425 [7.402, 7.448] ns. The bounded template fit is 13.874 [13.515, 14.222] ns.

## 5. Falsification and leakage controls

The result would have falsified a new-architecture claim if every non-MLP/CNN model had overlapped or underperformed the established MLP/CNN family and the analytic/template baselines by the preregistered metrics. The run split is the main leakage guard, and the feature audits below exclude identifiers and label-defining variables.

| check                            |   value | pass   | detail                                                                                                                               |
|:---------------------------------|--------:|:-------|:-------------------------------------------------------------------------------------------------------------------------------------|
| timing_train_heldout_run_overlap |       0 | True   | nan                                                                                                                                  |
| timing_feature_audit             |       0 | True   | same-pulse waveform, amplitude summaries, and stave one-hot only; no event id, run id, other-stave time, or held-out residual target |
| timing_target_base               |       0 | True   | ML models correct residuals left by the analytic_timewalk traditional baseline                                                       |

| check                               |   value | pass   | detail                                                                                      |
|:------------------------------------|--------:|:-------|:--------------------------------------------------------------------------------------------|
| two_pulse_train_heldout_run_overlap |       0 | True   | nan                                                                                         |
| two_pulse_truth_source              |       0 | True   | targets are injected from train/heldout source runs and do not use real beam pile-up labels |
| two_pulse_feature_audit             |       0 | True   | ML features are same-channel waveform summaries or normalized waveform samples only         |

Multiple comparisons are handled conservatively in the conclusion: a method is named a point-estimate winner, but adoption is only claimed when the bootstrap interval and guard metrics are also favorable. This is an architecture screen, not a production calibration.

## 6. Systematics and caveats

- Timing labels are same-particle residual proxies, not external truth. A lower pairwise width can reflect better correction or residual coupling to the other staves.
- Two-pulse labels are injected and template-like. Real high-current overlaps may contain baseline excursions, saturation, or topology not represented in this closure test.
- Bootstrap intervals resample held-out events or source runs, so they cover finite held-out statistics better than model-selection uncertainty.
- The ResNet/TCN/attention/GRU models are deliberately small laptop-safe architectures. A null result does not exclude larger models, but it does bound what a small architecture sweep can justify.

## 7. Verdict and hypothesis

Timing point-estimate winner is mlp at 1.176 ns versus analytic_timewalk 1.495 ns. Two-pulse point-estimate winner is gradient_boosted_trees at 7.425 ns versus constrained_template_fit 13.874 ns. The winner named here is the held-out metric winner; adoption remains conditional on the failure-rate and leakage guards documented in REPORT.md.

Hypothesis: the dominant useful information for these 18-sample waveforms is local pulse-shape and amplitude structure already captured by strong analytic/template terms plus small tabular or convolutional models. Residual connections, attention, and recurrent memory add little because the waveform is short and phase-locked; they should only help if future tasks include longer windows or explicit pretrigger history.

## 8. Next experiment

A high-information follow-up is to test support-preserving augmentation and ensembling only for the task where a neural model has favorable guard metrics. That directly answers whether current limits are architecture capacity or training-support coverage, without expanding the search blindly.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s19a_0000000006_1_nnarch_sweep.py --config configs/s19a_0000000006_1_nnarch_sweep.yaml
```

Runtime in this execution was `178.82` s. Machine-readable outputs include `result.json`, `manifest.json`, `timing_head_to_head.csv`, `two_pulse_head_to_head.csv`, `timing_architecture_cv.csv`, and `two_pulse_architecture_cv.csv`.
