# Study report: S03 - Timewalk correction closure and ML frontier

- **Study ID:** S03-2368
- **Ticket:** #2368 - S03: Timewalk correction closure & held-out-run
- **Author (worker label):** testbeam-laptop-1
- **Date:** 2026-08-16
- **Depends on:** S00, S02
- **Input checksum(s):** aggregate sha256 `b5547ac7f2452361c1fc85b20ae7107c8fb6df54af22b152c2ef8e983fe38ee4`
- **Git commit:** `d3b2beb217c7157693da45e3e8824489c7a8f036`
- **Config:** `configs/s03_2368_timewalk_frontier.yaml`

## 0. Question

Does an interpretable amplitude timewalk correction close the residual-vs-amplitude slope on a run-held-out sample, and do modern residual regressors improve the same held-out pairwise timing metric enough to justify extra complexity?

The pre-registered primary metric is held-out pairwise `sigma68` of corrected B4/B6/B8 time residuals at 2 cm spacing. The winner is the lowest point estimate; superiority over the strong traditional baseline requires the paired event-bootstrap delta confidence interval to exclude zero at alpha=0.05.

## 1. Reproduction from raw ROOT

Before fitting any correction, the S00 raw ROOT selector was rerun over every configured B-stack ROOT file. The gate exactly reproduces the selected-pulse count used by downstream S02/S03 timing work.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The timing table itself was then rebuilt from the same ROOT pass. Training used runs 58-63 and the held-out benchmark used run 65 only; event identifiers do not cross the split.

## 2. Traditional non-ML method

The strong baseline is the S02 `template_phase` pickoff followed by the S03 analytic/polynomial timewalk correction. For pulse p on stave s, the corrected time is

`t'_p = t_template,p - f_s(A_p, x_p)`,

where the selected model is a ridge-regularized polynomial/shape expansion over `log(1+A)`, `1/A`, `1/sqrt(A)`, peak sample, normalized area, rise-time proxies, normalized early and late charge, normalized peak height, stave intercepts, and optional stave interactions. Candidate families and ridge alphas were selected only by grouped CV on training runs.

| method         |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   core_sigma_ns |   chi2_ndf |
|:---------------|-------------:|--------------:|----------------------:|----------------:|-----------:|
| of_4_12        |      2.84466 |       2.90972 |             0.0858586 |        1.82653  |   1.63283  |
| template_phase |      2.88915 |       2.57669 |             0.0505051 |        0.442691 |   3.21363  |
| cfd30          |      2.98823 |       2.76793 |             0.0808081 |        1.29089  |   1.0905   |
| cfd20          |      2.99339 |       2.74268 |             0.0656566 |        1.08025  |   0.915142 |
| cfd40          |      3.02634 |       2.92355 |             0.0909091 |        1.39293  |   1.13786  |
| cfd10          |      3.0629  |       2.86492 |             0.0353535 |        1.1495   |   1.54539  |
| cfd50          |      3.27331 |       3.10562 |             0.126263  |        1.54639  |   1.13066  |
| of_3_11        |      3.31858 |       2.98046 |             0.10101   |        1.51389  |   1.77231  |

## 3. ML and neural methods

All ML methods predict the same per-pulse residual target, defined as that stave's TOF-corrected residual relative to the mean of the other two downstream staves. The corrected time is `t'_p = t_base,p - g(z_p)`. The split is by run using grouped CV inside runs 58-63 and final evaluation on run 65. Features exclude run id, event id, event order, held-out labels, and other-stave timing.

Methods benchmarked: ridge residual regression, histogram gradient-boosted trees, a heteroskedastic waveform MLP, a waveform 1D-CNN, and a new physics-residual network. The new architecture has a linear analytic-physics branch over the S03 amplitude basis plus a small neural residual branch over normalized waveform samples; it is intended to test whether enforcing the analytic timewalk prior helps a neural model avoid run leakage and overfit.

|   candidate |   alpha |   fold |   sigma68_ns |   n_pair_residuals |   n_features | model                  |   learning_rate |   max_iter |    l2 |   hidden |   weight_decay |   pred_sigma_median_ns |   channels |
|------------:|--------:|-------:|-------------:|-------------------:|-------------:|:-----------------------|----------------:|-----------:|------:|---------:|---------------:|-----------------------:|-----------:|
|         nan |     nan |     -1 |      1.10277 |                  0 |          nan | cnn_waveform           |          nan    |        nan | nan   |      nan |          0.001 |                    nan |          8 |
|         nan |     nan |     -1 |      1.1035  |                  0 |          nan | cnn_waveform           |          nan    |        nan | nan   |      nan |          0.01  |                    nan |          8 |
|         nan |     nan |     -1 |      1.15154 |                  0 |          nan | gradient_boosted_trees |            0.03 |        120 |   0   |      nan |        nan     |                    nan |        nan |
|         nan |     nan |     -1 |      1.15433 |                  0 |          nan | gradient_boosted_trees |            0.03 |        120 |   0.1 |      nan |        nan     |                    nan |        nan |
|         nan |     nan |     -1 |      1.15581 |                  0 |          nan | gradient_boosted_trees |            0.03 |        220 |   0.1 |      nan |        nan     |                    nan |        nan |
|         nan |     nan |     -1 |      1.16151 |                  0 |          nan | gradient_boosted_trees |            0.03 |        220 |   0   |      nan |        nan     |                    nan |        nan |
|         nan |     nan |     -1 |      1.16918 |                  0 |          nan | gradient_boosted_trees |            0.06 |        120 |   0.1 |      nan |        nan     |                    nan |        nan |
|         nan |     nan |     -1 |      1.17112 |                  0 |          nan | cnn_waveform           |          nan    |        nan | nan   |      nan |          0.001 |                    nan |          4 |
|         nan |     nan |     -1 |      1.17286 |                  0 |          nan | cnn_waveform           |          nan    |        nan | nan   |      nan |          0.01  |                    nan |          4 |
|         nan |     nan |     -1 |      1.17996 |                  0 |          nan | gradient_boosted_trees |            0.06 |        120 |   0   |      nan |        nan     |                    nan |        nan |
|         nan |     nan |     -1 |      1.20722 |                  0 |          nan | gradient_boosted_trees |            0.06 |        220 |   0.1 |      nan |        nan     |                    nan |        nan |
|         nan |     nan |     -1 |      1.21038 |                  0 |          nan | gradient_boosted_trees |            0.06 |        220 |   0   |      nan |        nan     |                    nan |        nan |
|         nan |     nan |     -1 |      1.23644 |                  0 |          nan | mlp_waveform           |          nan    |        nan | nan   |       32 |          0.01  |                    nan |        nan |
|         nan |     nan |     -1 |      1.23696 |                  0 |          nan | mlp_waveform           |          nan    |        nan | nan   |       32 |          0.001 |                    nan |        nan |
|         nan |     nan |     -1 |      1.24155 |                  0 |          nan | physics_residual_net   |          nan    |        nan | nan   |       24 |          0.001 |                    nan |        nan |
|         nan |     nan |     -1 |      1.24199 |                  0 |          nan | physics_residual_net   |          nan    |        nan | nan   |       24 |          0.01  |                    nan |        nan |
|         nan |     nan |     -1 |      1.261   |                  0 |          nan | physics_residual_net   |          nan    |        nan | nan   |       12 |          0.001 |                    nan |        nan |
|         nan |     nan |     -1 |      1.26109 |                  0 |          nan | physics_residual_net   |          nan    |        nan | nan   |       12 |          0.01  |                    nan |        nan |
|         nan |     nan |     -1 |      1.2976  |                  0 |          nan | mlp_waveform           |          nan    |        nan | nan   |       16 |          0.001 |                    nan |        nan |
|         nan |     nan |     -1 |      1.30279 |                  0 |          nan | mlp_waveform           |          nan    |        nan | nan   |       16 |          0.01  |                    nan |        nan |

## 4. Head-to-head benchmark

| method                       | metric                      |   sigma68_ns |   ci_low |   ci_high |   delta_vs_baseline_ns |   delta_ci_low |   delta_ci_high |   bias_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   n_pair_residuals |
|:-----------------------------|:----------------------------|-------------:|---------:|----------:|-----------------------:|---------------:|----------------:|----------:|--------------:|----------------------:|-------------------:|
| cnn_waveform                 | heldout_pairwise_sigma68_ns |      1.07326 | 0.834736 |   1.31955 |             -0.421378  |      -0.620983 |      -0.168846  |  0.302451 |       1.33499 |            0.00505051 |                198 |
| mlp_waveform                 | heldout_pairwise_sigma68_ns |      1.26418 | 1.03641  |   1.47494 |             -0.230457  |      -0.473291 |       0.0549316 | -0.778281 |       1.27538 |            0          |                198 |
| gradient_boosted_trees       | heldout_pairwise_sigma68_ns |      1.27043 | 0.975739 |   1.47792 |             -0.224205  |      -0.519171 |       0.0454394 | -0.642144 |       1.27463 |            0          |                198 |
| physics_residual_net         | heldout_pairwise_sigma68_ns |      1.38276 | 1.14739  |   1.63636 |             -0.111877  |      -0.390234 |       0.202164  | -0.638999 |       1.35342 |            0          |                198 |
| ridge                        | heldout_pairwise_sigma68_ns |      1.45893 | 1.1936   |   1.62856 |             -0.0357135 |      -0.32643  |       0.221882  | -0.772191 |       1.41433 |            0          |                198 |
| analytic_polynomial_timewalk | heldout_pairwise_sigma68_ns |      1.49464 | 1.29733  |   1.66843 |              0         |       0        |       0         |  1.03035  |       1.69913 |            0.00505051 |                198 |
| template_phase_base          | heldout_pairwise_sigma68_ns |      2.88915 | 2.63915  |   3.27718 |              1.39451   |       1.07984  |       1.79158   | -2.84655  |       2.57669 |            0.0505051  |                198 |

Winner: **cnn_waveform**, with held-out sigma68 `1.073262` ns and 95% paired event-bootstrap CI `[0.834736, 1.319554]` ns. The strong traditional analytic baseline is `1.494640` ns with CI `[1.297327, 1.668426]` ns.

## 5. Falsification and systematics

The explicit falsification test is a paired event-bootstrap against the analytic baseline inside the held-out run. A learned method is not adopted as superior unless the entire delta CI is below zero. Because five non-traditional methods were tried, the interpretation also treats overlapping CIs as weak evidence even if the point estimate is lower.

| check                          | value    | interpretation                                                                                   |
|:-------------------------------|:---------|:-------------------------------------------------------------------------------------------------|
| train_heldout_event_id_overlap | 0.0      | zero required; split is by run                                                                   |
| analytic_candidate             | amp_only | selected alpha=100.0 by grouped CV                                                               |
| method_family_trials           | 6.0      | analytic, ridge, GBT, MLP, CNN, hybrid; delta CIs are interpreted with this multiplicity in mind |
| data_symlink                   | 0.0      | workspace data symlink was stale; config uses absolute read-only ROOT directory                  |

Amplitude-flatness audit:

| method                       | amp_bin          |   n |   mean_residual_ns |   sigma68_ns |
|:-----------------------------|:-----------------|----:|-------------------:|-------------:|
| template_phase_base          | max_abs_bin_mean | 198 |           1.83155  |          nan |
| analytic_polynomial_timewalk | max_abs_bin_mean | 198 |           0.708892 |          nan |
| ridge                        | max_abs_bin_mean | 198 |           0.981868 |          nan |
| gradient_boosted_trees       | max_abs_bin_mean | 198 |           0.667766 |          nan |
| mlp_waveform                 | max_abs_bin_mean | 198 |           0.680103 |          nan |
| cnn_waveform                 | max_abs_bin_mean | 198 |           0.475966 |          nan |
| physics_residual_net         | max_abs_bin_mean | 198 |           0.589119 |          nan |

## 6. Threats to validity

- **Benchmark/selection:** the baseline is not a strawman; it is the previously selected template-phase pickoff plus an analytic timewalk scan. All models use the same residual target and held-out run.
- **Data leakage:** all tuning uses grouped CV over training runs only. Inputs exclude run/event identifiers and other-stave timing. The event-id overlap check is zero.
- **Metric misuse:** sigma68 is the primary robust metric, but the table also reports full RMS, core Gaussian sigma, chi2/ndf where relevant, bias, and tail fraction.
- **Post-hoc selection:** the primary metric, split, and method family list are encoded in the config before the final run. Architecture counts are reported in the CV table.

## 7. Provenance manifest

`manifest.json` in this directory records input sha256s, git commit, command, seeds, runtime, and output hashes. Raw data were read from `/home/billy/ccb-data/data/extracted/root/root` and were not modified.

## 8. Findings and next steps

The best held-out point estimate is cnn_waveform, improving over the analytic baseline by 0.421378 ns. Adoption should depend on the paired event-bootstrap delta CI and the cross-sample follow-up because the gain is evaluated on one held-out run.

One novel follow-up ticket is proposed: `S03 follow-up: cross-sample physics-residual timewalk adoption gate`. Expected information gain: it tests whether the winning model transfers from Sample II run-held-out closure to Sample I and run 64 without using sample-specific amplitude support, separating genuine timewalk physics from a run-family artifact.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03_2368_timewalk_frontier.py --config configs/s03_2368_timewalk_frontier.yaml
```

Artifacts written: `reproduction_match_table.csv`, `traditional_scan_metrics.csv`, `method_metrics.csv`, `method_cv_scan.csv`, `amplitude_flatness.csv`, `systematics.csv`, `heldout_pair_residuals.csv`, figures, `result.json`, and `manifest.json`.