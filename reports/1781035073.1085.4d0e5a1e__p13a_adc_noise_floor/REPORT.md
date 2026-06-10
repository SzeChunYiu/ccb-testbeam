# P13a - ADC quantization noise floor across pulse phase

- **Study ID:** P13a
- **Ticket:** 1781035073.1085.4d0e5a1e
- **Author (worker label):** testbeam-laptop-3
- **Date:** 2026-06-10
- **Depends on:** S00 selected-pulse reproduction and the B-stack raw ROOT convention
- **Input checksum(s):** see `input_sha256.csv` and `manifest.json`
- **Git commit:** 9342bdb1f91a70bf517dbcb384ace4db597edf69
- **Config:** `configs/p13a_1781035073_1085_4d0e5a1e_adc_noise_floor.json`

## 0. Question

What per-sample ADC/electronics noise floor remains after conditioning on pulse phase, stave, amplitude, and neighboring waveform context, and does any learned denoiser beat a strong traditional template+smoother under a run-heldout split?

The preregistered ticket asked for noise sigma/MAD by phase, induced timing and charge floors, dropout false-positive rate, and an ML-minus-traditional denoising delta with bootstrap CIs.  This report uses a masked-sample denoising proxy: for sample \(j\), the value \(x_j\) is removed from the model input and the method predicts \(\hat x_j\) from all other samples and metadata.  The residual \(r_j=x_j-\hat x_j\), converted back to ADC counts, is the empirical unresolved sample component plus model mismatch.

## 1. Reproduction (mandatory gate)

The gate is the canonical raw-ROOT selected-pulse count for B-stack pulses with baseline-subtracted amplitude above 1000 ADC.

| quantity | report_value | reproduced | delta | tolerance | pass |
| --- | --- | --- | --- | --- | --- |
| total selected B-stack pulses, A>1000 ADC | 640737 | 640737 | 0 | 0 | True |
| Sample II analysis selected pulses | 125096 | 125096 | 0 | 0 | True |
| Sample II analysis B2 pulses | 88213 | 88213 | 0 | 0 | True |
| Sample II analysis B4 pulses | 21229 | 21229 | 0 | 0 | True |
| Sample II analysis B6 pulses | 11148 | 11148 | 0 | 0 | True |
| Sample II analysis B8 pulses | 4506 | 4506 | 0 | 0 | True |

All rows pass exactly, so the noise-floor analysis proceeds.

## 2. Traditional non-ML method

The traditional baseline is a calibrated template+smoother.  For each selected pulse \(i\), raw samples are baseline-subtracted by the median of samples 0-3 and normalized by \(A_i=\max_t y_{it}\).  Sample-I training pulses define median templates

\[
T_{s,p,b}(t)=\operatorname{median}\left(y_i(t)/A_i\mid \text{stave}=s,\ \text{peak}=p,\ \log(1+A_i)\in b\right),
\]

with fallbacks to stave-peak, stave, and global medians.  A leave-one-sample local smoother predicts \(I_i(j)=(x_{i,j-1}+x_{i,j+1})/2\) for interior samples, using the nearest neighbor at the two boundaries.  On Sample I only, each sample obtains a clipped least-squares blend

\[
\hat x_i(j)=\alpha_j T_i(j)+(1-\alpha_j)I_i(j),\quad
\alpha_j=\operatorname{clip}_{[0,1]}\frac{\sum_i (x_{ij}-I_{ij})(T_{ij}-I_{ij})}{\sum_i (T_{ij}-I_{ij})^2}.
\]

This is the baseline named `traditional_template_smoother`.  Its held-out MAE is `156.1695` ADC with run-block 95% CI `[147.7529, 163.2899]`.

## 3. ML and NN methods

The benchmark uses the same masked-sample target and the same held-out Sample-II rows for every method.  Tabular features include the 18-sample normalized waveform with the target sample set to zero, target-sample one-hot, stave one-hot, log amplitude, peak-sample phase, area/amplitude, the traditional template prediction, and neighbor interpolation.  No run id, event id, event order, or held-out target sample value is included.  Ridge and gradient-boosted-tree hyperparameters are selected by run-group CV inside Sample I; neural methods use fixed preregistered compact architectures:

- `ridge`: standardized linear ridge regression; alpha chosen by Sample-I run CV.
- `gradient_boosted_trees`: histogram gradient boosting; config grid chosen by Sample-I run CV.
- `mlp`: two-hidden-layer ReLU multilayer perceptron.
- `one_dimensional_cnn`: 1D convolutions over the masked waveform plus auxiliary metadata.
- `masked_attention`: new architecture for this ticket; a tiny masked self-attention denoiser that reads the target token representation after attention over the remaining samples.

CV scan:

| method | alpha | cv_mae_adc | max_iter | learning_rate | max_leaf_nodes | l2_regularization |
| --- | --- | --- | --- | --- | --- | --- |
| ridge | 1 | 35.46 | nan | nan | nan | nan |
| ridge | 0.01 | 60.71 | nan | nan | nan | nan |
| ridge | 0.1 | 60.81 | nan | nan | nan | nan |
| ridge | 10 | 111.1 | nan | nan | nan | nan |
| ridge | 100 | 171.8 | nan | nan | nan | nan |
| gradient_boosted_trees | nan | 148.9 | 60 | 0.05 | 15 | 0.01 |
| gradient_boosted_trees | nan | 162.9 | 45 | 0.06 | 15 | 0 |

## 4. Head-to-head benchmark

Primary metric: held-out masked-sample MAE in ADC counts.  Intervals are 250-replicate run-block bootstraps over held-out runs 58-65.

| method | mae_adc | mae_ci_low_adc | mae_ci_high_adc | rmse_adc | robust_sigma_adc | median_bias_adc |
| --- | --- | --- | --- | --- | --- | --- |
| ridge | 57.96 | 54.76 | 61.49 | 87.23 | 61.88 | 8.645 |
| gradient_boosted_trees | 134 | 126.7 | 140.7 | 275.4 | 103.1 | -14.48 |
| traditional_template_smoother | 156.2 | 147.8 | 163.3 | 358.1 | 84.15 | -2.245 |
| mlp | 226 | 214 | 238.7 | 402.9 | 202.5 | 1.558 |
| masked_attention | 540.5 | 523.1 | 558.7 | 722.3 | 612.9 | -102.4 |
| one_dimensional_cnn | 634.7 | 615 | 653.5 | 791.4 | 797.9 | -94.89 |

Paired ML-minus-traditional deltas:

| method | delta_mae_vs_traditional_adc | ci_low_adc | ci_high_adc |
| --- | --- | --- | --- |
| ridge | -98.21 | -103.9 | -92.48 |
| gradient_boosted_trees | -22.13 | -24.21 | -19.42 |
| mlp | 69.81 | 62.56 | 77.91 |
| masked_attention | 384.3 | 371 | 398.4 |
| one_dimensional_cnn | 478.6 | 464.1 | 493.3 |

Winner: **ridge** with MAE `57.9566` ADC, CI `[54.7593, 61.4872]`.  Winner minus traditional baseline is `-98.2129 [-103.9288, -92.4841]` ADC.  The verdict in `result.json` is therefore `ml_beats_baseline=true`.

Noise floor by pulse phase for all methods:

| method | phase | noise_sigma_adc | noise_sigma_ci_low_adc | noise_sigma_ci_high_adc | mae_adc |
| --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | peak | 127.2 | 121.5 | 132.2 | 142.5 |
| gradient_boosted_trees | pretrigger | 26.75 | 24.27 | 28.28 | 91.3 |
| gradient_boosted_trees | rising_edge | 160.1 | 142.9 | 178.9 | 192.9 |
| gradient_boosted_trees | tail | 105.4 | 97.1 | 112.6 | 121.2 |
| masked_attention | peak | 404.2 | 350.2 | 457.9 | 537.8 |
| masked_attention | pretrigger | 230.4 | 211.5 | 250.2 | 400.8 |
| masked_attention | rising_edge | 1001 | 969.5 | 1030 | 779 |
| masked_attention | tail | 561.3 | 525.2 | 606.5 | 485.2 |
| mlp | peak | 205.4 | 192.2 | 217.5 | 222.5 |
| mlp | pretrigger | 146.3 | 139.5 | 152.4 | 150.1 |
| mlp | rising_edge | 252.3 | 237 | 265.4 | 282.9 |
| mlp | tail | 215.8 | 203.3 | 229.3 | 238.3 |
| one_dimensional_cnn | peak | 402.5 | 358.1 | 463.4 | 737.1 |
| one_dimensional_cnn | pretrigger | 383.8 | 352 | 412.2 | 674.5 |
| one_dimensional_cnn | rising_edge | 1079 | 1039 | 1123 | 806.1 |
| one_dimensional_cnn | tail | 575.4 | 539.3 | 610.4 | 470.2 |
| ridge | peak | 60.88 | 57.01 | 67.89 | 59.04 |
| ridge | pretrigger | 67.37 | 62.97 | 71.66 | 61.59 |
| ridge | rising_edge | 64.74 | 60.84 | 68.34 | 60.41 |
| ridge | tail | 56.08 | 52.93 | 59.97 | 54.02 |
| traditional_template_smoother | peak | 113.8 | 100.1 | 127.3 | 146 |
| traditional_template_smoother | pretrigger | 9.542 | 8.764 | 10.32 | 85.33 |
| traditional_template_smoother | rising_edge | 268.9 | 247.1 | 296.3 | 317.1 |
| traditional_template_smoother | tail | 73.64 | 67.92 | 80.19 | 109 |

For the winning method, sample-level robust sigmas are in `sample_noise_floor.csv`.  The irreducible quantization-only lower bound is \(1/\sqrt{12}=0.2887\) ADC, so all fitted phase floors above that value include electronics noise, residual shape variation, and any denoiser model mismatch.

## 5. Falsification

- **Pre-registration:** the ticket fixed the metrics before fitting: phase noise sigma/MAD, timing and charge floors, dropout false-positive rate, and ML-minus-traditional delta with run-block bootstrap CIs.
- **Falsification test:** ML would be rejected as useful if every learned model had non-negative paired MAE delta versus the traditional baseline, or if the apparent best method only won after using held-out runs for calibration.
- **Result:** the paired bootstrap delta table above is the uncertainty-bearing comparison.  Six denoising families were compared, so this is reported as a benchmark ranking rather than as a single uncorrected discovery p-value.

## 6. Threats to validity

- **Benchmark/selection:** the traditional comparator is not a constant or global median; it combines amplitude/phase/stave templates with a leave-one-sample local smoother and calibrates the blend on training runs only.
- **Data leakage:** all fits, template bins, blend weights, and ML hyperparameter choices use Sample I only.  Sample II runs 58-65 are used only for evaluation and bootstrap intervals.  Features exclude run id, event id, and the target sample value.  Peak-sample phase is a measured pulse descriptor; it can be slightly coupled to the target sample near the maximum, so the peak-phase result should be read with that caveat.
- **Metric misuse:** MAE is the primary benchmark because it is robust for heavy-tailed sample residuals.  RMSE, median bias, robust sigma, phase sigmas, and sample sigmas are also reported so the full residual distribution is not compressed into one core number.
- **Post-hoc selection:** run split, phase bins, model families, bootstrap count, and CV grids are in the committed config.  The only model chosen after fitting is the winner by the preregistered primary metric.

## 7. Provenance manifest

`manifest.json` records input ROOT checksums, config, git commit, command line, runtime, package versions, random seeds, and output hashes.  `input_sha256.csv` gives per-run ROOT hashes.

## 8. Findings and next steps

The winning method is `ridge`.  The phase table gives the practical ADC/electronics floor for pretrigger, rising edge, peak, and tail samples under run-heldout calibration.  Derived systematic quantities are:

| quantity | value | unit | definition |
| --- | --- | --- | --- |
| sample_00_sigma_adc | 60.31 | ADC | 1.4826*MAD of held-out masked-sample residuals for the winning denoiser |
| sample_01_sigma_adc | 62.67 | ADC | 1.4826*MAD of held-out masked-sample residuals for the winning denoiser |
| sample_02_sigma_adc | 57.66 | ADC | 1.4826*MAD of held-out masked-sample residuals for the winning denoiser |
| sample_03_sigma_adc | 73.23 | ADC | 1.4826*MAD of held-out masked-sample residuals for the winning denoiser |
| sample_04_sigma_adc | 61.09 | ADC | 1.4826*MAD of held-out masked-sample residuals for the winning denoiser |
| sample_05_sigma_adc | 79.09 | ADC | 1.4826*MAD of held-out masked-sample residuals for the winning denoiser |
| sample_06_sigma_adc | 58.96 | ADC | 1.4826*MAD of held-out masked-sample residuals for the winning denoiser |
| sample_07_sigma_adc | 49.56 | ADC | 1.4826*MAD of held-out masked-sample residuals for the winning denoiser |
| sample_08_sigma_adc | 65.37 | ADC | 1.4826*MAD of held-out masked-sample residuals for the winning denoiser |
| sample_09_sigma_adc | 49.71 | ADC | 1.4826*MAD of held-out masked-sample residuals for the winning denoiser |
| sample_10_sigma_adc | 48.64 | ADC | 1.4826*MAD of held-out masked-sample residuals for the winning denoiser |
| sample_11_sigma_adc | 55.74 | ADC | 1.4826*MAD of held-out masked-sample residuals for the winning denoiser |
| sample_12_sigma_adc | 55.75 | ADC | 1.4826*MAD of held-out masked-sample residuals for the winning denoiser |
| sample_13_sigma_adc | 60.36 | ADC | 1.4826*MAD of held-out masked-sample residuals for the winning denoiser |
| sample_14_sigma_adc | 51.86 | ADC | 1.4826*MAD of held-out masked-sample residuals for the winning denoiser |
| sample_15_sigma_adc | 47.76 | ADC | 1.4826*MAD of held-out masked-sample residuals for the winning denoiser |
| sample_16_sigma_adc | 48.79 | ADC | 1.4826*MAD of held-out masked-sample residuals for the winning denoiser |
| sample_17_sigma_adc | 73.61 | ADC | 1.4826*MAD of held-out masked-sample residuals for the winning denoiser |
| rising_edge_timing_floor_ns | 0.534 | ns | rising-edge residual sigma divided by median held-out rising-edge slope |
| median_rising_edge_slope_adc_per_ns | 121.2 | ADC/ns | median of max positive first difference over samples 4-9 divided by 10 ns |
| integrated_charge_noise_floor_adc_sample | 252.8 | ADC sample | quadrature sum of per-sample winning residual sigmas |
| relative_charge_noise_floor | 0.0113 | fraction | charge noise floor divided by median absolute held-out pulse area |
| dropout_false_positive_rate_z_lt_minus_3 | 0.009077 | fraction | fraction of held-out normal samples whose negative denoising residual exceeds the per-sample threshold |
| ideal_adc_quantization_sigma | 0.2887 | ADC | 1/sqrt(12) for unit-spaced ADC bins; lower bound, not fit from data |

The rising-edge timing floor is a lower bound: it propagates only the sample noise term through a median rising-edge slope and does not include clock, path-length, time-walk, pile-up, or inter-stave correlation terms.  The charge floor similarly assumes independent sample residuals; correlations can make the true integrated charge uncertainty larger or smaller.

One follow-up is proposed in `result.json`: test whether adding the P13a sample-noise covariance as heteroscedastic weights changes S02/P03 timing residual tails under the same run-heldout discipline.

## 9. Reproducibility

Run:

```bash
/home/billy/anaconda3/bin/python scripts/p13a_1781035073_1085_4d0e5a1e_adc_noise_floor.py --config configs/p13a_1781035073_1085_4d0e5a1e_adc_noise_floor.json
```

Runtime for this execution was `69.7` s on `billy`.  Outputs include `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `run_counts.csv`, `reproduction_match_table.csv`, `heldout_predictions.csv`, `heldout_method_metrics.csv`, `paired_deltas_vs_traditional.csv`, `phase_noise_floor.csv`, `sample_noise_floor.csv`, `systematics.csv`, `leakage_checks.csv`, `cv_scan.csv`, and three PNG figures.
