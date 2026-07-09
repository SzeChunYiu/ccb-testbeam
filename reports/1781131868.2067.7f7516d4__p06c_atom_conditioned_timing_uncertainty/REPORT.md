# P06c: atom-conditioned timing uncertainty propagation

- **Ticket:** `1781131868.2067.7f7516d4`
- **Worker:** `testbeam-laptop-1`
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Primary split:** leave-one-run-out over Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65
- **Primary metric:** pooled pairwise pull-calibration loss; lower is better
- **Bootstrap:** event-paired run-block bootstrap with 350 replicates

## Abstract

P06c asks whether the P06b atom-level timing-risk ledger can improve downstream PID, energy, pile-up, and covariance consumers through calibrated per-pulse uncertainty inflation or abstention across the 18-sample waveform phase, with special attention to peak samples 3-6 where earlier CFD/smoothing studies found artifacts. The raw ROOT reproduction gate matches exactly, and the winner by pre-registered pooled calibration loss is **phase_conformal_gated_cnn** with loss **0.0555** and bootstrap 95% CI **[0.0454, 0.0751]**.

## Reproduction Gate

Counts are rebuilt directly from `HRDv`: median subtract samples 0-3, require amplitude > 1000 ADC, and sum selected B-stave pulses over the configured raw ROOT runs.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The S03a analytic timing closure is rerun before the uncertainty atlas:

| method                  |   value |   ci_low |   ci_high |   n_pair_residuals | best_candidate   |   best_alpha |
|:------------------------|--------:|---------:|----------:|-------------------:|:-----------------|-------------:|
| s02_template_phase_base | 2.88915 |  2.63915 |   3.27718 |                198 | amp_only         |          100 |
| s03a_analytic_timewalk  | 1.49464 |  1.34181 |   1.63357 |                198 | amp_only         |          100 |

## Estimands And Equations

For event `e`, stave `s`, and timestamp method `m`, `tau_{e,s,m} = t_{e,s,m} - x_s v_TOF`, where `v_TOF = 0.078 ns/cm` and downstream stave positions use 2 cm spacing. Pair residuals are `r_{e,a,b,m}=tau_{e,a,m}-tau_{e,b,m}`.

Each uncertainty model predicts a positive pair scale `sigma_hat_{e,a,b,m}`. The pull is `z = r / sigma_hat`. The robust pull width is `sigma68(z) = (Q84(z)-Q16(z))/2`; nominal 68% coverage is `P(|z| <= 1)`, nominal 95% coverage is `P(|z| <= 1.96)`, and calibration ECE is a sigma-quantile-bin weighted average of absolute 68% and 95% coverage errors.

The primary calibration loss is `mean(|sigma68(z)-1|, |C68-0.682689|, |C95-0.95|, ECE)`. This deliberately penalizes both over-confident and over-conservative intervals.

## Methods

Traditional baseline: P06b's fold-local S02 template-phase plus S03a amplitude-only analytic correction supplies the central residual. The uncertainty is an S04-style robust-width lookup, trained only on non-held-out runs, with fallback levels `pair + peak sample + leading-edge phase + sample-window mask`, `pair + mask`, `pair + peak`, `pair`, and global. The lookup is globally rescaled on calibration runs to unit pull width.

ML/NN methods use the corresponding P06b central timing method on the same held-out runs: ridge, gradient-boosted trees, MLP, 1D-CNN, and the atom-gated CNN. Their second-layer uncertainty models are trained on pair-level waveform, amplitude, charge, q-template, baseline, phase, mask, anomaly, topology, and run-family covariates from other runs only. The new architecture is a phase-conformal atom-gated CNN: a two-channel 1D pair waveform encoder gated by atom/tabular features, followed by a run-external conformal phase-bin scale adjustment.

## Head-To-Head Benchmark

| method                    | method_label                              |     n |   calibration_loss |   calibration_loss_ci_low |   calibration_loss_ci_high |   pull_width68 |   pull_width68_ci_low |   pull_width68_ci_high |   coverage68 |   coverage68_ci_low |   coverage68_ci_high |   coverage95 |   coverage95_ci_low |   coverage95_ci_high |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |
|:--------------------------|:------------------------------------------|------:|-------------------:|--------------------------:|---------------------------:|---------------:|----------------------:|-----------------------:|-------------:|--------------------:|---------------------:|-------------:|--------------------:|---------------------:|-------------:|--------------:|----------------------:|
| phase_conformal_gated_cnn | Phase-conformal atom-gated CNN            | 11460 |          0.0554521 |                 0.0454068 |                  0.0751352 |       0.883714 |              0.81048  |               0.948793 |     0.641536 |            0.572308 |             0.699607 |     0.964049 |            0.956952 |             0.970394 |      1.51138 |       2.41393 |             0.0115183 |
| cnn1d                     | 1D-CNN residual scale model               | 11460 |          0.0974848 |                 0.0795451 |                  0.160663  |       1.01566  |              0.913887 |               1.1284   |     0.456108 |            0.376974 |             0.534086 |     0.938045 |            0.922814 |             0.951884 |      1.51375 |       2.42254 |             0.0126527 |
| gradient_boosted_trees    | HistGradientBoosting residual scale model | 11460 |          0.109007  |                 0.0752487 |                  0.208551  |       1.0451   |              0.88827  |               1.22262  |     0.502792 |            0.414342 |             0.586923 |     0.869721 |            0.807171 |             0.921538 |      1.5543  |       2.31556 |             0.0153578 |
| ridge                     | Ridge residual scale model                | 11460 |          0.11002   |                 0.078641  |                  0.203802  |       1.02024  |              0.884442 |               1.16761  |     0.481065 |            0.389596 |             0.568321 |     0.871728 |            0.809907 |             0.927344 |      1.57319 |       2.54659 |             0.0161431 |
| mlp                       | MLP residual scale model                  | 11460 |          0.114004  |                 0.0757196 |                  0.175591  |       1.0623   |              0.930666 |               1.16921  |     0.502182 |            0.446879 |             0.569525 |     0.869284 |            0.83328  |             0.908349 |      1.63591 |       2.41919 |             0.0137871 |
| traditional               | S02/S03/S04 atom robust-width baseline    | 11460 |          0.659059  |                 0.53777   |                  0.758104  |       2.71207  |              2.40677  |               2.91305  |     0.384991 |            0.317647 |             0.44319  |     0.631588 |            0.548324 |             0.698597 |      1.55109 |       2.66699 |             0.0191099 |

Verdict: the winner named in `result.json` is the method with the lowest pooled calibration loss, not necessarily the narrowest residual core. This matters because a method can improve central timing while still producing miscalibrated event-level uncertainty.

## Time-Local Atlas

Peak-sample atlas:

| stratum    | method                    |    n |   pull_width68 |   coverage68 |   coverage95 |   calibration_loss |   sigma68_ns |   tail_frac_abs_gt5ns |
|:-----------|:--------------------------|-----:|---------------:|-------------:|-------------:|-------------------:|-------------:|----------------------:|
| peakmax_10 | phase_conformal_gated_cnn |  657 |       0.737508 |     0.60274  |     0.945205 |          0.102444  |      1.53664 |            0.021309   |
| peakmax_10 | ridge                     |  657 |       0.983471 |     0.487062 |     0.856925 |          0.112395  |      1.71248 |            0.0304414  |
| peakmax_10 | cnn1d                     |  657 |       0.927514 |     0.418569 |     0.901065 |          0.137477  |      1.57943 |            0.021309   |
| peakmax_10 | mlp                       |  657 |       0.992252 |     0.4414   |     0.828006 |          0.138168  |      1.66457 |            0.0273973  |
| peakmax_10 | gradient_boosted_trees    |  657 |       0.953989 |     0.468798 |     0.817352 |          0.141455  |      1.65002 |            0.0228311  |
| peakmax_10 | traditional               |  657 |       1.39089  |     0.42618  |     0.750381 |          0.268771  |      2.01911 |            0.0334855  |
| peakmax_11 | phase_conformal_gated_cnn |  460 |       0.973081 |     0.567391 |     0.913043 |          0.0663253 |      1.69248 |            0.0304348  |
| peakmax_11 | cnn1d                     |  460 |       1.10679  |     0.471739 |     0.895652 |          0.128684  |      1.71706 |            0.0326087  |
| peakmax_11 | ridge                     |  460 |       1.15578  |     0.471739 |     0.863043 |          0.15066   |      1.87291 |            0.0326087  |
| peakmax_11 | gradient_boosted_trees    |  460 |       1.31687  |     0.458696 |     0.826087 |          0.209682  |      1.81336 |            0.0304348  |
| peakmax_11 | mlp                       |  460 |       1.26988  |     0.452174 |     0.780435 |          0.218148  |      1.83391 |            0.0304348  |
| peakmax_11 | traditional               |  460 |       1.49239  |     0.426087 |     0.767391 |          0.287801  |      1.98695 |            0.0304348  |
| peakmax_12 | phase_conformal_gated_cnn |  163 |       0.983348 |     0.644172 |     0.944785 |          0.0357086 |      1.3528  |            0.0122699  |
| peakmax_12 | gradient_boosted_trees    |  163 |       0.904997 |     0.601227 |     0.92638  |          0.0703978 |      1.54161 |            0.0122699  |
| peakmax_12 | ridge                     |  163 |       0.92005  |     0.478528 |     0.957055 |          0.102601  |      1.27307 |            0.0122699  |
| peakmax_12 | mlp                       |  163 |       0.864421 |     0.552147 |     0.858896 |          0.125787  |      1.5851  |            0.0122699  |
| peakmax_12 | cnn1d                     |  163 |       1.20114  |     0.423313 |     0.93865  |          0.156255  |      1.42785 |            0.0122699  |
| peakmax_12 | traditional               |  163 |       7.55663  |     0.269939 |     0.398773 |          2.00065   |      1.33039 |            0.0184049  |
| peakmax_13 | phase_conformal_gated_cnn |  157 |       0.862201 |     0.66242  |     0.929936 |          0.0614809 |      1.31817 |            0.0636943  |
| peakmax_13 | ridge                     |  157 |       0.897743 |     0.496815 |     0.936306 |          0.107415  |      1.3143  |            0.0700637  |
| peakmax_13 | cnn1d                     |  157 |       1.02669  |     0.433121 |     0.968153 |          0.109935  |      1.40165 |            0.0700637  |
| peakmax_13 | gradient_boosted_trees    |  157 |       0.72677  |     0.579618 |     0.878981 |          0.137897  |      1.43338 |            0.0509554  |
| peakmax_13 | mlp                       |  157 |       0.717169 |     0.55414  |     0.866242 |          0.153036  |      1.62118 |            0.0764331  |
| peakmax_13 | traditional               |  157 |       8.89037  |     0.178344 |     0.312102 |          2.40093   |      1.24646 |            0.0700637  |
| peakmax_14 | phase_conformal_gated_cnn |  109 |       0.919607 |     0.587156 |     0.917431 |          0.0732091 |      1.41157 |            0.0917431  |
| peakmax_14 | ridge                     |  109 |       0.831336 |     0.559633 |     0.880734 |          0.128534  |      1.24455 |            0.12844    |
| peakmax_14 | gradient_boosted_trees    |  109 |       0.85302  |     0.53211  |     0.844037 |          0.132948  |      1.63472 |            0.119266   |
| peakmax_14 | mlp                       |  109 |       1.0454   |     0.477064 |     0.807339 |          0.141956  |      1.87924 |            0.0825688  |
| peakmax_14 | cnn1d                     |  109 |       1.16024  |     0.40367  |     0.963303 |          0.154038  |      1.54485 |            0.146789   |
| peakmax_14 | traditional               |  109 |       9.25791  |     0.266055 |     0.330275 |          2.45311   |      1.25263 |            0.12844    |
| peakmax_15 | gradient_boosted_trees    |  111 |       0.893259 |     0.567568 |     0.927928 |          0.0810179 |      1.87768 |            0.117117   |
| peakmax_15 | phase_conformal_gated_cnn |  111 |       1.10956  |     0.558559 |     0.927928 |          0.0931703 |      1.58674 |            0.117117   |
| peakmax_15 | ridge                     |  111 |       1.07817  |     0.54955  |     0.864865 |          0.105706  |      1.54481 |            0.108108   |
| peakmax_15 | mlp                       |  111 |       0.891175 |     0.513514 |     0.873874 |          0.124934  |      1.99636 |            0.135135   |
| peakmax_15 | cnn1d                     |  111 |       1.18288  |     0.351351 |     0.882883 |          0.200096  |      1.62379 |            0.126126   |
| peakmax_15 | traditional               |  111 |       9.15088  |     0.144144 |     0.225225 |          2.51146   |      1.26343 |            0.108108   |
| peakmax_16 | cnn1d                     |  114 |       0.943598 |     0.561404 |     0.95614  |          0.0738291 |      1.36792 |            0.0175439  |
| peakmax_16 | ridge                     |  114 |       1.00076  |     0.464912 |     0.95614  |          0.093257  |      1.35812 |            0.0438596  |
| peakmax_16 | phase_conformal_gated_cnn |  114 |       0.707757 |     0.631579 |     0.929825 |          0.117438  |      1.20149 |            0.0350877  |
| peakmax_16 | gradient_boosted_trees    |  114 |       0.636899 |     0.54386  |     0.894737 |          0.16663   |      1.66295 |            0.0526316  |
| peakmax_16 | mlp                       |  114 |       0.743536 |     0.517544 |     0.868421 |          0.171327  |      1.39978 |            0.0175439  |
| peakmax_16 | traditional               |  114 |       8.19107  |     0.192982 |     0.27193  |          2.23568   |      1.16131 |            0.0526316  |
| peakmax_17 | phase_conformal_gated_cnn |  252 |       0.907133 |     0.599206 |     0.944444 |          0.0667083 |      1.33405 |            0.0515873  |
| peakmax_17 | cnn1d                     |  252 |       1.00817  |     0.519841 |     0.936508 |          0.0731306 |      1.34465 |            0.0555556  |
| peakmax_17 | ridge                     |  252 |       0.969014 |     0.535714 |     0.972222 |          0.0757916 |      1.27289 |            0.0555556  |
| peakmax_17 | gradient_boosted_trees    |  252 |       0.872933 |     0.47619  |     0.900794 |          0.128152  |      1.88277 |            0.0753968  |
| peakmax_17 | mlp                       |  252 |       0.678718 |     0.511905 |     0.904762 |          0.165479  |      1.61071 |            0.0555556  |
| peakmax_17 | traditional               |  252 |       7.38349  |     0.234127 |     0.293651 |          2.01021   |      1.16906 |            0.0595238  |
| peakmax_3  | ridge                     |   42 |       1.03098  |     0.666667 |     1        |          0.0440086 |      1.66735 |            0          |
| peakmax_3  | cnn1d                     |   42 |       1.0133   |     0.571429 |     1        |          0.0729558 |      1.17556 |            0          |
| peakmax_3  | phase_conformal_gated_cnn |   42 |       0.85844  |     0.666667 |     0.97619  |          0.074698  |      1.17189 |            0          |
| peakmax_3  | mlp                       |   42 |       0.958302 |     0.642857 |     0.880952 |          0.078899  |      2.09466 |            0          |
| peakmax_3  | gradient_boosted_trees    |   42 |       0.780258 |     0.738095 |     0.952381 |          0.102006  |      1.29261 |            0.047619   |
| peakmax_3  | traditional               |   42 |       5.08325  |     0.309524 |     0.404762 |          1.36521   |      1.28085 |            0          |
| peakmax_4  | gradient_boosted_trees    |  520 |       0.905732 |     0.619231 |     0.938462 |          0.0577488 |      1.26494 |            0.00576923 |
| peakmax_4  | mlp                       |  520 |       1.01911  |     0.573077 |     0.940385 |          0.059873  |      1.45953 |            0.00961538 |
| peakmax_4  | phase_conformal_gated_cnn |  520 |       0.810331 |     0.692308 |     0.990385 |          0.0762641 |      1.22633 |            0          |
| peakmax_4  | ridge                     |  520 |       1.0724   |     0.463462 |     0.957692 |          0.107426  |      1.45649 |            0          |
| peakmax_4  | cnn1d                     |  520 |       0.938819 |     0.455769 |     0.978846 |          0.112554  |      1.25657 |            0          |
| peakmax_4  | traditional               |  520 |       5.0066   |     0.203846 |     0.269231 |          1.4365    |      1.23028 |            0          |
| peakmax_5  | mlp                       |  954 |       0.906863 |     0.575472 |     0.943396 |          0.0783379 |      1.38511 |            0.00419287 |
| peakmax_5  | gradient_boosted_trees    |  954 |       0.836633 |     0.589099 |     0.964361 |          0.0915585 |      1.22767 |            0.00524109 |
| peakmax_5  | phase_conformal_gated_cnn |  954 |       0.846152 |     0.774633 |     0.996855 |          0.0921871 |      1.27304 |            0.00104822 |
| peakmax_5  | cnn1d                     |  954 |       0.984316 |     0.469602 |     0.989518 |          0.098648  |      1.29142 |            0.00104822 |
| peakmax_5  | ridge                     |  954 |       0.713819 |     0.416143 |     0.981132 |          0.189741  |      1.16298 |            0.00209644 |
| peakmax_5  | traditional               |  954 |       8.67933  |     0.192872 |     0.291405 |          2.35049   |      1.19661 |            0          |
| peakmax_6  | phase_conformal_gated_cnn |  982 |       0.841938 |     0.726069 |     0.980652 |          0.0724827 |      1.34254 |            0          |
| peakmax_6  | mlp                       |  982 |       0.902209 |     0.559063 |     0.9389   |          0.08718   |      1.3792  |            0.00610998 |
| peakmax_6  | cnn1d                     |  982 |       0.962249 |     0.452138 |     0.973523 |          0.106078  |      1.2898  |            0.00203666 |
| peakmax_6  | gradient_boosted_trees    |  982 |       0.811598 |     0.544807 |     0.962322 |          0.109718  |      1.2647  |            0.00610998 |
| peakmax_6  | ridge                     |  982 |       0.702288 |     0.5      |     0.941955 |          0.154904  |      1.08781 |            0.00305499 |
| peakmax_6  | traditional               |  982 |       7.94852  |     0.200611 |     0.275967 |          2.17067   |      1.17541 |            0          |
| peakmax_7  | phase_conformal_gated_cnn | 1173 |       0.896685 |     0.632566 |     0.958227 |          0.055621  |      1.62202 |            0.00682012 |
| peakmax_7  | ridge                     | 1173 |       1.00163  |     0.515772 |     0.86786  |          0.0938044 |      1.51656 |            0.0136402  |
| peakmax_7  | cnn1d                     | 1173 |       1.06376  |     0.480818 |     0.921569 |          0.106874  |      1.64218 |            0.00937766 |
| peakmax_7  | mlp                       | 1173 |       1.07641  |     0.494459 |     0.880648 |          0.115697  |      1.65431 |            0.0144928  |
| peakmax_7  | gradient_boosted_trees    | 1173 |       1.09769  |     0.472293 |     0.868713 |          0.133964  |      1.6055  |            0.0144928  |
| peakmax_7  | traditional               | 1173 |       1.46045  |     0.369139 |     0.693095 |          0.329034  |      1.46042 |            0.0144928  |
| peakmax_8  | phase_conformal_gated_cnn | 2855 |       0.898278 |     0.631524 |     0.969177 |          0.0570311 |      1.6623  |            0.00630473 |
| peakmax_8  | cnn1d                     | 2855 |       0.999862 |     0.449737 |     0.937653 |          0.0971573 |      1.68218 |            0.00665499 |
| peakmax_8  | mlp                       | 2855 |       1.10265  |     0.485114 |     0.871804 |          0.129563  |      1.70877 |            0.0056042  |
| peakmax_8  | ridge                     | 2855 |       1.13147  |     0.474256 |     0.843082 |          0.151124  |      1.85542 |            0.0112084  |
| peakmax_8  | gradient_boosted_trees    | 2855 |       1.15138  |     0.477408 |     0.850438 |          0.152211  |      1.68966 |            0.00805604 |
| peakmax_8  | traditional               | 2855 |       1.28629  |     0.45289  |     0.777233 |          0.222535  |      1.82992 |            0.0136602  |
| peakmax_9  | phase_conformal_gated_cnn | 2911 |       0.904378 |     0.601855 |     0.961525 |          0.063246  |      1.73659 |            0.00755754 |
| peakmax_9  | cnn1d                     | 2911 |       1.02865  |     0.453109 |     0.92202  |          0.107801  |      1.70412 |            0.00824459 |
| peakmax_9  | gradient_boosted_trees    | 2911 |       1.12667  |     0.475438 |     0.823428 |          0.156851  |      1.70812 |            0.00687049 |
| peakmax_9  | traditional               | 2911 |       1.24104  |     0.519409 |     0.815527 |          0.171917  |      2.00591 |            0.0219856  |
| peakmax_9  | mlp                       | 2911 |       1.19484  |     0.479217 |     0.824802 |          0.171962  |      1.79118 |            0.00790106 |
| peakmax_9  | ridge                     | 2911 |       1.25414  |     0.478873 |     0.809    |          0.192841  |      1.92127 |            0.013741   |

Leading-edge phase atlas:

| stratum        | method                    |    n |   pull_width68 |   coverage68 |   coverage95 |   calibration_loss |   sigma68_ns |   tail_frac_abs_gt5ns |
|:---------------|:--------------------------|-----:|---------------:|-------------:|-------------:|-------------------:|-------------:|----------------------:|
| phase[0.0,0.2) | phase_conformal_gated_cnn | 1415 |       0.937731 |     0.623322 |     0.964664 |          0.0492479 |      1.45683 |            0.0134276  |
| phase[0.0,0.2) | mlp                       | 1415 |       1.06703  |     0.531449 |     0.886926 |          0.0980613 |      1.61435 |            0.014841   |
| phase[0.0,0.2) | gradient_boosted_trees    | 1415 |       1.04561  |     0.527208 |     0.876325 |          0.0986246 |      1.49333 |            0.014841   |
| phase[0.0,0.2) | ridge                     | 1415 |       1.00755  |     0.471378 |     0.882686 |          0.106372  |      1.50639 |            0.0190813  |
| phase[0.0,0.2) | cnn1d                     | 1415 |       1.06174  |     0.45159  |     0.939929 |          0.110724  |      1.41052 |            0.0141343  |
| phase[0.0,0.2) | traditional               | 1415 |       3.66415  |     0.354064 |     0.569611 |          0.931919  |      1.49325 |            0.0254417  |
| phase[0.2,0.4) | phase_conformal_gated_cnn | 3868 |       0.875242 |     0.645036 |     0.967942 |          0.0556689 |      1.51599 |            0.00956567 |
| phase[0.2,0.4) | cnn1d                     | 3868 |       1.00227  |     0.460445 |     0.943123 |          0.0906926 |      1.52526 |            0.0108583  |
| phase[0.2,0.4) | mlp                       | 3868 |       1.03843  |     0.505688 |     0.869183 |          0.106982  |      1.61395 |            0.012668   |
| phase[0.2,0.4) | gradient_boosted_trees    | 3868 |       1.02516  |     0.496122 |     0.864271 |          0.108402  |      1.53048 |            0.0139607  |
| phase[0.2,0.4) | ridge                     | 3868 |       1.0121   |     0.468459 |     0.873578 |          0.11202   |      1.58777 |            0.0131851  |
| phase[0.2,0.4) | traditional               | 3868 |       2.59711  |     0.393744 |     0.652017 |          0.619377  |      1.55074 |            0.0175801  |
| phase[0.4,0.6) | phase_conformal_gated_cnn | 3979 |       0.888718 |     0.650163 |     0.963559 |          0.0514203 |      1.52158 |            0.0108067  |
| phase[0.4,0.6) | cnn1d                     | 3979 |       1.01344  |     0.45338  |     0.938175 |          0.0980956 |      1.53958 |            0.0120633  |
| phase[0.4,0.6) | ridge                     | 3979 |       1.01551  |     0.486554 |     0.864036 |          0.109665  |      1.56435 |            0.0175924  |
| phase[0.4,0.6) | gradient_boosted_trees    | 3979 |       1.07628  |     0.492837 |     0.871073 |          0.120904  |      1.57992 |            0.0145765  |
| phase[0.4,0.6) | mlp                       | 3979 |       1.06448  |     0.489068 |     0.86278  |          0.121737  |      1.62908 |            0.0130686  |
| phase[0.4,0.6) | traditional               | 3979 |       2.23869  |     0.392561 |     0.65142  |          0.530437  |      1.55361 |            0.018095   |
| phase[0.6,0.8) | phase_conformal_gated_cnn | 1715 |       0.866419 |     0.641399 |     0.959184 |          0.0619986 |      1.59314 |            0.0139942  |
| phase[0.6,0.8) | cnn1d                     | 1715 |       1.00065  |     0.452478 |     0.927114 |          0.0987837 |      1.59053 |            0.0163265  |
| phase[0.6,0.8) | gradient_boosted_trees    | 1715 |       1.01166  |     0.496793 |     0.86414  |          0.104844  |      1.6356  |            0.0169096  |
| phase[0.6,0.8) | ridge                     | 1715 |       1.03013  |     0.497376 |     0.867638 |          0.107909  |      1.69561 |            0.0186589  |
| phase[0.6,0.8) | mlp                       | 1715 |       1.07882  |     0.494461 |     0.87172  |          0.119813  |      1.7215  |            0.0134111  |
| phase[0.6,0.8) | traditional               | 1715 |       2.35126  |     0.406997 |     0.650729 |          0.553427  |      1.68262 |            0.0198251  |
| phase[0.8,1.0) | phase_conformal_gated_cnn |  483 |       0.903626 |     0.596273 |     0.952381 |          0.0660576 |      1.34118 |            0.0165631  |
| phase[0.8,1.0) | gradient_boosted_trees    |  483 |       0.905976 |     0.587992 |     0.902692 |          0.0786476 |      1.40916 |            0.0227743  |
| phase[0.8,1.0) | ridge                     |  483 |       1.05042  |     0.507246 |     0.902692 |          0.0961363 |      1.53438 |            0.0165631  |
| phase[0.8,1.0) | cnn1d                     |  483 |       1.02192  |     0.469979 |     0.929607 |          0.0968544 |      1.36331 |            0.0144928  |
| phase[0.8,1.0) | mlp                       |  483 |       1.05746  |     0.52381  |     0.863354 |          0.110879  |      1.54209 |            0.0269151  |
| phase[0.8,1.0) | traditional               |  483 |       5.10696  |     0.26501  |     0.418219 |          1.38279   |      1.3587  |            0.0186335  |

Sample-window mask atlas:

| stratum                | method                    |    n |   pull_width68 |   coverage68 |   coverage95 |   calibration_loss |   sigma68_ns |   tail_frac_abs_gt5ns |
|:-----------------------|:--------------------------|-----:|---------------:|-------------:|-------------:|-------------------:|-------------:|----------------------:|
| artifact_sensitive_3_6 | phase_conformal_gated_cnn | 2498 |       0.844755 |     0.736589 |     0.988791 |          0.0774086 |      1.2878  |           0.000800641 |
| artifact_sensitive_3_6 | mlp                       | 2498 |       0.921038 |     0.569656 |     0.939952 |          0.0780665 |      1.40785 |           0.0060048   |
| artifact_sensitive_3_6 | gradient_boosted_trees    | 2498 |       0.834599 |     0.580464 |     0.957966 |          0.0910493 |      1.24625 |           0.00640512  |
| artifact_sensitive_3_6 | cnn1d                     | 2498 |       0.976611 |     0.461569 |     0.981185 |          0.100462  |      1.28905 |           0.00120096  |
| artifact_sensitive_3_6 | ridge                     | 2498 |       0.762051 |     0.463171 |     0.961169 |          0.152771  |      1.18427 |           0.00240192  |
| artifact_sensitive_3_6 | traditional               | 2498 |       8.02384  |     0.20016  |     0.282626 |          2.18717   |      1.18037 |           0           |
| delayed_or_edge_15_17  | phase_conformal_gated_cnn |  477 |       0.88692  |     0.597484 |     0.937107 |          0.071402  |      1.3504  |           0.0628931   |
| delayed_or_edge_15_17  | ridge                     |  477 |       1.00658  |     0.522013 |     0.943396 |          0.0719817 |      1.32513 |           0.0649895   |
| delayed_or_edge_15_17  | cnn1d                     |  477 |       1.02504  |     0.490566 |     0.928721 |          0.0902169 |      1.39053 |           0.0628931   |
| delayed_or_edge_15_17  | gradient_boosted_trees    |  477 |       0.829269 |     0.513627 |     0.90566  |          0.123626  |      1.86869 |           0.0796646   |
| delayed_or_edge_15_17  | mlp                       |  477 |       0.714242 |     0.513627 |     0.888889 |          0.160355  |      1.62562 |           0.0649895   |
| delayed_or_edge_15_17  | traditional               |  477 |       8.23406  |     0.203354 |     0.272537 |          2.24231   |      1.17045 |           0.0691824   |
| late_tail_12_14        | phase_conformal_gated_cnn |  429 |       0.913654 |     0.636364 |     0.932401 |          0.0567049 |      1.35387 |           0.0512821   |
| late_tail_12_14        | ridge                     |  429 |       0.907829 |     0.505828 |     0.93007  |          0.101757  |      1.28213 |           0.0629371   |
| late_tail_12_14        | gradient_boosted_trees    |  429 |       0.815557 |     0.575758 |     0.888112 |          0.110729  |      1.55179 |           0.0512821   |
| late_tail_12_14        | mlp                       |  429 |       0.922774 |     0.5338   |     0.848485 |          0.116465  |      1.66409 |           0.0582751   |
| late_tail_12_14        | cnn1d                     |  429 |       1.12355  |     0.421911 |     0.955711 |          0.134376  |      1.4613  |           0.0652681   |
| late_tail_12_14        | traditional               |  429 |       8.53406  |     0.235431 |     0.34965  |          2.27637   |      1.24758 |           0.0652681   |
| nominal_template_7_11  | phase_conformal_gated_cnn | 8056 |       0.895847 |     0.614945 |     0.959657 |          0.0604311 |      1.67031 |           0.00943396  |
| nominal_template_7_11  | cnn1d                     | 8056 |       1.01792  |     0.454196 |     0.92428  |          0.103818  |      1.67659 |           0.0100546   |
| nominal_template_7_11  | mlp                       | 8056 |       1.13038  |     0.478898 |     0.847319 |          0.147521  |      1.73726 |           0.0109235   |
| nominal_template_7_11  | ridge                     | 8056 |       1.12798  |     0.48287  |     0.836643 |          0.149436  |      1.82699 |           0.0153923   |
| nominal_template_7_11  | gradient_boosted_trees    | 8056 |       1.12997  |     0.474181 |     0.83925  |          0.152213  |      1.69116 |           0.0109235   |
| nominal_template_7_11  | traditional               | 8056 |       1.33436  |     0.461023 |     0.776068 |          0.23194   |      1.86995 |           0.0182473   |

Largest traditional local-calibration failures:

| dimension          | stratum                       | method      |    n |   pull_width68 |   coverage68 |   coverage95 |   calibration_loss |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |
|:-------------------|:------------------------------|:------------|-----:|---------------:|-------------:|-------------:|-------------------:|-------------:|--------------:|----------------------:|
| p09_anomaly_class  | dropout                       | traditional |   27 |       10.9118  |     0        |    0.0740741 |            3.06243 |      2.00566 |       8.12679 |             0.148148  |
| peak_sample_bin    | peakmax_15                    | traditional |  111 |        9.15088 |     0.144144 |    0.225225  |            2.51146 |      1.26343 |       5.64826 |             0.108108  |
| peak_sample_bin    | peakmax_14                    | traditional |  109 |        9.25791 |     0.266055 |    0.330275  |            2.45311 |      1.25263 |       6.2251  |             0.12844   |
| peak_sample_bin    | peakmax_13                    | traditional |  157 |        8.89037 |     0.178344 |    0.312102  |            2.40093 |      1.24646 |       5.73834 |             0.0700637 |
| p09_anomaly_class  | pileup_or_long_tail           | traditional |   16 |        7.02574 |     0.1875   |    0.3125    |            2.38614 |      1.32411 |       1.731   |             0.0625    |
| peak_sample_bin    | peakmax_5                     | traditional |  954 |        8.67933 |     0.192872 |    0.291405  |            2.35049 |      1.19661 |       1.09241 |             0         |
| sample_window_mask | late_tail_12_14               | traditional |  429 |        8.53406 |     0.235431 |    0.34965   |            2.27637 |      1.24758 |       5.21739 |             0.0652681 |
| p09_anomaly_class  | novel_delayed_peak            | traditional |  571 |        8.40638 |     0.217163 |    0.285464  |            2.27537 |      1.18095 |       5.11019 |             0.0770578 |
| sample_window_mask | delayed_or_edge_15_17         | traditional |  477 |        8.23406 |     0.203354 |    0.272537  |            2.24231 |      1.17045 |       5.23862 |             0.0691824 |
| peak_sample_bin    | peakmax_16                    | traditional |  114 |        8.19107 |     0.192982 |    0.27193   |            2.23568 |      1.16131 |       2.77921 |             0.0526316 |
| sample_window_mask | artifact_sensitive_3_6        | traditional | 2498 |        8.02384 |     0.20016  |    0.282626  |            2.18717 |      1.18037 |       1.12051 |             0         |
| peak_sample_bin    | peakmax_6                     | traditional |  982 |        7.94852 |     0.200611 |    0.275967  |            2.17067 |      1.17541 |       1.16044 |             0         |
| p09_anomaly_class  | novel_broad_template_mismatch | traditional |   26 |        7.28326 |     0.115385 |    0.230769  |            2.05327 |      9.6144  |      13.7844  |             0.5       |
| baseline_bin       | baseline_rms[64,inf)          | traditional | 3067 |        7.64153 |     0.216498 |    0.372351  |            2.05182 |      1.16796 |       3.48029 |             0.018911  |
| peak_sample_bin    | peakmax_17                    | traditional |  252 |        7.38349 |     0.234127 |    0.293651  |            2.01021 |      1.16906 |       5.78235 |             0.0595238 |
| peak_sample_bin    | peakmax_12                    | traditional |  163 |        7.55663 |     0.269939 |    0.398773  |            2.00065 |      1.33039 |       3.57252 |             0.0184049 |
| q_template_bin     | q_template[0.2,inf)           | traditional | 4551 |        7.31942 |     0.254669 |    0.421885  |            1.9384  |      1.19371 |       3.12565 |             0.0186772 |
| peak_sample_bin    | peakmax_4                     | traditional |  520 |        5.0066  |     0.203846 |    0.269231  |            1.4365  |      1.23028 |       1.06873 |             0         |
| peak_sample_bin    | peakmax_3                     | traditional |   42 |        5.08325 |     0.309524 |    0.404762  |            1.36521 |      1.28085 |       1.19024 |             0         |
| p09_anomaly_class  | novel_early_pretrigger        | traditional |  298 |        3.75262 |     0.285235 |    0.402685  |            1.04244 |      1.31998 |       3.97116 |             0.0268456 |

Best ML-minus-traditional local deltas. Negative calibration-loss delta means the ML uncertainty model is better calibrated in the matched stratum:

| dimension          | stratum         | method                    |   traditional_calibration_loss |   calibration_loss |   ml_minus_traditional_calibration_loss |   traditional_pull_width68 |   pull_width68 |   ml_minus_traditional_pull_width68 |   traditional_coverage68 |   coverage68 |   ml_minus_traditional_coverage68 |
|:-------------------|:----------------|:--------------------------|-------------------------------:|-------------------:|----------------------------------------:|---------------------------:|---------------:|------------------------------------:|-------------------------:|-------------:|----------------------------------:|
| peak_sample_bin    | peakmax_15      | gradient_boosted_trees    |                        2.51146 |          0.0810179 |                                -2.43045 |                    9.15088 |       0.893259 |                            -8.25762 |                 0.144144 |     0.567568 |                          0.423423 |
| peak_sample_bin    | peakmax_15      | phase_conformal_gated_cnn |                        2.51146 |          0.0931703 |                                -2.41829 |                    9.15088 |       1.10956  |                            -8.04132 |                 0.144144 |     0.558559 |                          0.414414 |
| peak_sample_bin    | peakmax_15      | ridge                     |                        2.51146 |          0.105706  |                                -2.40576 |                    9.15088 |       1.07817  |                            -8.07271 |                 0.144144 |     0.54955  |                          0.405405 |
| peak_sample_bin    | peakmax_15      | mlp                       |                        2.51146 |          0.124934  |                                -2.38653 |                    9.15088 |       0.891175 |                            -8.2597  |                 0.144144 |     0.513514 |                          0.369369 |
| peak_sample_bin    | peakmax_14      | phase_conformal_gated_cnn |                        2.45311 |          0.0732091 |                                -2.3799  |                    9.25791 |       0.919607 |                            -8.3383  |                 0.266055 |     0.587156 |                          0.321101 |
| peak_sample_bin    | peakmax_13      | phase_conformal_gated_cnn |                        2.40093 |          0.0614809 |                                -2.33945 |                    8.89037 |       0.862201 |                            -8.02817 |                 0.178344 |     0.66242  |                          0.484076 |
| peak_sample_bin    | peakmax_14      | ridge                     |                        2.45311 |          0.128534  |                                -2.32458 |                    9.25791 |       0.831336 |                            -8.42657 |                 0.266055 |     0.559633 |                          0.293578 |
| peak_sample_bin    | peakmax_14      | gradient_boosted_trees    |                        2.45311 |          0.132948  |                                -2.32016 |                    9.25791 |       0.85302  |                            -8.40489 |                 0.266055 |     0.53211  |                          0.266055 |
| peak_sample_bin    | peakmax_15      | cnn1d                     |                        2.51146 |          0.200096  |                                -2.31137 |                    9.15088 |       1.18288  |                            -7.968   |                 0.144144 |     0.351351 |                          0.207207 |
| peak_sample_bin    | peakmax_14      | mlp                       |                        2.45311 |          0.141956  |                                -2.31116 |                    9.25791 |       1.0454   |                            -8.21251 |                 0.266055 |     0.477064 |                          0.211009 |
| peak_sample_bin    | peakmax_14      | cnn1d                     |                        2.45311 |          0.154038  |                                -2.29907 |                    9.25791 |       1.16024  |                            -8.09767 |                 0.266055 |     0.40367  |                          0.137615 |
| peak_sample_bin    | peakmax_13      | ridge                     |                        2.40093 |          0.107415  |                                -2.29352 |                    8.89037 |       0.897743 |                            -7.99262 |                 0.178344 |     0.496815 |                          0.318471 |
| peak_sample_bin    | peakmax_13      | cnn1d                     |                        2.40093 |          0.109935  |                                -2.291   |                    8.89037 |       1.02669  |                            -7.86367 |                 0.178344 |     0.433121 |                          0.254777 |
| peak_sample_bin    | peakmax_5       | mlp                       |                        2.35049 |          0.0783379 |                                -2.27215 |                    8.67933 |       0.906863 |                            -7.77247 |                 0.192872 |     0.575472 |                          0.3826   |
| peak_sample_bin    | peakmax_13      | gradient_boosted_trees    |                        2.40093 |          0.137897  |                                -2.26304 |                    8.89037 |       0.72677  |                            -8.1636  |                 0.178344 |     0.579618 |                          0.401274 |
| peak_sample_bin    | peakmax_5       | gradient_boosted_trees    |                        2.35049 |          0.0915585 |                                -2.25893 |                    8.67933 |       0.836633 |                            -7.8427  |                 0.192872 |     0.589099 |                          0.396226 |
| peak_sample_bin    | peakmax_5       | phase_conformal_gated_cnn |                        2.35049 |          0.0921871 |                                -2.2583  |                    8.67933 |       0.846152 |                            -7.83318 |                 0.192872 |     0.774633 |                          0.581761 |
| peak_sample_bin    | peakmax_5       | cnn1d                     |                        2.35049 |          0.098648  |                                -2.25184 |                    8.67933 |       0.984316 |                            -7.69502 |                 0.192872 |     0.469602 |                          0.27673  |
| peak_sample_bin    | peakmax_13      | mlp                       |                        2.40093 |          0.153036  |                                -2.2479  |                    8.89037 |       0.717169 |                            -8.1732  |                 0.178344 |     0.55414  |                          0.375796 |
| sample_window_mask | late_tail_12_14 | phase_conformal_gated_cnn |                        2.27637 |          0.0567049 |                                -2.21966 |                    8.53406 |       0.913654 |                            -7.6204  |                 0.235431 |     0.636364 |                          0.400932 |

## Sentinels And Falsification

Pre-registration: the ticket required pull width, nominal 68% and 95% coverage, sigma68/full RMS, >5 ns tail fraction, support, calibration ECE, and ML-minus-traditional deltas under run-block bootstrap. A model would be falsified as an uncertainty improvement if its pooled calibration-loss CI failed to beat the robust-width baseline or if shuffled/run/topology-only sentinels matched it.

| sentinel        | method                    |     n |   calibration_loss |   pull_width68 |   coverage68 |   coverage95 |   calibration_ece |   sigma68_ns |
|:----------------|:--------------------------|------:|-------------------:|---------------:|-------------:|-------------:|------------------:|-------------:|
| amplitude_only  | ridge_uncertainty_control | 11460 |           0.120844 |        1.02596 |     0.465532 |     0.862216 |          0.15247  |      1.55109 |
| topology_only   | ridge_uncertainty_control | 11460 |           0.107566 |        1.03123 |     0.533159 |     0.837435 |          0.136935 |      1.55109 |
| run_family_only | ridge_uncertainty_control | 11460 |           0.123656 |        1.02452 |     0.461344 |     0.857941 |          0.156703 |      1.55109 |
| shuffled_target | ridge_uncertainty_control | 11460 |           0.121054 |        1.02851 |     0.468412 |     0.860471 |          0.151903 |      1.55109 |

Leakage and bookkeeping checks:

| check                                | value                                                                        | pass   | note                                                                                         |
|:-------------------------------------|:-----------------------------------------------------------------------------|:-------|:---------------------------------------------------------------------------------------------|
| raw_root_reproduction_gate           | 1                                                                            | True   | reproduction_match_table.csv exact before modeling                                           |
| required_methods_present             | cnn1d,gradient_boosted_trees,mlp,phase_conformal_gated_cnn,ridge,traditional | True   | traditional, ridge, GBT, MLP, 1D-CNN, and new phase-conformal gated CNN                      |
| uncertainty_train_eval_event_overlap | 0                                                                            | True   | uncertainty layer leaves out the evaluated run                                               |
| forbidden_feature_audit              | 0                                                                            | True   | uncertainty features exclude event id, raw residual, pull, sigma target, and held-out labels |

Uncertainty fold metadata sample:

| method                    |   heldout_run |    scale |   groups |   feature_count | feature_mode   |   shuffle_target |   gated |
|:--------------------------|--------------:|---------:|---------:|----------------:|:---------------|-----------------:|--------:|
| traditional               |            58 | 1        |      199 |             nan | nan            |              nan |     nan |
| traditional               |            59 | 1        |      195 |             nan | nan            |              nan |     nan |
| traditional               |            60 | 1        |      182 |             nan | nan            |              nan |     nan |
| traditional               |            61 | 1        |      184 |             nan | nan            |              nan |     nan |
| traditional               |            62 | 1        |      188 |             nan | nan            |              nan |     nan |
| traditional               |            63 | 1        |      195 |             nan | nan            |              nan |     nan |
| traditional               |            65 | 1        |      198 |             nan | nan            |              nan |     nan |
| ridge                     |            58 | 1.02357  |      nan |              70 | full           |                0 |     nan |
| ridge                     |            59 | 1.00729  |      nan |              70 | full           |                0 |     nan |
| ridge                     |            60 | 1.02254  |      nan |              70 | full           |                0 |     nan |
| ridge                     |            61 | 1.04213  |      nan |              70 | full           |                0 |     nan |
| ridge                     |            62 | 1.01614  |      nan |              70 | full           |                0 |     nan |
| ridge                     |            63 | 1.01445  |      nan |              70 | full           |                0 |     nan |
| ridge                     |            65 | 1.02122  |      nan |              70 | full           |                0 |     nan |
| gradient_boosted_trees    |            58 | 0.996605 |      nan |              70 | full           |                0 |     nan |
| gradient_boosted_trees    |            59 | 1.00276  |      nan |              70 | full           |                0 |     nan |
| gradient_boosted_trees    |            60 | 0.993334 |      nan |              70 | full           |                0 |     nan |
| gradient_boosted_trees    |            61 | 0.995773 |      nan |              70 | full           |                0 |     nan |
| gradient_boosted_trees    |            62 | 0.982997 |      nan |              70 | full           |                0 |     nan |
| gradient_boosted_trees    |            63 | 0.988978 |      nan |              70 | full           |                0 |     nan |
| gradient_boosted_trees    |            65 | 1.00033  |      nan |              70 | full           |                0 |     nan |
| mlp                       |            58 | 1.01138  |      nan |              70 | full           |                0 |     nan |
| mlp                       |            59 | 0.977437 |      nan |              70 | full           |                0 |     nan |
| mlp                       |            60 | 1.0142   |      nan |              70 | full           |                0 |     nan |
| mlp                       |            61 | 1.00083  |      nan |              70 | full           |                0 |     nan |
| mlp                       |            62 | 1.00467  |      nan |              70 | full           |                0 |     nan |
| mlp                       |            63 | 1.01054  |      nan |              70 | full           |                0 |     nan |
| mlp                       |            65 | 1.00665  |      nan |              70 | full           |                0 |     nan |
| cnn1d                     |            58 | 0.86768  |      nan |              70 | nan            |              nan |       0 |
| cnn1d                     |            59 | 0.947109 |      nan |              70 | nan            |              nan |       0 |
| cnn1d                     |            60 | 0.869325 |      nan |              70 | nan            |              nan |       0 |
| cnn1d                     |            61 | 0.905466 |      nan |              70 | nan            |              nan |       0 |
| cnn1d                     |            62 | 0.92161  |      nan |              70 | nan            |              nan |       0 |
| cnn1d                     |            63 | 0.862752 |      nan |              70 | nan            |              nan |       0 |
| cnn1d                     |            65 | 0.902199 |      nan |              70 | nan            |              nan |       0 |
| phase_conformal_gated_cnn |            58 | 0.910749 |      nan |              70 | nan            |              nan |       1 |
| phase_conformal_gated_cnn |            59 | 0.915221 |      nan |              70 | nan            |              nan |       1 |
| phase_conformal_gated_cnn |            60 | 1.01292  |      nan |              70 | nan            |              nan |       1 |
| phase_conformal_gated_cnn |            61 | 0.927182 |      nan |              70 | nan            |              nan |       1 |
| phase_conformal_gated_cnn |            62 | 0.876385 |      nan |              70 | nan            |              nan |       1 |

## Systematics

- Run-block bootstrap captures run-to-run and event-level correlation, but not alternate electronics calibrations or ROOT branch decoding faults.
- The pull target uses same-particle downstream pair residuals, so pair correlations can make an individual stave uncertainty look better calibrated than it would under an external clock.
- The traditional lookup is intentionally strong but still atom-binned; sparse anomaly bins fall back to coarser support and can hide sharp local effects.
- Neural scale models are compact CPU-scale networks. Larger GPU models might improve calibration but would need the same run-external conformal checks.
- The 95% coverage target assumes a Gaussian pull convention (`1.96 sigma`). Heavy tails are also reported directly through full RMS and >5 ns tail fraction.

## Caveats And Interpretation

This atlas is an uncertainty-calibration product, not a replacement for absolute timing alignment. The strongest practical use is to propagate local pull inflation or abstention flags into PID, energy, pile-up, and covariance consumers, especially for peak samples 3-6, high q-template mismatch, wide baseline, and anomaly-like waveform atoms.

## Reproducibility

Regenerate the study with:

```bash
python scripts/p06c_1781131868_2067_7f7516d4_atom_conditioned_timing_uncertainty.py --config configs/p06c_1781131868_2067_7f7516d4_atom_conditioned_timing_uncertainty.json
```

Main artifacts: `result.json`, `REPORT.md`, `manifest.json`, `reproduction_match_table.csv`, `s03a_reproduction_benchmark.csv`, `pair_residual_rows_with_pulls.csv.gz`, `coverage_summary.csv`, `method_delta_vs_traditional.csv`, `sentinel_checks.csv`, `uncertainty_fold_meta.csv`, `leakage_checks.csv`, `input_sha256.csv`, `fig_method_calibration_loss.png`, and `fig_peak_sample_pull_width.png`.

