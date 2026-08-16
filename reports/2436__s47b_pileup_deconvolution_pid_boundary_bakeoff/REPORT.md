# S47b: Pile-up Deconvolution PID Boundary Robustness Bakeoff

## Abstract

Ticket `#2436` was claimed for worker `testbeam-laptop-1`.  The study tests whether explicit pile-up deconvolution and learned waveform representations improve PID-boundary robustness under overlapping pulses, saturation, pedestal variation, and timing/energy coupling.  The method panel contains the required strong traditional comparator, ridge, gradient-boosted trees, MLP, 1D-CNN, a sequence transformer, and a new hybrid architecture.  The winner named in `result.json` is **template_residual_boosted_stack_new**, selected by minimum held-out run-block composite score `0.21571`.

## Reproduction Anchor

The canonical selected-pulse count is reproduced directly from raw B-stack ROOT files under `/home/billy/ccb-data/data/extracted/root/root`.  For each run, `h101/HRDv` is reshaped to `(event, channel, sample)` with 18 samples per channel.  Physical B staves are channels 0, 2, 4, and 6.

| quantity                           |   expected |   reproduced |   delta | pass   |
|:-----------------------------------|-----------:|-------------:|--------:|:-------|
| S00 selected B-stave pulse records |     640737 |       640737 |       0 | True   |

The reproduced selection is the B-stack pulse indicator

`I_ec = 1[max_t(x_ect - median(x_ec, t=0..3)) > 1000 ADC]`,

aggregated over B2/B4/B6/B8.  Per-run raw ROOT counts and file hashes are written to `reproduction_counts_by_run.csv`; the S00 raw-derived table hash used as the expected-count cross-check is `648c32d0109fb05cdf04b2a0d2817044067e8741c70a53f540308a1c038a8b2f`.

## Data And Split

The benchmark table is the keyed GEANT4/native-digitizer event prediction panel from `/home/billy/ccb-testbeam/reports/1784176179.839.48902217__s39c_likelihood_pid_boundaries_multitask_classifiers/source_event_predictions_selected_methods.csv.gz`.  It contains `7392` method-event rows over train runs `[50, 51, 52, 53, 54, 55, 56, 57]` and held-out runs `[58, 60, 62, 64, 65]`.  All headline metrics below use held-out runs only; confidence intervals resample held-out source runs with replacement for `600` bootstrap replicates.

PID truth is the GEANT4 Sci-bar dominant proton/deuteron label in the keyed benchmark.  Energy residuals are fractional residuals `(Ehat-Etrue)/Etrue`.  Timing residuals are in ns.  Pile-up and saturation strata are truth labels carried by the source benchmark.

## Methods

The traditional comparator is `deltaE_over_E_likelihood_template`, a charge/shape likelihood-template PID boundary with explicit dE/E-like structure and deterministic deconvolution failure handling.  Learned comparators are:

| method | family | role |
|---|---|---|
| ridge | linear ML | regularized linear/logistic baseline |
| gradient_boosted_trees | tree ML | nonlinear tabular residual learner |
| mlp | neural tabular | dense neural baseline |
| 1d_cnn | neural convolutional | waveform-local convolutional model |
| joint_sequence_transformer | neural sequence | compact self-attention pulse model |
| template_residual_boosted_stack_new | new hybrid architecture | template residual stack combining physics-template features with boosted residual heads |

## Metrics

For method `m`, PID discrimination is `AUC(Y, s_m)`.  The hard PID boundary is `1[s_m >= 0.5]`; confusion matrices use labels `[proton_like=0, deuteron_like=1]`.  Energy resolution is

`sigma_68(r_E) = 0.5 [Q_84(r_E) - Q_16(r_E)]`.

The registered score is

`L_m = 0.30(1-AUC_PID) + 0.20(1-BAcc_PID) + 0.20 sigma68_E + 0.008 sigma68_t + 0.12 r_miss + 0.08 max(0,AUC_unsat-AUC_sat) + 0.07 d_boundary`.

Lower is better.  The score penalizes PID loss, boundary imbalance, energy/timing resolution, failed overlap deconvolution, saturation-specific PID loss, and disagreement with the traditional boundary.

## Overall Held-Out Results

| method                              | family                  |   winner_score |   pid_auc |   pid_auc_ci_low |   pid_auc_ci_high |   pid_balanced_accuracy |   pid_balanced_accuracy_ci_low |   pid_balanced_accuracy_ci_high |   energy_sigma68_frac |   energy_sigma68_frac_ci_low |   energy_sigma68_frac_ci_high |   timing_sigma68_ns |   timing_sigma68_ns_ci_low |   timing_sigma68_ns_ci_high |   pileup_miss_rate |   boundary_disagreement_rate |
|:------------------------------------|:------------------------|---------------:|----------:|-----------------:|------------------:|------------------------:|-------------------------------:|--------------------------------:|----------------------:|-----------------------------:|------------------------------:|--------------------:|---------------------------:|----------------------------:|-------------------:|-----------------------------:|
| template_residual_boosted_stack_new | new_hybrid_architecture |        0.21571 |   0.89463 |          0.86963 |           0.91121 |                 0.832   |                        0.79862 |                         0.86168 |               0.20144 |                      0.18224 |                       0.23319 |              7.3572 |                     6.4642 |                      7.8284 |            0.3125  |                      0.19792 |
| gradient_boosted_trees              | ml_tree                 |        0.22214 |   0.9059  |          0.87252 |           0.92717 |                 0.81915 |                        0.78505 |                         0.85517 |               0.20735 |                      0.17018 |                       0.22374 |              7.292  |                     6.4194 |                      8.1039 |            0.3625  |                      0.20625 |
| 1d_cnn                              | nn_convolutional        |        0.24445 |   0.79262 |          0.74824 |           0.81915 |                 0.72058 |                        0.6958  |                         0.73948 |               0.20005 |                      0.1613  |                       0.2178  |              4.6396 |                     4.2325 |                      5.103  |            0.34583 |                      0.11042 |
| ridge                               | ml_linear               |        0.25175 |   0.82223 |          0.79554 |           0.84669 |                 0.73521 |                        0.71684 |                         0.75042 |               0.18699 |                      0.17324 |                       0.2061  |              7.06   |                     6.0062 |                      8.1646 |            0.36667 |                      0.10833 |
| deltaE_over_E_likelihood_template   | traditional             |        0.30271 |   0.75033 |          0.72246 |           0.77462 |                 0.72757 |                        0.69389 |                         0.75289 |               0.19104 |                      0.16326 |                       0.23569 |              7.7642 |                     6.2082 |                      8.8377 |            0.60833 |                      0       |
| mlp                                 | nn_tabular              |        0.31092 |   0.72599 |          0.6908  |           0.76118 |                 0.66713 |                        0.62319 |                         0.71141 |               0.25274 |                      0.20912 |                       0.28643 |              6.8611 |                     5.7468 |                      8.2698 |            0.3875  |                      0.14583 |
| joint_sequence_transformer          | nn_sequence             |        0.42705 |   0.51125 |          0.4653  |           0.55842 |                 0.49844 |                        0.46813 |                         0.53792 |               0.23751 |                      0.20984 |                       0.26141 |              6.9695 |                     6.4206 |                      7.7072 |            0.40833 |                      0.39792 |

## Method Deltas Versus Traditional

| method                              |   delta_pid_auc_vs_traditional |   delta_energy_sigma68_vs_traditional |   delta_timing_sigma68_vs_traditional_ns |   delta_winner_score_vs_traditional |
|:------------------------------------|-------------------------------:|--------------------------------------:|-----------------------------------------:|------------------------------------:|
| template_residual_boosted_stack_new |                       0.14431  |                             0.010398  |                                 -0.40706 |                          -0.087001  |
| gradient_boosted_trees              |                       0.15557  |                             0.016311  |                                 -0.47224 |                          -0.080565  |
| 1d_cnn                              |                       0.042293 |                             0.0090075 |                                 -3.1247  |                          -0.058256  |
| ridge                               |                       0.071906 |                            -0.004049  |                                 -0.70427 |                          -0.050961  |
| deltaE_over_E_likelihood_template   |                       0        |                             0         |                                  0       |                           0         |
| mlp                                 |                      -0.024333 |                             0.061703  |                                 -0.9031  |                           0.0082127 |
| joint_sequence_transformer          |                      -0.23908  |                             0.046469  |                                 -0.79477 |                           0.12434   |

## Held-Out Run Stability

|   heldout_run | method                              |   n_events |   pid_auc |   pid_balanced_accuracy |   energy_sigma68_frac |   timing_sigma68_ns |   pileup_miss_rate |
|--------------:|:------------------------------------|-----------:|----------:|------------------------:|----------------------:|--------------------:|-------------------:|
|            58 | deltaE_over_E_likelihood_template   |         96 |   0.79172 |                 0.76248 |               0.1417  |              8.8751 |            0.58333 |
|            60 | deltaE_over_E_likelihood_template   |         96 |   0.71788 |                 0.73958 |               0.23813 |              6.109  |            0.58333 |
|            62 | deltaE_over_E_likelihood_template   |         96 |   0.74164 |                 0.67846 |               0.17341 |              7.9124 |            0.60417 |
|            64 | deltaE_over_E_likelihood_template   |         96 |   0.70944 |                 0.69312 |               0.14355 |              5.0994 |            0.66667 |
|            65 | deltaE_over_E_likelihood_template   |         96 |   0.77342 |                 0.76078 |               0.18571 |              8.5619 |            0.60417 |
|            58 | gradient_boosted_trees              |         96 |   0.93612 |                 0.87787 |               0.18421 |              8.0145 |            0.35417 |
|            60 | gradient_boosted_trees              |         96 |   0.92057 |                 0.85417 |               0.22877 |              5.9918 |            0.3125  |
|            62 | gradient_boosted_trees              |         96 |   0.84151 |                 0.7601  |               0.19835 |              7.1153 |            0.39583 |
|            64 | gradient_boosted_trees              |         96 |   0.90035 |                 0.78836 |               0.15832 |              7.6725 |            0.375   |
|            65 | gradient_boosted_trees              |         96 |   0.92288 |                 0.82026 |               0.21218 |              6.2855 |            0.375   |
|            58 | template_residual_boosted_stack_new |         96 |   0.91183 |                 0.86505 |               0.20589 |              7.9146 |            0.27083 |
|            60 | template_residual_boosted_stack_new |         96 |   0.90148 |                 0.88542 |               0.21945 |              6.4071 |            0.29167 |
|            62 | template_residual_boosted_stack_new |         96 |   0.84238 |                 0.7805  |               0.18892 |              7.1011 |            0.35417 |
|            64 | template_residual_boosted_stack_new |         96 |   0.90035 |                 0.79497 |               0.15314 |              5.969  |            0.29167 |
|            65 | template_residual_boosted_stack_new |         96 |   0.91373 |                 0.83137 |               0.24355 |              6.2881 |            0.35417 |

## Pile-Up, Saturation, Pedestal, Energy, Timing, Stave, And PID Strata

| stratum        | value         | method                              |   n_events |   pid_auc |   pid_balanced_accuracy |   energy_sigma68_frac |   timing_sigma68_ns |   pileup_miss_rate |
|:---------------|:--------------|:------------------------------------|-----------:|----------:|------------------------:|----------------------:|--------------------:|-------------------:|
| pileup_bin     | pileup        | deltaE_over_E_likelihood_template   |        240 |   0.747   |                 0.72939 |              0.19667  |              7.1254 |            0.60833 |
| pileup_bin     | single        | deltaE_over_E_likelihood_template   |        240 |   0.7523  |                 0.72285 |              0.17968  |             11.573  |          nan       |
| pileup_bin     | pileup        | template_residual_boosted_stack_new |        240 |   0.86332 |                 0.81176 |              0.19486  |              6.7782 |            0.3125  |
| pileup_bin     | single        | template_residual_boosted_stack_new |        240 |   0.92892 |                 0.84921 |              0.21202  |              7.3427 |          nan       |
| saturation_bin | saturated     | deltaE_over_E_likelihood_template   |        179 |   0.81659 |                 0.78211 |              0.17886  |              7.9104 |            0.68041 |
| saturation_bin | unsaturated   | deltaE_over_E_likelihood_template   |        301 |   0.71935 |                 0.69566 |              0.19869  |              5.9918 |            0.55944 |
| saturation_bin | saturated     | template_residual_boosted_stack_new |        179 |   0.92166 |                 0.85076 |              0.17594  |              7.5766 |            0.3299  |
| saturation_bin | unsaturated   | template_residual_boosted_stack_new |        301 |   0.87619 |                 0.82099 |              0.22187  |              6.9732 |            0.3007  |
| pedestal_bin   | pedestal_high | deltaE_over_E_likelihood_template   |        118 |   0.73293 |                 0.69473 |              0.22216  |              9.0441 |            0.57627 |
| pedestal_bin   | pedestal_low  | deltaE_over_E_likelihood_template   |        181 |   0.73135 |                 0.74294 |              0.18475  |              5.731  |            0.59551 |
| pedestal_bin   | pedestal_mid  | deltaE_over_E_likelihood_template   |        181 |   0.78952 |                 0.73625 |              0.17479  |              6.6011 |            0.6413  |
| pedestal_bin   | pedestal_high | template_residual_boosted_stack_new |        118 |   0.88339 |                 0.818   |              0.2668   |              8.4761 |            0.22034 |
| pedestal_bin   | pedestal_low  | template_residual_boosted_stack_new |        181 |   0.86868 |                 0.81081 |              0.16456  |              6.067  |            0.25843 |
| pedestal_bin   | pedestal_mid  | template_residual_boosted_stack_new |        181 |   0.93397 |                 0.86751 |              0.20165  |              5.1783 |            0.42391 |
| energy_bin     | energy_high   | deltaE_over_E_likelihood_template   |        158 |   0.73128 |                 0.7191  |              0.13697  |              8.4088 |            0.57534 |
| energy_bin     | energy_low    | deltaE_over_E_likelihood_template   |        169 |   0.7149  |                 0.64847 |              0.088093 |              7.3013 |            0.62921 |
| energy_bin     | energy_mid    | deltaE_over_E_likelihood_template   |        153 |   0.80453 |                 0.78704 |              0.13707  |              5.6563 |            0.61538 |
| energy_bin     | energy_high   | template_residual_boosted_stack_new |        158 |   0.85762 |                 0.78275 |              0.16415  |              6.5803 |            0.31507 |
| energy_bin     | energy_low    | template_residual_boosted_stack_new |        169 |   0.87678 |                 0.82106 |              0.091521 |              7.5374 |            0.32584 |
| energy_bin     | energy_mid    | template_residual_boosted_stack_new |        153 |   0.94102 |                 0.87731 |              0.10706  |              7.5352 |            0.29487 |
| timing_bin     | time_early    | deltaE_over_E_likelihood_template   |        148 |   0.9932  |                 0.97959 |              0.16274  |              7.8637 |            0.52308 |
| timing_bin     | time_late     | deltaE_over_E_likelihood_template   |        168 |   0.29647 |                 0.41575 |              0.14726  |              8.7819 |            0.62069 |
| timing_bin     | time_mid      | deltaE_over_E_likelihood_template   |        164 |   0.59651 |                 0.63502 |              0.23675  |              5.0689 |            0.65909 |
| timing_bin     | time_early    | template_residual_boosted_stack_new |        148 |   0.97959 |                 0.97959 |              0.17881  |              7.8135 |            0.26154 |
| timing_bin     | time_late     | template_residual_boosted_stack_new |        168 |   0.66879 |                 0.53995 |              0.19585  |              6.7261 |            0.29885 |
| timing_bin     | time_mid      | template_residual_boosted_stack_new |        164 |   0.77235 |                 0.70145 |              0.20638  |              7.2352 |            0.36364 |
| stave          | B2            | deltaE_over_E_likelihood_template   |        132 |   0.82406 |                 0.7235  |              0.16916  |              4.3822 |            0.73529 |
| stave          | B4            | deltaE_over_E_likelihood_template   |        108 |   0.73878 |                 0.63885 |              0.17019  |              4.8337 |            0.81818 |
| stave          | B6            | deltaE_over_E_likelihood_template   |        121 |   0.70956 |                 0.74426 |              0.17089  |              7.6923 |            0.4918  |
| stave          | B8            | deltaE_over_E_likelihood_template   |        119 |   0.82233 |                 0.81429 |              0.18816  |              7.4829 |            0.375   |
| stave          | B2            | template_residual_boosted_stack_new |        132 |   0.90695 |                 0.83237 |              0.1941   |              4.6477 |            0.47059 |
| stave          | B4            | template_residual_boosted_stack_new |        108 |   0.91725 |                 0.85659 |              0.20252  |              6.7088 |            0.34545 |
| stave          | B6            | template_residual_boosted_stack_new |        121 |   0.86366 |                 0.79413 |              0.22293  |              8.51   |            0.2459  |
| stave          | B8            | template_residual_boosted_stack_new |        119 |   0.90184 |                 0.84529 |              0.20096  |              6.2225 |            0.16071 |
| pid_name       | deuteron      | deltaE_over_E_likelihood_template   |        235 | nan       |                 0.65106 |              0.18577  |              8.4821 |            0.61157 |
| pid_name       | proton        | deltaE_over_E_likelihood_template   |        245 | nan       |                 0.80408 |              0.18182  |              6.9138 |            0.60504 |
| pid_name       | deuteron      | template_residual_boosted_stack_new |        235 | nan       |                 0.86809 |              0.21814  |              6.3583 |            0.32231 |
| pid_name       | proton        | template_residual_boosted_stack_new |        245 | nan       |                 0.79592 |              0.19568  |              7.5992 |            0.30252 |

## Systematics And Caveats

The count anchor is a fresh raw ROOT scan.  The main remaining limitation is the downstream event benchmark: it is a keyed GEANT4/native-digitizer join, not an independent beam-particle species tag.  Follow-up ticket `#2470` records the need to document the alternate raw ROOT mount path and keep byte-level reproduction paths stable across workers.  Failed deconvolutions enter as zero acceptance and are penalized through separation efficiency and pile-up miss rate; energy and timing resolution are computed on accepted rows only.  Bootstrap intervals quantify run-transfer uncertainty across five held-out source runs, not detector hardware systematics or GEANT4 physics-list variation.  The traditional likelihood boundary is used both as a comparator and as the reference for boundary-disagreement rate, so the score intentionally rewards conservative boundary stability in addition to raw AUC.

## Verdict

`result.json` names **template_residual_boosted_stack_new** as the S47b winner.  The result is a robustness benchmark for pile-up deconvolution and PID-boundary behavior under the available keyed benchmark, not a new absolute detector-performance claim.
