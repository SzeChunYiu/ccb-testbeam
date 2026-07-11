# Study report: S19c - causal timing and pile-up deconvolution from waveform windows

- **Study ID:** S19c
- **Ticket:** `1783751737.13524.25796187`
- **Author:** `testbeam-laptop-1`
- **Date:** 2026-07-11
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Config:** `configs/s19c_1783751737_13524_25796187_causal_timing_pileup.yaml`
- **Git commit at run time:** `9a367a2f9aa2d7fd8c59f097923e312669be0556`

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
| mlp                    |      1.18404 |
| gradient_boosted_trees |      1.2047  |
| mlp                    |      1.21757 |
| gru                    |      1.25877 |
| attention              |      1.28658 |
| resnet                 |      1.29053 |
| tcn                    |      1.29198 |
| cnn                    |      1.29389 |
| ridge                  |      1.33793 |
| ridge                  |      1.33999 |
| ridge                  |      1.34055 |

Two-pulse CV rows are grouped by source run and score detection/recovery on validation folds; the full table is `two_pulse_architecture_cv.csv`.

| model                  |   time_rms_ns |
|:-----------------------|--------------:|
| gradient_boosted_trees |       8.35922 |
| ridge                  |       9.02888 |
| mlp                    |      12.5395  |

## 4. Held-out head-to-head

### Timing

| model                  |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   n_pair_residuals |   train_seconds |   n_parameters |
|:-----------------------|-------------:|---------:|----------:|--------------:|-------------------:|----------------:|---------------:|
| gru                    |      1.20177 | 1.02148  |   1.50668 |       1.31254 |                198 |      9.22147    |           1249 |
| gradient_boosted_trees |      1.21945 | 0.916927 |   1.47122 |       1.25105 |                198 |      0.630487   |             26 |
| mlp                    |      1.23077 | 1.03298  |   1.48064 |       1.28598 |                198 |      3.75052    |           1664 |
| tcn                    |      1.32215 | 1.04892  |   1.61369 |       1.36597 |                198 |      3.28781    |            337 |
| resnet                 |      1.34064 | 1.05665  |   1.58708 |       1.32942 |                198 |      3.77128    |            537 |
| cnn                    |      1.34473 | 1.0545   |   1.63215 |       1.37567 |                198 |      2.52392    |            337 |
| attention              |      1.40666 | 1.01717  |   1.63869 |       1.41069 |                198 |     10.5666     |            425 |
| ridge                  |      1.44284 | 1.14983  |   1.63308 |       1.41159 |                198 |      0.00819445 |             26 |
| analytic_timewalk      |      1.49464 | 1.32623  |   1.65491 |       1.69913 |                198 |    nan          |            nan |
| s02_ridge_cfd20        |      1.77781 | 1.50911  |   2.10407 |       1.71577 |                198 |    nan          |            nan |
| template_phase         |      2.88915 | 2.63915  |   3.27718 |       2.57669 |                198 |    nan          |            nan |
| cfd20                  |      2.99339 | 2.68921  |   3.41812 |       2.74268 |                198 |    nan          |            nan |

Winner by point estimate: `gru` with 1.202 [1.021, 1.507] ns. The analytic traditional baseline is 1.495 [1.326, 1.655] ns.

### Two-pulse recovery

| model                    |   detection_ap |   time_rms_ns |   time_rms_ns_ci_low |   time_rms_ns_ci_high |   charge_fractional_bias |   charge_fractional_res68 |   failure_rate |   train_seconds |   n_parameters |
|:-------------------------|---------------:|--------------:|---------------------:|----------------------:|-------------------------:|--------------------------:|---------------:|----------------:|---------------:|
| gradient_boosted_trees   |       0.845705 |       6.91672 |              6.87793 |               6.95658 |              -0.00660263 |                 0.0634939 |       0.283333 |       1.39263   |            120 |
| ridge                    |       0.815132 |       8.48575 |              8.44488 |               8.52615 |              -0.0152973  |                 0.0765963 |       0.321429 |       0.0856137 |            125 |
| mlp                      |       0.827077 |      11.5288  |             10.8575  |              12.2122  |              -0.020806   |                 0.11863   |       0.316667 |       3.13748   |           2736 |
| gru                      |       0.763912 |      11.6345  |             11.5051  |              11.7678  |              -0.0428039  |                 0.0887274 |       0.42619  |       2.5868    |           1269 |
| resnet                   |       0.797044 |      12.1451  |             11.703   |              12.5746  |              -0.00584758 |                 0.103068  |       0.297619 |       1.3895    |            661 |
| tcn                      |       0.793985 |      12.5353  |             12.3727  |              12.6981  |              -0.027948   |                 0.0921455 |       0.342857 |       1.10168   |            461 |
| cnn                      |       0.790084 |      14.0003  |             13.9336  |              14.0673  |              -0.027099   |                 0.0929131 |       0.354762 |       1.13822   |            461 |
| attention                |       0.697231 |      14.1021  |             13.8933  |              14.3382  |               0.0233453  |                 0.107707  |       0.380952 |       2.16531   |            549 |
| constrained_template_fit |       0.727056 |      15.311   |             14.6101  |              15.9473  |              -0.0208496  |                 0.0963638 |       0.192857 |     nan         |              0 |

Winner by point estimate: `gradient_boosted_trees` with 6.917 [6.878, 6.957] ns. The bounded template fit is 15.311 [14.610, 15.947] ns.

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

Timing point-estimate winner is gru at 1.202 ns versus analytic_timewalk 1.495 ns. Two-pulse point-estimate winner is gradient_boosted_trees at 6.917 ns versus constrained_template_fit 15.311 ns. The winner named here is the held-out metric winner; adoption remains conditional on the failure-rate and leakage guards documented in REPORT.md.

Hypothesis: the dominant useful information for these 18-sample waveforms is local pulse-shape and amplitude structure already captured by strong analytic/template terms plus small tabular or convolutional models. Residual connections, attention, and recurrent memory add little because the waveform is short and phase-locked; they should only help if future tasks include longer windows or explicit pretrigger history.

## 8. Next experiment

A high-information follow-up is to test whether the S19c winners remain stable under run-held-out pedestal and pulse-shape drift. The proposed S19d ticket would refit only the timing GRU and two-pulse gradient-boosted tree with nested run-block calibration, adversarial pedestal offsets, and blinded validation runs. That directly separates architecture merit from calibration fragility before production timing or pile-up deconvolution use.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s19a_0000000006_1_nnarch_sweep.py --config configs/s19c_1783751737_13524_25796187_causal_timing_pileup.yaml
```

Runtime in this execution was `195.37` s. Machine-readable outputs include `result.json`, `manifest.json`, `timing_head_to_head.csv`, `two_pulse_head_to_head.csv`, `timing_architecture_cv.csv`, and `two_pulse_architecture_cv.csv`.
