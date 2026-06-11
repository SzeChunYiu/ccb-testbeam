# S06c: timewalk-energy support closure after action bands

- **Ticket:** `1781056892.649.4cbb3cd2`
- **Worker:** `testbeam-laptop-4`
- **Date:** `2026-06-11`
- **Depends on:** S00 raw ROOT selected-pulse gate; P06c/S06b run-external timing-uncertainty panel
- **Input:** raw B-stack ROOT under `data/root/root` plus committed pair-residual rows listed in `source_benchmark_rows.json`
- **Split:** leave-one-run-out by run over 58, 59, 60, 61, 62, 63, 65
- **Bootstrap:** event-paired run-block bootstrap, 200 replicates

## 0. Question

After applying the current timing, saturation, dropout/anomaly, baseline, q-template, and amplitude/charge energy-support action bands, do the same-particle downstream timing residuals have stable enough resolution and calibrated pulls for S06 consumers, and does any ML/NN method beat the strong traditional baseline on the accepted support?

The pre-registered decision metric is pooled accepted-support pull-calibration loss. The constraints are reported simultaneously: `sigma68`, full RMS, >5 ns tail fraction, pull width, 68% and 95% coverage, accepted-support composition, amplitude/charge bias slopes, and run-held-out bootstrap CIs.

## 1. Reproduction Gate

The raw ROOT reproduction is independent of the committed benchmark rows. For every configured B-stack ROOT file, `HRDv` is reshaped to 8 channels by 18 samples, the median of samples 0-3 is subtracted, and a B-stave pulse is selected when its baseline-subtracted maximum exceeds 1000 ADC.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The S03a analytic timewalk reference is also rerun before interpreting the closure rows:

| method                  |   value |   ci_low |   ci_high |   n_pair_residuals | best_candidate   |   best_alpha |
|:------------------------|--------:|---------:|----------:|-------------------:|:-----------------|-------------:|
| s02_template_phase_base | 2.88915 |  2.63915 |   3.27718 |                198 | amp_only         |          100 |
| s03a_analytic_timewalk  | 1.49464 |  1.33581 |   1.61242 |                198 | amp_only         |          100 |

## 2. Methods And Equations

For event `e`, stave `s`, and method `m`, the geometry-corrected timestamp is

`tau_{e,s,m}=t_{e,s,m}-x_s v_TOF`, with `v_TOF=0.078 ns/cm`.

The downstream pair residual is

`r_{e,a,b,m}=tau_{e,a,m}-tau_{e,b,m}`, for B4-B6, B4-B8, and B6-B8.

The robust width is `sigma68(r)=(Q84(r)-Q16(r))/2`, and full RMS is computed about the mean. Each uncertainty method predicts `sigma_hat`; the pull is `z=r/sigma_hat`. The calibration loss is

`L = mean(|sigma68(z)-1|, |P(|z|<=1)-0.682689|, |P(|z|<=1.96)-0.95|, ECE)`,

where ECE is the sigma-quantile-bin weighted average of absolute 68% and 95% coverage errors. Lower is better. Bias slopes are ordinary least-squares slopes of residual median against the amplitude or charge-bin midpoint; they are diagnostic rather than the winner metric.

Action-band acceptance is deterministic and uses no residual magnitude: nominal peak window 7-11, peak-sample delta <= 2, no saturation proxy, no dropout/noncommon P09 anomaly, baseline RMS < 32 ADC, q-template RMSE < 0.08, 1500 <= mean amplitude < 7000 ADC, and 8000 <= mean charge proxy < 40000 ADC samples.

Traditional baseline: fold-local S02 template-phase timing plus S03a amplitude-only analytic timewalk, with an S04-style robust-width lookup over pair, timing phase/mask atoms, and coarser fallbacks. This is a strong traditional comparator because it uses known timing physics and calibrated atom bins without training on the held-out run.

ML/NN methods: ridge, HistGradientBoosting, MLP, 1D-CNN, and a new phase-conformal atom-gated CNN. The new architecture encodes the two normalized pair waveforms with 1D convolutions, gates convolution channels with tabular support atoms, and applies a run-external conformal phase-bin scale. All methods are scored on the same held-out pair residuals.

## 3. Head-To-Head Benchmark

Full support before action-band acceptance:

| method                    | method_label                              |     n |   calibration_loss |   calibration_loss_ci_low |   calibration_loss_ci_high |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   pull_width68 |   coverage68 |   coverage95 |
|:--------------------------|:------------------------------------------|------:|-------------------:|--------------------------:|---------------------------:|-------------:|--------------:|----------------------:|---------------:|-------------:|-------------:|
| phase_conformal_gated_cnn | Phase-conformal atom-gated CNN            | 11460 |          0.0534484 |                 0.0417656 |                  0.0716527 |      1.50399 |       2.41532 |             0.0114311 |       0.901022 |     0.631937 |     0.960995 |
| cnn1d                     | 1D-CNN residual scale model               | 11460 |          0.0973354 |                 0.0818516 |                  0.159682  |      1.5101  |       2.42042 |             0.0129145 |       1.00983  |     0.454538 |     0.936126 |
| mlp                       | MLP residual scale model                  | 11460 |          0.103472  |                 0.0705131 |                  0.165041  |      1.64477 |       2.42453 |             0.0138743 |       1.05182  |     0.516928 |     0.876003 |
| gradient_boosted_trees    | HistGradientBoosting residual scale model | 11460 |          0.109007  |                 0.0754915 |                  0.226666  |      1.5543  |       2.31556 |             0.0153578 |       1.0451   |     0.502792 |     0.869721 |
| ridge                     | Ridge residual scale model                | 11460 |          0.110021  |                 0.0801671 |                  0.207816  |      1.57318 |       2.54659 |             0.0161431 |       1.02024  |     0.481065 |     0.871728 |
| traditional               | S02/S03/S04 atom robust-width baseline    | 11460 |          0.659059  |                 0.560172  |                  0.779231  |      1.55109 |       2.66699 |             0.0191099 |       2.71207  |     0.384991 |     0.631588 |

Accepted support after action bands:

| method                    | method_label                              |    n |   calibration_loss |   calibration_loss_ci_low |   calibration_loss_ci_high |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   pull_width68 |   coverage68 |   coverage95 |
|:--------------------------|:------------------------------------------|-----:|-------------------:|--------------------------:|---------------------------:|-------------:|--------------------:|---------------------:|--------------:|----------------------:|---------------:|-------------:|-------------:|
| phase_conformal_gated_cnn | Phase-conformal atom-gated CNN            | 3095 |          0.0748153 |                 0.0542841 |                   0.106241 |      1.63093 |             1.46285 |              1.79955 |       1.55533 |           0.000969305 |       0.851297 |     0.614863 |     0.969305 |
| cnn1d                     | 1D-CNN residual scale model               | 3095 |          0.104678  |                 0.0905747 |                   0.16357  |      1.67444 |             1.50354 |              1.91325 |       1.62009 |           0.00161551  |       0.96937  |     0.452019 |     0.935703 |
| mlp                       | MLP residual scale model                  | 3095 |          0.125722  |                 0.0777587 |                   0.197859 |      1.69535 |             1.55193 |              1.88858 |       1.63691 |           0.000969305 |       1.0886   |     0.485945 |     0.873344 |
| gradient_boosted_trees    | HistGradientBoosting residual scale model | 3095 |          0.134938  |                 0.0763808 |                   0.28125  |      1.64027 |             1.3947  |              1.94673 |       1.60736 |           0.000969305 |       1.08169  |     0.476575 |     0.852666 |
| ridge                     | Ridge residual scale model                | 3095 |          0.142737  |                 0.0740575 |                   0.288415 |      1.84718 |             1.51092 |              2.18222 |       1.80132 |           0.00420032  |       1.10044  |     0.474313 |     0.846204 |
| traditional               | S02/S03/S04 atom robust-width baseline    | 3095 |          0.203856  |                 0.0919344 |                   0.384142 |      1.84325 |             1.56036 |              2.20429 |       1.88008 |           0.00775444  |       1.27156  |     0.482714 |     0.787399 |

Verdict: the accepted-support winner is **phase_conformal_gated_cnn** with calibration loss **0.0748** and 95% CI **[0.0543, 0.1062]**. The traditional baseline has loss **0.2039** with CI **[0.0919, 0.3841]**. The best ML-minus-traditional loss delta is **-0.1290** and the sigma68 delta is **-0.2123 ns**.

Per-run accepted-support bootstrap scores:

|   run | method                    |   n |   calibration_loss |   calibration_loss_ci_low |   calibration_loss_ci_high |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   pull_width68 |   coverage68 |   coverage95 |
|------:|:--------------------------|----:|-------------------:|--------------------------:|---------------------------:|-------------:|--------------------:|---------------------:|--------------:|----------------------:|---------------:|-------------:|-------------:|
|    58 | traditional               |  32 |          0.108026  |                 0.0871303 |                  0.279598  |      1.53996 |            0.827277 |              2.23464 |       1.45508 |            0          |       0.991029 |     0.46875  |     0.90625  |
|    58 | mlp                       |  32 |          0.174166  |                 0.123086  |                  0.327799  |      1.33822 |            0.706316 |              1.84431 |       1.30221 |            0          |       0.867094 |     0.34375  |     0.9375   |
|    58 | gradient_boosted_trees    |  32 |          0.216564  |                 0.116958  |                  0.436344  |      1.66801 |            0.858568 |              1.98197 |       1.3679  |            0          |       1.21566  |     0.375    |     0.84375  |
|    58 | cnn1d                     |  32 |          0.239741  |                 0.173582  |                  0.382409  |      1.39545 |            0.764786 |              1.88189 |       1.30653 |            0          |       0.785384 |     0.21875  |     0.96875  |
|    58 | ridge                     |  32 |          0.242009  |                 0.149195  |                  0.355942  |      1.06446 |            0.897873 |              1.9086  |       1.30386 |            0          |       0.62643  |     0.4375   |     0.84375  |
|    58 | phase_conformal_gated_cnn |  32 |          0.242992  |                 0.143236  |                  0.315732  |      1.28352 |            0.701435 |              1.67665 |       1.25173 |            0          |       0.470818 |     0.4375   |     1        |
|    59 | phase_conformal_gated_cnn | 643 |          0.0866359 |                 0.0655544 |                  0.110444  |      1.53499 |            1.41205  |              1.62721 |       1.4616  |            0.00155521 |       0.802515 |     0.617418 |     0.973561 |
|    59 | traditional               | 643 |          0.0916481 |                 0.0582654 |                  0.131359  |      1.58338 |            1.51798  |              1.77856 |       1.67381 |            0.00466563 |       1.07774  |     0.578538 |     0.861586 |
|    59 | gradient_boosted_trees    | 643 |          0.105721  |                 0.0844402 |                  0.14975   |      1.47686 |            1.31964  |              1.57681 |       1.44552 |            0          |       1.01506  |     0.506998 |     0.85381  |
|    59 | mlp                       | 643 |          0.108325  |                 0.0904089 |                  0.131135  |      1.50581 |            1.40979  |              1.68921 |       1.52986 |            0          |       0.955003 |     0.505443 |     0.870918 |
|    59 | ridge                     | 643 |          0.117864  |                 0.088209  |                  0.170606  |      1.5976  |            1.50136  |              1.77563 |       1.61049 |            0          |       1.05197  |     0.494557 |     0.858476 |
|    59 | cnn1d                     | 643 |          0.131059  |                 0.109374  |                  0.157373  |      1.52264 |            1.44218  |              1.62485 |       1.46607 |            0.00155521 |       0.909012 |     0.413686 |     0.942457 |
|    60 | phase_conformal_gated_cnn | 731 |          0.0805483 |                 0.0680619 |                  0.102147  |      1.38702 |            1.28777  |              1.48611 |       1.36066 |            0          |       0.802634 |     0.642955 |     0.968536 |
|    60 | gradient_boosted_trees    | 731 |          0.085894  |                 0.0703414 |                  0.109098  |      1.33619 |            1.25089  |              1.4846  |       1.38807 |            0.00273598 |       0.951012 |     0.522572 |     0.915185 |
|    60 | traditional               | 731 |          0.08703   |                 0.070323  |                  0.117388  |      1.47039 |            1.38546  |              1.65553 |       1.53112 |            0.00273598 |       0.985319 |     0.540356 |     0.870041 |
|    60 | cnn1d                     | 731 |          0.0929788 |                 0.0723321 |                  0.113843  |      1.49946 |            1.41503  |              1.62162 |       1.48349 |            0.00136799 |       0.871168 |     0.5513   |     0.93844  |
|    60 | ridge                     | 731 |          0.115498  |                 0.0909211 |                  0.129988  |      1.39404 |            1.31369  |              1.5134  |       1.48585 |            0.00273598 |       0.810091 |     0.555404 |     0.900137 |
|    60 | mlp                       | 731 |          0.128164  |                 0.0985486 |                  0.16474   |      1.55017 |            1.44822  |              1.64302 |       1.53302 |            0.00136799 |       1.1076   |     0.478796 |     0.885089 |
|    61 | phase_conformal_gated_cnn | 686 |          0.121308  |                 0.0980883 |                  0.148605  |      1.87768 |            1.76295  |              2.0132  |       1.75313 |            0          |       0.876413 |     0.473761 |     0.98105  |
|    61 | cnn1d                     | 686 |          0.219405  |                 0.188127  |                  0.2574    |      2.09886 |            1.98104  |              2.21436 |       1.92692 |            0.00145773 |       1.20454  |     0.281341 |     0.913994 |
|    61 | mlp                       | 686 |          0.235868  |                 0.197176  |                  0.271724  |      1.95143 |            1.83847  |              2.04368 |       1.83272 |            0.00145773 |       1.27869  |     0.379009 |     0.810496 |
|    61 | gradient_boosted_trees    | 686 |          0.369221  |                 0.317273  |                  0.41428   |      2.02284 |            1.92819  |              2.16536 |       1.91956 |            0.00145773 |       1.47537  |     0.272595 |     0.69242  |
|    61 | ridge                     | 686 |          0.406187  |                 0.35565   |                  0.441749  |      2.4199  |            2.27282  |              2.55395 |       2.23786 |            0.0116618  |       1.54889  |     0.249271 |     0.666181 |
|    61 | traditional               | 686 |          0.507077  |                 0.474278  |                  0.549124  |      2.36402 |            2.29179  |              2.56993 |       2.31734 |            0.0204082  |       1.78846  |     0.268222 |     0.537901 |
|    62 | mlp                       | 655 |          0.0717592 |                 0.0553966 |                  0.101154  |      1.69168 |            1.58978  |              1.80378 |       1.59896 |            0          |       0.973704 |     0.557252 |     0.914504 |
|    62 | ridge                     | 655 |          0.0733027 |                 0.0564846 |                  0.101868  |      1.76587 |            1.62908  |              1.91002 |       1.69085 |            0.00152672 |       0.956052 |     0.554198 |     0.925191 |
|    62 | phase_conformal_gated_cnn | 655 |          0.0763037 |                 0.0548373 |                  0.10088   |      1.61567 |            1.52246  |              1.70308 |       1.51714 |            0          |       0.850735 |     0.732824 |     0.951145 |
|    62 | gradient_boosted_trees    | 655 |          0.0831544 |                 0.062895  |                  0.107335  |      1.601   |            1.50077  |              1.68992 |       1.53953 |            0          |       0.905959 |     0.569466 |     0.919084 |
|    62 | cnn1d                     | 655 |          0.0866202 |                 0.0670409 |                  0.111593  |      1.63521 |            1.5339   |              1.71198 |       1.55609 |            0          |       0.901256 |     0.543511 |     0.941985 |
|    62 | traditional               | 655 |          0.140956  |                 0.104667  |                  0.179041  |      1.81457 |            1.61214  |              1.95432 |       1.75595 |            0.00305344 |       1.16507  |     0.514504 |     0.854962 |
|    63 | ridge                     | 298 |          0.05139   |                 0.0350025 |                  0.107474  |      1.67627 |            1.5572   |              1.89154 |       1.64432 |            0.0033557  |       1.0168   |     0.587248 |     0.932886 |
|    63 | phase_conformal_gated_cnn | 298 |          0.0544348 |                 0.038932  |                  0.109309  |      1.66243 |            1.47949  |              1.9481  |       1.66633 |            0          |       0.934051 |     0.614094 |     0.969799 |
|    63 | mlp                       | 298 |          0.0570423 |                 0.0439524 |                  0.122335  |      1.65406 |            1.47055  |              1.80407 |       1.60347 |            0          |       0.999518 |     0.587248 |     0.909396 |
|    63 | gradient_boosted_trees    | 298 |          0.0642062 |                 0.0420942 |                  0.0997588 |      1.57319 |            1.42738  |              1.71067 |       1.56386 |            0.0033557  |       0.937008 |     0.587248 |     0.922819 |
|    63 | cnn1d                     | 298 |          0.121568  |                 0.087405  |                  0.156785  |      1.49298 |            1.3115   |              1.67136 |       1.52217 |            0          |       0.771321 |     0.533557 |     0.942953 |
|    63 | traditional               | 298 |          0.124044  |                 0.0607527 |                  0.197897  |      1.7304  |            1.5182   |              1.90399 |       1.72157 |            0.0033557  |       1.15117  |     0.563758 |     0.838926 |
|    65 | phase_conformal_gated_cnn |  50 |          0.0379573 |                 0.0322424 |                  0.127565  |      1.93843 |            1.58666  |              2.37076 |       1.81611 |            0          |       0.937591 |     0.68     |     0.98     |
|    65 | cnn1d                     |  50 |          0.203297  |                 0.148617  |                  0.295537  |      1.80354 |            1.5047   |              2.42848 |       1.82037 |            0          |       1.19415  |     0.3      |     0.96     |
|    65 | traditional               |  50 |          0.230858  |                 0.131927  |                  0.45377   |      2.09754 |            1.62662  |              2.70712 |       2.07056 |            0          |       1.3344   |     0.46     |     0.78     |
|    65 | gradient_boosted_trees    |  50 |          0.267683  |                 0.122355  |                  0.416843  |      2.07831 |            1.40167  |              2.40209 |       1.83562 |            0          |       1.4617   |     0.4      |     0.84     |
|    65 | mlp                       |  50 |          0.27457   |                 0.136927  |                  0.491602  |      1.94289 |            1.56416  |              2.49467 |       1.81912 |            0          |       1.37924  |     0.36     |     0.8      |
|    65 | ridge                     |  50 |          0.27796   |                 0.111088  |                  0.496652  |      2.16619 |            1.61194  |              2.67436 |       1.99895 |            0          |       1.51281  |     0.42     |     0.82     |

## 4. Amplitude And Energy Closure

Accepted-support amplitude bins:

| stratum            | method                    |    n |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   calibration_loss |   pull_width68 |   coverage68 |   coverage95 |
|:-------------------|:--------------------------|-----:|---------:|-------------:|--------------------:|---------------------:|--------------:|----------------------:|-------------------:|---------------:|-------------:|-------------:|
| amp_adc[1500,2500) | ridge                     |  930 |        7 |      1.84168 |             1.49669 |              2.14167 |       1.78486 |            0.00322581 |          0.142314  |       0.948382 |     0.450538 |     0.84086  |
| amp_adc[1500,2500) | mlp                       |  930 |        7 |      1.58105 |             1.44229 |              1.74974 |       1.56821 |            0.00215054 |          0.143564  |       0.854671 |     0.484946 |     0.867742 |
| amp_adc[1500,2500) | gradient_boosted_trees    |  930 |        7 |      1.53978 |             1.36115 |              1.74126 |       1.55883 |            0.00107527 |          0.15153   |       0.866354 |     0.462366 |     0.856989 |
| amp_adc[1500,2500) | phase_conformal_gated_cnn |  930 |        7 |      1.51482 |             1.25877 |              1.69412 |       1.51735 |            0.00215054 |          0.178365  |       0.471294 |     0.596774 |     0.975269 |
| amp_adc[1500,2500) | cnn1d                     |  930 |        7 |      1.64665 |             1.42241 |              1.82366 |       1.58878 |            0.00215054 |          0.186759  |       0.658343 |     0.431183 |     0.952688 |
| amp_adc[1500,2500) | traditional               |  930 |        7 |      1.94618 |             1.5507  |              2.32442 |       1.92899 |            0.00752688 |          0.226419  |       1.27277  |     0.458065 |     0.752688 |
| amp_adc[2500,4000) | phase_conformal_gated_cnn | 2036 |        7 |      1.59259 |             1.42386 |              1.78824 |       1.5191  |            0          |          0.0547549 |       0.914034 |     0.625737 |     0.967092 |
| amp_adc[2500,4000) | cnn1d                     | 2036 |        7 |      1.6251  |             1.44035 |              1.95026 |       1.58599 |            0.00147348 |          0.0977047 |       1.00971  |     0.460216 |     0.931729 |
| amp_adc[2500,4000) | mlp                       | 2036 |        7 |      1.66641 |             1.51359 |              1.87514 |       1.62202 |            0.00147348 |          0.140507  |       1.15307  |     0.486739 |     0.874754 |
| amp_adc[2500,4000) | gradient_boosted_trees    | 2036 |        7 |      1.57839 |             1.35444 |              1.89275 |       1.59193 |            0.00196464 |          0.147633  |       1.13983  |     0.481336 |     0.85167  |
| amp_adc[2500,4000) | ridge                     | 2036 |        7 |      1.78817 |             1.51027 |              2.19731 |       1.76745 |            0.00343811 |          0.170384  |       1.23329  |     0.487721 |     0.848232 |
| amp_adc[2500,4000) | traditional               | 2036 |        7 |      1.8118  |             1.507   |              2.15119 |       1.83152 |            0.00933202 |          0.179943  |       1.25256  |     0.506385 |     0.814833 |
| amp_adc[4000,7000) | phase_conformal_gated_cnn |  129 |        5 |      1.54956 |             1.25646 |              1.89103 |       1.44831 |            0          |          0.0707774 |       1.09532  |     0.573643 |     0.96124  |
| amp_adc[4000,7000) | ridge                     |  129 |        5 |      1.76838 |             1.48916 |              2.52145 |       1.81422 |            0.0155039  |          0.140243  |       0.960155 |     0.434109 |     0.852713 |
| amp_adc[4000,7000) | gradient_boosted_trees    |  129 |        5 |      1.46186 |             1.20787 |              1.88892 |       1.42057 |            0          |          0.19848   |       1.35651  |     0.503876 |     0.837209 |
| amp_adc[4000,7000) | mlp                       |  129 |        5 |      1.48135 |             1.22582 |              1.96145 |       1.42877 |            0          |          0.209332  |       1.42434  |     0.48062  |     0.891473 |
| amp_adc[4000,7000) | cnn1d                     |  129 |        5 |      1.48186 |             1.21088 |              2.03017 |       1.43247 |            0          |          0.209482  |       1.39975  |     0.472868 |     0.875969 |
| amp_adc[4000,7000) | traditional               |  129 |        5 |      1.68585 |             1.27545 |              2.3511  |       1.69947 |            0.00775194 |          0.310933  |       1.13191  |     0.286822 |     0.604651 |

Accepted-support charge-energy proxy bins:

| stratum             | method                    |    n |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   calibration_loss |   pull_width68 |   coverage68 |   coverage95 |
|:--------------------|:--------------------------|-----:|---------:|-------------:|--------------------:|---------------------:|--------------:|----------------------:|-------------------:|---------------:|-------------:|-------------:|
| charge[8000,14000)  | ridge                     |  178 |        7 |      1.71531 |             1.38759 |              2.19892 |       1.72902 |            0.00561798 |          0.15478   |       0.824295 |     0.488764 |     0.848315 |
| charge[8000,14000)  | gradient_boosted_trees    |  178 |        7 |      1.62998 |             1.23552 |              1.89663 |       1.57977 |            0          |          0.157612  |       0.930945 |     0.438202 |     0.820225 |
| charge[8000,14000)  | mlp                       |  178 |        7 |      1.61511 |             1.28516 |              1.85118 |       1.53883 |            0          |          0.162764  |       0.928877 |     0.455056 |     0.797753 |
| charge[8000,14000)  | traditional               |  178 |        7 |      1.83428 |             1.47088 |              2.29388 |       1.90673 |            0.0168539  |          0.190798  |       1.16327  |     0.488764 |     0.752809 |
| charge[8000,14000)  | phase_conformal_gated_cnn |  178 |        7 |      1.48835 |             1.19454 |              1.96802 |       1.53639 |            0          |          0.202852  |       0.413599 |     0.578652 |     0.994382 |
| charge[8000,14000)  | cnn1d                     |  178 |        7 |      1.68508 |             1.3031  |              1.9738  |       1.5817  |            0          |          0.23014   |       0.588587 |     0.376404 |     0.983146 |
| charge[14000,24000) | phase_conformal_gated_cnn | 1907 |        7 |      1.54479 |             1.32275 |              1.76431 |       1.52603 |            0.00262192 |          0.123547  |       0.651314 |     0.624541 |     0.972732 |
| charge[14000,24000) | ridge                     | 1907 |        7 |      1.78528 |             1.3945  |              2.08542 |       1.78158 |            0.00419507 |          0.124039  |       0.994356 |     0.462507 |     0.847404 |
| charge[14000,24000) | gradient_boosted_trees    | 1907 |        7 |      1.59698 |             1.38906 |              1.85784 |       1.59278 |            0.00262192 |          0.129213  |       0.957142 |     0.463555 |     0.856319 |
| charge[14000,24000) | mlp                       | 1907 |        7 |      1.6154  |             1.45372 |              1.83772 |       1.61222 |            0.00262192 |          0.131846  |       0.883945 |     0.479287 |     0.884111 |
| charge[14000,24000) | cnn1d                     | 1907 |        7 |      1.62979 |             1.46818 |              1.95636 |       1.60356 |            0.00262192 |          0.153937  |       0.784887 |     0.437336 |     0.945464 |
| charge[14000,24000) | traditional               | 1907 |        7 |      1.84163 |             1.51761 |              2.15757 |       1.88887 |            0.00681699 |          0.214704  |       1.27947  |     0.466702 |     0.779759 |
| charge[24000,40000) | phase_conformal_gated_cnn | 1010 |        7 |      1.54553 |             1.40606 |              1.70372 |       1.43449 |            0          |          0.0563185 |       1.07545  |     0.60297  |     0.958416 |
| charge[24000,40000) | cnn1d                     | 1010 |        7 |      1.51083 |             1.32909 |              1.68593 |       1.45994 |            0          |          0.135273  |       1.18097  |     0.493069 |     0.908911 |
| charge[24000,40000) | gradient_boosted_trees    | 1010 |        7 |      1.51825 |             1.28581 |              1.74244 |       1.47599 |            0          |          0.172063  |       1.27526  |     0.507921 |     0.851485 |
| charge[24000,40000) | mlp                       | 1010 |        7 |      1.57134 |             1.35286 |              1.76637 |       1.48841 |            0          |          0.179722  |       1.32025  |     0.50396  |     0.866337 |
| charge[24000,40000) | traditional               | 1010 |        7 |      1.83078 |             1.59809 |              2.14429 |       1.84707 |            0.00792079 |          0.186819  |       1.27794  |     0.511881 |     0.807921 |
| charge[24000,40000) | ridge                     | 1010 |        7 |      1.78635 |             1.58844 |              2.12994 |       1.7492  |            0.0039604  |          0.198358  |       1.34876  |     0.494059 |     0.843564 |

Median residual bias slopes after action-band acceptance. Units are ns/ADC for amplitude and ns/(ADC sample) for charge proxy; CIs use the same run/event bootstrap.

| dimension     | method                    |    n |   n_runs |   n_bins |   median_residual_slope_ns_per_unit |   slope_ci_low |   slope_ci_high |   intercept_ns |
|:--------------|:--------------------------|-----:|---------:|---------:|------------------------------------:|---------------:|----------------:|---------------:|
| amplitude_bin | cnn1d                     | 3095 |        7 |        3 |                        -0.000521726 |   -0.000708323 |    -0.000325087 |       2.9658   |
| amplitude_bin | phase_conformal_gated_cnn | 3095 |        7 |        3 |                        -0.000505927 |   -0.000613645 |    -0.000339266 |       2.93501  |
| amplitude_bin | gradient_boosted_trees    | 3095 |        7 |        3 |                        -0.000492231 |   -0.00060565  |    -0.000321032 |       2.73181  |
| amplitude_bin | mlp                       | 3095 |        7 |        3 |                        -0.000477046 |   -0.000594737 |    -0.000230481 |       2.78365  |
| amplitude_bin | ridge                     | 3095 |        7 |        3 |                         1.53842e-05 |   -0.000187392 |     0.00022462  |       1.5116   |
| amplitude_bin | traditional               | 3095 |        7 |        3 |                         0.000296273 |    7.92847e-05 |     0.000504741 |       0.573744 |
| charge_bin    | mlp                       | 3095 |        7 |        3 |                        -7.63368e-05 |   -8.9669e-05  |    -3.02168e-05 |       3.06415  |
| charge_bin    | phase_conformal_gated_cnn | 3095 |        7 |        3 |                        -6.98162e-05 |   -9.21054e-05 |    -3.56215e-05 |       2.96733  |
| charge_bin    | cnn1d                     | 3095 |        7 |        3 |                        -6.89079e-05 |   -9.03902e-05 |    -2.11914e-05 |       2.92078  |
| charge_bin    | gradient_boosted_trees    | 3095 |        7 |        3 |                        -5.98082e-05 |   -9.1884e-05  |    -3.53256e-05 |       2.59811  |
| charge_bin    | ridge                     | 3095 |        7 |        3 |                        -5.58304e-05 |   -7.9736e-05  |    -2.95058e-05 |       2.61588  |
| charge_bin    | traditional               | 3095 |        7 |        3 |                        -2.44498e-05 |   -4.92653e-05 |     2.46107e-06 |       1.8393   |

Best ML-minus-traditional deltas by accepted amplitude/charge bin:

| dimension     | stratum             | method                    |   traditional_calibration_loss |   calibration_loss |   ml_minus_traditional_calibration_loss |   traditional_sigma68_ns |   sigma68_ns |   ml_minus_traditional_sigma68_ns |   traditional_tail_frac_abs_gt5ns |   tail_frac_abs_gt5ns |   ml_minus_traditional_tail_frac_abs_gt5ns |
|:--------------|:--------------------|:--------------------------|-------------------------------:|-------------------:|----------------------------------------:|-------------------------:|-------------:|----------------------------------:|----------------------------------:|----------------------:|-------------------------------------------:|
| amplitude_bin | amp_adc[4000,7000)  | phase_conformal_gated_cnn |                       0.310933 |          0.0707774 |                              -0.240155  |                  1.68585 |      1.54956 |                        -0.136292  |                        0.00775194 |            0          |                                -0.00775194 |
| amplitude_bin | amp_adc[4000,7000)  | ridge                     |                       0.310933 |          0.140243  |                              -0.17069   |                  1.68585 |      1.76838 |                         0.08253   |                        0.00775194 |            0.0155039  |                                 0.00775194 |
| charge_bin    | charge[24000,40000) | phase_conformal_gated_cnn |                       0.186819 |          0.0563185 |                              -0.1305    |                  1.83078 |      1.54553 |                        -0.285248  |                        0.00792079 |            0          |                                -0.00792079 |
| amplitude_bin | amp_adc[2500,4000)  | phase_conformal_gated_cnn |                       0.179943 |          0.0547549 |                              -0.125188  |                  1.8118  |      1.59259 |                        -0.219206  |                        0.00933202 |            0          |                                -0.00933202 |
| amplitude_bin | amp_adc[4000,7000)  | gradient_boosted_trees    |                       0.310933 |          0.19848   |                              -0.112453  |                  1.68585 |      1.46186 |                        -0.223985  |                        0.00775194 |            0          |                                -0.00775194 |
| amplitude_bin | amp_adc[4000,7000)  | mlp                       |                       0.310933 |          0.209332  |                              -0.1016    |                  1.68585 |      1.48135 |                        -0.204495  |                        0.00775194 |            0          |                                -0.00775194 |
| amplitude_bin | amp_adc[4000,7000)  | cnn1d                     |                       0.310933 |          0.209482  |                              -0.101451  |                  1.68585 |      1.48186 |                        -0.203991  |                        0.00775194 |            0          |                                -0.00775194 |
| charge_bin    | charge[14000,24000) | phase_conformal_gated_cnn |                       0.214704 |          0.123547  |                              -0.0911576 |                  1.84163 |      1.54479 |                        -0.296836  |                        0.00681699 |            0.00262192 |                                -0.00419507 |
| charge_bin    | charge[14000,24000) | ridge                     |                       0.214704 |          0.124039  |                              -0.0906652 |                  1.84163 |      1.78528 |                        -0.0563495 |                        0.00681699 |            0.00419507 |                                -0.00262192 |
| charge_bin    | charge[14000,24000) | gradient_boosted_trees    |                       0.214704 |          0.129213  |                              -0.0854911 |                  1.84163 |      1.59698 |                        -0.244649  |                        0.00681699 |            0.00262192 |                                -0.00419507 |
| amplitude_bin | amp_adc[1500,2500)  | ridge                     |                       0.226419 |          0.142314  |                              -0.0841051 |                  1.94618 |      1.84168 |                        -0.104497  |                        0.00752688 |            0.00322581 |                                -0.00430108 |
| charge_bin    | charge[14000,24000) | mlp                       |                       0.214704 |          0.131846  |                              -0.0828579 |                  1.84163 |      1.6154  |                        -0.226226  |                        0.00681699 |            0.00262192 |                                -0.00419507 |
| amplitude_bin | amp_adc[1500,2500)  | mlp                       |                       0.226419 |          0.143564  |                              -0.0828549 |                  1.94618 |      1.58105 |                        -0.365127  |                        0.00752688 |            0.00215054 |                                -0.00537634 |
| amplitude_bin | amp_adc[2500,4000)  | cnn1d                     |                       0.179943 |          0.0977047 |                              -0.082238  |                  1.8118  |      1.6251  |                        -0.1867    |                        0.00933202 |            0.00147348 |                                -0.00785855 |
| amplitude_bin | amp_adc[1500,2500)  | gradient_boosted_trees    |                       0.226419 |          0.15153   |                              -0.0748884 |                  1.94618 |      1.53978 |                        -0.406396  |                        0.00752688 |            0.00107527 |                                -0.00645161 |
| charge_bin    | charge[14000,24000) | cnn1d                     |                       0.214704 |          0.153937  |                              -0.0607678 |                  1.84163 |      1.62979 |                        -0.211843  |                        0.00681699 |            0.00262192 |                                -0.00419507 |
| charge_bin    | charge[24000,40000) | cnn1d                     |                       0.186819 |          0.135273  |                              -0.0515459 |                  1.83078 |      1.51083 |                        -0.31995   |                        0.00792079 |            0          |                                -0.00792079 |
| amplitude_bin | amp_adc[1500,2500)  | phase_conformal_gated_cnn |                       0.226419 |          0.178365  |                              -0.0480537 |                  1.94618 |      1.51482 |                        -0.431361  |                        0.00752688 |            0.00215054 |                                -0.00537634 |
| amplitude_bin | amp_adc[1500,2500)  | cnn1d                     |                       0.226419 |          0.186759  |                              -0.03966   |                  1.94618 |      1.64665 |                        -0.299526  |                        0.00752688 |            0.00215054 |                                -0.00537634 |
| amplitude_bin | amp_adc[2500,4000)  | mlp                       |                       0.179943 |          0.140507  |                              -0.0394363 |                  1.8118  |      1.66641 |                        -0.145391  |                        0.00933202 |            0.00147348 |                                -0.00785855 |
| charge_bin    | charge[8000,14000)  | ridge                     |                       0.190798 |          0.15478   |                              -0.0360176 |                  1.83428 |      1.71531 |                        -0.11897   |                        0.0168539  |            0.00561798 |                                -0.011236   |
| charge_bin    | charge[8000,14000)  | gradient_boosted_trees    |                       0.190798 |          0.157612  |                              -0.0331856 |                  1.83428 |      1.62998 |                        -0.204301  |                        0.0168539  |            0          |                                -0.0168539  |
| amplitude_bin | amp_adc[2500,4000)  | gradient_boosted_trees    |                       0.179943 |          0.147633  |                              -0.0323095 |                  1.8118  |      1.57839 |                        -0.233412  |                        0.00933202 |            0.00196464 |                                -0.00736739 |
| charge_bin    | charge[8000,14000)  | mlp                       |                       0.190798 |          0.162764  |                              -0.0280339 |                  1.83428 |      1.61511 |                        -0.219169  |                        0.0168539  |            0          |                                -0.0168539  |

Acceptance impact relative to full support:

| method                    |    n |   full_n |   accepted_minus_full_n |   calibration_loss |   full_calibration_loss |   accepted_minus_full_calibration_loss |   sigma68_ns |   full_sigma68_ns |   accepted_minus_full_sigma68_ns |   tail_frac_abs_gt5ns |   full_tail_frac_abs_gt5ns |   accepted_minus_full_tail_frac_abs_gt5ns |
|:--------------------------|-----:|---------:|------------------------:|-------------------:|------------------------:|---------------------------------------:|-------------:|------------------:|---------------------------------:|----------------------:|---------------------------:|------------------------------------------:|
| phase_conformal_gated_cnn | 3095 |    11460 |                   -8365 |          0.0748153 |               0.0534484 |                             0.0213669  |      1.63093 |           1.50399 |                        0.126945  |           0.000969305 |                  0.0114311 |                                -0.0104618 |
| cnn1d                     | 3095 |    11460 |                   -8365 |          0.104678  |               0.0973354 |                             0.00734244 |      1.67444 |           1.5101  |                        0.164339  |           0.00161551  |                  0.0129145 |                                -0.011299  |
| mlp                       | 3095 |    11460 |                   -8365 |          0.125722  |               0.103472  |                             0.0222503  |      1.69535 |           1.64477 |                        0.0505793 |           0.000969305 |                  0.0138743 |                                -0.012905  |
| gradient_boosted_trees    | 3095 |    11460 |                   -8365 |          0.134938  |               0.109007  |                             0.0259313  |      1.64027 |           1.5543  |                        0.0859767 |           0.000969305 |                  0.0153578 |                                -0.0143885 |
| ridge                     | 3095 |    11460 |                   -8365 |          0.142737  |               0.110021  |                             0.032716   |      1.84718 |           1.57318 |                        0.273998  |           0.00420032  |                  0.0161431 |                                -0.0119428 |
| traditional               | 3095 |    11460 |                   -8365 |          0.203856  |               0.659059  |                            -0.455204   |      1.84325 |           1.55109 |                        0.292158  |           0.00775444  |                  0.0191099 |                                -0.0113555 |

Action-band and energy-support composition from nonduplicated traditional rows:

| dimension     | stratum             |   bin_mid |   n_pair_residuals |   n_runs |   accepted_fraction |   timing_window_action_fraction |   saturation_action_fraction |   dropout_action_fraction |   baseline_action_fraction |   q_template_action_fraction |   energy_support_action_fraction |
|:--------------|:--------------------|----------:|-------------------:|---------:|--------------------:|--------------------------------:|-----------------------------:|--------------------------:|---------------------------:|-----------------------------:|---------------------------------:|
| amplitude_bin | amp_adc[1000,1500)  |      1250 |                256 |        7 |            0        |                        0.683594 |                   0          |                 0.253906  |                   0.660156 |                     0.976562 |                        1         |
| amplitude_bin | amp_adc[1500,2500)  |      2000 |               3901 |        7 |            0.2384   |                        0.372212 |                   0          |                 0.0992053 |                   0.374263 |                     0.754166 |                        0.0264035 |
| amplitude_bin | amp_adc[2500,4000)  |      3250 |               6811 |        7 |            0.298928 |                        0.312583 |                   0          |                 0.0638673 |                   0.239759 |                     0.675084 |                        0.0146821 |
| amplitude_bin | amp_adc[4000,7000)  |      5500 |                492 |        7 |            0.262195 |                        0.376016 |                   0.0325203  |                 0.115854  |                   0.229675 |                     0.715447 |                        0.0609756 |
| charge_bin    | charge[1000,4000)   |      2500 |                 60 |        7 |            0        |                        1        |                   0          |                 1         |                   0.05     |                     1        |                        1         |
| charge_bin    | charge[4000,8000)   |      6000 |                285 |        7 |            0        |                        0.975439 |                   0          |                 0.708772  |                   0.498246 |                     1        |                        1         |
| charge_bin    | charge[8000,14000)  |     11000 |               1471 |        7 |            0.121006 |                        0.603671 |                   0          |                 0.242012  |                   0.479266 |                     0.872196 |                        0.0774983 |
| charge_bin    | charge[14000,24000) |     19000 |               5990 |        7 |            0.318364 |                        0.269616 |                   0          |                 0.0392321 |                   0.2601   |                     0.660601 |                        0         |
| charge_bin    | charge[24000,40000) |     32000 |               3624 |        7 |            0.278698 |                        0.298565 |                   0.00331126 |                 0.0229029 |                   0.261589 |                     0.697296 |                        0         |
| charge_bin    | charge[40000,80000) |     60000 |                 30 |        6 |            0        |                        0.6      |                   0.133333   |                 0.266667  |                   0.633333 |                     1        |                        1         |

## 5. Falsification And Controls

The claim would fail if the accepted support did not include all held-out runs, if the best ML/NN accepted-support loss CI overlapped or exceeded the traditional loss CI, if shuffled action/energy controls matched the observed acceptance, or if the result required residual-defined acceptance.

Permutation and topology-only controls on traditional rows:

| control                   | method      |   accepted_fraction |    n |   bias_ns |   median_ns |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   pull_width68 |   coverage68 |   coverage95 |   coverage68_error |   coverage95_error |   calibration_ece |   calibration_loss |
|:--------------------------|:------------|--------------------:|-----:|----------:|------------:|-------------:|--------------:|----------------------:|---------------:|-------------:|-------------:|-------------------:|-------------------:|------------------:|-------------------:|
| observed_action_bands     | traditional |            0.27007  | 3095 |   1.26922 |     1.23746 |      1.84325 |       1.88008 |            0.00775444 |        1.27156 |     0.482714 |     0.787399 |           0.199975 |           0.162601 |          0.181288 |           0.203856 |
| energy_shuffle_within_run | traditional |            0.258202 | 2959 |   1.2647  |     1.22259 |      1.84337 |       1.88383 |            0.00811085 |        1.26953 |     0.484961 |     0.787428 |           0.197728 |           0.162572 |          0.18015  |           0.202495 |
| action_shuffle_within_run | traditional |            0.27007  | 3095 |   1.28386 |     1.49422 |      1.57657 |       2.77781 |            0.0239095  |        2.62668 |     0.388691 |     0.632633 |           0.293998 |           0.317367 |          0.305682 |           0.635932 |
| topology_only_acceptance  | traditional |            0.656108 | 7519 |   1.22391 |     1.20197 |      1.86123 |       2.13526 |            0.0154276  |        1.31987 |     0.46828  |     0.781088 |           0.214409 |           0.168912 |          0.191661 |           0.223713 |

Action-band strata retained for systematic accounting:

| action_band           | method                    |   support_fraction |    n |   n_runs |   calibration_loss |   calibration_loss_ci_low |   calibration_loss_ci_high |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   pull_width68 |   coverage68 |   coverage95 |
|:----------------------|:--------------------------|-------------------:|-----:|---------:|-------------------:|--------------------------:|---------------------------:|-------------:|--------------:|----------------------:|---------------:|-------------:|-------------:|
| accepted_support      | phase_conformal_gated_cnn |         0.27007    | 3095 |        7 |          0.0748153 |                 0.0550786 |                  0.10708   |      1.63093 |       1.55533 |           0.000969305 |       0.851297 |     0.614863 |     0.969305 |
| accepted_support      | cnn1d                     |         0.27007    | 3095 |        7 |          0.104678  |                 0.091308  |                  0.152829  |      1.67444 |       1.62009 |           0.00161551  |       0.96937  |     0.452019 |     0.935703 |
| accepted_support      | mlp                       |         0.27007    | 3095 |        7 |          0.125722  |                 0.0767487 |                  0.186713  |      1.69535 |       1.63691 |           0.000969305 |       1.0886   |     0.485945 |     0.873344 |
| accepted_support      | gradient_boosted_trees    |         0.27007    | 3095 |        7 |          0.134938  |                 0.0754717 |                  0.266664  |      1.64027 |       1.60736 |           0.000969305 |       1.08169  |     0.476575 |     0.852666 |
| accepted_support      | ridge                     |         0.27007    | 3095 |        7 |          0.142737  |                 0.0737546 |                  0.337247  |      1.84718 |       1.80132 |           0.00420032  |       1.10044  |     0.474313 |     0.846204 |
| accepted_support      | traditional               |         0.27007    | 3095 |        7 |          0.203856  |                 0.094128  |                  0.386934  |      1.84325 |       1.88008 |           0.00775444  |       1.27156  |     0.482714 |     0.787399 |
| baseline_action       | phase_conformal_gated_cnn |         0.294503   | 3375 |        7 |          0.0581036 |                 0.0351974 |                  0.0904609 |      1.32589 |       3.44681 |           0.0195556   |       0.856684 |     0.697185 |     0.968296 |
| baseline_action       | mlp                       |         0.294503   | 3375 |        7 |          0.0800071 |                 0.0616241 |                  0.0966915 |      1.44928 |       3.34994 |           0.0242963   |       0.902839 |     0.58163  |     0.922963 |
| baseline_action       | cnn1d                     |         0.294503   | 3375 |        7 |          0.0928942 |                 0.0824194 |                  0.129097  |      1.32098 |       3.38795 |           0.0195556   |       0.974124 |     0.469926 |     0.962074 |
| baseline_action       | gradient_boosted_trees    |         0.294503   | 3375 |        7 |          0.0961482 |                 0.0702153 |                  0.117497  |      1.27955 |       3.11216 |           0.026963    |       0.841696 |     0.56237  |     0.937185 |
| baseline_action       | ridge                     |         0.294503   | 3375 |        7 |          0.145591  |                 0.129503  |                  0.167321  |      1.21973 |       3.41817 |           0.021037    |       0.758724 |     0.479704 |     0.940741 |
| baseline_action       | traditional               |         0.294503   | 3375 |        7 |          1.97414   |                 1.87432   |                  2.12322   |      1.1839  |       3.52964 |           0.0195556   |       7.40886  |     0.240296 |     0.400593 |
| dropout_action        | phase_conformal_gated_cnn |         0.0823735  |  944 |        7 |          0.0571865 |                 0.0395519 |                  0.0740973 |      1.35867 |       5.00779 |           0.0646186   |       0.935642 |     0.610169 |     0.931144 |
| dropout_action        | gradient_boosted_trees    |         0.0823735  |  944 |        7 |          0.0825968 |                 0.0620833 |                  0.133842  |      1.75348 |       4.62845 |           0.0815678   |       0.970819 |     0.541314 |     0.89089  |
| dropout_action        | mlp                       |         0.0823735  |  944 |        7 |          0.104251  |                 0.0774092 |                  0.139122  |      1.83001 |       5.04255 |           0.0762712   |       0.946088 |     0.53178  |     0.865466 |
| dropout_action        | cnn1d                     |         0.0823735  |  944 |        7 |          0.108618  |                 0.0646075 |                  0.16949   |      1.3704  |       5.05821 |           0.0720339   |       1.06875  |     0.476695 |     0.922669 |
| dropout_action        | ridge                     |         0.0823735  |  944 |        7 |          0.12308   |                 0.0581163 |                  0.187887  |      1.5509  |       5.04025 |           0.0709746   |       1.20075  |     0.53178  |     0.909958 |
| dropout_action        | traditional               |         0.0823735  |  944 |        7 |          2.01547   |                 1.8214    |                  2.2791    |      1.27912 |       5.31291 |           0.0709746   |       7.4248   |     0.227754 |     0.313559 |
| energy_support_action | phase_conformal_gated_cnn |         0.0426702  |  489 |        7 |          0.0963253 |                 0.0669406 |                  0.174054  |      1.27895 |       3.51517 |           0.0286299   |       0.760753 |     0.633947 |     0.952965 |
| energy_support_action | ridge                     |         0.0426702  |  489 |        7 |          0.135623  |                 0.0986969 |                  0.195239  |      1.23447 |       3.59248 |           0.0327198   |       0.735471 |     0.515337 |     0.94274  |
| energy_support_action | cnn1d                     |         0.0426702  |  489 |        7 |          0.159799  |                 0.086475  |                  0.225053  |      1.2714  |       3.48181 |           0.0265849   |       0.771291 |     0.439673 |     0.932515 |
| energy_support_action | mlp                       |         0.0426702  |  489 |        7 |          0.177271  |                 0.139256  |                  0.200274  |      1.38726 |       3.65893 |           0.0408998   |       0.596486 |     0.539877 |     0.912065 |
| energy_support_action | gradient_boosted_trees    |         0.0426702  |  489 |        7 |          0.188988  |                 0.136335  |                  0.22941   |      1.35685 |       3.30962 |           0.0245399   |       0.560671 |     0.509202 |     0.916155 |
| energy_support_action | traditional               |         0.0426702  |  489 |        7 |          2.00513   |                 1.79842   |                  2.27965   |      1.2803  |       3.63758 |           0.0286299   |       7.27699  |     0.184049 |     0.286299 |
| q_template_action     | phase_conformal_gated_cnn |         0.710471   | 8142 |        7 |          0.0501585 |                 0.0367502 |                  0.0679373 |      1.45016 |       2.68455 |           0.0153525   |       0.907874 |     0.639155 |     0.95861  |
| q_template_action     | gradient_boosted_trees    |         0.710471   | 8142 |        7 |          0.091465  |                 0.0732755 |                  0.188404  |      1.51576 |       2.54426 |           0.0206338   |       1.00287  |     0.514616 |     0.877917 |
| q_template_action     | mlp                       |         0.710471   | 8142 |        7 |          0.0930622 |                 0.0682381 |                  0.157039  |      1.623   |       2.67632 |           0.0189143   |       1.02905  |     0.529845 |     0.878408 |
| q_template_action     | cnn1d                     |         0.710471   | 8142 |        7 |          0.0980322 |                 0.0774369 |                  0.160813  |      1.44563 |       2.67508 |           0.0176861   |       1.01805  |     0.456645 |     0.937239 |
| q_template_action     | ridge                     |         0.710471   | 8142 |        7 |          0.101947  |                 0.0811383 |                  0.175336  |      1.47729 |       2.79137 |           0.021125    |       0.993716 |     0.483542 |     0.881479 |
| q_template_action     | traditional               |         0.710471   | 8142 |        7 |          0.948569  |                 0.836754  |                  1.05823   |      1.43658 |       2.92153 |           0.0239499   |       3.72089  |     0.347335 |     0.569762 |
| saturation_action     | cnn1d                     |         0.00139616 |   16 |        3 |          0.178621  |                 0.0297816 |                  1.39711   |      5.20142 |       9.89485 |           0.1875      |       1.27817  |     0.5625   |     0.8125   |
| saturation_action     | mlp                       |         0.00139616 |   16 |        3 |          0.253007  |                 0.0494512 |                  1.04178   |      3.627   |      10.68    |           0.3125      |       0.873669 |     0.375    |     0.625    |
| saturation_action     | ridge                     |         0.00139616 |   16 |        3 |          0.300694  |                 0.120261  |                  0.612298  |      5.79958 |      10.6591  |           0.4375      |       1.26939  |     0.3125   |     0.6875   |
| saturation_action     | gradient_boosted_trees    |         0.00139616 |   16 |        3 |          0.404313  |                 0.139329  |                  1.18635   |      3.364   |       8.68853 |           0.1875      |       1.51775  |     0.375    |     0.5625   |
| saturation_action     | phase_conformal_gated_cnn |         0.00139616 |   16 |        3 |          0.787061  |                 0.0666528 |                  4.03946   |      5.37965 |      10.2355  |           0.25        |       2.91599  |     0.5      |     0.6875   |
| saturation_action     | traditional               |         0.00139616 |   16 |        3 |          1.48628   |                 0.575299  |                  7.35529   |      4.71691 |      10.2914  |           0.3125      |       4.07616  |     0.0625   |     0.1875   |
| timing_window_action  | phase_conformal_gated_cnn |         0.343892   | 3941 |        7 |          0.0525833 |                 0.0389544 |                  0.0786048 |      1.32375 |       3.23873 |           0.0215681   |       0.870594 |     0.688658 |     0.965998 |
| timing_window_action  | mlp                       |         0.343892   | 3941 |        7 |          0.0901472 |                 0.0733834 |                  0.113155  |      1.5154  |       3.21386 |           0.0268967   |       0.901502 |     0.566607 |     0.906369 |
| timing_window_action  | cnn1d                     |         0.343892   | 3941 |        7 |          0.0930186 |                 0.0839116 |                  0.150704  |      1.33334 |       3.20743 |           0.0235981   |       1.00491  |     0.454453 |     0.957879 |
| timing_window_action  | gradient_boosted_trees    |         0.343892   | 3941 |        7 |          0.0942025 |                 0.0744956 |                  0.113704  |      1.35264 |       2.96011 |           0.0294342   |       0.863481 |     0.558741 |     0.924892 |
| timing_window_action  | ridge                     |         0.343892   | 3941 |        7 |          0.12921   |                 0.104899  |                  0.15295   |      1.27751 |       3.30527 |           0.0253743   |       0.838244 |     0.472469 |     0.940117 |
| timing_window_action  | traditional               |         0.343892   | 3941 |        7 |          2.12567   |                 2.00417   |                  2.27238   |      1.2111  |       3.46155 |           0.0258818   |       7.9123   |     0.226085 |     0.346359 |

Leakage and bookkeeping checks:

| check                                       | value                                                                                                         | pass   | note                                                                        |
|:--------------------------------------------|:--------------------------------------------------------------------------------------------------------------|:-------|:----------------------------------------------------------------------------|
| raw_root_reproduction_passed                | True                                                                                                          | True   | raw HRDv count gate must pass before closure rows are interpreted           |
| required_methods_present                    | cnn1d,gradient_boosted_trees,mlp,phase_conformal_gated_cnn,ridge,traditional                                  | True   | traditional plus ridge, GBT, MLP, 1D-CNN, and phase-conformal gated CNN     |
| split_by_run                                | 58,59,60,61,62,63,65                                                                                          | True   | pair rows are leave-one-run-out over Sample-II analysis runs                |
| accepted_support_nonempty_all_runs          | 58,59,60,61,62,63,65                                                                                          | True   | action-band gate must not collapse to a subset of runs                      |
| no_label_defining_dt_features_in_acceptance | timing_window_action,saturation_action,dropout_action,baseline_action,q_template_action,energy_support_action | True   | acceptance uses waveform support atoms, not pair residual magnitude or pull |

## 6. Threats To Validity

- **Benchmark/selection:** the traditional comparator is the same strong analytic/template plus robust atom-width baseline used in S06b, and all methods are evaluated on identical held-out rows after one deterministic action-band rule.
- **Data leakage:** folds are by run. The action-band rule uses waveform support atoms and fixed thresholds, not residual magnitude, pull, or the winning method.
- **Metric misuse:** central sigma68, full RMS, >5 ns tails, pull width, and nominal coverages are all reported; the winner optimizes calibrated uncertainty rather than a narrow core alone.
- **Post-hoc selection:** thresholds and winner metric are fixed in the config before this script inspects the accepted rows. This study reports all required model families and the full action-stratum audit.
- **Systematics:** charge proxy is waveform area, not an externally calibrated proton energy; pair residuals remove common event time but are not an external absolute clock; sparse high-charge and high-amplitude bands remain abstention regions, not evidence of production closure.

## 7. Findings And Next Steps

After deterministic action-band acceptance, 0.270 of nonduplicated traditional pair rows remain across all held-out runs. The accepted-support winner is phase_conformal_gated_cnn with calibration loss 0.0748; the best ML-minus-traditional calibration-loss delta is -0.1290. The action rule removes the worst support mixtures but does not make the traditional pull model calibrated enough for downstream uncertainty propagation.

Hypothesis: most residual sigma(E) instability after S06b is not a smooth energy dependence but an action-band support mixture. If the hypothesis is correct, propagating the accepted-support intervals into PID/range-energy consumers should improve pull coverage at a fixed abstention budget; if false, consumer-level pulls will remain miscalibrated even on accepted support.

Queued follow-up: `S06d: propagate S06c accepted-support timing intervals into PID/range-energy pulls under a fixed abstention budget`.

## 8. Reproducibility

Regenerate with:

```bash
/home/billy/anaconda3/bin/python scripts/s06c_1781056892_649_4cbb3cd2_timewalk_energy_action_band_closure.py --config configs/s06c_1781056892_649_4cbb3cd2_timewalk_energy_action_band_closure.json
```

Artifacts: `REPORT.md`, `result.json`, `manifest.json`, `reproduction_match_table.csv`, `s03a_reproduction_benchmark.csv`, `pair_residual_rows_with_pulls.csv.gz`, `accepted_pair_residual_rows.csv.gz`, `full_method_summary.csv`, `accepted_method_summary.csv`, `accepted_per_run_bootstrap_summary.csv`, `accepted_amplitude_charge_summary.csv`, `bias_slope_summary.csv`, `accepted_delta_vs_traditional.csv`, `acceptance_delta_vs_full.csv`, `action_band_summary.csv`, `action_band_composition.csv`, `action_shuffle_controls.csv`, `leakage_checks.csv`, `input_sha256.csv`, and four figures.

