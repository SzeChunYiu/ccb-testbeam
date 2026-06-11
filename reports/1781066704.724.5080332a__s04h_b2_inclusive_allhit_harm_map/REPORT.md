# S04h: B2-inclusive all-hit timing closure harm map

- **Ticket:** `1781066704.724.5080332a`
- **Worker:** `testbeam-laptop-2`
- **Input:** raw B-stack ROOT under `data/root/root`
- **Output:** `reports/1781066704.724.5080332a__s04h_b2_inclusive_allhit_harm_map`
- **Git commit:** `5350839182da2984a79cb76b16bc5d69af10dacd`

## Preregistered Question

Does adding B2-inclusive all-hit topology to external B-stack timing closure improve any supported atom, or does it systematically harm closure? The analysis freezes the population before modeling: an event enters the closure only if B2, B4, B6, and B8 all pass the raw median-baseline selected-pulse gate `A > 1000 ADC`. Models are trained only on calibration runs and scored on held-out runs 58, 59, 60, 61, 62, 63, and 65.

The primary estimand is the held-out-run mean robust width

`sigma68(r, m, S) = [q84(Delta t_m,S,r) - q16(Delta t_m,S,r)] / 2`,

where `S` is either the three downstream pairs `(B4,B6), (B4,B8), (B6,B8)` or all six B2/B4/B6/B8 pairs. The B2-inclusion harm statistic is

`H_m = sigma68_m(all six pairs) - sigma68_m(downstream only)`.

Negative `H_m` would mean B2-inclusive all-hit closure improves relative to the downstream reference; positive `H_m` means B2 inclusion widens the closure.

## Raw-ROOT Reproduction Gate

The count gate was rebuilt directly from `h101/HRDv` in the raw ROOT files. The baseline is the median of samples 0-3 per channel, and selected pulses satisfy `max(HRDv - baseline) > 1000 ADC`.

| quantity                           |   expected |   observed |   delta | pass   |
|:-----------------------------------|-----------:|-----------:|--------:|:-------|
| selected_pulses_total              |     640737 |     640737 |       0 | True   |
| sample_ii_analysis_selected_pulses |     125096 |     125096 |       0 | True   |
| run64_selected_pulses              |      14630 |      14630 |       0 | True   |
| run64_all_hit_events               |        207 |        207 |       0 | True   |
| heldout_all_hit_events             |       3774 |       3774 |       0 | True   |

The reproduction gate passes. No sorted table or previous report artifact is used for the gate.

## Methods

Let `t_i` be the CFD20 time of stave `i` after a fixed time-of-flight geometry subtraction, and let the downstream training target be

`y_i = t_i - mean(t_j : j in {B4, B6, B8}, j != i)`.

The strong traditional method is a Ridge explicit timewalk correction using `log(1+A)`, `log(1+A)^2`, `1/sqrt(A)`, area/amplitude, peak sample, stave identity, and amplitude-bin by stave interactions. Hyperparameters are chosen by grouped CV over training runs.

The ML/NN bakeoff uses the same downstream target and the same held-out runs. The feature vector contains the normalized 18-sample waveform, amplitude, area/amplitude, peak sample, baseline, B2 amplitude ratio, peak spread, baseline span, event flags, and stave identity. Models are:

- `ridge`: linear waveform Ridge.
- `hgb`: histogram gradient-boosted trees.
- `mlp`: scikit-learn multilayer perceptron.
- `cnn1d`: compact 1D convolutional regressor over waveform samples plus summary features.
- `gated_mixer`: new architecture for this ticket; a learned gate mixes a waveform branch and a summary/topology branch.

Controls are reported separately: run-only, target-stave-excluded HGB, and shuffled-target Ridge.

## Head-to-Head Result

Primary metric: all-six B2-inclusive held-out-run `sigma68`, with 95% CIs from non-parametric bootstrap over held-out runs. The table below contains production methods only; controls are deliberately ineligible to win.

| method                        |   mean_run_sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   mean_run_full_rms_ns |   mean_run_tail_frac_abs_gt5ns |   b2_inclusion_harm_delta_ns |   b2_inclusion_harm_ci_low_ns |   b2_inclusion_harm_ci_high_ns |
|:------------------------------|----------------------:|--------------------:|---------------------:|-----------------------:|-------------------------------:|-----------------------------:|------------------------------:|-------------------------------:|
| cnn1d                         |               3.09715 |             2.82707 |              3.39191 |                12.7323 |                       0.117749 |                      1.20495 |                      0.914551 |                        1.49897 |
| gated_mixer                   |               3.10709 |             2.82532 |              3.40929 |                12.8467 |                       0.122208 |                      1.19871 |                      0.924912 |                        1.48704 |
| hgb                           |               3.12637 |             2.77701 |              3.52008 |                12.7751 |                       0.138832 |                      1.19597 |                      0.901801 |                        1.52881 |
| traditional_explicit_timewalk |               3.16909 |             2.92403 |              3.45322 |                12.8115 |                       0.142732 |                      1.35265 |                      1.03637  |                        1.67556 |
| mlp                           |               3.39524 |             3.01642 |              3.79814 |                12.7538 |                       0.145058 |                      1.2879  |                      0.952959 |                        1.648   |
| ridge                         |               3.89304 |             3.55183 |              4.3827  |                12.8993 |                       0.169049 |                      1.82413 |                      1.45703  |                        2.31152 |

Winner on the preregistered all-six metric: **cnn1d**, with sigma68 3.097 [2.827, 3.392] ns. Relative to the traditional explicit-timewalk comparator, the point delta is `-0.072 ns`.

## Downstream-Only Diagnostic

The same all-hit events are scored after excluding B2-containing pairs:

| method                        |   mean_run_sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   mean_run_full_rms_ns |   mean_run_tail_frac_abs_gt5ns |
|:------------------------------|----------------------:|--------------------:|---------------------:|-----------------------:|-------------------------------:|
| traditional_explicit_timewalk |               1.81643 |             1.72523 |              1.90368 |                5.21328 |                      0.0668855 |
| cnn1d                         |               1.89219 |             1.80609 |              2.00113 |                5.01549 |                      0.0247132 |
| gated_mixer                   |               1.90838 |             1.8184  |              2.00644 |                5.1613  |                      0.0285959 |
| hgb                           |               1.9304  |             1.84877 |              2.0147  |                5.17988 |                      0.0599337 |
| ridge                         |               2.06891 |             2.00613 |              2.14772 |                5.43665 |                      0.0839012 |
| mlp                           |               2.10734 |             2.04364 |              2.16803 |                5.10584 |                      0.0631968 |

For every production method, `H_m` is positive: adding B2-containing all-hit pairs widens the closure. The result is therefore a harm map, not an adoption gate for B2-inclusive timing constraints.

## Per-Run Table

|   run | method                            | pair_scope      |   n_all_hit_events |   n_pair_residuals |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |
|------:|:----------------------------------|:----------------|-------------------:|-------------------:|-------------:|--------------:|----------------------:|
|    58 | cfd20_uncorrected                 | all_six_with_b2 |                 72 |                432 |      3.8072  |      19.3819  |             0.298611  |
|    58 | cfd20_uncorrected                 | downstream_only |                 72 |                216 |      3.10179 |       5.72687 |             0.226852  |
|    58 | traditional_explicit_timewalk     | all_six_with_b2 |                 72 |                432 |      3.89078 |      19.0649  |             0.215278  |
|    58 | traditional_explicit_timewalk     | downstream_only |                 72 |                216 |      1.83062 |       4.46147 |             0.087963  |
|    58 | ridge                             | all_six_with_b2 |                 72 |                432 |      5.23199 |      19.2489  |             0.243056  |
|    58 | ridge                             | downstream_only |                 72 |                216 |      2.01204 |       4.57584 |             0.101852  |
|    58 | hgb                               | all_six_with_b2 |                 72 |                432 |      3.97081 |      19.3863  |             0.219907  |
|    58 | hgb                               | downstream_only |                 72 |                216 |      2.00945 |       4.99559 |             0.087963  |
|    58 | mlp                               | all_six_with_b2 |                 72 |                432 |      4.38999 |      19.1402  |             0.224537  |
|    58 | mlp                               | downstream_only |                 72 |                216 |      2.223   |       4.25216 |             0.0787037 |
|    58 | cnn1d                             | all_six_with_b2 |                 72 |                432 |      3.77419 |      19.0458  |             0.180556  |
|    58 | cnn1d                             | downstream_only |                 72 |                216 |      1.8581  |       4.15184 |             0.0231481 |
|    58 | gated_mixer                       | all_six_with_b2 |                 72 |                432 |      3.8155  |      19.3381  |             0.185185  |
|    58 | gated_mixer                       | downstream_only |                 72 |                216 |      1.93656 |       4.95989 |             0.0324074 |
|    58 | run_only_control                  | all_six_with_b2 |                 72 |                432 |      4.24805 |      19.2011  |             0.238426  |
|    58 | run_only_control                  | downstream_only |                 72 |                216 |      2.02186 |       4.72536 |             0.115741  |
|    58 | target_stave_excluded_hgb_control | all_six_with_b2 |                 72 |                432 |      3.9854  |      19.204   |             0.217593  |
|    58 | target_stave_excluded_hgb_control | downstream_only |                 72 |                216 |      2.04432 |       4.24287 |             0.0972222 |
|    58 | shuffled_target_ridge_control     | all_six_with_b2 |                 72 |                432 |      3.25756 |      19.2556  |             0.233796  |
|    58 | shuffled_target_ridge_control     | downstream_only |                 72 |                216 |      2.55537 |       5.25354 |             0.115741  |
|    59 | cfd20_uncorrected                 | all_six_with_b2 |                749 |               4494 |      3.40146 |      11.9117  |             0.247219  |
|    59 | cfd20_uncorrected                 | downstream_only |                749 |               2247 |      3.18762 |       6.47263 |             0.22964   |
|    59 | traditional_explicit_timewalk     | all_six_with_b2 |                749 |               4494 |      3.04355 |      11.5923  |             0.144192  |
|    59 | traditional_explicit_timewalk     | downstream_only |                749 |               2247 |      1.7569  |       5.52293 |             0.0614152 |
|    59 | ridge                             | all_six_with_b2 |                749 |               4494 |      3.65208 |      11.5748  |             0.161771  |
|    59 | ridge                             | downstream_only |                749 |               2247 |      1.9604  |       5.36219 |             0.0698709 |
|    59 | hgb                               | all_six_with_b2 |                749 |               4494 |      2.91833 |      11.5226  |             0.142635  |
|    59 | hgb                               | downstream_only |                749 |               2247 |      1.81815 |       5.47487 |             0.058745  |
|    59 | mlp                               | all_six_with_b2 |                749 |               4494 |      3.22831 |      11.4164  |             0.14931   |
|    59 | mlp                               | downstream_only |                749 |               2247 |      2.05318 |       5.22957 |             0.0725412 |
|    59 | cnn1d                             | all_six_with_b2 |                749 |               4494 |      2.9724  |      11.5009  |             0.120605  |
|    59 | cnn1d                             | downstream_only |                749 |               2247 |      1.81602 |       5.29465 |             0.023587  |
|    59 | gated_mixer                       | all_six_with_b2 |                749 |               4494 |      2.98566 |      11.5913  |             0.124166  |
|    59 | gated_mixer                       | downstream_only |                749 |               2247 |      1.82352 |       5.29601 |             0.0253672 |
|    59 | run_only_control                  | all_six_with_b2 |                749 |               4494 |      3.64632 |      11.7004  |             0.171785  |
|    59 | run_only_control                  | downstream_only |                749 |               2247 |      2.09455 |       5.86598 |             0.109034  |
|    59 | target_stave_excluded_hgb_control | all_six_with_b2 |                749 |               4494 |      3.08507 |      11.5537  |             0.15287   |
|    59 | target_stave_excluded_hgb_control | downstream_only |                749 |               2247 |      1.9386  |       5.26152 |             0.0694259 |
|    59 | shuffled_target_ridge_control     | all_six_with_b2 |                749 |               4494 |      2.80444 |      11.7516  |             0.184691  |
|    59 | shuffled_target_ridge_control     | downstream_only |                749 |               2247 |      2.49567 |       6.14152 |             0.115265  |
|    60 | cfd20_uncorrected                 | all_six_with_b2 |                802 |               4812 |      2.97681 |       9.8929  |             0.172901  |
|    60 | cfd20_uncorrected                 | downstream_only |                802 |               2406 |      3.12455 |       7.87869 |             0.221945  |
|    60 | traditional_explicit_timewalk     | all_six_with_b2 |                802 |               4812 |      2.80689 |       9.44035 |             0.0887365 |
|    60 | traditional_explicit_timewalk     | downstream_only |                802 |               2406 |      1.97344 |       6.89749 |             0.0793849 |
|    60 | ridge                             | all_six_with_b2 |                802 |               4812 |      3.39941 |       9.59374 |             0.114713  |
|    60 | ridge                             | downstream_only |                802 |               2406 |      2.03865 |       7.08394 |             0.0872818 |
|    60 | hgb                               | all_six_with_b2 |                802 |               4812 |      2.56755 |       9.25294 |             0.0710723 |
|    60 | hgb                               | downstream_only |                802 |               2406 |      1.77113 |       6.50815 |             0.0515378 |
|    60 | mlp                               | all_six_with_b2 |                802 |               4812 |      2.7881  |       9.26204 |             0.0802161 |
|    60 | mlp                               | downstream_only |                802 |               2406 |      1.96783 |       6.46055 |             0.0548628 |
|    60 | cnn1d                             | all_six_with_b2 |                802 |               4812 |      2.58311 |       9.26225 |             0.0534081 |
|    60 | cnn1d                             | downstream_only |                802 |               2406 |      1.84191 |       6.54406 |             0.024522  |
|    60 | gated_mixer                       | all_six_with_b2 |                802 |               4812 |      2.63139 |       9.41707 |             0.0565254 |
|    60 | gated_mixer                       | downstream_only |                802 |               2406 |      1.86844 |       6.74876 |             0.0253533 |
|    60 | run_only_control                  | all_six_with_b2 |                802 |               4812 |      3.22091 |       9.52769 |             0.10453   |
|    60 | run_only_control                  | downstream_only |                802 |               2406 |      2.22712 |       7.17181 |             0.120532  |
|    60 | target_stave_excluded_hgb_control | all_six_with_b2 |                802 |               4812 |      2.907   |       9.25177 |             0.108063  |
|    60 | target_stave_excluded_hgb_control | downstream_only |                802 |               2406 |      2.1212  |       6.77519 |             0.110973  |
|    60 | shuffled_target_ridge_control     | all_six_with_b2 |                802 |               4812 |      2.46609 |       9.72494 |             0.109102  |
|    60 | shuffled_target_ridge_control     | downstream_only |                802 |               2406 |      2.498   |       7.59399 |             0.111388  |
|    61 | cfd20_uncorrected                 | all_six_with_b2 |                925 |               5550 |      2.7603  |       8.16963 |             0.145225  |
|    61 | cfd20_uncorrected                 | downstream_only |                925 |               2775 |      2.9148  |       7.13033 |             0.162162  |
|    61 | traditional_explicit_timewalk     | all_six_with_b2 |                925 |               5550 |      2.97029 |       7.86869 |             0.0911712 |
|    61 | traditional_explicit_timewalk     | downstream_only |                925 |               2775 |      1.97289 |       6.53094 |             0.0814414 |
|    61 | ridge                             | all_six_with_b2 |                925 |               5550 |      3.59607 |       7.89776 |             0.138739  |
|    61 | ridge                             | downstream_only |                925 |               2775 |      2.25175 |       6.58077 |             0.118198  |
|    61 | hgb                               | all_six_with_b2 |                925 |               5550 |      2.82088 |       7.81834 |             0.0891892 |
|    61 | hgb                               | downstream_only |                925 |               2775 |      2.02451 |       6.33545 |             0.0659459 |
|    61 | mlp                               | all_six_with_b2 |                925 |               5550 |      3.08511 |       7.6606  |             0.103604  |
|    61 | mlp                               | downstream_only |                925 |               2775 |      2.17806 |       6.20272 |             0.0735135 |
|    61 | cnn1d                             | all_six_with_b2 |                925 |               5550 |      3.00103 |       7.77311 |             0.0812613 |
|    61 | cnn1d                             | downstream_only |                925 |               2775 |      2.15809 |       6.3511  |             0.0454054 |
|    61 | gated_mixer                       | all_six_with_b2 |                925 |               5550 |      3.00232 |       7.70421 |             0.087027  |
|    61 | gated_mixer                       | downstream_only |                925 |               2775 |      2.14342 |       6.19113 |             0.0472072 |
|    61 | run_only_control                  | all_six_with_b2 |                925 |               5550 |      3.58007 |       7.95939 |             0.141441  |
|    61 | run_only_control                  | downstream_only |                925 |               2775 |      2.38805 |       6.76425 |             0.156036  |
|    61 | target_stave_excluded_hgb_control | all_six_with_b2 |                925 |               5550 |      3.12035 |       7.82206 |             0.113514  |
|    61 | target_stave_excluded_hgb_control | downstream_only |                925 |               2775 |      2.26119 |       6.57184 |             0.108468  |
|    61 | shuffled_target_ridge_control     | all_six_with_b2 |                925 |               5550 |      2.2835  |       8.01491 |             0.0891892 |
|    61 | shuffled_target_ridge_control     | downstream_only |                925 |               2775 |      2.27806 |       6.86748 |             0.0745946 |

## Hyperparameter CV

CV is grouped by training run. The target table reports residual-target sigma68 for model selection; final claims are made only on held-out run closure.

| model       | feature_set       |   alpha |   fold |   sigma68_ns | candidate                                                     |   target_sigma68_ns |
|:------------|:------------------|--------:|-------:|-------------:|:--------------------------------------------------------------|--------------------:|
| traditional | amp_poly_by_stave |     0.1 |      1 |      2.12627 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     0.1 |      2 |      2.16174 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     0.1 |      3 |      2.41232 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     0.1 |      4 |      2.31143 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     0.1 |     -1 |      2.25294 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     1   |      1 |      2.13706 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     1   |      2 |      2.15268 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     1   |      3 |      2.39568 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     1   |      4 |      2.3109  | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |     1   |     -1 |      2.24908 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |    10   |      1 |      2.09173 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |    10   |      2 |      2.13438 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |    10   |      3 |      2.36553 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |    10   |      4 |      2.28467 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |    10   |     -1 |      2.21908 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |   100   |      1 |      2.21425 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |   100   |      2 |      1.9922  | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |   100   |      3 |      2.22021 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |   100   |      4 |      2.10717 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |   100   |     -1 |      2.13346 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |  1000   |      1 |      2.05637 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |  1000   |      2 |      1.84519 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |  1000   |      3 |      1.95524 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |  1000   |      4 |      1.89407 | nan                                                           |           nan       |
| traditional | amp_poly_by_stave |  1000   |     -1 |      1.93772 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     0.1 |      1 |      2.35254 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     0.1 |      2 |      1.97367 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     0.1 |      3 |      2.17266 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     0.1 |      4 |      2.29165 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     0.1 |     -1 |      2.19763 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     1   |      1 |      2.35156 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     1   |      2 |      1.9725  | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     1   |      3 |      2.17079 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     1   |      4 |      2.28985 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |     1   |     -1 |      2.19618 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |    10   |      1 |      2.32353 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |    10   |      2 |      1.94548 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |    10   |      3 |      2.1598  | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |    10   |      4 |      2.29338 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |    10   |     -1 |      2.18055 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |   100   |      1 |      2.2339  | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |   100   |      2 |      1.9076  | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |   100   |      3 |      2.06478 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |   100   |      4 |      2.17506 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |   100   |     -1 |      2.09533 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |  1000   |      1 |      1.7867  | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |  1000   |      2 |      1.56931 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |  1000   |      3 |      1.68363 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |  1000   |      4 |      1.75429 | nan                                                           |           nan       |
| traditional | amp_bin_by_stave  |  1000   |     -1 |      1.69848 | nan                                                           |           nan       |
| ridge       | nan               |   nan   |      1 |    nan       | {"alpha": 0.1}                                                |             1.6106  |
| ridge       | nan               |   nan   |      2 |    nan       | {"alpha": 0.1}                                                |             1.5817  |
| ridge       | nan               |   nan   |      3 |    nan       | {"alpha": 0.1}                                                |             1.78897 |
| ridge       | nan               |   nan   |      4 |    nan       | {"alpha": 0.1}                                                |             1.64354 |
| ridge       | nan               |   nan   |     -1 |    nan       | {"alpha": 0.1}                                                |             1.6562  |
| ridge       | nan               |   nan   |      1 |    nan       | {"alpha": 1.0}                                                |             1.59318 |
| ridge       | nan               |   nan   |      2 |    nan       | {"alpha": 1.0}                                                |             1.57758 |
| ridge       | nan               |   nan   |      3 |    nan       | {"alpha": 1.0}                                                |             1.78019 |
| ridge       | nan               |   nan   |      4 |    nan       | {"alpha": 1.0}                                                |             1.62894 |
| ridge       | nan               |   nan   |     -1 |    nan       | {"alpha": 1.0}                                                |             1.64497 |
| ridge       | nan               |   nan   |      1 |    nan       | {"alpha": 10.0}                                               |             1.57329 |
| ridge       | nan               |   nan   |      2 |    nan       | {"alpha": 10.0}                                               |             1.54048 |
| ridge       | nan               |   nan   |      3 |    nan       | {"alpha": 10.0}                                               |             1.73249 |
| ridge       | nan               |   nan   |      4 |    nan       | {"alpha": 10.0}                                               |             1.65227 |
| ridge       | nan               |   nan   |     -1 |    nan       | {"alpha": 10.0}                                               |             1.62463 |
| ridge       | nan               |   nan   |      1 |    nan       | {"alpha": 100.0}                                              |             1.45333 |
| ridge       | nan               |   nan   |      2 |    nan       | {"alpha": 100.0}                                              |             1.44139 |
| ridge       | nan               |   nan   |      3 |    nan       | {"alpha": 100.0}                                              |             1.63923 |
| ridge       | nan               |   nan   |      4 |    nan       | {"alpha": 100.0}                                              |             1.5727  |
| ridge       | nan               |   nan   |     -1 |    nan       | {"alpha": 100.0}                                              |             1.52666 |
| hgb         | nan               |   nan   |      1 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 15} |             1.47247 |
| hgb         | nan               |   nan   |      2 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 15} |             1.67935 |
| hgb         | nan               |   nan   |      3 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 15} |             1.4687  |
| hgb         | nan               |   nan   |      4 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 15} |             1.61931 |
| hgb         | nan               |   nan   |     -1 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 15} |             1.55996 |
| hgb         | nan               |   nan   |      1 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 31} |             1.50464 |
| hgb         | nan               |   nan   |      2 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 31} |             1.70453 |
| hgb         | nan               |   nan   |      3 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 31} |             1.47996 |
| hgb         | nan               |   nan   |      4 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 31} |             1.53021 |
| hgb         | nan               |   nan   |     -1 |    nan       | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 31} |             1.55484 |

## Controls and Leakage Sentinels

| control                           | best                                                                                                      |   cv_rows |
|:----------------------------------|:----------------------------------------------------------------------------------------------------------|----------:|
| run_only_control                  | {"alpha": 100.0, "model": "ridge", "score": 1.4527392756938933}                                           |        20 |
| target_stave_excluded_hgb_control | {"learning_rate": 0.06, "max_iter": 80, "max_leaf_nodes": 31, "model": "hgb", "score": 1.583682579642565} |        10 |
| shuffled_target_ridge_control     | {"alpha": 100.0, "model": "ridge", "score": 3.848638626337052}                                            |        20 |

All-six held-out scores for ineligible controls:

| method                            |   mean_run_sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   b2_inclusion_harm_delta_ns |   b2_inclusion_harm_ci_low_ns |   b2_inclusion_harm_ci_high_ns |
|:----------------------------------|----------------------:|--------------------:|---------------------:|-----------------------------:|------------------------------:|-------------------------------:|
| shuffled_target_ridge_control     |               2.80036 |             2.54046 |              3.03437 |                     0.292603 |                     0.0929199 |                       0.490552 |
| target_stave_excluded_hgb_control |               3.38361 |             3.03422 |              3.74926 |                     1.28628  |                     0.970144  |                       1.61429  |
| run_only_control                  |               3.69099 |             3.46109 |              3.9223  |                     1.55601  |                     1.26738   |                       1.84409  |

Run-only and target-stave-excluded controls test whether run period or peer topology can imitate a waveform correction. The shuffled-target control is a lower-bound leakage sentinel; it should not win a genuine timing closure benchmark.

## Supported Atom Harm Map

The atom table is evaluated for the winning production method and keeps only cells with at least 25 held-out all-hit events.

| atom                 | level        |   n_all_hit_events |   all_six_sigma68_ns |   downstream_sigma68_ns |   b2_inclusion_harm_delta_ns |   all_six_tail_frac_abs_gt5ns |
|:---------------------|:-------------|-------------------:|---------------------:|------------------------:|-----------------------------:|------------------------------:|
| peak_spread_bin      | pathological |                 78 |             38.7043  |                 3.0203  |                    35.684    |                     0.476496  |
| event_anomaly_any    | True         |                275 |             19.5294  |                 2.42689 |                    17.1026   |                     0.314545  |
| baseline_bin         | excursion    |                213 |             17.8361  |                 2.26083 |                    15.5752   |                     0.273083  |
| event_saturation_any | True         |                 36 |             14.8968  |                 1.85013 |                    13.0467   |                     0.439815  |
| peak_spread_bin      | wide         |                164 |             14.3519  |                 2.12665 |                    12.2253   |                     0.322154  |
| baseline_bin         | quiet        |                105 |             13.5545  |                 2.06278 |                    11.4917   |                     0.215873  |
| b2_amp_bin           | very_high    |                 82 |             11.3348  |                 2.00477 |                     9.33004  |                     0.384146  |
| b2_ratio_bin         | b2_extreme   |                227 |             11.0975  |                 1.87354 |                     9.22401  |                     0.35536   |
| b2_amp_bin           | high         |                783 |              4.23957 |                 2.07839 |                     2.16118  |                     0.219455  |
| run                  | 58           |                 72 |              3.77419 |                 1.8581  |                     1.91609  |                     0.180556  |
| b2_ratio_bin         | b2_high      |                610 |              3.59784 |                 1.98396 |                     1.61388  |                     0.16694   |
| run                  | 65           |                 63 |              3.59451 |                 2.00685 |                     1.58766  |                     0.169312  |
| run                  | 63           |                365 |              3.04587 |                 1.71716 |                     1.3287   |                     0.152055  |
| peak_spread_bin      | moderate     |               1096 |              3.13101 |                 1.91768 |                     1.21333  |                     0.12576   |
| run                  | 59           |                749 |              2.9724  |                 1.81602 |                     1.15637  |                     0.120605  |
| event_dropout_any    | False        |               3503 |              2.87219 |                 1.91966 |                     0.952533 |                     0.0879246 |
| event_saturation_any | False        |               3738 |              2.82888 |                 1.92022 |                     0.908668 |                     0.0869895 |
| baseline_bin         | shifted      |               3456 |              2.78485 |                 1.89825 |                     0.886605 |                     0.0752797 |
| event_anomaly_any    | False        |               3499 |              2.77003 |                 1.89301 |                     0.877011 |                     0.0727351 |
| run                  | 62           |                798 |              2.70892 |                 1.84721 |                     0.861703 |                     0.0670426 |
| run                  | 61           |                925 |              3.00103 |                 2.15809 |                     0.842941 |                     0.0812613 |
| b2_ratio_bin         | balanced     |               2776 |              2.65111 |                 1.90439 |                     0.746727 |                     0.050072  |
| run                  | 60           |                802 |              2.58311 |                 1.84191 |                     0.741203 |                     0.0534081 |
| b2_amp_bin           | mid          |               2769 |              2.60056 |                 1.88041 |                     0.72015  |                     0.0448417 |
| peak_spread_bin      | tight        |               2436 |              2.61387 |                 1.89557 |                     0.718306 |                     0.0464559 |
| event_dropout_any    | True         |                271 |              2.42586 |                 1.89673 |                     0.529134 |                     0.121771  |
| b2_ratio_bin         | b2_low       |                161 |              2.54961 |                 2.02669 |                     0.522914 |                     0.121118  |
| b2_amp_bin           | low          |                140 |              1.97561 |                 1.76701 |                     0.208603 |                     0.0964286 |

The largest harms concentrate in B2-amplitude imbalance, broad peak-spread, and baseline-excursion atoms. Those are detector/topology support failures, not evidence that a more flexible timing correction should absorb B2 as a precision constraint.

## Systematics and Caveats

The study is raw-data anchored but still conditional on the selected-pulse definition. CFD20 timing and the fixed geometry subtraction are inherited from prior timing studies; changing the leading-edge fraction would change absolute widths but not the run-held-out comparison design. The all-hit population is sparse in some runs, so CIs bootstrap runs rather than individual pair rows. The neural networks are deliberately compact laptop-budget models, and the sklearn MLP is treated as a budget-limited comparator rather than a fully optimized network. Their failure to make B2 inclusion helpful is evidence against easy adoption, not a theorem about all possible architectures. The target is a same-event closure observable, not absolute particle time or PID truth.

## Verdict

The preregistered all-six B2-inclusive winner is cnn1d with mean held-out-run sigma68 3.097 ns [2.827, 3.392]. The traditional explicit-timewalk comparator gives 3.169 ns [2.924, 3.453]. B2 inclusion is harmful rather than helpful: all production methods have positive all-six minus downstream-only harm deltas. The result agrees with the fleet summary that B2-containing residuals are topology/support dominated.

## Next Experiment

S04i: support-preserving B2 abstention rule for all-hit timing closure

Question: can a preregistered B2 abstention rule based on B2 amplitude imbalance, peak-spread, and baseline-excursion atoms recover downstream-like closure while retaining a useful fraction of all-hit events? Expected information gain: converts the S04h harm map into an operational accept/abstain boundary with run-held-out CIs, preventing unsupported B2-inclusive timing constraints from contaminating pile-up or same-particle timing consumers.
