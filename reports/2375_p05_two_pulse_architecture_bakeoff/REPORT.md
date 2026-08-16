# P05-2375: pile-up detection and two-pulse decomposition architecture bakeoff

- **Ticket:** `#2375` P05: Pile-up detection & two-pulse decomposition (deep vs fit)
- **Author:** `testbeam-laptop-2`
- **Date:** 2026-08-16
- **Config:** `configs/p05_2375_two_pulse_architecture_bakeoff.json`
- **Input checksums:** `input_sha256.csv`; output hashes in `manifest.json`

## Abstract

This study asks when a learned waveform decomposer beats a strong constrained two-pulse template fit on controlled pile-up injections derived from raw ROOT B-stave pulses. The raw-ROOT reproduction gate exactly reproduces the S00 selected-pulse anchor before any learning. The benchmark then compares a traditional template fit with ridge, gradient-boosted trees, MLP, 1D-CNN, and a new template-residual fusion architecture on a strict run split.

The winner by the pre-registered composite score is **`template_residual_fusion_new`** with held-out constituent-time RMS `6.505` ns (95% run-bootstrap CI `5.805`--`7.100`), charge fractional res68 `0.0546`, and failure rate `0.257`. The traditional fit has time RMS `13.583` ns and failure rate `0.148`.

## 1. Reproduction gate from raw ROOT

For every configured run, `h101/HRDv` is reshaped to `(event, channel, sample)` with 18 samples per channel. The pedestal is

`b_{ec}=median(x_{ec0},x_{ec1},x_{ec2},x_{ec3})`,

and the selected-pulse indicator is

`I_{ec}=1[max_t(x_{ect}-b_{ec})>1000 ADC]`.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## 2. Data-generating benchmark

Train runs are `[58, 59, 60, 61, 62]` and held-out runs are `[63, 65]`. Template construction uses only train-run clean pulses with amplitude 1500--12000 ADC and peak sample 4--12.

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |             1100 |                   4.055 |                      8 |           9.001 |
| B4      |             1100 |                   4.461 |                      8 |           8.82  |
| B6      |             1068 |                   5.307 |                      9 |           8.242 |
| B8      |              951 |                   5.277 |                      9 |           9.089 |

Injected doublets use

`w(t)=A_1 T_s(t-t_1)+r A_1 T_s(t-t_1-Delta)+epsilon_{r,s}(t)+p`,

where the residual `epsilon` is sampled from raw single-pulse residuals from the same source run and stave, and `p` is a small uniform pedestal offset. Clean controls use the same machinery with `r=0`.

## 3. Methods

The traditional method is a bounded two-pulse least-squares template fit. For one- and two-pulse hypotheses, it minimizes

`SSE_k=sum_t [w(t)-b-sum_{j=1}^k A_j T_s(t-t_j)]^2`,

over a first-pulse shift grid, a fixed separation grid, positive amplitudes, an amplitude-ratio bound, and a bounded pedestal. Its detection score is `(SSE_1-SSE_2)/SSE_1`.

The ML/NN methods see identical train/held-out rows and no run id or event id feature. Ridge uses L2 logistic classification plus Ridge regression. Gradient-boosted trees use histogram boosting for detection and multi-output regression. MLP uses one hidden classifier layer and a two-layer regressor. The 1D-CNN is the established P05 compact two-head convolutional network over the normalized 18 samples.

The new architecture, `template_residual_fusion_new`, concatenates waveform summaries with frozen traditional fit outputs and learns residual boosted-tree corrections. This is sensible here because the physics prior localizes the candidate pulses while the learned stage can correct systematic template mismatch and failure boundaries.

## 4. Metrics and uncertainty

For accepted true doublets, constituent timing errors are

`e_t=10 ns * (hat t - t)`,

and total charge closure is

`e_Q=((hat A_1+hat A_2)-(A_1+A_2))/(A_1+A_2)`.

The robust width is `sigma_68=(Q_84-Q_16)/2`. The pre-registered winner score is

`C = RMS_t + 12 sigma_68(e_Q) + 8 |median(e_Q)| + 18 r_fail`.

Confidence intervals are percentile 95% intervals from 400 bootstrap resamples of held-out source runs.

## 5. Overall held-out results

| method                       |   winner_score |   detection_ap |   time_rms_ns |   time_rms_ns_ci_low |   time_rms_ns_ci_high |   charge_fractional_bias |   charge_fractional_res68 |   failure_rate |
|:-----------------------------|---------------:|---------------:|--------------:|---------------------:|----------------------:|-------------------------:|--------------------------:|---------------:|
| template_residual_fusion_new |          11.81 |         0.9021 |         6.505 |                5.805 |                 7.1   |                -0.003939 |                   0.05456 |         0.2567 |
| gradient_boosted_trees       |          12.18 |         0.8944 |         6.88  |                6.308 |                 7.412 |                -0.004374 |                   0.06378 |         0.25   |
| one_d_cnn                    |          13.82 |         0.886  |         8.492 |                8.401 |                 8.585 |                -0.009122 |                   0.08031 |         0.2383 |
| ridge                        |          14.88 |         0.8439 |         8.682 |                8.505 |                 8.854 |                -0.02136  |                   0.07747 |         0.2833 |
| mlp                          |          15.75 |         0.8678 |         9.628 |                9.132 |                10.08  |                -0.01792  |                   0.07824 |         0.28   |
| traditional                  |          17.53 |         0.7787 |        13.58  |               12.66  |                14.51  |                -0.02218  |                   0.0917  |         0.1483 |

## 6. Separation and amplitude-ratio systematics

The full stratum table is `strata_metrics.csv`. The first rows below show the predeclared stress axes.

| stratum         |   value | method                       |   time_rms_ns |   charge_fractional_bias |   charge_fractional_res68 |   failure_rate |
|:----------------|--------:|:-----------------------------|--------------:|-------------------------:|--------------------------:|---------------:|
| true_sep_sample |    0.5  | traditional                  |        18.07  |                0.002586  |                   0.1467  |        0.2     |
| true_sep_sample |    0.5  | ridge                        |        10.39  |               -0.01506   |                   0.08765 |        0.4714  |
| true_sep_sample |    0.5  | gradient_boosted_trees       |         7.517 |                0.01412   |                   0.04944 |        0.4429  |
| true_sep_sample |    0.5  | mlp                          |        10.31  |                0.02036   |                   0.08815 |        0.5     |
| true_sep_sample |    0.5  | one_d_cnn                    |        10.26  |                0.02111   |                   0.09969 |        0.4571  |
| true_sep_sample |    0.5  | template_residual_fusion_new |         7.884 |               -0.0004729 |                   0.04689 |        0.4571  |
| true_sep_sample |    0.75 | traditional                  |        17.25  |               -0.01179   |                   0.08311 |        0.25    |
| true_sep_sample |    0.75 | ridge                        |        10.24  |               -0.008478  |                   0.1025  |        0.4062  |
| true_sep_sample |    0.75 | gradient_boosted_trees       |         6.973 |                0.005048  |                   0.07239 |        0.4219  |
| true_sep_sample |    0.75 | mlp                          |         9.384 |                0.01037   |                   0.0974  |        0.4531  |
| true_sep_sample |    0.75 | one_d_cnn                    |         9.186 |                0.007358  |                   0.07903 |        0.5625  |
| true_sep_sample |    0.75 | template_residual_fusion_new |         6.989 |                0.004499  |                   0.05513 |        0.4688  |
| true_sep_sample |    1    | traditional                  |        13.42  |               -0.02218   |                   0.09015 |        0.1897  |
| true_sep_sample |    1    | ridge                        |         8.979 |               -0.01071   |                   0.07256 |        0.3793  |
| true_sep_sample |    1    | gradient_boosted_trees       |         7.916 |                0.01345   |                   0.03564 |        0.431   |
| true_sep_sample |    1    | mlp                          |        12.55  |                0.02015   |                   0.08175 |        0.4138  |
| true_sep_sample |    1    | one_d_cnn                    |         9.565 |                0.004363  |                   0.08798 |        0.4483  |
| true_sep_sample |    1    | template_residual_fusion_new |         6.603 |                0.002562  |                   0.03927 |        0.3793  |
| true_sep_sample |    1.5  | traditional                  |        15.25  |                0.002674  |                   0.09264 |        0.2182  |
| true_sep_sample |    1.5  | ridge                        |         7.841 |               -0.0112    |                   0.07105 |        0.4     |
| true_sep_sample |    1.5  | gradient_boosted_trees       |         5.989 |                0.004285  |                   0.03839 |        0.4     |
| true_sep_sample |    1.5  | mlp                          |         7.622 |               -0.02506   |                   0.04929 |        0.3818  |
| true_sep_sample |    1.5  | one_d_cnn                    |         6.968 |               -0.01909   |                   0.06081 |        0.2545  |
| true_sep_sample |    1.5  | template_residual_fusion_new |         4.451 |               -0.005894  |                   0.04513 |        0.3818  |
| true_sep_sample |    2    | traditional                  |        12.56  |               -0.02507   |                   0.0806  |        0.1282  |
| true_sep_sample |    2    | ridge                        |         7.124 |               -0.01333   |                   0.0794  |        0.2436  |
| true_sep_sample |    2    | gradient_boosted_trees       |         5.529 |               -0.02024   |                   0.06412 |        0.2308  |
| true_sep_sample |    2    | mlp                          |         8.024 |               -0.04086   |                   0.08009 |        0.2308  |
| true_sep_sample |    2    | one_d_cnn                    |         6.952 |               -0.006034  |                   0.06894 |        0.1795  |
| true_sep_sample |    2    | template_residual_fusion_new |         5.464 |               -0.008101  |                   0.04657 |        0.2051  |
| true_sep_sample |    3    | traditional                  |        11.22  |               -0.005918  |                   0.08679 |        0.09524 |
| true_sep_sample |    3    | ridge                        |         7.057 |               -0.02921   |                   0.06371 |        0.2381  |
| true_sep_sample |    3    | gradient_boosted_trees       |         7.432 |               -0.001883  |                   0.05796 |        0.1587  |
| true_sep_sample |    3    | mlp                          |         9.01  |               -0.01776   |                   0.06979 |        0.2222  |
| true_sep_sample |    3    | one_d_cnn                    |         7.807 |               -0.007996  |                   0.07858 |        0.1429  |
| true_sep_sample |    3    | template_residual_fusion_new |         6.778 |               -0.002339  |                   0.06535 |        0.2063  |

## 7. Validation, caveats, and threats to validity

The benchmark is fair at the row level: every method receives the same waveform, label, target, split, and metric. The split is by source run, and templates are fit only from train-run clean pulses. Group-CV AP/AUC rows are written to `group_cv.csv` for the train-run hyperparameter sanity check.

The main caveat is that the truth comes from controlled injections, not hand-labeled real beam pile-up. The residuals and templates are raw-ROOT-derived, but independent real doublets may have different morphology, electronics saturation, or pile-up topology. The result therefore supports adoption only for template-like overlap recovery and motivates a real-candidate validation gate before physics use.

## 8. Provenance and reproducibility

Run:

```bash
python scripts/p05_2375_two_pulse_architecture_bakeoff.py --config configs/p05_2375_two_pulse_architecture_bakeoff.json
```

Runtime was `46.47` s. Outputs: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `method_metrics.csv`, `event_predictions.csv`, `strata_metrics.csv`, `group_cv.csv`, and `template_summary.csv`.
