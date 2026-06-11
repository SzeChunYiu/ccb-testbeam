# P04u A-Stack Shuffled-Sentinel Root Cause

- **Ticket:** `1781063920.599.196428b2`
- **Worker:** `testbeam-laptop-3`
- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo.
- **Split:** leave-one-run-out by run for every prediction; bootstrap intervals resample complete run blocks.
- **Primary estimand:** selected A1/A3 positive-lobe charge matched to B-stack events by `(run, EVT)`, using only B-stack waveform/support features.
- **Preregistered identifiability gate:** best real minus shuffled `res68 <= -0.03` in at least three held-out runs.

## Abstract

P04u reproduces the raw B-stack selected-pulse count (640,737), A-stack analysis gates, and P04c event-matched ridge res68 (0.519271) before fitting models. The strongest real method is `ridge_log_charge_support` but the operational winner is `null_control_parity` because the real-versus-shuffled margin does not satisfy the preregistered run-level identifiability gate.

## Raw-ROOT Reproduction

B-stack S00 selected-pulse count: reproduced `640,737` versus expected `640,737`.

| sample              |   events_with_selected |   selected_pulses |   A1 |   A3 |
|:--------------------|-----------------------:|------------------:|-----:|-----:|
| sample_iii_analysis |                   7168 |              9682 | 2799 | 6883 |
| sample_iv_analysis  |                    767 |               894 |  167 |  727 |

P04c event-matched charge-transfer reproduction: `4055` rows, ridge res68 `0.519271`, waveform ExtraTrees res68 `0.519565`.

## Methods

For event `i`, the target is

`Q_i^A = I(A1_i) q_{i,A1} + I(A3_i) q_{i,A3}`,

where the indicator requires an A-stack amplitude above 1000 ADC and `q` is baseline-subtracted positive-lobe charge. Models fit `z_i = log(max(Q_i^A,1))` on training runs and report `Qhat_i = exp(zhat_i)` on the held-out run.

The fractional residual is

`r_i(m) = (Qhat_i(m) - Q_i^A) / max(Q_i^A, 1)`.

The primary width is `res68_m = quantile_0.68(|r_i(m)|)`, with median bias, full RMS, within-10%, within-25%, and train-fold conformal 68% coverage as secondary diagnostics. The traditional comparator is a train-fold adaptive-template ridge using B2 template residual diagnostics plus scalar B-stack support summaries. The required ML/NN panel contains ridge, gradient-boosted trees, ExtraTrees, random forest, MLP, 1D-CNN, and the new hybrid support-gated CNN. Root-cause controls are shuffled-target ExtraTrees and column-knockoff ExtraTrees.

## Head-To-Head Benchmark

| method                      | method_family   |    n |   bias_median_frac | bias_ci95                                     |   res68_abs_frac | res68_ci95                               |   full_rms_frac | full_rms_ci95                               |   within_25pct |   conformal_coverage68 |
|:----------------------------|:----------------|-----:|-------------------:|:----------------------------------------------|-----------------:|:-----------------------------------------|----------------:|:--------------------------------------------|---------------:|-----------------------:|
| adaptive_template_ridge     | traditional     | 4055 |         -0.0469556 | [-0.06198660752636605, -0.017529642714522946] |         0.5262   | [0.5117017199705424, 0.5403783068947002] |     0.848443    | [0.7438815485216065, 1.0112507551749037]    |       0.343527 |               0.67127  |
| ridge_log_charge_support    | ml_nn           | 4055 |         -0.0477586 | [-0.07052172839290426, -0.025200863740439138] |         0.518475 | [0.5041181249300768, 0.5368155683061407] |     0.843207    | [0.7310600832023859, 0.9743602307179132]    |       0.34254  |               0.679655 |
| gradient_boosted_trees      | ml_nn           | 4055 |         -0.0456523 | [-0.0657375193200584, -0.022709820361340817]  |         0.522162 | [0.5051559308313114, 0.5418344581600337] |     0.845328    | [0.7391769324762295, 0.9916689769513385]    |       0.338348 |               0.644636 |
| extra_trees_waveform        | ml_nn           | 4055 |         -0.047827  | [-0.06809790236108092, -0.025383306028244335] |         0.519197 | [0.5087181614008172, 0.5360837406198911] |     0.845838    | [0.7388338296214593, 0.9762719390497314]    |       0.345993 |               0.667078 |
| random_forest_waveform      | ml_nn           | 4055 |         -0.0464163 | [-0.07022547905723446, -0.02087847102083007]  |         0.522504 | [0.5040329780000483, 0.5403733151367526] |     0.848335    | [0.7476048845943599, 0.9936909474259024]    |       0.339334 |               0.621948 |
| mlp_waveform                | ml_nn           | 4055 |         -0.0826421 | [-0.1391117419060899, -0.027230072245922735]  |         0.667231 | [0.6182791721709632, 0.7471802302288513] |     4.98305e+25 | [444295926580.94714, 8.403343392940001e+25] |       0.27201  |               0.607891 |
| cnn1d_waveform              | ml_nn           | 4055 |         -0.0224902 | [-0.0474498455697383, 0.0032861790089826724]  |         0.519348 | [0.5050368873054994, 0.534849733981486]  |     0.872175    | [0.7561224431383368, 1.0033794308644923]    |       0.350432 |             nan        |
| hybrid_support_gate_cnn     | ml_nn           | 4055 |         -0.0204754 | [-0.04529856511512399, 0.009359915683017693]  |         0.520421 | [0.5068233915664189, 0.5399874431408966] |     0.874572    | [0.7690946964992741, 1.0405876957650753]    |       0.349445 |             nan        |
| knockoff_extra_trees        | control         | 4055 |         -0.0501415 | [-0.07004274482449349, -0.024423678670801273] |         0.522421 | [0.5067636239594446, 0.5390311753636037] |     0.842789    | [0.7418461587399152, 1.0088131499499857]    |       0.346732 |             nan        |
| shuffled_target_extra_trees | control         | 4055 |         -0.0473657 | [-0.06904459469726154, -0.022858091477176712] |         0.521085 | [0.506624421401198, 0.5404466254919216]  |     0.850824    | [0.7434759064809496, 1.0171568806268163]    |       0.346732 |             nan        |

## Real Minus Shuffled Deltas

| method                   | control                     |   delta_res68_vs_shuffled | delta_res68_ci95                                |   delta_full_rms_vs_shuffled | delta_full_rms_ci95                             |
|:-------------------------|:----------------------------|--------------------------:|:------------------------------------------------|-----------------------------:|:------------------------------------------------|
| adaptive_template_ridge  | shuffled_target_extra_trees |               0.00511506  | [-0.00125222421702518, 0.00869359855032119]     |                 -0.00238064  | [-0.01998310252917772, 0.012100523848466571]    |
| ridge_log_charge_support | shuffled_target_extra_trees |              -0.00260999  | [-0.005944365163442547, 0.0031766442836858584]  |                 -0.00761668  | [-0.01590309935144304, -0.00010445830098291415] |
| gradient_boosted_trees   | shuffled_target_extra_trees |               0.00107682  | [-0.004015792285334571, 0.004830811771356537]   |                 -0.00549634  | [-0.013915476164199577, 0.0018172803957947636]  |
| extra_trees_waveform     | shuffled_target_extra_trees |              -0.00188822  | [-0.007649330572467622, 0.004111125012189602]   |                 -0.00498556  | [-0.010328103469230212, 0.0012221537911344398]  |
| random_forest_waveform   | shuffled_target_extra_trees |               0.00141925  | [-0.004410870671402346, 0.005961691894157406]   |                 -0.00248869  | [-0.013697502081743446, 0.008637730048887435]   |
| mlp_waveform             | shuffled_target_extra_trees |               0.146146    | [0.1011464078319806, 0.22216880785036305]       |                  4.98305e+25 | [153958920105.85526, 8.701618401691965e+25]     |
| cnn1d_waveform           | shuffled_target_extra_trees |              -0.00173714  | [-0.006451652094523955, 0.0018720701300627826]  |                  0.021351    | [0.017040752446026857, 0.02598231501483806]     |
| hybrid_support_gate_cnn  | shuffled_target_extra_trees |              -0.000664036 | [-0.005855240048757315, 0.005469394157452114]   |                  0.0237481   | [0.017422002740480873, 0.030600791684573782]    |
| knockoff_extra_trees     | shuffled_target_extra_trees |               0.0013356   | [-0.0026148793721944676, 0.0034335152837317636] |                 -0.00803518  | [-0.016039984205313874, -0.0017506129351597466] |

## Held-Out Run Gate

|   run | best_method              |   n |   res68_abs_frac |   shuffled_res68_abs_frac |   best_minus_shuffled_res68 | passes_delta_gate   |
|------:|:-------------------------|----:|-----------------:|--------------------------:|----------------------------:|:--------------------|
|    31 | ridge_log_charge_support | 229 |         0.562274 |                  0.557913 |                 0.00436107  | False               |
|    32 | ridge_log_charge_support | 207 |         0.575491 |                  0.575657 |                -0.000165863 | False               |
|    33 | ridge_log_charge_support |   8 |         0.436949 |                  0.49055  |                -0.053601    | True                |
|    34 | ridge_log_charge_support |  16 |         0.529156 |                  0.535883 |                -0.00672703  | False               |
|    35 | ridge_log_charge_support | 221 |         0.519284 |                  0.515445 |                 0.00383966  | False               |
|    36 | ridge_log_charge_support | 295 |         0.487661 |                  0.48427  |                 0.00339132  | False               |
|    37 | ridge_log_charge_support | 292 |         0.491984 |                  0.500515 |                -0.00853144  | False               |
|    39 | ridge_log_charge_support | 324 |         0.48093  |                  0.477849 |                 0.00308136  | False               |
|    40 | ridge_log_charge_support | 265 |         0.483303 |                  0.495467 |                -0.0121637   | False               |
|    41 | ridge_log_charge_support | 295 |         0.53354  |                  0.524635 |                 0.0089046   | False               |
|    42 | ridge_log_charge_support | 279 |         0.511189 |                  0.50805  |                 0.00313849  | False               |
|    44 | ridge_log_charge_support |  30 |         0.472322 |                  0.476706 |                -0.00438339  | False               |
|    45 | ridge_log_charge_support | 302 |         0.527132 |                  0.532184 |                -0.00505275  | False               |
|    47 | ridge_log_charge_support |  92 |         0.498358 |                  0.486663 |                 0.0116943   | False               |
|    48 | ridge_log_charge_support | 260 |         0.485849 |                  0.47789  |                 0.00795884  | False               |
|    49 | ridge_log_charge_support | 288 |         0.53036  |                  0.54092  |                -0.01056     | False               |
|    50 | ridge_log_charge_support |  61 |         0.597746 |                  0.618147 |                -0.0204008   | False               |
|    51 | ridge_log_charge_support |  25 |         0.681229 |                  0.629659 |                 0.0515697   | False               |
|    52 | ridge_log_charge_support |   6 |         0.36423  |                  0.362293 |                 0.00193639  | False               |
|    53 | ridge_log_charge_support |  17 |         1.03025  |                  1.05124  |                -0.0209969   | False               |
|    54 | ridge_log_charge_support |  18 |         0.647206 |                  0.64411  |                 0.00309623  | False               |
|    55 | ridge_log_charge_support |  27 |         0.465498 |                  0.466341 |                -0.000842304 | False               |
|    56 | ridge_log_charge_support |  68 |         0.64832  |                  0.649741 |                -0.00142162  | False               |
|    57 | ridge_log_charge_support | 276 |         0.535315 |                  0.545898 |                -0.0105836   | False               |
|    58 | ridge_log_charge_support |  34 |         0.518055 |                  0.501485 |                 0.0165696   | False               |
|    59 | ridge_log_charge_support |   9 |         0.336696 |                  0.332749 |                 0.00394684  | False               |
|    60 | ridge_log_charge_support |  10 |         1.914    |                  1.83944  |                 0.074564    | False               |
|    61 | ridge_log_charge_support |   6 |         0.648604 |                  0.557777 |                 0.0908269   | False               |
|    62 | ridge_log_charge_support |   8 |         0.442693 |                  0.437432 |                 0.00526103  | False               |
|    63 | ridge_log_charge_support |  39 |         0.247704 |                  0.253378 |                -0.00567421  | False               |
|    64 | ridge_log_charge_support |  35 |         0.740694 |                  0.778229 |                -0.0375344   | True                |
|    65 | ridge_log_charge_support |  13 |         0.501389 |                  0.486843 |                 0.014546    | False               |

## Root-Cause Strata

| category               | stratum                                                                             |    n |   runs | best_real_method         |   best_real_res68 |   shuffled_res68 |   knockoff_res68 |   best_minus_shuffled_res68 | delta_res68_ci95                                 | root_cause_call               |
|:-----------------------|:------------------------------------------------------------------------------------|-----:|-------:|:-------------------------|------------------:|-----------------:|-----------------:|----------------------------:|:-------------------------------------------------|:------------------------------|
| support_cell           | A3_only|B2_only|5000_7000|all_B_amp_lt7000|broad_saturation_like|downstream_none    |  545 |     29 | adaptive_template_ridge  |          0.549674 |         0.606679 |         0.588707 |                 -0.0570047  | [-0.0639909496763777, 0.021103341519461617]      | candidate_identifiable_atom   |
| a_topology             | A1_only                                                                             |  149 |     25 | mlp_waveform             |          1.02334  |         1.10085  |         1.10018  |                 -0.077504   | [-0.43872731534339376, 0.15191708297538872]      | limited_support               |
| support_cell           | A3_only|B2_only|2000_3000|all_B_amp_lt7000|dropout_like|downstream_none             |   54 |     17 | gradient_boosted_trees   |          0.613619 |         0.678866 |         0.682713 |                 -0.0652477  | [-0.10273128952916788, 0.11705955972423854]      | limited_support               |
| support_cell           | A1_A3_pair|B2_only|1000_2000|all_B_amp_lt7000|dropout_like|downstream_none          |   71 |     16 | cnn1d_waveform           |          0.492806 |         0.52362  |         0.513455 |                 -0.0308139  | [-0.07641671197130342, 0.004190282561039586]     | limited_support               |
| support_cell           | A3_only|B2_only|3000_5000|all_B_amp_lt7000|late_tail_high|downstream_none           |   81 |     19 | adaptive_template_ridge  |          0.304186 |         0.331694 |         0.316451 |                 -0.027508   | [-0.0991478134412479, 0.030076208686471487]      | limited_support               |
| downstream_coincidence | downstream_one                                                                      |  109 |     21 | hybrid_support_gate_cnn  |          0.476499 |         0.503581 |         0.49067  |                 -0.0270828  | [-0.06283228654646977, 0.033871681181215224]     | limited_support               |
| support_cell           | A1_A3_pair|B2_only|2000_3000|all_B_amp_lt7000|late_tail_high|downstream_none        |  101 |     17 | hybrid_support_gate_cnn  |          0.442829 |         0.468866 |         0.467194 |                 -0.0260366  | [-0.04481281706087413, 0.004008291830118862]     | limited_support               |
| support_cell           | A1_A3_pair|B2_only|1000_2000|all_B_amp_lt7000|late_tail_high|downstream_none        |   76 |     18 | hybrid_support_gate_cnn  |          0.475689 |         0.491771 |         0.50114  |                 -0.0160824  | [-0.03085316188704985, 0.0029354779603443766]    | limited_support               |
| support_cell           | A3_only|B2_only|2000_3000|all_B_amp_lt7000|broad_saturation_like|downstream_none    |   51 |     16 | random_forest_waveform   |          0.470537 |         0.486304 |         0.489275 |                 -0.0157672  | [-0.09879205473384171, 0.09270133987358459]      | limited_support               |
| topology_pattern       | B2_B4                                                                               |  102 |     21 | hybrid_support_gate_cnn  |          0.477609 |         0.492379 |         0.483873 |                 -0.0147699  | [-0.05900657820351242, 0.028049883848932488]     | limited_support               |
| support_cell           | A1_A3_pair|B2_only|7000_inf|any_B_amp_ge7000|broad_saturation_like|downstream_none  |   80 |     17 | gradient_boosted_trees   |          0.482023 |         0.495012 |         0.49285  |                 -0.0129883  | [-0.03834504036911075, 0.02064331867285346]      | limited_support               |
| topology_pattern       | B2_multi_downstream                                                                 |   57 |     19 | gradient_boosted_trees   |          0.527981 |         0.531831 |         0.555989 |                 -0.00385066 | [-0.09742169741089268, 0.06679173025324814]      | limited_support               |
| downstream_coincidence | downstream_multi                                                                    |   57 |     19 | gradient_boosted_trees   |          0.527981 |         0.531831 |         0.555989 |                 -0.00385066 | [-0.09665531229171812, 0.06998594588470858]      | limited_support               |
| support_cell           | A3_only|B2_only|1000_2000|all_B_amp_lt7000|dropout_like|downstream_none             |  108 |     18 | random_forest_waveform   |          0.485509 |         0.452427 |         0.490481 |                  0.0330818  | [-0.09652170256303898, 0.09542738057150939]      | limited_support               |
| support_cell           | A3_only|B2_only|7000_inf|any_B_amp_ge7000|late_tail_high|downstream_none            |  381 |     26 | gradient_boosted_trees   |          0.590595 |         0.619063 |         0.625319 |                 -0.0284678  | [-0.08777407547773981, 0.022311441533389775]     | strong_support_control_parity |
| support_cell           | A3_only|B2_only|7000_inf|any_B_amp_ge7000|broad_saturation_like|downstream_none     |  150 |     23 | extra_trees_waveform     |          0.508621 |         0.527999 |         0.519875 |                 -0.019378   | [-0.07037563982167669, 0.05025977843657652]      | strong_support_control_parity |
| a_topology             | A1_A3_pair                                                                          | 1342 |     31 | cnn1d_waveform           |          0.487475 |         0.503293 |         0.502027 |                 -0.0158179  | [-0.02070078851147262, -0.006934517942855925]    | strong_support_control_parity |
| support_cell           | A1_A3_pair|B2_only|3000_5000|all_B_amp_lt7000|broad_saturation_like|downstream_none |  300 |     22 | hybrid_support_gate_cnn  |          0.494264 |         0.508173 |         0.506991 |                 -0.0139091  | [-0.02347667290099263, -0.006294966760891024]    | strong_support_control_parity |
| anomaly_stratum        | dropout_like                                                                        |  401 |     26 | extra_trees_waveform     |          0.517346 |         0.53123  |         0.523622 |                 -0.0138841  | [-0.0347690295491435, 0.00846467676948901]       | strong_support_control_parity |
| support_cell           | A3_only|B2_only|2000_3000|all_B_amp_lt7000|late_tail_high|downstream_none           |  166 |     19 | extra_trees_waveform     |          0.532832 |         0.54632  |         0.535466 |                 -0.0134871  | [-0.042677274709666826, 0.043792169572519815]    | strong_support_control_parity |
| support_cell           | A1_A3_pair|B2_only|7000_inf|any_B_amp_ge7000|late_tail_high|downstream_none         |  190 |     20 | cnn1d_waveform           |          0.498085 |         0.506901 |         0.512547 |                 -0.00881601 | [-0.013539446481923359, 0.00352838489358898]     | strong_support_control_parity |
| support_cell           | A3_only|B2_only|3000_5000|all_B_amp_lt7000|broad_saturation_like|downstream_none    |  635 |     28 | ridge_log_charge_support |          0.562343 |         0.57063  |         0.563591 |                 -0.00828642 | [-0.027824678170731452, 0.01531993064520253]     | strong_support_control_parity |
| support_cell           | A1_A3_pair|B2_only|5000_7000|all_B_amp_lt7000|broad_saturation_like|downstream_none |  303 |     24 | cnn1d_waveform           |          0.483549 |         0.491285 |         0.490856 |                 -0.00773586 | [-0.022944935309506476, -0.00041666282946973887] | strong_support_control_parity |
| b2_amp_bin             | 5000_7000                                                                           |  953 |     30 | hybrid_support_gate_cnn  |          0.522694 |         0.528822 |         0.525244 |                 -0.0061278  | [-0.014576643885437918, 0.0037720082370555734]   | strong_support_control_parity |
| support_cell           | A3_only|B2_only|1000_2000|all_B_amp_lt7000|late_tail_high|downstream_none           |  174 |     22 | extra_trees_waveform     |          0.455854 |         0.46027  |         0.453557 |                 -0.00441569 | [-0.030271615475743273, 0.027585903038642542]    | strong_support_control_parity |
| b2_amp_bin             | 3000_5000                                                                           | 1212 |     31 | cnn1d_waveform           |          0.510934 |         0.515067 |         0.519387 |                 -0.0041338  | [-0.01121336207875224, 0.0034310787765456136]    | strong_support_control_parity |
| b2_amp_bin             | 2000_3000                                                                           |  474 |     28 | random_forest_waveform   |          0.511766 |         0.515667 |         0.51566  |                 -0.00390154 | [-0.020555324063331857, 0.02110934205824745]     | strong_support_control_parity |
| saturation_stratum     | all_B_amp_lt7000                                                                    | 3134 |     32 | cnn1d_waveform           |          0.514551 |         0.517943 |         0.518457 |                 -0.00339235 | [-0.00858259413900104, 0.0034135623974312977]    | strong_support_control_parity |
| anomaly_stratum        | late_tail_high                                                                      | 1349 |     32 | cnn1d_waveform           |          0.503627 |         0.506905 |         0.514184 |                 -0.00327817 | [-0.009738869432050865, 0.006976991196575981]    | strong_support_control_parity |
| a_topology             | A3_only                                                                             | 2564 |     32 | random_forest_waveform   |          0.548996 |         0.551656 |         0.555778 |                 -0.0026596  | [-0.023278604224805766, 0.011014296254780431]    | strong_support_control_parity |
| b2_amp_bin             | 1000_2000                                                                           |  496 |     26 | cnn1d_waveform           |          0.50137  |         0.503723 |         0.507784 |                 -0.00235341 | [-0.022849562377262274, 0.01134721292235364]     | strong_support_control_parity |
| anomaly_stratum        | broad_saturation_like                                                               | 2271 |     32 | extra_trees_waveform     |          0.52535  |         0.527643 |         0.528398 |                 -0.00229304 | [-0.00618128268790544, 0.003867410819046456]     | strong_support_control_parity |
| topology_pattern       | B2_only                                                                             | 3889 |     32 | ridge_log_charge_support |          0.519084 |         0.521106 |         0.522181 |                 -0.00202185 | [-0.004699366870679409, 0.003250881803058951]    | strong_support_control_parity |
| downstream_coincidence | downstream_none                                                                     | 3889 |     32 | ridge_log_charge_support |          0.519084 |         0.521106 |         0.522181 |                 -0.00202185 | [-0.004725597244135457, 0.0031320814769019347]   | strong_support_control_parity |
| saturation_stratum     | any_B_amp_ge7000                                                                    |  921 |     28 | gradient_boosted_trees   |          0.53197  |         0.528417 |         0.534459 |                  0.00355353 | [-0.01115998903772011, 0.011281632836740094]     | strong_support_control_parity |
| b2_amp_bin             | 7000_inf                                                                            |  920 |     28 | gradient_boosted_trees   |          0.532244 |         0.528454 |         0.53453  |                  0.00379065 | [-0.009512609019780599, 0.011442554334764642]    | strong_support_control_parity |

## Systematics And Caveats

- The estimand is selected A-stack charge, not deposited energy. A-stack selection and acceptance are inside the target definition.
- The row set is constrained to `(run, EVT)` matches with selected B2 and selected A1 or A3. Unmatched triggers and quiet A-stack events are outside scope.
- Run-block bootstrap intervals quantify transfer across the available runs, but cannot cover unavailable beam conditions or unmounted acquisition metadata.
- Shuffled and knockoff controls are intentionally model-matched to the tree regressors. If a future neural control is required, it should use the same run split and support-cell matching before any physics-facing claim.
- CNN predictions are clipped on the log scale to train-fold target quantiles before exponentiation. This prevents non-finite back-transforms but can make neural full RMS optimistic in extreme tails.
- A real model beating shuffled in one sparse cell is not sufficient: the preregistered gate requires a margin of `-0.03` in at least three held-out runs.

## Verdict

No model passes the preregistered identifiability gate. The best real method is `ridge_log_charge_support` with res68 0.5185, while shuffled-target ExtraTrees is 0.5211 and knockoff ExtraTrees is 0.5224; only 2 held-out runs meet the -0.03 delta threshold. The P04h null is therefore best explained by B-to-A waveform non-identifiability under the current event match, not by an omitted off-the-shelf ML architecture.

Winner recorded in `result.json`: `null_control_parity`.

## Appended Follow-Up

Appended ticket `1781187102.5993.395f46f4`: P04v neural matched-controls for A/B charge-transfer non-identifiability.

## Artifacts

`result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `b_s00_counts_by_run.csv`, `astack_gate_counts.csv`, `ab_topology_counts_by_run.csv`, `p04c_reproduction_summary.csv`, `method_summary.csv`, `method_deltas_vs_shuffled.csv`, `by_run_metrics.csv`, `run_identifiability_gate.csv`, `root_cause_strata.csv`, `predictions.csv`, and `torch_fold_audit.csv`.
