# P07l blinded downstream-energy closure for duplicate-gated B2 corrections

## Abstract

This ticket freezes the P07j/P07k duplicate-gated B2 correction and asks whether it remains safe when propagated to a final blinded energy/PID summary table. The raw ROOT reproduction gate passes exactly: 640737 selected B-stave pulses, 183132 high-amplitude B2 duplicate rows, 565387 duplicate-knee rows, 177508 blinded downstream candidates, and 2716 duplicate-closure oracle acceptances. The production winner is `traditional_run_family_duplicate_gate`. Its energy proxy has charge res68 0.01541 [0.01491, 0.01599], median charge bias 0.01384 [0.01339, 0.01428], PID harm rate 0, accepted fraction 0.01530, and precision against the blinded duplicate oracle 0.815.

The support-utility winner remains `NN_1d_cnn` but is not promoted because this final closure prioritizes blinded downstream safety before support expansion.

## Ticket and Pre-registration

- Ticket: `1783638674.13974.657f2ad3`.
- Worker: `testbeam-laptop-3`.
- Frozen predecessors: `1781151055.1851.734c09d2` (P07j duplicate-gated independent consumers) and `1781153592.1544.2e244948` (P07k action-band downstream consumers).
- Primary question: after the duplicate gate is formed, can downstream energy/PID summaries be evaluated without odd-channel or duplicate-residual columns and still identify a production-safe correction rule?
- Primary rule: side-effect safety first, energy closure second. Methods must pass PID harm, timing-tail, q_template, and CFD20-shift screens before charge res68 and absolute charge bias decide the final winner.

## Raw ROOT Reproduction

Raw B-stack ROOT files under `data/root/root` were read through the frozen P07 extraction code. `HRDv` is reshaped to event-channel-sample tensors, samples 0-3 define the pedestal, and B2/even and odd duplicate quantities are recomputed before any predecessor table is trusted.

| quantity                                    |   report_value |   reproduced |   delta |   tolerance | pass   |
|:--------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00 selected B-stave pulse records          |      640737    |    640737    |       0 |       0     | True   |
| P07e high-amplitude B2 duplicate rows       |      183132    |    183132    |       0 |       0     | True   |
| P07f duplicate-proxy knee rows              |      565387    |    565387    |       0 |       0     | True   |
| P07f low-family median knee ADC             |        2752.02 |      2752.02 |       0 |       1e-06 | True   |
| P07f high-family median knee ADC            |        7239.7  |      7239.7  |       0 |       1e-06 | True   |
| P07k blinded downstream candidate rows      |      177508    |    177508    |       0 |       0     | True   |
| P07k duplicate-closure oracle accepted rows |        2716    |      2716    |       0 |       0     | True   |

## Methods

Let `x` be B2 amplitude and `y` the odd/even duplicate-charge ratio in a training run. The frozen traditional calibration fits a continuous piecewise-linear low/high-knee envelope,

```text
f_r(x) = a_r + b_r x + c_r max(0, x - k_r),
```

where `k_r` is the run-specific knee. The duplicate residual is `e_i = (y_i - f_r(x_i)) / f_r(x_i)`. A candidate correction is admitted only inside high-knee support, bounded residual support, and post-correction side-effect gates. This is the strong traditional method because it uses the independent duplicate readout to form the frozen calibration envelope before the downstream table is blinded.

The ML/NN benchmark is inherited unchanged from frozen P07k and is evaluated leave-one-run-out by run with run-block bootstrap CIs. It includes L2 ridge/logistic regression on even-waveform scalars, histogram gradient-boosted trees, a two-layer MLP, a compact 1D CNN over the normalized B2 waveform, and a new residual-gated CNN that gates convolution channels with learned residual-support features. Supervised features exclude run id, event id, odd-channel samples, odd charge/amplitude/peak, duplicate charge ratio, and duplicate residuals.

For method `m` and held-out run `r`, the final energy proxy is `Q_68(m,r) = percentile_68(|e_i^after| : accepted_m)`, and the PID stability proxy is `H(m,r) = mean(accepted_m and side_effect_harm_i)`. Whole-program estimates use run-block bootstrap over held-out runs, preserving run-to-run correlations rather than treating rows as independent.

## Blinding Audit

| method                                | uses_odd_or_duplicate_columns_after_gate   | allowed_inputs_after_gate                                                                                                        |
|:--------------------------------------|:-------------------------------------------|:---------------------------------------------------------------------------------------------------------------------------------|
| NN_1d_cnn                             | False                                      | even B2 waveform and even-waveform scalars only; no run id, event id, odd channel, duplicate charge ratio, or duplicate residual |
| NN_residual_gated_cnn_new             | False                                      | even B2 waveform and even-waveform scalars only; no run id, event id, odd channel, duplicate charge ratio, or duplicate residual |
| traditional_run_family_duplicate_gate | False                                      | frozen action label only; downstream table contains run, B2 amplitude support, q_template/timing/energy summaries                |
| ML_gradient_boosted_trees             | False                                      | even B2 waveform and even-waveform scalars only; no run id, event id, odd channel, duplicate charge ratio, or duplicate residual |
| ML_mlp                                | False                                      | even B2 waveform and even-waveform scalars only; no run id, event id, odd channel, duplicate charge ratio, or duplicate residual |
| ML_ridge_logistic                     | False                                      | even B2 waveform and even-waveform scalars only; no run id, event id, odd channel, duplicate charge ratio, or duplicate residual |

## Final Benchmark

| method                                | safety_screen_pass   |   energy_charge_res68 |   energy_charge_bias |   pid_harm_rate |   accepted_fraction |   precision_vs_duplicate_oracle |
|:--------------------------------------|:---------------------|----------------------:|---------------------:|----------------:|--------------------:|--------------------------------:|
| traditional_run_family_duplicate_gate | True                 |             0.0154068 |           0.0138432  |     0           |           0.0153007 |                       0.814515  |
| ML_mlp                                | True                 |             0.0155739 |           0.0140536  |     5.63355e-05 |           0.0342182 |                       0.498784  |
| NN_residual_gated_cnn_new             | False                |             0.0125814 |           0.00395299 |     0.0169063   |           0.77205   |                       0.0238456 |
| NN_1d_cnn                             | False                |             0.0194345 |           0.00276657 |     0.0570284   |           0.999718  |                       0.0152876 |
| ML_ridge_logistic                     | False                |             0.0130982 |           0.0107509  |     0.00252383  |           0.0927113 |                       0.212766  |
| ML_gradient_boosted_trees             | False                |             0.0139209 |           0.0124445  |     0.000146472 |           0.0679744 |                       0.322866  |

## ML-minus-traditional deltas

| method                    |   charge_res68_minus_traditional |   charge_res68_minus_traditional_ci_low |   charge_res68_minus_traditional_ci_high |   harm_rate_vs_no_correction_minus_traditional |   harm_rate_vs_no_correction_minus_traditional_ci_low |   harm_rate_vs_no_correction_minus_traditional_ci_high |
|:--------------------------|---------------------------------:|----------------------------------------:|-----------------------------------------:|-----------------------------------------------:|------------------------------------------------------:|-------------------------------------------------------:|
| NN_1d_cnn                 |                      0.00136518  |                             -0.0021401  |                              0.00474473  |                                    0.120768    |                                           0.0966921   |                                            0.150009    |
| NN_residual_gated_cnn_new |                     -0.00408952  |                             -0.00566308 |                             -0.00240273  |                                    0.0500089   |                                           0.0335225   |                                            0.0709144   |
| ML_gradient_boosted_trees |                     -0.00215488  |                             -0.00312525 |                             -0.0011667   |                                    0.000398093 |                                           0.000181131 |                                            0.000681744 |
| ML_mlp                    |                     -0.000389571 |                             -0.00144342 |                              0.000612681 |                                    0.000209548 |                                           8.11616e-05 |                                            0.000397149 |
| ML_ridge_logistic         |                     -0.00308851  |                             -0.00410915 |                             -0.0021754   |                                    0.00509822  |                                           0.0038341   |                                            0.00652904  |

## Consumer-level Interpretation

| consumer   | method                                | primary_metric             |     estimate |       ci_low |      ci_high | secondary_metric           |   secondary_estimate |
|:-----------|:--------------------------------------|:---------------------------|-------------:|-------------:|-------------:|:---------------------------|---------------------:|
| timing     | NN_1d_cnn                             | timing_tail_delta          | -1.69006e-05 | -3.66025e-05 |  0           | median_abs_cfd20_shift_ns  |           0.00329655 |
| PID        | NN_1d_cnn                             | harm_rate_vs_no_correction |  0.0570284   |  0.0433841   |  0.0811171   | precision_vs_oracle_accept |           0.0152876  |
| q_template | NN_1d_cnn                             | q_template_median_shift    | -0.000787909 | -0.00110649  | -0.000614085 | calibration_coverage       |           0.942968   |
| energy     | NN_1d_cnn                             | charge_bias                |  0.00276657  |  0.00211074  |  0.00376229  | charge_res68               |           0.0194345  |
| timing     | NN_residual_gated_cnn_new             | timing_tail_delta          | -5.63355e-06 | -1.63456e-05 |  0           | median_abs_cfd20_shift_ns  |           0.00150042 |
| PID        | NN_residual_gated_cnn_new             | harm_rate_vs_no_correction |  0.0169063   |  0.0094648   |  0.0285848   | precision_vs_oracle_accept |           0.0238456  |
| q_template | NN_residual_gated_cnn_new             | q_template_median_shift    | -0.000365767 | -0.000656205 | -0.000227765 | calibration_coverage       |           0.979231   |
| energy     | NN_residual_gated_cnn_new             | charge_bias                |  0.00395299  |  0.00268127  |  0.00564684  | charge_res68               |           0.0125814  |
| timing     | traditional_run_family_duplicate_gate | timing_tail_delta          |  0           |  0           |  0           | median_abs_cfd20_shift_ns  |           0          |
| PID        | traditional_run_family_duplicate_gate | harm_rate_vs_no_correction |  0           |  0           |  0           | precision_vs_oracle_accept |           0.814515   |
| q_template | traditional_run_family_duplicate_gate | q_template_median_shift    |  0           |  0           |  0           | calibration_coverage       |           1          |
| energy     | traditional_run_family_duplicate_gate | charge_bias                |  0.0138432   |  0.0133879   |  0.0142832   | charge_res68               |           0.0154068  |
| timing     | ML_gradient_boosted_trees             | timing_tail_delta          | -5.63355e-06 | -1.75209e-05 |  0           | median_abs_cfd20_shift_ns  |           0          |
| PID        | ML_gradient_boosted_trees             | harm_rate_vs_no_correction |  0.000146472 |  9.0873e-05  |  0.000224802 | precision_vs_oracle_accept |           0.322866   |
| q_template | ML_gradient_boosted_trees             | q_template_median_shift    |  0           |  0           |  0           | calibration_coverage       |           0.997722   |
| energy     | ML_gradient_boosted_trees             | charge_bias                |  0.0124445   |  0.0111706   |  0.0138258   | charge_res68               |           0.0139209  |
| timing     | ML_mlp                                | timing_tail_delta          |  0           |  0           |  0           | median_abs_cfd20_shift_ns  |           0          |
| PID        | ML_mlp                                | harm_rate_vs_no_correction |  5.63355e-05 |  1.9296e-05  |  0.000123903 | precision_vs_oracle_accept |           0.498784   |
| q_template | ML_mlp                                | q_template_median_shift    |  0           |  0           |  0           | calibration_coverage       |           0.998858   |
| energy     | ML_mlp                                | charge_bias                |  0.0140536   |  0.0129488   |  0.0153216   | charge_res68               |           0.0155739  |
| timing     | ML_ridge_logistic                     | timing_tail_delta          | -5.63355e-06 | -1.7749e-05  |  0           | median_abs_cfd20_shift_ns  |           0          |
| PID        | ML_ridge_logistic                     | harm_rate_vs_no_correction |  0.00252383  |  0.00155844  |  0.00401687  | precision_vs_oracle_accept |           0.212766   |
| q_template | ML_ridge_logistic                     | q_template_median_shift    |  0           |  0           |  0           | calibration_coverage       |           0.967665   |
| energy     | ML_ridge_logistic                     | charge_bias                |  0.0107509   |  0.00953223  |  0.0123145   | charge_res68               |           0.0130982  |

The final safety screen changes the interpretation of P07k's utility ordering. `NN_1d_cnn` accepts nearly the full candidate population and is useful as a stress-test upper envelope, but it has nonzero PID harm and q_template/CFD shifts. `NN_residual_gated_cnn_new` improves energy res68 but still has a nonzero harm interval. The transparent run-family duplicate gate accepts only the narrow duplicate-supported correction band, but it is the only production method with zero observed downstream harm, zero q_template shift, zero timing-tail shift, and high precision against the blinded duplicate oracle.

## Systematics and Caveats

- The energy observable is a duplicate-charge closure proxy, not an independently calibrated calorimetric truth label.
- The PID observable is a support-stability proxy. It detects action-induced waveform/shape harm; it does not identify particle species.
- The traditional gate is intentionally advantaged for production safety because it is allowed to use the independent duplicate readout before blinding. The ML/NN panel answers whether even-waveform features alone can replace that frozen gate downstream.
- Bootstrap intervals are run-block intervals. They are wider and more relevant than row bootstrap intervals because run-family saturation behavior is the dominant correlation structure.
- P07l should therefore be read as a production-adoption closure for duplicate-gated B2 correction, not as a claim that duplicate closure supplies absolute energy or PID truth.

## Verdict

`traditional_run_family_duplicate_gate` wins the blinded downstream-energy/PID closure. The recommended production policy is to keep the transparent P07j/P07k duplicate envelope as the correction gate, expose only the final action label and blinded downstream summaries to consumers, and retain the ML/NN methods as monitoring/stress-test panels rather than production replacements.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `raw_reproduction.csv`, `reproduction_counts_by_run.csv`, `blinded_final_closure.csv`, `ml_minus_traditional_bootstrap.csv`, `downstream_consumer_summary.csv`, `leakage_sentinels.csv`, `blinded_feature_audit.csv`, and `REPORT.md`.
