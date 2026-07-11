# G4-05D: run-blinded hierarchical-shrinkage transfer guard on adjacent S02/S03 campaign

- **Ticket:** `1783775641.21314.24a82b5b`
- **Worker:** `testbeam-laptop-1`
- **Date:** 2026-07-11
- **Input:** raw B-stack ROOT files under `data/root/root`; no Monte Carlo or external labels.
- **Frozen training domain:** Sample-I analysis runs 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57.
- **Blinded scoring domain:** Sample-II analysis runs 58, 59, 60, 61, 62, 63, 65.
- **Config:** `configs/g4_05d_1783775641_21314_24a82b5b_adjacent_s02_s03_transfer_guard.yaml`

## Abstract

This study tests whether the G4-05C observation that HGB approached hierarchical shrinkage transfers when the waveform/morphology residual architecture and hyperparameters are frozen on Sample I before Sample II scoring. The raw ROOT selected-pulse counts are reproduced first. A strong traditional analytic hierarchy is then benchmarked against ridge, gradient-boosted trees, MLP, 1D-CNN, and the ticket-local morphology-gated CNN. The winner in `result.json` is **hierarchical_shrinkage** with pooled Sample-II pairwise sigma68 **1.115 ns** and 95% run-bootstrap CI [1.049, 1.261] ns.

## 1. Raw ROOT Reproduction

The S00 selected-pulse gate is rerun directly on `HRDv`: B-stack channels B2/B4/B6/B8, median baseline over samples 0-3, and amplitude greater than 1000 ADC. This reproduces the ticket-scale raw number before any model is trained.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## 2. Estimand

For event \(e\) and downstream stave \(s\), the base template-phase time is corrected by longitudinal flight distance,

\[ c_{es}=t^{(0)}_{es}-x_s v^{-1},\quad v^{-1}=0.078\;\mathrm{ns/cm}. \]

The self-supervised residual target on the training domain is the leave-one-stave contrast

\[ y_{es}=c_{es}-\frac{1}{2}\sum_{r\ne s} c_{er}. \]

A fitted residual model \(\hat y=f_\theta(w,z)\) produces corrected time \(\hat t=t^{(0)}-\hat y\). The reported timing metric is

\[ \sigma_{68}=\{Q_{84}(\Delta \hat c)-Q_{16}(\Delta \hat c)\}/2, \]

computed on B4-B6, B4-B8, and B6-B8 same-event pairwise residuals. Confidence intervals for per-run rows bootstrap pairwise residuals within that run; the primary pooled CI resamples Sample-II runs.

## 3. Frozen Methods

- **Traditional template-phase base:** the uncorrected pre-registered template phase selected on Sample-I training rows.
- **Analytic timewalk:** S03a amplitude-only analytic residual correction.
- **Hierarchical shrinkage:** population amplitude coefficients plus L2-shrunk Sample-I run deviations; because Sample II is blinded, the Sample-II prediction uses the population component without Sample-II deviations.
- **Ridge:** standardized 18-sample waveform plus scalar morphology with alpha selected by Sample-I grouped CV.
- **Gradient-boosted trees:** histogram GBT on the same features with all hyperparameter selection restricted to Sample-I grouped CV.
- **MLP:** fixed two-hidden-layer ReLU network trained on Sample-I rows only.
- **1D-CNN:** fixed two-layer convolution over normalized waveforms with scalar morphology concatenated only after convolution.
- **New architecture:** `waveform_morphology_gated_cnn_new`, a morphology-gated waveform CNN in which scalar pulse morphology multiplicatively gates the waveform latent vector before regression.

Feature controls exclude run number, event identifiers, event order, and cross-stave times. Standardization constants are fit only on Sample-I rows.

## 4. Hyperparameter Selection on Sample I

| model                  |   alpha |   fold |   sigma68_ns |   max_iter |   learning_rate |   max_leaf_nodes |   l2_regularization |   max_bins |   random_state |   alpha_global |   alpha_dev |   n_pair_residuals |
|:-----------------------|--------:|-------:|-------------:|-----------:|----------------:|-----------------:|--------------------:|-----------:|---------------:|---------------:|------------:|-------------------:|
| hgb                    |  nan    |     -1 |     1.22205  |         60 |            0.04 |               15 |                 0   |         64 |    2.02607e+07 |          nan   |         nan |                nan |
| hgb                    |  nan    |     -1 |     1.24544  |         60 |            0.04 |               15 |                 0.1 |         64 |    2.02607e+07 |          nan   |         nan |                nan |
| hgb                    |  nan    |     -1 |     1.40296  |         60 |            0.04 |                7 |                 0.1 |         64 |    2.02607e+07 |          nan   |         nan |                nan |
| hgb                    |  nan    |     -1 |     1.40649  |         60 |            0.04 |                7 |                 0   |         64 |    2.02607e+07 |          nan   |         nan |                nan |
| hgb                    |  nan    |     -1 |     1.44381  |        100 |            0.04 |               15 |                 0.1 |         64 |    2.02607e+07 |          nan   |         nan |                nan |
| hgb                    |  nan    |     -1 |     1.44989  |        100 |            0.04 |               15 |                 0   |         64 |    2.02607e+07 |          nan   |         nan |                nan |
| hgb                    |  nan    |     -1 |     1.46429  |         60 |            0.08 |               15 |                 0.1 |         64 |    2.02607e+07 |          nan   |         nan |                nan |
| hgb                    |  nan    |     -1 |     1.47398  |         60 |            0.08 |               15 |                 0   |         64 |    2.02607e+07 |          nan   |         nan |                nan |
| hgb                    |  nan    |     -1 |     1.48699  |        100 |            0.08 |               15 |                 0.1 |         64 |    2.02607e+07 |          nan   |         nan |                nan |
| hgb                    |  nan    |     -1 |     1.49812  |        100 |            0.08 |               15 |                 0   |         64 |    2.02607e+07 |          nan   |         nan |                nan |
| hgb                    |  nan    |     -1 |     1.56712  |        100 |            0.08 |                7 |                 0.1 |         64 |    2.02607e+07 |          nan   |         nan |                nan |
| hgb                    |  nan    |     -1 |     1.56772  |         60 |            0.08 |                7 |                 0   |         64 |    2.02607e+07 |          nan   |         nan |                nan |
| hgb                    |  nan    |     -1 |     1.56969  |         60 |            0.08 |                7 |                 0.1 |         64 |    2.02607e+07 |          nan   |         nan |                nan |
| hgb                    |  nan    |     -1 |     1.57432  |        100 |            0.04 |                7 |                 0   |         64 |    2.02607e+07 |          nan   |         nan |                nan |
| hgb                    |  nan    |     -1 |     1.57612  |        100 |            0.08 |                7 |                 0   |         64 |    2.02607e+07 |          nan   |         nan |                nan |
| hgb                    |  nan    |     -1 |     1.58416  |        100 |            0.04 |                7 |                 0.1 |         64 |    2.02607e+07 |          nan   |         nan |                nan |
| hierarchical_shrinkage |  nan    |     -1 |     0.649418 |        nan |          nan    |              nan |               nan   |        nan |  nan           |          100   |          10 |                  0 |
| hierarchical_shrinkage |  nan    |     -1 |     1.24091  |        nan |          nan    |              nan |               nan   |        nan |  nan           |          100   |         100 |                  0 |
| hierarchical_shrinkage |  nan    |     -1 |     1.36141  |        nan |          nan    |              nan |               nan   |        nan |  nan           |           10   |          10 |                  0 |
| hierarchical_shrinkage |  nan    |     -1 |     1.57916  |        nan |          nan    |              nan |               nan   |        nan |  nan           |          100   |        1000 |                  0 |
| hierarchical_shrinkage |  nan    |     -1 |     1.61587  |        nan |          nan    |              nan |               nan   |        nan |  nan           |          100   |       10000 |                  0 |
| hierarchical_shrinkage |  nan    |     -1 |     1.70183  |        nan |          nan    |              nan |               nan   |        nan |  nan           |            1   |          10 |                  0 |
| hierarchical_shrinkage |  nan    |     -1 |     1.71298  |        nan |          nan    |              nan |               nan   |        nan |  nan           |            0.1 |          10 |                  0 |
| hierarchical_shrinkage |  nan    |     -1 |     1.71633  |        nan |          nan    |              nan |               nan   |        nan |  nan           |           10   |         100 |                  0 |
| hierarchical_shrinkage |  nan    |     -1 |     1.73493  |        nan |          nan    |              nan |               nan   |        nan |  nan           |            0.1 |       10000 |                  0 |
| hierarchical_shrinkage |  nan    |     -1 |     1.7414   |        nan |          nan    |              nan |               nan   |        nan |  nan           |            0.1 |        1000 |                  0 |
| hierarchical_shrinkage |  nan    |     -1 |     1.7461   |        nan |          nan    |              nan |               nan   |        nan |  nan           |            0.1 |         100 |                  0 |
| hierarchical_shrinkage |  nan    |     -1 |     1.75325  |        nan |          nan    |              nan |               nan   |        nan |  nan           |           10   |       10000 |                  0 |
| hierarchical_shrinkage |  nan    |     -1 |     1.75449  |        nan |          nan    |              nan |               nan   |        nan |  nan           |           10   |        1000 |                  0 |
| hierarchical_shrinkage |  nan    |     -1 |     1.7582   |        nan |          nan    |              nan |               nan   |        nan |  nan           |            1   |       10000 |                  0 |
| hierarchical_shrinkage |  nan    |     -1 |     1.76224  |        nan |          nan    |              nan |               nan   |        nan |  nan           |            1   |        1000 |                  0 |
| hierarchical_shrinkage |  nan    |     -1 |     1.76824  |        nan |          nan    |              nan |               nan   |        nan |  nan           |            1   |         100 |                  0 |
| ridge                  |  100    |     -1 |     1.58538  |        nan |          nan    |              nan |               nan   |        nan |  nan           |          nan   |         nan |                nan |
| ridge                  |    1    |     -1 |     1.73482  |        nan |          nan    |              nan |               nan   |        nan |  nan           |          nan   |         nan |                nan |
| ridge                  |   10    |     -1 |     1.73851  |        nan |          nan    |              nan |               nan   |        nan |  nan           |          nan   |         nan |                nan |
| ridge                  |    0.1  |     -1 |     1.74153  |        nan |          nan    |              nan |               nan   |        nan |  nan           |          nan   |         nan |                nan |
| ridge                  |    0.01 |     -1 |     1.74203  |        nan |          nan    |              nan |               nan   |        nan |  nan           |          nan   |         nan |                nan |

## 5. Sample-II Head-to-Head Benchmark

|   heldout_run | method                            | family      |    value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|--------------:|:----------------------------------|:------------|---------:|---------:|----------:|-------------------:|----------------------:|
|            58 | cnn1d                             | nn          | 1.5388   | 1.39033  |  1.7327   |                219 |            0.0273973  |
|            58 | gradient_boosted_trees            | ml          | 1.28416  | 1.16245  |  1.51285  |                219 |            0.00913242 |
|            58 | hierarchical_shrinkage            | traditional | 0.504654 | 0.368049 |  0.739596 |                219 |            0.0136986  |
|            58 | mlp                               | nn          | 1.58799  | 1.42442  |  1.88809  |                219 |            0.0365297  |
|            58 | ridge                             | ml          | 1.58352  | 1.46807  |  1.68642  |                219 |            0.00913242 |
|            58 | s03a_amp_only_global              | traditional | 1.66707  | 1.58342  |  1.69865  |                219 |            0.00913242 |
|            58 | template_phase_base               | traditional | 2.35907  | 2.35907  |  2.50242  |                219 |            0.100457   |
|            58 | waveform_morphology_gated_cnn_new | nn          | 1.69418  | 1.48216  |  1.96537  |                219 |            0.0410959  |
|            59 | cnn1d                             | nn          | 1.79303  | 1.71568  |  1.88047  |               2289 |            0.0323285  |
|            59 | gradient_boosted_trees            | ml          | 1.50773  | 1.44022  |  1.58122  |               2289 |            0.0148536  |
|            59 | hierarchical_shrinkage            | traditional | 1.15707  | 0.992978 |  1.22772  |               2289 |            0.0336391  |
|            59 | mlp                               | nn          | 1.90111  | 1.79889  |  2.0379   |               2289 |            0.0292704  |
|            59 | ridge                             | ml          | 1.7066   | 1.67618  |  1.72777  |               2289 |            0.0183486  |
|            59 | s03a_amp_only_global              | traditional | 1.68126  | 1.66501  |  1.70253  |               2289 |            0.0222805  |
|            59 | template_phase_base               | traditional | 2.60907  | 2.35907  |  2.75242  |               2289 |            0.153342   |
|            59 | waveform_morphology_gated_cnn_new | nn          | 1.89441  | 1.75724  |  2.02026  |               2289 |            0.0297073  |
|            60 | cnn1d                             | nn          | 1.76188  | 1.68915  |  1.83232  |               2424 |            0.0437294  |
|            60 | gradient_boosted_trees            | ml          | 1.49802  | 1.4603   |  1.55265  |               2424 |            0.0210396  |
|            60 | hierarchical_shrinkage            | traditional | 1.09525  | 1.00412  |  1.26265  |               2424 |            0.0317657  |
|            60 | mlp                               | nn          | 1.92486  | 1.84656  |  2.05155  |               2424 |            0.0474422  |
|            60 | ridge                             | ml          | 1.73503  | 1.70963  |  1.7599   |               2424 |            0.0169142  |
|            60 | s03a_amp_only_global              | traditional | 1.69469  | 1.6742   |  1.80595  |               2424 |            0.0193894  |
|            60 | template_phase_base               | traditional | 2.35907  | 2.35907  |  2.60907  |               2424 |            0.151403   |
|            60 | waveform_morphology_gated_cnn_new | nn          | 1.86704  | 1.79046  |  1.96289  |               2424 |            0.0511551  |
|            61 | cnn1d                             | nn          | 2.18978  | 2.10927  |  2.25267  |               2799 |            0.0603787  |
|            61 | gradient_boosted_trees            | ml          | 1.71715  | 1.66459  |  1.79293  |               2799 |            0.030368   |
|            61 | hierarchical_shrinkage            | traditional | 1.31198  | 1.25165  |  1.48309  |               2799 |            0.0332262  |
|            61 | mlp                               | nn          | 2.2576   | 2.15937  |  2.37558  |               2799 |            0.0714541  |
|            61 | ridge                             | ml          | 1.98628  | 1.88685  |  2.06915  |               2799 |            0.0242944  |
|            61 | s03a_amp_only_global              | traditional | 2.1017   | 2.00798  |  2.19381  |               2799 |            0.0282244  |
|            61 | template_phase_base               | traditional | 2.60907  | 2.35907  |  2.75     |               2799 |            0.130046   |
|            61 | waveform_morphology_gated_cnn_new | nn          | 2.33656  | 2.23024  |  2.47564  |               2799 |            0.0721686  |
|            62 | cnn1d                             | nn          | 1.7235   | 1.64598  |  1.78606  |               2421 |            0.031805   |
|            62 | gradient_boosted_trees            | ml          | 1.4599   | 1.40486  |  1.52676  |               2421 |            0.015696   |
|            62 | hierarchical_shrinkage            | traditional | 1.06042  | 0.956762 |  1.23288  |               2421 |            0.0330442  |
|            62 | mlp                               | nn          | 1.80444  | 1.71886  |  1.91872  |               2421 |            0.0380008  |
|            62 | ridge                             | ml          | 1.7211   | 1.69084  |  1.75216  |               2421 |            0.0152829  |
|            62 | s03a_amp_only_global              | traditional | 1.68767  | 1.66746  |  1.7325   |               2421 |            0.0185874  |
|            62 | template_phase_base               | traditional | 2.35907  | 2.35907  |  2.60907  |               2421 |            0.148699   |
|            62 | waveform_morphology_gated_cnn_new | nn          | 1.82606  | 1.74079  |  1.91817  |               2421 |            0.0400661  |
|            63 | cnn1d                             | nn          | 1.74063  | 1.6331   |  1.83511  |               1110 |            0.0351351  |
|            63 | gradient_boosted_trees            | ml          | 1.42987  | 1.31029  |  1.52496  |               1110 |            0.0225225  |
|            63 | hierarchical_shrinkage            | traditional | 1.21504  | 1.06586  |  1.46331  |               1110 |            0.0369369  |
|            63 | mlp                               | nn          | 1.72559  | 1.59618  |  1.88652  |               1110 |            0.0306306  |
|            63 | ridge                             | ml          | 1.71764  | 1.66821  |  1.76259  |               1110 |            0.0234234  |
|            63 | s03a_amp_only_global              | traditional | 1.69744  | 1.67215  |  1.72567  |               1110 |            0.0243243  |
|            63 | template_phase_base               | traditional | 2.75242  | 2.35907  |  3.00242  |               1110 |            0.16036    |
|            63 | waveform_morphology_gated_cnn_new | nn          | 1.71219  | 1.61626  |  1.86989  |               1110 |            0.0342342  |
|            65 | cnn1d                             | nn          | 1.61785  | 1.44293  |  1.82954  |                198 |            0.030303   |
|            65 | gradient_boosted_trees            | ml          | 1.52405  | 1.28061  |  1.75752  |                198 |            0.0151515  |
|            65 | hierarchical_shrinkage            | traditional | 0.663862 | 0.399054 |  1.22703  |                198 |            0.030303   |
|            65 | mlp                               | nn          | 1.70917  | 1.54186  |  2.24248  |                198 |            0.0252525  |
|            65 | ridge                             | ml          | 1.68335  | 1.52994  |  1.79731  |                198 |            0.0151515  |
|            65 | s03a_amp_only_global              | traditional | 1.6526   | 1.59943  |  1.7041   |                198 |            0.0151515  |
|            65 | template_phase_base               | traditional | 2.35907  | 2.35907  |  2.75242  |                198 |            0.111111   |
|            65 | waveform_morphology_gated_cnn_new | nn          | 1.65553  | 1.43432  |  2.13606  |                198 |            0.0505051  |

Pooled run-bootstrap summary:

| method                            | family      |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:----------------------------------|:------------|--------:|---------:|----------:|-------------------:|----------------------:|
| template_phase_base               | traditional | 2.5     |  2.35907 |   2.60907 |              11460 |             0.149738  |
| s03a_amp_only_global              | traditional | 1.72254 |  1.68    |   1.91995 |              11460 |             0.0222513 |
| hierarchical_shrinkage            | traditional | 1.11525 |  1.04885 |   1.26057 |              11460 |             0.032897  |
| ridge                             | ml          | 1.73588 |  1.70582 |   1.82854 |              11460 |             0.0191972 |
| gradient_boosted_trees            | ml          | 1.51141 |  1.45414 |   1.65736 |              11460 |             0.0209424 |
| mlp                               | nn          | 1.94808 |  1.79432 |   2.13012 |              11460 |             0.0457243 |
| cnn1d                             | nn          | 1.84081 |  1.72262 |   2.05088 |              11460 |             0.0410122 |
| waveform_morphology_gated_cnn_new | nn          | 1.93012 |  1.80177 |   2.16534 |              11460 |             0.0472077 |

## 6. Sample-II Shift and Systematics

|   heldout_run | quantity           |      train_mean |    heldout_mean |   train_sigma68 |   heldout_sigma68 |   ks_stat |   ks_pvalue |
|--------------:|:-------------------|----------------:|----------------:|----------------:|------------------:|----------:|------------:|
|            58 | target_residual_ns |    -5.92523e-17 |     0           |         4.07357 |           4.07357 | 0.112502  | 0.00795274  |
|            58 | amplitude_adc      |  2740.95        |  2754.41        |       792.05    |         714.96    | 0.0495761 | 0.647482    |
|            58 | peak_sample        |     8.19331     |     9.9589      |         2.5     |           4.5     | 0.306246  | 2.13828e-18 |
|            58 | area_adc_samples   | 19898.1         | 17989.7         |      8984.5     |        9051.5     | 0.118639  | 0.00429026  |
|            59 | target_residual_ns |    -5.43082e-17 |    -7.76041e-17 |         4.07357 |           4.07357 | 0.030844  | 0.0529131   |
|            59 | amplitude_adc      |  2772.49        |  2589           |       786.65    |         780.42    | 0.115857  | 1.188e-22   |
|            59 | peak_sample        |     8.32362     |     7.72914     |         3       |           2       | 0.112928  | 1.53696e-21 |
|            59 | area_adc_samples   | 20004.1         | 19200.2         |      9118.3     |        8367.02    | 0.0817568 | 1.7489e-11  |
|            60 | target_residual_ns |    -4.98014e-17 |    -9.96636e-17 |         4.07357 |           4.07357 | 0.0184778 | 0.500638    |
|            60 | amplitude_adc      |  2694.07        |  2954.61        |       786.6     |         775.88    | 0.161983  | 5.35956e-46 |
|            60 | peak_sample        |     8.3296      |     7.73515     |         2       |           2       | 0.110036  | 2.13024e-21 |
|            60 | area_adc_samples   | 19344.6         | 22233.9         |      8761.8     |        9407.78    | 0.172499  | 3.82009e-52 |
|            61 | target_residual_ns |    -7.70073e-17 |     1.26928e-17 |         4.07357 |           4.07357 | 0.0641038 | 2.34434e-08 |
|            61 | amplitude_adc      |  2723.73        |  2807.27        |       792.45    |         770.61    | 0.0554572 | 2.31455e-06 |
|            61 | peak_sample        |     8.30732     |     7.89925     |         2.2     |           2       | 0.0589133 | 3.9991e-07  |
|            61 | area_adc_samples   | 19530.1         | 21143.5         |      8938.6     |        8739.92    | 0.103914  | 2.80594e-21 |
|            62 | target_residual_ns |    -4.7848e-17  |    -1.05657e-16 |         4.07357 |           4.07357 | 0.0240829 | 0.196856    |
|            62 | amplitude_adc      |  2746.97        |  2714.85        |       798.25    |         762.35    | 0.0316031 | 0.0372007   |
|            62 | peak_sample        |     8.32533     |     7.75382     |         2       |           2       | 0.0919876 | 4.64004e-15 |
|            62 | area_adc_samples   | 19835.5         | 20009.2         |      9100.88    |        8475.6     | 0.0349488 | 0.0153366   |
|            63 | target_residual_ns |    -5.77677e-17 |    -6.40129e-17 |         4.07357 |           4.07357 | 0.0401252 | 0.0733765   |
|            63 | amplitude_adc      |  2755.74        |  2579.72        |       787.54    |         821.82    | 0.115091  | 3.33439e-12 |
|            63 | peak_sample        |     8.24317     |     7.98919     |         2.5     |           1.5     | 0.0509558 | 0.00976243  |
|            63 | area_adc_samples   | 19975.6         | 18662           |      8966.74    |        8859.5     | 0.117124  | 1.26662e-12 |
|            65 | target_residual_ns |    -6.13093e-17 |     1.43544e-16 |         4.07357 |           4.07357 | 0.0668194 | 0.333837    |
|            65 | amplitude_adc      |  2744.88        |  2493.69        |       790.62    |         859.7     | 0.159745  | 8.1737e-05  |
|            65 | peak_sample        |     8.20451     |     9.39899     |         2.5     |           3       | 0.143623  | 0.000566566 |
|            65 | area_adc_samples   | 19908.2         | 17108.9         |      8985.86    |        7912.84    | 0.183194  | 3.36238e-06 |

The covariate-shift table is interpreted as a systematic diagnostic, not as a post-hoc feature-selection stage. The frozen model choice is not changed after observing these rows.

## 7. Leakage and Negative Controls

| check                                             |   min_value |   median_value |   max_value |
|:--------------------------------------------------|------------:|---------------:|------------:|
| features_exclude_run_event_order_cross_stave_time |     1       |        1       |     1       |
| final_models_use_sample_ii_labels_or_rows         |     0       |        0       |     0       |
| hgb_shuffled_target_sigma68                       |     2.74059 |        3.0785  |     3.16177 |
| hyperparameters_selected_on_sample_i_only         |     1       |        1       |     1       |
| ridge_shuffled_target_sigma68                     |     2.48222 |        2.77285 |     2.81933 |
| train_heldout_event_id_overlap                    |     0       |        0       |     0       |

The event-overlap check is exact on the loader event identifier. Shuffled-target controls refit ridge and HGB after permuting Sample-I residual targets; broad shuffled scores indicate the Sample-II winner is not explained by a trivial feature leak. Neural models receive no Sample-II labels during training.

## 8. Caveats

- The target remains a same-event downstream-stave timing closure target rather than an external absolute clock.
- Sample-II has only seven held-out run units, so run-bootstrap intervals are intentionally conservative and coarse.
- The neural architectures are fixed from the predecessor study; this is a transfer test, not a new architecture search.
- The hierarchy cannot estimate Sample-II run deviations without violating the blinded transfer rule. Its Sample-II prediction is therefore the frozen population correction.
- If the gating CNN wins, it demonstrates transferable waveform/morphology information, not detector-causal truth by itself.

## 9. Verdict

`result.json` names `hierarchical_shrinkage` as the winner. The best traditional method is `hierarchical_shrinkage` at 1.115 ns; the best ML/NN method is `gradient_boosted_trees` at 1.511 ns.
The transfer conclusion is: hierarchical_shrinkage is the best frozen Sample-I to Sample-II transfer method; best ML/NN minus best traditional = 0.396 ns.

## 10. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/g4_05d_1783775641_21314_24a82b5b_adjacent_s02_s03_transfer_guard.py --config configs/g4_05d_1783775641_21314_24a82b5b_adjacent_s02_s03_transfer_guard.yaml
```

Artifacts include `result.json`, `manifest.json`, `REPORT.md`, `reproduction_match_table.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv.gz`, `model_cv_scan.csv`, `leakage_checks.csv`, `run_shift_summary.csv`, `feature_manifest.csv`, `input_sha256.csv`, and figures.
