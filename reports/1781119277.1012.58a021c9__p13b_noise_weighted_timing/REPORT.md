# Study report: P13b - heteroscedastic sample-noise weighting in timing residual fits

- **Ticket:** 1781119277.1012.58a021c9
- **Worker:** testbeam-laptop-1
- **Date:** 2026-07-09
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave one run out across Sample II analysis runs 58, 59, 60, 61, 62, 63, and 65
- **Output directory:** `reports/1781119277.1012.58a021c9__p13b_noise_weighted_timing`

## Abstract

This study tests whether the sample-level ADC noise estimates measured in P13a improve downstream timing residual correction when they are used as heteroscedastic loss weights.  The answer is negative in the pre-registered primary metric: the winner is `gradient_boosted_trees_unweighted` with pooled leave-run-out sigma68 1.1294 ns [1.0990, 1.1559], while the analytic timewalk traditional baseline is 1.5511 ns [1.5196, 1.5852].

## Raw-data reproduction gate

The analysis first rereads raw ROOT files and reproduces the selected-pulse counts with zero tolerance.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

All rows pass exactly; no downstream benchmark is accepted unless this gate is true.

## Methods

### Timing residual objective

For each event and stave, a geometry-corrected time is `u_{is}=t_{is}-x_s v^{-1}` with `v^{-1}=0.078 ns/cm`.  A model predicts the residual of a base time against the other two downstream staves,

`r_{is}=u_{is}^{base} - (1/2) sum_{q != s} u_{iq}^{base}`.

The corrected time is `t'_{is}=t^{base}_{is}-f(x_{is})`.  The primary metric is the sigma68 half-width of all corrected pair differences B4-B6, B4-B8, and B6-B8 in the held-out run.  Bootstrap confidence intervals resample event units, preserving the three pair residuals per event.

### Traditional baselines

Traditional candidates are CFD10/20/30/40/50, a 500 ADC leading edge, template phase matching, and optimal-filter windows.  The strongest traditional method used for the headline comparison is the S03a analytic timewalk correction trained fold-locally on amplitude, rise-shape, and stave terms, with the base method chosen from the training runs.

### Heteroscedastic weights

P13a provides a per-sample ADC noise scale `sigma_j` for the 18 samples.  For pulse `i`, normalized waveform `z_ij=y_ij/A_i`, and time derivative `g_ij=dz_ij/dt`, the local timing-noise variance proxy is

`s_i^2 = (sum_j (sigma_j/A_i)^2 g_ij^2) / (sum_j g_ij^2)^2 + s_min^2`,

computed over samples 3--10.  The training weight is `w_i=(1/s_i^2)/median(1/s_i^2)`, clipped to [0.1, 10.0].  Weights are used only in training losses; validation and scoring remain unweighted event-pair residual widths.

### ML/NN benchmark

Each fold trains unweighted and noise-weighted variants of ridge, histogram gradient-boosted trees, a torch MLP, a 1D-CNN, and a TCN.  The TCN is the new architecture: a small dilated convolutional sequence regressor intended to capture local rise/tail structure with a larger temporal receptive field than the plain CNN.  Inputs are same-pulse waveform features, amplitude summaries, and stave one-hot encodings only; no event id, run id, other-stave time, or held-out labels enter the predictors.

## Pooled Benchmark

| method                                |   n_runs |   n_events |   n_pair_residuals |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   tail_frac_abs_gt5ns |   delta_vs_analytic_timewalk_ns |   delta_ci_low |   delta_ci_high |
|:--------------------------------------|---------:|-----------:|-------------------:|-------------:|---------:|----------:|--------------:|----------------------:|--------------------------------:|---------------:|----------------:|
| gradient_boosted_trees_unweighted     |        7 |       3820 |              11460 |      1.12942 |  1.09904 |   1.15586 |       2.11023 |               0.01457 |                        -0.42167 |       -0.46599 |        -0.38343 |
| tcn_noise_weighted                    |        7 |       3820 |              11460 |      1.14204 |  1.11099 |   1.18006 |       2.42147 |               0.01405 |                        -0.40905 |       -0.44189 |        -0.37163 |
| cnn_noise_weighted                    |        7 |       3820 |              11460 |      1.14450 |  1.11447 |   1.18179 |       2.42289 |               0.01422 |                        -0.40659 |       -0.43855 |        -0.36726 |
| cnn_unweighted                        |        7 |       3820 |              11460 |      1.14770 |  1.10931 |   1.18865 |       2.42349 |               0.01370 |                        -0.40339 |       -0.44028 |        -0.36742 |
| tcn_unweighted                        |        7 |       3820 |              11460 |      1.16021 |  1.12741 |   1.19966 |       2.42905 |               0.01387 |                        -0.39089 |       -0.42257 |        -0.35180 |
| gradient_boosted_trees_noise_weighted |        7 |       3820 |              11460 |      1.20445 |  1.17535 |   1.23448 |       2.33658 |               0.01771 |                        -0.34664 |       -0.39088 |        -0.30730 |
| mlp_unweighted                        |        7 |       3820 |              11460 |      1.21175 |  1.19009 |   1.23423 |       2.18572 |               0.01082 |                        -0.33934 |       -0.37606 |        -0.29393 |
| ridge_unweighted                      |        7 |       3820 |              11460 |      1.32673 |  1.30016 |   1.35470 |       2.39035 |               0.01291 |                        -0.22436 |       -0.26348 |        -0.18615 |
| ridge_noise_weighted                  |        7 |       3820 |              11460 |      1.34678 |  1.32162 |   1.37205 |       2.38306 |               0.01326 |                        -0.20431 |       -0.24175 |        -0.16990 |
| mlp_noise_weighted                    |        7 |       3820 |              11460 |      1.35931 |  1.32449 |   1.39265 |       2.38590 |               0.01806 |                        -0.19178 |       -0.23386 |        -0.15087 |
| analytic_timewalk_unweighted          |        7 |       3820 |              11460 |      1.55109 |  1.51963 |   1.58518 |       2.66699 |               0.01911 |                         0.00000 |        0.00000 |         0.00000 |
| template_phase_unweighted             |        7 |       3820 |              11460 |      2.74141 |  2.73617 |   2.78246 |       3.30837 |               0.08133 |                         1.19032 |        1.15477 |         1.25241 |
| cfd20_unweighted                      |        7 |       3820 |              11460 |      3.15027 |  3.11539 |   3.18892 |       6.20431 |               0.05794 |                         1.59917 |        1.55037 |         1.64706 |

## Fold-level Results

|   heldout_run |   analytic_timewalk_unweighted |   cfd20_unweighted |   cnn_noise_weighted |   cnn_unweighted |   gradient_boosted_trees_noise_weighted |   gradient_boosted_trees_unweighted |   mlp_noise_weighted |   mlp_unweighted |   ridge_noise_weighted |   ridge_unweighted |   tcn_noise_weighted |   tcn_unweighted |   template_phase_unweighted |
|--------------:|-------------------------------:|-------------------:|---------------------:|-----------------:|----------------------------------------:|------------------------------------:|---------------------:|-----------------:|-----------------------:|-------------------:|---------------------:|-----------------:|----------------------------:|
|            58 |                        1.18748 |            3.11542 |              0.65548 |          0.75853 |                                 1.43304 |                             1.0926  |              2.14548 |          1.10487 |                1.25896 |            1.12686 |              0.65363 |          0.76476 |                     2.6428  |
|            59 |                        1.45871 |            3.19039 |              1.17895 |          1.03966 |                                 1.16605 |                             1.09257 |              1.19856 |          1.12831 |                1.37319 |            1.35119 |              1.16811 |          1.0381  |                     2.99232 |
|            60 |                        1.3437  |            3.13862 |              1.03052 |          1.12908 |                                 1.30143 |                             1.19227 |              1.38394 |          1.30735 |                1.32375 |            1.31736 |              1.03384 |          1.21037 |                     2.66393 |
|            61 |                        2.12996 |            2.91408 |              1.21612 |          1.21024 |                                 1.1153  |                             1.05665 |              1.43521 |          1.15655 |                1.31361 |            1.27459 |              1.22164 |          1.21329 |                     2.70351 |
|            62 |                        1.469   |            3.23169 |              1.08598 |          1.06117 |                                 1.20756 |                             1.10796 |              1.27798 |          1.2014  |                1.33436 |            1.34126 |              1.08653 |          1.06317 |                     2.90117 |
|            63 |                        1.39132 |            3.40351 |              1.12183 |          1.113   |                                 1.16524 |                             1.21086 |              1.4402  |          1.30209 |                1.40821 |            1.43356 |              1.11897 |          1.09942 |                     2.87872 |
|            65 |                        1.49464 |            2.99339 |              1.05642 |          1.26286 |                                 1.37975 |                             1.13437 |              1.56305 |          1.25105 |                1.47413 |            1.41781 |              1.05071 |          1.25978 |                     2.88915 |

## Weight Diagnostics

|   heldout_run | scope   |   n_pulses |   sigma_t_median_ns |   sigma_t_p16_ns |   sigma_t_p84_ns |   weight_median |   weight_p16 |   weight_p84 |
|--------------:|:--------|-----------:|--------------------:|-----------------:|-----------------:|----------------:|-------------:|-------------:|
|            58 | train   |      11241 |             1.04910 |          0.61154 |          1.55750 |         1.00034 |      0.45386 |      2.94398 |
|            58 | heldout |        219 |             1.08779 |          0.71856 |         11.93617 |         0.93045 |      0.10000 |      2.13238 |
|            59 | train   |       9171 |             1.03247 |          0.60661 |          1.53685 |         1.03283 |      0.46614 |      2.99205 |
|            59 | heldout |       2289 |             1.11431 |          0.64168 |          1.67797 |         0.88668 |      0.39103 |      2.67386 |
|            60 | train   |       9036 |             1.07597 |          0.63402 |          1.60676 |         0.95100 |      0.42646 |      2.73892 |
|            60 | heldout |       2424 |             0.97211 |          0.53231 |          1.37171 |         1.16506 |      0.58514 |      3.88562 |
|            61 | train   |       8661 |             1.05550 |          0.61245 |          1.59333 |         0.98825 |      0.43368 |      2.93520 |
|            61 | heldout |       2799 |             1.02764 |          0.61350 |          1.48684 |         1.04256 |      0.49803 |      2.92515 |
|            62 | train   |       9039 |             1.04620 |          0.61141 |          1.57207 |         1.00590 |      0.44549 |      2.94517 |
|            62 | heldout |       2421 |             1.05804 |          0.61788 |          1.55031 |         0.98352 |      0.45809 |      2.88384 |
|            63 | train   |      10350 |             1.04069 |          0.60713 |          1.54709 |         1.01657 |      0.45999 |      2.98693 |
|            63 | heldout |       1110 |             1.13638 |          0.67038 |          1.77219 |         0.85259 |      0.35056 |      2.44985 |
|            65 | train   |      11262 |             1.04646 |          0.61050 |          1.55442 |         1.00539 |      0.45566 |      2.95404 |
|            65 | heldout |        198 |             1.26052 |          0.77920 |          2.43744 |         0.69292 |      0.18560 |      1.81343 |

The best noise-weighted method is `tcn_noise_weighted` at 1.1420 ns; its unweighted peer is `tcn_unweighted` at 1.1602 ns.  The paired delta is -0.0182 ns, so sample-noise weighting does not show a practically useful gain in this benchmark.

## Systematics and Caveats

- The P13a noise table is a sample-phase aggregate, not a direct event-by-event electronics covariance measurement.
- Weighting changes the training loss but not the held-out metric; this is deliberate because the physics timing resolution should remain an unweighted event property.
- Neural models use fixed compact hyperparameters to keep the leave-run-out benchmark reproducible; larger sweeps could change model ordering.
- The downstream coincidence selection favors clean B4/B6/B8 events and is not a full B-stack trigger-efficiency study.
- Bootstrap intervals resample held-out events and do not include uncertainty from the P13a noise-estimation stage.

## Conclusion

The winner recorded in `result.json` is `gradient_boosted_trees_unweighted`.  Heteroscedastic sample-noise weighting does not beat the best unweighted timing correction with these inputs.  The result points away from independent ADC sample noise as the dominant source of residual timing tails and toward waveform shape, pile-up, or run-support systematics.

## Reproduction

`/home/billy/anaconda3/bin/python scripts/p13b_1781119277_1012_58a021c9_noise_weighted_timing.py --config configs/p13b_1781119277_1012_58a021c9_noise_weighted_timing.yaml`

Key output files: `pooled_benchmark.csv`, `fold_benchmark.csv`, `pair_residuals.csv`, `noise_weight_summary.csv`, `model_meta.csv`, `result.json`, and `manifest.json`.
