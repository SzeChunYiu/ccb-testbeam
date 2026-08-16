# Ticket #2404: P10 Conditional Generative Pulse Template Bakeoff

## Abstract

This report resolves ticket `#2404` for worker `testbeam-laptop-3`. The raw ROOT selected-pulse count is reproduced exactly, then a run-held-out template-generation benchmark compares a strong empirical amplitude-bin template against ridge, gradient-boosted trees, MLP, a compact conditional 1D-CNN, and a new residual-fusion architecture. The winner by the predeclared composite score is **`gradient_boosted_trees`**.

## Raw ROOT Reproduction

For each B-stack ROOT file in the configured run set, the `h101/HRDv` branch is reshaped to `(event, channel, sample)` with 18 samples per channel. For B2, B4, B6, and B8 the pedestal is

`b_ec = median{x_ec0, x_ec1, x_ec2, x_ec3}`,

and the selected-pulse indicator is

`I_ec = 1[max_t(x_ect - b_ec) > 1000 ADC]`.

| quantity | expected | reproduced | delta | pass |
| --- | --- | --- | --- | --- |
| selected B-stave pulses from raw ROOT | 640737 | 640737 | 0 | True |
| analysis selected rows | 377362 | 377362 | 0 | True |

## Methods

Let `y_i(t)` be the CFD20-aligned and amplitude-normalized pulse waveform for event-pulse `i`, and let `x_i` contain standardized log-amplitude, log-area, peak sample, area/peak ratio, and stave one-hot features. The empirical traditional comparator is

`T_trad(s, a_bin, t) = median{y_i(t): stave_i=s, amp_i in a_bin, i in train}`.

The ridge method solves `argmin_B ||Y - XB||_2^2 + alpha ||B||_2^2`. The gradient-boosted tree method fits one histogram-gradient boosting regressor per sample. The MLP is a two-hidden-layer nonlinear multi-output regressor. The 1D-CNN tiles the conditioning vector over the 18-sample time grid and applies convolutional filters along sample index. The new architecture, `empirical_residual_boosted_fusion_new`, adds a boosted-tree residual correction to the empirical template, so it preserves the train-run median morphology while learning systematic conditional residuals.

## Split and Uncertainty

Training uses only calibration runs 31-42 and 64. Evaluation uses analysis runs 44-57, 58-63, and 65. Confidence intervals are percentile 95% intervals from bootstrap resampling of held-out run-level metric rows. The primary metric is q-template MSE; timing residual is the CFD20 displacement of the predicted template relative to the observed aligned pulse, reported in ns.

## Overall Results

| method | score | q_template_mse [95% CI] | q_template_rmse [95% CI] | timing_sigma68_ns [95% CI] | timing_bias_ns [95% CI] |
|---|---:|---:|---:|---:|---:|
| gradient_boosted_trees | 0.0063472 | 0.00633397 [0.00533215, 0.00726213] | 0.0781632 [0.0719891, 0.0841742] | 0.109214 [0.104933, 0.11386] | -0.0462522 [-0.0532293, -0.0391791] |
| mlp | 0.00649315 | 0.00647201 [0.00541103, 0.00743735] | 0.0790539 [0.0722095, 0.0852226] | 0.202227 [0.174899, 0.231097] | 0.0181996 [0.00134132, 0.036406] |
| empirical_residual_boosted_fusion_new | 0.00789608 | 0.00788328 [0.00670299, 0.00905348] | 0.087398 [0.0808439, 0.0943363] | 0.105466 [0.102199, 0.108975] | -0.0451448 [-0.0466325, -0.043682] |
| 1d_cnn | 0.0172702 | 0.0170903 [0.0148769, 0.01951] | 0.128871 [0.119201, 0.137861] | 0.756616 [0.701459, 0.807585] | -2.08336 [-2.24428, -1.94169] |
| ridge | 0.0224792 | 0.0224137 [0.0193751, 0.0256639] | 0.147509 [0.137671, 0.15874] | 0.471583 [0.442464, 0.49875] | -0.366676 [-0.417269, -0.315307] |
| traditional_empirical_ampbin | 0.080951 | 0.0809406 [0.0672533, 0.094657] | 0.278668 [0.252919, 0.301658] | 0.0982249 [0.0962278, 0.100098] | -0.011727 [-0.0150112, -0.00886542] |

## Run-Level Stability

| method | run | n | q_template_mse | q_template_rmse | timing_bias_ns | timing_sigma68_ns |
| --- | --- | --- | --- | --- | --- | --- |
| traditional_empirical_ampbin | 44 | 2038 | 0.119463 | 0.345633 | -0.00660925 | 0.0994524 |
| traditional_empirical_ampbin | 45 | 24333 | 0.128244 | 0.358112 | -0.00694272 | 0.103787 |
| traditional_empirical_ampbin | 46 | 687 | 0.0590335 | 0.242968 | -0.0129399 | 0.101207 |
| traditional_empirical_ampbin | 47 | 5276 | 0.0695134 | 0.263654 | -0.00936784 | 0.0970021 |
| traditional_empirical_ampbin | 48 | 14000 | 0.124568 | 0.352942 | -0.0121991 | 0.102522 |
| traditional_empirical_ampbin | 49 | 14815 | 0.124682 | 0.353104 | -0.010487 | 0.10157 |
| traditional_empirical_ampbin | 50 | 35217 | 0.0441828 | 0.210197 | -0.0034122 | 0.0944467 |
| traditional_empirical_ampbin | 51 | 14740 | 0.0512992 | 0.226493 | -0.00197563 | 0.093863 |
| traditional_empirical_ampbin | 52 | 7152 | 0.0525091 | 0.229149 | -0.00109927 | 0.0943933 |
| traditional_empirical_ampbin | 53 | 32200 | 0.0403438 | 0.200858 | -0.00626234 | 0.0897015 |
| traditional_empirical_ampbin | 54 | 30440 | 0.0364708 | 0.190973 | -0.00690033 | 0.0890939 |
| traditional_empirical_ampbin | 55 | 17387 | 0.0542082 | 0.232827 | -0.00596801 | 0.0939289 |
| traditional_empirical_ampbin | 56 | 40148 | 0.0423898 | 0.205888 | -0.00443364 | 0.09422 |
| traditional_empirical_ampbin | 57 | 13833 | 0.130408 | 0.36112 | -0.0116171 | 0.101715 |
| traditional_empirical_ampbin | 58 | 16781 | 0.0562336 | 0.237136 | -0.0134566 | 0.0988178 |
| traditional_empirical_ampbin | 59 | 21377 | 0.0908734 | 0.301452 | -0.0245023 | 0.10374 |
| traditional_empirical_ampbin | 60 | 17029 | 0.100204 | 0.316551 | -0.0229512 | 0.102701 |
| traditional_empirical_ampbin | 61 | 18965 | 0.0853532 | 0.292153 | -0.0232526 | 0.102941 |
| traditional_empirical_ampbin | 62 | 19089 | 0.0896319 | 0.299386 | -0.0228041 | 0.101718 |
| traditional_empirical_ampbin | 63 | 18817 | 0.087544 | 0.295878 | -0.0193157 | 0.10078 |
| traditional_empirical_ampbin | 65 | 13038 | 0.112595 | 0.335552 | -0.0197709 | 0.095122 |
| ridge | 44 | 2038 | 0.0322186 | 0.179495 | -0.3028 | 0.504578 |
| ridge | 45 | 24333 | 0.0341778 | 0.184872 | -0.354197 | 0.521782 |
| ridge | 46 | 687 | 0.014765 | 0.121511 | -0.200323 | 0.397429 |
| ridge | 47 | 5276 | 0.0196495 | 0.140177 | -0.222548 | 0.455922 |
| ridge | 48 | 14000 | 0.0324497 | 0.180138 | -0.293581 | 0.505351 |
| ridge | 49 | 14815 | 0.0328715 | 0.181305 | -0.29252 | 0.498498 |
| ridge | 50 | 35217 | 0.0158627 | 0.125947 | -0.550929 | 0.415305 |
| ridge | 51 | 14740 | 0.0162309 | 0.127401 | -0.517415 | 0.422405 |
| ridge | 52 | 7152 | 0.0172287 | 0.131258 | -0.518568 | 0.419407 |
| ridge | 53 | 32200 | 0.0120926 | 0.109967 | -0.504396 | 0.361069 |
| ridge | 54 | 30440 | 0.0109926 | 0.104846 | -0.503133 | 0.360014 |
| ridge | 55 | 17387 | 0.0160606 | 0.12673 | -0.509388 | 0.414946 |
| ridge | 56 | 40148 | 0.015526 | 0.124603 | -0.521343 | 0.421748 |
| ridge | 57 | 13833 | 0.0327174 | 0.18088 | -0.306144 | 0.510424 |
| ridge | 58 | 16781 | 0.0143503 | 0.119793 | -0.480808 | 0.429463 |
| ridge | 59 | 21377 | 0.0266971 | 0.163392 | -0.235919 | 0.54599 |
| ridge | 60 | 17029 | 0.0285613 | 0.169001 | -0.210876 | 0.556699 |
| ridge | 61 | 18965 | 0.026178 | 0.161796 | -0.251846 | 0.565867 |
| ridge | 62 | 19089 | 0.0265689 | 0.163 | -0.240286 | 0.554423 |
| ridge | 63 | 18817 | 0.0234405 | 0.153103 | -0.346286 | 0.5331 |
| ridge | 65 | 13038 | 0.0220474 | 0.148484 | -0.336896 | 0.508823 |
| gradient_boosted_trees | 44 | 2038 | 0.00903358 | 0.0950451 | -0.0498869 | 0.112641 |
| gradient_boosted_trees | 45 | 24333 | 0.0103382 | 0.101677 | -0.0520234 | 0.117677 |
| gradient_boosted_trees | 46 | 687 | 0.00292356 | 0.05407 | -0.0413327 | 0.103492 |
| gradient_boosted_trees | 47 | 5276 | 0.00656526 | 0.0810263 | -0.0383626 | 0.101328 |
| gradient_boosted_trees | 48 | 14000 | 0.00953712 | 0.0976582 | -0.0527938 | 0.11447 |
| gradient_boosted_trees | 49 | 14815 | 0.00969126 | 0.0984442 | -0.0544529 | 0.113222 |
| gradient_boosted_trees | 50 | 35217 | 0.0051264 | 0.0715989 | -0.0247613 | 0.0993733 |
| gradient_boosted_trees | 51 | 14740 | 0.00435375 | 0.065983 | -0.0252054 | 0.100685 |
| gradient_boosted_trees | 52 | 7152 | 0.00488626 | 0.0699018 | -0.024371 | 0.0989273 |
| gradient_boosted_trees | 53 | 32200 | 0.0036201 | 0.0601673 | -0.0227514 | 0.0921643 |
| gradient_boosted_trees | 54 | 30440 | 0.0031405 | 0.0560402 | -0.0231061 | 0.0920064 |
| gradient_boosted_trees | 55 | 17387 | 0.0042373 | 0.0650945 | -0.027624 | 0.0995299 |
| gradient_boosted_trees | 56 | 40148 | 0.00426897 | 0.0653374 | -0.0258776 | 0.0997929 |
| gradient_boosted_trees | 57 | 13833 | 0.00942442 | 0.0970795 | -0.0544619 | 0.114923 |
| gradient_boosted_trees | 58 | 16781 | 0.00369903 | 0.0608197 | -0.0608971 | 0.111864 |
| gradient_boosted_trees | 59 | 21377 | 0.00879814 | 0.0937984 | -0.0651756 | 0.123892 |
| gradient_boosted_trees | 60 | 17029 | 0.00655087 | 0.0809374 | -0.0715254 | 0.121801 |
| gradient_boosted_trees | 61 | 18965 | 0.00645062 | 0.0803157 | -0.0726235 | 0.123739 |
| gradient_boosted_trees | 62 | 19089 | 0.00740476 | 0.0860509 | -0.0680214 | 0.122868 |
| gradient_boosted_trees | 63 | 18817 | 0.00762771 | 0.0873368 | -0.062277 | 0.119997 |
| gradient_boosted_trees | 65 | 13038 | 0.00533554 | 0.0730448 | -0.0537653 | 0.109101 |
| mlp | 44 | 2038 | 0.00860845 | 0.0927817 | 0.020766 | 0.19445 |
| mlp | 45 | 24333 | 0.00941853 | 0.0970491 | 0.0149276 | 0.196446 |
| mlp | 46 | 687 | 0.00255695 | 0.0505663 | 0.0361258 | 0.171869 |
| mlp | 47 | 5276 | 0.00619581 | 0.0787135 | 0.0256916 | 0.180537 |
| mlp | 48 | 14000 | 0.00908579 | 0.0953194 | 0.038539 | 0.202102 |
| mlp | 49 | 14815 | 0.00916419 | 0.0957298 | 0.0307412 | 0.200277 |
| mlp | 50 | 35217 | 0.00494678 | 0.0703334 | -0.0354359 | 0.137914 |
| mlp | 51 | 14740 | 0.00437044 | 0.0661093 | -0.0265137 | 0.1439 |
| mlp | 52 | 7152 | 0.00455736 | 0.0675082 | -0.0274368 | 0.146826 |
| mlp | 53 | 32200 | 0.00371502 | 0.0609509 | -0.0304869 | 0.127924 |
| mlp | 54 | 30440 | 0.00329223 | 0.0573779 | -0.0327879 | 0.128097 |
| mlp | 55 | 17387 | 0.00434171 | 0.0658916 | -0.031717 | 0.144095 |
| mlp | 56 | 40148 | 0.00436957 | 0.0661027 | -0.0354655 | 0.142395 |
| mlp | 57 | 13833 | 0.00844045 | 0.0918719 | 0.038682 | 0.203109 |
| mlp | 58 | 16781 | 0.00430669 | 0.0656253 | 0.0675624 | 0.179897 |
| mlp | 59 | 21377 | 0.00992211 | 0.0996098 | 0.0386799 | 0.327585 |
| mlp | 60 | 17029 | 0.00812352 | 0.0901306 | 0.0140616 | 0.328274 |
| mlp | 61 | 18965 | 0.00763494 | 0.0873781 | 0.0648955 | 0.309862 |
| mlp | 62 | 19089 | 0.00858454 | 0.0926528 | 0.0346951 | 0.324889 |
| mlp | 63 | 18817 | 0.00828645 | 0.0910299 | 0.0690593 | 0.256969 |
| mlp | 65 | 13038 | 0.00599077 | 0.0774001 | 0.107608 | 0.199361 |
| 1d_cnn | 44 | 2038 | 0.0248196 | 0.157542 | -2.05547 | 0.893493 |
| 1d_cnn | 45 | 24333 | 0.0263859 | 0.162437 | -2.11582 | 0.941272 |
| 1d_cnn | 46 | 687 | 0.0105116 | 0.102526 | -1.99024 | 0.700572 |
| 1d_cnn | 47 | 5276 | 0.0154339 | 0.124233 | -2.05001 | 0.77818 |
| 1d_cnn | 48 | 14000 | 0.0248796 | 0.157733 | -2.01046 | 0.863253 |
| 1d_cnn | 49 | 14815 | 0.0252403 | 0.158872 | -2.02402 | 0.888925 |
| 1d_cnn | 50 | 35217 | 0.0125994 | 0.112247 | -2.58339 | 0.631745 |
| 1d_cnn | 51 | 14740 | 0.012765 | 0.112982 | -2.51428 | 0.683957 |
| 1d_cnn | 52 | 7152 | 0.0134989 | 0.116185 | -2.52701 | 0.67109 |
| 1d_cnn | 53 | 32200 | 0.00969586 | 0.0984676 | -2.45038 | 0.488028 |
| 1d_cnn | 54 | 30440 | 0.00875108 | 0.0935472 | -2.44718 | 0.483535 |
| 1d_cnn | 55 | 17387 | 0.0125365 | 0.111966 | -2.49612 | 0.660518 |
| 1d_cnn | 56 | 40148 | 0.0122525 | 0.110691 | -2.55785 | 0.65941 |
| 1d_cnn | 57 | 13833 | 0.0245705 | 0.15675 | -2.00774 | 0.886118 |
| 1d_cnn | 58 | 16781 | 0.0103346 | 0.101659 | -2.02572 | 0.891938 |
| 1d_cnn | 59 | 21377 | 0.0205843 | 0.143472 | -1.61836 | 0.763805 |
| 1d_cnn | 60 | 17029 | 0.0210419 | 0.145058 | -1.67219 | 0.868985 |
| 1d_cnn | 61 | 18965 | 0.0190997 | 0.138202 | -1.69568 | 0.7801 |
| 1d_cnn | 62 | 19089 | 0.0198147 | 0.140765 | -1.63676 | 0.7785 |
| 1d_cnn | 63 | 18817 | 0.0181013 | 0.134541 | -1.67912 | 0.834892 |
| 1d_cnn | 65 | 13038 | 0.0159802 | 0.126413 | -1.59272 | 0.740611 |
| empirical_residual_boosted_fusion_new | 44 | 2038 | 0.0107763 | 0.103809 | -0.0435176 | 0.108304 |
| empirical_residual_boosted_fusion_new | 45 | 24333 | 0.0122442 | 0.110654 | -0.048596 | 0.11176 |
| empirical_residual_boosted_fusion_new | 46 | 687 | 0.00393949 | 0.0627653 | -0.0429718 | 0.097758 |
| empirical_residual_boosted_fusion_new | 47 | 5276 | 0.00772138 | 0.0878714 | -0.0388158 | 0.100516 |
| empirical_residual_boosted_fusion_new | 48 | 14000 | 0.0115059 | 0.107266 | -0.0468807 | 0.110592 |
| empirical_residual_boosted_fusion_new | 49 | 14815 | 0.0117026 | 0.108179 | -0.0462888 | 0.109931 |
| empirical_residual_boosted_fusion_new | 50 | 35217 | 0.00618456 | 0.078642 | -0.0439314 | 0.0992748 |
| empirical_residual_boosted_fusion_new | 51 | 14740 | 0.00547455 | 0.0739902 | -0.0414026 | 0.0989472 |
| empirical_residual_boosted_fusion_new | 52 | 7152 | 0.00592715 | 0.076988 | -0.0402582 | 0.0988359 |
| empirical_residual_boosted_fusion_new | 53 | 32200 | 0.00460313 | 0.0678464 | -0.0425171 | 0.0930128 |
| empirical_residual_boosted_fusion_new | 54 | 30440 | 0.00407027 | 0.0637987 | -0.0430347 | 0.0921345 |
| empirical_residual_boosted_fusion_new | 55 | 17387 | 0.00537907 | 0.0733421 | -0.0449041 | 0.0993754 |
| empirical_residual_boosted_fusion_new | 56 | 40148 | 0.00534189 | 0.0730882 | -0.0445917 | 0.0990987 |
| empirical_residual_boosted_fusion_new | 57 | 13833 | 0.0113759 | 0.106658 | -0.0466721 | 0.111059 |
| empirical_residual_boosted_fusion_new | 58 | 16781 | 0.00497806 | 0.0705554 | -0.04282 | 0.104998 |
| empirical_residual_boosted_fusion_new | 59 | 21377 | 0.0108242 | 0.104039 | -0.0507183 | 0.118312 |
| empirical_residual_boosted_fusion_new | 60 | 17029 | 0.00884389 | 0.0940419 | -0.0514527 | 0.115973 |
| empirical_residual_boosted_fusion_new | 61 | 18965 | 0.008573 | 0.0925905 | -0.0506327 | 0.114824 |
| empirical_residual_boosted_fusion_new | 62 | 19089 | 0.00938022 | 0.0968515 | -0.0502252 | 0.115294 |
| empirical_residual_boosted_fusion_new | 63 | 18817 | 0.00944171 | 0.0971684 | -0.0461212 | 0.112117 |
| empirical_residual_boosted_fusion_new | 65 | 13038 | 0.00726132 | 0.0852134 | -0.0416873 | 0.102669 |

## Systematics and Caveats

- The target is the raw waveform template quality requested by P10, not an external truth-energy label.
- The timing residual is a template-phase proxy derived from the same aligned pulse. It detects morphology-induced phase bias but is not a full downstream event-time closure.
- Calibration and analysis runs are disjoint, and no run id or event id enters the feature matrix.
- The new residual-fusion architecture can only be trusted inside the amplitude/stave support represented in the calibration runs; extrapolation beyond the selected B-stack pulse population is not claimed.
- The 1D-CNN is conditional on scalar pulse descriptors plus sample coordinate, so it tests neural sequence generation rather than waveform autoencoding from the answer waveform.

## Conclusion

`gradient_boosted_trees` is the named winner in `result.json`. It has q-template MSE `0.00633397` and timing sigma68 `0.109214` ns on run-held-out analysis pulses. No follow-up ticket was appended because the current queue already contains P10/P11 follow-up coverage and this run should append at most one novel ticket.
