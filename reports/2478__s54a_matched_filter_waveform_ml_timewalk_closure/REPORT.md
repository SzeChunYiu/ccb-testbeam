# S54a/#2478: Matched-Filter Rise-Shape Timing versus Waveform ML Time-Walk Closure

## Abstract

This ticket benchmarks a strong traditional waveform timing correction against ridge regression, gradient-boosted trees, MLP, 1D-CNN, a compact pair transformer, and a new rise/tail-gated CNN. The raw ROOT selected-pulse number is reproduced before model fitting. The benchmark is split by held-out run and uses paired run bootstrap confidence intervals. The selected winner written to `result.json` is **mlp**.

## Ticket and Data Provenance

Claim recovery was necessary because `tn-ticket claim testbeam-laptop-4 --project testbeam` returned the known `null` pseudo-ticket pattern without labeling an issue. The claimed issue is #2478 after a direct label swap to `factory:claimed` and `worker:testbeam-laptop-4`; the helper was not run a second time.

Ticket text: `claim_helper_command: tn-ticket claim testbeam-laptop-4 --project testbeam claim_helper_stderr: null claim_helper_stdout: # null  null manual_claim_issue: 2478 manual_claim_command: gh issue edit 2478 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open #2478 S54a: Matched-filter rise-shape timing versus waveform ML time-walk closure `

Raw `h101/HRDv` waveforms were read from `/home/billy/ccb-data/data/extracted/root/root`. The B-stave channels are `{'B2': 0, 'B4': 2, 'B6': 4, 'B8': 6}`. A selected pulse is a baseline-subtracted B-stave channel with amplitude above `1000` ADC using the four pretrigger samples.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Estimand

For each same-event downstream pair `(a,b)`, the uncorrected timing residual is

`r_i = [t_a(CFD20) - t_b(CFD20)] - (x_a - x_b) tau`,

where `t(CFD20)` is the constant-fraction crossing at fraction `0.20`, and `tau=0.078` ns/cm is the nominal propagation term. A method predicts a correction `c_m(z_i)` from run-external features and waveforms; the scored residual is

`e_i,m = r_i - c_m(z_i)`.

The primary metric is `sigma68(e) = [Q_84(e) - Q_16(e)]/2`, with secondary bias, RMS, and tail fractions.

## Traditional Matched-Filter/Template Method

The traditional method estimates a median pulse template from training runs only after four-sample pedestal subtraction and amplitude normalization. For each held-out pair, the method computes a matched-filter correlation, a rise-tail balance, a leading-edge/time-walk axis, amplitude-ratio bins, and pair identity. It predicts the run-excluded median residual from the most specific populated calibration cell, backing off to coarser cells. This is deliberately stronger than a bare CFD correction because it combines constant-fraction timing with analytic pulse-shape and template time-walk terms while preserving run-held-out calibration.

## ML and Neural Comparators

The tabular ML panel uses the same pairwise covariates: ridge regression, histogram gradient-boosted trees, and MLP. The sequence panel uses baseline-subtracted normalized waveform pairs. The 1D-CNN is a compact convolutional regressor. The compact pair transformer uses one self-attention encoder layer over the 18 waveform samples. The new architecture is `rise_tail_gated_cnn_new`, which gates convolutional channels with rise, curvature, tail, and pretrigger covariates before residual regression. All methods exclude event identifiers and train only on runs different from the held-out run.

## Primary Results with Paired Run Bootstrap CIs

Bootstrap intervals resample held-out runs with replacement, preserving the method pairing within each sampled run.

| method                              |   n_pairs |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   tail_abs_gt_0p5_ns |   tail_abs_gt_0p5_ns_ci_low |   tail_abs_gt_0p5_ns_ci_high |     bias_ns |   bias_ns_ci_low |   bias_ns_ci_high |   delta_sigma68_vs_traditional_ns_ci_low |   delta_sigma68_vs_traditional_ns_ci_high |
|:------------------------------------|----------:|-------------:|--------------------:|---------------------:|---------------------:|----------------------------:|-----------------------------:|------------:|-----------------:|------------------:|-----------------------------------------:|------------------------------------------:|
| uncorrected_cfd20                   |     18098 |     2.94278  |            2.84413  |             3.04562  |             0.922643 |                    0.916647 |                     0.929333 | -3.41237    |       -3.56098   |        -3.30425   |                                 1.5295   |                                  1.75097  |
| traditional_matched_filter_template |     18098 |     1.30072  |            1.26639  |             1.33955  |             0.696873 |                    0.691508 |                     0.706383 | -0.397496   |       -0.48918   |        -0.315483  |                                 0        |                                  0        |
| ridge                               |     18098 |     2.48476  |            2.44196  |             2.53672  |             0.844237 |                    0.837867 |                     0.854791 | -0.0170447  |       -0.223276  |         0.194969  |                                 1.12031  |                                  1.25327  |
| gradient_boosted_trees              |     18098 |     0.702287 |            0.676679 |             0.732918 |             0.454691 |                    0.441316 |                     0.475274 | -0.013718   |       -0.0619272 |         0.0810691 |                                -0.628733 |                                 -0.562765 |
| mlp                                 |     18098 |     0.607168 |            0.525226 |             0.751871 |             0.394906 |                    0.337719 |                     0.478993 |  0.00769975 |       -0.0273891 |         0.0675356 |                                -0.783944 |                                 -0.556093 |
| one_dimensional_cnn                 |     18098 |     1.10537  |            1.07904  |             1.14605  |             0.647972 |                    0.639862 |                     0.65859  | -0.27501    |       -0.393757  |        -0.174145  |                                -0.222573 |                                 -0.159528 |
| compact_pair_transformer            |     18098 |     1.11637  |            1.08436  |             1.14498  |             0.64869  |                    0.640537 |                     0.6591   | -0.318215   |       -0.428287  |        -0.151181  |                                -0.21837  |                                 -0.141665 |
| rise_tail_gated_cnn_new             |     18098 |     1.14577  |            1.11938  |             1.17152  |             0.657089 |                    0.64867  |                     0.664666 | -0.277184   |       -0.361478  |        -0.183909  |                                -0.189767 |                                 -0.117772 |

## Per-Run Stability

| method                              |   run |   n_pairs |   sigma68_ns |   tail_abs_gt_0p5_ns |    bias_ns |
|:------------------------------------|------:|----------:|-------------:|---------------------:|-----------:|
| compact_pair_transformer            |    58 |       353 |     1.31953  |             0.648725 |  0.36206   |
| compact_pair_transformer            |    59 |      3753 |     1.05308  |             0.636291 | -0.530366  |
| compact_pair_transformer            |    60 |      3700 |     1.06655  |             0.638919 | -0.371972  |
| compact_pair_transformer            |    61 |      4245 |     1.10998  |             0.648763 | -0.454509  |
| compact_pair_transformer            |    62 |      3833 |     1.14388  |             0.667362 | -0.115895  |
| compact_pair_transformer            |    63 |      1816 |     1.12939  |             0.653084 | -0.125204  |
| compact_pair_transformer            |    65 |       398 |     1.12942  |             0.655779 |  0.203235  |
| gradient_boosted_trees              |    58 |       353 |     0.861282 |             0.541076 |  0.857807  |
| gradient_boosted_trees              |    59 |      3753 |     0.646136 |             0.428191 | -0.0691002 |
| gradient_boosted_trees              |    60 |      3700 |     0.697183 |             0.437568 |  0.0719484 |
| gradient_boosted_trees              |    61 |      4245 |     0.711891 |             0.456066 | -0.0627004 |
| gradient_boosted_trees              |    62 |      3833 |     0.737104 |             0.478215 | -0.0289102 |
| gradient_boosted_trees              |    63 |      1816 |     0.699072 |             0.465859 | -0.0766747 |
| gradient_boosted_trees              |    65 |       398 |     0.733718 |             0.494975 | -0.104856  |
| mlp                                 |    58 |       353 |     0.828955 |             0.507082 |  0.467465  |
| mlp                                 |    59 |      3753 |     0.470611 |             0.291767 |  0.0166068 |
| mlp                                 |    60 |      3700 |     0.597012 |             0.391622 |  0.0269132 |
| mlp                                 |    61 |      4245 |     0.509835 |             0.325559 | -0.022572  |
| mlp                                 |    62 |      3833 |     0.72584  |             0.48552  | -0.037056  |
| mlp                                 |    63 |      1816 |     0.854853 |             0.535793 |  0.0962094 |
| mlp                                 |    65 |       398 |     0.87359  |             0.522613 | -0.312643  |
| one_dimensional_cnn                 |    58 |       353 |     1.2871   |             0.691218 |  0.495126  |
| one_dimensional_cnn                 |    59 |      3753 |     1.0849   |             0.656541 | -0.233237  |
| one_dimensional_cnn                 |    60 |      3700 |     1.13659  |             0.656757 | -0.254342  |
| one_dimensional_cnn                 |    61 |      4245 |     1.1201   |             0.639105 | -0.487385  |
| one_dimensional_cnn                 |    62 |      3833 |     1.05126  |             0.632403 | -0.170818  |
| one_dimensional_cnn                 |    63 |      1816 |     1.12459  |             0.650881 | -0.332635  |
| one_dimensional_cnn                 |    65 |       398 |     1.24875  |             0.678392 | -0.0194725 |
| ridge                               |    58 |       353 |     3.05307  |             0.858357 |  1.35613   |
| ridge                               |    59 |      3753 |     2.51539  |             0.843059 | -0.0547327 |
| ridge                               |    60 |      3700 |     2.50951  |             0.838919 |  0.236933  |
| ridge                               |    61 |      4245 |     2.40224  |             0.83298  | -0.242949  |
| ridge                               |    62 |      3833 |     2.51325  |             0.849204 |  0.0749275 |
| ridge                               |    63 |      1816 |     2.49056  |             0.863987 | -0.473     |
| ridge                               |    65 |       398 |     2.47766  |             0.874372 |  0.363478  |
| rise_tail_gated_cnn_new             |    58 |       353 |     1.38073  |             0.668555 |  0.36018   |
| rise_tail_gated_cnn_new             |    59 |      3753 |     1.14468  |             0.663736 | -0.298985  |
| rise_tail_gated_cnn_new             |    60 |      3700 |     1.09458  |             0.642162 | -0.266248  |
| rise_tail_gated_cnn_new             |    61 |      4245 |     1.15024  |             0.65371  | -0.411035  |
| rise_tail_gated_cnn_new             |    62 |      3833 |     1.16126  |             0.66084  | -0.140395  |
| rise_tail_gated_cnn_new             |    63 |      1816 |     1.12663  |             0.65804  | -0.396162  |
| rise_tail_gated_cnn_new             |    65 |       398 |     1.27548  |             0.718593 | -0.0854191 |
| traditional_matched_filter_template |    58 |       353 |     1.34652  |             0.730878 |  0.117073  |
| traditional_matched_filter_template |    59 |      3753 |     1.24574  |             0.686917 | -0.406612  |
| traditional_matched_filter_template |    60 |      3700 |     1.26842  |             0.693514 | -0.518767  |
| traditional_matched_filter_template |    61 |      4245 |     1.2924   |             0.70318  | -0.300951  |
| traditional_matched_filter_template |    62 |      3833 |     1.26135  |             0.693191 | -0.356823  |
| traditional_matched_filter_template |    63 |      1816 |     1.32222  |             0.698238 | -0.58081   |
| traditional_matched_filter_template |    65 |       398 |     1.48111  |             0.753769 | -0.225564  |
| uncorrected_cfd20                   |    58 |       353 |     2.8642   |             0.923513 | -2.85184   |
| uncorrected_cfd20                   |    59 |      3753 |     2.95704  |             0.928324 | -3.47279   |
| uncorrected_cfd20                   |    60 |      3700 |     2.96349  |             0.917027 | -3.51308   |
| uncorrected_cfd20                   |    61 |      4245 |     2.7526   |             0.912603 | -3.26935   |
| uncorrected_cfd20                   |    62 |      3833 |     3.00859  |             0.926689 | -3.32187   |
| uncorrected_cfd20                   |    63 |      1816 |     3.18528  |             0.932269 | -3.71769   |
| uncorrected_cfd20                   |    65 |       398 |     2.58048  |             0.944724 | -3.40749   |

## Stratified Diagnostics

The requested energy and PID-proxy stratifications are operational proxies from waveform charge, since no external PID truth is available in this raw ROOT panel. Near-threshold energy is defined by the lower pair amplitude, and PID proxy by pair charge sum.

| stratum               | value           | method                              |   n_pairs |   sigma68_ns |   tail_abs_gt_0p5_ns |     bias_ns |
|:----------------------|:----------------|:------------------------------------|----------:|-------------:|---------------------:|------------:|
| pid_proxy             | high_charge     | compact_pair_transformer            |      9049 |     1.16284  |             0.662504 | -0.304281   |
| pid_proxy             | high_charge     | gradient_boosted_trees              |      9049 |     0.692939 |             0.447121 | -0.00598051 |
| pid_proxy             | high_charge     | mlp                                 |      9049 |     0.617923 |             0.397945 |  0.0152955  |
| pid_proxy             | high_charge     | one_dimensional_cnn                 |      9049 |     1.14298  |             0.658857 | -0.300114   |
| pid_proxy             | high_charge     | ridge                               |      9049 |     2.45995  |             0.846392 | -0.00662568 |
| pid_proxy             | high_charge     | rise_tail_gated_cnn_new             |      9049 |     1.18007  |             0.666814 | -0.272406   |
| pid_proxy             | high_charge     | traditional_matched_filter_template |      9049 |     1.26191  |             0.690353 | -0.277123   |
| pid_proxy             | high_charge     | uncorrected_cfd20                   |      9049 |     3.0131   |             0.938667 | -3.36938    |
| pid_proxy             | low_charge      | compact_pair_transformer            |      9049 |     1.0635   |             0.634877 | -0.332148   |
| pid_proxy             | low_charge      | gradient_boosted_trees              |      9049 |     0.712338 |             0.462261 | -0.0214554  |
| pid_proxy             | low_charge      | mlp                                 |      9049 |     0.596488 |             0.391867 |  0.00010401 |
| pid_proxy             | low_charge      | one_dimensional_cnn                 |      9049 |     1.06692  |             0.637087 | -0.249906   |
| pid_proxy             | low_charge      | ridge                               |      9049 |     2.50473  |             0.842082 | -0.0274637  |
| pid_proxy             | low_charge      | rise_tail_gated_cnn_new             |      9049 |     1.10863  |             0.647364 | -0.281961   |
| pid_proxy             | low_charge      | traditional_matched_filter_template |      9049 |     1.33341  |             0.703393 | -0.51787    |
| pid_proxy             | low_charge      | uncorrected_cfd20                   |      9049 |     2.92452  |             0.90662  | -3.45537    |
| near_threshold_energy | above_threshold | compact_pair_transformer            |     16111 |     1.11118  |             0.649742 | -0.299413   |
| near_threshold_energy | above_threshold | gradient_boosted_trees              |     16111 |     0.680382 |             0.444665 | -0.0223461  |
| near_threshold_energy | above_threshold | mlp                                 |     16111 |     0.593156 |             0.384396 |  0.00385955 |
| near_threshold_energy | above_threshold | one_dimensional_cnn                 |     16111 |     1.09554  |             0.648501 | -0.253372   |
| near_threshold_energy | above_threshold | ridge                               |     16111 |     2.3858   |             0.839426 | -0.0223927  |
| near_threshold_energy | above_threshold | rise_tail_gated_cnn_new             |     16111 |     1.13908  |             0.656446 | -0.249224   |
| near_threshold_energy | above_threshold | traditional_matched_filter_template |     16111 |     1.28439  |             0.693377 | -0.320677   |
| near_threshold_energy | above_threshold | uncorrected_cfd20                   |     16111 |     2.91216  |             0.933462 | -3.44724    |
| near_threshold_energy | near_threshold  | compact_pair_transformer            |      1987 |     1.19018  |             0.640161 | -0.470666   |
| near_threshold_energy | near_threshold  | gradient_boosted_trees              |      1987 |     0.920776 |             0.535984 |  0.0562403  |
| near_threshold_energy | near_threshold  | mlp                                 |      1987 |     0.761147 |             0.480121 |  0.0388369  |
| near_threshold_energy | near_threshold  | one_dimensional_cnn                 |      1987 |     1.19882  |             0.643684 | -0.450456   |
| near_threshold_energy | near_threshold  | ridge                               |      1987 |     3.65792  |             0.883241 |  0.0263181  |
| near_threshold_energy | near_threshold  | rise_tail_gated_cnn_new             |      1987 |     1.21671  |             0.662305 | -0.503884   |
| near_threshold_energy | near_threshold  | traditional_matched_filter_template |      1987 |     1.48489  |             0.725214 | -1.02036    |
| near_threshold_energy | near_threshold  | uncorrected_cfd20                   |      1987 |     3.0347   |             0.834927 | -3.12969    |

## Systematics

The main systematic is that pair residuals are not an absolute external clock; common-mode timing errors can cancel. Bootstrap intervals have seven independent held-out run units and should be read as run-transfer uncertainty rather than asymptotic precision. The PID and energy strata are waveform-charge proxies, not externally calibrated particle labels or MeV energies. Hyperparameters are intentionally compact for reproducibility on the worker. The matched-filter template and every ML model are trained inside each fold, so leakage through held-out waveforms is controlled, but remaining electronics-current or beam-condition metadata are not modeled explicitly.

## Caveats

The study ranks correction capacity for same-event downstream-pair timing, not absolute detector timing. It does not establish that a neural method is safe for publication without external clock validation. Rare pulse families are bounded by the raw ROOT selected-pulse support and by the modest sequence-model size. Conclusions for near-threshold and PID-proxy bins should be treated as diagnostic until an external PID or beamline truth join exists.

## Conclusion

The winner named in `result.json` is `mlp` by the registered rule: lowest held-out `sigma68_ns` among correction methods, with tail fraction and absolute bias as tie breakers. Exactly one novel follow-up ticket was appended as #2485: external clock/trigger-reference validation for this same method panel.
