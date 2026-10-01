# S61c: Energy PID Pedestal Pile-Up Disentanglement

Ticket: `2560`  
Worker: `testbeam-laptop-4`  
Raw ROOT directory: `data/root/root`

## Abstract

This study reproduces the canonical B-stack selected-pulse count directly from raw ROOT and benchmarks a traditional dE-E likelihood calibration with explicit tail-integration and pedestal-memory nuisance terms against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new compact spectral transformer. The raw count is **640,737**, exactly matching the registered **640,737** selected pulses. The registered joint score names **gradient_boosted_trees** as the winner across run-held-out and proxy particle-held-out splits.

## Raw ROOT Reproduction

Each `hrdb_run_XXXX.root` file is opened at `h101/HRDv`; the branch is reshaped to `(event, channel, sample)`, samples 0-3 define the channel pedestal, channels B2/B4/B6/B8 are baseline-subtracted, and a pulse is selected when its corrected maximum exceeds 1000 ADC.

| quantity | expected | reproduced | delta |
|---|---:|---:|---:|
| selected B-stave pulses | 640,737 | 640,737 | 0 |

## Split Design and Bootstrap

The run-held-out split removes complete runs `42, 50, 57, 58, 60, 62, 64, 65`. The particle-held-out split removes the proxy particle family `high_amplitude_tail_family` from training; because the reduced raw ROOT branch has no independent species truth, this is a duplicate-response/tail/amplitude family and is treated as a stress test, not a literal beam-particle validation.

For held-out blocks `D_r`, bootstrap replicate `b` draws block labels with replacement and evaluates `theta_b = T(union_{r in S_b} D_r)`. The 95% CI is `[Q_0.025(theta_b), Q_0.975(theta_b)]`. Classification endpoints use ROC AUC and calibration ECE; energy uses `sigma68 = 0.5[Q_0.84(yhat-y)-Q_0.16(yhat-y)]`.

## Methods and Equations

The traditional comparator uses engineered dE-E and pulse-shape variables: log charge, duplicate-readout response, CFD times, Gatti/template distances, Haar coefficients, late/early charge ratios, FFT harmonic fractions, and pedestal residuals. In notation, `E_i=log(1+A_i)-median_{run,stave} log(1+A)`, `T_i=sum_{t=12}^{17} x_i(t)/sum_t x_i(t)`, and `M_i=B_i-median_{run,stave} B`; the traditional likelihood is a regularized linear/Huber surrogate over `[E_i,T_i,M_i,dE/dx-like duplicate response]`.

Ridge minimizes `||y-X beta||_2^2 + lambda ||beta||_2^2`; boosted trees fit `F_M(x)=sum_m eta h_m(x)`; the MLP is a two-layer ReLU network; the 1D-CNN learns local filters over the 18-sample waveform; the new spectral transformer embeds `(sample,time)` tokens and gates the attention-pooled representation by normalized FFT magnitudes.

The registered joint loss is `0.32(1-AUC_PID)+0.24 sigma68_E+0.12(1-AUC_pileup)+0.10(1-AUC_sat)+0.12(1-AUC_ped)+0.10(1-AUC_tail)`. Lower is better.

## Primary Joint Results

Run-held-out:

| method                                    |   joint_loss |   mean_joint_loss |   pid_separation |   energy_scale |   pileup_sideband |   saturation_clipping |   pedestal_noise_color |   pulse_shape_harmonics |
|:------------------------------------------|-------------:|------------------:|-----------------:|---------------:|------------------:|----------------------:|-----------------------:|------------------------:|
| gradient_boosted_trees                    |     0.042312 |          0.069521 |          0.99851 |        0.13912 |           0.99958 |               0.98946 |                0.93882 |                 1       |
| ridge                                     |     0.058166 |          0.094838 |          0.99067 |        0.14288 |           0.99931 |               0.90361 |                0.9149  |                 0.99044 |
| traditional_dE_E_tail_pedestal_likelihood |     0.060238 |          0.098964 |          0.99131 |        0.14911 |           0.99931 |               0.90016 |                0.91142 |                 0.99027 |
| mlp                                       |     0.14938  |          0.2143   |          0.92059 |        0.29045 |           0.9858  |               0.80536 |                0.84796 |                 0.85156 |
| spectral_transformer_new                  |     0.345    |          0.31595  |          0.60098 |        0.42257 |           0.8382  |               0.63834 |                0.71055 |                 0.74425 |
| 1d_cnn                                    |     0.34777  |          0.34958  |          0.59129 |        0.42959 |           0.69781 |               0.78676 |                0.69552 |                 0.80243 |

Particle-held-out proxy:

| method                                    |   joint_loss |   mean_joint_loss |   pid_separation |   energy_scale |   pileup_sideband |   saturation_clipping |   pedestal_noise_color |   pulse_shape_harmonics |
|:------------------------------------------|-------------:|------------------:|-----------------:|---------------:|------------------:|----------------------:|-----------------------:|------------------------:|
| gradient_boosted_trees                    |     0.096731 |          0.069521 |          0.93312 |        0.11845 |           0.9959  |               1       |                0.61327 |                 1       |
| ridge                                     |     0.13151  |          0.094838 |          0.93183 |        0.11875 |           0.99787 |               0.79358 |                0.59616 |                 0.88165 |
| traditional_dE_E_tail_pedestal_likelihood |     0.13769  |          0.098964 |          0.91989 |        0.12275 |           0.99785 |               0.79078 |                0.58535 |                 0.88343 |
| mlp                                       |     0.27923  |          0.2143   |          0.79568 |        0.33244 |           0.93531 |               0.65625 |                0.49771 |                 0.68347 |
| spectral_transformer_new                  |     0.28689  |          0.31595  |          0.57233 |        0.17679 |           0.89852 |               0.86435 |                0.63533 |                 0.6189  |
| 1d_cnn                                    |     0.35139  |          0.34958  |          0.41776 |        0.17194 |           0.86299 |               0.84487 |                0.47506 |                 0.71141 |

## Endpoint Bootstrap CIs

| split_name       | endpoint              | method                                    |   metric_value |   ci_low |   ci_high |   n |   positives |
|:-----------------|:----------------------|:------------------------------------------|---------------:|---------:|----------:|----:|------------:|
| run_heldout      | pid_separation        | gradient_boosted_trees                    |        0.99851 |  0.99747 |   0.99938 | 960 |         556 |
| run_heldout      | pid_separation        | traditional_dE_E_tail_pedestal_likelihood |        0.99131 |  0.98706 |   0.99444 | 960 |         556 |
| run_heldout      | pid_separation        | ridge                                     |        0.99067 |  0.98705 |   0.99406 | 960 |         556 |
| run_heldout      | pid_separation        | mlp                                       |        0.92059 |  0.9057  |   0.93468 | 960 |         556 |
| run_heldout      | pid_separation        | spectral_transformer_new                  |        0.60098 |  0.56205 |   0.62716 | 960 |         556 |
| run_heldout      | pid_separation        | 1d_cnn                                    |        0.59129 |  0.56096 |   0.62429 | 960 |         556 |
| run_heldout      | energy_scale          | gradient_boosted_trees                    |        0.13912 |  0.10314 |   0.2112  | 960 |             |
| run_heldout      | energy_scale          | ridge                                     |        0.14288 |  0.10982 |   0.22522 | 960 |             |
| run_heldout      | energy_scale          | traditional_dE_E_tail_pedestal_likelihood |        0.14911 |  0.12691 |   0.16088 | 960 |             |
| run_heldout      | energy_scale          | mlp                                       |        0.29045 |  0.25964 |   0.32728 | 960 |             |
| run_heldout      | energy_scale          | spectral_transformer_new                  |        0.42257 |  0.39465 |   0.44672 | 960 |             |
| run_heldout      | energy_scale          | 1d_cnn                                    |        0.42959 |  0.39667 |   0.44988 | 960 |             |
| run_heldout      | pileup_sideband       | gradient_boosted_trees                    |        0.99958 |  0.99903 |   1       | 960 |         152 |
| run_heldout      | pileup_sideband       | ridge                                     |        0.99931 |  0.99871 |   0.99989 | 960 |         152 |
| run_heldout      | pileup_sideband       | traditional_dE_E_tail_pedestal_likelihood |        0.99931 |  0.99853 |   0.99982 | 960 |         152 |
| run_heldout      | pileup_sideband       | mlp                                       |        0.9858  |  0.97403 |   0.99423 | 960 |         152 |
| run_heldout      | pileup_sideband       | spectral_transformer_new                  |        0.8382  |  0.79935 |   0.864   | 960 |         152 |
| run_heldout      | pileup_sideband       | 1d_cnn                                    |        0.69781 |  0.65496 |   0.72476 | 960 |         152 |
| run_heldout      | saturation_clipping   | gradient_boosted_trees                    |        0.98946 |  0.95825 |   0.99788 | 960 |          61 |
| run_heldout      | saturation_clipping   | ridge                                     |        0.90361 |  0.76079 |   0.96624 | 960 |          61 |
| run_heldout      | saturation_clipping   | traditional_dE_E_tail_pedestal_likelihood |        0.90016 |  0.74933 |   0.96171 | 960 |          61 |
| run_heldout      | saturation_clipping   | mlp                                       |        0.80536 |  0.64164 |   0.86924 | 960 |          61 |
| run_heldout      | saturation_clipping   | 1d_cnn                                    |        0.78676 |  0.62958 |   0.88487 | 960 |          61 |
| run_heldout      | saturation_clipping   | spectral_transformer_new                  |        0.63834 |  0.57942 |   0.68156 | 960 |          61 |
| run_heldout      | pedestal_noise_color  | gradient_boosted_trees                    |        0.93882 |  0.91034 |   0.97173 | 960 |         189 |
| run_heldout      | pedestal_noise_color  | ridge                                     |        0.9149  |  0.88786 |   0.93893 | 960 |         189 |
| run_heldout      | pedestal_noise_color  | traditional_dE_E_tail_pedestal_likelihood |        0.91142 |  0.89303 |   0.93688 | 960 |         189 |
| run_heldout      | pedestal_noise_color  | mlp                                       |        0.84796 |  0.82615 |   0.86323 | 960 |         189 |
| run_heldout      | pedestal_noise_color  | spectral_transformer_new                  |        0.71055 |  0.67229 |   0.75955 | 960 |         189 |
| run_heldout      | pedestal_noise_color  | 1d_cnn                                    |        0.69552 |  0.64114 |   0.74553 | 960 |         189 |
| run_heldout      | pulse_shape_harmonics | gradient_boosted_trees                    |        1       |  1       |   1       | 960 |         192 |
| run_heldout      | pulse_shape_harmonics | ridge                                     |        0.99044 |  0.98846 |   0.99273 | 960 |         192 |
| run_heldout      | pulse_shape_harmonics | traditional_dE_E_tail_pedestal_likelihood |        0.99027 |  0.98778 |   0.99233 | 960 |         192 |
| run_heldout      | pulse_shape_harmonics | mlp                                       |        0.85156 |  0.78196 |   0.89072 | 960 |         192 |
| run_heldout      | pulse_shape_harmonics | 1d_cnn                                    |        0.80243 |  0.7336  |   0.85844 | 960 |         192 |
| run_heldout      | pulse_shape_harmonics | spectral_transformer_new                  |        0.74425 |  0.72462 |   0.76875 | 960 |         192 |
| particle_heldout | pid_separation        | gradient_boosted_trees                    |        0.93312 |  0.91054 |   0.95446 | 462 |          99 |
| particle_heldout | pid_separation        | ridge                                     |        0.93183 |  0.89477 |   0.96895 | 462 |          99 |
| particle_heldout | pid_separation        | traditional_dE_E_tail_pedestal_likelihood |        0.91989 |  0.88463 |   0.95245 | 462 |          99 |
| particle_heldout | pid_separation        | mlp                                       |        0.79568 |  0.75351 |   0.83168 | 462 |          99 |
| particle_heldout | pid_separation        | spectral_transformer_new                  |        0.57233 |  0.5096  |   0.63927 | 462 |          99 |
| particle_heldout | pid_separation        | 1d_cnn                                    |        0.41776 |  0.36754 |   0.4736  | 462 |          99 |
| particle_heldout | energy_scale          | gradient_boosted_trees                    |        0.11845 |  0.1042  |   0.14188 | 462 |             |
| particle_heldout | energy_scale          | ridge                                     |        0.11875 |  0.099   |   0.13754 | 462 |             |
| particle_heldout | energy_scale          | traditional_dE_E_tail_pedestal_likelihood |        0.12275 |  0.10993 |   0.15269 | 462 |             |
| particle_heldout | energy_scale          | 1d_cnn                                    |        0.17194 |  0.15786 |   0.1884  | 462 |             |
| particle_heldout | energy_scale          | spectral_transformer_new                  |        0.17679 |  0.15684 |   0.19019 | 462 |             |
| particle_heldout | energy_scale          | mlp                                       |        0.33244 |  0.30814 |   0.3729  | 462 |             |
| particle_heldout | pileup_sideband       | ridge                                     |        0.99787 |  0.99531 |   0.99946 | 462 |         204 |
| particle_heldout | pileup_sideband       | traditional_dE_E_tail_pedestal_likelihood |        0.99785 |  0.99615 |   0.99936 | 462 |         204 |
| particle_heldout | pileup_sideband       | gradient_boosted_trees                    |        0.9959  |  0.99311 |   0.99825 | 462 |         204 |
| particle_heldout | pileup_sideband       | mlp                                       |        0.93531 |  0.90837 |   0.96122 | 462 |         204 |
| particle_heldout | pileup_sideband       | spectral_transformer_new                  |        0.89852 |  0.86975 |   0.92656 | 462 |         204 |
| particle_heldout | pileup_sideband       | 1d_cnn                                    |        0.86299 |  0.82387 |   0.89987 | 462 |         204 |
| particle_heldout | saturation_clipping   | gradient_boosted_trees                    |        1       |  1       |   1       | 462 |          16 |
| particle_heldout | saturation_clipping   | spectral_transformer_new                  |        0.86435 |  0.77644 |   0.97135 | 462 |          16 |
| particle_heldout | saturation_clipping   | 1d_cnn                                    |        0.84487 |  0.74134 |   0.96119 | 462 |          16 |
| particle_heldout | saturation_clipping   | ridge                                     |        0.79358 |  0.67067 |   0.94294 | 462 |          16 |
| particle_heldout | saturation_clipping   | traditional_dE_E_tail_pedestal_likelihood |        0.79078 |  0.63441 |   0.95867 | 462 |          16 |
| particle_heldout | saturation_clipping   | mlp                                       |        0.65625 |  0.54994 |   0.78571 | 462 |          16 |
| particle_heldout | pedestal_noise_color  | spectral_transformer_new                  |        0.63533 |  0.52213 |   0.75624 | 462 |          25 |
| particle_heldout | pedestal_noise_color  | gradient_boosted_trees                    |        0.61327 |  0.45376 |   0.72996 | 462 |          25 |
| particle_heldout | pedestal_noise_color  | ridge                                     |        0.59616 |  0.5024  |   0.70312 | 462 |          25 |
| particle_heldout | pedestal_noise_color  | traditional_dE_E_tail_pedestal_likelihood |        0.58535 |  0.49351 |   0.68119 | 462 |          25 |
| particle_heldout | pedestal_noise_color  | mlp                                       |        0.49771 |  0.49496 |   0.5     | 462 |          25 |
| particle_heldout | pedestal_noise_color  | 1d_cnn                                    |        0.47506 |  0.37931 |   0.57192 | 462 |          25 |
| particle_heldout | pulse_shape_harmonics | gradient_boosted_trees                    |        1       |  1       |   1       | 462 |         305 |
| particle_heldout | pulse_shape_harmonics | traditional_dE_E_tail_pedestal_likelihood |        0.88343 |  0.84789 |   0.91439 | 462 |         305 |
| particle_heldout | pulse_shape_harmonics | ridge                                     |        0.88165 |  0.83548 |   0.91447 | 462 |         305 |
| particle_heldout | pulse_shape_harmonics | 1d_cnn                                    |        0.71141 |  0.66186 |   0.74989 | 462 |         305 |
| particle_heldout | pulse_shape_harmonics | mlp                                       |        0.68347 |  0.64968 |   0.72208 | 462 |         305 |
| particle_heldout | pulse_shape_harmonics | spectral_transformer_new                  |        0.6189  |  0.57716 |   0.66932 | 462 |         305 |

## PID Calibration and Energy Residuals

| split_name       | method                                    |     auc |      ece |   n |   positives |
|:-----------------|:------------------------------------------|--------:|---------:|----:|------------:|
| particle_heldout | 1d_cnn                                    | 0.41776 | 0.32522  | 462 |          99 |
| particle_heldout | gradient_boosted_trees                    | 0.93312 | 0.20085  | 462 |          99 |
| particle_heldout | mlp                                       | 0.79568 | 0.39774  | 462 |          99 |
| particle_heldout | ridge                                     | 0.93183 | 0.26864  | 462 |          99 |
| particle_heldout | spectral_transformer_new                  | 0.57233 | 0.31164  | 462 |          99 |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood | 0.91989 | 0.26279  | 462 |          99 |
| run_heldout      | 1d_cnn                                    | 0.59129 | 0.074033 | 960 |         556 |
| run_heldout      | gradient_boosted_trees                    | 0.99851 | 0.053229 | 960 |         556 |
| run_heldout      | mlp                                       | 0.92059 | 0.28717  | 960 |         556 |
| run_heldout      | ridge                                     | 0.99067 | 0.26663  | 960 |         556 |
| run_heldout      | spectral_transformer_new                  | 0.60098 | 0.077481 | 960 |         556 |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood | 0.99131 | 0.27159  | 960 |         556 |

Energy residual rows are the `energy_scale` endpoint in the CI table; they are log-amplitude residuals after run/stave centering, not an externally calibrated MeV scale.

## Paired Bootstrap Deltas vs Traditional

| split_name       | endpoint              | method                   |   delta_vs_traditional |      ci_low |     ci_high | delta_definition                                             |
|:-----------------|:----------------------|:-------------------------|-----------------------:|------------:|------------:|:-------------------------------------------------------------|
| particle_heldout | energy_scale          | 1d_cnn                   |             0.045848   |  0.026656   |  0.064749   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | gradient_boosted_trees   |            -0.0031263  | -0.02031    |  0.015259   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | mlp                      |             0.20874    |  0.17542    |  0.23834    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | ridge                    |            -0.0077628  | -0.027858   |  0.0084997  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | spectral_transformer_new |             0.048278   |  0.030074   |  0.062854   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | 1d_cnn                   |            -0.099839   | -0.21753    |  0.013869   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | gradient_boosted_trees   |             0.029407   | -0.11876    |  0.17816    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | mlp                      |            -0.083402   | -0.18958    |  0.00067322 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | ridge                    |             0.011977   | -0.012974   |  0.038617   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | spectral_transformer_new |             0.047374   | -0.133      |  0.22331    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | 1d_cnn                   |            -0.50024    | -0.57023    | -0.42953    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | gradient_boosted_trees   |             0.016048   | -0.013759   |  0.061844   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | mlp                      |            -0.12218    | -0.16098    | -0.085145   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | ridge                    |             0.011687   |  0.0041906  |  0.017867   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | spectral_transformer_new |            -0.34517    | -0.41084    | -0.27582    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | 1d_cnn                   |            -0.13726    | -0.17122    | -0.10939    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | gradient_boosted_trees   |            -0.0020432  | -0.0043338  | -0.00050974 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | mlp                      |            -0.062778   | -0.090507   | -0.038273   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | ridge                    |             3.9395e-05 | -7.78e-05   |  0.00024511 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | spectral_transformer_new |            -0.098875   | -0.12752    | -0.07354    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | 1d_cnn                   |            -0.16746    | -0.2199     | -0.11667    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | gradient_boosted_trees   |             0.11917    |  0.081564   |  0.15722    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | mlp                      |            -0.20238    | -0.23463    | -0.16773    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | ridge                    |            -0.0014408  | -0.0051477  |  0.0023566  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | spectral_transformer_new |            -0.26774    | -0.31806    | -0.21671    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | 1d_cnn                   |             0.04424    | -0.1222     |  0.20712    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | gradient_boosted_trees   |             0.20087    |  0.040374   |  0.3684     | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | mlp                      |            -0.12869    | -0.29028    |  0.049013   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | ridge                    |             0.0030324  | -0.0055274  |  0.016107   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | spectral_transformer_new |             0.078353   | -0.081366   |  0.2481     | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | 1d_cnn                   |             0.27884    |  0.24534    |  0.31722    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | gradient_boosted_trees   |            -0.011237   | -0.061127   |  0.05796    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | mlp                      |             0.13996    |  0.10623    |  0.19328    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | ridge                    |             0.013782   | -0.040906   |  0.10773    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | spectral_transformer_new |             0.26873    |  0.24333    |  0.30097    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | 1d_cnn                   |            -0.21568    | -0.2754     | -0.16041    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | gradient_boosted_trees   |             0.026099   |  0.0085454  |  0.050374   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | mlp                      |            -0.0642     | -0.081322   | -0.04886    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | ridge                    |             0.0037508  | -0.0088991  |  0.016705   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | spectral_transformer_new |            -0.20274    | -0.26067    | -0.15644    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | 1d_cnn                   |            -0.39902    | -0.43622    | -0.36987    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | gradient_boosted_trees   |             0.0072461  |  0.0045204  |  0.011081   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | mlp                      |            -0.070657   | -0.086125   | -0.055759   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | ridge                    |            -0.0005841  | -0.0012663  |  0.0001657  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | spectral_transformer_new |            -0.39132    | -0.42073    | -0.36727    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | 1d_cnn                   |            -0.30292    | -0.33584    | -0.27758    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | gradient_boosted_trees   |             0.00025747 | -0.00020759 |  0.00080112 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | mlp                      |            -0.013538   | -0.024749   | -0.0051848  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | ridge                    |             3.7007e-18 | -1.1102e-16 |  2.2204e-16 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | spectral_transformer_new |            -0.16069    | -0.201      | -0.12814    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | 1d_cnn                   |            -0.18797    | -0.26379    | -0.13797    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | gradient_boosted_trees   |             0.0095553  |  0.0073696  |  0.011462   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | mlp                      |            -0.137      | -0.20029    | -0.090752   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | ridge                    |             0.00015857 | -0.00043614 |  0.0006446  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | spectral_transformer_new |            -0.24699    | -0.26502    | -0.21874    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | 1d_cnn                   |            -0.12609    | -0.24025    | -0.053609   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | gradient_boosted_trees   |             0.10251    |  0.024918   |  0.22383    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | mlp                      |            -0.10239    | -0.2131     | -0.055137   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | ridge                    |             0.0038546  | -0.006225   |  0.015698   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | spectral_transformer_new |            -0.25176    | -0.32441    | -0.11592    | AUC gain for classification; sigma68 increase for regression |

## Stratified Systematics

The full `strata_metrics.csv` file stratifies each endpoint by late-tail amplitude, pedestal history, pulse-shape harmonic content, timing residual, pile-up flag, saturation flag, and energy bin. The excerpt below shows the winner on the two most relevant PID/energy axes.

| split_name       | endpoint       | stratum_axis         | stratum         |   n | metric   |   value |
|:-----------------|:---------------|:---------------------|:----------------|----:|:---------|--------:|
| particle_heldout | energy_scale   | tail_amplitude_bin   | tail_high       | 447 | sigma68  | 0.11896 |
| particle_heldout | energy_scale   | pedestal_history_bin | pedestal_memory | 121 | sigma68  | 0.10064 |
| particle_heldout | energy_scale   | pedestal_history_bin | pedestal_mid    | 174 | sigma68  | 0.10346 |
| particle_heldout | energy_scale   | pedestal_history_bin | pedestal_quiet  | 167 | sigma68  | 0.18735 |
| particle_heldout | energy_scale   | pulse_shape_bin      | low_harmonic    | 212 | sigma68  | 0.14557 |
| particle_heldout | energy_scale   | pulse_shape_bin      | mid_harmonic    | 247 | sigma68  | 0.11626 |
| particle_heldout | energy_scale   | timing_residual_bin  | timing_core     | 136 | sigma68  | 0.12514 |
| particle_heldout | energy_scale   | timing_residual_bin  | timing_mid      | 144 | sigma68  | 0.14025 |
| particle_heldout | energy_scale   | timing_residual_bin  | timing_tail     | 182 | sigma68  | 0.11583 |
| particle_heldout | energy_scale   | pileup_flag          | pileup_proxy    | 204 | sigma68  | 0.11658 |
| particle_heldout | energy_scale   | pileup_flag          | single_proxy    | 258 | sigma68  | 0.13279 |
| particle_heldout | energy_scale   | saturation_flag      | linear_proxy    | 446 | sigma68  | 0.11625 |
| particle_heldout | energy_scale   | energy_bin           | energy_high     | 436 | sigma68  | 0.11563 |
| particle_heldout | pid_separation | tail_amplitude_bin   | tail_high       | 447 | auc      | 0.93045 |
| particle_heldout | pid_separation | pedestal_history_bin | pedestal_memory | 121 | auc      | 0.93839 |
| particle_heldout | pid_separation | pedestal_history_bin | pedestal_mid    | 174 | auc      | 0.93592 |
| particle_heldout | pid_separation | pedestal_history_bin | pedestal_quiet  | 167 | auc      | 0.92724 |
| particle_heldout | pid_separation | pulse_shape_bin      | low_harmonic    | 212 | auc      | 0.89553 |
| particle_heldout | pid_separation | pulse_shape_bin      | mid_harmonic    | 247 | auc      | 0.90223 |
| particle_heldout | pid_separation | timing_residual_bin  | timing_core     | 136 | auc      | 0.92658 |
| particle_heldout | pid_separation | timing_residual_bin  | timing_mid      | 144 | auc      | 0.84084 |
| particle_heldout | pid_separation | timing_residual_bin  | timing_tail     | 182 | auc      | 0.9698  |
| particle_heldout | pid_separation | pileup_flag          | pileup_proxy    | 204 | auc      | 0.9683  |
| particle_heldout | pid_separation | pileup_flag          | single_proxy    | 258 | auc      | 0.89086 |
| particle_heldout | pid_separation | saturation_flag      | linear_proxy    | 446 | auc      | 0.94218 |
| particle_heldout | pid_separation | energy_bin           | energy_high     | 436 | auc      | 0.93294 |
| run_heldout      | energy_scale   | tail_amplitude_bin   | tail_high       | 320 | sigma68  | 0.1026  |
| run_heldout      | energy_scale   | tail_amplitude_bin   | tail_low        | 317 | sigma68  | 0.16188 |
| run_heldout      | energy_scale   | tail_amplitude_bin   | tail_mid        | 323 | sigma68  | 0.1644  |
| run_heldout      | energy_scale   | pedestal_history_bin | pedestal_memory | 330 | sigma68  | 0.10139 |

## Leakage, Feature, and Attention Audits

| split_name       | method                                    |   pid_auc |   energy_sigma68 |   late_tail_auc |   pedestal_auc |   pid_ece |   cross_task_leakage_index | interpretation                                                                          |
|:-----------------|:------------------------------------------|----------:|-----------------:|----------------:|---------------:|----------:|---------------------------:|:----------------------------------------------------------------------------------------|
| particle_heldout | 1d_cnn                                    |   0.41776 |          0.17194 |         0.71141 |        0.47506 |  0.32522  |                   0        | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | gradient_boosted_trees                    |   0.93312 |          0.11845 |         1       |        0.61327 |  0.20085  |                   0.32139  | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | mlp                                       |   0.79568 |          0.33244 |         0.68347 |        0.49771 |  0.39774  |                   0.29797  | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | ridge                                     |   0.93183 |          0.11875 |         0.88165 |        0.59616 |  0.26864  |                   0.33692  | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | spectral_transformer_new                  |   0.57233 |          0.17679 |         0.6189  |        0.63533 |  0.31164  |                   0        | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood |   0.91989 |          0.12275 |         0.88343 |        0.58535 |  0.26279  |                   0.33453  | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | 1d_cnn                                    |   0.59129 |          0.42959 |         0.80243 |        0.69552 |  0.074033 |                   0        | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | gradient_boosted_trees                    |   0.99851 |          0.13912 |         1       |        0.93882 |  0.053229 |                   0.059688 | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | mlp                                       |   0.92059 |          0.29045 |         0.85156 |        0.84796 |  0.28717  |                   0.072626 | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | ridge                                     |   0.99067 |          0.14288 |         0.99044 |        0.9149  |  0.26663  |                   0.075775 | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | spectral_transformer_new                  |   0.60098 |          0.42257 |         0.74425 |        0.71055 |  0.077481 |                   0        | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood |   0.99131 |          0.14911 |         0.99027 |        0.91142 |  0.27159  |                   0.079891 | proxy-label coupling audit; high values require external truth before physics promotion |

Feature-family audit:

| feature                   | family                         |
|:--------------------------|:-------------------------------|
| tail_10_17_over_total     | charge_comparison_psd          |
| tail_12_17_over_total     | charge_comparison_psd          |
| tail_14_17_over_total     | charge_comparison_psd          |
| early_0_4_over_total      | charge_comparison_psd          |
| middle_5_9_over_total     | charge_comparison_psd          |
| late_minus_early_asym     | charge_comparison_psd          |
| rise_10_50                | rise_time_width                |
| rise_20_80                | rise_time_width                |
| width20                   | rise_time_width                |
| width50                   | rise_time_width                |
| max_rise_step             | zero_crossing_derivative       |
| max_fall_step             | zero_crossing_derivative       |
| zero_crossings_derivative | zero_crossing_derivative       |
| mean_time                 | mean_time_moments              |
| time_variance             | mean_time_moments              |
| time_skewness             | mean_time_moments              |
| time_kurtosis             | mean_time_moments              |
| fft_k1_fraction           | frequency_domain_fft           |
| fft_k2_fraction           | frequency_domain_fft           |
| fft_high_over_low         | frequency_domain_fft           |
| cfd20_time                | constant_fraction_shape_ratios |
| cfd50_time                | constant_fraction_shape_ratios |
| le_ratio_s4_s7            | constant_fraction_shape_ratios |
| le_ratio_s5_s7            | constant_fraction_shape_ratios |
| cf_ratio_s6_s8            | constant_fraction_shape_ratios |
| haar_l0_d00               | wavelet_haar                   |
| haar_l0_d01               | wavelet_haar                   |
| haar_l0_d02               | wavelet_haar                   |
| haar_l0_d03               | wavelet_haar                   |
| haar_l0_d04               | wavelet_haar                   |
| haar_l0_d05               | wavelet_haar                   |
| haar_l0_d06               | wavelet_haar                   |
| haar_l0_d07               | wavelet_haar                   |
| haar_l1_d00               | wavelet_haar                   |
| haar_l1_d01               | wavelet_haar                   |
| haar_l1_d02               | wavelet_haar                   |
| haar_l1_d03               | wavelet_haar                   |
| haar_l2_d00               | wavelet_haar                   |
| haar_l2_d01               | wavelet_haar                   |
| haar_l3_d00               | wavelet_haar                   |

The spectral-transformer row is the attention-style sensitivity audit: its gains or losses are compared with the feature-engineered traditional baseline and the 1D-CNN under identical splits. This script does not export per-head attention maps; with 18 samples and proxy labels, endpoint-stable performance is treated as stronger evidence than visual attention weights.

## Ticket 2560 Addendum: Energy/PID Disentanglement

Ticket `#2560` asks what pulse information remains for energy reconstruction and proton/deuteron PID after controlling pedestal memory, pile-up, saturation, and timing phase. The base benchmark is intentionally conservative: the ROOT branch has no external species or MeV truth, so energy and PID are waveform-derived proxy endpoints. The report therefore treats high performance as evidence about transferable pulse information and leakage risk, not as a final physics PID measurement.

The analysis starts from raw B-stack ROOT, reproduces the registered selected-pulse count, samples only after that count closure, and splits by complete run. A second proxy-family split is retained as a particle-family stress test. The model panel is the requested traditional dE-E/range-energy style baseline, ridge, histogram gradient-boosted trees, MLP, 1D-CNN, and a new compact spectral-transformer waveform architecture.

### Pedestal-State Held-Out Stress

| split_name       | endpoint              | method                                    | metric   |   metric_value |   ci_low |   ci_high |   n |
|:-----------------|:----------------------|:------------------------------------------|:---------|---------------:|---------:|----------:|----:|
| particle_heldout | energy_scale          | 1d_cnn                                    | sigma68  |       0.15201  | 0.13334  |   0.1687  | 121 |
| particle_heldout | energy_scale          | gradient_boosted_trees                    | sigma68  |       0.10064  | 0.088306 |   0.12721 | 121 |
| particle_heldout | energy_scale          | mlp                                       | sigma68  |       0.25581  | 0.20323  |   0.28835 | 121 |
| particle_heldout | energy_scale          | ridge                                     | sigma68  |       0.098063 | 0.075733 |   0.11184 | 121 |
| particle_heldout | energy_scale          | spectral_transformer_new                  | sigma68  |       0.14683  | 0.12783  |   0.17055 | 121 |
| particle_heldout | energy_scale          | traditional_dE_E_tail_pedestal_likelihood | sigma68  |       0.10934  | 0.095181 |   0.13679 | 121 |
| particle_heldout | pedestal_noise_color  | 1d_cnn                                    | auc      |       0.52877  | 0.27803  |   0.71702 | 121 |
| particle_heldout | pedestal_noise_color  | gradient_boosted_trees                    | auc      |       0.56845  | 0.38836  |   0.78238 | 121 |
| particle_heldout | pedestal_noise_color  | mlp                                       | auc      |       0.5      | 0.5      |   0.5     | 121 |
| particle_heldout | pedestal_noise_color  | ridge                                     | auc      |       0.65179  | 0.5264   |   0.78111 | 121 |
| particle_heldout | pedestal_noise_color  | spectral_transformer_new                  | auc      |       0.53075  | 0.43981  |   0.65233 | 121 |
| particle_heldout | pedestal_noise_color  | traditional_dE_E_tail_pedestal_likelihood | auc      |       0.67659  | 0.53597  |   0.81225 | 121 |
| particle_heldout | pid_separation        | 1d_cnn                                    | auc      |       0.1369   | 0.088889 |   0.34051 | 121 |
| particle_heldout | pid_separation        | gradient_boosted_trees                    | auc      |       0.93839  | 0.8562   |   0.96946 | 121 |
| particle_heldout | pid_separation        | mlp                                       | auc      |       0.82857  | 0.80403  |   0.86301 | 121 |
| particle_heldout | pid_separation        | ridge                                     | auc      |       0.98214  | 0.97035  |   0.99697 | 121 |
| particle_heldout | pid_separation        | spectral_transformer_new                  | auc      |       0.83155  | 0.67293  |   0.94722 | 121 |
| particle_heldout | pid_separation        | traditional_dE_E_tail_pedestal_likelihood | auc      |       0.96726  | 0.94128  |   0.98994 | 121 |
| particle_heldout | pileup_sideband       | 1d_cnn                                    | auc      |       0.99536  | 0.98507  |   0.99941 | 121 |
| particle_heldout | pileup_sideband       | gradient_boosted_trees                    | auc      |       0.9985   | 0.99438  |   1       | 121 |
| particle_heldout | pileup_sideband       | mlp                                       | auc      |       0.90984  | 0.8585   |   0.94905 | 121 |
| particle_heldout | pileup_sideband       | ridge                                     | auc      |       0.99836  | 0.99287  |   0.99989 | 121 |
| particle_heldout | pileup_sideband       | spectral_transformer_new                  | auc      |       0.98224  | 0.96217  |   0.99549 | 121 |
| particle_heldout | pileup_sideband       | traditional_dE_E_tail_pedestal_likelihood | auc      |       0.99836  | 0.99335  |   0.99987 | 121 |
| particle_heldout | pulse_shape_harmonics | 1d_cnn                                    | auc      |       0.71355  | 0.62077  |   0.83405 | 121 |
| particle_heldout | pulse_shape_harmonics | gradient_boosted_trees                    | auc      |       1        | 1        |   1       | 121 |
| particle_heldout | pulse_shape_harmonics | mlp                                       | auc      |       0.58645  | 0.54346  |   0.66887 | 121 |
| particle_heldout | pulse_shape_harmonics | ridge                                     | auc      |       0.77875  | 0.67138  |   0.85462 | 121 |
| particle_heldout | pulse_shape_harmonics | spectral_transformer_new                  | auc      |       0.70733  | 0.57782  |   0.79903 | 121 |
| particle_heldout | pulse_shape_harmonics | traditional_dE_E_tail_pedestal_likelihood | auc      |       0.77656  | 0.6582   |   0.87427 | 121 |
| particle_heldout | saturation_clipping   | 1d_cnn                                    | auc      |       0.5      | 0.013823 |   0.96968 | 121 |
| particle_heldout | saturation_clipping   | gradient_boosted_trees                    | auc      |       1        | 1        |   1       | 121 |
| particle_heldout | saturation_clipping   | mlp                                       | auc      |       0.5      | 0.5      |   0.5     | 121 |
| particle_heldout | saturation_clipping   | ridge                                     | auc      |       0.31092  | 0.025245 |   0.63538 | 121 |
| particle_heldout | saturation_clipping   | spectral_transformer_new                  | auc      |       0.84034  | 0.77454  |   0.88544 | 121 |
| particle_heldout | saturation_clipping   | traditional_dE_E_tail_pedestal_likelihood | auc      |       0.31933  | 0.04552  |   0.59545 | 121 |

### Topology-Matched Negative Controls

Rows below condition simultaneously on pile-up proxy, saturation proxy, and energy bin before recomputing endpoint metrics. These controls ask whether winner performance survives topology matching rather than merely exploiting gross occupancy or amplitude differences.

| split_name       | endpoint            | pileup_flag   | saturation_flag   | energy_bin   | metric   |   metric_value |     ci_low |    ci_high |   n |
|:-----------------|:--------------------|:--------------|:------------------|:-------------|:---------|---------------:|-----------:|-----------:|----:|
| particle_heldout | energy_scale        | single_proxy  | linear_proxy      | energy_high  | sigma68  |       0.11528  |   0.10014  |   0.14754  | 231 |
| particle_heldout | energy_scale        | pileup_proxy  | linear_proxy      | energy_high  | sigma68  |       0.11167  |   0.088865 |   0.1288   | 192 |
| particle_heldout | pid_separation      | single_proxy  | linear_proxy      | energy_high  | auc      |       0.88026  |   0.86047  |   0.89872  | 231 |
| particle_heldout | pid_separation      | pileup_proxy  | linear_proxy      | energy_high  | auc      |       0.98984  |   0.9768   |   1        | 192 |
| particle_heldout | pileup_sideband     | single_proxy  | linear_proxy      | energy_high  | auc      |     nan        | nan        | nan        | 231 |
| particle_heldout | pileup_sideband     | pileup_proxy  | linear_proxy      | energy_high  | auc      |     nan        | nan        | nan        | 192 |
| particle_heldout | saturation_clipping | single_proxy  | linear_proxy      | energy_high  | auc      |     nan        | nan        | nan        | 231 |
| particle_heldout | saturation_clipping | pileup_proxy  | linear_proxy      | energy_high  | auc      |     nan        | nan        | nan        | 192 |
| run_heldout      | energy_scale        | single_proxy  | linear_proxy      | energy_low   | sigma68  |       0.14764  |   0.10768  |   0.1787   | 270 |
| run_heldout      | energy_scale        | single_proxy  | linear_proxy      | energy_high  | sigma68  |       0.1424   |   0.10762  |   0.2209   | 253 |
| run_heldout      | energy_scale        | single_proxy  | linear_proxy      | energy_mid   | sigma68  |       0.10219  |   0.070964 |   0.14973  | 231 |
| run_heldout      | energy_scale        | pileup_proxy  | linear_proxy      | energy_mid   | sigma68  |       0.056518 |   0.045491 |   0.087133 |  65 |
| run_heldout      | energy_scale        | pileup_proxy  | linear_proxy      | energy_low   | sigma68  |       0.072946 |   0.062172 |   0.089408 |  44 |
| run_heldout      | energy_scale        | pileup_proxy  | linear_proxy      | energy_high  | sigma68  |       0.065533 |   0.035548 |   0.1928   |  36 |
| run_heldout      | energy_scale        | single_proxy  | saturation_proxy  | energy_mid   | sigma68  |       0.095258 |   0.021675 |   0.097227 |  27 |
| run_heldout      | energy_scale        | single_proxy  | saturation_proxy  | energy_high  | sigma68  |       0.34166  |   0.16732  |   0.44569  |  25 |
| run_heldout      | pid_separation      | single_proxy  | linear_proxy      | energy_low   | auc      |       0.99911  |   0.99633  |   1        | 270 |
| run_heldout      | pid_separation      | single_proxy  | linear_proxy      | energy_high  | auc      |       0.995    |   0.9912   |   0.99865  | 253 |
| run_heldout      | pid_separation      | single_proxy  | linear_proxy      | energy_mid   | auc      |       0.99976  |   0.99928  |   1        | 231 |
| run_heldout      | pid_separation      | pileup_proxy  | linear_proxy      | energy_mid   | auc      |       1        |   1        |   1        |  65 |
| run_heldout      | pid_separation      | pileup_proxy  | linear_proxy      | energy_low   | auc      |       1        |   1        |   1        |  44 |
| run_heldout      | pid_separation      | pileup_proxy  | linear_proxy      | energy_high  | auc      |       1        |   1        |   1        |  36 |
| run_heldout      | pid_separation      | single_proxy  | saturation_proxy  | energy_mid   | auc      |       1        |   1        |   1        |  27 |
| run_heldout      | pid_separation      | single_proxy  | saturation_proxy  | energy_high  | auc      |       1        |   1        |   1        |  25 |
| run_heldout      | pileup_sideband     | single_proxy  | linear_proxy      | energy_low   | auc      |     nan        | nan        | nan        | 270 |
| run_heldout      | pileup_sideband     | single_proxy  | linear_proxy      | energy_high  | auc      |     nan        | nan        | nan        | 253 |
| run_heldout      | pileup_sideband     | single_proxy  | linear_proxy      | energy_mid   | auc      |     nan        | nan        | nan        | 231 |
| run_heldout      | pileup_sideband     | pileup_proxy  | linear_proxy      | energy_mid   | auc      |     nan        | nan        | nan        |  65 |
| run_heldout      | pileup_sideband     | pileup_proxy  | linear_proxy      | energy_low   | auc      |     nan        | nan        | nan        |  44 |
| run_heldout      | pileup_sideband     | pileup_proxy  | linear_proxy      | energy_high  | auc      |     nan        | nan        | nan        |  36 |
| run_heldout      | pileup_sideband     | single_proxy  | saturation_proxy  | energy_mid   | auc      |     nan        | nan        | nan        |  27 |
| run_heldout      | pileup_sideband     | single_proxy  | saturation_proxy  | energy_high  | auc      |     nan        | nan        | nan        |  25 |
| run_heldout      | saturation_clipping | single_proxy  | linear_proxy      | energy_low   | auc      |     nan        | nan        | nan        | 270 |
| run_heldout      | saturation_clipping | single_proxy  | linear_proxy      | energy_high  | auc      |     nan        | nan        | nan        | 253 |
| run_heldout      | saturation_clipping | single_proxy  | linear_proxy      | energy_mid   | auc      |     nan        | nan        | nan        | 231 |
| run_heldout      | saturation_clipping | pileup_proxy  | linear_proxy      | energy_mid   | auc      |     nan        | nan        | nan        |  65 |
| run_heldout      | saturation_clipping | pileup_proxy  | linear_proxy      | energy_low   | auc      |     nan        | nan        | nan        |  44 |
| run_heldout      | saturation_clipping | pileup_proxy  | linear_proxy      | energy_high  | auc      |     nan        | nan        | nan        |  36 |
| run_heldout      | saturation_clipping | single_proxy  | saturation_proxy  | energy_mid   | auc      |     nan        | nan        | nan        |  27 |
| run_heldout      | saturation_clipping | single_proxy  | saturation_proxy  | energy_high  | auc      |     nan        | nan        | nan        |  25 |

### Shape/Timing/Pedestal/Pile-Up/Saturation Ablations

Ablation is summarized as the held-out metric span across nuisance strata. For AUC endpoints, a low worst-stratum value marks a failure mode; for energy, a high sigma68 stratum marks the failure mode.

| split_name       | endpoint             | ablation_axis   |   metric_span | worst_stratum    | interpretation                                                              |
|:-----------------|:---------------------|:----------------|--------------:|:-----------------|:----------------------------------------------------------------------------|
| run_heldout      | pedestal_noise_color | tail            |     0.23357   | tail_high        | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | pedestal_noise_color | pedestal        |     0.20881   | pedestal_quiet   | span across matched strata; larger span means stronger nuisance sensitivity |
| particle_heldout | pedestal_noise_color | pedestal        |     0.19272   | pedestal_quiet   | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | pedestal_noise_color | timing_phase    |     0.18378   | timing_core      | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | energy_scale         | pedestal        |     0.17405   | pedestal_quiet   | span across matched strata; larger span means stronger nuisance sensitivity |
| particle_heldout | pedestal_noise_color | shape           |     0.14947   | mid_harmonic     | span across matched strata; larger span means stronger nuisance sensitivity |
| particle_heldout | pedestal_noise_color | pileup          |     0.14844   | single_proxy     | span across matched strata; larger span means stronger nuisance sensitivity |
| particle_heldout | pid_separation       | timing_phase    |     0.12896   | timing_mid       | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | saturation_clipping  | energy          |     0.11453   | energy_low       | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | energy_scale         | saturation      |     0.10908   | saturation_proxy | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | pedestal_noise_color | pileup          |     0.10421   | pileup_proxy     | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | saturation_clipping  | timing_phase    |     0.090561  | timing_tail      | span across matched strata; larger span means stronger nuisance sensitivity |
| particle_heldout | energy_scale         | pedestal        |     0.086715  | pedestal_quiet   | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | energy_scale         | timing_phase    |     0.084663  | timing_core      | span across matched strata; larger span means stronger nuisance sensitivity |
| particle_heldout | pid_separation       | pileup          |     0.077434  | single_proxy     | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | energy_scale         | pileup          |     0.069721  | single_proxy     | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | pedestal_noise_color | energy          |     0.064258  | energy_high      | span across matched strata; larger span means stronger nuisance sensitivity |
| particle_heldout | pedestal_noise_color | timing_phase    |     0.064138  | timing_mid       | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | energy_scale         | tail            |     0.061802  | tail_mid         | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | saturation_clipping  | shape           |     0.057308  | mid_harmonic     | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | saturation_clipping  | tail            |     0.055525  | tail_low         | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | saturation_clipping  | pedestal        |     0.053603  | pedestal_memory  | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | energy_scale         | energy          |     0.049545  | energy_high      | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | pedestal_noise_color | shape           |     0.047763  | high_harmonic    | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | energy_scale         | shape           |     0.043781  | low_harmonic     | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | pedestal_noise_color | saturation      |     0.029464  | linear_proxy     | span across matched strata; larger span means stronger nuisance sensitivity |
| particle_heldout | energy_scale         | shape           |     0.02931   | low_harmonic     | span across matched strata; larger span means stronger nuisance sensitivity |
| particle_heldout | energy_scale         | timing_phase    |     0.024426  | timing_mid       | span across matched strata; larger span means stronger nuisance sensitivity |
| particle_heldout | energy_scale         | pileup          |     0.016203  | single_proxy     | span across matched strata; larger span means stronger nuisance sensitivity |
| particle_heldout | pid_separation       | pedestal        |     0.011148  | pedestal_quiet   | span across matched strata; larger span means stronger nuisance sensitivity |
| particle_heldout | pileup_sideband      | timing_phase    |     0.010108  | timing_mid       | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | saturation_clipping  | pileup          |     0.0093028 | single_proxy     | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | pileup_sideband      | saturation      |     0.0076621 | saturation_proxy | span across matched strata; larger span means stronger nuisance sensitivity |
| particle_heldout | pileup_sideband      | shape           |     0.0074119 | mid_harmonic     | span across matched strata; larger span means stronger nuisance sensitivity |
| particle_heldout | pid_separation       | shape           |     0.0067029 | low_harmonic     | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | pid_separation       | shape           |     0.0059801 | low_harmonic     | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | pid_separation       | timing_phase    |     0.0047709 | timing_tail      | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | pid_separation       | tail            |     0.0045339 | tail_high        | span across matched strata; larger span means stronger nuisance sensitivity |
| particle_heldout | pileup_sideband      | pedestal        |     0.0036169 | pedestal_mid     | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | pid_separation       | energy          |     0.0035551 | energy_high      | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | pid_separation       | pileup          |     0.0029872 | pileup_proxy     | span across matched strata; larger span means stronger nuisance sensitivity |
| run_heldout      | pileup_sideband      | timing_phase    |     0.0019544 | timing_mid       | span across matched strata; larger span means stronger nuisance sensitivity |

### Pedestal Shuffle and PID Calibration

Pedestal labels are shuffled within run blocks with scores fixed. A large observed-minus-shuffle value means the endpoint contains real run-local pedestal information; a small value would indicate that apparent pedestal discrimination is consistent with the run-preserving null.

| split_name       | method                                    |   observed_auc |   shuffled_auc_mean |   shuffled_auc_ci_low |   shuffled_auc_ci_high |   observed_minus_shuffle |   n |
|:-----------------|:------------------------------------------|---------------:|--------------------:|----------------------:|-----------------------:|-------------------------:|----:|
| particle_heldout | spectral_transformer_new                  |        0.63533 |             0.51768 |               0.448   |                0.65074 |               0.11765    | 462 |
| particle_heldout | gradient_boosted_trees                    |        0.61327 |             0.51031 |               0.39247 |                0.60513 |               0.10296    | 462 |
| particle_heldout | ridge                                     |        0.59616 |             0.51047 |               0.39324 |                0.62934 |               0.085683   | 462 |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood |        0.58535 |             0.5095  |               0.41756 |                0.60151 |               0.07585    | 462 |
| particle_heldout | mlp                                       |        0.49771 |             0.49771 |               0.49771 |                0.49771 |              -5.5511e-17 | 462 |
| particle_heldout | 1d_cnn                                    |        0.47506 |             0.47831 |               0.38826 |                0.58908 |              -0.0032494  | 462 |
| run_heldout      | ridge                                     |        0.9149  |             0.50029 |               0.46167 |                0.54839 |               0.41461    | 960 |
| run_heldout      | gradient_boosted_trees                    |        0.93882 |             0.52491 |               0.497   |                0.54784 |               0.41391    | 960 |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood |        0.91142 |             0.50889 |               0.48288 |                0.54486 |               0.40253    | 960 |
| run_heldout      | mlp                                       |        0.84796 |             0.50964 |               0.48233 |                0.54203 |               0.33832    | 960 |
| run_heldout      | spectral_transformer_new                  |        0.71055 |             0.49475 |               0.45861 |                0.53287 |               0.2158     | 960 |
| run_heldout      | 1d_cnn                                    |        0.69552 |             0.48717 |               0.44814 |                0.52162 |               0.20836    | 960 |

Ten-bin reliability curves are saved in `calibration_curves.csv`. The PID excerpt for the winning method is:

| split_name       |   bin |   n |   mean_predicted_probability |   observed_positive_fraction |   abs_calibration_error |
|:-----------------|------:|----:|-----------------------------:|-----------------------------:|------------------------:|
| particle_heldout |     0 | 221 |                     0.050768 |                     0        |                0.050768 |
| particle_heldout |     1 |  32 |                     0.15087  |                     0        |                0.15087  |
| particle_heldout |     2 |  10 |                     0.23188  |                     0.2      |                0.031879 |
| particle_heldout |     3 |   3 |                     0.34481  |                     0        |                0.34481  |
| particle_heldout |     4 |  10 |                     0.46919  |                     0.3      |                0.16919  |
| particle_heldout |     5 |   7 |                     0.53363  |                     0.42857  |                0.10506  |
| particle_heldout |     6 |   5 |                     0.62124  |                     0        |                0.62124  |
| particle_heldout |     7 |   7 |                     0.75484  |                     0.28571  |                0.46912  |
| particle_heldout |     8 |  22 |                     0.87522  |                     0.31818  |                0.55704  |
| particle_heldout |     9 | 145 |                     0.94014  |                     0.56552  |                0.37463  |
| run_heldout      |     0 | 338 |                     0.047299 |                     0        |                0.047299 |
| run_heldout      |     1 |  30 |                     0.14586  |                     0.033333 |                0.11252  |
| run_heldout      |     2 |  15 |                     0.25773  |                     0.13333  |                0.1244   |
| run_heldout      |     3 |  10 |                     0.35963  |                     0.1      |                0.25963  |
| run_heldout      |     4 |  15 |                     0.43657  |                     0.53333  |                0.096767 |
| run_heldout      |     5 |  10 |                     0.54385  |                     0.5      |                0.043852 |
| run_heldout      |     6 |   6 |                     0.63314  |                     0.83333  |                0.20019  |
| run_heldout      |     7 |  13 |                     0.77033  |                     0.92308  |                0.15274  |
| run_heldout      |     8 |  26 |                     0.8568   |                     1        |                0.1432   |
| run_heldout      |     9 | 497 |                     0.96082  |                     0.99799  |                0.037171 |

### S61c Verdict

The winner is `gradient_boosted_trees` under the pre-registered mean joint loss. The main caveat is also the main scientific result: pedestal, pile-up, saturation, and timing-phase covariates carry enough information to help proxy energy/PID endpoints, but they are strong enough to be leakage paths without external truth. The traditional baseline remains interpretable and competitive on energy residuals; the learned winner gains by capturing nonlinear interactions among duplicate-readout response, late-tail charge, harmonic content, and pedestal state.

## Caveats

- PID, pile-up, saturation, and pedestal labels are deterministic raw-waveform proxies, not external truth labels.
- The particle-held-out split uses proxy particle families because species truth is absent from the reduced HRD ROOT branch.
- Run-block bootstrap covers observed run-to-run variation but cannot cover beam settings not present in runs 31-65.
- High AUC values can reflect proximity between feature definitions and proxy labels; the leakage table is therefore part of the result, not a cosmetic diagnostic.
- The winner is valid for this registered proxy benchmark; physics promotion requires external PID/energy truth or digitized GEANT4 closure.

## Verdict

`result.json` names **gradient_boosted_trees** as the winner because it minimizes mean registered joint loss across the run-held-out and proxy particle-held-out splits. The scientifically useful conclusion is that tail and pedestal memory terms are necessary diagnostics: they improve uncertainty accounting, but they also expose where proxy labels can leak cross-task information.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/ticket_2560_s61c_energy_pid_pedestal_pileup_disentanglement.py
```

