# S56c/#2507 Likelihood PID Templates vs Multitask Waveform Networks

**Ticket:** `#2507`  
**Worker:** `testbeam-laptop-2`  
**Raw ROOT directory:** `/home/billy/ccb-data/data/extracted/root/root`  
**Source prediction artifact:** `reports/1783809265.5764.0f2a2dda__s29a_digitized_g4_multitask_truth_benchmark`  
**Git commit at execution:** `b3627abca9fdc535eb8ae51a0791c6c23fe9a688`

## Abstract

Ticket `#2507` asks whether a transparent deltaE-E likelihood-template PID
method with pedestal-state nuisance terms remains competitive against ridge,
gradient-boosted trees, MLP, 1D-CNN waveform heads, and a sensible new
architecture when pedestal state, pile-up, and saturation are allowed to move
PID boundaries and energy-transfer calibration.  The raw selected-pulse
reproduction gate passes exactly: `640737`
selected B-stave pulses versus the reference `640737`, delta
`0`.

The winner named in `result.json` is **`template_residual_boosted_stack_new`** with composite loss
`0.2335`.  Relative to the traditional
`deltaE_over_E_likelihood_template`, the winner changes PID balanced accuracy
by `0.0809`,
energy sigma68 by `-0.01735`,
timing sigma68 by `-3.505` ns,
and pile-up miss rate by `-0.3485`.

## Raw ROOT Reproduction

For each `hrdb_run_NNNN.root`, branch `h101/HRDv` is reshaped into
`(event, channel, sample)` with eighteen samples per channel.  The per-event
pedestal is

`b_{e,c} = median_{t in {0,1,2,3}} x_{e,c,t}`,

and the selected B-stack pulse indicator for B2/B4/B6/B8 channels is

`I_{e,c} = 1[max_t (x_{e,c,t} - b_{e,c}) > 1000 ADC]`.

The reproduced ticket number is

`N = sum_runs sum_e sum_{c in {B2,B4,B6,B8}} I_{e,c}`.

| quantity                           |   expected |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|-----------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |     640737 |       640737 |       0 |           0 | True   |
| sample_i_calib selected_pulses     |     248745 |       248745 |       0 |           0 | True   |
| sample_i_analysis selected_pulses  |     252266 |       252266 |       0 |           0 | True   |
| sample_ii_calib selected_pulses    |      14630 |        14630 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |     125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |      88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |      21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |      11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |       4506 |         4506 |       0 |           0 | True   |

Run-level raw counts are stored in `reproduction_counts_by_run.csv`; the first
and last five rows are shown below.

|   run | group              |   events_total |   selected_pulses |    B2 |   B4 |   B6 |   B8 |
|------:|:-------------------|---------------:|------------------:|------:|-----:|-----:|-----:|
|    31 | sample_i_calib     |          39990 |             27871 | 26948 |  592 |  237 |   94 |
|    32 | sample_i_calib     |          41921 |             28240 | 27316 |  605 |  224 |   95 |
|    33 | sample_i_calib     |          57173 |             48737 | 47724 |  559 |  318 |  136 |
|    34 | sample_i_calib     |          39765 |             34118 | 33373 |  412 |  244 |   89 |
|    35 | sample_i_calib     |          27786 |             11667 | 11029 |  403 |  163 |   72 |
|    61 | sample_ii_analysis |          36535 |             18965 | 11015 | 4401 | 2490 | 1059 |
|    62 | sample_ii_analysis |          37584 |             19089 | 11635 | 4183 | 2342 |  929 |
|    63 | sample_ii_analysis |          37030 |             18817 | 14566 | 2645 | 1153 |  453 |
|    64 | sample_ii_calib    |          35943 |             14630 | 11907 | 1689 |  763 |  271 |
|    65 | sample_ii_analysis |          38424 |             13038 | 11768 |  842 |  323 |  105 |

## Data, Split, and Leakage Controls

The supervised benchmark uses the existing S29a digitized GEANT4 event table
and predictions because that artifact already joins raw-data waveform
templates/residuals to event-aligned GEANT4 PID, energy, timing, pile-up,
saturation, and pedestal truth proxies.  This S56c runner does not refit those
models; it re-scores them for the ticket-specific estimands.  Training and
evaluation are split by source run.  The held-out runs are the five runs present
in `run_heldout_metrics.csv`; no method receives run id, event id, or GEANT4
entry as a predictor in the source benchmark.

The main PID label is deuteron-like versus proton-like from dominant GEANT4
Sci_bar PDG.  Pile-up is the controlled-overlap label, saturation is the clipped
truth-waveform label, and pedestal state is the injected/raw-template pedestal
ADC value binned into held-out tertiles.

## Methods

The traditional comparator is a deltaE-E likelihood template with pedestal-state
nuisance calibration.  With standardized charge-depth variables `z_j` and PID
class `y`,

`log p(z | y, s) = -1/2 sum_j [((z_j - mu_{y,s,j})^2 / sigma_{y,s,j}^2) + log sigma_{y,s,j}^2] + log pi_y`,

where `s` denotes the pedestal/pile-up/saturation state used for diagnostics.
Timing and pile-up components use the same bounded template/CFD machinery as
the source benchmark.

Ridge uses L2-regularized linear heads,

`hat beta = argmin_beta ||y - X beta||_2^2 + lambda ||beta||_2^2`.

Gradient-boosted trees model nonlinear charge, timing, and shape interactions.
The MLP is a dense nonlinear tabular/waveform-summary network.  The 1D-CNN
operates directly on the ordered eighteen-sample waveform.  The available new
architecture is `template_residual_boosted_stack_new`, a physics-residual stack
that uses the transparent likelihood/template solution as a first stage and
learns residual corrections for PID, energy, timing, pile-up, and saturation.
The transformer candidate `joint_sequence_transformer` is retained in the panel
because event-level waveform context is available.

## Estimands and Scoring

For each method `m`, PID efficiency, purity, specificity, and balanced accuracy
are computed from held-out confusion matrices.  The energy residual is

`r_E = (hat E - E_true) / max(E_true, epsilon)`,

with robust width

`sigma68(r_E) = 0.5 [Q_84(r_E) - Q_16(r_E)]`.

Timing uses `sigma68(hat t - t_true)` in ns.  Boundary displacement is the
difference between the local PID-score threshold that maximizes balanced
accuracy inside a pedestal, pile-up, or saturation stratum and the method's
global held-out threshold:

`Delta tau_{m,g} = tau^*_{m,g} - tau^*_m`.

The predeclared S56c loss, lower is better, is

`L_m = sigma_E + 0.01 sigma_t + 0.25(1 - BAcc_PID) + 0.05 r_miss + 0.05 r_false + 0.02 r_tail`.

## Overall Held-Out Results

| method                              | family                 |   winner_score |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|:-----------------------|---------------:|------------------------:|-----------------:|-------------:|----------------------------:|------------------:|-------------------:|-------------------:|
| template_residual_boosted_stack_new | new_architecture       |         0.2335 |                  0.8488 |           0.9055 |       0.8115 |                      0.0829 |            8.0963 |             0.3394 |             0.2485 |
| gradient_boosted_trees              | gradient_boosted_trees |         0.2373 |                  0.8443 |           0.8994 |       0.8082 |                      0.0862 |            8.2219 |             0.3061 |             0.2455 |
| ridge                               | ridge                  |         0.2856 |                  0.7527 |           0.6951 |       0.7835 |                      0.0887 |           10.3409 |             0.2848 |             0.2818 |
| 1d_cnn                              | 1d_cnn                 |         0.2977 |                  0.7771 |           0.7561 |       0.7873 |                      0.1030 |           10.7809 |             0.2879 |             0.2515 |
| deltaE_over_E_likelihood_template   | traditional            |         0.3181 |                  0.7679 |           0.7195 |       0.7946 |                      0.1003 |           11.6018 |             0.6879 |             0.0939 |
| joint_sequence_transformer          | new_transformer        |         0.4003 |                  0.5147 |           0.4421 |       0.5142 |                      0.1224 |           12.3811 |             0.3333 |             0.2212 |
| mlp                                 | mlp                    |         0.4203 |                  0.7026 |           0.6311 |       0.7340 |                      0.1614 |           14.8538 |             0.2970 |             0.2909 |

## Bootstrap Confidence Intervals

The source benchmark supplies percentile 95% intervals from held-out run-block
bootstrap resampling.  These are copied into ticket-local CSV tables and
summarized here.

| method                              | pid_balanced_accuracy_ci   | energy_sigma68_ci       | timing_sigma68_ns_ci    |
|:------------------------------------|:---------------------------|:------------------------|:------------------------|
| template_residual_boosted_stack_new | 0.8488 [0.8128, 0.8749]    | 0.0829 [0.0727, 0.0938] | 8.096 [7.479, 9.023]    |
| gradient_boosted_trees              | 0.8443 [0.8001, 0.8800]    | 0.0862 [0.0839, 0.0933] | 8.222 [7.239, 9.549]    |
| ridge                               | 0.7527 [0.7264, 0.7801]    | 0.0887 [0.0764, 0.1050] | 10.341 [9.310, 11.031]  |
| 1d_cnn                              | 0.7771 [0.7405, 0.8205]    | 0.1030 [0.0861, 0.1322] | 10.781 [9.385, 12.096]  |
| deltaE_over_E_likelihood_template   | 0.7679 [0.7424, 0.7990]    | 0.1003 [0.0917, 0.1206] | 11.602 [9.603, 14.556]  |
| joint_sequence_transformer          | 0.5147 [0.4849, 0.5533]    | 0.1224 [0.1102, 0.1339] | 12.381 [11.424, 14.252] |
| mlp                                 | 0.7026 [0.6792, 0.7250]    | 0.1614 [0.1394, 0.1849] | 14.854 [13.765, 16.572] |

## Run-Held-Out Stability

| method                              |   heldout_run |   pid_balanced_accuracy |   pid_efficiency |   pid_purity |   energy_fractional_sigma68 |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:------------------------------------|--------------:|------------------------:|-----------------:|-------------:|----------------------------:|------------------:|-------------------:|-------------------:|
| deltaE_over_E_likelihood_template   |            58 |                  0.7652 |           0.6667 |       0.8302 |                      0.0920 |           14.6776 |             0.5909 |             0.0909 |
| deltaE_over_E_likelihood_template   |            60 |                  0.8219 |           0.7581 |       0.8545 |                      0.1038 |            9.7415 |             0.6818 |             0.1667 |
| deltaE_over_E_likelihood_template   |            62 |                  0.7862 |           0.7581 |       0.7833 |                      0.0980 |           10.5528 |             0.7424 |             0.0758 |
| deltaE_over_E_likelihood_template   |            64 |                  0.7194 |           0.7222 |       0.7536 |                      0.1100 |           13.1425 |             0.7273 |             0.0758 |
| deltaE_over_E_likelihood_template   |            65 |                  0.7424 |           0.6970 |       0.7667 |                      0.1292 |            6.6517 |             0.6970 |             0.0606 |
| template_residual_boosted_stack_new |            58 |                  0.8864 |           0.9091 |       0.8696 |                      0.0675 |            7.7479 |             0.2424 |             0.3333 |
| template_residual_boosted_stack_new |            60 |                  0.8712 |           0.8710 |       0.8571 |                      0.0929 |            7.3787 |             0.3636 |             0.3333 |
| template_residual_boosted_stack_new |            62 |                  0.8445 |           0.9032 |       0.7887 |                      0.0669 |            9.0623 |             0.3788 |             0.2273 |
| template_residual_boosted_stack_new |            64 |                  0.7778 |           0.8889 |       0.7619 |                      0.0877 |            7.3984 |             0.3939 |             0.1667 |
| template_residual_boosted_stack_new |            65 |                  0.8561 |           0.9545 |       0.7975 |                      0.0934 |            9.0340 |             0.3182 |             0.1818 |

## PID Confusion Matrices by Pedestal, Pile-Up, and Saturation

The winner's held-out PID confusion matrices show where the decision boundary
moves under detector-state changes.

| method                              | stratum        | value                 |   n |   tp |   fp |   tn |   fn |   pid_efficiency |   pid_purity |   pid_specificity |   pid_balanced_accuracy |
|:------------------------------------|:---------------|:----------------------|----:|-----:|-----:|-----:|-----:|-----------------:|-------------:|------------------:|------------------------:|
| template_residual_boosted_stack_new | pedestal_bin   | (-4320.819, -170.068] | 220 |   94 |   23 |   91 |   12 |           0.8868 |       0.8034 |            0.7982 |                  0.8425 |
| template_residual_boosted_stack_new | pedestal_bin   | (-170.068, -8.932]    | 220 |   99 |   22 |   90 |    9 |           0.9167 |       0.8182 |            0.8036 |                  0.8601 |
| template_residual_boosted_stack_new | pedestal_bin   | (-8.932, 609.332]     | 220 |  104 |   24 |   82 |   10 |           0.9123 |       0.8125 |            0.7736 |                  0.8429 |
| template_residual_boosted_stack_new | pileup_bin     | clean                 | 330 |  153 |   34 |  133 |   10 |           0.9387 |       0.8182 |            0.7964 |                  0.8675 |
| template_residual_boosted_stack_new | pileup_bin     | overlap               | 330 |  144 |   35 |  130 |   21 |           0.8727 |       0.8045 |            0.7879 |                  0.8303 |
| template_residual_boosted_stack_new | saturation_bin | saturated             | 240 |  111 |   32 |   90 |    7 |           0.9407 |       0.7762 |            0.7377 |                  0.8392 |
| template_residual_boosted_stack_new | saturation_bin | unsaturated           | 420 |  186 |   37 |  173 |   24 |           0.8857 |       0.8341 |            0.8238 |                  0.8548 |

## Boundary Displacement

| method                              | stratum        | value                 |   n |   global_pid_threshold |   local_pid_threshold |   boundary_displacement |   global_balanced_accuracy |   local_balanced_accuracy |
|:------------------------------------|:---------------|:----------------------|----:|-----------------------:|----------------------:|------------------------:|---------------------------:|--------------------------:|
| template_residual_boosted_stack_new | pedestal_bin   | (-4320.819, -170.068] | 220 |                 0.3956 |                0.2091 |                 -0.1865 |                     0.8489 |                    0.8492 |
| template_residual_boosted_stack_new | pedestal_bin   | (-170.068, -8.932]    | 220 |                 0.3956 |                0.6067 |                  0.2111 |                     0.8489 |                    0.8641 |
| template_residual_boosted_stack_new | pedestal_bin   | (-8.932, 609.332]     | 220 |                 0.3956 |                0.5810 |                  0.1854 |                     0.8489 |                    0.8483 |
| template_residual_boosted_stack_new | pileup_bin     | clean                 | 330 |                 0.3956 |                0.4778 |                  0.0821 |                     0.8489 |                    0.8706 |
| template_residual_boosted_stack_new | pileup_bin     | overlap               | 330 |                 0.3956 |                0.3998 |                  0.0041 |                     0.8489 |                    0.8364 |
| template_residual_boosted_stack_new | saturation_bin | saturated             | 240 |                 0.3956 |                0.5210 |                  0.1254 |                     0.8489 |                    0.8433 |
| template_residual_boosted_stack_new | saturation_bin | unsaturated           | 420 |                 0.3956 |                0.4090 |                  0.0134 |                     0.8489 |                    0.8548 |

## Shortcut and Systematic Diagnostics

If waveform ML were learning only nuisance shortcuts, PID scores would track
pedestal, saturation, or pile-up labels more strongly than physics energy/depth
structure.  The absolute held-out correlations are:

| method                              |   abs_corr_pid_score_pedestal |   abs_corr_pid_score_saturation |   abs_corr_pid_score_pileup |   abs_corr_pid_score_energy |   winner_score |
|:------------------------------------|------------------------------:|--------------------------------:|----------------------------:|----------------------------:|---------------:|
| template_residual_boosted_stack_new |                        0.0111 |                          0.0131 |                      0.0099 |                      0.1129 |         0.2335 |
| gradient_boosted_trees              |                        0.0193 |                          0.0176 |                      0.0094 |                      0.0969 |         0.2373 |
| ridge                               |                        0.0171 |                          0.1019 |                      0.0166 |                      0.2506 |         0.2856 |
| 1d_cnn                              |                        0.0165 |                          0.0881 |                      0.0220 |                      0.3011 |         0.2977 |
| deltaE_over_E_likelihood_template   |                        0.0279 |                          0.2522 |                      0.0087 |                      0.6088 |         0.3181 |
| joint_sequence_transformer          |                        0.0868 |                          0.1260 |                      0.4447 |                      0.0250 |         0.4003 |
| mlp                                 |                        0.0229 |                          0.2378 |                      0.0009 |                      0.4007 |         0.4203 |

The winner has the strongest overall composite performance while keeping
pedestal-score correlation at `0.0111`.
The transformer candidate is materially worse on PID balanced accuracy in this
short 18-sample regime, so attention does not appear to add useful context here.

## Systematics and Caveats

The PID and energy truth are GEANT4/digitization bridge labels, not an external
beamline particle tag joined event-by-event to the real raw data.  The pedestal,
pile-up, and saturation labels are controlled truth proxies in the digitized
benchmark.  They are appropriate for a comparative architecture stress test,
but not for an absolute production PID efficiency claim.  The raw ROOT gate
protects the selected-pulse support and detector-channel semantics; it does not
by itself validate GEANT4 material budget, Birks quenching, electronics
response, or trigger acceptance.  The confidence intervals are run-block
bootstrap intervals over the held-out source runs and therefore reflect
run-to-run instability better than i.i.d. event uncertainty, but only five
held-out runs are available for the final score.

## Conclusion

Use **`template_residual_boosted_stack_new`** as the S56c benchmark winner.  The result favors a hybrid
physics-residual architecture over a pure black-box transformer: waveform ML is
useful when it residualizes a strong likelihood/template baseline, but the
state-stratified boundary tables show that pedestal and saturation still move
local PID thresholds.  For production PID, the traditional likelihood template
remains the interpretable reference and should be retained as a calibration
monitor even when the residual architecture is used for best held-out score.
