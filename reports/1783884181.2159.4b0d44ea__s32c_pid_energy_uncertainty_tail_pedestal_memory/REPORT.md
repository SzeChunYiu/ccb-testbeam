# S32c: PID-Energy Uncertainty from Pulse Tails and Pedestal Memory

Ticket: `1783884181.2159.4b0d44ea`  
Worker: `testbeam-laptop-2`  
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
| gradient_boosted_trees                    |     0.028003 |          0.039583 |          0.99958 |       0.087805 |           0.99995 |               0.99729 |                0.94569 |                 1       |
| ridge                                     |     0.054593 |          0.078426 |          0.99323 |       0.1104   |           0.9997  |               0.88619 |                0.88501 |                 0.99284 |
| traditional_dE_E_tail_pedestal_likelihood |     0.059216 |          0.085209 |          0.99342 |       0.12908  |           0.9997  |               0.88332 |                0.88555 |                 0.99308 |
| mlp                                       |     0.072346 |          0.11781  |          0.98528 |       0.10036  |           0.98342 |               0.78319 |                0.85554 |                 0.97455 |
| spectral_transformer_new                  |     0.25371  |          0.24701  |          0.72889 |       0.39982  |           0.96609 |               0.74728 |                0.79132 |                 0.83379 |
| 1d_cnn                                    |     0.26807  |          0.25572  |          0.71578 |       0.38139  |           0.95845 |               0.76056 |                0.68319 |                 0.81355 |

Particle-held-out proxy:

| method                                    |   joint_loss |   mean_joint_loss |   pid_separation |   energy_scale |   pileup_sideband |   saturation_clipping |   pedestal_noise_color |   pulse_shape_harmonics |
|:------------------------------------------|-------------:|------------------:|-----------------:|---------------:|------------------:|----------------------:|-----------------------:|------------------------:|
| gradient_boosted_trees                    |     0.051163 |          0.039583 |          0.98382 |       0.089347 |           0.99906 |               1       |                0.79645 |                 0.99996 |
| ridge                                     |     0.10226  |          0.078426 |          0.95251 |       0.088084 |           0.99874 |               0.94052 |                0.61133 |                 0.86816 |
| traditional_dE_E_tail_pedestal_likelihood |     0.1112   |          0.085209 |          0.94194 |       0.11457  |           0.99869 |               0.93906 |                0.61686 |                 0.87102 |
| mlp                                       |     0.16328  |          0.11781  |          0.87163 |       0.10806  |           0.96391 |               0.74912 |                0.51484 |                 0.91367 |
| spectral_transformer_new                  |     0.24032  |          0.24701  |          0.80901 |       0.32327  |           0.99448 |               0.70654 |                0.55261 |                 0.82082 |
| 1d_cnn                                    |     0.24337  |          0.25572  |          0.73746 |       0.23537  |           0.94061 |               0.77919 |                0.54971 |                 0.8037  |

## Endpoint Bootstrap CIs

| split_name       | endpoint              | method                                    |   metric_value |   ci_low |   ci_high |    n |   positives |
|:-----------------|:----------------------|:------------------------------------------|---------------:|---------:|----------:|-----:|------------:|
| run_heldout      | pid_separation        | gradient_boosted_trees                    |       0.99958  | 0.99925  |   0.99977 | 3816 |        2165 |
| run_heldout      | pid_separation        | traditional_dE_E_tail_pedestal_likelihood |       0.99342  | 0.99112  |   0.99586 | 3816 |        2165 |
| run_heldout      | pid_separation        | ridge                                     |       0.99323  | 0.99041  |   0.99595 | 3816 |        2165 |
| run_heldout      | pid_separation        | mlp                                       |       0.98528  | 0.98217  |   0.98784 | 3816 |        2165 |
| run_heldout      | pid_separation        | spectral_transformer_new                  |       0.72889  | 0.70839  |   0.74934 | 3816 |        2165 |
| run_heldout      | pid_separation        | 1d_cnn                                    |       0.71578  | 0.68227  |   0.7525  | 3816 |        2165 |
| run_heldout      | energy_scale          | gradient_boosted_trees                    |       0.087805 | 0.063393 |   0.1361  | 3816 |             |
| run_heldout      | energy_scale          | mlp                                       |       0.10036  | 0.077704 |   0.12731 | 3816 |             |
| run_heldout      | energy_scale          | ridge                                     |       0.1104   | 0.081855 |   0.17944 | 3816 |             |
| run_heldout      | energy_scale          | traditional_dE_E_tail_pedestal_likelihood |       0.12908  | 0.11645  |   0.13784 | 3816 |             |
| run_heldout      | energy_scale          | 1d_cnn                                    |       0.38139  | 0.34658  |   0.41103 | 3816 |             |
| run_heldout      | energy_scale          | spectral_transformer_new                  |       0.39982  | 0.36508  |   0.43147 | 3816 |             |
| run_heldout      | pileup_sideband       | gradient_boosted_trees                    |       0.99995  | 0.99992  |   0.99998 | 3816 |         633 |
| run_heldout      | pileup_sideband       | ridge                                     |       0.9997   | 0.99953  |   0.99984 | 3816 |         633 |
| run_heldout      | pileup_sideband       | traditional_dE_E_tail_pedestal_likelihood |       0.9997   | 0.99956  |   0.99987 | 3816 |         633 |
| run_heldout      | pileup_sideband       | mlp                                       |       0.98342  | 0.98001  |   0.9872  | 3816 |         633 |
| run_heldout      | pileup_sideband       | spectral_transformer_new                  |       0.96609  | 0.9615   |   0.97096 | 3816 |         633 |
| run_heldout      | pileup_sideband       | 1d_cnn                                    |       0.95845  | 0.94355  |   0.9688  | 3816 |         633 |
| run_heldout      | saturation_clipping   | gradient_boosted_trees                    |       0.99729  | 0.99427  |   0.99885 | 3816 |         261 |
| run_heldout      | saturation_clipping   | ridge                                     |       0.88619  | 0.82578  |   0.91745 | 3816 |         261 |
| run_heldout      | saturation_clipping   | traditional_dE_E_tail_pedestal_likelihood |       0.88332  | 0.82913  |   0.91155 | 3816 |         261 |
| run_heldout      | saturation_clipping   | mlp                                       |       0.78319  | 0.65213  |   0.85747 | 3816 |         261 |
| run_heldout      | saturation_clipping   | 1d_cnn                                    |       0.76056  | 0.60803  |   0.82652 | 3816 |         261 |
| run_heldout      | saturation_clipping   | spectral_transformer_new                  |       0.74728  | 0.66107  |   0.79741 | 3816 |         261 |
| run_heldout      | pedestal_noise_color  | gradient_boosted_trees                    |       0.94569  | 0.91821  |   0.9657  | 3816 |         789 |
| run_heldout      | pedestal_noise_color  | traditional_dE_E_tail_pedestal_likelihood |       0.88555  | 0.85286  |   0.90631 | 3816 |         789 |
| run_heldout      | pedestal_noise_color  | ridge                                     |       0.88501  | 0.85754  |   0.90674 | 3816 |         789 |
| run_heldout      | pedestal_noise_color  | mlp                                       |       0.85554  | 0.82587  |   0.8818  | 3816 |         789 |
| run_heldout      | pedestal_noise_color  | spectral_transformer_new                  |       0.79132  | 0.74528  |   0.83338 | 3816 |         789 |
| run_heldout      | pedestal_noise_color  | 1d_cnn                                    |       0.68319  | 0.6543   |   0.70949 | 3816 |         789 |
| run_heldout      | pulse_shape_harmonics | gradient_boosted_trees                    |       1        | 0.99999  |   1       | 3816 |         767 |
| run_heldout      | pulse_shape_harmonics | traditional_dE_E_tail_pedestal_likelihood |       0.99308  | 0.99052  |   0.99539 | 3816 |         767 |
| run_heldout      | pulse_shape_harmonics | ridge                                     |       0.99284  | 0.99022  |   0.99534 | 3816 |         767 |
| run_heldout      | pulse_shape_harmonics | mlp                                       |       0.97455  | 0.96886  |   0.98044 | 3816 |         767 |
| run_heldout      | pulse_shape_harmonics | spectral_transformer_new                  |       0.83379  | 0.78424  |   0.86103 | 3816 |         767 |
| run_heldout      | pulse_shape_harmonics | 1d_cnn                                    |       0.81355  | 0.75691  |   0.84324 | 3816 |         767 |
| particle_heldout | pid_separation        | gradient_boosted_trees                    |       0.98382  | 0.97865  |   0.98861 | 1739 |         494 |
| particle_heldout | pid_separation        | ridge                                     |       0.95251  | 0.94127  |   0.96188 | 1739 |         494 |
| particle_heldout | pid_separation        | traditional_dE_E_tail_pedestal_likelihood |       0.94194  | 0.93084  |   0.95268 | 1739 |         494 |
| particle_heldout | pid_separation        | mlp                                       |       0.87163  | 0.84851  |   0.89335 | 1739 |         494 |
| particle_heldout | pid_separation        | spectral_transformer_new                  |       0.80901  | 0.78121  |   0.83373 | 1739 |         494 |
| particle_heldout | pid_separation        | 1d_cnn                                    |       0.73746  | 0.71012  |   0.76566 | 1739 |         494 |
| particle_heldout | energy_scale          | ridge                                     |       0.088084 | 0.074452 |   0.10521 | 1739 |             |
| particle_heldout | energy_scale          | gradient_boosted_trees                    |       0.089347 | 0.080431 |   0.09939 | 1739 |             |
| particle_heldout | energy_scale          | mlp                                       |       0.10806  | 0.09774  |   0.11901 | 1739 |             |
| particle_heldout | energy_scale          | traditional_dE_E_tail_pedestal_likelihood |       0.11457  | 0.10432  |   0.12514 | 1739 |             |
| particle_heldout | energy_scale          | 1d_cnn                                    |       0.23537  | 0.22402  |   0.24812 | 1739 |             |
| particle_heldout | energy_scale          | spectral_transformer_new                  |       0.32327  | 0.2984   |   0.3366  | 1739 |             |
| particle_heldout | pileup_sideband       | gradient_boosted_trees                    |       0.99906  | 0.99848  |   0.99946 | 1739 |         737 |
| particle_heldout | pileup_sideband       | ridge                                     |       0.99874  | 0.99804  |   0.99932 | 1739 |         737 |
| particle_heldout | pileup_sideband       | traditional_dE_E_tail_pedestal_likelihood |       0.99869  | 0.99803  |   0.99926 | 1739 |         737 |
| particle_heldout | pileup_sideband       | spectral_transformer_new                  |       0.99448  | 0.99223  |   0.99634 | 1739 |         737 |
| particle_heldout | pileup_sideband       | mlp                                       |       0.96391  | 0.95154  |   0.97377 | 1739 |         737 |
| particle_heldout | pileup_sideband       | 1d_cnn                                    |       0.94061  | 0.92443  |   0.95573 | 1739 |         737 |
| particle_heldout | saturation_clipping   | gradient_boosted_trees                    |       1        | 1        |   1       | 1739 |          44 |
| particle_heldout | saturation_clipping   | ridge                                     |       0.94052  | 0.88893  |   0.97383 | 1739 |          44 |
| particle_heldout | saturation_clipping   | traditional_dE_E_tail_pedestal_likelihood |       0.93906  | 0.9007   |   0.97398 | 1739 |          44 |
| particle_heldout | saturation_clipping   | 1d_cnn                                    |       0.77919  | 0.72185  |   0.84491 | 1739 |          44 |
| particle_heldout | saturation_clipping   | mlp                                       |       0.74912  | 0.68024  |   0.82246 | 1739 |          44 |
| particle_heldout | saturation_clipping   | spectral_transformer_new                  |       0.70654  | 0.64426  |   0.77395 | 1739 |          44 |
| particle_heldout | pedestal_noise_color  | gradient_boosted_trees                    |       0.79645  | 0.73409  |   0.85165 | 1739 |          84 |
| particle_heldout | pedestal_noise_color  | traditional_dE_E_tail_pedestal_likelihood |       0.61686  | 0.53398  |   0.69427 | 1739 |          84 |
| particle_heldout | pedestal_noise_color  | ridge                                     |       0.61133  | 0.53602  |   0.67492 | 1739 |          84 |
| particle_heldout | pedestal_noise_color  | spectral_transformer_new                  |       0.55261  | 0.49609  |   0.61842 | 1739 |          84 |
| particle_heldout | pedestal_noise_color  | 1d_cnn                                    |       0.54971  | 0.49189  |   0.61055 | 1739 |          84 |
| particle_heldout | pedestal_noise_color  | mlp                                       |       0.51484  | 0.49723  |   0.5388  | 1739 |          84 |
| particle_heldout | pulse_shape_harmonics | gradient_boosted_trees                    |       0.99996  | 0.99988  |   1       | 1739 |        1050 |
| particle_heldout | pulse_shape_harmonics | mlp                                       |       0.91367  | 0.8939   |   0.93071 | 1739 |        1050 |
| particle_heldout | pulse_shape_harmonics | traditional_dE_E_tail_pedestal_likelihood |       0.87102  | 0.84787  |   0.89216 | 1739 |        1050 |
| particle_heldout | pulse_shape_harmonics | ridge                                     |       0.86816  | 0.84121  |   0.8918  | 1739 |        1050 |
| particle_heldout | pulse_shape_harmonics | spectral_transformer_new                  |       0.82082  | 0.7983   |   0.84599 | 1739 |        1050 |
| particle_heldout | pulse_shape_harmonics | 1d_cnn                                    |       0.8037   | 0.78098  |   0.82421 | 1739 |        1050 |

## PID Calibration and Energy Residuals

| split_name       | method                                    |     auc |       ece |    n |   positives |
|:-----------------|:------------------------------------------|--------:|----------:|-----:|------------:|
| particle_heldout | 1d_cnn                                    | 0.73746 | 0.22003   | 1739 |         494 |
| particle_heldout | gradient_boosted_trees                    | 0.98382 | 0.11114   | 1739 |         494 |
| particle_heldout | mlp                                       | 0.87163 | 0.32076   | 1739 |         494 |
| particle_heldout | ridge                                     | 0.95251 | 0.24607   | 1739 |         494 |
| particle_heldout | spectral_transformer_new                  | 0.80901 | 0.23199   | 1739 |         494 |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood | 0.94194 | 0.22825   | 1739 |         494 |
| run_heldout      | 1d_cnn                                    | 0.71578 | 0.1395    | 3816 |        2165 |
| run_heldout      | gradient_boosted_trees                    | 0.99958 | 0.0068336 | 3816 |        2165 |
| run_heldout      | mlp                                       | 0.98528 | 0.35444   | 3816 |        2165 |
| run_heldout      | ridge                                     | 0.99323 | 0.27243   | 3816 |        2165 |
| run_heldout      | spectral_transformer_new                  | 0.72889 | 0.11584   | 3816 |        2165 |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood | 0.99342 | 0.2768    | 3816 |        2165 |

Energy residual rows are the `energy_scale` endpoint in the CI table; they are log-amplitude residuals after run/stave centering, not an externally calibrated MeV scale.

## Paired Bootstrap Deltas vs Traditional

| split_name       | endpoint              | method                   |   delta_vs_traditional |      ci_low |     ci_high | delta_definition                                             |
|:-----------------|:----------------------|:-------------------------|-----------------------:|------------:|------------:|:-------------------------------------------------------------|
| particle_heldout | energy_scale          | 1d_cnn                   |             0.12075    |  0.10756    |  0.13471    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | gradient_boosted_trees   |            -0.024935   | -0.03512    | -0.013286   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | mlp                      |            -0.0058176  | -0.018301   |  0.0062907  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | ridge                    |            -0.026831   | -0.039784   | -0.011064   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | spectral_transformer_new |             0.20553    |  0.17884    |  0.22513    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | 1d_cnn                   |            -0.069076   | -0.14493    | -0.00099127 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | gradient_boosted_trees   |             0.17534    |  0.10525    |  0.24321    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | mlp                      |            -0.10101    | -0.1801     | -0.029181   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | ridge                    |            -0.006691   | -0.020122   |  0.0069957  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | spectral_transformer_new |            -0.067349   | -0.1332     |  0.0031224  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | 1d_cnn                   |            -0.2042     | -0.23199    | -0.17536    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | gradient_boosted_trees   |             0.042121   |  0.032065   |  0.05127    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | mlp                      |            -0.068975   | -0.089079   | -0.049029   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | ridge                    |             0.010567   |  0.0078603  |  0.013517   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | spectral_transformer_new |            -0.13489    | -0.16083    | -0.1113     | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | 1d_cnn                   |            -0.05811    | -0.075071   | -0.044092   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | gradient_boosted_trees   |             0.00037048 |  0.00011995 |  0.00074749 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | mlp                      |            -0.034677   | -0.046806   | -0.024509   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | ridge                    |             4.7673e-05 |  1.9763e-05 |  8.6244e-05 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | spectral_transformer_new |            -0.0043022  | -0.0057754  | -0.0029123  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | 1d_cnn                   |            -0.066474   | -0.090888   | -0.041312   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | gradient_boosted_trees   |             0.12983    |  0.10869    |  0.15271    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | mlp                      |             0.04216    |  0.015664   |  0.072838   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | ridge                    |            -0.0028711  | -0.005306   | -0.00084585 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | spectral_transformer_new |            -0.050688   | -0.071931   | -0.028936   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | 1d_cnn                   |            -0.15957    | -0.24063    | -0.088048   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | gradient_boosted_trees   |             0.062071   |  0.028437   |  0.10536    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | mlp                      |            -0.19062    | -0.25314    | -0.13244    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | ridge                    |             0.001417   | -0.0056218  |  0.010095   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | spectral_transformer_new |            -0.22797    | -0.306      | -0.15029    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | 1d_cnn                   |             0.25439    |  0.22278    |  0.28928    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | gradient_boosted_trees   |            -0.038434   | -0.063419   |  0.012605   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | mlp                      |            -0.026116   | -0.050101   |  0.0055944  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | ridge                    |            -0.011525   | -0.053919   |  0.062184   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | spectral_transformer_new |             0.27032    |  0.23437    |  0.30554    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | 1d_cnn                   |            -0.2017     | -0.21922    | -0.18294    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | gradient_boosted_trees   |             0.06086    |  0.051952   |  0.07108    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | mlp                      |            -0.030072   | -0.043488   | -0.02012    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | ridge                    |            -0.00030469 | -0.0039326  |  0.0037527  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | spectral_transformer_new |            -0.094211   | -0.12487    | -0.064971   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | 1d_cnn                   |            -0.27718    | -0.31137    | -0.24341    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | gradient_boosted_trees   |             0.0059993  |  0.0036214  |  0.0084606  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | mlp                      |            -0.00821    | -0.010575   | -0.0054267  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | ridge                    |            -0.00017376 | -0.00065909 |  0.00034776 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | spectral_transformer_new |            -0.26379    | -0.28714    | -0.24386    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | 1d_cnn                   |            -0.040439   | -0.052378   | -0.030954   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | gradient_boosted_trees   |             0.00026164 |  0.00013884 |  0.00041271 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | mlp                      |            -0.016148   | -0.019684   | -0.012219   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | ridge                    |             4.5986e-06 | -7.3452e-06 |  2.3939e-05 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | spectral_transformer_new |            -0.033381   | -0.038474   | -0.028508   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | 1d_cnn                   |            -0.18043    | -0.23102    | -0.14513    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | gradient_boosted_trees   |             0.0069595  |  0.0045269  |  0.0093617  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | mlp                      |            -0.018438   | -0.024558   | -0.013871   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | ridge                    |            -0.00023583 | -0.00048761 | -1.3403e-05 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | spectral_transformer_new |            -0.15972    | -0.20489    | -0.13087    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | 1d_cnn                   |            -0.12736    | -0.18729    | -0.085652   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | gradient_boosted_trees   |             0.12055    |  0.087599   |  0.1643     | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | mlp                      |            -0.10121    | -0.16583    | -0.052119   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | ridge                    |             0.002866   |  0.00071598 |  0.0052087  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | spectral_transformer_new |            -0.14043    | -0.17794    | -0.11297    | AUC gain for classification; sigma68 increase for regression |

## Stratified Systematics

The full `strata_metrics.csv` file stratifies each endpoint by late-tail amplitude, pedestal history, pulse-shape harmonic content, timing residual, pile-up flag, saturation flag, and energy bin. The excerpt below shows the winner on the two most relevant PID/energy axes.

| split_name       | endpoint       | stratum_axis         | stratum          |    n | metric   |    value |
|:-----------------|:---------------|:---------------------|:-----------------|-----:|:---------|---------:|
| particle_heldout | energy_scale   | tail_amplitude_bin   | tail_high        | 1669 | sigma68  | 0.088878 |
| particle_heldout | energy_scale   | tail_amplitude_bin   | tail_mid         |   70 | sigma68  | 0.1241   |
| particle_heldout | energy_scale   | pedestal_history_bin | pedestal_memory  |  472 | sigma68  | 0.062356 |
| particle_heldout | energy_scale   | pedestal_history_bin | pedestal_mid     |  683 | sigma68  | 0.076598 |
| particle_heldout | energy_scale   | pedestal_history_bin | pedestal_quiet   |  584 | sigma68  | 0.14892  |
| particle_heldout | energy_scale   | pulse_shape_bin      | low_harmonic     |  812 | sigma68  | 0.092755 |
| particle_heldout | energy_scale   | pulse_shape_bin      | mid_harmonic     |  917 | sigma68  | 0.079304 |
| particle_heldout | energy_scale   | timing_residual_bin  | timing_core      |  559 | sigma68  | 0.09769  |
| particle_heldout | energy_scale   | timing_residual_bin  | timing_mid       |  473 | sigma68  | 0.093535 |
| particle_heldout | energy_scale   | timing_residual_bin  | timing_tail      |  707 | sigma68  | 0.074171 |
| particle_heldout | energy_scale   | pileup_flag          | pileup_proxy     |  737 | sigma68  | 0.073934 |
| particle_heldout | energy_scale   | pileup_flag          | single_proxy     | 1002 | sigma68  | 0.09336  |
| particle_heldout | energy_scale   | saturation_flag      | linear_proxy     | 1695 | sigma68  | 0.086501 |
| particle_heldout | energy_scale   | saturation_flag      | saturation_proxy |   44 | sigma68  | 0.18256  |
| particle_heldout | energy_scale   | energy_bin           | energy_high      | 1630 | sigma68  | 0.084963 |
| particle_heldout | energy_scale   | energy_bin           | energy_mid       |   90 | sigma68  | 0.099075 |
| particle_heldout | pid_separation | tail_amplitude_bin   | tail_high        | 1669 | auc      | 0.98278  |
| particle_heldout | pid_separation | tail_amplitude_bin   | tail_mid         |   70 | auc      | 1        |
| particle_heldout | pid_separation | pedestal_history_bin | pedestal_memory  |  472 | auc      | 0.98046  |
| particle_heldout | pid_separation | pedestal_history_bin | pedestal_mid     |  683 | auc      | 0.98745  |
| particle_heldout | pid_separation | pedestal_history_bin | pedestal_quiet   |  584 | auc      | 0.98393  |
| particle_heldout | pid_separation | pulse_shape_bin      | low_harmonic     |  812 | auc      | 0.99539  |
| particle_heldout | pid_separation | pulse_shape_bin      | mid_harmonic     |  917 | auc      | 0.96322  |
| particle_heldout | pid_separation | timing_residual_bin  | timing_core      |  559 | auc      | 0.98061  |
| particle_heldout | pid_separation | timing_residual_bin  | timing_mid       |  473 | auc      | 0.95168  |
| particle_heldout | pid_separation | timing_residual_bin  | timing_tail      |  707 | auc      | 0.99528  |
| particle_heldout | pid_separation | pileup_flag          | pileup_proxy     |  737 | auc      | 0.99424  |
| particle_heldout | pid_separation | pileup_flag          | single_proxy     | 1002 | auc      | 0.97055  |
| particle_heldout | pid_separation | saturation_flag      | linear_proxy     | 1695 | auc      | 0.98567  |
| particle_heldout | pid_separation | saturation_flag      | saturation_proxy |   44 | auc      | 0.87153  |

## Leakage, Feature, and Attention Audits

| split_name       | method                                    |   pid_auc |   energy_sigma68 |   late_tail_auc |   pedestal_auc |   pid_ece |   cross_task_leakage_index | interpretation                                                                          |
|:-----------------|:------------------------------------------|----------:|-----------------:|----------------:|---------------:|----------:|---------------------------:|:----------------------------------------------------------------------------------------|
| particle_heldout | 1d_cnn                                    |   0.73746 |         0.23537  |         0.8037  |        0.54971 | 0.22003   |                   0.18775  | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | gradient_boosted_trees                    |   0.98382 |         0.089347 |         0.99996 |        0.79645 | 0.11114   |                   0.21802  | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | mlp                                       |   0.87163 |         0.10806  |         0.91367 |        0.51484 | 0.32076   |                   0.36874  | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | ridge                                     |   0.95251 |         0.088084 |         0.86816 |        0.61133 | 0.24607   |                   0.3731   | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | spectral_transformer_new                  |   0.80901 |         0.32327  |         0.82082 |        0.55261 | 0.23199   |                   0.2564   | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood |   0.94194 |         0.11457  |         0.87102 |        0.61686 | 0.22825   |                   0.33051  | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | 1d_cnn                                    |   0.71578 |         0.38139  |         0.81355 |        0.68319 | 0.1395    |                   0.032596 | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | gradient_boosted_trees                    |   0.99958 |         0.087805 |         1       |        0.94569 | 0.0068336 |                   0.08609  | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | mlp                                       |   0.98528 |         0.10036  |         0.97455 |        0.85554 | 0.35444   |                   0.14938  | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | ridge                                     |   0.99323 |         0.1104   |         0.99284 |        0.88501 | 0.27243   |                   0.11782  | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | spectral_transformer_new                  |   0.72889 |         0.39982  |         0.83379 |        0.79132 | 0.11584   |                   0        | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood |   0.99342 |         0.12908  |         0.99308 |        0.88555 | 0.2768    |                   0.10787  | proxy-label coupling audit; high values require external truth before physics promotion |

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
/home/billy/anaconda3/bin/python scripts/s32c_1783884181_2159_4b0d44ea_pid_energy_uncertainty_tail_pedestal_memory.py --config configs/s32c_1783884181_2159_4b0d44ea_pid_energy_uncertainty_tail_pedestal_memory.json
```

