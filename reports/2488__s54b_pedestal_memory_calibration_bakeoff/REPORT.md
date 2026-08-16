# S54b/#2488: Pedestal-Memory Calibration Bakeoff

## Abstract

Ticket `#2488` asks how pedestal drift and baseline memory propagate into pulse
timing, charge/energy calibration, pile-up tagging, saturation flags, and PID
operating points under run-held-out transfer.  The raw ROOT reproduction gate
recomputes **640,737** selected B-stave
pulses, exactly matching the registered anchor.  The winner recorded in
`result.json` is **`gradient_boosted_trees`**, selected by an auxiliary calibration score that
combines duplicate-readout energy resolution, energy scale bias, PID AUC,
pile-up AUC, and saturation AUC.  Its energy sigma68 is
`0.1222` with 95% run-bootstrap CI
[`0.1115`, `0.1325`].

## Ticket Claim Provenance

The required command `tn-ticket claim testbeam-laptop-1 --project testbeam` was
run exactly once.  It returned the known malformed null pseudo-ticket output
instead of a real issue, while direct queue inspection still showed open
testbeam tickets and no `worker:testbeam-laptop-1` claim.  Without rerunning the
helper, issue `#2488` was manually moved from `factory:open` to
`factory:claimed` and labeled `worker:testbeam-laptop-1`; the raw issue text is
saved in `claimed_ticket.txt`.

## Raw ROOT Reproduction

The input is `/home/billy/ccb-data/data/extracted/root/root/hrdb_run_*.root`.
For each event, `h101/HRDv` is reshaped to `(channel, sample)` with 18 samples
per channel.  For B-stave channel `c`,

`b_ec = median_{t in {0,1,2,3}} x_ect`,

`A_ec = max_t (x_ect - b_ec)`,

and a selected pulse satisfies `A_ec > 1000 ADC`.
The reproduction is performed before row sampling or model fitting.

| group                 |   events_total |   selected_pulses |   expected_selected_pulses |   delta | pass   |
|:----------------------|---------------:|------------------:|---------------------------:|--------:|:-------|
| sample_i_calib        |         409815 |            248745 |                     248745 |       0 | True   |
| sample_i_analysis     |         388879 |            252266 |                     252266 |       0 | True   |
| sample_ii_calib       |          35943 |             14630 |                      14630 |       0 | True   |
| sample_ii_analysis    |         262091 |            125096 |                     125096 |       0 | True   |
| all_registered_groups |        1096728 |            640737 |                     640737 |       0 | True   |

## Estimands

Timing uses the run/stave-centered CFD20 residual

`y_i = 10 ns [t_0.20,i - median(t_0.20 | run_i, stave_i)]`.

Energy uses the hidden duplicate-readout log-response closure

`r_i = log(1 + A'_i) - log(1 + A_i)`,

where `A_i` is the analysed even B-stave pulse amplitude and `A'_i` is the
paired odd-channel amplitude, withheld from all auxiliary features.  The
reported energy scale error is `hat r_i - r_i`, approximately a fractional
closure error for small deviations.  PID is represented by the high
duplicate-ratio sideband, pile-up by late secondary-pulse evidence, and
saturation by high-amplitude or flat-top occupancy.  These are raw-waveform
sideband labels, not external particle-truth labels.

All models are trained on runs outside `[42, 50, 57, 58, 60, 62, 64, 65]` and scored only
on those held-out runs.  Confidence intervals are percentile 95% intervals from
run-block bootstrap resamples.

## Methods

The traditional comparator, `traditional_state_space_gls`, is a rolling
pedestal and state-space baseline model: it estimates stave-local duplicate
closure from training runs, adds a linear pedestal-state correction, and uses
template residual cuts for PID, pile-up, and saturation scores.  The ML/NN panel
contains ridge, gradient-boosted trees, MLP, 1D-CNN, a masked waveform
transformer, and the new `pedestal_residual_fusion_new` gated CNN.  No method is
given run number, event number, or duplicate amplitude as a feature.

## Timing Benchmark

| method                            |    n |   bias_ns |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   tail_fraction_abs_gt_5ns |
|:----------------------------------|-----:|----------:|-------------:|--------------------:|---------------------:|---------------------------:|
| traditional_cfd_template_timewalk | 3669 |    0.5032 |        1.006 |              0.5867 |                1.196 |                     0      |
| gradient_boosted_trees            | 3669 |   -0.4765 |        3.749 |              3.166  |                4.103 |                     0.1834 |
| mlp                               | 3669 |   -0.4917 |        4.113 |              3.666  |                4.708 |                     0.2398 |
| ridge                             | 3669 |   -0.2584 |        4.247 |              3.702  |                5.077 |                     0.2464 |
| edge_attention_cnn_new            | 3669 |   -1.016  |        8.052 |              7.463  |                8.848 |                     0.5127 |
| 1d_cnn                            | 3669 |   -0.3237 |        9.974 |              8.738  |               11.81  |                     0.5846 |
| waveform_transformer              | 3669 |    1.525  |       10.93  |              9.759  |               12.07  |                     0.6623 |

## Calibration and PID Benchmark

Lower auxiliary score is better.  PID, pile-up, and saturation metrics are AUC
or average precision on held-out runs; fixed-purity efficiency is recall at at
least 90% purity.

| method                       |    n |   auxiliary_score |   energy_scale_bias |   energy_sigma68 |   energy_sigma68_ci_low |   energy_sigma68_ci_high |   pid_auc |   pid_ap |   pid_fixed_purity_eff |   pileup_auc |   saturation_auc |
|:-----------------------------|-----:|------------------:|--------------------:|-----------------:|------------------------:|-------------------------:|----------:|---------:|-----------------------:|-------------:|-----------------:|
| gradient_boosted_trees       | 3669 |            0.1236 |           -0.006608 |           0.1222 |                  0.1115 |                   0.1325 |    0.9987 |   0.9978 |              0.9971    |       1      |           1      |
| mlp                          | 3669 |            0.543  |           -0.03278  |           0.535  |                  0.5095 |                   0.5659 |    0.9824 |   0.9729 |              0.918     |       1      |           0.9999 |
| ridge                        | 3669 |            0.6345 |           -0.05743  |           0.6203 |                  0.5966 |                   0.6405 |    0.9671 |   0.952  |              0.8662    |       0.9996 |           0.999  |
| pedestal_residual_fusion_new | 3669 |            0.8958 |           -0.1101   |           0.8481 |                  0.8096 |                   0.8848 |    0.9445 |   0.9314 |              0.8359    |       0.9028 |           0.6161 |
| 1d_cnn                       | 3669 |            1.003  |           -0.01672  |           0.9743 |                  0.9146 |                   1.043  |    0.9426 |   0.9319 |              0.8525    |       0.9093 |           0.6232 |
| traditional_state_space_gls  | 3669 |            1.866  |            0.4087   |           1.664  |                  1.448  |                   1.878  |    0.1432 |   0.178  |              0.0009766 |       0.1409 |           1      |
| waveform_transformer         | 3669 |            2.136  |            0.3419   |           2.036  |                  1.577  |                   2.278  |    0.8739 |   0.8537 |              0.6807    |       0.9264 |           0.5682 |

The traditional energy sigma68 is `1.664`; the winner
energy sigma68 is `0.1222`.  The method-minus-traditional
timing deltas are:

| method                 | reference_method                  |   delta_sigma68_ns |   delta_sigma68_ns_ci_low |   delta_sigma68_ns_ci_high |
|:-----------------------|:----------------------------------|-------------------:|--------------------------:|---------------------------:|
| gradient_boosted_trees | traditional_cfd_template_timewalk |              2.743 |                     2.153 |                      3.162 |
| mlp                    | traditional_cfd_template_timewalk |              3.108 |                     2.605 |                      3.805 |
| ridge                  | traditional_cfd_template_timewalk |              3.241 |                     2.661 |                      4.201 |
| edge_attention_cnn_new | traditional_cfd_template_timewalk |              7.047 |                     6.381 |                      7.877 |
| 1d_cnn                 | traditional_cfd_template_timewalk |              8.969 |                     7.715 |                     10.78  |
| waveform_transformer   | traditional_cfd_template_timewalk |              9.922 |                     8.72  |                     11.1   |

## Run and Stratum Stability

| method                       |   run |   n |   energy_scale_bias |   energy_sigma68 |   pid_auc |   pileup_auc |   saturation_auc |
|:-----------------------------|------:|----:|--------------------:|-----------------:|----------:|-------------:|-----------------:|
| 1d_cnn                       |    42 | 460 |            0.1276   |           0.9843 |   0.9267  |      0.9363  |           0.6666 |
| 1d_cnn                       |    50 | 460 |            0.2428   |           1.099  |   0.8936  |      0.9721  |           0.7549 |
| 1d_cnn                       |    57 | 460 |            0.05116  |           1.082  |   0.92    |      0.9426  |           0.6439 |
| 1d_cnn                       |    58 | 459 |           -0.01818  |           0.9674 |   0.916   |      0.9072  |           0.5924 |
| 1d_cnn                       |    60 | 460 |           -0.1836   |           0.8971 |   0.9777  |      0.8523  |           0.5411 |
| 1d_cnn                       |    62 | 460 |           -0.1691   |           0.8819 |   0.9781  |      0.856   |           0.5964 |
| 1d_cnn                       |    64 | 460 |           -0.02918  |           0.8499 |   0.9813  |      0.8826  |           0.5798 |
| 1d_cnn                       |    65 | 450 |           -0.1148   |           0.8779 |   0.9189  |      0.8612  |           0.5534 |
| gradient_boosted_trees       |    42 | 460 |           -0.001851 |           0.1142 |   0.9943  |      1       |           1      |
| gradient_boosted_trees       |    50 | 460 |           -0.001393 |           0.1252 |   0.9993  |      1       |           1      |
| gradient_boosted_trees       |    57 | 460 |           -0.002405 |           0.1144 |   0.999   |      1       |           1      |
| gradient_boosted_trees       |    58 | 459 |           -0.01376  |           0.1332 |   0.999   |      1       |           1      |
| gradient_boosted_trees       |    60 | 460 |           -0.01333  |           0.1007 |   0.9998  |      1       |           1      |
| gradient_boosted_trees       |    62 | 460 |           -0.01154  |           0.1136 |   0.9998  |      1       |           1      |
| gradient_boosted_trees       |    64 | 460 |           -0.001536 |           0.1179 |   0.9997  |      1       |           1      |
| gradient_boosted_trees       |    65 | 450 |           -0.005008 |           0.1408 |   0.9982  |      1       |           1      |
| mlp                          |    42 | 460 |           -0.008581 |           0.4688 |   0.9741  |      1       |           0.9999 |
| mlp                          |    50 | 460 |           -0.02017  |           0.5683 |   0.9704  |      1       |           0.9999 |
| mlp                          |    57 | 460 |           -0.0484   |           0.4818 |   0.979   |      1       |           0.9993 |
| mlp                          |    58 | 459 |           -0.04418  |           0.5931 |   0.9574  |      1       |           1      |
| mlp                          |    60 | 460 |           -0.0375   |           0.4987 |   0.9923  |      1       |           0.9999 |
| mlp                          |    62 | 460 |           -0.03891  |           0.5535 |   0.9948  |      0.9999  |           0.9999 |
| mlp                          |    64 | 460 |           -0.03067  |           0.5665 |   0.9969  |      1       |           0.9999 |
| mlp                          |    65 | 450 |           -0.0338   |           0.5511 |   0.9836  |      1       |           0.9999 |
| pedestal_residual_fusion_new |    42 | 460 |           -0.03065  |           0.8629 |   0.9279  |      0.9311  |           0.6606 |
| pedestal_residual_fusion_new |    50 | 460 |            0.026    |           0.9453 |   0.8974  |      0.9657  |           0.7429 |
| pedestal_residual_fusion_new |    57 | 460 |           -0.0772   |           0.8877 |   0.9193  |      0.9381  |           0.6402 |
| pedestal_residual_fusion_new |    58 | 459 |           -0.08997  |           0.862  |   0.9154  |      0.9005  |           0.597  |
| pedestal_residual_fusion_new |    60 | 460 |           -0.1807   |           0.8168 |   0.9771  |      0.8436  |           0.5129 |
| pedestal_residual_fusion_new |    62 | 460 |           -0.2544   |           0.7909 |   0.9791  |      0.8466  |           0.5832 |
| pedestal_residual_fusion_new |    64 | 460 |           -0.1087   |           0.7733 |   0.981   |      0.8736  |           0.5694 |
| pedestal_residual_fusion_new |    65 | 450 |           -0.1833   |           0.8008 |   0.9286  |      0.852   |           0.5421 |
| ridge                        |    42 | 460 |           -0.02523  |           0.5957 |   0.9556  |      0.9968  |           0.9975 |
| ridge                        |    50 | 460 |           -0.001105 |           0.6418 |   0.9511  |      1       |           0.9986 |
| ridge                        |    57 | 460 |           -0.03748  |           0.5968 |   0.9512  |      1       |           0.999  |
| ridge                        |    58 | 459 |           -0.05743  |           0.6461 |   0.9322  |      1       |           0.9993 |
| ridge                        |    60 | 460 |           -0.07471  |           0.5624 |   0.9811  |      1       |           0.9997 |
| ridge                        |    62 | 460 |           -0.1297   |           0.6442 |   0.9896  |      1       |           0.9998 |
| ridge                        |    64 | 460 |           -0.08883  |           0.6499 |   0.9909  |      1       |           0.9997 |
| ridge                        |    65 | 450 |           -0.05666  |           0.6147 |   0.9624  |      1       |           0.9981 |
| traditional_state_space_gls  |    42 | 460 |            0.1916   |           1.652  |   0.1701  |      0.1204  |           1      |
| traditional_state_space_gls  |    50 | 460 |            0.4899   |           1.286  |   0.2396  |      0.07289 |           1      |
| traditional_state_space_gls  |    57 | 460 |            0.2332   |           1.632  |   0.162   |      0.1445  |           1      |
| traditional_state_space_gls  |    58 | 459 |            0.5695   |           1.29   |   0.1806  |      0.1079  |           1      |
| traditional_state_space_gls  |    60 | 460 |            0.4641   |           2.097  |   0.07916 |      0.2063  |           1      |
| traditional_state_space_gls  |    62 | 460 |            0.3309   |           1.936  |   0.09719 |      0.2328  |           1      |
| traditional_state_space_gls  |    64 | 460 |            0.523    |           1.881  |   0.108   |      0.1347  |           1      |
| traditional_state_space_gls  |    65 | 450 |            0.3683   |           1.449  |   0.1593  |      0.1602  |           1      |
| waveform_transformer         |    42 | 460 |            0.0348   |           1.868  |   0.8537  |      0.9437  |           0.5439 |
| waveform_transformer         |    50 | 460 |            0.4508   |           1.271  |   0.8006  |      0.9748  |           0.598  |
| waveform_transformer         |    57 | 460 |            0.07587  |           1.912  |   0.8525  |      0.9556  |           0.5835 |
| waveform_transformer         |    58 | 459 |            0.4712   |           1.518  |   0.8372  |      0.9349  |           0.5463 |
| waveform_transformer         |    60 | 460 |            0.4134   |           2.488  |   0.9256  |      0.8732  |           0.5666 |
| waveform_transformer         |    62 | 460 |            0.2793   |           2.457  |   0.9288  |      0.8811  |           0.5972 |
| waveform_transformer         |    64 | 460 |            0.548    |           2.187  |   0.913   |      0.9119  |           0.5995 |
| waveform_transformer         |    65 | 450 |            0.3254   |           1.796  |   0.8505  |      0.8979  |           0.5881 |

Pedestal, PID-sideband, pile-up, and saturation slices for duplicate-readout
energy closure:

| stratum               | level           | method                       |    n |   energy_scale_bias |   energy_sigma68 |
|:----------------------|:----------------|:-----------------------------|-----:|--------------------:|-----------------:|
| pedestal_drift_bin    | high            | 1d_cnn                       | 1170 |          -0.2154    |          0.9954  |
| pedestal_drift_bin    | low             | 1d_cnn                       | 1198 |           0.06785   |          1.004   |
| pedestal_drift_bin    | mid             | 1d_cnn                       | 1301 |           0.1113    |          0.8979  |
| pid_sideband          | central         | 1d_cnn                       | 2501 |          -0.1786    |          0.8501  |
| pid_sideband          | high_duplicate  | 1d_cnn                       |  582 |          -0.3631    |          0.9631  |
| pid_sideband          | low_duplicate   | 1d_cnn                       |  586 |           0.9541    |          0.7942  |
| pileup_separation_bin | close           | 1d_cnn                       | 1103 |           0.3276    |          0.8993  |
| pileup_separation_bin | late            | 1d_cnn                       |    3 |           0.02167   |          0.8054  |
| pileup_separation_bin | mid             | 1d_cnn                       |  786 |          -0.3766    |          0.7978  |
| pileup_separation_bin | none            | 1d_cnn                       | 1777 |          -0.06039   |          1.03    |
| saturation_onset_bin  | linear          | 1d_cnn                       | 2641 |          -0.02331   |          0.9641  |
| saturation_onset_bin  | near_saturation | 1d_cnn                       | 1028 |          -0.004288  |          1.004   |
| pedestal_drift_bin    | high            | gradient_boosted_trees       | 1170 |          -0.005926  |          0.09606 |
| pedestal_drift_bin    | low             | gradient_boosted_trees       | 1198 |          -0.006524  |          0.1379  |
| pedestal_drift_bin    | mid             | gradient_boosted_trees       | 1301 |          -0.007576  |          0.1332  |
| pid_sideband          | central         | gradient_boosted_trees       | 2501 |          -0.02162   |          0.1266  |
| pid_sideband          | high_duplicate  | gradient_boosted_trees       |  582 |          -0.00176   |          0.05052 |
| pid_sideband          | low_duplicate   | gradient_boosted_trees       |  586 |           0.07778   |          0.214   |
| pileup_separation_bin | close           | gradient_boosted_trees       | 1103 |          -0.004373  |          0.09827 |
| pileup_separation_bin | late            | gradient_boosted_trees       |    3 |           0.06659   |          0.1918  |
| pileup_separation_bin | mid             | gradient_boosted_trees       |  786 |          -0.009715  |          0.065   |
| pileup_separation_bin | none            | gradient_boosted_trees       | 1777 |          -0.005116  |          0.1762  |
| saturation_onset_bin  | linear          | gradient_boosted_trees       | 2641 |          -0.008641  |          0.1273  |
| saturation_onset_bin  | near_saturation | gradient_boosted_trees       | 1028 |          -0.003194  |          0.1089  |
| pedestal_drift_bin    | high            | mlp                          | 1170 |          -0.01856   |          0.3862  |
| pedestal_drift_bin    | low             | mlp                          | 1198 |          -0.07159   |          0.5847  |
| pedestal_drift_bin    | mid             | mlp                          | 1301 |          -0.05088   |          0.5816  |
| pid_sideband          | central         | mlp                          | 2501 |          -0.2091    |          0.5105  |
| pid_sideband          | high_duplicate  | mlp                          |  582 |          -0.0002308 |          0.06042 |
| pid_sideband          | low_duplicate   | mlp                          |  586 |           0.6965    |          0.4716  |
| pileup_separation_bin | close           | mlp                          | 1103 |          -0.02212   |          0.534   |
| pileup_separation_bin | late            | mlp                          |    3 |          -0.6334    |          1.394   |
| pileup_separation_bin | mid             | mlp                          |  786 |          -0.01737   |          0.1771  |
| pileup_separation_bin | none            | mlp                          | 1777 |          -0.07297   |          0.6494  |
| saturation_onset_bin  | linear          | mlp                          | 2641 |          -0.03035   |          0.5388  |
| saturation_onset_bin  | near_saturation | mlp                          | 1028 |          -0.04114   |          0.533   |
| pedestal_drift_bin    | high            | pedestal_residual_fusion_new | 1170 |          -0.3445    |          0.832   |
| pedestal_drift_bin    | low             | pedestal_residual_fusion_new | 1198 |           0.009104  |          0.8518  |
| pedestal_drift_bin    | mid             | pedestal_residual_fusion_new | 1301 |           0.03805   |          0.8236  |
| pid_sideband          | central         | pedestal_residual_fusion_new | 2501 |          -0.2336    |          0.6962  |
| pid_sideband          | high_duplicate  | pedestal_residual_fusion_new |  582 |          -0.4664    |          0.7616  |
| pid_sideband          | low_duplicate   | pedestal_residual_fusion_new |  586 |           0.9969    |          0.5772  |
| pileup_separation_bin | close           | pedestal_residual_fusion_new | 1103 |           0.2285    |          0.8002  |
| pileup_separation_bin | late            | pedestal_residual_fusion_new |    3 |          -0.2302    |          0.6864  |
| pileup_separation_bin | mid             | pedestal_residual_fusion_new |  786 |          -0.3567    |          0.7085  |
| pileup_separation_bin | none            | pedestal_residual_fusion_new | 1777 |          -0.1565    |          0.8362  |
| saturation_onset_bin  | linear          | pedestal_residual_fusion_new | 2641 |          -0.1335    |          0.8274  |
| saturation_onset_bin  | near_saturation | pedestal_residual_fusion_new | 1028 |          -0.07325   |          0.8858  |
| pedestal_drift_bin    | high            | ridge                        | 1170 |          -0.1       |          0.5683  |
| pedestal_drift_bin    | low             | ridge                        | 1198 |          -0.03592   |          0.6443  |
| pedestal_drift_bin    | mid             | ridge                        | 1301 |          -0.004983  |          0.6481  |
| pid_sideband          | central         | ridge                        | 2501 |          -0.201     |          0.545   |
| pid_sideband          | high_duplicate  | ridge                        |  582 |          -0.07657   |          0.3234  |
| pid_sideband          | low_duplicate   | ridge                        |  586 |           0.775     |          0.5011  |
| pileup_separation_bin | close           | ridge                        | 1103 |          -0.0263    |          0.6221  |
| pileup_separation_bin | late            | ridge                        |    3 |          -0.101     |          0.3936  |
| pileup_separation_bin | mid             | ridge                        |  786 |          -0.06514   |          0.3194  |
| pileup_separation_bin | none            | ridge                        | 1777 |          -0.07142   |          0.719   |
| saturation_onset_bin  | linear          | ridge                        | 2641 |          -0.04781   |          0.6199  |
| saturation_onset_bin  | near_saturation | ridge                        | 1028 |          -0.08794   |          0.6146  |
| pedestal_drift_bin    | high            | traditional_state_space_gls  | 1170 |          -0.8239    |          2.284   |
| pedestal_drift_bin    | low             | traditional_state_space_gls  | 1198 |           0.5961    |          0.9722  |
| pedestal_drift_bin    | mid             | traditional_state_space_gls  | 1301 |           0.6805    |          1.09    |
| pid_sideband          | central         | traditional_state_space_gls  | 2501 |           0.3659    |          0.9062  |
| pid_sideband          | high_duplicate  | traditional_state_space_gls  |  582 |          -3.167     |          1.207   |
| pid_sideband          | low_duplicate   | traditional_state_space_gls  |  586 |           1.804     |          0.4284  |
| pileup_separation_bin | close           | traditional_state_space_gls  | 1103 |           0.7681    |          1.327   |
| pileup_separation_bin | late            | traditional_state_space_gls  |    3 |          -0.1683    |          1.371   |
| pileup_separation_bin | mid             | traditional_state_space_gls  |  786 |          -1.813     |          2.307   |
| pileup_separation_bin | none            | traditional_state_space_gls  | 1777 |           0.4617    |          0.9767  |
| saturation_onset_bin  | linear          | traditional_state_space_gls  | 2641 |           0.3726    |          1.674   |
| saturation_onset_bin  | near_saturation | traditional_state_space_gls  | 1028 |           0.4907    |          1.609   |
| pedestal_drift_bin    | high            | waveform_transformer         | 1170 |          -2.081     |          2.633   |
| pedestal_drift_bin    | low             | waveform_transformer         | 1198 |           0.5944    |          1.012   |
| pedestal_drift_bin    | mid             | waveform_transformer         | 1301 |           0.6799    |          1.12    |
| pid_sideband          | central         | waveform_transformer         | 2501 |           0.3401    |          0.9585  |
| pid_sideband          | high_duplicate  | waveform_transformer         |  582 |          -4.075     |          0.6272  |
| pid_sideband          | low_duplicate   | waveform_transformer         |  586 |           1.795     |          0.3933  |
| pileup_separation_bin | close           | waveform_transformer         | 1103 |           0.8458    |          1.262   |
| pileup_separation_bin | late            | waveform_transformer         |    3 |          -0.1045    |          1.29    |
| pileup_separation_bin | mid             | waveform_transformer         |  786 |          -2.224     |          2.624   |
| pileup_separation_bin | none            | waveform_transformer         | 1777 |           0.2835    |          1.111   |
| saturation_onset_bin  | linear          | waveform_transformer         | 2641 |           0.2771    |          2.176   |
| saturation_onset_bin  | near_saturation | waveform_transformer         | 1028 |           0.4593    |          1.564   |

## Systematics and Caveats

The ROOT files do not carry independent particle species, calorimeter truth, or
electronics saturation truth for these B-stave pulses.  PID, pile-up, saturation,
and energy are therefore duplicate-readout and waveform-sideband closure
estimands.  They are valuable leakage-resistant stress tests because the
duplicate amplitude is hidden from the fitted feature set, but they should not
be read as external truth.  The bootstrap samples runs rather than events, so
the intervals emphasize run-transfer uncertainty.  The new gated CNN improves
some waveform-sideband scores, but any production adoption must still pass a
future externally labelled PID/energy validation.

## Conclusion

The raw count is exactly reproducible from ROOT and the strongest overall
sideband calibration method is `gradient_boosted_trees`.  This supports the hypothesis that
pedestal-memory information is present in local waveform shape and baseline
state, but the conclusion remains a closure result rather than an absolute PID
or calorimetric calibration.

No new follow-up ticket was appended.

Runtime was `109.2 s` on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35` with Python
`3.13.12`.
