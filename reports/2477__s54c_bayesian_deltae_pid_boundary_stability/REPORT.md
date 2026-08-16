# S54c: Bayesian deltaE-E PID Templates Versus Multitask Waveform ML Boundary Stability

## Abstract

Ticket `2477` asks whether a traditional Bayesian deltaE-E/template PID
boundary remains stable against several ML and neural alternatives.  The raw
ROOT reproduction gate is exact: `640737` selected
B-stave pulses versus reference `640737`, delta
`0`.  The held-out split is by run: train
`[58, 59, 60, 61, 62]` and held-out `[63, 65]`.

The winner named in `result.json` is **`gradient_boosted_trees`** by the declared
boundary-stability score

`S_m = (1 - BAcc_m) + ECE_m + M_m + 0.15 sigma_E,m + 0.005 sigma_t,m + 0.10 P_m`,

where `BAcc` is weak-label balanced accuracy, `ECE` is calibration error, `M` is
boundary migration relative to the frozen deltaE/E-depth label, `sigma_E` is
log-charge residual sigma68, `sigma_t` is CFD timing residual sigma68 in ns, and
`P` is the pedestal-band score span.

## Raw ROOT Reproduction

Raw files are read from `data/root/root`.  For B2/B4/B6/B8 channels
`c`, the pedestal is `b_c = median(x_c[0:4])`, the corrected waveform is
`y_c(t)=x_c(t)-b_c`, and selected B-stave pulses satisfy
`max_t y_c(t) > 1000` ADC.  The reproduction table is:

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Frozen PID Boundary

No event-level external PID truth ROOT was mounted in this worker.  Therefore
S54c is framed as a raw-data weak PID boundary-stability benchmark.  The label is
frozen from train runs only:

`z_i = 1.2 (L_i-q_0.58(L))/sigma_L + 0.9 (D_i-q_0.58(D))/sigma_D - 0.45 (R_i-q_0.42(R))/sigma_R`,

with late/deep label `y_i=1[z_i >= 0]`.  `L` is late charge fraction
`(B6+B8)/(B2+B4+B6+B8)`, `D` is charge-weighted depth, and `R` is upstream
deltaE-over-downstream-energy.  The thresholds are:

| quantity                  |      value |
|:--------------------------|-----------:|
| late_fraction_train_q58   |   0.006172 |
| depth_mean_train_q58      |   0.06943  |
| deltae_over_e_train_q42   | 138.6      |
| train_positive_fraction   |   0.3491   |
| heldout_positive_fraction |   0.2356   |

## Methods

The strong traditional method is `bayesian_deltae_template_likelihood`.  It uses
pedestal-subtracted charge integration, CFD timing, depth-weighted deltaE/E
features, and diagonal Gaussian class likelihoods

`log p(z|y) = -1/2 sum_j [(z_j-mu_yj)^2/sigma_yj^2 + log sigma_yj^2] + log pi_y`.

The ML/NN panel contains `ridge`, `gradient_boosted_trees`, `mlp`, `1d_cnn`, and
the new `multitask_waveform_transformer_new`.  The neural models consume the
4x18 B-stack waveform tensor and jointly predict PID boundary score, log-charge
energy proxy, and CFD timing proxy.  All preprocessing, Gaussian moments,
scalers, tree splits, and neural weights are fitted on train runs only.

## Overall Held-Out Results

| method                              |   winner_score |   pid_auc |   pid_auc_ci_low |   pid_auc_ci_high |   pid_balanced_accuracy |   pid_balanced_accuracy_ci_low |   pid_balanced_accuracy_ci_high |   calibration_ece |   boundary_migration_rate |   energy_log_area_sigma68 |   timing_cfd20_sigma68_ns |   pedestal_transfer_span |
|:------------------------------------|---------------:|----------:|-----------------:|------------------:|------------------------:|-------------------------------:|--------------------------------:|------------------:|--------------------------:|--------------------------:|--------------------------:|-------------------------:|
| gradient_boosted_trees              |        0.02626 |    0.9999 |           0.9998 |            1      |                  0.9938 |                         0.991  |                          0.9968 |          0.003733 |                  0.004444 |                  0.004514 |                   0.04307 |                  0.1102  |
| mlp                                 |        0.1413  |    0.992  |           0.9911 |            0.9929 |                  0.9459 |                         0.9349 |                          0.9564 |          0.01303  |                  0.03778  |                  0.1437   |                   0.8289  |                  0.1076  |
| 1d_cnn                              |        0.168   |    0.9922 |           0.9908 |            0.994  |                  0.9524 |                         0.9506 |                          0.9544 |          0.0299   |                  0.04278  |                  0.1393   |                   3.073   |                  0.1146  |
| ridge                               |        0.1958  |    0.9902 |           0.9892 |            0.9911 |                  0.9281 |                         0.9222 |                          0.9335 |          0.0411   |                  0.03889  |                  0.2279   |                   0.01508 |                  0.09588 |
| multitask_waveform_transformer_new  |        0.2121  |    0.9941 |           0.992  |            0.9966 |                  0.8984 |                         0.8939 |                          0.9024 |          0.03471  |                  0.05056  |                  0.05716  |                   1.449   |                  0.09396 |
| bayesian_deltae_template_likelihood |        0.3962  |    0.9181 |           0.9107 |            0.9281 |                  0.7846 |                         0.7445 |                          0.8216 |          0.06183  |                  0.1122   |                  0        |                   0       |                  0.06805 |

Relative to the traditional baseline, `gradient_boosted_trees` changes balanced
accuracy by `0.2092`,
boundary migration by `-0.1078`,
energy sigma68 by `0.004514`,
and timing sigma68 by `0.04307` ns.

## Run-Held-Out Stability

| method                              |   heldout_run |   pid_auc |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   boundary_migration_rate |   energy_log_area_sigma68 |   timing_cfd20_sigma68_ns |
|:------------------------------------|--------------:|----------:|------------------------:|-----------------:|-------------:|--------------------------:|--------------------------:|--------------------------:|
| 1d_cnn                              |            63 |    0.9908 |                  0.9506 |           0.9409 |       0.8846 |                  0.04444  |                  0.1494   |                   3.22    |
| 1d_cnn                              |            65 |    0.994  |                  0.9544 |           0.9461 |       0.8813 |                  0.04111  |                  0.1289   |                   2.978   |
| bayesian_deltae_template_likelihood |            63 |    0.9281 |                  0.8216 |           0.6682 |       0.8963 |                  0.1      |                  0        |                   0       |
| bayesian_deltae_template_likelihood |            65 |    0.9107 |                  0.7445 |           0.5049 |       0.9035 |                  0.1244   |                  0        |                   0       |
| gradient_boosted_trees              |            63 |    0.9998 |                  0.991  |           0.9864 |       0.9864 |                  0.006667 |                  0.004591 |                   0.04599 |
| gradient_boosted_trees              |            65 |    1      |                  0.9968 |           0.9951 |       0.9951 |                  0.002222 |                  0.004495 |                   0.04043 |
| mlp                                 |            63 |    0.9929 |                  0.9564 |           0.9318 |       0.9404 |                  0.03111  |                  0.1442   |                   0.8491  |
| mlp                                 |            65 |    0.9911 |                  0.9349 |           0.8971 |       0.9059 |                  0.04444  |                  0.1426   |                   0.8162  |
| multitask_waveform_transformer_new  |            63 |    0.992  |                  0.9024 |           0.8136 |       0.9676 |                  0.05222  |                  0.05844  |                   1.493   |
| multitask_waveform_transformer_new  |            65 |    0.9966 |                  0.8939 |           0.7892 |       0.9938 |                  0.04889  |                  0.05412  |                   1.398   |
| ridge                               |            63 |    0.9911 |                  0.9335 |           0.8773 |       0.965  |                  0.03778  |                  0.2507   |                   0.01611 |
| ridge                               |            65 |    0.9892 |                  0.9222 |           0.8529 |       0.9667 |                  0.04     |                  0.2169   |                   0.01448 |

## Systematic Sidebands

| sideband        | value   | method                              |   pid_balanced_accuracy |   boundary_migration_rate |   calibration_ece |   energy_log_area_sigma68 |   timing_cfd20_sigma68_ns |
|:----------------|:--------|:------------------------------------|------------------------:|--------------------------:|------------------:|--------------------------:|--------------------------:|
| depth_band      | deep    | 1d_cnn                              |                  0.8553 |                  0.11     |         0.04747   |                  0.2894   |                   5.353   |
| depth_band      | deep    | bayesian_deltae_template_likelihood |                  0.7833 |                  0.2917   |         0.2021    |                  0        |                   0       |
| depth_band      | deep    | gradient_boosted_trees              |                  0.9869 |                  0.01167  |         0.01045   |                  0.007126 |                   0.085   |
| depth_band      | deep    | mlp                                 |                  0.9046 |                  0.09167  |         0.04688   |                  0.2265   |                   1.073   |
| depth_band      | deep    | multitask_waveform_transformer_new  |                  0.897  |                  0.1417   |         0.1222    |                  0.1387   |                   2.91    |
| depth_band      | deep    | ridge                               |                  0.9099 |                  0.1083   |         0.07707   |                  0.5199   |                   0.0194  |
| depth_band      | mid     | 1d_cnn                              |                  0.9917 |                  0.008333 |         0.05103   |                  0.08026  |                   2.306   |
| depth_band      | mid     | bayesian_deltae_template_likelihood |                  0.98   |                  0.02     |         0.168     |                  0        |                   0       |
| depth_band      | mid     | gradient_boosted_trees              |                  1      |                  0        |         0.0002053 |                  0.003868 |                   0.03305 |
| depth_band      | mid     | mlp                                 |                  0.9817 |                  0.01833  |         0.05198   |                  0.1214   |                   0.7279  |
| depth_band      | mid     | multitask_waveform_transformer_new  |                  0.9983 |                  0.001667 |         0.01023   |                  0.02803  |                   0.911   |
| depth_band      | mid     | ridge                               |                  0.995  |                  0.005    |         0.07804   |                  0.1633   |                   0.01311 |
| depth_band      | shallow | 1d_cnn                              |                  0.995  |                  0.01     |         0.01201   |                  0.09554  |                   2.389   |
| depth_band      | shallow | bayesian_deltae_template_likelihood |                  0.5908 |                  0.025    |         0.05733   |                  0        |                   0       |
| depth_band      | shallow | gradient_boosted_trees              |                  0.9992 |                  0.001667 |         0.002741  |                  0.003515 |                   0.03569 |
| depth_band      | shallow | mlp                                 |                  0.9983 |                  0.003333 |         0.004588  |                  0.1216   |                   0.7392  |
| depth_band      | shallow | multitask_waveform_transformer_new  |                  0.9958 |                  0.008333 |         0.007839  |                  0.03214  |                   1.129   |
| depth_band      | shallow | ridge                               |                  0.9983 |                  0.003333 |         0.0112    |                  0.1692   |                   0.01173 |
| energy_band     | high    | 1d_cnn                              |                  0.9788 |                  0.025    |         0.0161    |                  0.1009   |                   1.833   |
| energy_band     | high    | bayesian_deltae_template_likelihood |                  0.9574 |                  0.025    |         0.1003    |                  0        |                   0       |
| energy_band     | high    | gradient_boosted_trees              |                  0.992  |                  0.005    |         0.004173  |                  0.002476 |                   0.05595 |
| energy_band     | high    | mlp                                 |                  0.977  |                  0.01333  |         0.00805   |                  0.1347   |                   0.9398  |
| energy_band     | high    | multitask_waveform_transformer_new  |                  0.9121 |                  0.04333  |         0.03168   |                  0.05936  |                   1.47    |
| energy_band     | high    | ridge                               |                  0.9781 |                  0.01167  |         0.008775  |                  0.2153   |                   0.01516 |
| energy_band     | low     | 1d_cnn                              |                  0.9285 |                  0.07488  |         0.06531   |                  0.2522   |                   4.813   |
| energy_band     | low     | bayesian_deltae_template_likelihood |                  0.6963 |                  0.2363   |         0.1394    |                  0        |                   0       |
| energy_band     | low     | gradient_boosted_trees              |                  0.996  |                  0.004992 |         0.006502  |                  0.0093   |                   0.04291 |
| energy_band     | low     | mlp                                 |                  0.9361 |                  0.06656  |         0.03705   |                  0.1836   |                   0.7733  |
| energy_band     | low     | multitask_waveform_transformer_new  |                  0.9024 |                  0.07654  |         0.05267   |                  0.1108   |                   2.126   |
| energy_band     | low     | ridge                               |                  0.9249 |                  0.06323  |         0.08871   |                  0.31     |                   0.01337 |
| energy_band     | mid     | 1d_cnn                              |                  0.9137 |                  0.02838  |         0.02493   |                  0.09766  |                   1.746   |
| energy_band     | mid     | bayesian_deltae_template_likelihood |                  0.6681 |                  0.07513  |         0.06072   |                  0        |                   0       |
| energy_band     | mid     | gradient_boosted_trees              |                  0.9825 |                  0.003339 |         0.003547  |                  0.004035 |                   0.03565 |
| energy_band     | mid     | mlp                                 |                  0.8403 |                  0.03339  |         0.02462   |                  0.1144   |                   0.7495  |
| energy_band     | mid     | multitask_waveform_transformer_new  |                  0.8333 |                  0.03172  |         0.02496   |                  0.02487  |                   0.9061  |
| energy_band     | mid     | ridge                               |                  0.7886 |                  0.04174  |         0.04854   |                  0.1536   |                   0.01391 |
| late_tail_band  | compact | 1d_cnn                              |                  0.9333 |                  0.02167  |         0.02465   |                  0.1344   |                   3.506   |
| late_tail_band  | compact | bayesian_deltae_template_likelihood |                  0.8657 |                  0.045    |         0.03713   |                  0        |                   0       |
| late_tail_band  | compact | gradient_boosted_trees              |                  0.9991 |                  0.001667 |         0.003659  |                  0.005386 |                   0.04235 |
| late_tail_band  | compact | mlp                                 |                  0.9982 |                  0.003333 |         0.007582  |                  0.1353   |                   0.753   |
| late_tail_band  | compact | multitask_waveform_transformer_new  |                  0.9122 |                  0.02     |         0.01011   |                  0.06057  |                   1.554   |
| late_tail_band  | compact | ridge                               |                  0.9973 |                  0.005    |         0.0145    |                  0.2419   |                   0.01423 |
| late_tail_band  | late    | 1d_cnn                              |                  0.9222 |                  0.075    |         0.07045   |                  0.1482   |                   4.236   |
| late_tail_band  | late    | bayesian_deltae_template_likelihood |                  0.7531 |                  0.2667   |         0.1272    |                  0        |                   0       |
| late_tail_band  | late    | gradient_boosted_trees              |                  0.9969 |                  0.003333 |         0.004861  |                  0.005694 |                   0.0486  |
| late_tail_band  | late    | mlp                                 |                  0.8992 |                  0.1017   |         0.03417   |                  0.1809   |                   0.864   |
| late_tail_band  | late    | multitask_waveform_transformer_new  |                  0.923  |                  0.08333  |         0.066     |                  0.08967  |                   1.842   |
| late_tail_band  | late    | ridge                               |                  0.901  |                  0.105    |         0.07907   |                  0.2853   |                   0.01727 |
| late_tail_band  | nominal | 1d_cnn                              |                  0.9505 |                  0.03167  |         0.02725   |                  0.06874  |                   1.837   |
| late_tail_band  | nominal | bayesian_deltae_template_likelihood |                  0.9141 |                  0.025    |         0.1312    |                  0        |                   0       |
| late_tail_band  | nominal | gradient_boosted_trees              |                  0.9794 |                  0.008333 |         0.006761  |                  0.003171 |                   0.03946 |
| late_tail_band  | nominal | mlp                                 |                  0.9954 |                  0.008333 |         0.02231   |                  0.133    |                   0.7894  |
| late_tail_band  | nominal | multitask_waveform_transformer_new  |                  0.7491 |                  0.04833  |         0.03454   |                  0.02905  |                   1.002   |
| late_tail_band  | nominal | ridge                               |                  0.9803 |                  0.006667 |         0.03931   |                  0.1846   |                   0.01325 |
| pedestal_band   | high    | 1d_cnn                              |                  0.9465 |                  0.04569  |         0.01827   |                  0.2178   |                   4.698   |
| pedestal_band   | high    | bayesian_deltae_template_likelihood |                  0.8831 |                  0.07107  |         0.04145   |                  0        |                   0       |
| pedestal_band   | high    | gradient_boosted_trees              |                  0.9954 |                  0.003384 |         0.00419   |                  0.006237 |                   0.07848 |
| pedestal_band   | high    | mlp                                 |                  0.96   |                  0.02876  |         0.01776   |                  0.1761   |                   0.9596  |
| pedestal_band   | high    | multitask_waveform_transformer_new  |                  0.9197 |                  0.04738  |         0.02569   |                  0.1065   |                   2.574   |
| pedestal_band   | high    | ridge                               |                  0.9565 |                  0.02707  |         0.01265   |                  0.448    |                   0.01759 |
| pedestal_band   | low     | 1d_cnn                              |                  0.9559 |                  0.04575  |         0.05765   |                  0.09472  |                   2.311   |
| pedestal_band   | low     | bayesian_deltae_template_likelihood |                  0.7082 |                  0.1699   |         0.07692   |                  0        |                   0       |
| pedestal_band   | low     | gradient_boosted_trees              |                  0.9908 |                  0.00817  |         0.007897  |                  0.004025 |                   0.03513 |
| pedestal_band   | low     | mlp                                 |                  0.9286 |                  0.05719  |         0.03181   |                  0.138    |                   0.7736  |
| pedestal_band   | low     | multitask_waveform_transformer_new  |                  0.896  |                  0.05882  |         0.05329   |                  0.04275  |                   1.102   |
| pedestal_band   | low     | ridge                               |                  0.9047 |                  0.05882  |         0.07293   |                  0.1854   |                   0.01458 |
| pedestal_band   | mid     | 1d_cnn                              |                  0.9517 |                  0.03685  |         0.03665   |                  0.1035   |                   2.681   |
| pedestal_band   | mid     | bayesian_deltae_template_likelihood |                  0.7765 |                  0.0938   |         0.07679   |                  0        |                   0       |
| pedestal_band   | mid     | gradient_boosted_trees              |                  0.9953 |                  0.001675 |         0.003095  |                  0.004115 |                   0.03603 |
| pedestal_band   | mid     | mlp                                 |                  0.9504 |                  0.0268   |         0.01686   |                  0.1286   |                   0.7484  |
| pedestal_band   | mid     | multitask_waveform_transformer_new  |                  0.8726 |                  0.04523  |         0.03524   |                  0.04308  |                   1.188   |
| pedestal_band   | mid     | ridge                               |                  0.9262 |                  0.03015  |         0.03999   |                  0.1979   |                   0.01418 |
| saturation_mask | 0       | 1d_cnn                              |                  0.9524 |                  0.04278  |         0.0299    |                  0.1393   |                   3.073   |
| saturation_mask | 0       | bayesian_deltae_template_likelihood |                  0.7846 |                  0.1122   |         0.06183   |                  0        |                   0       |
| saturation_mask | 0       | gradient_boosted_trees              |                  0.9938 |                  0.004444 |         0.003733  |                  0.004514 |                   0.04307 |
| saturation_mask | 0       | mlp                                 |                  0.9459 |                  0.03778  |         0.01303   |                  0.1437   |                   0.8289  |
| saturation_mask | 0       | multitask_waveform_transformer_new  |                  0.8984 |                  0.05056  |         0.03471   |                  0.05716  |                   1.449   |
| saturation_mask | 0       | ridge                               |                  0.9281 |                  0.03889  |         0.0411    |                  0.2279   |                   0.01508 |

## Systematics and Caveats

This is not a particle-truth PID measurement.  It tests stability of a
train-frozen raw deltaE/E-depth boundary under method substitution.  A model can
win the benchmark by reproducing the frozen boundary while still being
unvalidated for physical proton/deuteron classification.  The main systematic is
support leakage through charge and depth, mitigated here by run-held-out splits,
train-only threshold freezing, and pedestal/saturation sideband tables.  The
bootstrap intervals resample held-out runs and therefore cover run-transfer
instability, not the uncertainty of the weak-label definition, detector material
model, or external beam composition.  Saturation is represented by a corrected
peak threshold above 14000 ADC; pile-up sensitivity is approximated by the late
charge tail and cannot replace a two-pulse hand-scan label.

Runtime was `71.4` s on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid` with git commit
`aff63eae22303a09a488511c6fed4a54ae3c2fed`.

## Follow-up Ticket

One novel follow-up was appended: #2480, `S54d: external PID truth join for S54c boundary validation`.
