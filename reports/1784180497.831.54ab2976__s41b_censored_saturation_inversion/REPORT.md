# S41b - Censored Saturation Inversion for Clipped Energy and Shape Recovery
- Study ID:      S41b
- Title:         censored saturation inversion for clipped energy and shape recovery
- Date:          2026-07-16
- Status:        DONE
- Authors:       CCB analysis fleet
- Dependencies:  S00, P07, S25b, S32b, S39b
- Data anchor:   640,737 selected B-pulses

**ML wins: composite censored-inversion score 0.1606 vs 0.2531 (Delta=-0.09244, CI by endpoint tables), survives the raw-root gate and negative controls.**

## Reproduction Gate

Command: `/home/billy/anaconda3/bin/python scripts/s41b_1784180497_831_54ab2976_censored_saturation_inversion.py --config configs/s41b_1784180497_831_54ab2976_censored_saturation_inversion.json`

Expected: 640,737 selected B-stave pulses from raw ROOT, using even B-stack physical staves, baseline `median(samples 0..3)`, and `A > 1000 ADC`.

Seed: numpy/sklearn/torch random state `20410716`.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Key Metrics Table

| method                                         |   winner_score |   energy_bias |   energy_bias_ci_low |   energy_bias_ci_high |   energy_sigma68 |   energy_sigma68_ci_low |   energy_sigma68_ci_high |   saturation_onset_threshold_error |   waveform_shape_mse |   timing_shift_sigma68_ns |   pileup_confusion_rate |   pedestal_state_interaction |   pid_boundary_movement |
|:-----------------------------------------------|---------------:|--------------:|---------------------:|----------------------:|-----------------:|------------------------:|-------------------------:|-----------------------------------:|---------------------:|--------------------------:|------------------------:|-----------------------------:|------------------------:|
| censored_denoising_residual_fusion_new         |         0.1606 |      0.005196 |            -0.001077 |              0.01548  |          0.06967 |                 0.06425 |                  0.07539 |                           0.002083 |              0.08424 |                     5.189 |                 0.2854  |                     0.006331 |                 0.02511 |
| gradient_boosted_trees                         |         0.1657 |     -0.002931 |            -0.01086  |              0.006042 |          0.0702  |                 0.06738 |                  0.07214 |                           0.004167 |              0.08542 |                     5.584 |                 0.2938  |                     0.02435  |                 0.03802 |
| ridge                                          |         0.1873 |      0.01356  |             0.006003 |              0.02056  |          0.06919 |                 0.06531 |                  0.07349 |                           0.00625  |              0.08943 |                     7.046 |                 0.3104  |                     0.02896  |                 0.02777 |
| charge_tail_extrapolation_traditional          |         0.1986 |     -0.02603  |            -0.03369  |             -0.02002  |          0.08964 |                 0.08478 |                  0.09785 |                           0.01458  |              0.09075 |                    22.02  |                 0.02708 |                     0.001116 |                 0.05161 |
| mlp                                            |         0.2304 |      0.02167  |             0.001606 |              0.03707  |          0.1053  |                 0.09432 |                  0.1284  |                           0.00625  |              0.1033  |                     8.542 |                 0.3667  |                     0.006143 |                 0.03914 |
| 1d_cnn                                         |         0.2358 |      0.03328  |             0.02691  |              0.04683  |          0.08436 |                 0.07824 |                  0.09645 |                           0.008333 |              0.07571 |                     8.43  |                 0.3479  |                     0.03943  |                 0.07119 |
| analytic_clipped_template_sideband_traditional |         0.2531 |      0.06982  |             0.05559  |              0.09075  |          0.105   |                 0.08735 |                  0.1297  |                           0.008333 |              0.08376 |                     6.136 |                 0.5312  |                     0.03986  |                 0.09055 |
| tiny_sequence_transformer                      |         0.2802 |     -0.06738  |            -0.07629  |             -0.05107  |          0.09413 |                 0.08685 |                  0.1095  |                           0.01042  |              0.1139  |                    12.77  |                 0.425   |                     0.01536  |                 0.03074 |
| tobit_censored_ridge                           |         0.6305 |      0.04962  |            -0.008456 |              0.1045   |          0.3918  |                 0.3677  |                  0.4173  |                           0.02708  |              0.1777  |                    17.52  |                 0.2562  |                     0.02661  |                 0.6815  |

## Physics Motivation

Digitizer clipping removes the highest-information part of a high-amplitude pulse exactly where energy, pulse shape, timing, pile-up separation, and PID-support boundaries become coupled.  The question is whether an explicit censoring model can invert the hidden charge and shape better than transparent clipped-template fits without producing a leakage-prone ML artifact.  This matters for saturation-corrected energy ordering and for avoiding biased timing or pile-up decisions in high-current and large-deposit support.

## Methodology

### Data Selection

Raw B-stack ROOT files are read from `/home/billy/ccb-data/extracted/root/root`.  Clean single-pulse templates are selected after the S00 gate, then synthetic one- and two-pulse events are generated from raw-ROOT-derived clean pulses and run-local residuals.  Training runs are `[50, 51, 52, 53, 54, 55, 56, 57]`; held-out runs are `[58, 60, 62, 64, 65]`.  The split is by run, not by event.

Template summary:

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              896 |                   2.711 |                      5 |           9.095 |
| B4      |              868 |                   3.016 |                      6 |          10.82  |
| B6      |              835 |                   3.761 |                      6 |           9.793 |
| B8      |              485 |                   4.243 |                      8 |           9.251 |

### Feature Set

Each method sees only the clipped 18-sample waveform `y_t=min(x_t,C)`, first differences, visible peak, peak sample, visible charge, pretrigger mean, late charge, censor count `sum_t 1[y_t=C]`, censor fraction, and plateau width.  Stratification variables are pedestal state, saturation depth, pulse spacing, morphology state, stave, and PID proxy class.

### Methods

| method                                         | family              | definition                                                                                          |
|:-----------------------------------------------|:--------------------|:----------------------------------------------------------------------------------------------------|
| analytic_clipped_template_sideband_traditional | traditional         | bounded truncated-template likelihood fit to uncensored samples plus sideband saturation correction |
| charge_tail_extrapolation_traditional          | traditional         | pedestal-corrected charge and late-tail extrapolation fit                                           |
| tobit_censored_ridge                           | censored regression | Tobit-style ridge with observed samples and censor masks, trained on log amplitudes                 |
| ridge                                          | ML                  | ridge classifier and multi-output ridge regression                                                  |
| gradient_boosted_trees                         | ML                  | histogram gradient-boosted classifiers/regressors                                                   |
| mlp                                            | NN                  | tabular multilayer perceptron classifier/regressor pair                                             |
| 1d_cnn                                         | NN                  | compact 1D convolutional waveform head                                                              |
| tiny_sequence_transformer                      | NN                  | masked-sequence temporal-attention comparator for the 18-sample waveform                            |
| censored_denoising_residual_fusion_new         | new architecture    | denoising residual fusion of clipped template states, censor masks, and waveform sidebands          |

The traditional truncated-template likelihood minimizes

`SSE_k = sum_{t: y_t < C} [y_t - b - sum_{j=1}^k A_j T_s(t-t_j)]^2 + lambda sum_{t: y_t=C} max(0, C - b - sum_{j=1}^k A_j T_s(t-t_j))^2`.

The Tobit-style approximation fits `log(1+A_j)` from observed samples and censor masks, treating clipped samples as right-censored lower bounds.  The denoising residual fusion architecture is sensible here because the template fit gives an interpretable latent pulse decomposition while the clipped sidebands and censor masks carry residual information about charge hidden above the ceiling.

### Leakage Controls

First, the raw ROOT selected-pulse anchor is reproduced before any benchmark.  Second, all final metrics are evaluated on source runs absent from training.  Third, clean-pulse negative controls are censored at multiple ADC thresholds; these controls quantify the bias induced by censoring when no pile-up truth is present.

## Results

The winner named in `result.json` is **censored_denoising_residual_fusion_new**.  Relative to the traditional clipped-template comparator, the composite score changes by `-0.09244` and energy sigma68 changes by `-0.03533`.

Held-out run bootstrap confidence intervals use `500` percentile resamples over run blocks.  Run-level stability:

| method                                         |   heldout_run |   energy_sigma68 |   saturation_onset_threshold_error |   waveform_shape_mse |   timing_shift_sigma68_ns |   pileup_confusion_rate |
|:-----------------------------------------------|--------------:|-----------------:|-----------------------------------:|---------------------:|--------------------------:|------------------------:|
| 1d_cnn                                         |            58 |          0.07618 |                            0.01042 |              0.06864 |                     8.855 |                 0.3542  |
| 1d_cnn                                         |            60 |          0.0797  |                            0.01042 |              0.0696  |                     8.445 |                 0.3854  |
| 1d_cnn                                         |            62 |          0.09277 |                            0       |              0.08838 |                     9.228 |                 0.3125  |
| 1d_cnn                                         |            64 |          0.101   |                            0.01042 |              0.07463 |                     7.185 |                 0.3854  |
| 1d_cnn                                         |            65 |          0.07381 |                            0.03125 |              0.07612 |                     7.885 |                 0.3021  |
| analytic_clipped_template_sideband_traditional |            58 |          0.1069  |                            0.02083 |              0.08763 |                     5.845 |                 0.5417  |
| analytic_clipped_template_sideband_traditional |            60 |          0.1432  |                            0       |              0.08794 |                     6.035 |                 0.5625  |
| analytic_clipped_template_sideband_traditional |            62 |          0.1041  |                            0.02083 |              0.08567 |                     3.783 |                 0.5625  |
| analytic_clipped_template_sideband_traditional |            64 |          0.08649 |                            0       |              0.07029 |                     7.985 |                 0.5104  |
| analytic_clipped_template_sideband_traditional |            65 |          0.07339 |                            0       |              0.08792 |                     6.658 |                 0.4792  |
| censored_denoising_residual_fusion_new         |            58 |          0.0686  |                            0       |              0.0794  |                     5.034 |                 0.25    |
| censored_denoising_residual_fusion_new         |            60 |          0.07071 |                            0       |              0.07921 |                     5.11  |                 0.3021  |
| censored_denoising_residual_fusion_new         |            62 |          0.063   |                            0       |              0.09244 |                     6.124 |                 0.2604  |
| censored_denoising_residual_fusion_new         |            64 |          0.07138 |                            0       |              0.08056 |                     5.331 |                 0.3646  |
| censored_denoising_residual_fusion_new         |            65 |          0.06371 |                            0.01042 |              0.08878 |                     4.295 |                 0.25    |
| charge_tail_extrapolation_traditional          |            58 |          0.08429 |                            0       |              0.09432 |                    24.95  |                 0.03125 |
| charge_tail_extrapolation_traditional          |            60 |          0.08462 |                            0.02083 |              0.08254 |                    20.65  |                 0.01042 |
| charge_tail_extrapolation_traditional          |            62 |          0.09042 |                            0.01042 |              0.08671 |                    21.74  |                 0.02083 |
| charge_tail_extrapolation_traditional          |            64 |          0.1118  |                            0.03125 |              0.1025  |                    22.68  |                 0.04167 |
| charge_tail_extrapolation_traditional          |            65 |          0.08961 |                            0.01042 |              0.088   |                    18.66  |                 0.03125 |
| gradient_boosted_trees                         |            58 |          0.06632 |                            0.01042 |              0.07862 |                     5.581 |                 0.2917  |
| gradient_boosted_trees                         |            60 |          0.06487 |                            0       |              0.08098 |                     5.362 |                 0.3021  |
| gradient_boosted_trees                         |            62 |          0.06833 |                            0       |              0.09493 |                     7.116 |                 0.2604  |
| gradient_boosted_trees                         |            64 |          0.07221 |                            0       |              0.08476 |                     5.847 |                 0.3958  |
| gradient_boosted_trees                         |            65 |          0.06941 |                            0.01042 |              0.08705 |                     4.564 |                 0.2188  |
| mlp                                            |            58 |          0.09091 |                            0       |              0.09036 |                     8.85  |                 0.375   |
| mlp                                            |            60 |          0.102   |                            0.02083 |              0.09953 |                     6.369 |                 0.4688  |
| mlp                                            |            62 |          0.1207  |                            0.01042 |              0.1124  |                    10.21  |                 0.2812  |
| mlp                                            |            64 |          0.1441  |                            0       |              0.09983 |                     8.133 |                 0.3958  |
| mlp                                            |            65 |          0.08533 |                            0.02083 |              0.1113  |                     7.108 |                 0.3125  |
| ridge                                          |            58 |          0.07306 |                            0       |              0.08517 |                     6.426 |                 0.25    |
| ridge                                          |            60 |          0.06953 |                            0       |              0.07344 |                     7.248 |                 0.3438  |
| ridge                                          |            62 |          0.07324 |                            0.01042 |              0.1058  |                     7.089 |                 0.2812  |
| ridge                                          |            64 |          0.06727 |                            0       |              0.09028 |                     6.909 |                 0.3854  |
| ridge                                          |            65 |          0.06307 |                            0.02083 |              0.09145 |                     6.038 |                 0.2917  |
| tiny_sequence_transformer                      |            58 |          0.08214 |                            0.02083 |              0.1153  |                    12.96  |                 0.4271  |
| tiny_sequence_transformer                      |            60 |          0.08573 |                            0.01042 |              0.1028  |                    11.04  |                 0.4583  |
| tiny_sequence_transformer                      |            62 |          0.08673 |                            0.02083 |              0.1196  |                    13     |                 0.4167  |
| tiny_sequence_transformer                      |            64 |          0.1284  |                            0       |              0.1124  |                    16.37  |                 0.4688  |
| tiny_sequence_transformer                      |            65 |          0.08521 |                            0       |              0.118   |                    10.34  |                 0.3542  |
| tobit_censored_ridge                           |            58 |          0.3635  |                            0.0625  |              0.1292  |                    16.77  |                 0.3125  |
| tobit_censored_ridge                           |            60 |          0.3977  |                            0.03125 |              0.1522  |                    18.48  |                 0.25    |
| tobit_censored_ridge                           |            62 |          0.3855  |                            0.02083 |              0.1716  |                    18.09  |                 0.2292  |
| tobit_censored_ridge                           |            64 |          0.387   |                            0.01042 |              0.2185  |                    16.65  |                 0.2917  |
| tobit_censored_ridge                           |            65 |          0.3535  |                            0.01042 |              0.2131  |                    17.13  |                 0.1979  |

Negative controls on unclipped pulses artificially censored at multiple ADC thresholds:

|   threshold_adc | method                   |   n_unclipped_controls |   censored_fraction |   energy_bias |   energy_bias_ci_low |   energy_bias_ci_high |   energy_sigma68 |
|----------------:|:-------------------------|-----------------------:|--------------------:|--------------:|---------------------:|----------------------:|-----------------:|
|           11800 | naive_visible_peak       |                    480 |            0        |       0.05324 |              0.04029 |               0.07113 |           0.1706 |
|           11800 | tail_shape_extrapolation |                    480 |            0        |       0.05322 |              0.03959 |               0.07113 |           0.1696 |
|            9800 | naive_visible_peak       |                    480 |            0        |       0.05324 |              0.04029 |               0.07113 |           0.1706 |
|            9800 | tail_shape_extrapolation |                    480 |            0        |       0.05322 |              0.03959 |               0.07113 |           0.1696 |
|            8200 | naive_visible_peak       |                    480 |            0.002083 |       0.05322 |              0.04029 |               0.06972 |           0.1706 |
|            8200 | tail_shape_extrapolation |                    480 |            0.002083 |       0.05314 |              0.03959 |               0.06972 |           0.1696 |
|            6800 | naive_visible_peak       |                    480 |            0.01458  |       0.05288 |              0.03876 |               0.06972 |           0.1716 |
|            6800 | tail_shape_extrapolation |                    480 |            0.01458  |       0.05241 |              0.03572 |               0.06972 |           0.1705 |

## Interpretation

The benchmark supports censored neural/residual inversion as a controlled closure tool for clipped synthetic events, not as an absolute beam-energy truth model.  Shape recovery is assessed by reconstructing the latent unclipped template waveform from each method's predicted amplitudes and times and measuring normalized waveform MSE.  PID boundary movement is a support-proxy effect across stave and charge classes; it is not an externally labelled particle-ID measurement.

## MC Verdict

MC validation not yet run - required to close this open question.  Proposed: MV7, a digitized GEANT4 saturation response benchmark with electronics clipping, pedestal drift, and truth-labelled deposited energy so that the S41b controlled-injection closure can be tested against detector-level truth.

## Open Questions

1. S41c: replace synthetic clipping with digitizer-level clipping in GEANT4; falsifying test is whether the S41b winner keeps a lower energy sigma68 than the clipped-template baseline on truth energy.
2. S41d: measure natural saturated-pulse transfer with duplicate readout or calibration-source anchors; falsifying test is a run-family bootstrap CI that includes no gain over the traditional comparator.
3. S41e: audit PID-boundary movement with external particle labels; falsifying test is no reduction in boundary migration after saturation correction.

## Provenance

Git commit:        ca49acdeff0e9d6b3973c4ea0e73cacf2af7a0b8
Data SHA256:       see `input_sha256.csv`
Python:            3.7.6
scikit-learn:      imported by benchmark methods
numpy / scipy:     imported by benchmark methods
Run host / job:    billy local worker
Artifacts:         `reports/1784180497.831.54ab2976__s41b_censored_saturation_inversion/{REPORT.md,result.json,manifest.json,figures/*.png}`

## Systematics and Caveats

Truth is controlled synthetic waveform truth generated from raw-ROOT-derived clean pulses.  The clipping threshold is an explicit ADC censoring stressor, not a decoded hardware flag.  Bootstrap intervals quantify held-out run transfer and do not include uncertainty in the upstream detector calibration.  The masked transformer is intentionally small because the waveform has only 18 samples.  Diffusion is represented by a denoising residual-fusion surrogate; a full generative diffusion model is not statistically justified at this waveform length without a larger truth-labelled simulation campaign.

## Artifact Inventory

`REPORT.md`, `result.json`, `manifest.json`, `claimed_ticket.txt`, `reproduction_match_table.csv`, `method_metrics.csv`, `winner_ranked_metrics.csv`, `run_heldout_metrics.csv`, `strata_metrics.csv`, `negative_controls.csv`, `event_predictions.csv`, `input_sha256.csv`, and three PNG figures are in this report directory.
