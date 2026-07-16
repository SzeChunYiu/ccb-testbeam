# Study report: S19b - pile-up deconvolution and saturation-recovery architecture bakeoff

- **Study ID:** S19b
- **Ticket:** `1783727976.8993.29540994`
- **Author:** `testbeam-laptop-4`
- **Date:** 2026-07-11
- **Input:** raw B-stack ROOT files under `/home/billy/ccb-data/extracted/root/root`
- **Config:** `configs/1783727976_8993_29540994_pileup_saturation_arch_bakeoff.yaml`
- **Git commit at run time:** `eaabf4d51696146e9e85ae3b525515692dec86f4`

## 0. Question

Do architectures beyond the established MLP/CNN baselines improve two waveform tasks when evaluated by run-held-out bootstrap intervals: downstream same-particle timing residual correction and injected two-pulse decomposition with clipped/high-amplitude charge-recovery diagnostics?

The pre-registered primary timing metric is held-out run-65 pairwise corrected residual `sigma68` in ns. The pre-registered primary two-pulse metric is held-out constituent time RMS in ns, with failure rate, detection AP, and constituent charge bias/resolution as adoption guards. The saturation-recovery component is necessarily a closure proxy: the available raw ROOT files do not carry an independent saturated-energy truth label, so this study tests recovery of injected clipped/high-amplitude overlapping pulse charge rather than claiming an absolute saturation calibration.

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

ML/NN competitors are ridge/logistic, gradient-boosted trees, MLP, 1D-CNN, 1D-ResNet, TCN, attention, and GRU. The ResNet/TCN/attention/GRU family is the new-architecture probe beyond the requested ridge, GBT, MLP, and 1D-CNN baselines. Classifier heads estimate overlap probability; regression heads estimate `t1`, `t2`, `A1/max(A)`, and `A2/max(A)` on injected positives.

The fitted waveform model for the traditional method is

`y_k = b + A_1 s(k - t_1) + A_2 s(k - t_2) + epsilon_k`,

with bounded amplitudes, baseline, and pulse separation. For ML regressors the charge-recovery target is the normalized constituent amplitude pair `(A_1/max(A), A_2/max(A))`; the reported charge fractional bias is `median((A_hat - A_true)/A_true)` over both constituents, and `charge_fractional_res68` is half the central 68% interval of the same fractional residuals. These charge metrics are the saturation-recovery proxy used here because they test whether a method can infer hidden constituent amplitudes after overlap or clipping-like information loss.

For the bounded template fit, the waveform noise covariance is not independently known, so an absolute `chi2/ndf` is not quoted as a calibrated goodness-of-fit. The comparable diagnostics are the one-pulse versus two-pulse SSE improvement, the constrained-fit failure rate, the full constituent-time error distribution, and the charge-error distribution.

## 3. Architecture CV

Timing CV rows are grouped by run and score validation pairwise `sigma68`; the full table is `timing_architecture_cv.csv`.

| model                  |   sigma68_ns |
|:-----------------------|-------------:|
| gradient_boosted_trees |      1.15194 |
| attention              |      1.18901 |
| resnet                 |      1.18977 |
| gradient_boosted_trees |      1.2047  |
| mlp                    |      1.20742 |
| mlp                    |      1.24314 |
| gru                    |      1.24953 |
| tcn                    |      1.29769 |
| cnn                    |      1.30099 |
| ridge                  |      1.33793 |
| ridge                  |      1.33999 |
| ridge                  |      1.34055 |

Two-pulse CV rows are grouped by source run and score detection/recovery on validation folds; the full table is `two_pulse_architecture_cv.csv`.

| model                  |   time_rms_ns |
|:-----------------------|--------------:|
| gradient_boosted_trees |       8.17259 |
| ridge                  |       9.11552 |
| mlp                    |      13.6735  |

## 4. Held-out head-to-head

### Timing

| model                  |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   n_pair_residuals |   train_seconds |   n_parameters |
|:-----------------------|-------------:|---------:|----------:|--------------:|-------------------:|----------------:|---------------:|
| mlp                    |      1.18473 | 0.978102 |   1.45576 |       1.30191 |                198 |       83.3742   |           1664 |
| gradient_boosted_trees |      1.28112 | 0.976684 |   1.47641 |       1.28966 |                198 |        0.860122 |             26 |
| gru                    |      1.30093 | 1.03746  |   1.53623 |       1.35902 |                198 |        9.88749  |           1249 |
| resnet                 |      1.31928 | 1.09857  |   1.56825 |       1.36301 |                198 |        3.74929  |            537 |
| cnn                    |      1.31942 | 1.06303  |   1.59079 |       1.39168 |                198 |        4.06383  |            337 |
| tcn                    |      1.32355 | 1.04277  |   1.57936 |       1.37168 |                198 |        3.18282  |            337 |
| attention              |      1.38633 | 1.01752  |   1.62214 |       1.40044 |                198 |       14.4403   |            425 |
| ridge                  |      1.44284 | 1.18172  |   1.62949 |       1.41159 |                198 |        0.058145 |             26 |
| analytic_timewalk      |      1.49464 | 1.31093  |   1.68574 |       1.69913 |                198 |      nan        |            nan |
| s02_ridge_cfd20        |      1.77781 | 1.5215   |   2.05625 |       1.71577 |                198 |      nan        |            nan |
| template_phase         |      2.88915 | 2.63915  |   3.27718 |       2.57669 |                198 |      nan        |            nan |
| cfd20                  |      2.99339 | 2.69328  |   3.37971 |       2.74268 |                198 |      nan        |            nan |

Winner by point estimate: `mlp` with 1.185 [0.978, 1.456] ns. The analytic traditional baseline is 1.495 [1.311, 1.686] ns.

### Two-pulse recovery

| model                    |   detection_ap |   time_rms_ns |   time_rms_ns_ci_low |   time_rms_ns_ci_high |   charge_fractional_bias |   charge_fractional_res68 |   failure_rate |   train_seconds |   n_parameters |
|:-------------------------|---------------:|--------------:|---------------------:|----------------------:|-------------------------:|--------------------------:|---------------:|----------------:|---------------:|
| gradient_boosted_trees   |       0.825147 |       7.42654 |              7.40307 |               7.44944 |              -0.00532716 |                 0.0600421 |       0.335714 |       1.23383   |            120 |
| ridge                    |       0.789895 |       8.99985 |              8.93018 |               9.07607 |              -0.0104425  |                 0.0726956 |       0.319048 |       0.0199749 |            125 |
| mlp                      |       0.807683 |      10.965   |             10.8434  |              11.0779  |              -0.00279027 |                 0.0842161 |       0.330952 |       1.26615   |           2736 |
| gru                      |       0.723006 |      11.3967  |             11.2602  |              11.5435  |              -0.00996343 |                 0.0824322 |       0.338095 |       2.65694   |           1269 |
| resnet                   |       0.769285 |      12.5708  |             11.9625  |              13.1891  |              -0.0072541  |                 0.0824411 |       0.414286 |       1.22882   |            661 |
| constrained_template_fit |       0.74444  |      14.5588  |             14.5529  |              14.5647  |              -0.0142664  |                 0.0937289 |       0.180952 |     nan         |              0 |
| attention                |       0.672313 |      14.6633  |             14.4446  |              14.8755  |               0.00369801 |                 0.0932123 |       0.385714 |       1.94894   |            549 |
| tcn                      |       0.744315 |      14.7235  |             14.6659  |              14.779   |               0.0150547  |                 0.079704  |       0.302381 |       1.15597   |            461 |
| cnn                      |       0.747735 |      14.8678  |             14.7841  |              14.9484  |               0.0186689  |                 0.0816176 |       0.278571 |       0.968427  |            461 |

Winner by point estimate: `gradient_boosted_trees` with 7.427 [7.403, 7.449] ns. The bounded template fit is 14.559 [14.553, 14.565] ns.

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
- Two-pulse labels are injected and template-like. Real high-current overlaps may contain baseline excursions, saturation, digitizer clipping, or topology not represented in this closure test.
- Saturation recovery is evaluated through constituent charge recovery in injected high-amplitude/overlap waveforms. Without independent saturated-energy truth in the ROOT stream, these numbers should be read as a closure benchmark, not an absolute correction for saturated detector response.
- Bootstrap intervals resample held-out events or source runs, so they cover finite held-out statistics better than model-selection uncertainty.
- The ResNet/TCN/attention/GRU models are deliberately small laptop-safe architectures. A null result does not exclude larger models, but it does bound what a small architecture sweep can justify.

## 7. Verdict and hypothesis

Timing point-estimate winner is mlp at 1.185 ns versus analytic_timewalk 1.495 ns. Two-pulse point-estimate winner is gradient_boosted_trees at 7.427 ns versus constrained_template_fit 14.559 ns. The winner named here is the held-out metric winner; adoption remains conditional on the failure-rate and leakage guards documented in REPORT.md.

Hypothesis: the dominant useful information for these 18-sample waveforms is local pulse-shape and amplitude structure already captured by strong analytic/template terms plus small tabular or convolutional models. Residual connections, attention, and recurrent memory add little because the waveform is short and phase-locked; they should only help if future tasks include longer windows or explicit pretrigger history.

## 8. Next experiment

A high-information follow-up is to test support-preserving augmentation and ensembling only for the task where a neural model has favorable guard metrics. That directly answers whether current limits are architecture capacity or training-support coverage, without expanding the search blindly.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s19a_0000000006_1_nnarch_sweep.py --config configs/1783727976_8993_29540994_pileup_saturation_arch_bakeoff.yaml
```

Runtime in this execution was `300.40` s. Machine-readable outputs include `result.json`, `manifest.json`, `timing_head_to_head.csv`, `two_pulse_head_to_head.csv`, `timing_architecture_cv.csv`, and `two_pulse_architecture_cv.csv`.
