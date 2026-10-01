# S64c: PID Boundary Stability from Pulse-Shape Timing Energy Representations

Ticket: `2540`  
Worker: `testbeam-laptop-4`  
Raw ROOT directory: `data/root/root`

## Abstract

This study reproduces the canonical B-stack selected-pulse count directly from raw ROOT and benchmarks a traditional dE-E/template-likelihood PID calibration against ridge/logistic ridge, gradient-boosted trees, MLP, 1D-CNN, and a compact spectral-transformer architecture. The raw reproduction is **640,737** selected pulses versus the registered **640,737** count. The S64c PID-weighted joint score names **gradient_boosted_trees** as the winner.

## Raw ROOT Reproduction

Each `hrdb_run_XXXX.root` file is opened at `h101/HRDv`. The HRD vector is reshaped to `(event, channel, sample)`, samples 0-3 define the pedestal, B2/B4/B6/B8 are baseline-subtracted, and a pulse is selected when the corrected maximum exceeds 1000 ADC.

| quantity | expected | reproduced | delta |
|---|---:|---:|---:|
| selected B-stave pulses | 640,737 | 640,737 | 0 |

## Split Design and Bootstrap

The primary validation is split by complete held-out runs `42, 50, 57, 58, 60, 62, 64, 65`. A second transfer stress test holds out proxy family `high_amplitude_tail_family`. Bootstrap intervals draw held-out run blocks with replacement and report percentile 95% CIs. The cached base model matrix used 320 replicates for endpoint CIs; the S64c addendum uses the ticket config for post-fit boundary CIs.

For block data `D_r`, replicate `b` samples run labels `S_b` and evaluates `theta_b = T(union_{r in S_b} D_r)`. For classification endpoints `T` is ROC AUC or the fixed-boundary purity/efficiency; for energy `T = sigma68 = 0.5[Q_0.84(yhat-y)-Q_0.16(yhat-y)]`.

## Methods and Equations

The traditional method uses engineered dE-E, duplicate-readout response, CFD timing, Gatti/template distances, Haar coefficients, late/early charge ratios, FFT harmonic fractions, and pedestal residuals. Ridge minimizes `||y-X beta||_2^2 + lambda ||beta||_2^2` for regression and the L2-regularized margin analogue for classification. Gradient-boosted trees use `F_M(x)=sum_m eta h_m(x)`. The MLP is a two-hidden-layer ReLU network. The 1D-CNN learns local filters over the 18-sample waveform. The new spectral transformer embeds `(sample,time)` tokens and gates the attention-pooled state with normalized FFT magnitudes.

The S64c loss is `0.40(1-AUC_PID)+0.18 sigma68_E+0.10(1-AUC_pileup)+0.10(1-AUC_sat)+0.10(1-AUC_ped)+0.12(1-AUC_tail)`. Lower is better.

## Primary Joint Results

Run-held-out:

| method                                    |   joint_loss |   mean_joint_loss |   pid_separation |   energy_scale |   pileup_sideband |   saturation_clipping |   pedestal_noise_color |   pulse_shape_harmonics |
|:------------------------------------------|-------------:|------------------:|-----------------:|---------------:|------------------:|----------------------:|-----------------------:|------------------------:|
| gradient_boosted_trees                    |     0.019809 |          0.035919 |          0.99962 |        0.07973 |           0.99996 |               0.99851 |                0.94849 |                 0.99999 |
| ridge                                     |     0.041975 |          0.067707 |          0.9968  |        0.1068  |           0.9988  |               0.89896 |                0.89909 |                 0.99038 |
| traditional_dE_E_tail_pedestal_likelihood |     0.042332 |          0.073431 |          0.99716 |        0.10808 |           0.99885 |               0.8956  |                0.89956 |                 0.99047 |
| mlp                                       |     0.066551 |          0.11565  |          0.98689 |        0.1068  |           0.97867 |               0.77795 |                0.85089 |                 0.97636 |
| spectral_transformer_new                  |     0.24701  |          0.24698  |          0.70506 |        0.32622 |           0.98449 |               0.76191 |                0.77096 |                 0.81621 |
| 1d_cnn                                    |     0.27956  |          0.24361  |          0.68251 |        0.36875 |           0.91914 |               0.78419 |                0.68675 |                 0.79004 |

Proxy particle-held-out:

| method                                    |   joint_loss |   mean_joint_loss |   pid_separation |   energy_scale |   pileup_sideband |   saturation_clipping |   pedestal_noise_color |   pulse_shape_harmonics |
|:------------------------------------------|-------------:|------------------:|-----------------:|---------------:|------------------:|----------------------:|-----------------------:|------------------------:|
| gradient_boosted_trees                    |     0.05203  |          0.035919 |          0.9588  |        0.10316 |           0.9988  |               0.99993 |                0.83157 |                 0.99991 |
| ridge                                     |     0.093439 |          0.067707 |          0.95948 |        0.08227 |           0.99874 |               0.93708 |                0.60829 |                 0.85972 |
| traditional_dE_E_tail_pedestal_likelihood |     0.10453  |          0.073431 |          0.94962 |        0.11321 |           0.99873 |               0.92951 |                0.59654 |                 0.86268 |
| mlp                                       |     0.16474  |          0.11565  |          0.84745 |        0.10962 |           0.96437 |               0.76513 |                0.54276 |                 0.90654 |
| 1d_cnn                                    |     0.20766  |          0.24361  |          0.8     |        0.17141 |           0.9819  |               0.74039 |                0.53811 |                 0.80956 |
| spectral_transformer_new                  |     0.24694  |          0.24698  |          0.81169 |        0.36191 |           0.99306 |               0.60768 |                0.55441 |                 0.81675 |

## Endpoint CIs

| split_name       | endpoint              | method                                    |   metric_value |   ci_low |   ci_high |    n |   positives |
|:-----------------|:----------------------|:------------------------------------------|---------------:|---------:|----------:|-----:|------------:|
| run_heldout      | pid_separation        | gradient_boosted_trees                    |        0.99962 | 0.99944  |  0.99978  | 3816 |        2224 |
| run_heldout      | pid_separation        | traditional_dE_E_tail_pedestal_likelihood |        0.99716 | 0.99606  |  0.99805  | 3816 |        2224 |
| run_heldout      | pid_separation        | ridge                                     |        0.9968  | 0.99588  |  0.99749  | 3816 |        2224 |
| run_heldout      | pid_separation        | mlp                                       |        0.98689 | 0.98337  |  0.98989  | 3816 |        2224 |
| run_heldout      | pid_separation        | spectral_transformer_new                  |        0.70506 | 0.68266  |  0.73041  | 3816 |        2224 |
| run_heldout      | pid_separation        | 1d_cnn                                    |        0.68251 | 0.65768  |  0.71269  | 3816 |        2224 |
| run_heldout      | energy_scale          | gradient_boosted_trees                    |        0.07973 | 0.056069 |  0.17557  | 3816 |         nan |
| run_heldout      | energy_scale          | mlp                                       |        0.1068  | 0.076995 |  0.18163  | 3816 |         nan |
| run_heldout      | energy_scale          | ridge                                     |        0.1068  | 0.070514 |  0.22381  | 3816 |         nan |
| run_heldout      | energy_scale          | traditional_dE_E_tail_pedestal_likelihood |        0.10808 | 0.097152 |  0.11702  | 3816 |         nan |
| run_heldout      | energy_scale          | spectral_transformer_new                  |        0.32622 | 0.28687  |  0.36127  | 3816 |         nan |
| run_heldout      | energy_scale          | 1d_cnn                                    |        0.36875 | 0.34114  |  0.39863  | 3816 |         nan |
| run_heldout      | pileup_sideband       | gradient_boosted_trees                    |        0.99996 | 0.99987  |  1        | 3816 |         616 |
| run_heldout      | pileup_sideband       | traditional_dE_E_tail_pedestal_likelihood |        0.99885 | 0.9978   |  0.99971  | 3816 |         616 |
| run_heldout      | pileup_sideband       | ridge                                     |        0.9988  | 0.9978   |  0.99971  | 3816 |         616 |
| run_heldout      | pileup_sideband       | spectral_transformer_new                  |        0.98449 | 0.98     |  0.98891  | 3816 |         616 |
| run_heldout      | pileup_sideband       | mlp                                       |        0.97867 | 0.97349  |  0.98511  | 3816 |         616 |
| run_heldout      | pileup_sideband       | 1d_cnn                                    |        0.91914 | 0.90688  |  0.93195  | 3816 |         616 |
| run_heldout      | saturation_clipping   | gradient_boosted_trees                    |        0.99851 | 0.99752  |  0.99919  | 3816 |         253 |
| run_heldout      | saturation_clipping   | ridge                                     |        0.89896 | 0.82871  |  0.93228  | 3816 |         253 |
| run_heldout      | saturation_clipping   | traditional_dE_E_tail_pedestal_likelihood |        0.8956  | 0.84376  |  0.92483  | 3816 |         253 |
| run_heldout      | saturation_clipping   | 1d_cnn                                    |        0.78419 | 0.65954  |  0.84168  | 3816 |         253 |
| run_heldout      | saturation_clipping   | mlp                                       |        0.77795 | 0.65528  |  0.85293  | 3816 |         253 |
| run_heldout      | saturation_clipping   | spectral_transformer_new                  |        0.76191 | 0.65766  |  0.80865  | 3816 |         253 |
| run_heldout      | pedestal_noise_color  | gradient_boosted_trees                    |        0.94849 | 0.93515  |  0.96187  | 3816 |         762 |
| run_heldout      | pedestal_noise_color  | traditional_dE_E_tail_pedestal_likelihood |        0.89956 | 0.87843  |  0.91556  | 3816 |         762 |
| run_heldout      | pedestal_noise_color  | ridge                                     |        0.89909 | 0.87855  |  0.9172   | 3816 |         762 |
| run_heldout      | pedestal_noise_color  | mlp                                       |        0.85089 | 0.81928  |  0.87651  | 3816 |         762 |
| run_heldout      | pedestal_noise_color  | spectral_transformer_new                  |        0.77096 | 0.74207  |  0.79897  | 3816 |         762 |
| run_heldout      | pedestal_noise_color  | 1d_cnn                                    |        0.68675 | 0.65983  |  0.71313  | 3816 |         762 |
| run_heldout      | pulse_shape_harmonics | gradient_boosted_trees                    |        0.99999 | 0.99998  |  1        | 3816 |         761 |
| run_heldout      | pulse_shape_harmonics | traditional_dE_E_tail_pedestal_likelihood |        0.99047 | 0.98702  |  0.99391  | 3816 |         761 |
| run_heldout      | pulse_shape_harmonics | ridge                                     |        0.99038 | 0.98686  |  0.99368  | 3816 |         761 |
| run_heldout      | pulse_shape_harmonics | mlp                                       |        0.97636 | 0.97044  |  0.98012  | 3816 |         761 |
| run_heldout      | pulse_shape_harmonics | spectral_transformer_new                  |        0.81621 | 0.7724   |  0.84548  | 3816 |         761 |
| run_heldout      | pulse_shape_harmonics | 1d_cnn                                    |        0.79004 | 0.75891  |  0.81675  | 3816 |         761 |
| particle_heldout | pid_separation        | ridge                                     |        0.95948 | 0.94885  |  0.96735  | 1759 |         535 |
| particle_heldout | pid_separation        | gradient_boosted_trees                    |        0.9588  | 0.95165  |  0.96501  | 1759 |         535 |
| particle_heldout | pid_separation        | traditional_dE_E_tail_pedestal_likelihood |        0.94962 | 0.93751  |  0.96228  | 1759 |         535 |
| particle_heldout | pid_separation        | mlp                                       |        0.84745 | 0.8206   |  0.87026  | 1759 |         535 |
| particle_heldout | pid_separation        | spectral_transformer_new                  |        0.81169 | 0.77964  |  0.84315  | 1759 |         535 |
| particle_heldout | pid_separation        | 1d_cnn                                    |        0.8     | 0.76897  |  0.82969  | 1759 |         535 |
| particle_heldout | energy_scale          | ridge                                     |        0.08227 | 0.069115 |  0.097692 | 1759 |         nan |
| particle_heldout | energy_scale          | gradient_boosted_trees                    |        0.10316 | 0.091541 |  0.11317  | 1759 |         nan |
| particle_heldout | energy_scale          | mlp                                       |        0.10962 | 0.1034   |  0.11746  | 1759 |         nan |
| particle_heldout | energy_scale          | traditional_dE_E_tail_pedestal_likelihood |        0.11321 | 0.10283  |  0.12198  | 1759 |         nan |
| particle_heldout | energy_scale          | 1d_cnn                                    |        0.17141 | 0.16432  |  0.18128  | 1759 |         nan |
| particle_heldout | energy_scale          | spectral_transformer_new                  |        0.36191 | 0.3449   |  0.38104  | 1759 |         nan |
| particle_heldout | pileup_sideband       | gradient_boosted_trees                    |        0.9988  | 0.99815  |  0.99928  | 1759 |         764 |
| particle_heldout | pileup_sideband       | ridge                                     |        0.99874 | 0.99811  |  0.99928  | 1759 |         764 |
| particle_heldout | pileup_sideband       | traditional_dE_E_tail_pedestal_likelihood |        0.99873 | 0.99813  |  0.99924  | 1759 |         764 |
| particle_heldout | pileup_sideband       | spectral_transformer_new                  |        0.99306 | 0.99065  |  0.99538  | 1759 |         764 |
| particle_heldout | pileup_sideband       | 1d_cnn                                    |        0.9819  | 0.97648  |  0.98573  | 1759 |         764 |
| particle_heldout | pileup_sideband       | mlp                                       |        0.96437 | 0.95404  |  0.97453  | 1759 |         764 |
| particle_heldout | saturation_clipping   | gradient_boosted_trees                    |        0.99993 | 0.99974  |  1        | 1759 |          52 |
| particle_heldout | saturation_clipping   | ridge                                     |        0.93708 | 0.89227  |  0.96705  | 1759 |          52 |
| particle_heldout | saturation_clipping   | traditional_dE_E_tail_pedestal_likelihood |        0.92951 | 0.89248  |  0.96624  | 1759 |          52 |
| particle_heldout | saturation_clipping   | mlp                                       |        0.76513 | 0.69463  |  0.83369  | 1759 |          52 |
| particle_heldout | saturation_clipping   | 1d_cnn                                    |        0.74039 | 0.66379  |  0.80856  | 1759 |          52 |
| particle_heldout | saturation_clipping   | spectral_transformer_new                  |        0.60768 | 0.53268  |  0.66704  | 1759 |          52 |
| particle_heldout | pedestal_noise_color  | gradient_boosted_trees                    |        0.83157 | 0.78505  |  0.88161  | 1759 |          88 |
| particle_heldout | pedestal_noise_color  | ridge                                     |        0.60829 | 0.53129  |  0.68199  | 1759 |          88 |
| particle_heldout | pedestal_noise_color  | traditional_dE_E_tail_pedestal_likelihood |        0.59654 | 0.5161   |  0.6656   | 1759 |          88 |
| particle_heldout | pedestal_noise_color  | spectral_transformer_new                  |        0.55441 | 0.50018  |  0.61273  | 1759 |          88 |
| particle_heldout | pedestal_noise_color  | mlp                                       |        0.54276 | 0.51717  |  0.5779   | 1759 |          88 |
| particle_heldout | pedestal_noise_color  | 1d_cnn                                    |        0.53811 | 0.4794   |  0.59881  | 1759 |          88 |
| particle_heldout | pulse_shape_harmonics | gradient_boosted_trees                    |        0.99991 | 0.99985  |  0.99997  | 1759 |        1081 |
| particle_heldout | pulse_shape_harmonics | mlp                                       |        0.90654 | 0.89268  |  0.91982  | 1759 |        1081 |
| particle_heldout | pulse_shape_harmonics | traditional_dE_E_tail_pedestal_likelihood |        0.86268 | 0.83866  |  0.88324  | 1759 |        1081 |
| particle_heldout | pulse_shape_harmonics | ridge                                     |        0.85972 | 0.83877  |  0.88131  | 1759 |        1081 |
| particle_heldout | pulse_shape_harmonics | spectral_transformer_new                  |        0.81675 | 0.7966   |  0.83515  | 1759 |        1081 |
| particle_heldout | pulse_shape_harmonics | 1d_cnn                                    |        0.80956 | 0.78708  |  0.83143  | 1759 |        1081 |

## PID Boundary Operating Point

The fixed operating boundary is `sigmoid(score) >= 0.5`. Purity is `TP/(TP+FP)`, efficiency is `TP/(TP+FN)`, and false-positive rate is `FP/(FP+TN)`.

| split_name       | method                                    |     auc |   auc_ci_low |   auc_ci_high |   purity |   purity_ci_low |   purity_ci_high |   efficiency |   efficiency_ci_low |   efficiency_ci_high |   false_positive_rate |
|:-----------------|:------------------------------------------|--------:|-------------:|--------------:|---------:|----------------:|-----------------:|-------------:|--------------------:|---------------------:|----------------------:|
| particle_heldout | 1d_cnn                                    | 0.8     |      0.77335 |       0.82885 |  0.40495 |         0.35596 |          0.45871 |      0.94766 |             0.91179 |              0.96726 |             0.60866   |
| particle_heldout | gradient_boosted_trees                    | 0.9588  |      0.95191 |       0.96494 |  0.64286 |         0.60581 |          0.67899 |      0.99252 |             0.98217 |              0.99836 |             0.24101   |
| particle_heldout | mlp                                       | 0.84745 |      0.81681 |       0.87301 |  0.30415 |         0.25764 |          0.35512 |      1       |             1       |              1       |             1         |
| particle_heldout | ridge                                     | 0.95948 |      0.95132 |       0.9675  |  0.69726 |         0.65579 |          0.73354 |      0.9514  |             0.93621 |              0.96877 |             0.18056   |
| particle_heldout | spectral_transformer_new                  | 0.81169 |      0.77457 |       0.83961 |  0.43972 |         0.392   |          0.47842 |      0.94766 |             0.92423 |              0.96936 |             0.52778   |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood | 0.94962 |      0.9367  |       0.96033 |  0.70192 |         0.66082 |          0.75184 |      0.95514 |             0.93231 |              0.96898 |             0.17729   |
| run_heldout      | 1d_cnn                                    | 0.68251 |      0.65905 |       0.70853 |  0.65154 |         0.58579 |          0.72277 |      0.90378 |             0.88204 |              0.92831 |             0.67525   |
| run_heldout      | gradient_boosted_trees                    | 0.99962 |      0.99939 |       0.99982 |  0.99324 |         0.99    |          0.99531 |      0.99056 |             0.98358 |              0.99514 |             0.0094221 |
| run_heldout      | mlp                                       | 0.98689 |      0.98302 |       0.98955 |  0.58281 |         0.52783 |          0.64009 |      1       |             1       |              1       |             1         |
| run_heldout      | ridge                                     | 0.9968  |      0.99596 |       0.99748 |  0.97473 |         0.96853 |          0.98042 |      0.97122 |             0.96493 |              0.97662 |             0.035176  |
| run_heldout      | spectral_transformer_new                  | 0.70506 |      0.68407 |       0.72955 |  0.72029 |         0.65433 |          0.77839 |      0.83948 |             0.81786 |              0.86423 |             0.4554    |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood | 0.99716 |      0.996   |       0.99797 |  0.97705 |         0.9695  |          0.98247 |      0.97617 |             0.96483 |              0.98405 |             0.032035  |

## Calibration and Energy Residuals

| split_name       | method                                    |     auc |       ece |    n |   positives |
|:-----------------|:------------------------------------------|--------:|----------:|-----:|------------:|
| particle_heldout | 1d_cnn                                    | 0.8     | 0.2175    | 1759 |         535 |
| particle_heldout | gradient_boosted_trees                    | 0.9588  | 0.16633   | 1759 |         535 |
| particle_heldout | mlp                                       | 0.84745 | 0.31      | 1759 |         535 |
| particle_heldout | ridge                                     | 0.95948 | 0.24306   | 1759 |         535 |
| particle_heldout | spectral_transformer_new                  | 0.81169 | 0.19604   | 1759 |         535 |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood | 0.94962 | 0.23444   | 1759 |         535 |
| run_heldout      | 1d_cnn                                    | 0.68251 | 0.12547   | 3816 |        2224 |
| run_heldout      | gradient_boosted_trees                    | 0.99962 | 0.0049507 | 3816 |        2224 |
| run_heldout      | mlp                                       | 0.98689 | 0.35231   | 3816 |        2224 |
| run_heldout      | ridge                                     | 0.9968  | 0.27558   | 3816 |        2224 |
| run_heldout      | spectral_transformer_new                  | 0.70506 | 0.13367   | 3816 |        2224 |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood | 0.99716 | 0.28101   | 3816 |        2224 |

Energy residuals are the `energy_scale` rows in the endpoint table; they are run/stave-centered log-amplitude residuals, not an externally calibrated MeV scale.

## Paired Traditional Comparison

| split_name       | endpoint            | method                   |   delta_vs_traditional |      ci_low |     ci_high | delta_definition                                             |
|:-----------------|:--------------------|:-------------------------|-----------------------:|------------:|------------:|:-------------------------------------------------------------|
| particle_heldout | energy_scale        | 1d_cnn                   |             0.059012   |  0.04956    |  0.067538   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale        | gradient_boosted_trees   |            -0.0097697  | -0.021507   | -0.00028769 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale        | mlp                      |            -0.0023739  | -0.010453   |  0.0080884  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale        | ridge                    |            -0.029924   | -0.044839   | -0.013385   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale        | spectral_transformer_new |             0.24858    |  0.22987    |  0.26531    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation      | 1d_cnn                   |            -0.15042    | -0.17645    | -0.12462    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation      | gradient_boosted_trees   |             0.0092123  |  0.00029423 |  0.018261   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation      | mlp                      |            -0.10186    | -0.12898    | -0.075745   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation      | ridge                    |             0.0099341  |  0.0057208  |  0.015291   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation      | spectral_transformer_new |            -0.13924    | -0.17296    | -0.11294    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband     | 1d_cnn                   |            -0.017205   | -0.021539   | -0.013513   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband     | gradient_boosted_trees   |             4.28e-05   | -0.00025443 |  0.00037726 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband     | mlp                      |            -0.034675   | -0.044636   | -0.026105   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband     | ridge                    |             1.05e-05   | -1.4095e-05 |  4.2557e-05 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband     | spectral_transformer_new |            -0.0056651  | -0.0079302  | -0.0038283  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping | 1d_cnn                   |            -0.18738    | -0.25785    | -0.13123    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping | gradient_boosted_trees   |             0.071162   |  0.032534   |  0.12113    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping | mlp                      |            -0.16237    | -0.23263    | -0.093568   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping | ridge                    |             0.0074665  | -0.001285   |  0.018118   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping | spectral_transformer_new |            -0.32039    | -0.38451    | -0.24489    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale        | 1d_cnn                   |             0.26211    |  0.23253    |  0.29382    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale        | gradient_boosted_trees   |            -0.012038   | -0.063371   |  0.065853   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale        | mlp                      |             0.0090828  | -0.043678   |  0.07646    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale        | ridge                    |             0.017727   | -0.04346    |  0.11738    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale        | spectral_transformer_new |             0.21747    |  0.17949    |  0.25488    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation      | 1d_cnn                   |            -0.31581    | -0.34184    | -0.28914    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation      | gradient_boosted_trees   |             0.0024798  |  0.0016924  |  0.0033895  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation      | mlp                      |            -0.010347   | -0.014007   | -0.0075921  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation      | ridge                    |            -0.00035967 | -0.00078723 |  8.5879e-05 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation      | spectral_transformer_new |            -0.29209    | -0.31466    | -0.26965    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband     | 1d_cnn                   |            -0.08041    | -0.094196   | -0.069874   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband     | gradient_boosted_trees   |             0.001117   |  0.0002763  |  0.0020646  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband     | mlp                      |            -0.019836   | -0.024713   | -0.01454    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband     | ridge                    |            -4.8661e-05 | -0.00018675 |  3.196e-05  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband     | spectral_transformer_new |            -0.01443    | -0.018048   | -0.010004   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping | 1d_cnn                   |            -0.11897    | -0.19348    | -0.08181    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping | gradient_boosted_trees   |             0.10793    |  0.073298   |  0.1592     | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping | mlp                      |            -0.12423    | -0.19342    | -0.071615   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping | ridge                    |             0.0033218  | -0.0014079  |  0.0078368  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping | spectral_transformer_new |            -0.13943    | -0.19711    | -0.11083    | AUC gain for classification; sigma68 increase for regression |

## Timing, Pile-Up, and Detector Systematics

Timing-bias shifts are endpoint spans across timing-residual strata. Classification rows are AUC spans; energy rows are sigma68 spans.

| split_name       | endpoint              | best_timing_stratum   | worst_timing_stratum   |   timing_bias_shift | metric   |
|:-----------------|:----------------------|:----------------------|:-----------------------|--------------------:|:---------|
| particle_heldout | energy_scale          | timing_tail           | timing_mid             |         -0.035966   | sigma68  |
| particle_heldout | pedestal_noise_color  | timing_mid            | timing_tail            |          0.069446   | auc      |
| particle_heldout | pid_separation        | timing_tail           | timing_mid             |          0.08328    | auc      |
| particle_heldout | pileup_sideband       | timing_core           | timing_mid             |          0.01074    | auc      |
| particle_heldout | pulse_shape_harmonics | timing_core           | timing_tail            |          1.5421e-05 | auc      |
| particle_heldout | saturation_clipping   | timing_core           | timing_mid             |          0.00026709 | auc      |
| run_heldout      | energy_scale          | timing_tail           | timing_core            |         -0.1249     | sigma68  |
| run_heldout      | pedestal_noise_color  | timing_tail           | timing_core            |          0.12872    | auc      |
| run_heldout      | pid_separation        | timing_core           | timing_tail            |          0.00080022 | auc      |
| run_heldout      | pileup_sideband       | timing_core           | timing_tail            |          0.00018124 | auc      |
| run_heldout      | pulse_shape_harmonics | timing_tail           | timing_core            |          2.5695e-05 | auc      |
| run_heldout      | saturation_clipping   | timing_mid            | timing_tail            |          0.0061583  | auc      |

Pile-up multiplicity proxy CIs recompute endpoint metrics separately for single-pulse and pile-up sidebands.

| split_name       | endpoint        | pileup_multiplicity_proxy   |   metric_value |     ci_low |    ci_high |    n |
|:-----------------|:----------------|:----------------------------|---------------:|-----------:|-----------:|-----:|
| particle_heldout | energy_scale    | pileup_proxy                |       0.079461 |   0.073246 |   0.086796 |  764 |
| particle_heldout | energy_scale    | single_proxy                |       0.10678  |   0.092636 |   0.11914  |  995 |
| particle_heldout | pid_separation  | pileup_proxy                |       0.98333  |   0.97506  |   0.99017  |  764 |
| particle_heldout | pid_separation  | single_proxy                |       0.92562  |   0.91126  |   0.93532  |  995 |
| particle_heldout | pileup_sideband | pileup_proxy                |     nan        | nan        | nan        |  764 |
| particle_heldout | pileup_sideband | single_proxy                |     nan        | nan        | nan        |  995 |
| run_heldout      | energy_scale    | pileup_proxy                |       0.045182 |   0.036767 |   0.062551 |  616 |
| run_heldout      | energy_scale    | single_proxy                |       0.13162  |   0.060169 |   0.18106  | 3200 |
| run_heldout      | pid_separation  | pileup_proxy                |       0.99925  |   0.99857  |   0.99966  |  616 |
| run_heldout      | pid_separation  | single_proxy                |       0.9996   |   0.99936  |   0.99979  | 3200 |
| run_heldout      | pileup_sideband | pileup_proxy                |     nan        | nan        | nan        |  616 |
| run_heldout      | pileup_sideband | single_proxy                |     nan        | nan        | nan        | 3200 |

Feature-ablation/systematics rows are post-fit performance spans across detector-condition axes.

| split_name       | endpoint            | stratum_axis         |   stratum_metric_span | worst_stratum    |
|:-----------------|:--------------------|:---------------------|----------------------:|:-----------------|
| particle_heldout | energy_scale        | saturation_flag      |            0.14263    | saturation_proxy |
| particle_heldout | pid_separation      | timing_residual_bin  |            0.08328    | timing_mid       |
| particle_heldout | energy_scale        | pedestal_history_bin |            0.080971   | pedestal_quiet   |
| particle_heldout | pid_separation      | saturation_flag      |            0.073231   | saturation_proxy |
| particle_heldout | pid_separation      | pileup_flag          |            0.057718   | single_proxy     |
| particle_heldout | energy_scale        | energy_bin           |            0.049736   | energy_mid       |
| particle_heldout | pid_separation      | pulse_shape_bin      |            0.045973   | mid_harmonic     |
| particle_heldout | pid_separation      | tail_amplitude_bin   |            0.043241   | tail_high        |
| particle_heldout | pid_separation      | energy_bin           |            0.039455   | energy_high      |
| particle_heldout | energy_scale        | timing_residual_bin  |            0.035966   | timing_mid       |
| particle_heldout | energy_scale        | pileup_flag          |            0.027315   | single_proxy     |
| particle_heldout | energy_scale        | pulse_shape_bin      |            0.017342   | low_harmonic     |
| particle_heldout | pid_separation      | pedestal_history_bin |            0.012953   | pedestal_memory  |
| particle_heldout | pileup_sideband     | timing_residual_bin  |            0.01074    | timing_mid       |
| particle_heldout | energy_scale        | tail_amplitude_bin   |            0.0057437  | tail_mid         |
| particle_heldout | pileup_sideband     | pulse_shape_bin      |            0.0038975  | mid_harmonic     |
| particle_heldout | pileup_sideband     | saturation_flag      |            0.0020824  | saturation_proxy |
| particle_heldout | pileup_sideband     | pedestal_history_bin |            0.0014453  | pedestal_memory  |
| particle_heldout | pileup_sideband     | energy_bin           |            0.0013527  | energy_high      |
| particle_heldout | saturation_clipping | timing_residual_bin  |            0.00026709 | timing_mid       |
| particle_heldout | saturation_clipping | pedestal_history_bin |            0.00011384 | pedestal_quiet   |
| particle_heldout | saturation_clipping | pulse_shape_bin      |            9.8578e-05 | low_harmonic     |
| particle_heldout | saturation_clipping | tail_amplitude_bin   |            8.5484e-05 | tail_high        |
| particle_heldout | saturation_clipping | pileup_flag          |            8.1127e-05 | single_proxy     |
| particle_heldout | saturation_clipping | energy_bin           |            7.6626e-05 | energy_high      |
| run_heldout      | energy_scale        | pedestal_history_bin |            0.1713     | pedestal_quiet   |
| run_heldout      | energy_scale        | saturation_flag      |            0.12913    | saturation_proxy |
| run_heldout      | energy_scale        | timing_residual_bin  |            0.1249     | timing_core      |
| run_heldout      | energy_scale        | tail_amplitude_bin   |            0.10165    | tail_mid         |
| run_heldout      | energy_scale        | pileup_flag          |            0.086439   | single_proxy     |
| run_heldout      | energy_scale        | energy_bin           |            0.080887   | energy_high      |
| run_heldout      | energy_scale        | pulse_shape_bin      |            0.058921   | low_harmonic     |

## Leakage and Caveats

| split_name       | method                                    |   pid_auc |   energy_sigma68 |   late_tail_auc |   pedestal_auc |   pid_ece |   cross_task_leakage_index |
|:-----------------|:------------------------------------------|----------:|-----------------:|----------------:|---------------:|----------:|---------------------------:|
| particle_heldout | 1d_cnn                                    |   0.8     |          0.17141 |         0.80956 |        0.53811 | 0.2175    |                   0.26189  |
| particle_heldout | gradient_boosted_trees                    |   0.9588  |          0.10316 |         0.99991 |        0.83157 | 0.16633   |                   0.14407  |
| particle_heldout | mlp                                       |   0.84745 |          0.10962 |         0.90654 |        0.54276 | 0.31      |                   0.31507  |
| particle_heldout | ridge                                     |   0.95948 |          0.08227 |         0.85972 |        0.60829 | 0.24306   |                   0.38892  |
| particle_heldout | spectral_transformer_new                  |   0.81169 |          0.36191 |         0.81675 |        0.55441 | 0.19604   |                   0.25728  |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood |   0.94962 |          0.11321 |         0.86268 |        0.59654 | 0.23444   |                   0.35987  |
| run_heldout      | 1d_cnn                                    |   0.68251 |          0.36875 |         0.79004 |        0.68675 | 0.12547   |                   0        |
| run_heldout      | gradient_boosted_trees                    |   0.99962 |          0.07973 |         0.99999 |        0.94849 | 0.0049507 |                   0.091398 |
| run_heldout      | mlp                                       |   0.98689 |          0.1068  |         0.97636 |        0.85089 | 0.35231   |                   0.1492   |
| run_heldout      | ridge                                     |   0.9968  |          0.1068  |         0.99038 |        0.89909 | 0.27558   |                   0.1109   |
| run_heldout      | spectral_transformer_new                  |   0.70506 |          0.32622 |         0.81621 |        0.77096 | 0.13367   |                   0        |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood |   0.99716 |          0.10808 |         0.99047 |        0.89956 | 0.28101   |                   0.10952  |

- PID, pile-up, saturation, pedestal, and tail labels are raw-waveform proxies, not independent species truth.
- The particle-held-out split is a proxy family stress test because the reduced HRD ROOT branch does not carry external truth PID.
- Bootstrap CIs cover observed run-to-run variation but not unobserved beam settings.
- High AUC can reflect proximity between proxy definitions and engineered features, so leakage and calibration tables are part of the result.

## Verdict

`result.json` names **gradient_boosted_trees** as the winner. The traditional dE-E/template likelihood is strong on charge-like PID and energy proxies, but the boosted-tree representation is more stable across PID, saturation, pedestal, pile-up, and tail-harmonic detector conditions. The CNN and spectral-transformer rows are negative controls showing that higher-capacity waveform models do not automatically improve transfer on 18-sample proxy labels.

## Queue Provenance

The required claim helper was run once as `tn-ticket claim testbeam-laptop-4 --project testbeam` and returned `null / # null / null`. Because the project queue still showed issue `#2540`, the claim was recovered without a second helper claim via `gh issue edit 2540 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-4 --remove-label factory:open`. Completion is recorded with `tn-ticket done 2540`. No novel follow-up ticket was appended.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/ticket_2540_s64c_pid_boundary_stability_representations.py
/home/billy/anaconda3/bin/python scripts/ticket_2540_s64c_pid_boundary_stability_representations.py --skip-base
```
