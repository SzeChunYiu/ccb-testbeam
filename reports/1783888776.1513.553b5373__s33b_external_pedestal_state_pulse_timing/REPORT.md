# S33b — External Pedestal-State Validation for Pulse-Shape Timing
- Study ID:      S33b
- Title:         external pedestal-state validation for pulse-shape timing
- Date:          2026-07-14
- Status:        DONE
- Authors:       CCB analysis fleet
- Dependencies:  S00, S16 forced/random audits, S32a, S33a
- Data anchor:   640,737 selected B-pulses

**ML loses: traditional registered score 1.134 is best; direct forced/random truth remains absent.**

## Reproduction Gate

Command: `/home/billy/anaconda3/bin/python scripts/s33b_1783888776_1513_553b5373_external_pedestal_state_pulse_timing.py --config configs/s33b_1783888776_1513_553b5373_external_pedestal_state_pulse_timing.json`

Expected: `640,737` selected B-stave pulses with `A > 1000 ADC`; Actual: `640,737`; Delta: `0`.

Seed: `random_state=20330713`.  Baseline is the median of samples `[0, 1, 2, 3]`; selected physical B staves are `['B2', 'B4', 'B6', 'B8']`.

| group                 |   events_total |   selected_pulses |   expected_selected_pulses |   delta | pass   |
|:----------------------|---------------:|------------------:|---------------------------:|--------:|:-------|
| sample_i_calib        |         409815 |            248745 |                     248745 |       0 | True   |
| sample_i_analysis     |         388879 |            252266 |                     252266 |       0 | True   |
| sample_ii_calib       |          35943 |             14630 |                      14630 |       0 | True   |
| sample_ii_analysis    |         262091 |            125096 |                     125096 |       0 | True   |
| all_registered_groups |        1096728 |            640737 |                     640737 |       0 | True   |

## Key Metrics

The registered score is

`S_m = sigma68_timing,m + 2 mean_e Brier_e,m + mean_e (1 - AUC_e,m)`,

where `e` runs over the independent pedestal/electronics-state endpoints.  Lower is better.  The winner is `traditional_cfd_template_pedestal`.

| method                            |   registered_score |   timing_sigma68_ns |   mean_state_auc |   mean_state_brier |   mean_state_log_loss |
|:----------------------------------|-------------------:|--------------------:|-----------------:|-------------------:|----------------------:|
| traditional_cfd_template_pedestal |              1.134 |              0.4223 |           0.7766 |             0.2439 |                 2.186 |
| mlp                               |              1.147 |              0.4302 |           0.7344 |             0.2258 |                 3.12  |
| gradient_boosted_trees            |              1.16  |              0.4215 |           0.7769 |             0.2576 |                 2.83  |
| ridge                             |              1.167 |              0.4643 |           0.7808 |             0.2416 |                 2.135 |
| gated_attention_waveform_new      |              3.633 |              2.658  |           0.6682 |             0.3216 |                 3.125 |
| 1d_cnn                            |              3.823 |              2.792  |           0.6348 |             0.333  |                 2.93  |

## Physics Motivation

S33a showed that pedestal-memory features can correlate with timing residuals, but that does not prove the endpoint is an electronics-state diagnostic.  S33b asks the sharper question: when the timing benchmark is compared with labels that are independent of the CFD residual, do waveform models actually recover pedestal/electronics state, or only reuse pulse-shape proxies?

## Methodology

Data selection starts from raw B-stack ROOT `h101/HRDv` waveforms.  For channel `c`,

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

`A_c = max_t (x_c(t) - b_c)`,

and a pulse is selected when `A_c > 1000 ADC`.  The raw gate is evaluated before the held-out prediction table is read.

The direct external-truth audit scanned every visible `hrda_run_*.root` and `hrdb_run_*.root` file for forced/random/pedestal filename tokens and for populated `TRIGGER != 1` rows.

|   root_files_audited |   files_with_trigger_branch |   filename_token_hits |   non_beam_trigger_entries |
|---------------------:|----------------------------:|----------------------:|---------------------------:|
|                  110 |                         110 |                     0 |                          0 |

No direct forced/random pedestal sample is visible in the mounted mirror.  Therefore the benchmark below uses independent raw sideband endpoints, not direct DAQ-provenanced electronics truth:

- `pedestal_state`: high/low pretrigger pedestal state.
- `electronics_epoch`: coarse run/electronics epoch label.
- `forced_random_surrogate`: no-beam-style surrogate label derived independently of the timing residual.
- `late_tail_memory`: late-tail/pedestal-memory state label.
- `saturation_clipping`: saturation/flat-top state label.

The method panel is:

| method                            | family           | description                                                                                                |
|:----------------------------------|:-----------------|:-----------------------------------------------------------------------------------------------------------|
| traditional_cfd_template_pedestal | traditional      | CFD/template pedestal comparator using leading-edge residuals plus raw pretrigger pedestal-state summaries |
| ridge                             | linear ML        | standardized ridge model on the same frozen waveform and pedestal-state features                           |
| gradient_boosted_trees            | tree ML          | histogram gradient-boosted trees over engineered waveform, pretrigger, tail, and saturation summaries      |
| mlp                               | neural tabular   | multi-layer perceptron using the ticket-frozen tabular feature representation                              |
| 1d_cnn                            | neural waveform  | compact convolutional network over normalized 18-sample waveforms                                          |
| gated_attention_waveform_new      | new architecture | gated attention waveform model that can emphasize pretrigger, leading-edge, and late-tail regions          |

Splits are by complete held-out run: `[42, 50, 57, 58, 60, 62, 64, 65]`.  Confidence intervals are percentile intervals from `1000` run-block bootstrap resamples.

## Results

Timing endpoint, evaluated as `error = y_true - score` in ns:

| method                            |    n |   bias_ns |   bias_ns_ci_low |   bias_ns_ci_high |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   rms_ns |   tail_fraction_abs_gt_5ns |
|:----------------------------------|-----:|----------:|-----------------:|------------------:|-------------:|--------------------:|---------------------:|---------:|---------------------------:|
| gradient_boosted_trees            | 3816 |   0.01453 |          -0.1959 |           0.1166  |       0.4215 |              0.3709 |               0.4684 |   0.4805 |                  0         |
| traditional_cfd_template_pedestal | 3816 |  -0.08245 |          -0.2126 |           0.02477 |       0.4223 |              0.3761 |               0.5049 |   0.528  |                  0         |
| mlp                               | 3816 |   0.02544 |          -0.2191 |           0.1209  |       0.4302 |              0.3843 |               0.4714 |   0.5102 |                  0.0002621 |
| ridge                             | 3816 |   0.02911 |          -0.2221 |           0.1528  |       0.4643 |              0.3891 |               0.488  |   0.4997 |                  0.0002621 |
| gated_attention_waveform_new      | 3816 |  -0.4046  |          -0.4467 |          -0.3508  |       2.658  |              1.656  |               3.365  |   3.28   |                  0.1156    |
| 1d_cnn                            | 3816 |  -0.2526  |          -0.3041 |          -0.1964  |       2.792  |              1.732  |               3.412  |   3.35   |                  0.1255    |

External pedestal/electronics-state endpoints:

| endpoint                | method                            |    n |    auc |   auc_ci_low |   auc_ci_high |    brier |   brier_ci_low |   brier_ci_high |   log_loss |
|:------------------------|:----------------------------------|-----:|-------:|-------------:|--------------:|---------:|---------------:|----------------:|-----------:|
| electronics_epoch       | ridge                             | 3816 | 0.6844 |       0.6165 |        0.7412 | 0.4005   |      0.1979    |        0.5687   |    3.434   |
| electronics_epoch       | traditional_cfd_template_pedestal | 3816 | 0.6793 |       0.6131 |        0.7389 | 0.4041   |      0.1944    |        0.581    |    3.433   |
| electronics_epoch       | 1d_cnn                            | 3816 | 0.5375 |       0.5096 |        0.5629 | 0.562    |      0.227     |        0.7951   |    4.361   |
| electronics_epoch       | gradient_boosted_trees            | 3816 | 0.5333 |       0.5172 |        0.5482 | 0.6021   |      0.2411    |        0.8581   |    8.061   |
| electronics_epoch       | mlp                               | 3816 | 0.5147 |       0.5049 |        0.5247 | 0.6038   |      0.2441    |        0.9571   |    8.341   |
| electronics_epoch       | gated_attention_waveform_new      | 3816 | 0.5107 |       0.4859 |        0.5353 | 0.607    |      0.2438    |        0.8532   |    6.929   |
| forced_random_surrogate | mlp                               | 3816 | 0.5525 |       0.5347 |        0.5705 | 0.4198   |      0.3853    |        0.4577   |    5.8     |
| forced_random_surrogate | gradient_boosted_trees            | 3816 | 0.5499 |       0.5318 |        0.5702 | 0.6182   |      0.3201    |        0.8236   |    5.204   |
| forced_random_surrogate | ridge                             | 3816 | 0.5515 |       0.508  |        0.5941 | 0.6964   |      0.4598    |        0.9316   |    6.027   |
| forced_random_surrogate | traditional_cfd_template_pedestal | 3816 | 0.5315 |       0.507  |        0.5555 | 0.7052   |      0.467     |        0.944    |    6.292   |
| forced_random_surrogate | gated_attention_waveform_new      | 3816 | 0.4943 |       0.4823 |        0.5038 | 0.7264   |      0.3639    |        0.971    |    6.246   |
| forced_random_surrogate | 1d_cnn                            | 3816 | 0.4952 |       0.4771 |        0.515  | 0.7357   |      0.368     |        0.9836   |    6.783   |
| late_tail_memory        | gradient_boosted_trees            | 3816 | 0.9967 |       0.9933 |        1      | 0.001132 |      1.039e-06 |        0.00261  |    0.01471 |
| late_tail_memory        | mlp                               | 3816 | 0.9884 |       0.9822 |        0.9958 | 0.004979 |      0.002353  |        0.007855 |    0.06879 |
| late_tail_memory        | ridge                             | 3816 | 0.9991 |       0.9973 |        0.9999 | 0.005006 |      0.003009  |        0.006923 |    0.02107 |
| late_tail_memory        | traditional_cfd_template_pedestal | 3816 | 0.999  |       0.9973 |        0.9999 | 0.005049 |      0.003114  |        0.006938 |    0.02124 |
| late_tail_memory        | gated_attention_waveform_new      | 3816 | 0.9427 |       0.9294 |        0.9566 | 0.07015  |      0.05648   |        0.08399  |    0.3012  |
| late_tail_memory        | 1d_cnn                            | 3816 | 0.7189 |       0.6962 |        0.7481 | 0.1497   |      0.09553   |        0.2015   |    1.448   |
| pedestal_state          | gradient_boosted_trees            | 3816 | 0.8775 |       0.8529 |        0.9003 | 0.0559   |      0.04843   |        0.0649   |    0.7429  |
| pedestal_state          | mlp                               | 3816 | 0.8425 |       0.8186 |        0.867  | 0.07102  |      0.06309   |        0.079    |    0.9811  |
| pedestal_state          | traditional_cfd_template_pedestal | 3816 | 0.8582 |       0.8285 |        0.8856 | 0.072    |      0.0637    |        0.08101  |    0.8433  |
| pedestal_state          | ridge                             | 3816 | 0.8568 |       0.8276 |        0.8848 | 0.07268  |      0.06364   |        0.08103  |    0.8505  |
| pedestal_state          | gated_attention_waveform_new      | 3816 | 0.6794 |       0.662  |        0.6996 | 0.1485   |      0.1354    |        0.1597   |    1.762   |
| pedestal_state          | 1d_cnn                            | 3816 | 0.6752 |       0.6601 |        0.6891 | 0.1648   |      0.1462    |        0.1818   |    1.646   |
| saturation_clipping     | gradient_boosted_trees            | 3816 | 0.927  |       0.8667 |        0.9599 | 0.01069  |      0.009091  |        0.01227  |    0.1282  |
| saturation_clipping     | mlp                               | 3816 | 0.7738 |       0.6261 |        0.8565 | 0.02961  |      0.02645   |        0.03263  |    0.4091  |
| saturation_clipping     | ridge                             | 3816 | 0.8125 |       0.6705 |        0.8895 | 0.03338  |      0.03052   |        0.03657  |    0.3419  |
| saturation_clipping     | traditional_cfd_template_pedestal | 3816 | 0.8149 |       0.6781 |        0.8932 | 0.03342  |      0.03024   |        0.03648  |    0.3402  |
| saturation_clipping     | 1d_cnn                            | 3816 | 0.7475 |       0.5827 |        0.8374 | 0.05281  |      0.03793   |        0.07228  |    0.4112  |
| saturation_clipping     | gated_attention_waveform_new      | 3816 | 0.7137 |       0.5678 |        0.7971 | 0.05618  |      0.04578   |        0.07168  |    0.3861  |

Comparison to the traditional comparator:

| endpoint                | method                       | reference_method                  |   delta_sigma68_ns |   delta_auc |   delta_brier |   delta_log_loss |
|:------------------------|:-----------------------------|:----------------------------------|-------------------:|------------:|--------------:|-----------------:|
| electronics_epoch       | 1d_cnn                       | traditional_cfd_template_pedestal |        nan         |   -0.1419   |     0.1578    |        0.9285    |
| electronics_epoch       | gated_attention_waveform_new | traditional_cfd_template_pedestal |        nan         |   -0.1686   |     0.2029    |        3.496     |
| electronics_epoch       | gradient_boosted_trees       | traditional_cfd_template_pedestal |        nan         |   -0.1461   |     0.198     |        4.628     |
| electronics_epoch       | mlp                          | traditional_cfd_template_pedestal |        nan         |   -0.1647   |     0.1997    |        4.909     |
| electronics_epoch       | ridge                        | traditional_cfd_template_pedestal |        nan         |    0.005054 |    -0.003579  |        0.001453  |
| forced_random_surrogate | 1d_cnn                       | traditional_cfd_template_pedestal |        nan         |   -0.0363   |     0.03049   |        0.4909    |
| forced_random_surrogate | gated_attention_waveform_new | traditional_cfd_template_pedestal |        nan         |   -0.03721  |     0.02121   |       -0.0459    |
| forced_random_surrogate | gradient_boosted_trees       | traditional_cfd_template_pedestal |        nan         |    0.01846  |    -0.08701   |       -1.088     |
| forced_random_surrogate | mlp                          | traditional_cfd_template_pedestal |        nan         |    0.02105  |    -0.2853    |       -0.4923    |
| forced_random_surrogate | ridge                        | traditional_cfd_template_pedestal |        nan         |    0.01997  |    -0.008788  |       -0.2655    |
| late_tail_memory        | 1d_cnn                       | traditional_cfd_template_pedestal |        nan         |   -0.2802   |     0.1447    |        1.426     |
| late_tail_memory        | gated_attention_waveform_new | traditional_cfd_template_pedestal |        nan         |   -0.05635  |     0.0651    |        0.2799    |
| late_tail_memory        | gradient_boosted_trees       | traditional_cfd_template_pedestal |        nan         |   -0.002317 |    -0.003917  |       -0.006533  |
| late_tail_memory        | mlp                          | traditional_cfd_template_pedestal |        nan         |   -0.01061  |    -6.994e-05 |        0.04755   |
| late_tail_memory        | ridge                        | traditional_cfd_template_pedestal |        nan         |    1.53e-06 |    -4.285e-05 |       -0.0001738 |
| pedestal_state          | 1d_cnn                       | traditional_cfd_template_pedestal |        nan         |   -0.183    |     0.09275   |        0.8026    |
| pedestal_state          | gated_attention_waveform_new | traditional_cfd_template_pedestal |        nan         |   -0.1789   |     0.07653   |        0.9184    |
| pedestal_state          | gradient_boosted_trees       | traditional_cfd_template_pedestal |        nan         |    0.01925  |    -0.0161    |       -0.1004    |
| pedestal_state          | mlp                          | traditional_cfd_template_pedestal |        nan         |   -0.01572  |    -0.0009835 |        0.1379    |
| pedestal_state          | ridge                        | traditional_cfd_template_pedestal |        nan         |   -0.001452 |     0.000684  |        0.00725   |
| saturation_clipping     | 1d_cnn                       | traditional_cfd_template_pedestal |        nan         |   -0.06739  |     0.0194    |        0.07104   |
| saturation_clipping     | gated_attention_waveform_new | traditional_cfd_template_pedestal |        nan         |   -0.1011   |     0.02276   |        0.0459    |
| saturation_clipping     | gradient_boosted_trees       | traditional_cfd_template_pedestal |        nan         |    0.1121   |    -0.02273   |       -0.212     |
| saturation_clipping     | mlp                          | traditional_cfd_template_pedestal |        nan         |   -0.04106  |    -0.003803  |        0.06893   |
| saturation_clipping     | ridge                        | traditional_cfd_template_pedestal |        nan         |   -0.002394 |    -3.721e-05 |        0.001718  |
| timing_residual         | 1d_cnn                       | traditional_cfd_template_pedestal |          2.37      |  nan        |   nan         |      nan         |
| timing_residual         | gated_attention_waveform_new | traditional_cfd_template_pedestal |          2.236     |  nan        |   nan         |      nan         |
| timing_residual         | gradient_boosted_trees       | traditional_cfd_template_pedestal |         -0.0007854 |  nan        |   nan         |      nan         |
| timing_residual         | mlp                          | traditional_cfd_template_pedestal |          0.007837  |  nan        |   nan         |      nan         |
| timing_residual         | ridge                        | traditional_cfd_template_pedestal |          0.04196   |  nan        |   nan         |      nan         |

Run-level timing spread:

| method                            |   run |   n |   bias_ns |   sigma68_ns |   tail_fraction_abs_gt_5ns |
|:----------------------------------|------:|----:|----------:|-------------:|---------------------------:|
| 1d_cnn                            |    42 | 477 |  -0.2019  |       3.925  |                   0.174    |
| 1d_cnn                            |    50 | 480 |  -0.1728  |       3.445  |                   0.1875   |
| 1d_cnn                            |    57 | 480 |  -0.3195  |       3.691  |                   0.1729   |
| 1d_cnn                            |    58 | 474 |  -0.1806  |       3.542  |                   0.1793   |
| 1d_cnn                            |    60 | 480 |  -0.2621  |       1.75   |                   0.0625   |
| 1d_cnn                            |    62 | 480 |  -0.3838  |       1.716  |                   0.03958  |
| 1d_cnn                            |    64 | 480 |  -0.3309  |       1.531  |                   0.05417  |
| 1d_cnn                            |    65 | 465 |  -0.1859  |       2.931  |                   0.1355   |
| gated_attention_waveform_new      |    42 | 477 |  -0.3511  |       3.826  |                   0.1698   |
| gated_attention_waveform_new      |    50 | 480 |  -0.2847  |       3.31   |                   0.1708   |
| gated_attention_waveform_new      |    57 | 480 |  -0.4037  |       3.606  |                   0.1583   |
| gated_attention_waveform_new      |    58 | 474 |  -0.3036  |       3.505  |                   0.1646   |
| gated_attention_waveform_new      |    60 | 480 |  -0.3891  |       1.646  |                   0.05208  |
| gated_attention_waveform_new      |    62 | 480 |  -0.4964  |       1.582  |                   0.0375   |
| gated_attention_waveform_new      |    64 | 480 |  -0.4663  |       1.475  |                   0.05208  |
| gated_attention_waveform_new      |    65 | 465 |  -0.3952  |       2.864  |                   0.1204   |
| gradient_boosted_trees            |    42 | 477 |   0.2746  |       0.2669 |                   0        |
| gradient_boosted_trees            |    50 | 480 |   0.08344 |       0.9271 |                   0        |
| gradient_boosted_trees            |    57 | 480 |   0.09879 |       0.3477 |                   0        |
| gradient_boosted_trees            |    58 | 474 |  -0.3555  |       0.2786 |                   0        |
| gradient_boosted_trees            |    60 | 480 |   0.1219  |       0.3857 |                   0        |
| gradient_boosted_trees            |    62 | 480 |  -0.04183 |       0.3679 |                   0        |
| gradient_boosted_trees            |    64 | 480 |  -0.1275  |       0.3715 |                   0        |
| gradient_boosted_trees            |    65 | 465 |  -0.1591  |       0.3569 |                   0        |
| mlp                               |    42 | 477 |   0.2447  |       0.2775 |                   0        |
| mlp                               |    50 | 480 |   0.1173  |       0.9234 |                   0        |
| mlp                               |    57 | 480 |   0.1241  |       0.3836 |                   0.002083 |
| mlp                               |    58 | 474 |  -0.3779  |       0.2979 |                   0        |
| mlp                               |    60 | 480 |   0.1064  |       0.4299 |                   0        |
| mlp                               |    62 | 480 |  -0.01307 |       0.3843 |                   0        |
| mlp                               |    64 | 480 |  -0.1346  |       0.3727 |                   0        |
| mlp                               |    65 | 465 |  -0.1626  |       0.3572 |                   0        |
| ridge                             |    42 | 477 |   0.2722  |       0.2534 |                   0        |
| ridge                             |    50 | 480 |   0.1198  |       0.9443 |                   0        |
| ridge                             |    57 | 480 |   0.09823 |       0.3538 |                   0.002083 |
| ridge                             |    58 | 474 |  -0.4251  |       0.2933 |                   0        |
| ridge                             |    60 | 480 |   0.136   |       0.4868 |                   0        |
| ridge                             |    62 | 480 |  -0.1924  |       0.427  |                   0        |
| ridge                             |    64 | 480 |  -0.1632  |       0.4374 |                   0        |
| ridge                             |    65 | 465 |  -0.1706  |       0.4162 |                   0        |
| traditional_cfd_template_pedestal |    42 | 477 |   0.1073  |       0.3528 |                   0        |
| traditional_cfd_template_pedestal |    50 | 480 |  -0.06708 |       0.9547 |                   0        |
| traditional_cfd_template_pedestal |    57 | 480 |  -0.02842 |       0.5367 |                   0        |
| traditional_cfd_template_pedestal |    58 | 474 |  -0.4311  |       0.4277 |                   0        |
| traditional_cfd_template_pedestal |    60 | 480 |   0.04107 |       0.2947 |                   0        |
| traditional_cfd_template_pedestal |    62 | 480 |  -0.156   |       0.3762 |                   0        |
| traditional_cfd_template_pedestal |    64 | 480 |  -0.2109  |       0.3725 |                   0        |
| traditional_cfd_template_pedestal |    65 | 465 |  -0.1256  |       0.3806 |                   0        |

## Interpretation

The result separates two claims.  For the timing residual alone, `gradient_boosted_trees` and the traditional comparator are nearly tied: boosted trees have sigma68 `0.4215 ns`, while the traditional comparator has `0.4223 ns`.  Boosted trees are stronger on pedestal, late-tail, and saturation labels, but their electronics-epoch and calibration penalties are large enough that the registered S33b composite still selects the traditional comparator.

This does not prove access to true electronics pedestal state.  The audit found `0` forced/random/non-beam ROOT entries and `0` forced/random/pedestal filename-token hits.  The correct physics conclusion is therefore conditional: waveform/state sidebands contain transferable information about operational pedestal-like states, but a true detector-state diagnostic still requires a mirrored forced/random pedestal acquisition or external DAQ run log.

## MC Verdict

MC validation not yet run.  Required closure is an MV7-style digitizer study with known pedestal/electronics-state labels and the same S33b method panel; only that can distinguish physics-event pretrigger labels from true electronics state.

## Open Questions

1. S33d: acquire or mirror true forced/random B-stack pedestal ROOT and rerun this exact S33b benchmark with DAQ-provenanced labels; falsify if the boosted-tree state advantage disappears.
2. MV7: generate digitized MC with known pedestal-memory states and benchmark whether the S33b winner recovers the injected state without using timing residual labels.
3. S34: freeze a deployable boosted-tree pedestal-state score and test downstream timing/PID/energy consumers; falsify if consumer gains vanish under run-family holdout.

## Provenance

Git commit:        `e2dabfe445a742377f867210ec2c9010b0cc3ee0`
Data SHA256:       see `input_sha256.csv`
Python:            `3.7.6`
scikit-learn:      used for AUC, Brier, and log-loss metrics
numpy / scipy:     numpy `1.21.6`
Run host / job:    `billy` / local
Artifacts:         `reports/1783888776.1513.553b5373__s33b_external_pedestal_state_pulse_timing/{REPORT.md,result.json,metrics.csv,method_deltas.csv,run_metrics.csv,trigger_audit.csv,input_sha256.csv,manifest.json}`

## Systematics and Caveats

The dominant systematic is truth availability.  Direct forced/random labels are absent in this mounted ROOT mirror, so S33b cannot validate a physical electronics pedestal endpoint.  The sideband labels are intentionally independent of the timing residual, but they are still derived from physics-event waveforms and can share acquisition-state correlations with pulse shape.  The run-block bootstrap covers observed held-out-run scatter, not unobserved DAQ modes.  The binary endpoints have severe class imbalance in some runs, which widens AUC uncertainty and makes Brier calibration sensitive to base rate.  Neural methods are compact and intentionally comparable to the existing S33a panel; a larger architecture search would be a different ticket.

Runtime was `128.8 s` on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid` with Python `3.7.6`.
