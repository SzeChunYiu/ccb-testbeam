# S59c/#2518 Causal Pile-Up PID Energy Disentanglement

**Ticket:** `#2518`  
**Worker:** `testbeam-laptop-4`  
**Raw ROOT directory:** `/home/billy/ccb-data/data/extracted/root/root`  
**Source prediction artifact:** `reports/1783809265.5764.0f2a2dda__s29a_digitized_g4_multitask_truth_benchmark`  
**Git commit at execution:** `cec9edc28257e0699c70c17fa9b2e8d806a3d42a`

## Abstract

Ticket `#2518` asks for a run-disjoint benchmark of overlapping-pulse PID and
energy inference.  The transparent comparator is interpreted here as
`sparse_nn_template_bayesian_deltaE_E_likelihood_traditional`: a nonnegative
two-pulse template deconvolution constrained by sideband pedestal estimates,
followed by a Bayesian deltaE-E PID likelihood.  It is compared with ridge,
gradient-boosted trees, MLP, 1D-CNN, a sequence transformer, and a new
physics-residual architecture.  The raw ROOT reproduction gate passes exactly:
`640737` selected
B-stave pulses versus the reference `640737`, delta
`0`.

The winner named in `result.json` is **`causal_template_residual_boosted_stack_new`** with S59c composite
loss `0.2397`.  Relative to the traditional method, the
winner changes PID AUC by `0.1163`,
PID purity by `0.0169`, energy
bias by `0.00390`,
timing sigma68 by `-3.505` ns,
and pile-up miss rate by `-0.3485`.

## Raw ROOT Reproduction

For each `hrdb_run_NNNN.root`, branch `h101/HRDv` is reshaped into
`(event, channel, sample)` with eighteen samples per channel.  The pedestal is

`b_{e,c} = median_{t in {0,1,2,3}} x_{e,c,t}`,

and the selected B-stack pulse indicator for B2/B4/B6/B8 channels is

`I_{e,c} = 1[max_t (x_{e,c,t} - b_{e,c}) > 1000 ADC]`.

Thus the reproduced ticket number is

`N = sum_runs sum_e sum_{c in {B2,B4,B6,B8}} I_{e,c}`.

| quantity                           | expected | reproduced | delta | tolerance | pass |
| ---------------------------------- | -------- | ---------- | ----- | --------- | ---- |
| total selected B-stave pulses      | 640737   | 640737     | 0     | 0         | True |
| sample_i_calib selected_pulses     | 248745   | 248745     | 0     | 0         | True |
| sample_i_analysis selected_pulses  | 252266   | 252266     | 0     | 0         | True |
| sample_ii_calib selected_pulses    | 14630    | 14630      | 0     | 0         | True |
| sample_ii_analysis selected_pulses | 125096   | 125096     | 0     | 0         | True |
| sample_ii_analysis B2              | 88213    | 88213      | 0     | 0         | True |
| sample_ii_analysis B4              | 21229    | 21229      | 0     | 0         | True |
| sample_ii_analysis B6              | 11148    | 11148      | 0     | 0         | True |
| sample_ii_analysis B8              | 4506     | 4506       | 0     | 0         | True |

Run-level counts are stored in `reproduction_counts_by_run.csv`; the first and
last five rows are:

| run | group              | events_total | selected_pulses | B2    | B4   | B6   | B8   |
| --- | ------------------ | ------------ | --------------- | ----- | ---- | ---- | ---- |
| 31  | sample_i_calib     | 39990        | 27871           | 26948 | 592  | 237  | 94   |
| 32  | sample_i_calib     | 41921        | 28240           | 27316 | 605  | 224  | 95   |
| 33  | sample_i_calib     | 57173        | 48737           | 47724 | 559  | 318  | 136  |
| 34  | sample_i_calib     | 39765        | 34118           | 33373 | 412  | 244  | 89   |
| 35  | sample_i_calib     | 27786        | 11667           | 11029 | 403  | 163  | 72   |
| 61  | sample_ii_analysis | 36535        | 18965           | 11015 | 4401 | 2490 | 1059 |
| 62  | sample_ii_analysis | 37584        | 19089           | 11635 | 4183 | 2342 | 929  |
| 63  | sample_ii_analysis | 37030        | 18817           | 14566 | 2645 | 1153 | 453  |
| 64  | sample_ii_calib    | 35943        | 14630           | 11907 | 1689 | 763  | 271  |
| 65  | sample_ii_analysis | 38424        | 13038           | 11768 | 842  | 323  | 105  |

## Data and Split

The supervised benchmark uses the validated S29a digitized GEANT4 event table
and prediction artifact.  It provides controlled synthetic overlays joined to
raw-data waveform templates and event-level GEANT4 PID, energy, timing,
pile-up, saturation, and pedestal truth proxies.  Training and held-out
evaluation are disjoint by source run; the held-out runs are
`[58, 60, 62, 64, 65]`.  The run-block
bootstrap resamples held-out runs, not individual rows, so the reported
intervals target run-to-run variation.

The real-data sideband check in `real_high_rate_sidebands.csv` compares the
controlled-overlap high-rate sideband against same-run clean controls.  Because
external beamline PID labels are not joined event-by-event, PID endpoints are
GEANT4/digitization bridge labels and should be read as comparative
architecture diagnostics rather than absolute production PID efficiencies.

## Methods

The traditional method solves a sparse nonnegative pulse decomposition

`hat a = argmin_{a >= 0} ||x - T(theta) a - b||_2^2 + lambda ||a||_1`,

where `T(theta)` contains one- and two-pulse templates over candidate
separations, `a` are nonnegative amplitudes, and `b` is a sideband pedestal
nuisance.  Its PID stage is a Bayesian deltaE-E likelihood

`log p(z | y,s) = -1/2 sum_j [((z_j - mu_{y,s,j})^2 / sigma_{y,s,j}^2) + log sigma_{y,s,j}^2] + log pi_y`,

with detector state `s` covering pedestal, saturation, and overlap strata.

Ridge uses L2-regularized linear heads,

`hat beta = argmin_beta ||y - X beta||_2^2 + lambda ||beta||_2^2`.

Gradient-boosted trees model nonlinear charge-depth interactions; the MLP is a
dense waveform-summary network; the 1D-CNN consumes the ordered eighteen-sample
waveform; and the sequence transformer tests attention over the short waveform.
The new architecture, `causal_template_residual_boosted_stack_new`,
uses the transparent template/likelihood solution as a first stage and learns
residual corrections for PID score, energy, timing, pile-up, and saturation.

## Estimands and Scoring

The held-out estimands are PID AUC, PID purity, fractional energy bias,
fractional energy robust width, timing separation width, pile-up miss rate,
clean-control false split rate, and late-tail rate.  Energy residuals are

`r_E = (hat E - E_true) / max(E_true, epsilon)`,

with width

`sigma68(r_E) = 0.5 [Q_84(r_E) - Q_16(r_E)]`.

The S59c composite loss is lower-is-better:

`L_m = 0.35(1-AUC_PID) + 0.20(1-Purity_PID) + 0.40|Bias_E| + sigma68_E + 0.006 sigma68_t + 0.05 r_miss + 0.03 r_false + 0.02 r_tail + P_controls`.

The negative-control penalty is

`P_controls = 0.08(|rho(score,pedestal)| + Delta_sat + |rho(score,source_run)|)`.

## Overall Held-Out Results

| method_alias                                                | family                 | winner_score | pid_auc | pid_purity | energy_fractional_bias | energy_fractional_sigma68 | time_sigma68_ns | pileup_miss_rate | false_split_rate | negative_control_penalty |
| ----------------------------------------------------------- | ---------------------- | ------------ | ------- | ---------- | ---------------------- | ------------------------- | --------------- | ---------------- | ---------------- | ------------------------ |
| causal_template_residual_boosted_stack_new                  | new_architecture       | 0.2397       | 0.9044  | 0.8115     | -0.0058                | 0.0829                    | 8.0963          | 0.3394           | 0.2485           | 0.0079                   |
| gradient_boosted_trees                                      | gradient_boosted_trees | 0.2435       | 0.9106  | 0.8082     | -0.0114                | 0.0862                    | 8.2219          | 0.3061           | 0.2455           | 0.0086                   |
| ridge                                                       | ridge                  | 0.2959       | 0.8378  | 0.7835     | -0.0230                | 0.0887                    | 10.3409         | 0.2848           | 0.2818           | 0.0099                   |
| 1d_cnn                                                      | 1d_cnn                 | 0.3209       | 0.8360  | 0.7873     | -0.0397                | 0.1030                    | 10.7809         | 0.2879           | 0.2515           | 0.0113                   |
| sparse_nn_template_bayesian_deltaE_E_likelihood_traditional | traditional            | 0.3463       | 0.7880  | 0.7946     | -0.0097                | 0.1003                    | 11.6018         | 0.6879           | 0.0939           | 0.0154                   |
| mlp                                                         | mlp                    | 0.4447       | 0.7688  | 0.7340     | -0.0509                | 0.1614                    | 14.8538         | 0.2970           | 0.2909           | 0.0095                   |
| sequence_transformer                                        | sequence_transformer   | 0.5267       | 0.5213  | 0.5142     | 0.0627                 | 0.1224                    | 12.3811         | 0.3333           | 0.2212           | 0.0118                   |

## Run-Block Bootstrap Confidence Intervals

| method_alias                                                | pid_auc_ci              | pid_purity_ci           | energy_bias_ci             | timing_sigma_ci_ns      | pileup_miss_ci          |
| ----------------------------------------------------------- | ----------------------- | ----------------------- | -------------------------- | ----------------------- | ----------------------- |
| causal_template_residual_boosted_stack_new                  | 0.9044 [0.8676, 0.9292] | 0.8115 [0.7789, 0.8484] | -0.0058 [-0.0160, 0.0034]  | 8.096 [7.479, 9.023]    | 0.3394 [0.2848, 0.3818] |
| gradient_boosted_trees                                      | 0.9106 [0.8784, 0.9377] | 0.8082 [0.7694, 0.8555] | -0.0114 [-0.0185, -0.0050] | 8.222 [7.239, 9.549]    | 0.3061 [0.2455, 0.3516] |
| ridge                                                       | 0.8378 [0.7874, 0.8826] | 0.7835 [0.7522, 0.8259] | -0.0230 [-0.0264, -0.0171] | 10.341 [9.310, 11.031]  | 0.2848 [0.2303, 0.3424] |
| 1d_cnn                                                      | 0.8360 [0.7915, 0.8729] | 0.7873 [0.7493, 0.8350] | -0.0397 [-0.0475, -0.0339] | 10.781 [9.385, 12.096]  | 0.2879 [0.2514, 0.3152] |
| sparse_nn_template_bayesian_deltaE_E_likelihood_traditional | 0.7880 [0.7444, 0.8298] | 0.7946 [0.7670, 0.8297] | -0.0097 [-0.0156, 0.0073]  | 11.602 [9.603, 14.556]  | 0.6879 [0.6333, 0.7273] |
| mlp                                                         | 0.7688 [0.7307, 0.8064] | 0.7340 [0.7079, 0.7548] | -0.0509 [-0.0628, -0.0412] | 14.854 [13.765, 16.572] | 0.2970 [0.2636, 0.3364] |
| sequence_transformer                                        | 0.5213 [0.4920, 0.5517] | 0.5142 [0.4638, 0.5632] | 0.0627 [0.0609, 0.0698]    | 12.381 [11.424, 14.252] | 0.3333 [0.2818, 0.3727] |

## Held-Out Run Stability

| method_alias                                                | heldout_run | pid_auc | pid_purity | pid_balanced_accuracy | energy_fractional_bias | time_sigma68_ns | pileup_miss_rate |
| ----------------------------------------------------------- | ----------- | ------- | ---------- | --------------------- | ---------------------- | --------------- | ---------------- |
| sparse_nn_template_bayesian_deltaE_E_likelihood_traditional | 58          | 0.8324  | 0.8302     | 0.7652                | -0.0156                | 14.6776         | 0.5909           |
| sparse_nn_template_bayesian_deltaE_E_likelihood_traditional | 60          | 0.8219  | 0.8545     | 0.8219                | 0.0032                 | 9.7415          | 0.6818           |
| sparse_nn_template_bayesian_deltaE_E_likelihood_traditional | 62          | 0.8396  | 0.7833     | 0.7862                | -0.0057                | 10.5528         | 0.7424           |
| sparse_nn_template_bayesian_deltaE_E_likelihood_traditional | 64          | 0.7035  | 0.7536     | 0.7194                | 0.0170                 | 13.1425         | 0.7273           |
| sparse_nn_template_bayesian_deltaE_E_likelihood_traditional | 65          | 0.7427  | 0.7667     | 0.7424                | -0.0197                | 6.6517          | 0.6970           |
| causal_template_residual_boosted_stack_new                  | 58          | 0.9226  | 0.8696     | 0.8864                | -0.0112                | 7.7479          | 0.2424           |
| causal_template_residual_boosted_stack_new                  | 60          | 0.9371  | 0.8571     | 0.8712                | 0.0037                 | 7.3787          | 0.3636           |
| causal_template_residual_boosted_stack_new                  | 62          | 0.8839  | 0.7887     | 0.8445                | -0.0194                | 9.0623          | 0.3788           |
| causal_template_residual_boosted_stack_new                  | 64          | 0.8366  | 0.7619     | 0.7778                | 0.0091                 | 7.3984          | 0.3939           |
| causal_template_residual_boosted_stack_new                  | 65          | 0.9293  | 0.7975     | 0.8561                | -0.0003                | 9.0340          | 0.3182           |

## Causal Strata

The winner's stratum table tests whether the conclusion depends on pulse
separation, pedestal state, saturation, or PID truth class.

| method                              | method_alias                               | stratum        | value                 | n_events | pid_purity | pid_efficiency | pid_specificity | pid_balanced_accuracy | energy_fractional_bias_proxy | timing_separation_sigma68_ns | pileup_recovery_efficiency |
| ----------------------------------- | ------------------------------------------ | -------------- | --------------------- | -------- | ---------- | -------------- | --------------- | --------------------- | ---------------------------- | ---------------------------- | -------------------------- |
| template_residual_boosted_stack_new | causal_template_residual_boosted_stack_new | spacing_bin    | merged_lt2            | 182      | 0.7263     | 0.7931         | 0.7263          | 0.7597                | 0.0000                       | 1.2368                       | 0.5714                     |
| template_residual_boosted_stack_new | causal_template_residual_boosted_stack_new | spacing_bin    | close_2_6             | 148      | 0.8929     | 0.9615         | 0.8714          | 0.9165                | 0.0000                       | 1.3705                       | 0.7703                     |
| template_residual_boosted_stack_new | causal_template_residual_boosted_stack_new | pedestal_bin   | (-4320.819, -170.068] | 220      | 0.8034     | 0.8868         | 0.7982          | 0.8425                | 0.0020                       | 1.7970                       | 0.5636                     |
| template_residual_boosted_stack_new | causal_template_residual_boosted_stack_new | pedestal_bin   | (-170.068, -8.932]    | 220      | 0.8182     | 0.9167         | 0.8036          | 0.8601                | 0.0000                       | 1.3713                       | 0.3955                     |
| template_residual_boosted_stack_new | causal_template_residual_boosted_stack_new | pedestal_bin   | (-8.932, 609.332]     | 220      | 0.8125     | 0.9123         | 0.7736          | 0.8429                | 0.0000                       | 1.3604                       | 0.4045                     |
| template_residual_boosted_stack_new | causal_template_residual_boosted_stack_new | saturation_bin | saturated             | 240      | 0.7762     | 0.9407         | 0.7377          | 0.8392                | 0.1046                       | 1.7917                       | 0.6417                     |
| template_residual_boosted_stack_new | causal_template_residual_boosted_stack_new | saturation_bin | unsaturated           | 420      | 0.8341     | 0.8857         | 0.8238          | 0.8548                | 0.0000                       | 1.3951                       | 0.3476                     |
| template_residual_boosted_stack_new | causal_template_residual_boosted_stack_new | pid_truth      | deuteron              | 328      | 1.0000     | 0.9055         | 0.0000          | 0.4527                | 0.0000                       | 1.4506                       | 0.4421                     |
| template_residual_boosted_stack_new | causal_template_residual_boosted_stack_new | pid_truth      | proton                | 332      | 0.0000     | 0.0000         | 0.7922          | 0.3961                | 0.0000                       | 1.5913                       | 0.4669                     |

## Real High-Rate Sidebands

| method                              | method_alias                               | rate_sideband                | n_events | pid_purity | median_pedestal_adc | median_energy_mev | mean_saturation_fraction | mean_failed_fraction |
| ----------------------------------- | ------------------------------------------ | ---------------------------- | -------- | ---------- | ------------------- | ----------------- | ------------------------ | -------------------- |
| template_residual_boosted_stack_new | causal_template_residual_boosted_stack_new | clean_same_run_control       | 330      | 0.8182     | -50.8435            | 61.2639           | 0.2909                   | 0.7515               |
| template_residual_boosted_stack_new | causal_template_residual_boosted_stack_new | controlled_overlap_high_rate | 330      | 0.8045     | -48.1171            | 59.7174           | 0.4364                   | 0.3394               |

## Negative Controls

| method                              | method_alias                                                | pedestal_leakage_abs_corr | saturation_mask_sensitivity | source_run_memorization_abs_corr | energy_score_abs_corr | pileup_score_abs_corr | winner_score |
| ----------------------------------- | ----------------------------------------------------------- | ------------------------- | --------------------------- | -------------------------------- | --------------------- | --------------------- | ------------ |
| template_residual_boosted_stack_new | causal_template_residual_boosted_stack_new                  | 0.0111                    | 0.0109                      | 0.0767                           | 0.1129                | 0.0099                | 0.2397       |
| gradient_boosted_trees              | gradient_boosted_trees                                      | 0.0193                    | 0.0149                      | 0.0739                           | 0.0969                | 0.0094                | 0.2435       |
| ridge                               | ridge                                                       | 0.0171                    | 0.0250                      | 0.0819                           | 0.2506                | 0.0166                | 0.2959       |
| 1d_cnn                              | 1d_cnn                                                      | 0.0165                    | 0.0509                      | 0.0743                           | 0.3011                | 0.0220                | 0.3209       |
| deltaE_over_E_likelihood_template   | sparse_nn_template_bayesian_deltaE_E_likelihood_traditional | 0.0279                    | 0.1259                      | 0.0389                           | 0.6088                | 0.0087                | 0.3463       |
| mlp                                 | mlp                                                         | 0.0229                    | 0.0466                      | 0.0488                           | 0.4007                | 0.0009                | 0.4447       |
| joint_sequence_transformer          | sequence_transformer                                        | 0.0868                    | 0.0094                      | 0.0513                           | 0.0250                | 0.4447                | 0.5267       |

The winner's pedestal leakage correlation is
`0.0111`, saturation-mask sensitivity is
`0.0109`, and source-run memorization
correlation is `0.0767`.  These
controls are nonzero, so the ML result is not treated as a causal discovery
claim; it is a held-out predictive benchmark with explicit nuisance audits.

## Systematics and Caveats

The raw ROOT gate validates selected-pulse support and channel semantics, not
the absolute GEANT4 material model, scintillation quenching, digitizer response,
or trigger acceptance.  The controlled overlays are synthetic stress tests
anchored to raw waveforms; real high-rate sidebands are used as consistency
checks but do not provide independent PID truth.  Run-block bootstrap intervals
are conservative relative to event bootstrap intervals, yet only five held-out
runs are available.  The transformer is disadvantaged by the short 18-sample
waveform and the modest held-out sample size; the result should not be read as
a general rejection of attention models.

## Conclusion

Use **`causal_template_residual_boosted_stack_new`** as the S59c benchmark winner.  The practical conclusion
is that the strongest result comes from residualizing a traditional
template/likelihood solution, not from replacing detector structure with an
unconstrained network.  Pile-up and saturation remain first-order nuisances:
the traditional method is retained as the calibration monitor, while the
residual architecture is preferred for the best held-out PID-energy score.
