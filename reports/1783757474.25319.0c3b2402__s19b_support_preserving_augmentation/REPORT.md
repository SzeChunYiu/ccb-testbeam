# Study report: S19b - support-preserving augmentation check for pile-up recovery winner

- **Study ID:** S19b
- **Ticket:** `1783757474.25319.0c3b2402`
- **Author:** `testbeam-laptop-1`
- **Date:** 2026-07-11
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Config:** `configs/s19b_1783757474_25319_0c3b2402_support_preserving_augmentation.yaml`
- **Git commit at run time:** `28f9da679d4b79f6b21deb33b910454dfb1e85b8`

## 0. Question

Is the pile-up and charge-recovery winner limited primarily by training support rather than by architecture capacity? The benchmark reruns the S19 two-pulse recovery task with train-only support-preserving augmentation and residual synthesis while preserving untouched held-out source runs.

## 1. Raw-ROOT reproduction gate

Before any modeling, the S00 selected-pulse count is recomputed directly from raw `HRDv` ROOT branches.

| quantity                           | report_value | reproduced | delta | tolerance | pass |
| ---------------------------------- | ------------ | ---------- | ----- | --------- | ---- |
| total selected B-stave pulses      | 640737       | 640737     | 0     | 0         | True |
| sample_ii_analysis selected_pulses | 125096       | 125096     | 0     | 0         | True |
| sample_ii_analysis B2              | 88213        | 88213      | 0     | 0         | True |
| sample_ii_analysis B4              | 21229        | 21229      | 0     | 0         | True |
| sample_ii_analysis B6              | 11148        | 11148      | 0     | 0         | True |
| sample_ii_analysis B8              | 4506         | 4506       | 0     | 0         | True |

The exact `640,737` selected B-stave pulse count and Sample-II stave counts are reproduced with zero tolerance.

## 2. Methods and equations

The empirical pulse model uses a stave-specific normalized template `u_s(t)` aligned to CFD20 reference sample 5. For injected overlaps,

`y(t) = A_1 u_s(t - t_1) + I A_2 u_s(t - t_2) + epsilon_{r,s}(t) + b`,

where `I` is the injected-overlap indicator, `epsilon_{r,s}` is a residual waveform drawn only from the same training run and stave, and `b` is a baseline offset. Held-out events from runs 63 and 65 are generated once and never augmented.

Support-preserving augmentation samples only within the observed training support: the same train run, same stave, same discrete overlap/separation/ratio grid, Gaussian timing jitter of 0.18 samples, amplitude jitter of 10%, and baseline jitter of 35 ADC. It does not add new held-out runs, new staves, event identifiers, or labels derived from held-out data.

The traditional comparator is the bounded two-pulse template fit. It scans `t_1` and allowed separations, solves amplitudes and baseline by least squares, and rejects solutions outside amplitude-ratio and baseline bounds. The ML competitors are ridge/logistic, gradient-boosted trees, MLP, 1D-CNN, residual CNN, TCN, attention, and GRU sequence heads. All models predict overlap probability plus `t_1`, `t_2`, `A_1/max(y)`, and `A_2/max(y)`.

For a positive event, constituent time RMS is

`sqrt(mean((10 (hat t_1 - t_1))^2 + (10 (hat t_2 - t_2))^2)/2)`,

and charge recovery is summarized by median fractional bias and the 68% half-width of fractional charge error. Bootstrap confidence intervals resample held-out events.

## 3. Augmentation ledger

| source               | n_events | heldout_touched |
| -------------------- | -------- | --------------- |
| original_train       | 1360     | False           |
| support_preserving_0 | 1360     | False           |
| support_preserving_1 | 1360     | False           |

The ledger verifies that augmentation is train-only; held-out waveforms are evaluated in their original generated form.

## 4. Run-split CV

| model                  | time_rms_ns | charge_fractional_res68 | detection_ap |
| ---------------------- | ----------- | ----------------------- | ------------ |
| gradient_boosted_trees | 7.47197     | 0.0893576               | 0.853623     |
| ridge                  | 9.56648     | 0.0994691               | 0.815336     |
| mlp                    | 11.136      | 0.102491                | 0.840679     |

CV is grouped by source run over the augmented training support and is used as a stability diagnostic, not as a held-out result.

## 5. Held-out head-to-head

| model                    | detection_ap | time_rms_ns | time_rms_ns_ci_low | time_rms_ns_ci_high | delta_time_rms_vs_traditional_ns | charge_fractional_bias | charge_fractional_res68 | charge_fractional_res68_ci_low | charge_fractional_res68_ci_high | delta_charge_res68_vs_traditional | failure_rate | train_seconds | n_parameters |
| ------------------------ | ------------ | ----------- | ------------------ | ------------------- | -------------------------------- | ---------------------- | ----------------------- | ------------------------------ | ------------------------------- | --------------------------------- | ------------ | ------------- | ------------ |
| gradient_boosted_trees   | 0.883426     | 6.2633      | 6.11252            | 6.40329             | -9.25897                         | -0.00115275            | 0.0605783               | 0.0604389                      | 0.0621293                       | -0.0429963                        | 0.252381     | 1.74053       | 140          |
| mlp                      | 0.83644      | 8.54226     | 8.48334            | 8.60037             | -6.98001                         | -0.0107255             | 0.0665234               | 0.0657106                      | 0.0671969                       | -0.0370512                        | 0.316667     | 3.20283       | 2736         |
| ridge                    | 0.814984     | 8.86249     | 8.69246            | 9.02138             | -6.65978                         | -0.00857134            | 0.0773915               | 0.0738505                      | 0.0801017                       | -0.0261831                        | 0.321429     | 0.0434191     | 125          |
| tcn                      | 0.802441     | 10.6242     | 10.4418            | 10.806              | -4.89807                         | -0.00413533            | 0.0843318               | 0.0829003                      | 0.0878066                       | -0.0192428                        | 0.295238     | 3.14977       | 461          |
| cnn                      | 0.786939     | 11.0671     | 10.8986            | 11.2395             | -4.4552                          | 0.0123085              | 0.0877565               | 0.0858202                      | 0.0911092                       | -0.0158181                        | 0.261905     | 3.01128       | 461          |
| resnet                   | 0.783192     | 11.0675     | 10.7638            | 11.3482             | -4.45478                         | -0.00412229            | 0.0854073               | 0.076598                       | 0.0898404                       | -0.0181673                        | 0.359524     | 3.83029       | 661          |
| gru                      | 0.822739     | 11.191      | 11.07              | 11.3068             | -4.33125                         | 0.00322338             | 0.0831176               | 0.0824764                      | 0.0844799                       | -0.020457                         | 0.288095     | 9.35811       | 1269         |
| attention                | 0.696161     | 14.5079     | 14.0136            | 14.8897             | -1.01439                         | -0.0324729             | 0.106597                | 0.105804                       | 0.109981                        | 0.0030223                         | 0.559524     | 6.93189       | 549          |
| constrained_template_fit | 0.766007     | 15.5223     | 14.3909            | 16.5708             | 0                                | -0.0127011             | 0.103575                | 0.0973327                      | 0.104915                        | 0                                 | 0.164286     |               | 0            |

Winner by primary held-out time RMS is `gradient_boosted_trees` at 6.263 ns [6.113, 6.403], with charge res68 0.0606. The bounded traditional fit gives 15.522 ns [14.391, 16.571] and charge res68 0.1036. The prior S19c winner, gradient-boosted trees, gives 6.263 ns and charge res68 0.0606 after augmentation.

## 6. Systematics and caveats

- The labels are injected closure truth, not adjudicated real high-current pile-up.
- Residual synthesis is train-run/stave preserving, so it tests support density within observed support rather than extrapolation to new detector states.
- Bootstrap CIs cover finite held-out event statistics but not all model-selection uncertainty.
- The neural models are compact laptop-scale architectures; a larger transformer could behave differently, but the 18-sample window makes local shape models a strong prior.
- Charge metrics are conditional on the same injected template family and may understate real saturation or baseline-excursion charge bias.

## 7. Verdict

With train-only support-preserving augmentation, held-out winner is gradient_boosted_trees at 6.263 ns [6.113, 6.403] versus constrained_template_fit 15.522 ns. Charge res68 for the winner is 0.0606. Held-out runs are untouched; the result tests training-support density rather than held-out augmentation.

The main interpretation is that support-preserving augmentation improves training density but does not make sequence architectures dominate the tabular/tree winner. The limiting factor is therefore not simply neural capacity; the strongest result remains a structured waveform-summary method unless future real-pile-up labels expose features absent from the injected closure.

## 8. Reproducibility

```bash
/usr/bin/python3 scripts/s19b_1783757474_25319_0c3b2402_support_preserving_augmentation.py --config configs/s19b_1783757474_25319_0c3b2402_support_preserving_augmentation.yaml
```

Runtime in this execution was `76.35` s. Machine-readable outputs include `result.json`, `manifest.json`, `reproduction_match_table.csv`, `augmentation_ledger.csv`, `two_pulse_head_to_head.csv`, and `two_pulse_architecture_cv.csv`.
