# S24C PID and Calibrated-Energy Composition Bridge

Ticket: `1783758004.33451.4b095b91`  
Worker: `testbeam-laptop-2`  
Claimed ticket title: Attach external beamline PID and calibrated energy labels to S24 pulse-shape predictions to separate waveform-timing transfer from species and energy-composition effects.

## Abstract

This study attaches the defensible composition information available for the S24 pulse-shape benchmark. The S24B raw ROOT loader reproduces the selected B-stave pulse count exactly, `N_sel = 640737`, and the S24B run-heldout pulse-shape panel is carried forward with bootstrap confidence intervals. The pulse-shape winner is `ML_gradient_boosted_trees` with heldout ROC AUC 0.948379 [0.924815, 0.964406]. The calibrated-energy bridge is attached from S24A; its best method is `geant4_birks_lookup` with fractional 68 percent resolution 0.040244 [0.038857, 0.041606].

The external PID part is intentionally not over-claimed. The prior S15C schema audit found no event-native, run/event-keyed PID, truth, species, Cherenkov, time-of-flight, or beamline tag branch joinable to the HRD waveform rows. Therefore S24C records `external_pid_join_status = blocked_no_event_native_external_pid_branch`: beamline-proxy PID support is available for composition stress tests, but event-level species labels are not attached.

## Raw ROOT Reproduction

The inherited S24B raw ROOT pass reads the B-stack `HRD`/`HRDv` waveform trees and applies the same selected-pulse definition used by the report family. For each candidate pulse, the reconstructed baseline is

`b_rec = median(x_0, x_1, x_2, x_3)`

and the baseline-subtracted pulse amplitude is

`a = max_t (x_t - b_rec)`.

A B-stave pulse is selected when `a > 1000 ADC`. Summing selected pulses by run gives

`N_sel = sum_run N_sel(run) = 640737`.

The expected value is `640737`, so the reproduction delta is `0`. The run-count table is written to `raw_reproduction_counts_by_run.csv`, and the exact match assertion is written to `raw_reproduction_match_table.csv`.

## Labels, Split, and Inference Target

S24B defines a run-local pedestal-drift target rather than a particle-species target:

`y = 1[ |b - median_run,stave(b)| >= q_0.80 ]`.

The fitted high-drift threshold is `38.25 ADC`. Training rows: `25493`. Heldout rows: `9745`. Heldout runs: `[42, 50, 57, 58, 60, 62, 64, 65]`. Confidence intervals use `500` run-block bootstrap replicates, preserving the run split as the unit of transfer stress.

This target is useful for timing and waveform-transfer stress because it asks whether pulse-shape models can recognize baseline-dependent shape changes on runs not used for training. It is not a replacement for event-level species PID.

## Model Panel

The benchmark includes a strong traditional engineered-feature method, a linear ML baseline, tree boosting, a multilayer perceptron, a 1D convolutional neural network, and a new residual squeeze CNN architecture. The primary heldout metric is ROC AUC with bootstrap confidence intervals.

| method                                | role                     | family                           |    n |   positives |   roc_auc |   auc_ci_low |   auc_ci_high |   average_precision |
|:--------------------------------------|:-------------------------|:---------------------------------|-----:|------------:|----------:|-------------:|--------------:|--------------------:|
| ML_gradient_boosted_trees             | ml_panel                 |                                  | 9745 |        2060 |  0.948379 |     0.924815 |      0.964406 |            0.920354 |
| ML_mlp                                | ml_panel                 |                                  | 9745 |        2060 |  0.918081 |     0.89078  |      0.937882 |            0.881292 |
| NN_residual_squeeze_cnn_new           | ml_panel                 |                                  | 9745 |        2060 |  0.906184 |     0.879512 |      0.923313 |            0.863167 |
| ML_ridge_classifier                   | ml_panel                 |                                  | 9745 |        2060 |  0.892608 |     0.868643 |      0.910655 |            0.842699 |
| traditional_fisher_gatti_all_features | traditional_multivariate | fisher_gatti_engineered_features | 9745 |        2060 |  0.887848 |     0.858537 |      0.906965 |            0.843737 |
| NN_1d_cnn                             | ml_panel                 |                                  | 9745 |        2060 |  0.707079 |     0.677108 |      0.733761 |            0.570204 |

The best traditional method is `traditional_fisher_gatti_all_features`, with ROC AUC 0.887848 [0.858537, 0.906965]. The best overall method is `ML_gradient_boosted_trees`. Relative to the traditional Fisher/Gatti panel, the absolute heldout AUC gain is 0.060532.

## Winner Per-Run Behavior

The winner's heldout performance by run is:

|   run |    n |   positives |   roc_auc |   average_precision |
|------:|-----:|------------:|----------:|--------------------:|
|    42 | 1124 |         238 |  0.918762 |            0.868258 |
|    50 | 1170 |         205 |  0.884499 |            0.822485 |
|    57 | 1103 |         232 |  0.936048 |            0.906268 |
|    58 | 1099 |         180 |  0.962828 |            0.919365 |
|    60 | 1400 |         374 |  0.957464 |            0.95278  |
|    62 | 1400 |         338 |  0.971899 |            0.955517 |
|    64 | 1321 |         277 |  0.975407 |            0.948753 |
|    65 | 1128 |         216 |  0.953064 |            0.921851 |

The spread across heldout runs is a material systematic, not a nuisance to average away. It reflects changing beam, pedestal, and amplitude-composition conditions that a transferable waveform model must tolerate.

## Calibrated Energy Bridge

S24A provides the calibrated-energy benchmark for the same selected-pulse family. The traditional Geant4-Birks method models charge saturation as

`Q = alpha E_dep / (1 + k_B dE/dx)`

and applies the inverse bridge

`E_cal = Q (1 + k_B dE/dx) / alpha`.

The energy-composition benchmark is:

| method                 | family                    |      n |   bias_frac |   res68_frac |   res68_ci95_low |   res68_ci95_high |   mae_mev |
|:-----------------------|:--------------------------|-------:|------------:|-------------:|-----------------:|------------------:|----------:|
| geant4_birks_lookup    | traditional_geant4_birks  | 332852 |  -0.0230986 |    0.040244  |        0.0388569 |         0.0416063 |   1.08244 |
| gradient_boosted_trees | ml_tree                   | 332852 |  -0.0167356 |    0.0566846 |        0.048804  |         0.0671974 |   1.00289 |
| physics_residual_mlp   | neural_physics_residual   | 332852 |  -0.0145744 |    0.0586802 |        0.0490247 |         0.0778825 |   1.05151 |
| ridge                  | ml_linear                 | 332852 |  -0.0235729 |    0.0966729 |        0.0887156 |         0.117206  |   1.41142 |
| transformer            | neural_waveform_attention | 332852 |   0.0326053 |    0.126436  |        0.120367  |         0.143977  |   1.9291  |
| 1d_cnn                 | neural_waveform           | 332852 |  -0.177739  |    0.265704  |        0.249266  |         0.289079  |   3.86211 |
| old_power_law          | traditional_empirical     | 332852 |  -0.297629  |    0.462358  |        0.444309  |         0.564375  |   7.8628  |
| mlp                    | neural_tabular            | 332852 |  -0.582686  |    0.692347  |        0.684237  |         0.699646  |  10.6163  |

The calibrated-energy winner is `geant4_birks_lookup` with fractional 68 percent resolution 0.040244 and 95 percent bootstrap CI [0.038857, 0.041606]. This is attached as an energy-composition bridge, not as an event-level truth label.

## Composition Proxy Shifts

Because event-native external PID is absent, S24C uses S24B's proxy shift table to quantify how the high-drift prediction target co-varies with timing, energy-amplitude, and PID-like residual proxies on heldout runs.

| metric                           | interpretation           |   high_minus_low_median_shift |       ci_low |       ci_high |   bootstrap_replicates |
|:---------------------------------|:-------------------------|------------------------------:|-------------:|--------------:|-----------------------:|
| shape_distance_nominal_chi2      | shape-distance stability |                     0.117121  |     0.103427 |     0.127212  |                    500 |
| timing_residual_mean_time_sample | timing residual          |                    -3.2409    |    -3.55744  |    -2.87098   |                    500 |
| energy_residual_log10_amplitude  | energy calibration proxy |                    -0.0902587 |    -0.100679 |    -0.0798376 |                    500 |
| pid_residual_odd_negative_adc    | PID score proxy          |                 -1545.62      | -1645.38     | -1424.03      |                    500 |

The energy proxy shift is the high-minus-low median shift in log10 amplitude residual. The PID proxy is the odd-negative ADC residual used by S24B as a species/composition-sensitive stress variable. These are proxy diagnostics only: they support sensitivity analysis, but they do not identify individual particle species.

## Systematics and Caveats

1. Raw selection systematic: the selected-pulse count is exactly reproduced from the S24B raw ROOT loader, but S24C itself is an aggregation layer and does not retrain the full waveform panel.
2. Run split systematic: all reported pulse-shape CIs come from heldout runs `[42, 50, 57, 58, 60, 62, 64, 65]`, so the interval covers run transfer better than random row splitting.
3. PID limitation: no audited raw HRD source exposes event-level PID/truth/species labels with joinable run and event keys. Any event-level species-conditioned conclusion would require new beamline PID data or a new calibrated join table.
4. Energy limitation: calibrated energy is attached through S24A's benchmark bridge. It separates amplitude/energy-composition effects at method level, but it is not an external particle label.
5. Model selection limitation: the residual squeeze CNN is the new architecture in the S24B panel; it improves the neural architecture family but does not beat gradient-boosted trees on the heldout transfer metric.

## Conclusion

S24C names `ML_gradient_boosted_trees` as the S24 pulse-shape winner and `geant4_birks_lookup` as the calibrated-energy winner. The analysis separates three things that were previously easy to conflate: waveform/pedestal transfer is benchmarked directly, calibrated-energy composition is attached through S24A, and external event-level PID remains blocked by the raw ROOT schema. The requested species-conditioned PID attachment cannot be made honestly with the current mirrored data.
