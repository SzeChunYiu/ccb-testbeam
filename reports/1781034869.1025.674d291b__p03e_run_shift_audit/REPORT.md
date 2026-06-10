# P03e: waveform residual target run-shift audit

- **Ticket:** 1781034869.1025.674d291b
- **Author:** testbeam-laptop-4
- **Date:** 2026-06-10
- **Input:** raw B-stack ROOT files under `data/root/root`; no Monte Carlo.
- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65.
- **Config:** `configs/p03e_1781034869_1025_674d291b_run_shift_audit.yaml`

## Abstract

This study audits the run-dependent waveform residual target behind the P03d MLP instability, with special attention to held-out run 61. The raw ROOT count gate is reproduced before modeling. A strong traditional partial-pooling analytic timewalk model is benchmarked against ridge regression, gradient-boosted trees, a tabular MLP, a waveform 1D-CNN, and a new morphology-gated CNN. The winner by pooled run-bootstrap sigma68 is **hierarchical_shrinkage** at **1.251 ns** with 95% CI [1.076, 1.489] ns.

## 1. Raw-ROOT Reproduction

The S00 selected-pulse gate was rerun directly on `HRDv`: B-stack even channels B2/B4/B6/B8, median baseline over samples 0-3, and amplitude greater than 1000 ADC.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The run-65 S03a reference is reproduced from the same raw-derived pulse table:

|   heldout_run | method               | metric                      |   value |   ci_low |   ci_high |   n_pair_residuals |   median_ns |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   core_sigma_ns |   chi2_ndf | train_runs        | s03a_candidate   |   s03a_alpha |   hier_alpha_global |   hier_alpha_dev |   hier_cv_sigma68_ns |   ridge_cv_sigma68_ns |   hgb_cv_sigma68_ns |   reference_value |   delta | pass   |
|--------------:|:---------------------|:----------------------------|--------:|---------:|----------:|-------------------:|------------:|-------------:|--------------:|----------------------:|----------------:|-----------:|:------------------|:-----------------|-------------:|--------------------:|-----------------:|---------------------:|----------------------:|--------------------:|------------------:|--------:|:-------|
|            65 | template_phase_base  | heldout_pairwise_sigma68_ns | 2.88915 |  2.63915 |   3.13915 |                198 |    -3.83043 |      2.88915 |       2.57669 |            0.0505051  |        0.442691 |    3.21363 | 58,59,60,61,62,63 | amp_only         |          100 |                 100 |              100 |              1.16137 |               1.63485 |              1.3257 |           2.88915 |       0 | True   |
|            65 | s03a_amp_only_global | heldout_pairwise_sigma68_ns | 1.49464 |  1.34201 |   1.637   |                198 |     1.17923 |      1.49464 |       1.69913 |            0.00505051 |        1.26115  |    2.03718 | 58,59,60,61,62,63 | amp_only         |          100 |                 100 |              100 |              1.16137 |               1.63485 |              1.3257 |           1.49464 |       0 | True   |

## 2. Estimand and Equations

For stave \(s\) in event \(e\), the template-phase time is corrected for flight distance as

\[ c_{es}=t^{(0)}_{es}-x_s v^{-1}, \]

where \(x_s\) is the B4/B6/B8 longitudinal position and \(v^{-1}=0.078\) ns/cm. The supervised residual target for a pulse is the leave-one-stave event contrast

\[ y_{es}=c_{es}-\frac{1}{2}\sum_{r\ne s}c_{er}. \]

A residual model \(\hat y_{es}=f_\theta(w_{es}, z_{es})\) produces corrected times

\[ \hat t_{es}=t^{(0)}_{es}-\hat y_{es}. \]

The reported score is the pairwise same-event robust width

\[ \sigma_{68}=\frac{Q_{84}(\Delta\hat c)-Q_{16}(\Delta\hat c)}{2}, \]

computed on B4-B6, B4-B8, and B6-B8 residuals in the held-out run. Pooled intervals resample held-out runs, not individual residuals.

## 3. Methods

- **Traditional baseline:** S03a amp-only ridge and S03d hierarchical shrinkage. The hierarchical model has population amplitude coefficients plus L2-shrunk train-run deviations; the held-out run deviation is absent, so prediction is population-only for the unseen run.
- **Ridge:** standardized waveform samples and scalar morphology features with inner run-grouped CV over ridge alpha.
- **Gradient-boosted trees:** histogram gradient boosting on the same tabular feature set with inner run-grouped CV.
- **MLP:** two-hidden-layer ReLU regressor on standardized waveform plus scalar features.
- **1D-CNN:** two convolutional layers over the 18-sample normalized waveform, concatenated with scalar morphology.
- **New architecture:** `shape_gated_cnn_new`, a CNN whose latent waveform channels are multiplicatively gated by scalar morphology (amplitude, peak sample, charge fractions, slopes, CFD times, and stave one-hot). It is designed to test whether waveform-shape covariate shift can condition the residual target without using run id.

All feature sets exclude run number, event identifiers, event order, cross-stave timing values, and held-out labels. Standardization constants are fit only on training runs.

## 4. Head-to-Head Results

|   heldout_run | method                 |    value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |   hier_cv_sigma68_ns |   ridge_cv_sigma68_ns |   hgb_cv_sigma68_ns |
|--------------:|:-----------------------|---------:|---------:|----------:|-------------------:|----------------------:|---------------------:|----------------------:|--------------------:|
|            58 | cnn1d                  | 1.70154  | 1.49674  |   1.82774 |                219 |            0.0228311  |              1.16034 |               1.62008 |             1.34217 |
|            58 | gradient_boosted_trees | 1.03627  | 0.829754 |   1.24123 |                219 |            0.0182648  |              1.16034 |               1.62008 |             1.34217 |
|            58 | hierarchical_shrinkage | 0.766925 | 0.685954 |   0.99177 |                219 |            0.0182648  |              1.16034 |               1.62008 |             1.34217 |
|            58 | mlp                    | 1.84849  | 1.60847  |   2.00851 |                219 |            0.0319635  |              1.16034 |               1.62008 |             1.34217 |
|            58 | ridge                  | 1.32679  | 1.17928  |   1.49175 |                219 |            0.0182648  |              1.16034 |               1.62008 |             1.34217 |
|            58 | s03a_amp_only_global   | 1.18748  | 1.13098  |   1.36548 |                219 |            0.0182648  |              1.16034 |               1.62008 |             1.34217 |
|            58 | shape_gated_cnn_new    | 1.80584  | 1.59315  |   1.99683 |                219 |            0.0273973  |              1.16034 |               1.62008 |             1.34217 |
|            58 | template_phase_base    | 2.6428   | 2.6428   |   2.77317 |                219 |            0.0776256  |              1.16034 |               1.62008 |             1.34217 |
|            59 | cnn1d                  | 1.48795  | 1.42728  |   1.5432  |               2289 |            0.0122324  |              1.16045 |               1.6049  |             1.35953 |
|            59 | gradient_boosted_trees | 1.19364  | 1.12928  |   1.23798 |               2289 |            0.0104849  |              1.16045 |               1.6049  |             1.35953 |
|            59 | hierarchical_shrinkage | 1.22376  | 1.1636   |   1.25105 |               2289 |            0.0122324  |              1.16045 |               1.6049  |             1.35953 |
|            59 | mlp                    | 1.5287   | 1.48881  |   1.59095 |               2289 |            0.0131062  |              1.16045 |               1.6049  |             1.35953 |
|            59 | ridge                  | 1.54922  | 1.48462  |   1.60294 |               2289 |            0.0126693  |              1.16045 |               1.6049  |             1.35953 |
|            59 | s03a_amp_only_global   | 1.45871  | 1.40026  |   1.51823 |               2289 |            0.0144168  |              1.16045 |               1.6049  |             1.35953 |
|            59 | shape_gated_cnn_new    | 1.47515  | 1.42361  |   1.5193  |               2289 |            0.0122324  |              1.16045 |               1.6049  |             1.35953 |
|            59 | template_phase_base    | 2.99232  | 2.99232  |   3.12333 |               2289 |            0.0677152  |              1.16045 |               1.6049  |             1.35953 |
|            60 | cnn1d                  | 1.47015  | 1.42014  |   1.53062 |               2424 |            0.015264   |              1.20608 |               1.60079 |             1.32177 |
|            60 | gradient_boosted_trees | 1.0942   | 1.05272  |   1.1464  |               2424 |            0.0136139  |              1.20608 |               1.60079 |             1.32177 |
|            60 | hierarchical_shrinkage | 1.05251  | 1.01288  |   1.10387 |               2424 |            0.0127888  |              1.20608 |               1.60079 |             1.32177 |
|            60 | mlp                    | 1.45148  | 1.38934  |   1.49058 |               2424 |            0.0148515  |              1.20608 |               1.60079 |             1.32177 |
|            60 | ridge                  | 1.40279  | 1.35564  |   1.4595  |               2424 |            0.0136139  |              1.20608 |               1.60079 |             1.32177 |
|            60 | s03a_amp_only_global   | 1.3437   | 1.28466  |   1.40077 |               2424 |            0.015264   |              1.20608 |               1.60079 |             1.32177 |
|            60 | shape_gated_cnn_new    | 1.46725  | 1.42415  |   1.51342 |               2424 |            0.0165017  |              1.20608 |               1.60079 |             1.32177 |
|            60 | template_phase_base    | 2.66393  | 2.66393  |   2.7113  |               2424 |            0.0944719  |              1.20608 |               1.60079 |             1.32177 |
|            61 | cnn1d                  | 1.83653  | 1.77411  |   1.8854  |               2799 |            0.0200071  |              1.07987 |               1.54883 |             1.26191 |
|            61 | gradient_boosted_trees | 1.69085  | 1.60656  |   1.79462 |               2799 |            0.0175063  |              1.07987 |               1.54883 |             1.26191 |
|            61 | hierarchical_shrinkage | 1.63537  | 1.53363  |   1.67061 |               2799 |            0.0228653  |              1.07987 |               1.54883 |             1.26191 |
|            61 | mlp                    | 1.84312  | 1.79361  |   1.90906 |               2799 |            0.017149   |              1.07987 |               1.54883 |             1.26191 |
|            61 | ridge                  | 2.06955  | 1.99585  |   2.13451 |               2799 |            0.0250089  |              1.07987 |               1.54883 |             1.26191 |
|            61 | s03a_amp_only_global   | 2.12996  | 1.99174  |   2.20532 |               2799 |            0.0314398  |              1.07987 |               1.54883 |             1.26191 |
|            61 | shape_gated_cnn_new    | 1.86884  | 1.80451  |   1.92562 |               2799 |            0.0185781  |              1.07987 |               1.54883 |             1.26191 |
|            61 | template_phase_base    | 2.70351  | 2.70351  |   2.70351 |               2799 |            0.0428725  |              1.07987 |               1.54883 |             1.26191 |
|            62 | cnn1d                  | 1.56182  | 1.52046  |   1.61701 |               2421 |            0.00950021 |              1.14757 |               1.60348 |             1.35306 |
|            62 | gradient_boosted_trees | 1.22577  | 1.1679   |   1.27686 |               2421 |            0.00950021 |              1.14757 |               1.60348 |             1.35306 |
|            62 | hierarchical_shrinkage | 1.18377  | 1.09965  |   1.25213 |               2421 |            0.0107394  |              1.14757 |               1.60348 |             1.35306 |
|            62 | mlp                    | 1.56265  | 1.52794  |   1.60629 |               2421 |            0.0107394  |              1.14757 |               1.60348 |             1.35306 |
|            62 | ridge                  | 1.50113  | 1.45287  |   1.55146 |               2421 |            0.0123916  |              1.14757 |               1.60348 |             1.35306 |
|            62 | s03a_amp_only_global   | 1.469    | 1.41417  |   1.51791 |               2421 |            0.0128046  |              1.14757 |               1.60348 |             1.35306 |
|            62 | shape_gated_cnn_new    | 1.52017  | 1.47876  |   1.56602 |               2421 |            0.00950021 |              1.14757 |               1.60348 |             1.35306 |
|            62 | template_phase_base    | 2.90117  | 2.90117  |   3.02631 |               2421 |            0.0929368  |              1.14757 |               1.60348 |             1.35306 |
|            63 | cnn1d                  | 1.52935  | 1.47897  |   1.58512 |               1110 |            0.0108108  |              1.16078 |               1.61267 |             1.3148  |
|            63 | gradient_boosted_trees | 1.13488  | 1.08855  |   1.2222  |               1110 |            0.0117117  |              1.16078 |               1.61267 |             1.3148  |
|            63 | hierarchical_shrinkage | 1.11004  | 1.03158  |   1.19782 |               1110 |            0.0189189  |              1.16078 |               1.61267 |             1.3148  |
|            63 | mlp                    | 1.50289  | 1.43544  |   1.58595 |               1110 |            0.0126126  |              1.16078 |               1.61267 |             1.3148  |
|            63 | ridge                  | 1.40267  | 1.33229  |   1.47048 |               1110 |            0.0189189  |              1.16078 |               1.61267 |             1.3148  |
|            63 | s03a_amp_only_global   | 1.39132  | 1.30071  |   1.45607 |               1110 |            0.0207207  |              1.16078 |               1.61267 |             1.3148  |
|            63 | shape_gated_cnn_new    | 1.40116  | 1.33117  |   1.4647  |               1110 |            0.0162162  |              1.16078 |               1.61267 |             1.3148  |
|            63 | template_phase_base    | 2.87872  | 2.87872  |   3.01249 |               1110 |            0.0963964  |              1.16078 |               1.61267 |             1.3148  |
|            65 | cnn1d                  | 1.64577  | 1.41136  |   1.82271 |                198 |            0.00505051 |              1.16137 |               1.63485 |             1.3257  |
|            65 | gradient_boosted_trees | 1.25318  | 1.12864  |   1.43347 |                198 |            0.00505051 |              1.16137 |               1.63485 |             1.3257  |
|            65 | hierarchical_shrinkage | 1.21984  | 1.00802  |   1.42152 |                198 |            0.00505051 |              1.16137 |               1.63485 |             1.3257  |
|            65 | mlp                    | 1.71798  | 1.54121  |   1.86191 |                198 |            0.00505051 |              1.16137 |               1.63485 |             1.3257  |
|            65 | ridge                  | 1.49989  | 1.30652  |   1.66951 |                198 |            0.00505051 |              1.16137 |               1.63485 |             1.3257  |
|            65 | s03a_amp_only_global   | 1.49464  | 1.34874  |   1.62118 |                198 |            0.00505051 |              1.16137 |               1.63485 |             1.3257  |
|            65 | shape_gated_cnn_new    | 1.57993  | 1.4294   |   1.76608 |                198 |            0          |              1.16137 |               1.63485 |             1.3257  |
|            65 | template_phase_base    | 2.88915  | 2.63915  |   3.20541 |                198 |            0.0505051  |              1.16137 |               1.63485 |             1.3257  |

Pooled run-bootstrap summary:

| method                 |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:-----------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| template_phase_base    | 2.74141 |  2.68945 |   2.98633 |              11460 |             0.0813264 |
| s03a_amp_only_global   | 1.55109 |  1.36432 |   1.91513 |              11460 |             0.0191099 |
| hierarchical_shrinkage | 1.251   |  1.07578 |   1.48885 |              11460 |             0.0153578 |
| ridge                  | 1.58722 |  1.4377  |   1.85022 |              11460 |             0.0166667 |
| gradient_boosted_trees | 1.28204 |  1.13263 |   1.56409 |              11460 |             0.0130017 |
| mlp                    | 1.60663 |  1.49428 |   1.75479 |              11460 |             0.0143106 |
| cnn1d                  | 1.6005  |  1.49241 |   1.72999 |              11460 |             0.0138743 |
| shape_gated_cnn_new    | 1.58298 |  1.46685 |   1.72972 |              11460 |             0.0146597 |

Run 61 detail:

| method                 |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:-----------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| template_phase_base    | 2.70351 |  2.70351 |   2.70351 |               2799 |             0.0428725 |
| s03a_amp_only_global   | 2.12996 |  1.99174 |   2.20532 |               2799 |             0.0314398 |
| hierarchical_shrinkage | 1.63537 |  1.53363 |   1.67061 |               2799 |             0.0228653 |
| ridge                  | 2.06955 |  1.99585 |   2.13451 |               2799 |             0.0250089 |
| gradient_boosted_trees | 1.69085 |  1.60656 |   1.79462 |               2799 |             0.0175063 |
| mlp                    | 1.84312 |  1.79361 |   1.90906 |               2799 |             0.017149  |
| cnn1d                  | 1.83653 |  1.77411 |   1.8854  |               2799 |             0.0200071 |
| shape_gated_cnn_new    | 1.86884 |  1.80451 |   1.92562 |               2799 |             0.0185781 |

## 5. Run-Shift Diagnostics

Per-fold train-vs-heldout target and covariate distribution shifts use two-sample Kolmogorov-Smirnov statistics for scalar distributions. The target rows show the quantity being learned; amplitude, peak sample, and area rows expose candidate waveform-shape covariate shifts.

|   heldout_run | quantity           |      train_mean |    heldout_mean |   train_sigma68 |   heldout_sigma68 |   ks_stat |   ks_pvalue |
|--------------:|:-------------------|----------------:|----------------:|----------------:|------------------:|----------:|------------:|
|            58 | target_residual_ns |     1.41843e-15 |     1.8818e-15  |         3.40976 |           3.40976 | 0.0681507 | 0.258825    |
|            58 | amplitude_adc      |  2746.7         |  2754.41        |       795.8     |         714.96    | 0.0485356 | 0.673231    |
|            58 | peak_sample        |     7.8332      |     9.9589      |         2       |           4.5     | 0.361431  | 1.15245e-25 |
|            58 | area_adc_samples   | 20422.5         | 17989.7         |      8926.4     |        9051.5     | 0.140799  | 0.000350965 |
|            59 | target_residual_ns |     5.77979e-16 |     5.02874e-16 |         3.36348 |           3.48848 | 0.0402637 | 0.00509643  |
|            59 | amplitude_adc      |  2786.24        |  2589           |       788       |         780.42    | 0.121791  | 3.66374e-15 |
|            59 | peak_sample        |     7.90993     |     7.72914     |         2       |           2       | 0.0504485 | 0.000170929 |
|            59 | area_adc_samples   | 20669.5         | 19200.2         |      9043.1     |        8367.02    | 0.111889  | 3.66374e-15 |
|            60 | target_residual_ns |     5.46511e-16 |     5.33493e-16 |         3.29983 |           3.37089 | 0.0260076 | 0.147591    |
|            60 | amplitude_adc      |  2691.11        |  2954.61        |       787.35    |         775.88    | 0.166093  | 9.99201e-16 |
|            60 | peak_sample        |     7.91102     |     7.73515     |         2       |           2       | 0.065897  | 1.16054e-07 |
|            60 | area_adc_samples   | 19877.6         | 22233.9         |      8705.9     |        9407.78    | 0.153964  | 9.99201e-16 |
|            61 | target_residual_ns |     1.10179e-15 |     1.10173e-15 |         3.47188 |           3.34688 | 0.0871328 | 2.07612e-14 |
|            61 | amplitude_adc      |  2727.32        |  2807.27        |       795.6     |         770.61    | 0.0549485 | 5.39033e-06 |
|            61 | peak_sample        |     7.8656      |     7.89925     |         2       |           2       | 0.0201969 | 0.34843     |
|            61 | area_adc_samples   | 20128           | 21143.5         |      8970.8     |        8739.92    | 0.0801426 | 2.87836e-12 |
|            62 | target_residual_ns |    -8.37181e-16 |    -8.7167e-16  |         3.41447 |           3.47718 | 0.0270129 | 0.120608    |
|            62 | amplitude_adc      |  2755.42        |  2714.85        |       803.92    |         762.35    | 0.0353458 | 0.0164645   |
|            62 | peak_sample        |     7.90596     |     7.75382     |         2       |           2       | 0.0280196 | 0.097539    |
|            62 | area_adc_samples   | 20474.3         | 20009.2         |      9002.1     |        8475.6     | 0.0357683 | 0.0146741   |
|            63 | target_residual_ns |    -6.15804e-16 |    -6.20925e-16 |         3.39374 |           3.4694  | 0.0403212 | 0.0748439   |
|            63 | amplitude_adc      |  2764.77        |  2579.72        |       792.25    |         821.82    | 0.119371  | 6.72867e-13 |
|            63 | peak_sample        |     7.86145     |     7.98919     |         2       |           1.5     | 0.0145215 | 0.982148    |
|            63 | area_adc_samples   | 20559.8         | 18662           |      8874.92    |        8859.5     | 0.141496  | 5.75943e-18 |
|            65 | target_residual_ns |    -2.20822e-17 |    -4.30632e-16 |         3.41578 |           3.41578 | 0.0496655 | 0.702799    |
|            65 | amplitude_adc      |  2751.3         |  2493.69        |       794.25    |         859.7     | 0.162752  | 5.56579e-05 |
|            65 | peak_sample        |     7.84701     |     9.39899     |         2       |           3       | 0.182849  | 3.53573e-06 |
|            65 | area_adc_samples   | 20433.5         | 17108.9         |      8908.72    |        7912.84    | 0.209554  | 5.44701e-08 |

Worst amplitude/peak strata by held-out analytic pulse-residual width:

|   heldout_run | stratum_type       | stratum             |   n_pulses |   target_mean_ns |   target_sigma68_ns |   analytic_pulse_residual_mean_ns |   analytic_pulse_residual_sigma68_ns |
|--------------:|:-------------------|:--------------------|-----------:|-----------------:|--------------------:|----------------------------------:|-------------------------------------:|
|            59 | peak_sample        | 15                  |         16 |         2.75771  |             4.79539 |                         2.61234   |                              3.63813 |
|            60 | peak_sample        | 15                  |         18 |         2.30464  |             2.61307 |                         1.58021   |                              3.26461 |
|            61 | peak_sample        | 14                  |         34 |         2.05176  |             3.47188 |                         2.25072   |                              2.83076 |
|            61 | peak_sample        | 9                   |        525 |         0.393223 |             2.97188 |                         0.504968  |                              1.79097 |
|            61 | peak_sample        | 8                   |        807 |        -0.148772 |             2.97188 |                        -0.165488  |                              1.53032 |
|            61 | peak_sample        | 7                   |        373 |        -0.203487 |             2.99185 |                        -0.473728  |                              1.4733  |
|            58 | peak_sample        | 7                   |         21 |        -1.89804  |             3.32387 |                        -1.72865   |                              1.46746 |
|            65 | amplitude_quartile | (1002.499, 1914.25] |         50 |        -1.01528  |             3.9197  |                         0.0964397 |                              1.41737 |
|            63 | peak_sample        | 9                   |        204 |         0.984985 |             4.14374 |                         0.345529  |                              1.40213 |
|            63 | peak_sample        | 8                   |        320 |        -0.618288 |             3.89374 |                        -0.284172  |                              1.34996 |
|            65 | peak_sample        | 7                   |         23 |         0.417674 |             4.07344 |                         0.233833  |                              1.34648 |
|            58 | peak_sample        | 9                   |         22 |         1.065    |             3.84516 |                         0.533623  |                              1.33673 |
|            59 | peak_sample        | 8                   |        714 |        -0.652715 |             3.91697 |                        -0.212763  |                              1.33281 |
|            62 | peak_sample        | 9                   |        475 |         0.771502 |             3.85218 |                         0.30152   |                              1.3157  |

## 6. Leakage and Negative Controls

| check                                             |   min_value |   median_value |   max_value |
|:--------------------------------------------------|------------:|---------------:|------------:|
| features_exclude_run_event_order_cross_stave_time |     1       |        1       |     1       |
| final_models_use_heldout_rows                     |     0       |        0       |     0       |
| hgb_shuffled_target_sigma68                       |     2.67546 |        2.84954 |     2.97932 |
| ridge_shuffled_target_sigma68                     |     2.68063 |        2.84437 |     2.99269 |
| standardization_fit_on_train_runs_only            |     1       |        1       |     1       |
| train_heldout_event_id_overlap                    |     0       |        0       |     0       |

The event-overlap check is exact on `(run, EVENTNO, EVT, loader_uid)`. Shuffled-target controls refit ridge and HGB after permuting training residual targets within the training runs; their scores remain broad and do not explain the promoted winner. Neural models are not given run labels or event keys and are trained only on train-run rows.

## 7. Systematics and Caveats

- The target is self-supervised from same-event downstream staves, not an external clock. It is appropriate for same-particle timing closure but does not establish an absolute beam-time truth.
- Run-bootstrap intervals have only seven held-out units, so they quantify between-run sensitivity but remain coarse.
- The neural models use fixed architecture hyperparameters to avoid an expensive nested search on a small Sample-II population; the comparison is therefore a disciplined benchmark panel, not an exhaustive neural architecture search.
- The morphology-gated CNN may exploit waveform-shape proxies for run condition, but because run id and held-out labels are excluded, any gain must transfer through measured pulse morphology.
- Run 61 has large pair statistics, so broad residuals there are not a low-statistics artifact; the diagnostic tables should be interpreted as distribution-shift evidence rather than proof of a single detector mechanism.

## 8. Verdict

`result.json` names `hierarchical_shrinkage` as the winner. The best strong traditional method is `hierarchical_shrinkage` at `1.251 ns`; the best ML/NN method is `gradient_boosted_trees` at `1.282 ns`.
For run 61, `hierarchical_shrinkage` is best at `1.635 ns`, while the traditional hierarchical score is `1.635 ns`.

This agrees with the current fleet synthesis: once the analytic amplitude timewalk family is made strong and evaluated leave-one-run-out, waveform MLP/CNN timing models do not beat the analytic baseline. P03e sharpens that statement by showing that even a morphology-gated CNN does not close the run-61 shift better than hierarchical shrinkage, while HGB is the closest ML comparator. The working hypothesis is that run-61 is dominated by a low-dimensional amplitude/run-coefficient shift plus sparse peak-sample strata, not by a waveform representation gap. A blinded Sample-I to Sample-II morphology-gated transfer with frozen hyperparameters would test whether the small HGB proximity is transferable or merely Sample-II tuning.

## 9. Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/p03e_1781034869_1025_674d291b_run_shift_audit.py --config configs/p03e_1781034869_1025_674d291b_run_shift_audit.yaml
```

Artifacts: `reproduction_match_table.csv`, `run65_reproduction.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `model_cv_scan.csv`, `torch_train_history.csv`, `run_shift_summary.csv`, `stratum_shift_summary.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.
