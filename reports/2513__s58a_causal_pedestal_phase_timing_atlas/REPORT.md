# S58a/#2513: Causal Pedestal-Phase Pulse-Shape Timing Atlas

## Abstract

This ticket benchmarks a strong traditional generalized least-squares matched-template/CFD timing correction against ridge regression, gradient-boosted trees, MLP, 1D-CNN, a compact waveform transformer, and a new causal pedestal-phase CNN. The raw ROOT selected-pulse number is reproduced before model fitting. The benchmark is split by held-out run and uses paired run bootstrap confidence intervals. The selected winner written to `result.json` is **mlp**.

## Ticket and Data Provenance

Claim recovery was necessary because `tn-ticket claim testbeam-laptop-3 --project testbeam` returned the known `null` pseudo-ticket pattern without labeling an issue. The claimed issue is #2513 after a direct label swap to `factory:claimed` and `worker:testbeam-laptop-3`; the helper was not run a second time.

Ticket text: `claim_helper_command: tn-ticket claim testbeam-laptop-3 --project testbeam claim_helper_stderr: null claim_helper_stdout: # null  null manual_claim_issue: 2513 manual_claim_command: gh issue edit 2513 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-3 --remove-label factory:open #2513 NEW S58a causal pedestal-phase pulse-shape timing atlas Question: Can a causal pedestal-state plus phase model separate pulse-shape drift from timing bias under mild pile-up?  Compare traditional generalized least-squares matched-template/CFD fits against ridge, gradient-boosted trees, MLP, 1D-CNN, and a small waveform transformer. Use run-heldout splits, pedestal strata, pile-up strata, and bootstrap CIs for timing bias, sigma68, shape residuals, and failure rates.  Deliverable: a compact scoreboard plus calibration plots identifying where pedestal memory changes pulse shape versus timing pickoff. `

Raw `h101/HRDv` waveforms were read from `data/extracted/root/root`. The B-stave channels are `{'B2': 0, 'B4': 2, 'B6': 4, 'B8': 6}`. A selected pulse is a baseline-subtracted B-stave channel with amplitude above `1000` ADC using the four pretrigger samples.

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

## Traditional Generalized Least-Squares Matched-Template/CFD Method

The traditional method estimates a median pulse template from training runs only after four-sample pedestal subtraction and amplitude normalization. For each held-out pair, the method computes a matched-filter correlation, a rise-tail balance, a leading-edge/time-walk axis, pedestal state, phase state, amplitude-ratio bins, and pair identity. It predicts the run-excluded median residual from the most specific populated calibration cell, backing off to coarser cells. This is deliberately stronger than a bare CFD correction because it combines constant-fraction timing with analytic pulse-shape and template time-walk terms while preserving run-held-out calibration.

## ML and Neural Comparators

The tabular ML panel uses the same pairwise covariates: ridge regression, histogram gradient-boosted trees, and MLP. The sequence panel uses baseline-subtracted normalized waveform pairs. The 1D-CNN is a compact convolutional regressor. The compact pair transformer uses one self-attention encoder layer over the 18 waveform samples. The new architecture is `causal_pedestal_phase_cnn_new`, a causal temporal-convolution head whose waveform branch is gated by pretrigger pedestal, phase, rise, curvature, and tail covariates before residual regression. All methods exclude event identifiers and train only on runs different from the held-out run.

## Primary Results with Paired Run Bootstrap CIs

Bootstrap intervals resample held-out runs with replacement, preserving the method pairing within each sampled run.

| method                              |   n_pairs |   sigma68_ns |   sigma68_ns_ci_low |   sigma68_ns_ci_high |   tail_abs_gt_0p5_ns |   tail_abs_gt_0p5_ns_ci_low |   tail_abs_gt_0p5_ns_ci_high |    bias_ns |   bias_ns_ci_low |   bias_ns_ci_high |   failure_rate |   failure_rate_ci_low |   failure_rate_ci_high |   phase_shape_residual_gap_ns |   phase_shape_residual_gap_ns_ci_low |   phase_shape_residual_gap_ns_ci_high |   delta_sigma68_vs_traditional_ns_ci_low |   delta_sigma68_vs_traditional_ns_ci_high |
|:------------------------------------|----------:|-------------:|--------------------:|---------------------:|---------------------:|----------------------------:|-----------------------------:|-----------:|-----------------:|------------------:|---------------:|----------------------:|-----------------------:|------------------------------:|-------------------------------------:|--------------------------------------:|-----------------------------------------:|------------------------------------------:|
| uncorrected_cfd20                   |     18098 |     2.94278  |            2.84571  |             3.04095  |             0.922643 |                    0.917151 |                     0.929277 | -3.41237   |       -3.52769   |        -3.30667   |              0 |                     0 |                      0 |                     0.691453  |                           0.188158   |                              1.30286  |                                 1.52805  |                                 1.75521   |
| traditional_matched_filter_template |     18098 |     1.30072  |            1.26263  |             1.34579  |             0.696873 |                    0.690864 |                     0.705891 | -0.397496  |       -0.477736  |        -0.317713  |              0 |                     0 |                      0 |                     0.715781  |                           0.234361   |                              1.23605  |                                 0        |                                 0         |
| ridge                               |     18098 |     2.48476  |            2.44831  |             2.5404   |             0.844237 |                    0.838292 |                     0.853681 | -0.0170447 |       -0.212936  |         0.1674    |              0 |                     0 |                      0 |                     0.400855  |                           0.126906   |                              0.622408 |                                 1.11988  |                                 1.25846   |
| gradient_boosted_trees              |     18098 |     0.689074 |            0.671784 |             0.714079 |             0.441264 |                    0.432942 |                     0.457101 | -0.030585  |       -0.0708685 |         0.0410247 |              0 |                     0 |                      0 |                     0.0928773 |                           0.00362317 |                              0.284334 |                                -0.644074 |                                -0.578343  |
| mlp                                 |     18098 |     0.602287 |            0.523414 |             0.677548 |             0.395679 |                    0.345164 |                     0.445832 | -0.017275  |       -0.0705449 |         0.0761916 |              0 |                     0 |                      0 |                     0.098909  |                           0.00735567 |                              0.222739 |                                -0.750561 |                                -0.644271  |
| one_dimensional_cnn                 |     18098 |     1.14555  |            1.12565  |             1.17541  |             0.661233 |                    0.652902 |                     0.672947 | -0.292863  |       -0.417228  |        -0.153757  |              0 |                     0 |                      0 |                     0.482258  |                           0.0906173  |                              0.864985 |                                -0.195802 |                                -0.0975889 |
| compact_pair_transformer            |     18098 |     1.12518  |            1.10336  |             1.14845  |             0.658857 |                    0.649974 |                     0.667705 | -0.318006  |       -0.464062  |        -0.10877   |              0 |                     0 |                      0 |                     0.359934  |                           0.0695531  |                              0.666755 |                                -0.222141 |                                -0.127467  |
| causal_pedestal_phase_cnn_new       |     18098 |     1.10376  |            1.09161  |             1.12051  |             0.643773 |                    0.633985 |                     0.655441 | -0.281976  |       -0.414066  |        -0.130062  |              0 |                     0 |                      0 |                     0.392185  |                           0.0568246  |                              0.701815 |                                -0.24087  |                                -0.157376  |

## Per-Run Stability

| method                              |   run |   n_pairs |   sigma68_ns |   tail_abs_gt_0p5_ns |      bias_ns |   failure_rate |   phase_shape_residual_gap_ns |
|:------------------------------------|------:|----------:|-------------:|---------------------:|-------------:|---------------:|------------------------------:|
| causal_pedestal_phase_cnn_new       |    58 |       353 |     1.36187  |             0.671388 |  0.661687    |              0 |                   2.16506     |
| causal_pedestal_phase_cnn_new       |    59 |      3753 |     1.08705  |             0.648015 | -0.404203    |              0 |                   0.63124     |
| causal_pedestal_phase_cnn_new       |    60 |      3700 |     1.1033   |             0.637027 | -0.200988    |              0 |                   0.860642    |
| causal_pedestal_phase_cnn_new       |    61 |      4245 |     1.09325  |             0.625677 | -0.415698    |              0 |                   0.034701    |
| causal_pedestal_phase_cnn_new       |    62 |      3833 |     1.09569  |             0.65797  | -0.0790466   |              0 |                   0.308519    |
| causal_pedestal_phase_cnn_new       |    63 |      1816 |     1.08651  |             0.64978  | -0.53283     |              0 |                   0.92535     |
| causal_pedestal_phase_cnn_new       |    65 |       398 |     1.11235  |             0.670854 | -0.102789    |              0 |                   0.157055    |
| compact_pair_transformer            |    58 |       353 |     1.2919   |             0.699717 |  0.684628    |              0 |                   2.3757      |
| compact_pair_transformer            |    59 |      3753 |     1.11663  |             0.661871 | -0.544898    |              0 |                   0.519695    |
| compact_pair_transformer            |    60 |      3700 |     1.12637  |             0.657027 | -0.377314    |              0 |                   0.897986    |
| compact_pair_transformer            |    61 |      4245 |     1.12173  |             0.649941 | -0.470513    |              0 |                   0.0288581   |
| compact_pair_transformer            |    62 |      3833 |     1.09585  |             0.67258  | -0.000550314 |              0 |                   0.303513    |
| compact_pair_transformer            |    63 |      1816 |     1.04786  |             0.639868 | -0.351184    |              0 |                   0.4382      |
| compact_pair_transformer            |    65 |       398 |     1.28414  |             0.660804 |  0.20431     |              0 |                   0.00569212  |
| gradient_boosted_trees              |    58 |       353 |     0.977888 |             0.558074 |  0.789661    |              0 |                   2.7409      |
| gradient_boosted_trees              |    59 |      3753 |     0.654952 |             0.426059 | -0.0672099   |              0 |                   0.110897    |
| gradient_boosted_trees              |    60 |      3700 |     0.695183 |             0.434324 |  0.0115068   |              0 |                   0.018865    |
| gradient_boosted_trees              |    61 |      4245 |     0.67937  |             0.437456 | -0.0978763   |              0 |                   0.162507    |
| gradient_boosted_trees              |    62 |      3833 |     0.688222 |             0.440125 | -0.00922048  |              0 |                   0.104933    |
| gradient_boosted_trees              |    63 |      1816 |     0.701847 |             0.463106 | -0.0848777   |              0 |                   0.000488737 |
| gradient_boosted_trees              |    65 |       398 |     0.759748 |             0.497487 | -0.0443427   |              0 |                   0.0242238   |
| mlp                                 |    58 |       353 |     1.13551  |             0.535411 |  1.18277     |              0 |                   1.62036     |
| mlp                                 |    59 |      3753 |     0.486737 |             0.331202 | -0.082928    |              0 |                   0.0111988   |
| mlp                                 |    60 |      3700 |     0.513305 |             0.328378 | -0.0164109   |              0 |                   0.0914574   |
| mlp                                 |    61 |      4245 |     0.670679 |             0.435807 | -0.00239354  |              0 |                   0.17282     |
| mlp                                 |    62 |      3833 |     0.642945 |             0.426298 | -0.0244877   |              0 |                   0.0299154   |
| mlp                                 |    63 |      1816 |     0.641385 |             0.46696  | -0.164774    |              0 |                   0.0686558   |
| mlp                                 |    65 |       398 |     0.691622 |             0.457286 |  0.113164    |              0 |                   0.211958    |
| one_dimensional_cnn                 |    58 |       353 |     1.37073  |             0.685552 |  0.564655    |              0 |                   2.14425     |
| one_dimensional_cnn                 |    59 |      3753 |     1.18842  |             0.678124 | -0.155602    |              0 |                   0.618102    |
| one_dimensional_cnn                 |    60 |      3700 |     1.13791  |             0.651622 | -0.33368     |              0 |                   1.10637     |
| one_dimensional_cnn                 |    61 |      4245 |     1.14216  |             0.648528 | -0.435532    |              0 |                   0.0228502   |
| one_dimensional_cnn                 |    62 |      3833 |     1.10713  |             0.659014 | -0.220365    |              0 |                   0.33318     |
| one_dimensional_cnn                 |    63 |      1816 |     1.1364   |             0.670705 | -0.582701    |              0 |                   0.922937    |
| one_dimensional_cnn                 |    65 |       398 |     1.14902  |             0.683417 |  0.177654    |              0 |                   0.169338    |
| ridge                               |    58 |       353 |     3.05307  |             0.858357 |  1.35613     |              0 |                   1.84334     |
| ridge                               |    59 |      3753 |     2.51539  |             0.843059 | -0.0547327   |              0 |                   0.109667    |
| ridge                               |    60 |      3700 |     2.50951  |             0.838919 |  0.236933    |              0 |                   0.696385    |
| ridge                               |    61 |      4245 |     2.40224  |             0.83298  | -0.242949    |              0 |                   0.461215    |
| ridge                               |    62 |      3833 |     2.51325  |             0.849204 |  0.0749275   |              0 |                   0.225524    |
| ridge                               |    63 |      1816 |     2.49056  |             0.863987 | -0.473       |              0 |                   0.957676    |
| ridge                               |    65 |       398 |     2.47766  |             0.874372 |  0.363478    |              0 |                   0.336912    |
| traditional_matched_filter_template |    58 |       353 |     1.34652  |             0.730878 |  0.117073    |              0 |                   1.05673     |
| traditional_matched_filter_template |    59 |      3753 |     1.24574  |             0.686917 | -0.406612    |              0 |                   1.02131     |
| traditional_matched_filter_template |    60 |      3700 |     1.26842  |             0.693514 | -0.518767    |              0 |                   1.5466      |
| traditional_matched_filter_template |    61 |      4245 |     1.2924   |             0.70318  | -0.300951    |              0 |                   0.145001    |
| traditional_matched_filter_template |    62 |      3833 |     1.26135  |             0.693191 | -0.356823    |              0 |                   0.589767    |
| traditional_matched_filter_template |    63 |      1816 |     1.32222  |             0.698238 | -0.58081     |              0 |                   0.698716    |
| traditional_matched_filter_template |    65 |       398 |     1.48111  |             0.753769 | -0.225564    |              0 |                   0.227962    |
| uncorrected_cfd20                   |    58 |       353 |     2.8642   |             0.923513 | -2.85184     |              0 |                   1.13281     |
| uncorrected_cfd20                   |    59 |      3753 |     2.95704  |             0.928324 | -3.47279     |              0 |                   0.754947    |
| uncorrected_cfd20                   |    60 |      3700 |     2.96349  |             0.917027 | -3.51308     |              0 |                   1.72152     |
| uncorrected_cfd20                   |    61 |      4245 |     2.7526   |             0.912603 | -3.26935     |              0 |                   0.0840217   |
| uncorrected_cfd20                   |    62 |      3833 |     3.00859  |             0.926689 | -3.32187     |              0 |                   0.542407    |
| uncorrected_cfd20                   |    63 |      1816 |     3.18528  |             0.932269 | -3.71769     |              0 |                   0.994002    |
| uncorrected_cfd20                   |    65 |       398 |     2.58048  |             0.944724 | -3.40749     |              0 |                   0.0787976   |

## Stratified Diagnostics

The requested pedestal, pile-up, shape, energy, and PID-proxy stratifications are operational proxies from waveform observables, since no external PID truth or calibrated energy truth is available in this raw ROOT panel. Near-threshold energy is defined by the lower pair amplitude, PID proxy by pair charge sum, pedestal state by pretrigger RMS/range, mild pile-up by late-tail/width asymmetry, and phase state by peak displacement plus leading curvature.

| stratum               | value             | method                              |   n_pairs |   sigma68_ns |   tail_abs_gt_0p5_ns |      bias_ns |
|:----------------------|:------------------|:------------------------------------|----------:|-------------:|---------------------:|-------------:|
| pid_proxy             | high_charge       | causal_pedestal_phase_cnn_new       |      9049 |     1.14055  |             0.656647 | -0.308883    |
| pid_proxy             | high_charge       | compact_pair_transformer            |      9049 |     1.16829  |             0.675765 | -0.322243    |
| pid_proxy             | high_charge       | gradient_boosted_trees              |      9049 |     0.673437 |             0.429329 | -0.0369966   |
| pid_proxy             | high_charge       | mlp                                 |      9049 |     0.601786 |             0.394187 |  0.000880963 |
| pid_proxy             | high_charge       | one_dimensional_cnn                 |      9049 |     1.18786  |             0.670129 | -0.323683    |
| pid_proxy             | high_charge       | ridge                               |      9049 |     2.45995  |             0.846392 | -0.00662568  |
| pid_proxy             | high_charge       | traditional_matched_filter_template |      9049 |     1.26191  |             0.690353 | -0.277123    |
| pid_proxy             | high_charge       | uncorrected_cfd20                   |      9049 |     3.0131   |             0.938667 | -3.36938     |
| pid_proxy             | low_charge        | causal_pedestal_phase_cnn_new       |      9049 |     1.06189  |             0.630898 | -0.255069    |
| pid_proxy             | low_charge        | compact_pair_transformer            |      9049 |     1.07806  |             0.641949 | -0.313768    |
| pid_proxy             | low_charge        | gradient_boosted_trees              |      9049 |     0.702413 |             0.453199 | -0.0241733   |
| pid_proxy             | low_charge        | mlp                                 |      9049 |     0.602483 |             0.397171 | -0.0354311   |
| pid_proxy             | low_charge        | one_dimensional_cnn                 |      9049 |     1.11323  |             0.652337 | -0.262044    |
| pid_proxy             | low_charge        | ridge                               |      9049 |     2.50473  |             0.842082 | -0.0274637   |
| pid_proxy             | low_charge        | traditional_matched_filter_template |      9049 |     1.33341  |             0.703393 | -0.51787     |
| pid_proxy             | low_charge        | uncorrected_cfd20                   |      9049 |     2.92452  |             0.90662  | -3.45537     |
| near_threshold_energy | above_threshold   | causal_pedestal_phase_cnn_new       |     16111 |     1.09729  |             0.643473 | -0.269596    |
| near_threshold_energy | above_threshold   | compact_pair_transformer            |     16111 |     1.11205  |             0.657936 | -0.308649    |
| near_threshold_energy | above_threshold   | gradient_boosted_trees              |     16111 |     0.668719 |             0.42952  | -0.0393044   |
| near_threshold_energy | above_threshold   | mlp                                 |     16111 |     0.585729 |             0.384458 | -0.0281321   |
| near_threshold_energy | above_threshold   | one_dimensional_cnn                 |     16111 |     1.13743  |             0.661101 | -0.270988    |
| near_threshold_energy | above_threshold   | ridge                               |     16111 |     2.3858   |             0.839426 | -0.0223927   |
| near_threshold_energy | above_threshold   | traditional_matched_filter_template |     16111 |     1.28439  |             0.693377 | -0.320677    |
| near_threshold_energy | above_threshold   | uncorrected_cfd20                   |     16111 |     2.91216  |             0.933462 | -3.44724     |
| near_threshold_energy | near_threshold    | causal_pedestal_phase_cnn_new       |      1987 |     1.15831  |             0.6462   | -0.382359    |
| near_threshold_energy | near_threshold    | compact_pair_transformer            |      1987 |     1.20807  |             0.666331 | -0.393873    |
| near_threshold_energy | near_threshold    | gradient_boosted_trees              |      1987 |     0.884384 |             0.536487 |  0.0401141   |
| near_threshold_energy | near_threshold    | mlp                                 |      1987 |     0.745581 |             0.486663 |  0.0707565   |
| near_threshold_energy | near_threshold    | one_dimensional_cnn                 |      1987 |     1.19999  |             0.662305 | -0.470229    |
| near_threshold_energy | near_threshold    | ridge                               |      1987 |     3.65792  |             0.883241 |  0.0263181   |
| near_threshold_energy | near_threshold    | traditional_matched_filter_template |      1987 |     1.48489  |             0.725214 | -1.02036     |
| near_threshold_energy | near_threshold    | uncorrected_cfd20                   |      1987 |     3.0347   |             0.834927 | -3.12969     |
| pedestal_state        | active_pedestal   | causal_pedestal_phase_cnn_new       |      6034 |     0.991706 |             0.592145 | -0.436731    |
| pedestal_state        | active_pedestal   | compact_pair_transformer            |      6034 |     1.03483  |             0.613689 | -0.510721    |
| pedestal_state        | active_pedestal   | gradient_boosted_trees              |      6034 |     0.818451 |             0.510938 | -0.131949    |
| pedestal_state        | active_pedestal   | mlp                                 |      6034 |     0.547252 |             0.363109 | -0.0287939   |
| pedestal_state        | active_pedestal   | one_dimensional_cnn                 |      6034 |     1.05285  |             0.616506 | -0.606223    |
| pedestal_state        | active_pedestal   | ridge                               |      6034 |     3.03895  |             0.859794 | -0.248024    |
| pedestal_state        | active_pedestal   | traditional_matched_filter_template |      6034 |     1.28207  |             0.690089 | -0.716496    |
| pedestal_state        | active_pedestal   | uncorrected_cfd20                   |      6034 |     2.84272  |             0.893437 | -3.06846     |
| pedestal_state        | moderate_pedestal | causal_pedestal_phase_cnn_new       |      6031 |     1.14794  |             0.671696 | -0.287441    |
| pedestal_state        | moderate_pedestal | compact_pair_transformer            |      6031 |     1.17149  |             0.683966 | -0.312743    |
| pedestal_state        | moderate_pedestal | gradient_boosted_trees              |      6031 |     0.65348  |             0.426297 | -0.0113268   |
| pedestal_state        | moderate_pedestal | mlp                                 |      6031 |     0.641894 |             0.428619 | -0.0396872   |
| pedestal_state        | moderate_pedestal | one_dimensional_cnn                 |      6031 |     1.18924  |             0.686619 | -0.227325    |
| pedestal_state        | moderate_pedestal | ridge                               |      6031 |     2.33861  |             0.83734  |  0.0403907   |
| pedestal_state        | moderate_pedestal | traditional_matched_filter_template |      6031 |     1.30203  |             0.696899 | -0.395307    |
| pedestal_state        | moderate_pedestal | uncorrected_cfd20                   |      6031 |     2.96607  |             0.934008 | -3.71995     |
| pedestal_state        | quiet_pedestal    | causal_pedestal_phase_cnn_new       |      6033 |     1.14455  |             0.667495 | -0.121733    |
| pedestal_state        | quiet_pedestal    | compact_pair_transformer            |      6033 |     1.15762  |             0.678933 | -0.130519    |
| pedestal_state        | quiet_pedestal    | gradient_boosted_trees              |      6033 |     0.603237 |             0.386541 |  0.0515436   |
| pedestal_state        | quiet_pedestal    | mlp                                 |      6033 |     0.615319 |             0.395326 |  0.0166504   |
| pedestal_state        | quiet_pedestal    | one_dimensional_cnn                 |      6033 |     1.17945  |             0.68059  | -0.0449682   |
| pedestal_state        | quiet_pedestal    | ridge                               |      6033 |     2.25455  |             0.835571 |  0.156557    |
| pedestal_state        | quiet_pedestal    | traditional_matched_filter_template |      6033 |     1.31425  |             0.70363  | -0.0806331   |
| pedestal_state        | quiet_pedestal    | uncorrected_cfd20                   |      6033 |     2.88437  |             0.940494 | -3.44886     |
| pileup_state          | mild_pileup       | causal_pedestal_phase_cnn_new       |      4525 |     1.34897  |             0.685304 | -0.849077    |
| pileup_state          | mild_pileup       | compact_pair_transformer            |      4525 |     1.36426  |             0.699669 | -0.774335    |
| pileup_state          | mild_pileup       | gradient_boosted_trees              |      4525 |     0.893766 |             0.530387 | -0.143232    |
| pileup_state          | mild_pileup       | mlp                                 |      4525 |     0.795491 |             0.48884  |  0.0358204   |
| pileup_state          | mild_pileup       | one_dimensional_cnn                 |      4525 |     1.37156  |             0.699006 | -0.88762     |
| pileup_state          | mild_pileup       | ridge                               |      4525 |     2.6733   |             0.847293 | -0.100216    |
| pileup_state          | mild_pileup       | traditional_matched_filter_template |      4525 |     1.38436  |             0.710055 | -1.02554     |
| pileup_state          | mild_pileup       | uncorrected_cfd20                   |      4525 |     3.26287  |             0.925525 | -3.46694     |
| pileup_state          | single_like       | causal_pedestal_phase_cnn_new       |     13573 |     1.03948  |             0.629927 | -0.0929145   |
| pileup_state          | single_like       | compact_pair_transformer            |     13573 |     1.06102  |             0.645252 | -0.165873    |
| pileup_state          | single_like       | gradient_boosted_trees              |     13573 |     0.63619  |             0.411552 |  0.00696943  |
| pileup_state          | single_like       | mlp                                 |     13573 |     0.551589 |             0.364621 | -0.0349761   |
| pileup_state          | single_like       | one_dimensional_cnn                 |     13573 |     1.08733  |             0.648641 | -0.0945818   |
| pileup_state          | single_like       | ridge                               |     13573 |     2.41744  |             0.843218 |  0.0106832   |
| pileup_state          | single_like       | traditional_matched_filter_template |     13573 |     1.26909  |             0.692478 | -0.188119    |
| pileup_state          | single_like       | uncorrected_cfd20                   |     13573 |     2.79828  |             0.921683 | -3.39418     |
| phase_state           | phase_nominal     | causal_pedestal_phase_cnn_new       |     13573 |     1.06833  |             0.633021 | -0.183919    |
| phase_state           | phase_nominal     | compact_pair_transformer            |     13573 |     1.09174  |             0.650998 | -0.228012    |
| phase_state           | phase_nominal     | gradient_boosted_trees              |     13573 |     0.669407 |             0.431592 | -0.0538069   |
| phase_state           | phase_nominal     | mlp                                 |     13573 |     0.590641 |             0.387239 | -0.042005    |
| phase_state           | phase_nominal     | one_dimensional_cnn                 |     13573 |     1.11938  |             0.652251 | -0.172285    |
| phase_state           | phase_nominal     | ridge                               |     13573 |     2.35114  |             0.837324 |  0.0831802   |
| phase_state           | phase_nominal     | traditional_matched_filter_template |     13573 |     1.25692  |             0.686878 | -0.218531    |
| phase_state           | phase_nominal     | uncorrected_cfd20                   |     13573 |     2.86891  |             0.920651 | -3.23949     |
| phase_state           | phase_shifted     | causal_pedestal_phase_cnn_new       |      4525 |     1.20214  |             0.676022 | -0.576104    |
| phase_state           | phase_shifted     | compact_pair_transformer            |      4525 |     1.22801  |             0.682431 | -0.587946    |
| phase_state           | phase_shifted     | gradient_boosted_trees              |      4525 |     0.766177 |             0.470276 |  0.0390705   |
| phase_state           | phase_shifted     | mlp                                 |      4525 |     0.639003 |             0.420994 |  0.056904    |
| phase_state           | phase_shifted     | one_dimensional_cnn                 |      4525 |     1.23644  |             0.688177 | -0.654543    |
| phase_state           | phase_shifted     | ridge                               |      4525 |     2.97479  |             0.864972 | -0.317675    |
| phase_state           | phase_shifted     | traditional_matched_filter_template |      4525 |     1.4558   |             0.726851 | -0.934312    |
| phase_state           | phase_shifted     | uncorrected_cfd20                   |      4525 |     3.18629  |             0.928619 | -3.93094     |

## Systematics

The main systematic is that pair residuals are not an absolute external clock; common-mode timing errors can cancel. Bootstrap intervals have seven independent held-out run units and should be read as run-transfer uncertainty rather than asymptotic precision. The PID and energy strata are waveform-charge proxies, not externally calibrated particle labels or MeV energies. Pedestal and pile-up states are causal pretrigger/tail observables rather than interventions. Hyperparameters are intentionally compact for reproducibility on the worker. The matched-filter template and every ML model are trained inside each fold, so leakage through held-out waveforms is controlled, but remaining electronics-current or beam-condition metadata are not modeled explicitly.

## Caveats

The study ranks correction capacity for same-event downstream-pair timing, not absolute detector timing. It does not establish that a neural method is safe for publication without external clock validation. Rare pulse families are bounded by the raw ROOT selected-pulse support and by the modest sequence-model size. Conclusions for near-threshold and PID-proxy bins should be treated as diagnostic until an external PID or beamline truth join exists.

## Conclusion

The winner named in `result.json` is `mlp` by the registered rule: lowest held-out `sigma68_ns` among correction methods, with tail fraction and absolute bias as tie breakers. No more than one novel follow-up ticket is proposed: external trigger validation for this same causal pedestal-phase method panel.
