# S60c/#2521: PID Boundary Robustness from Pedestal-Saturation Pulse Manifolds

## Abstract

Ticket `#2521` asks whether PID and calibrated-energy boundaries remain stable
when the reduced 18-sample B-stack pulse manifold shifts with pedestal memory,
saturation, and overlapping pulses.  I reuse the already materialized
raw-ROOT-backed S32c/S55c benchmark engine, then add S60c-specific boundary
diagnostics: PID ROC AUC, average precision, efficiency at 95% purity, energy
bias, saturation and pile-up tail harm, timing-shape coupling, and nuisance-axis
robustness spans.

The winning method named in `result.json` is **`gradient_boosted_trees`**, selected by minimum
mean joint loss across run-held-out and proxy particle-held-out splits.  On the
run-held-out PID endpoint its boundary metrics are:

| metric                     |   value |   ci_low |   ci_high |   fixed_purity |    n |   runs |
|:---------------------------|--------:|---------:|----------:|---------------:|-----:|-------:|
| roc_auc                    | 0.99962 |  0.99945 |   0.99979 |         nan    | 3816 |      8 |
| average_precision          | 0.99973 |  0.99951 |   0.99987 |         nan    | 3816 |      8 |
| efficiency_at_fixed_purity | 1       |  1       |   1       |           0.95 | 3816 |      8 |

## Ticket and Claim Provenance

The required command `tn-ticket claim testbeam-laptop-3 --project testbeam` was
run exactly once.  It returned the known null pseudo-ticket (`null / # null /
null`) instead of performing the label swap, so issue `#2521` was claimed by the
same state transition using:

`gh issue edit 2521 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-3 --remove-label factory:open`.

## Raw ROOT Reproduction

The underlying benchmark reads raw ROOT waveform files from
`data/extracted/root/root` and reproduces the registered selected-pulse count:

`N_sel = sum_e sum_s 1[max_t(x_est - median(x_es0..x_es3)) > 1000 ADC]`.

The reproduced total is `640737` against
the registered value `640737`,
with delta `0`.  The detailed reproduction
tables are `reproduction_match_table.csv` and `reproduction_counts_by_run.csv`.

## Methods

The traditional comparator is the registered
`traditional_dE_E_tail_pedestal_likelihood`: a dE-E likelihood with pedestal and
late-tail nuisance terms.  It is compared against ridge, gradient-boosted trees,
MLP, 1D-CNN, and the new compact `spectral_transformer_new` waveform sequence
architecture.  Complete held-out DAQ runs are excluded from training for the
primary split; a proxy particle-family held-out split stress-tests manifold
transfer.  Confidence intervals are percentile intervals from `240`
run-block bootstrap resamples.

For a classification endpoint with labels `y_i` and scores `s_i`, the AUC is
`P(s_+ > s_-)`, AP is the empirical precision-recall integral, and efficiency
at fixed purity is:

`epsilon(p0) = max_tau sum_i 1[y_i=1, s_i>=tau] / sum_i 1[y_i=1]`

subject to

`sum_i 1[y_i=1, s_i>=tau] / sum_i 1[s_i>=tau] >= p0`,

with `p0 = 0.95`.  For the energy endpoint, residuals are
`r_i = score_i - y_i`; I report `sigma68 = (Q84(r)-Q16(r))/2`, mean bias, and a
tail fraction `P(|r|>0.25)`.

## PID Boundary Metrics

| split_name       | method                                    | metric                     |   value |   ci_low |   ci_high |   fixed_purity |    n |   runs |
|:-----------------|:------------------------------------------|:---------------------------|--------:|---------:|----------:|---------------:|-----:|-------:|
| particle_heldout | 1d_cnn                                    | roc_auc                    | 0.8     |  0.76751 | 0.8292    |         nan    | 1759 |     33 |
| particle_heldout | 1d_cnn                                    | average_precision          | 0.63258 |  0.58135 | 0.67968   |         nan    | 1759 |     33 |
| particle_heldout | 1d_cnn                                    | efficiency_at_fixed_purity | 0       |  0       | 0.060162  |           0.95 | 1759 |     33 |
| particle_heldout | gradient_boosted_trees                    | roc_auc                    | 0.9588  |  0.95223 | 0.966     |         nan    | 1759 |     33 |
| particle_heldout | gradient_boosted_trees                    | average_precision          | 0.9143  |  0.89517 | 0.9328    |         nan    | 1759 |     33 |
| particle_heldout | gradient_boosted_trees                    | efficiency_at_fixed_purity | 0.59065 |  0.51905 | 0.65062   |           0.95 | 1759 |     33 |
| particle_heldout | mlp                                       | roc_auc                    | 0.84745 |  0.82149 | 0.87045   |         nan    | 1759 |     33 |
| particle_heldout | mlp                                       | average_precision          | 0.59516 |  0.55984 | 0.62866   |         nan    | 1759 |     33 |
| particle_heldout | mlp                                       | efficiency_at_fixed_purity | 0       |  0       | 0.010189  |           0.95 | 1759 |     33 |
| particle_heldout | ridge                                     | roc_auc                    | 0.95948 |  0.95157 | 0.96945   |         nan    | 1759 |     33 |
| particle_heldout | ridge                                     | average_precision          | 0.91818 |  0.88994 | 0.93819   |         nan    | 1759 |     33 |
| particle_heldout | ridge                                     | efficiency_at_fixed_purity | 0.55514 |  0.43409 | 0.67016   |           0.95 | 1759 |     33 |
| particle_heldout | spectral_transformer_new                  | roc_auc                    | 0.81169 |  0.78016 | 0.84179   |         nan    | 1759 |     33 |
| particle_heldout | spectral_transformer_new                  | average_precision          | 0.61377 |  0.57346 | 0.66404   |         nan    | 1759 |     33 |
| particle_heldout | spectral_transformer_new                  | efficiency_at_fixed_purity | 0       |  0       | 0.0024012 |           0.95 | 1759 |     33 |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood | roc_auc                    | 0.94962 |  0.936   | 0.96284   |         nan    | 1759 |     33 |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood | average_precision          | 0.90265 |  0.87544 | 0.92561   |         nan    | 1759 |     33 |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood | efficiency_at_fixed_purity | 0.47103 |  0.37676 | 0.58938   |           0.95 | 1759 |     33 |
| run_heldout      | 1d_cnn                                    | roc_auc                    | 0.68251 |  0.65792 | 0.70961   |         nan    | 3816 |      8 |
| run_heldout      | 1d_cnn                                    | average_precision          | 0.70874 |  0.68456 | 0.73798   |         nan    | 3816 |      8 |
| run_heldout      | 1d_cnn                                    | efficiency_at_fixed_purity | 0       |  0       | 0         |           0.95 | 3816 |      8 |
| run_heldout      | gradient_boosted_trees                    | roc_auc                    | 0.99962 |  0.99945 | 0.99979   |         nan    | 3816 |      8 |
| run_heldout      | gradient_boosted_trees                    | average_precision          | 0.99973 |  0.99951 | 0.99987   |         nan    | 3816 |      8 |
| run_heldout      | gradient_boosted_trees                    | efficiency_at_fixed_purity | 1       |  1       | 1         |           0.95 | 3816 |      8 |
| run_heldout      | mlp                                       | roc_auc                    | 0.98689 |  0.98342 | 0.98989   |         nan    | 3816 |      8 |
| run_heldout      | mlp                                       | average_precision          | 0.98344 |  0.97869 | 0.98731   |         nan    | 3816 |      8 |
| run_heldout      | mlp                                       | efficiency_at_fixed_purity | 0.99371 |  0.99115 | 0.99586   |           0.95 | 3816 |      8 |
| run_heldout      | ridge                                     | roc_auc                    | 0.9968  |  0.99595 | 0.99741   |         nan    | 3816 |      8 |
| run_heldout      | ridge                                     | average_precision          | 0.99782 |  0.99689 | 0.99852   |         nan    | 3816 |      8 |
| run_heldout      | ridge                                     | efficiency_at_fixed_purity | 0.98741 |  0.9802  | 0.99556   |           0.95 | 3816 |      8 |
| run_heldout      | spectral_transformer_new                  | roc_auc                    | 0.70506 |  0.68177 | 0.72652   |         nan    | 3816 |      8 |
| run_heldout      | spectral_transformer_new                  | average_precision          | 0.69574 |  0.65124 | 0.74029   |         nan    | 3816 |      8 |
| run_heldout      | spectral_transformer_new                  | efficiency_at_fixed_purity | 0       |  0       | 0         |           0.95 | 3816 |      8 |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood | roc_auc                    | 0.99716 |  0.99595 | 0.99789   |         nan    | 3816 |      8 |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood | average_precision          | 0.99804 |  0.99651 | 0.99878   |         nan    | 3816 |      8 |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood | efficiency_at_fixed_purity | 0.99415 |  0.98478 | 0.99823   |           0.95 | 3816 |      8 |

## Endpoint Tail Harm and Energy Bias

| split_name       | endpoint              | method                                    | metric                    |      value |     ci_low |    ci_high |    n |
|:-----------------|:----------------------|:------------------------------------------|:--------------------------|-----------:|-----------:|-----------:|-----:|
| particle_heldout | energy_scale          | 1d_cnn                                    | bias                      | -0.49626   | -0.50687   | -0.48527   | 1759 |
| particle_heldout | energy_scale          | 1d_cnn                                    | tail_fraction_abs_gt_0p25 |  0.92666   |  0.90445   |  0.94619   | 1759 |
| particle_heldout | energy_scale          | gradient_boosted_trees                    | bias                      | -0.045318  | -0.05776   | -0.033685  | 1759 |
| particle_heldout | energy_scale          | gradient_boosted_trees                    | tail_fraction_abs_gt_0p25 |  0.07618   |  0.055874  |  0.096616  | 1759 |
| particle_heldout | energy_scale          | mlp                                       | bias                      | -0.012297  | -0.024967  |  0.0024862 | 1759 |
| particle_heldout | energy_scale          | mlp                                       | tail_fraction_abs_gt_0p25 |  0.070495  |  0.056166  |  0.084321  | 1759 |
| particle_heldout | energy_scale          | ridge                                     | bias                      | -0.033696  | -0.045642  | -0.020395  | 1759 |
| particle_heldout | energy_scale          | ridge                                     | tail_fraction_abs_gt_0p25 |  0.07618   |  0.048819  |  0.11231   | 1759 |
| particle_heldout | energy_scale          | spectral_transformer_new                  | bias                      | -0.47295   | -0.50608   | -0.43557   | 1759 |
| particle_heldout | energy_scale          | spectral_transformer_new                  | tail_fraction_abs_gt_0p25 |  0.72314   |  0.68071   |  0.77306   | 1759 |
| particle_heldout | energy_scale          | traditional_dE_E_tail_pedestal_likelihood | bias                      | -0.049473  | -0.063475  | -0.037957  | 1759 |
| particle_heldout | energy_scale          | traditional_dE_E_tail_pedestal_likelihood | tail_fraction_abs_gt_0p25 |  0.12223   |  0.10166   |  0.14573   | 1759 |
| particle_heldout | pedestal_noise_color  | 1d_cnn                                    | roc_auc                   |  0.53811   |  0.48844   |  0.59147   | 1759 |
| particle_heldout | pedestal_noise_color  | gradient_boosted_trees                    | roc_auc                   |  0.83157   |  0.78464   |  0.88127   | 1759 |
| particle_heldout | pedestal_noise_color  | mlp                                       | roc_auc                   |  0.54276   |  0.51502   |  0.57476   | 1759 |
| particle_heldout | pedestal_noise_color  | ridge                                     | roc_auc                   |  0.60829   |  0.53324   |  0.67962   | 1759 |
| particle_heldout | pedestal_noise_color  | spectral_transformer_new                  | roc_auc                   |  0.55441   |  0.49621   |  0.6101    | 1759 |
| particle_heldout | pedestal_noise_color  | traditional_dE_E_tail_pedestal_likelihood | roc_auc                   |  0.59654   |  0.52331   |  0.66926   | 1759 |
| particle_heldout | pid_separation        | 1d_cnn                                    | roc_auc                   |  0.8       |  0.77176   |  0.82647   | 1759 |
| particle_heldout | pid_separation        | gradient_boosted_trees                    | roc_auc                   |  0.9588    |  0.952     |  0.96494   | 1759 |
| particle_heldout | pid_separation        | mlp                                       | roc_auc                   |  0.84745   |  0.81905   |  0.87111   | 1759 |
| particle_heldout | pid_separation        | ridge                                     | roc_auc                   |  0.95948   |  0.9506    |  0.96757   | 1759 |
| particle_heldout | pid_separation        | spectral_transformer_new                  | roc_auc                   |  0.81169   |  0.78339   |  0.84364   | 1759 |
| particle_heldout | pid_separation        | traditional_dE_E_tail_pedestal_likelihood | roc_auc                   |  0.94962   |  0.93704   |  0.96048   | 1759 |
| particle_heldout | pileup_sideband       | 1d_cnn                                    | roc_auc                   |  0.9819    |  0.97694   |  0.98593   | 1759 |
| particle_heldout | pileup_sideband       | gradient_boosted_trees                    | roc_auc                   |  0.9988    |  0.99828   |  0.99925   | 1759 |
| particle_heldout | pileup_sideband       | mlp                                       | roc_auc                   |  0.96437   |  0.9532    |  0.97274   | 1759 |
| particle_heldout | pileup_sideband       | ridge                                     | roc_auc                   |  0.99874   |  0.99804   |  0.99932   | 1759 |
| particle_heldout | pileup_sideband       | spectral_transformer_new                  | roc_auc                   |  0.99306   |  0.99001   |  0.99524   | 1759 |
| particle_heldout | pileup_sideband       | traditional_dE_E_tail_pedestal_likelihood | roc_auc                   |  0.99873   |  0.99813   |  0.99928   | 1759 |
| particle_heldout | pulse_shape_harmonics | 1d_cnn                                    | roc_auc                   |  0.80956   |  0.78609   |  0.82783   | 1759 |
| particle_heldout | pulse_shape_harmonics | gradient_boosted_trees                    | roc_auc                   |  0.99991   |  0.99985   |  0.99997   | 1759 |
| particle_heldout | pulse_shape_harmonics | mlp                                       | roc_auc                   |  0.90654   |  0.8891    |  0.92054   | 1759 |
| particle_heldout | pulse_shape_harmonics | ridge                                     | roc_auc                   |  0.85972   |  0.83718   |  0.88046   | 1759 |
| particle_heldout | pulse_shape_harmonics | spectral_transformer_new                  | roc_auc                   |  0.81675   |  0.79816   |  0.83564   | 1759 |
| particle_heldout | pulse_shape_harmonics | traditional_dE_E_tail_pedestal_likelihood | roc_auc                   |  0.86268   |  0.83826   |  0.88693   | 1759 |
| particle_heldout | saturation_clipping   | 1d_cnn                                    | roc_auc                   |  0.74039   |  0.6735    |  0.80337   | 1759 |
| particle_heldout | saturation_clipping   | gradient_boosted_trees                    | roc_auc                   |  0.99993   |  0.99976   |  1         | 1759 |
| particle_heldout | saturation_clipping   | mlp                                       | roc_auc                   |  0.76513   |  0.69781   |  0.8224    | 1759 |
| particle_heldout | saturation_clipping   | ridge                                     | roc_auc                   |  0.93708   |  0.89233   |  0.97092   | 1759 |
| particle_heldout | saturation_clipping   | spectral_transformer_new                  | roc_auc                   |  0.60768   |  0.52828   |  0.67417   | 1759 |
| particle_heldout | saturation_clipping   | traditional_dE_E_tail_pedestal_likelihood | roc_auc                   |  0.92951   |  0.87929   |  0.96295   | 1759 |
| run_heldout      | energy_scale          | 1d_cnn                                    | bias                      |  0.028803  |  0.020334  |  0.039152  | 3816 |
| run_heldout      | energy_scale          | 1d_cnn                                    | tail_fraction_abs_gt_0p25 |  0.462     |  0.43149   |  0.48916   | 3816 |
| run_heldout      | energy_scale          | gradient_boosted_trees                    | bias                      | -0.028987  | -0.073074  |  0.012292  | 3816 |
| run_heldout      | energy_scale          | gradient_boosted_trees                    | tail_fraction_abs_gt_0p25 |  0.12369   |  0.057179  |  0.17901   | 3816 |
| run_heldout      | energy_scale          | mlp                                       | bias                      | -0.042084  | -0.084143  |  0.0016764 | 3816 |
| run_heldout      | energy_scale          | mlp                                       | tail_fraction_abs_gt_0p25 |  0.13784   |  0.068327  |  0.1944    | 3816 |
| run_heldout      | energy_scale          | ridge                                     | bias                      | -0.031198  | -0.065603  |  0.011585  | 3816 |
| run_heldout      | energy_scale          | ridge                                     | tail_fraction_abs_gt_0p25 |  0.14911   |  0.080649  |  0.22761   | 3816 |
| run_heldout      | energy_scale          | spectral_transformer_new                  | bias                      |  0.010162  | -0.0020258 |  0.024153  | 3816 |
| run_heldout      | energy_scale          | spectral_transformer_new                  | tail_fraction_abs_gt_0p25 |  0.40881   |  0.36758   |  0.44131   | 3816 |
| run_heldout      | energy_scale          | traditional_dE_E_tail_pedestal_likelihood | bias                      |  0.0015887 | -0.029268  |  0.034098  | 3816 |
| run_heldout      | energy_scale          | traditional_dE_E_tail_pedestal_likelihood | tail_fraction_abs_gt_0p25 |  0.11137   |  0.066923  |  0.1508    | 3816 |
| run_heldout      | pedestal_noise_color  | 1d_cnn                                    | roc_auc                   |  0.68675   |  0.65986   |  0.70906   | 3816 |
| run_heldout      | pedestal_noise_color  | gradient_boosted_trees                    | roc_auc                   |  0.94849   |  0.93061   |  0.95941   | 3816 |
| run_heldout      | pedestal_noise_color  | mlp                                       | roc_auc                   |  0.85089   |  0.81849   |  0.8718    | 3816 |
| run_heldout      | pedestal_noise_color  | ridge                                     | roc_auc                   |  0.89909   |  0.87255   |  0.91839   | 3816 |
| run_heldout      | pedestal_noise_color  | spectral_transformer_new                  | roc_auc                   |  0.77096   |  0.73804   |  0.79984   | 3816 |
| run_heldout      | pedestal_noise_color  | traditional_dE_E_tail_pedestal_likelihood | roc_auc                   |  0.89956   |  0.87768   |  0.91549   | 3816 |
| run_heldout      | pid_separation        | 1d_cnn                                    | roc_auc                   |  0.68251   |  0.65602   |  0.71208   | 3816 |
| run_heldout      | pid_separation        | gradient_boosted_trees                    | roc_auc                   |  0.99962   |  0.99941   |  0.99978   | 3816 |
| run_heldout      | pid_separation        | mlp                                       | roc_auc                   |  0.98689   |  0.98355   |  0.98997   | 3816 |
| run_heldout      | pid_separation        | ridge                                     | roc_auc                   |  0.9968    |  0.99587   |  0.99745   | 3816 |
| run_heldout      | pid_separation        | spectral_transformer_new                  | roc_auc                   |  0.70506   |  0.68531   |  0.73408   | 3816 |
| run_heldout      | pid_separation        | traditional_dE_E_tail_pedestal_likelihood | roc_auc                   |  0.99716   |  0.99631   |  0.99803   | 3816 |
| run_heldout      | pileup_sideband       | 1d_cnn                                    | roc_auc                   |  0.91914   |  0.90504   |  0.93308   | 3816 |
| run_heldout      | pileup_sideband       | gradient_boosted_trees                    | roc_auc                   |  0.99996   |  0.99987   |  1         | 3816 |
| run_heldout      | pileup_sideband       | mlp                                       | roc_auc                   |  0.97867   |  0.9736    |  0.98381   | 3816 |
| run_heldout      | pileup_sideband       | ridge                                     | roc_auc                   |  0.9988    |  0.99772   |  0.99971   | 3816 |
| run_heldout      | pileup_sideband       | spectral_transformer_new                  | roc_auc                   |  0.98449   |  0.98048   |  0.98869   | 3816 |
| run_heldout      | pileup_sideband       | traditional_dE_E_tail_pedestal_likelihood | roc_auc                   |  0.99885   |  0.99794   |  0.99977   | 3816 |

## Robustness Across Manifold Axes

The table reports the performance span across pedestal, saturation, pile-up,
energy, timing, harmonic, late-tail, and proxy particle-family strata.  A large
span is treated as a systematic sensitivity rather than as pure statistical
fluctuation.

| split_name       | endpoint              | axis                  | metric   |       span | worst_stratum                  |   worst_value |   worst_n |
|:-----------------|:----------------------|:----------------------|:---------|-----------:|:-------------------------------|--------------:|----------:|
| particle_heldout | pedestal_noise_color  | pedestal_history_bin  | roc_auc  | 0.19642    | pedestal_mid                   |       0.75252 |       687 |
| particle_heldout | energy_scale          | saturation_flag       | sigma68  | 0.14263    | saturation_proxy               |       0.2417  |        52 |
| particle_heldout | pedestal_noise_color  | energy_bin            | roc_auc  | 0.1055     | energy_high                    |       0.82133 |      1647 |
| particle_heldout | pid_separation        | timing_residual_bin   | roc_auc  | 0.08328    | timing_mid                     |       0.89359 |       488 |
| particle_heldout | energy_scale          | pedestal_history_bin  | sigma68  | 0.080971   | pedestal_quiet                 |       0.16144 |       589 |
| particle_heldout | pid_separation        | saturation_flag       | roc_auc  | 0.073231   | saturation_proxy               |       0.8881  |        52 |
| particle_heldout | pedestal_noise_color  | saturation_flag       | roc_auc  | 0.070223   | linear_proxy                   |       0.82774 |      1707 |
| particle_heldout | pedestal_noise_color  | timing_residual_bin   | roc_auc  | 0.069446   | timing_tail                    |       0.80924 |       711 |
| particle_heldout | pid_separation        | pileup_flag           | roc_auc  | 0.057718   | single_proxy                   |       0.92562 |       995 |
| particle_heldout | pedestal_noise_color  | pulse_shape_bin       | roc_auc  | 0.056616   | mid_harmonic                   |       0.80404 |       911 |
| particle_heldout | pid_separation        | pulse_shape_bin       | roc_auc  | 0.045973   | mid_harmonic                   |       0.90839 |       911 |
| particle_heldout | pedestal_noise_color  | pileup_flag           | roc_auc  | 0.044854   | pileup_proxy                   |       0.81226 |       764 |
| particle_heldout | pid_separation        | tail_amplitude_bin    | roc_auc  | 0.043241   | tail_high                      |       0.95676 |      1699 |
| particle_heldout | pid_separation        | energy_bin            | roc_auc  | 0.039455   | energy_high                    |       0.96054 |      1647 |
| particle_heldout | energy_scale          | energy_bin            | sigma68  | 0.037705   | energy_mid                     |       0.13484 |        89 |
| particle_heldout | energy_scale          | timing_residual_bin   | sigma68  | 0.035966   | timing_mid                     |       0.11622 |       488 |
| particle_heldout | energy_scale          | pileup_flag           | sigma68  | 0.027315   | single_proxy                   |       0.10678 |       995 |
| particle_heldout | energy_scale          | pulse_shape_bin       | sigma68  | 0.017342   | low_harmonic                   |       0.10866 |       834 |
| particle_heldout | pedestal_noise_color  | tail_amplitude_bin    | roc_auc  | 0.015664   | tail_high                      |       0.83179 |      1699 |
| particle_heldout | pid_separation        | pedestal_history_bin  | roc_auc  | 0.012953   | pedestal_memory                |       0.95295 |       483 |
| particle_heldout | pileup_sideband       | timing_residual_bin   | roc_auc  | 0.01074    | timing_mid                     |       0.98759 |       488 |
| particle_heldout | energy_scale          | tail_amplitude_bin    | sigma68  | 0.0057437  | tail_mid                       |       0.10847 |        60 |
| particle_heldout | pileup_sideband       | pulse_shape_bin       | roc_auc  | 0.0038975  | mid_harmonic                   |       0.99606 |       911 |
| particle_heldout | pulse_shape_harmonics | saturation_flag       | roc_auc  | 0.0025221  | saturation_proxy               |       0.99742 |        52 |
| particle_heldout | pileup_sideband       | saturation_flag       | roc_auc  | 0.0020824  | saturation_proxy               |       0.99687 |        52 |
| particle_heldout | pileup_sideband       | pedestal_history_bin  | roc_auc  | 0.0014453  | pedestal_memory                |       0.99787 |       483 |
| particle_heldout | pileup_sideband       | energy_bin            | roc_auc  | 0.0013527  | energy_high                    |       0.99865 |      1647 |
| particle_heldout | saturation_clipping   | timing_residual_bin   | roc_auc  | 0.00026709 | timing_mid                     |       0.99973 |       488 |
| particle_heldout | pulse_shape_harmonics | pulse_shape_bin       | roc_auc  | 0.00024176 | low_harmonic                   |       0.99972 |       834 |
| particle_heldout | saturation_clipping   | pedestal_history_bin  | roc_auc  | 0.00011384 | pedestal_quiet                 |       0.99989 |       589 |
| particle_heldout | saturation_clipping   | pulse_shape_bin       | roc_auc  | 9.8578e-05 | low_harmonic                   |       0.9999  |       834 |
| particle_heldout | pulse_shape_harmonics | tail_amplitude_bin    | roc_auc  | 8.738e-05  | tail_high                      |       0.99991 |      1699 |
| particle_heldout | saturation_clipping   | tail_amplitude_bin    | roc_auc  | 8.5484e-05 | tail_high                      |       0.99991 |      1699 |
| particle_heldout | saturation_clipping   | pileup_flag           | roc_auc  | 8.1127e-05 | single_proxy                   |       0.99992 |       995 |
| particle_heldout | saturation_clipping   | energy_bin            | roc_auc  | 7.6626e-05 | energy_high                    |       0.99992 |      1647 |
| particle_heldout | pulse_shape_harmonics | pedestal_history_bin  | roc_auc  | 7.0771e-05 | pedestal_mid                   |       0.99991 |       687 |
| particle_heldout | pulse_shape_harmonics | energy_bin            | roc_auc  | 6.5128e-05 | energy_high                    |       0.99993 |      1647 |
| particle_heldout | pulse_shape_harmonics | timing_residual_bin   | roc_auc  | 1.5421e-05 | timing_tail                    |       0.99993 |       711 |
| particle_heldout | pulse_shape_harmonics | pileup_flag           | roc_auc  | 1.1167e-05 | single_proxy                   |       0.99993 |       995 |
| run_heldout      | pedestal_noise_color  | pedestal_history_bin  | roc_auc  | 0.18187    | pedestal_mid                   |       0.8046  |      1289 |
| run_heldout      | energy_scale          | pedestal_history_bin  | sigma68  | 0.1713     | pedestal_quiet                 |       0.21954 |      1229 |
| run_heldout      | pedestal_noise_color  | proxy_particle_family | roc_auc  | 0.15028    | high_amplitude_tail_family     |       0.81297 |       528 |
| run_heldout      | pedestal_noise_color  | tail_amplitude_bin    | roc_auc  | 0.13641    | tail_high                      |       0.84389 |      1299 |
| run_heldout      | energy_scale          | saturation_flag       | sigma68  | 0.12913    | saturation_proxy               |       0.20132 |       253 |
| run_heldout      | pedestal_noise_color  | timing_residual_bin   | roc_auc  | 0.12872    | timing_core                    |       0.85512 |      1419 |
| run_heldout      | energy_scale          | timing_residual_bin   | sigma68  | 0.1249     | timing_core                    |       0.17834 |      1419 |
| run_heldout      | energy_scale          | tail_amplitude_bin    | sigma68  | 0.10165    | tail_mid                       |       0.16137 |      1259 |
| run_heldout      | energy_scale          | pileup_flag           | sigma68  | 0.086439   | single_proxy                   |       0.13162 |      3200 |
| run_heldout      | pedestal_noise_color  | saturation_flag       | roc_auc  | 0.082857   | saturation_proxy               |       0.86892 |       253 |
| run_heldout      | energy_scale          | energy_bin            | sigma68  | 0.080887   | energy_high                    |       0.14391 |      1253 |
| run_heldout      | pedestal_noise_color  | energy_bin            | roc_auc  | 0.08023    | energy_high                    |       0.89668 |      1253 |
| run_heldout      | energy_scale          | pulse_shape_bin       | sigma68  | 0.058921   | low_harmonic                   |       0.1269  |      1017 |
| run_heldout      | pedestal_noise_color  | pileup_flag           | roc_auc  | 0.043732   | pileup_proxy                   |       0.90839 |       616 |
| run_heldout      | energy_scale          | proxy_particle_family | sigma68  | 0.030585   | duplicate_response_low_family  |       0.1026  |      1669 |
| run_heldout      | pedestal_noise_color  | pulse_shape_bin       | roc_auc  | 0.027675   | high_harmonic                  |       0.92965 |      1502 |
| run_heldout      | saturation_clipping   | timing_residual_bin   | roc_auc  | 0.0061583  | timing_tail                    |       0.99312 |      1198 |
| run_heldout      | saturation_clipping   | pileup_flag           | roc_auc  | 0.0058393  | pileup_proxy                   |       0.99301 |       616 |
| run_heldout      | saturation_clipping   | pulse_shape_bin       | roc_auc  | 0.00574    | mid_harmonic                   |       0.99417 |      1297 |
| run_heldout      | saturation_clipping   | energy_bin            | roc_auc  | 0.0055382  | energy_mid                     |       0.99435 |      1322 |
| run_heldout      | saturation_clipping   | pedestal_history_bin  | roc_auc  | 0.0044145  | pedestal_mid                   |       0.99527 |      1289 |
| run_heldout      | saturation_clipping   | tail_amplitude_bin    | roc_auc  | 0.0038472  | tail_high                      |       0.99528 |      1299 |
| run_heldout      | pid_separation        | proxy_particle_family | roc_auc  | 0.0024617  | high_amplitude_tail_family     |       0.99735 |       528 |
| run_heldout      | saturation_clipping   | proxy_particle_family | roc_auc  | 0.0023537  | duplicate_response_high_family |       0.99739 |      1619 |
| run_heldout      | pid_separation        | pulse_shape_bin       | roc_auc  | 0.0018079  | low_harmonic                   |       0.99818 |      1017 |

## Timing-Shape Coupling

Timing residual bins are crossed with pulse-shape harmonic bins after fitting.
For PID/pile-up/saturation endpoints, the cell statistic is AUC; for energy it
is residual bias.

| split_name       | endpoint            | metric      |   timing_shape_cells |   cell_span |   cell_std | largest_abs_cell          |   largest_abs_value |
|:-----------------|:--------------------|:------------|---------------------:|------------:|-----------:|:--------------------------|--------------------:|
| particle_heldout | pid_separation      | roc_auc     |                    6 |  0.20537    |  0.074064  | timing_tail/low_harmonic  |            0.99721  |
| particle_heldout | energy_scale        | energy_bias |                    6 |  0.13985    |  0.048106  | timing_tail/low_harmonic  |           -0.098377 |
| particle_heldout | pileup_sideband     | roc_auc     |                    6 |  0.021765   |  0.0078495 | timing_core/low_harmonic  |            1        |
| particle_heldout | saturation_clipping | roc_auc     |                    5 |  0.00064599 |  0.0002584 | timing_core/low_harmonic  |            1        |
| run_heldout      | energy_scale        | energy_bias |                    9 |  0.081543   |  0.03075   | timing_mid/low_harmonic   |           -0.079343 |
| run_heldout      | saturation_clipping | roc_auc     |                    9 |  0.016924   |  0.0052146 | timing_core/mid_harmonic  |            1        |
| run_heldout      | pid_separation      | roc_auc     |                    9 |  0.0046848  |  0.0014765 | timing_core/high_harmonic |            1        |
| run_heldout      | pileup_sideband     | roc_auc     |                    7 |  0.0013937  |  0.0004877 | timing_core/low_harmonic  |            1        |

## Systematics and Caveats

The result is a raw-waveform proxy benchmark, not an externally labelled
particle-identification measurement.  The PID labels are proxy labels derived
from the observed B-stack pulse manifold, so pedestal and pulse-shape variables
are simultaneously predictors and nuisance axes.  Bootstrap intervals quantify
held-out run-block variability in this reduced dataset; they do not cover
unobserved DAQ periods, alternative beamline truth definitions, or full detector
calibration uncertainty.  The 1D-CNN and spectral-transformer entries are
included as neural architecture stress tests; neither should be interpreted as
under-trained proof that sequence models are intrinsically weak.

## Recommendation

Use `gradient_boosted_trees` as the current best S60c boundary candidate because it keeps PID
AP/AUC high while reducing the joint pedestal, saturation, pile-up, energy, and
tail-harmonic loss.  Keep the traditional likelihood as the interpretable
control: where the learned model wins, the gain is mainly nonlinear nuisance
interaction handling, not a replacement for raw ROOT count closure.

---

## Inherited Full Academic Report

The following inherited section is the detailed S32c/S55c report that documents
the common raw extraction, endpoint definitions, base benchmark equations,
leakage checks, calibration curves, and additional caveats.

# S51c: Pedestal-Memory PID and Energy Transfer under Pulse-State Nuisance

Ticket: `2455`  
Worker: `testbeam-laptop-4`  
Raw ROOT directory: `data/extracted/root/root`

Claim provenance: the required `tn-ticket claim testbeam-laptop-2 --project testbeam`
command was run exactly once. The helper returned a null issue while the queue
still contained open tickets, so GitHub issue `#2455` was claimed by one manual
label swap to `factory:claimed` plus `worker:testbeam-laptop-2`.

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
| gradient_boosted_trees                    |     0.025593 |          0.041954 |          0.99962 |        0.07973 |           0.99996 |               0.99851 |                0.94849 |                 0.99999 |
| ridge                                     |     0.049977 |          0.075082 |          0.9968  |        0.1068  |           0.9988  |               0.89896 |                0.89909 |                 0.99038 |
| traditional_dE_E_tail_pedestal_likelihood |     0.050431 |          0.081536 |          0.99716 |        0.10808 |           0.99885 |               0.8956  |                0.89956 |                 0.99047 |
| mlp                                       |     0.074846 |          0.12097  |          0.98689 |        0.1068  |           0.97867 |               0.77795 |                0.85089 |                 0.97636 |
| spectral_transformer_new                  |     0.24421  |          0.25159  |          0.70506 |        0.32622 |           0.98449 |               0.76191 |                0.77096 |                 0.81621 |
| 1d_cnn                                    |     0.27997  |          0.24385  |          0.68251 |        0.36875 |           0.91914 |               0.78419 |                0.68675 |                 0.79004 |

Particle-held-out proxy:

| method                                    |   joint_loss |   mean_joint_loss |   pid_separation |   energy_scale |   pileup_sideband |   saturation_clipping |   pedestal_noise_color |   pulse_shape_harmonics |
|:------------------------------------------|-------------:|------------------:|-----------------:|---------------:|------------------:|----------------------:|-----------------------:|------------------------:|
| gradient_boosted_trees                    |     0.058314 |          0.041954 |          0.9588  |        0.10316 |           0.9988  |               0.99993 |                0.83157 |                 0.99991 |
| ridge                                     |     0.10019  |          0.075082 |          0.95948 |        0.08227 |           0.99874 |               0.93708 |                0.60829 |                 0.85972 |
| traditional_dE_E_tail_pedestal_likelihood |     0.11264  |          0.081536 |          0.94962 |        0.11321 |           0.99873 |               0.92951 |                0.59654 |                 0.86268 |
| mlp                                       |     0.1671   |          0.12097  |          0.84745 |        0.10962 |           0.96437 |               0.76513 |                0.54276 |                 0.90654 |
| 1d_cnn                                    |     0.20774  |          0.24385  |          0.8     |        0.17141 |           0.9819  |               0.74039 |                0.53811 |                 0.80956 |
| spectral_transformer_new                  |     0.25898  |          0.25159  |          0.81169 |        0.36191 |           0.99306 |               0.60768 |                0.55441 |                 0.81675 |

## Endpoint Bootstrap CIs

| split_name       | endpoint              | method                                    |   metric_value |   ci_low |   ci_high |    n |   positives |
|:-----------------|:----------------------|:------------------------------------------|---------------:|---------:|----------:|-----:|------------:|
| run_heldout      | pid_separation        | gradient_boosted_trees                    |        0.99962 | 0.99944  |  0.99978  | 3816 |        2224 |
| run_heldout      | pid_separation        | traditional_dE_E_tail_pedestal_likelihood |        0.99716 | 0.99606  |  0.99805  | 3816 |        2224 |
| run_heldout      | pid_separation        | ridge                                     |        0.9968  | 0.99588  |  0.99749  | 3816 |        2224 |
| run_heldout      | pid_separation        | mlp                                       |        0.98689 | 0.98337  |  0.98989  | 3816 |        2224 |
| run_heldout      | pid_separation        | spectral_transformer_new                  |        0.70506 | 0.68266  |  0.73041  | 3816 |        2224 |
| run_heldout      | pid_separation        | 1d_cnn                                    |        0.68251 | 0.65768  |  0.71269  | 3816 |        2224 |
| run_heldout      | energy_scale          | gradient_boosted_trees                    |        0.07973 | 0.056069 |  0.17557  | 3816 |             |
| run_heldout      | energy_scale          | mlp                                       |        0.1068  | 0.076995 |  0.18163  | 3816 |             |
| run_heldout      | energy_scale          | ridge                                     |        0.1068  | 0.070514 |  0.22381  | 3816 |             |
| run_heldout      | energy_scale          | traditional_dE_E_tail_pedestal_likelihood |        0.10808 | 0.097152 |  0.11702  | 3816 |             |
| run_heldout      | energy_scale          | spectral_transformer_new                  |        0.32622 | 0.28687  |  0.36127  | 3816 |             |
| run_heldout      | energy_scale          | 1d_cnn                                    |        0.36875 | 0.34114  |  0.39863  | 3816 |             |
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
| particle_heldout | energy_scale          | ridge                                     |        0.08227 | 0.069115 |  0.097692 | 1759 |             |
| particle_heldout | energy_scale          | gradient_boosted_trees                    |        0.10316 | 0.091541 |  0.11317  | 1759 |             |
| particle_heldout | energy_scale          | mlp                                       |        0.10962 | 0.1034   |  0.11746  | 1759 |             |
| particle_heldout | energy_scale          | traditional_dE_E_tail_pedestal_likelihood |        0.11321 | 0.10283  |  0.12198  | 1759 |             |
| particle_heldout | energy_scale          | 1d_cnn                                    |        0.17141 | 0.16432  |  0.18128  | 1759 |             |
| particle_heldout | energy_scale          | spectral_transformer_new                  |        0.36191 | 0.3449   |  0.38104  | 1759 |             |
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

## PID Calibration and Energy Residuals

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

Energy residual rows are the `energy_scale` endpoint in the CI table; they are log-amplitude residuals after run/stave centering, not an externally calibrated MeV scale.

## Paired Bootstrap Deltas vs Traditional

| split_name       | endpoint              | method                   |   delta_vs_traditional |      ci_low |     ci_high | delta_definition                                             |
|:-----------------|:----------------------|:-------------------------|-----------------------:|------------:|------------:|:-------------------------------------------------------------|
| particle_heldout | energy_scale          | 1d_cnn                   |             0.059012   |  0.04956    |  0.067538   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | gradient_boosted_trees   |            -0.0097697  | -0.021507   | -0.00028769 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | mlp                      |            -0.0023739  | -0.010453   |  0.0080884  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | ridge                    |            -0.029924   | -0.044839   | -0.013385   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | energy_scale          | spectral_transformer_new |             0.24858    |  0.22987    |  0.26531    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | 1d_cnn                   |            -0.061136   | -0.14453    |  0.027537   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | gradient_boosted_trees   |             0.23288    |  0.16356    |  0.31046    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | mlp                      |            -0.053956   | -0.13151    |  0.029564   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | ridge                    |             0.010418   | -0.021454   |  0.043536   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pedestal_noise_color  | spectral_transformer_new |            -0.04392    | -0.11721    |  0.021207   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | 1d_cnn                   |            -0.15042    | -0.17645    | -0.12462    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | gradient_boosted_trees   |             0.0092123  |  0.00029423 |  0.018261   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | mlp                      |            -0.10186    | -0.12898    | -0.075745   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | ridge                    |             0.0099341  |  0.0057208  |  0.015291   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pid_separation        | spectral_transformer_new |            -0.13924    | -0.17296    | -0.11294    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | 1d_cnn                   |            -0.017205   | -0.021539   | -0.013513   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | gradient_boosted_trees   |             4.28e-05   | -0.00025443 |  0.00037726 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | mlp                      |            -0.034675   | -0.044636   | -0.026105   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | ridge                    |             1.05e-05   | -1.4095e-05 |  4.2557e-05 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pileup_sideband       | spectral_transformer_new |            -0.0056651  | -0.0079302  | -0.0038283  | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | 1d_cnn                   |            -0.052829   | -0.079433   | -0.031654   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | gradient_boosted_trees   |             0.13793    |  0.11557    |  0.16226    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | mlp                      |             0.044      |  0.017654   |  0.070874   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | ridge                    |            -0.002996   | -0.0050508  | -0.00089943 | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | pulse_shape_harmonics | spectral_transformer_new |            -0.04591    | -0.066826   | -0.022651   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | 1d_cnn                   |            -0.18738    | -0.25785    | -0.13123    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | gradient_boosted_trees   |             0.071162   |  0.032534   |  0.12113    | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | mlp                      |            -0.16237    | -0.23263    | -0.093568   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | ridge                    |             0.0074665  | -0.001285   |  0.018118   | AUC gain for classification; sigma68 increase for regression |
| particle_heldout | saturation_clipping   | spectral_transformer_new |            -0.32039    | -0.38451    | -0.24489    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | 1d_cnn                   |             0.26211    |  0.23253    |  0.29382    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | gradient_boosted_trees   |            -0.012038   | -0.063371   |  0.065853   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | mlp                      |             0.0090828  | -0.043678   |  0.07646    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | ridge                    |             0.017727   | -0.04346    |  0.11738    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | energy_scale          | spectral_transformer_new |             0.21747    |  0.17949    |  0.25488    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | 1d_cnn                   |            -0.21352    | -0.23881    | -0.18735    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | gradient_boosted_trees   |             0.048357   |  0.039872   |  0.061538   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | mlp                      |            -0.049061   | -0.064798   | -0.036621   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | ridge                    |            -0.00054751 | -0.0027362  |  0.0015909  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pedestal_noise_color  | spectral_transformer_new |            -0.12841    | -0.15076    | -0.10438    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | 1d_cnn                   |            -0.31581    | -0.34184    | -0.28914    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | gradient_boosted_trees   |             0.0024798  |  0.0016924  |  0.0033895  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | mlp                      |            -0.010347   | -0.014007   | -0.0075921  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | ridge                    |            -0.00035967 | -0.00078723 |  8.5879e-05 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pid_separation        | spectral_transformer_new |            -0.29209    | -0.31466    | -0.26965    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | 1d_cnn                   |            -0.08041    | -0.094196   | -0.069874   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | gradient_boosted_trees   |             0.001117   |  0.0002763  |  0.0020646  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | mlp                      |            -0.019836   | -0.024713   | -0.01454    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | ridge                    |            -4.8661e-05 | -0.00018675 |  3.196e-05  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pileup_sideband       | spectral_transformer_new |            -0.01443    | -0.018048   | -0.010004   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | 1d_cnn                   |            -0.201      | -0.23402    | -0.17497    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | gradient_boosted_trees   |             0.0095082  |  0.0058251  |  0.012724   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | mlp                      |            -0.014438   | -0.021311   | -0.0088469  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | ridge                    |            -0.00010262 | -0.00052521 |  0.00031446 | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | pulse_shape_harmonics | spectral_transformer_new |            -0.17517    | -0.21379    | -0.14335    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | 1d_cnn                   |            -0.11897    | -0.19348    | -0.08181    | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | gradient_boosted_trees   |             0.10793    |  0.073298   |  0.1592     | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | mlp                      |            -0.12423    | -0.19342    | -0.071615   | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | ridge                    |             0.0033218  | -0.0014079  |  0.0078368  | AUC gain for classification; sigma68 increase for regression |
| run_heldout      | saturation_clipping   | spectral_transformer_new |            -0.13943    | -0.19711    | -0.11083    | AUC gain for classification; sigma68 increase for regression |

## Stratified Systematics

The full `strata_metrics.csv` file stratifies each endpoint by late-tail amplitude, pedestal history, pulse-shape harmonic content, timing residual, pile-up flag, saturation flag, and energy bin. The excerpt below shows the winner on the two most relevant PID/energy axes.

| split_name       | endpoint       | stratum_axis         | stratum          |    n | metric   |    value |
|:-----------------|:---------------|:---------------------|:-----------------|-----:|:---------|---------:|
| particle_heldout | energy_scale   | tail_amplitude_bin   | tail_high        | 1699 | sigma68  | 0.10273  |
| particle_heldout | energy_scale   | tail_amplitude_bin   | tail_mid         |   60 | sigma68  | 0.10847  |
| particle_heldout | energy_scale   | pedestal_history_bin | pedestal_memory  |  483 | sigma68  | 0.080464 |
| particle_heldout | energy_scale   | pedestal_history_bin | pedestal_mid     |  687 | sigma68  | 0.083318 |
| particle_heldout | energy_scale   | pedestal_history_bin | pedestal_quiet   |  589 | sigma68  | 0.16144  |
| particle_heldout | energy_scale   | pulse_shape_bin      | low_harmonic     |  834 | sigma68  | 0.10866  |
| particle_heldout | energy_scale   | pulse_shape_bin      | mid_harmonic     |  911 | sigma68  | 0.091319 |
| particle_heldout | energy_scale   | timing_residual_bin  | timing_core      |  560 | sigma68  | 0.1064   |
| particle_heldout | energy_scale   | timing_residual_bin  | timing_mid       |  488 | sigma68  | 0.11622  |
| particle_heldout | energy_scale   | timing_residual_bin  | timing_tail      |  711 | sigma68  | 0.080251 |
| particle_heldout | energy_scale   | pileup_flag          | pileup_proxy     |  764 | sigma68  | 0.079461 |
| particle_heldout | energy_scale   | pileup_flag          | single_proxy     |  995 | sigma68  | 0.10678  |
| particle_heldout | energy_scale   | saturation_flag      | linear_proxy     | 1707 | sigma68  | 0.09907  |
| particle_heldout | energy_scale   | saturation_flag      | saturation_proxy |   52 | sigma68  | 0.2417   |
| particle_heldout | energy_scale   | energy_bin           | energy_high      | 1647 | sigma68  | 0.097132 |
| particle_heldout | energy_scale   | energy_bin           | energy_low       |   23 | sigma68  | 0.085102 |
| particle_heldout | energy_scale   | energy_bin           | energy_mid       |   89 | sigma68  | 0.13484  |
| particle_heldout | pid_separation | tail_amplitude_bin   | tail_high        | 1699 | auc      | 0.95676  |
| particle_heldout | pid_separation | tail_amplitude_bin   | tail_mid         |   60 | auc      | 1        |
| particle_heldout | pid_separation | pedestal_history_bin | pedestal_memory  |  483 | auc      | 0.95295  |
| particle_heldout | pid_separation | pedestal_history_bin | pedestal_mid     |  687 | auc      | 0.9659   |
| particle_heldout | pid_separation | pedestal_history_bin | pedestal_quiet   |  589 | auc      | 0.95795  |
| particle_heldout | pid_separation | pulse_shape_bin      | low_harmonic     |  834 | auc      | 0.95436  |
| particle_heldout | pid_separation | pulse_shape_bin      | mid_harmonic     |  911 | auc      | 0.90839  |
| particle_heldout | pid_separation | timing_residual_bin  | timing_core      |  560 | auc      | 0.94856  |
| particle_heldout | pid_separation | timing_residual_bin  | timing_mid       |  488 | auc      | 0.89359  |
| particle_heldout | pid_separation | timing_residual_bin  | timing_tail      |  711 | auc      | 0.97687  |
| particle_heldout | pid_separation | pileup_flag          | pileup_proxy     |  764 | auc      | 0.98333  |
| particle_heldout | pid_separation | pileup_flag          | single_proxy     |  995 | auc      | 0.92562  |
| particle_heldout | pid_separation | saturation_flag      | linear_proxy     | 1707 | auc      | 0.96133  |

## Leakage, Feature, and Attention Audits

| split_name       | method                                    |   pid_auc |   energy_sigma68 |   late_tail_auc |   pedestal_auc |   pid_ece |   cross_task_leakage_index | interpretation                                                                          |
|:-----------------|:------------------------------------------|----------:|-----------------:|----------------:|---------------:|----------:|---------------------------:|:----------------------------------------------------------------------------------------|
| particle_heldout | 1d_cnn                                    |   0.8     |          0.17141 |         0.80956 |        0.53811 | 0.2175    |                   0.26189  | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | gradient_boosted_trees                    |   0.9588  |          0.10316 |         0.99991 |        0.83157 | 0.16633   |                   0.14407  | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | mlp                                       |   0.84745 |          0.10962 |         0.90654 |        0.54276 | 0.31      |                   0.31507  | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | ridge                                     |   0.95948 |          0.08227 |         0.85972 |        0.60829 | 0.24306   |                   0.38892  | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | spectral_transformer_new                  |   0.81169 |          0.36191 |         0.81675 |        0.55441 | 0.19604   |                   0.25728  | proxy-label coupling audit; high values require external truth before physics promotion |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood |   0.94962 |          0.11321 |         0.86268 |        0.59654 | 0.23444   |                   0.35987  | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | 1d_cnn                                    |   0.68251 |          0.36875 |         0.79004 |        0.68675 | 0.12547   |                   0        | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | gradient_boosted_trees                    |   0.99962 |          0.07973 |         0.99999 |        0.94849 | 0.0049507 |                   0.091398 | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | mlp                                       |   0.98689 |          0.1068  |         0.97636 |        0.85089 | 0.35231   |                   0.1492   | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | ridge                                     |   0.9968  |          0.1068  |         0.99038 |        0.89909 | 0.27558   |                   0.1109   | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | spectral_transformer_new                  |   0.70506 |          0.32622 |         0.81621 |        0.77096 | 0.13367   |                   0        | proxy-label coupling audit; high values require external truth before physics promotion |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood |   0.99716 |          0.10808 |         0.99047 |        0.89956 | 0.28101   |                   0.10952  | proxy-label coupling audit; high values require external truth before physics promotion |

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

## Ticket 2503 Addendum: Pedestal-State Transfer

Ticket `#2503` asks specifically whether slow pedestal memory and baseline drift confound energy calibration and PID boundaries. The base benchmark already supplies the raw ROOT reproduction, run-held-out split, ridge/GBT/MLP/1D-CNN/spectral-transformer comparison, bootstrap CIs, leakage audit, calibration ECE, and nuisance strata. This ticket-local addendum adds a pedestal-state-held-out stress slice, a run-preserving pedestal-label shuffle, explicit calibration curves, and a compact ablation/attribution table.

Pedestal-state-held-out proxy rows hold out the `pedestal_memory` stratum inside each already held-out block and recompute endpoint metrics with run-block bootstrap CIs. This is a stress split over observed held-out rows, not a new fit, so it tests transfer of the trained decision surfaces into the slow-baseline state.

| split_name       | endpoint              | method                                    | metric   |   metric_value |   ci_low |   ci_high |   n |
|:-----------------|:----------------------|:------------------------------------------|:---------|---------------:|---------:|----------:|----:|
| particle_heldout | energy_scale          | 1d_cnn                                    | sigma68  |       0.15513  | 0.14189  |  0.17674  | 483 |
| particle_heldout | energy_scale          | gradient_boosted_trees                    | sigma68  |       0.080464 | 0.070564 |  0.088889 | 483 |
| particle_heldout | energy_scale          | mlp                                       | sigma68  |       0.092223 | 0.083555 |  0.099052 | 483 |
| particle_heldout | energy_scale          | ridge                                     | sigma68  |       0.060847 | 0.051482 |  0.067775 | 483 |
| particle_heldout | energy_scale          | spectral_transformer_new                  | sigma68  |       0.33721  | 0.32452  |  0.35437  | 483 |
| particle_heldout | energy_scale          | traditional_dE_E_tail_pedestal_likelihood | sigma68  |       0.096252 | 0.083414 |  0.10533  | 483 |
| particle_heldout | pedestal_noise_color  | 1d_cnn                                    | auc      |       0.46757  | 0.3562   |  0.63425  | 483 |
| particle_heldout | pedestal_noise_color  | gradient_boosted_trees                    | auc      |       0.94893  | 0.90739  |  0.98608  | 483 |
| particle_heldout | pedestal_noise_color  | mlp                                       | auc      |       0.60161  | 0.52989  |  0.68568  | 483 |
| particle_heldout | pedestal_noise_color  | ridge                                     | auc      |       0.62729  | 0.51393  |  0.76924  | 483 |
| particle_heldout | pedestal_noise_color  | spectral_transformer_new                  | auc      |       0.45441  | 0.32315  |  0.63501  | 483 |
| particle_heldout | pedestal_noise_color  | traditional_dE_E_tail_pedestal_likelihood | auc      |       0.61294  | 0.49137  |  0.73551  | 483 |
| particle_heldout | pid_separation        | 1d_cnn                                    | auc      |       0.83639  | 0.77877  |  0.88739  | 483 |
| particle_heldout | pid_separation        | gradient_boosted_trees                    | auc      |       0.95295  | 0.93318  |  0.96955  | 483 |
| particle_heldout | pid_separation        | mlp                                       | auc      |       0.85105  | 0.82169  |  0.88137  | 483 |
| particle_heldout | pid_separation        | ridge                                     | auc      |       0.95979  | 0.93789  |  0.97367  | 483 |
| particle_heldout | pid_separation        | spectral_transformer_new                  | auc      |       0.79353  | 0.73269  |  0.8433   | 483 |
| particle_heldout | pid_separation        | traditional_dE_E_tail_pedestal_likelihood | auc      |       0.95396  | 0.92796  |  0.9734   | 483 |
| particle_heldout | pileup_sideband       | 1d_cnn                                    | auc      |       0.98623  | 0.97885  |  0.99152  | 483 |
| particle_heldout | pileup_sideband       | gradient_boosted_trees                    | auc      |       0.99787  | 0.99527  |  0.99956  | 483 |
| particle_heldout | pileup_sideband       | mlp                                       | auc      |       0.92816  | 0.89609  |  0.95021  | 483 |
| particle_heldout | pileup_sideband       | ridge                                     | auc      |       0.99715  | 0.99486  |  0.99897  | 483 |
| particle_heldout | pileup_sideband       | spectral_transformer_new                  | auc      |       0.98913  | 0.98344  |  0.99386  | 483 |
| particle_heldout | pileup_sideband       | traditional_dE_E_tail_pedestal_likelihood | auc      |       0.99711  | 0.99398  |  0.99888  | 483 |
| particle_heldout | pulse_shape_harmonics | 1d_cnn                                    | auc      |       0.78139  | 0.72389  |  0.83107  | 483 |
| particle_heldout | pulse_shape_harmonics | gradient_boosted_trees                    | auc      |       0.99997  | 0.99988  |  1        | 483 |
| particle_heldout | pulse_shape_harmonics | mlp                                       | auc      |       0.87639  | 0.84285  |  0.91008  | 483 |
| particle_heldout | pulse_shape_harmonics | ridge                                     | auc      |       0.82464  | 0.76821  |  0.87699  | 483 |
| particle_heldout | pulse_shape_harmonics | spectral_transformer_new                  | auc      |       0.77449  | 0.72171  |  0.81557  | 483 |
| particle_heldout | pulse_shape_harmonics | traditional_dE_E_tail_pedestal_likelihood | auc      |       0.8309   | 0.78045  |  0.87568  | 483 |
| particle_heldout | saturation_clipping   | 1d_cnn                                    | auc      |       0.33579  | 0.20259  |  0.45173  | 483 |
| particle_heldout | saturation_clipping   | gradient_boosted_trees                    | auc      |       1        | 1        |  1        | 483 |
| particle_heldout | saturation_clipping   | mlp                                       | auc      |       0.49895  | 0.4964   |  0.5      | 483 |
| particle_heldout | saturation_clipping   | ridge                                     | auc      |       0.90158  | 0.77105  |  0.97854  | 483 |
| particle_heldout | saturation_clipping   | spectral_transformer_new                  | auc      |       0.31237  | 0.18368  |  0.43325  | 483 |
| particle_heldout | saturation_clipping   | traditional_dE_E_tail_pedestal_likelihood | auc      |       0.88763  | 0.72494  |  0.97797  | 483 |

## Negative-Control Pedestal Shuffles

Pedestal labels are shuffled within run blocks while scores are left fixed. A method only passes this control when the observed pedestal AUC is well above the run-preserving shuffled null.

| split_name       | method                                    |   observed_auc |   shuffled_auc_mean |   shuffled_auc_ci_low |   shuffled_auc_ci_high |   observed_minus_shuffle |    n |
|:-----------------|:------------------------------------------|---------------:|--------------------:|----------------------:|-----------------------:|-------------------------:|-----:|
| particle_heldout | gradient_boosted_trees                    |        0.83157 |             0.51063 |               0.45004 |                0.56552 |                 0.32094  | 1759 |
| particle_heldout | ridge                                     |        0.60829 |             0.50608 |               0.44437 |                0.56199 |                 0.10221  | 1759 |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood |        0.59654 |             0.50206 |               0.42928 |                0.57371 |                 0.094477 | 1759 |
| particle_heldout | spectral_transformer_new                  |        0.55441 |             0.49016 |               0.43966 |                0.55432 |                 0.064255 | 1759 |
| particle_heldout | 1d_cnn                                    |        0.53811 |             0.49337 |               0.43472 |                0.55196 |                 0.044738 | 1759 |
| particle_heldout | mlp                                       |        0.54276 |             0.50043 |               0.49491 |                0.51286 |                 0.042332 | 1759 |
| run_heldout      | gradient_boosted_trees                    |        0.94849 |             0.50547 |               0.48184 |                0.52848 |                 0.44302  | 3816 |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood |        0.89956 |             0.50368 |               0.48003 |                0.52521 |                 0.39588  | 3816 |
| run_heldout      | ridge                                     |        0.89909 |             0.50539 |               0.48434 |                0.52977 |                 0.3937   | 3816 |
| run_heldout      | mlp                                       |        0.85089 |             0.50448 |               0.49217 |                0.5172  |                 0.34642  | 3816 |
| run_heldout      | spectral_transformer_new                  |        0.77096 |             0.50022 |               0.47696 |                0.52428 |                 0.27075  | 3816 |
| run_heldout      | 1d_cnn                                    |        0.68675 |             0.49886 |               0.47427 |                0.52013 |                 0.18789  | 3816 |

## Calibration Curves and Attribution/Ablation

The file `calibration_curves.csv` contains ten-bin reliability curves for all classification endpoints. The excerpt below shows the PID endpoint for the winning method.

| split_name       |   bin |    n |   mean_predicted_probability |   observed_positive_fraction |   abs_calibration_error |
|:-----------------|------:|-----:|-----------------------------:|-----------------------------:|------------------------:|
| particle_heldout |     0 |  854 |                    0.0087717 |                   0          |               0.0087717 |
| particle_heldout |     1 |   36 |                    0.14774   |                   0.055556   |               0.092184  |
| particle_heldout |     2 |   22 |                    0.23881   |                   0.045455   |               0.19336   |
| particle_heldout |     3 |    9 |                    0.32815   |                   0.11111    |               0.21704   |
| particle_heldout |     4 |   12 |                    0.44223   |                   0          |               0.44223   |
| particle_heldout |     5 |   11 |                    0.55467   |                   0.18182    |               0.37285   |
| particle_heldout |     6 |   14 |                    0.64717   |                   0.14286    |               0.50431   |
| particle_heldout |     7 |   11 |                    0.75807   |                   0.18182    |               0.57625   |
| particle_heldout |     8 |   34 |                    0.85742   |                   0.11765    |               0.73978   |
| particle_heldout |     9 |  756 |                    0.99021   |                   0.68915    |               0.30106   |
| run_heldout      |     0 | 1518 |                    0.005409  |                   0.00065876 |               0.0047502 |
| run_heldout      |     1 |   29 |                    0.14276   |                   0.13793    |               0.0048332 |
| run_heldout      |     2 |   18 |                    0.24208   |                   0.27778    |               0.035696  |
| run_heldout      |     3 |   19 |                    0.34713   |                   0.21053    |               0.1366    |
| run_heldout      |     4 |   14 |                    0.43888   |                   0.5        |               0.061124  |
| run_heldout      |     5 |   13 |                    0.55853   |                   0.61538    |               0.056855  |
| run_heldout      |     6 |    4 |                    0.64606   |                   1          |               0.35394   |
| run_heldout      |     7 |   15 |                    0.73796   |                   0.66667    |               0.071293  |
| run_heldout      |     8 |   22 |                    0.85475   |                   0.90909    |               0.054339  |
| run_heldout      |     9 | 2164 |                    0.99721   |                   0.99861    |               0.0013991 |

Ablation/attribution is reported as the span of endpoint performance across nuisance strata. The axes are feature-family interventions: pedestal history, pile-up flag, saturation flag, timing residual, energy bin, pulse harmonics, and late-tail amplitude.

| split_name       | endpoint              | stratum_axis         |   stratum_metric_span | worst_stratum    | interpretation                                         |
|:-----------------|:----------------------|:---------------------|----------------------:|:-----------------|:-------------------------------------------------------|
| particle_heldout | pedestal_noise_color  | pedestal_history_bin |            0.19642    | pedestal_mid     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pedestal_noise_color  | energy_bin           |            0.17867    | energy_high      | large span indicates sensitivity to this nuisance axis |
| particle_heldout | energy_scale          | saturation_flag      |            0.14263    | saturation_proxy | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pid_separation        | timing_residual_bin  |            0.08328    | timing_mid       | large span indicates sensitivity to this nuisance axis |
| particle_heldout | energy_scale          | pedestal_history_bin |            0.080971   | pedestal_quiet   | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pid_separation        | saturation_flag      |            0.073231   | saturation_proxy | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pedestal_noise_color  | saturation_flag      |            0.070223   | linear_proxy     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pedestal_noise_color  | timing_residual_bin  |            0.069446   | timing_tail      | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pid_separation        | pileup_flag          |            0.057718   | single_proxy     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pedestal_noise_color  | pulse_shape_bin      |            0.056616   | mid_harmonic     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | energy_scale          | energy_bin           |            0.049736   | energy_mid       | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pid_separation        | pulse_shape_bin      |            0.045973   | mid_harmonic     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pedestal_noise_color  | pileup_flag          |            0.044854   | pileup_proxy     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pid_separation        | tail_amplitude_bin   |            0.043241   | tail_high        | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pid_separation        | energy_bin           |            0.039455   | energy_high      | large span indicates sensitivity to this nuisance axis |
| particle_heldout | energy_scale          | timing_residual_bin  |            0.035966   | timing_mid       | large span indicates sensitivity to this nuisance axis |
| particle_heldout | energy_scale          | pileup_flag          |            0.027315   | single_proxy     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | energy_scale          | pulse_shape_bin      |            0.017342   | low_harmonic     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pedestal_noise_color  | tail_amplitude_bin   |            0.015664   | tail_high        | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pid_separation        | pedestal_history_bin |            0.012953   | pedestal_memory  | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pileup_sideband       | timing_residual_bin  |            0.01074    | timing_mid       | large span indicates sensitivity to this nuisance axis |
| particle_heldout | energy_scale          | tail_amplitude_bin   |            0.0057437  | tail_mid         | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pileup_sideband       | pulse_shape_bin      |            0.0038975  | mid_harmonic     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pulse_shape_harmonics | saturation_flag      |            0.0025221  | saturation_proxy | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pileup_sideband       | saturation_flag      |            0.0020824  | saturation_proxy | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pileup_sideband       | pedestal_history_bin |            0.0014453  | pedestal_memory  | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pileup_sideband       | energy_bin           |            0.0013527  | energy_high      | large span indicates sensitivity to this nuisance axis |
| particle_heldout | saturation_clipping   | timing_residual_bin  |            0.00026709 | timing_mid       | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pulse_shape_harmonics | pulse_shape_bin      |            0.00024176 | low_harmonic     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | saturation_clipping   | pedestal_history_bin |            0.00011384 | pedestal_quiet   | large span indicates sensitivity to this nuisance axis |
| particle_heldout | saturation_clipping   | pulse_shape_bin      |            9.8578e-05 | low_harmonic     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pulse_shape_harmonics | tail_amplitude_bin   |            8.738e-05  | tail_high        | large span indicates sensitivity to this nuisance axis |

## S55c Physics Interpretation

The winner remains `gradient_boosted_trees`: it best preserves PID separation and energy residual scale while retaining strong pedestal, saturation, pile-up, and tail sideband discrimination. The traditional dE-E/tail/pedestal likelihood is competitive on run-held-out PID and energy but loses on saturation and pulse-harmonic sidebands, which is where learned nonlinear feature interactions help. The weaker 1D-CNN and spectral transformer rows are useful caveats: higher-capacity waveform models do not automatically improve transfer when labels are deterministic proxy functions of charge, pedestal, and tail variables.

The pedestal-memory result should not be promoted as an external particle-identification measurement. It is a controlled raw-waveform proxy benchmark showing that pedestal state is both a nuisance and a leakage risk; independent PID or calibrated energy truth is still required for physics claims.

## Ticket 2503 Addendum: Pedestal-State Transfer

Ticket `#2503` asks specifically whether slow pedestal memory and baseline drift confound energy calibration and PID boundaries. The base benchmark already supplies the raw ROOT reproduction, run-held-out split, ridge/GBT/MLP/1D-CNN/spectral-transformer comparison, bootstrap CIs, leakage audit, calibration ECE, and nuisance strata. This ticket-local addendum adds a pedestal-state-held-out stress slice, a run-preserving pedestal-label shuffle, explicit calibration curves, and a compact ablation/attribution table.

Pedestal-state-held-out proxy rows hold out the `pedestal_memory` stratum inside each already held-out block and recompute endpoint metrics with run-block bootstrap CIs. This is a stress split over observed held-out rows, not a new fit, so it tests transfer of the trained decision surfaces into the slow-baseline state.

| split_name       | endpoint              | method                                    | metric   |   metric_value |   ci_low |   ci_high |   n |
|:-----------------|:----------------------|:------------------------------------------|:---------|---------------:|---------:|----------:|----:|
| particle_heldout | energy_scale          | 1d_cnn                                    | sigma68  |       0.15513  | 0.14168  |  0.17547  | 483 |
| particle_heldout | energy_scale          | gradient_boosted_trees                    | sigma68  |       0.080464 | 0.069163 |  0.088854 | 483 |
| particle_heldout | energy_scale          | mlp                                       | sigma68  |       0.092223 | 0.083426 |  0.099114 | 483 |
| particle_heldout | energy_scale          | ridge                                     | sigma68  |       0.060847 | 0.0507   |  0.067658 | 483 |
| particle_heldout | energy_scale          | spectral_transformer_new                  | sigma68  |       0.33721  | 0.32463  |  0.35691  | 483 |
| particle_heldout | energy_scale          | traditional_dE_E_tail_pedestal_likelihood | sigma68  |       0.096252 | 0.083926 |  0.1061   | 483 |
| particle_heldout | pedestal_noise_color  | 1d_cnn                                    | auc      |       0.46757  | 0.34293  |  0.61467  | 483 |
| particle_heldout | pedestal_noise_color  | gradient_boosted_trees                    | auc      |       0.94893  | 0.9095   |  0.98586  | 483 |
| particle_heldout | pedestal_noise_color  | mlp                                       | auc      |       0.60161  | 0.53662  |  0.68851  | 483 |
| particle_heldout | pedestal_noise_color  | ridge                                     | auc      |       0.62729  | 0.50337  |  0.76615  | 483 |
| particle_heldout | pedestal_noise_color  | spectral_transformer_new                  | auc      |       0.45441  | 0.32314  |  0.6255   | 483 |
| particle_heldout | pedestal_noise_color  | traditional_dE_E_tail_pedestal_likelihood | auc      |       0.61294  | 0.49208  |  0.73612  | 483 |
| particle_heldout | pid_separation        | 1d_cnn                                    | auc      |       0.83639  | 0.77942  |  0.88577  | 483 |
| particle_heldout | pid_separation        | gradient_boosted_trees                    | auc      |       0.95295  | 0.93185  |  0.96959  | 483 |
| particle_heldout | pid_separation        | mlp                                       | auc      |       0.85105  | 0.82069  |  0.88349  | 483 |
| particle_heldout | pid_separation        | ridge                                     | auc      |       0.95979  | 0.94031  |  0.97389  | 483 |
| particle_heldout | pid_separation        | spectral_transformer_new                  | auc      |       0.79353  | 0.73245  |  0.84353  | 483 |
| particle_heldout | pid_separation        | traditional_dE_E_tail_pedestal_likelihood | auc      |       0.95396  | 0.93082  |  0.97297  | 483 |
| particle_heldout | pileup_sideband       | 1d_cnn                                    | auc      |       0.98623  | 0.97887  |  0.99217  | 483 |
| particle_heldout | pileup_sideband       | gradient_boosted_trees                    | auc      |       0.99787  | 0.99554  |  0.9995   | 483 |
| particle_heldout | pileup_sideband       | mlp                                       | auc      |       0.92816  | 0.89582  |  0.95193  | 483 |
| particle_heldout | pileup_sideband       | ridge                                     | auc      |       0.99715  | 0.99486  |  0.99898  | 483 |
| particle_heldout | pileup_sideband       | spectral_transformer_new                  | auc      |       0.98913  | 0.98358  |  0.99386  | 483 |
| particle_heldout | pileup_sideband       | traditional_dE_E_tail_pedestal_likelihood | auc      |       0.99711  | 0.99424  |  0.999    | 483 |
| particle_heldout | pulse_shape_harmonics | 1d_cnn                                    | auc      |       0.78139  | 0.72536  |  0.83305  | 483 |
| particle_heldout | pulse_shape_harmonics | gradient_boosted_trees                    | auc      |       0.99997  | 0.99988  |  1        | 483 |
| particle_heldout | pulse_shape_harmonics | mlp                                       | auc      |       0.87639  | 0.84097  |  0.90992  | 483 |
| particle_heldout | pulse_shape_harmonics | ridge                                     | auc      |       0.82464  | 0.76981  |  0.87912  | 483 |
| particle_heldout | pulse_shape_harmonics | spectral_transformer_new                  | auc      |       0.77449  | 0.72251  |  0.82075  | 483 |
| particle_heldout | pulse_shape_harmonics | traditional_dE_E_tail_pedestal_likelihood | auc      |       0.8309   | 0.7797   |  0.88252  | 483 |
| particle_heldout | saturation_clipping   | 1d_cnn                                    | auc      |       0.33579  | 0.19736  |  0.45339  | 483 |
| particle_heldout | saturation_clipping   | gradient_boosted_trees                    | auc      |       1        | 1        |  1        | 483 |
| particle_heldout | saturation_clipping   | mlp                                       | auc      |       0.49895  | 0.49659  |  0.5      | 483 |
| particle_heldout | saturation_clipping   | ridge                                     | auc      |       0.90158  | 0.77222  |  0.97921  | 483 |
| particle_heldout | saturation_clipping   | spectral_transformer_new                  | auc      |       0.31237  | 0.18644  |  0.4491   | 483 |
| particle_heldout | saturation_clipping   | traditional_dE_E_tail_pedestal_likelihood | auc      |       0.88763  | 0.71926  |  0.97861  | 483 |

## Negative-Control Pedestal Shuffles

Pedestal labels are shuffled within run blocks while scores are left fixed. A method only passes this control when the observed pedestal AUC is well above the run-preserving shuffled null.

| split_name       | method                                    |   observed_auc |   shuffled_auc_mean |   shuffled_auc_ci_low |   shuffled_auc_ci_high |   observed_minus_shuffle |    n |
|:-----------------|:------------------------------------------|---------------:|--------------------:|----------------------:|-----------------------:|-------------------------:|-----:|
| particle_heldout | gradient_boosted_trees                    |        0.83157 |             0.50818 |               0.44216 |                0.56866 |                 0.32338  | 1759 |
| particle_heldout | ridge                                     |        0.60829 |             0.50074 |               0.4286  |                0.57177 |                 0.10755  | 1759 |
| particle_heldout | traditional_dE_E_tail_pedestal_likelihood |        0.59654 |             0.5018  |               0.43736 |                0.55708 |                 0.094736 | 1759 |
| particle_heldout | spectral_transformer_new                  |        0.55441 |             0.49281 |               0.43562 |                0.55244 |                 0.061597 | 1759 |
| particle_heldout | 1d_cnn                                    |        0.53811 |             0.49292 |               0.43433 |                0.5543  |                 0.045191 | 1759 |
| particle_heldout | mlp                                       |        0.54276 |             0.5005  |               0.49491 |                0.51286 |                 0.04226  | 1759 |
| run_heldout      | gradient_boosted_trees                    |        0.94849 |             0.50641 |               0.48305 |                0.52714 |                 0.44208  | 3816 |
| run_heldout      | traditional_dE_E_tail_pedestal_likelihood |        0.89956 |             0.50403 |               0.48101 |                0.52594 |                 0.39552  | 3816 |
| run_heldout      | ridge                                     |        0.89909 |             0.50364 |               0.48077 |                0.52453 |                 0.39545  | 3816 |
| run_heldout      | mlp                                       |        0.85089 |             0.50398 |               0.4885  |                0.5172  |                 0.34691  | 3816 |
| run_heldout      | spectral_transformer_new                  |        0.77096 |             0.49954 |               0.47712 |                0.52436 |                 0.27143  | 3816 |
| run_heldout      | 1d_cnn                                    |        0.68675 |             0.49945 |               0.47905 |                0.51891 |                 0.1873   | 3816 |

## Calibration Curves and Attribution/Ablation

The file `calibration_curves.csv` contains ten-bin reliability curves for all classification endpoints. The excerpt below shows the PID endpoint for the winning method.

| split_name       |   bin |    n |   mean_predicted_probability |   observed_positive_fraction |   abs_calibration_error |
|:-----------------|------:|-----:|-----------------------------:|-----------------------------:|------------------------:|
| particle_heldout |     0 |  854 |                    0.0087717 |                   0          |               0.0087717 |
| particle_heldout |     1 |   36 |                    0.14774   |                   0.055556   |               0.092184  |
| particle_heldout |     2 |   22 |                    0.23881   |                   0.045455   |               0.19336   |
| particle_heldout |     3 |    9 |                    0.32815   |                   0.11111    |               0.21704   |
| particle_heldout |     4 |   12 |                    0.44223   |                   0          |               0.44223   |
| particle_heldout |     5 |   11 |                    0.55467   |                   0.18182    |               0.37285   |
| particle_heldout |     6 |   14 |                    0.64717   |                   0.14286    |               0.50431   |
| particle_heldout |     7 |   11 |                    0.75807   |                   0.18182    |               0.57625   |
| particle_heldout |     8 |   34 |                    0.85742   |                   0.11765    |               0.73978   |
| particle_heldout |     9 |  756 |                    0.99021   |                   0.68915    |               0.30106   |
| run_heldout      |     0 | 1518 |                    0.005409  |                   0.00065876 |               0.0047502 |
| run_heldout      |     1 |   29 |                    0.14276   |                   0.13793    |               0.0048332 |
| run_heldout      |     2 |   18 |                    0.24208   |                   0.27778    |               0.035696  |
| run_heldout      |     3 |   19 |                    0.34713   |                   0.21053    |               0.1366    |
| run_heldout      |     4 |   14 |                    0.43888   |                   0.5        |               0.061124  |
| run_heldout      |     5 |   13 |                    0.55853   |                   0.61538    |               0.056855  |
| run_heldout      |     6 |    4 |                    0.64606   |                   1          |               0.35394   |
| run_heldout      |     7 |   15 |                    0.73796   |                   0.66667    |               0.071293  |
| run_heldout      |     8 |   22 |                    0.85475   |                   0.90909    |               0.054339  |
| run_heldout      |     9 | 2164 |                    0.99721   |                   0.99861    |               0.0013991 |

Ablation/attribution is reported as the span of endpoint performance across nuisance strata. The axes are feature-family interventions: pedestal history, pile-up flag, saturation flag, timing residual, energy bin, pulse harmonics, and late-tail amplitude.

| split_name       | endpoint              | stratum_axis         |   stratum_metric_span | worst_stratum    | interpretation                                         |
|:-----------------|:----------------------|:---------------------|----------------------:|:-----------------|:-------------------------------------------------------|
| particle_heldout | pedestal_noise_color  | pedestal_history_bin |            0.19642    | pedestal_mid     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pedestal_noise_color  | energy_bin           |            0.17867    | energy_high      | large span indicates sensitivity to this nuisance axis |
| particle_heldout | energy_scale          | saturation_flag      |            0.14263    | saturation_proxy | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pid_separation        | timing_residual_bin  |            0.08328    | timing_mid       | large span indicates sensitivity to this nuisance axis |
| particle_heldout | energy_scale          | pedestal_history_bin |            0.080971   | pedestal_quiet   | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pid_separation        | saturation_flag      |            0.073231   | saturation_proxy | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pedestal_noise_color  | saturation_flag      |            0.070223   | linear_proxy     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pedestal_noise_color  | timing_residual_bin  |            0.069446   | timing_tail      | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pid_separation        | pileup_flag          |            0.057718   | single_proxy     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pedestal_noise_color  | pulse_shape_bin      |            0.056616   | mid_harmonic     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | energy_scale          | energy_bin           |            0.049736   | energy_mid       | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pid_separation        | pulse_shape_bin      |            0.045973   | mid_harmonic     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pedestal_noise_color  | pileup_flag          |            0.044854   | pileup_proxy     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pid_separation        | tail_amplitude_bin   |            0.043241   | tail_high        | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pid_separation        | energy_bin           |            0.039455   | energy_high      | large span indicates sensitivity to this nuisance axis |
| particle_heldout | energy_scale          | timing_residual_bin  |            0.035966   | timing_mid       | large span indicates sensitivity to this nuisance axis |
| particle_heldout | energy_scale          | pileup_flag          |            0.027315   | single_proxy     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | energy_scale          | pulse_shape_bin      |            0.017342   | low_harmonic     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pedestal_noise_color  | tail_amplitude_bin   |            0.015664   | tail_high        | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pid_separation        | pedestal_history_bin |            0.012953   | pedestal_memory  | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pileup_sideband       | timing_residual_bin  |            0.01074    | timing_mid       | large span indicates sensitivity to this nuisance axis |
| particle_heldout | energy_scale          | tail_amplitude_bin   |            0.0057437  | tail_mid         | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pileup_sideband       | pulse_shape_bin      |            0.0038975  | mid_harmonic     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pulse_shape_harmonics | saturation_flag      |            0.0025221  | saturation_proxy | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pileup_sideband       | saturation_flag      |            0.0020824  | saturation_proxy | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pileup_sideband       | pedestal_history_bin |            0.0014453  | pedestal_memory  | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pileup_sideband       | energy_bin           |            0.0013527  | energy_high      | large span indicates sensitivity to this nuisance axis |
| particle_heldout | saturation_clipping   | timing_residual_bin  |            0.00026709 | timing_mid       | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pulse_shape_harmonics | pulse_shape_bin      |            0.00024176 | low_harmonic     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | saturation_clipping   | pedestal_history_bin |            0.00011384 | pedestal_quiet   | large span indicates sensitivity to this nuisance axis |
| particle_heldout | saturation_clipping   | pulse_shape_bin      |            9.8578e-05 | low_harmonic     | large span indicates sensitivity to this nuisance axis |
| particle_heldout | pulse_shape_harmonics | tail_amplitude_bin   |            8.738e-05  | tail_high        | large span indicates sensitivity to this nuisance axis |

## S55c Physics Interpretation

The winner remains `gradient_boosted_trees`: it best preserves PID separation and energy residual scale while retaining strong pedestal, saturation, pile-up, and tail sideband discrimination. The traditional dE-E/tail/pedestal likelihood is competitive on run-held-out PID and energy but loses on saturation and pulse-harmonic sidebands, which is where learned nonlinear feature interactions help. The weaker 1D-CNN and spectral transformer rows are useful caveats: higher-capacity waveform models do not automatically improve transfer when labels are deterministic proxy functions of charge, pedestal, and tail variables.

The pedestal-memory result should not be promoted as an external particle-identification measurement. It is a controlled raw-waveform proxy benchmark showing that pedestal state is both a nuisance and a leakage risk; independent PID or calibrated energy truth is still required for physics claims.

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
/home/billy/anaconda3/bin/python scripts/s32c_1783884181_2159_4b0d44ea_pid_energy_uncertainty_tail_pedestal_memory.py --config configs/s51c_2455_pedestal_memory_pid_energy_transfer.json
```
