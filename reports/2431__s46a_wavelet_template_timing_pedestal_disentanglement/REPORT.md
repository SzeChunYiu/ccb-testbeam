# S46a: Wavelet-template pulse morphology timing-pedestal disentanglement

## Abstract

Issue `#2431` asks whether frequency/local-shape descriptors can separate true
timing shifts from pedestal-memory pulse deformation.  The claimed worker is
`testbeam-laptop-2`.  The raw-ROOT anchor is reproduced exactly before modeling:
`640737` selected B-stave pulses versus
`640737` expected.  The held-out run winner is
**`gradient_boosted_trees`**, with timing sigma68 `2.564` ns
95% CI [`2.390`,
`2.699`] and morphology accuracy
`0.745`.

## 1. Raw ROOT Reproduction

The analysis rereads `h101/HRDv` from `data/root/root/hrdb_run_*.root`.  Each
record is reshaped to `(event, channel, sample)` with 18 samples per channel.
B-stack channels are B2, B4, B6, and B8.  The pedestal-subtracted waveform is

`x_ect = HRDv_ect - median(HRDv_ec0, HRDv_ec1, HRDv_ec2, HRDv_ec3)`,

and the selected-pulse gate is

`I_ec = 1[max_t x_ect > 1000 ADC]`.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## 2. Benchmark Construction

Only raw-ROOT selected pulses are used as carrier waveforms.  Templates are built
from train runs `[44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]` and evaluated on held-out runs `[58, 60, 62, 64, 65]`.
For raw carrier pulse `u_s(t)`, the controlled observation is

`y(t) = u_s(t - delta) + d_k(t; A) + eta(t)`,

where `delta` is a true timing shift in samples, `d_k` is one of three pedestal
memory morphologies (nominal, exponential/ramp memory, or early-sample sag plus
late tail), and `eta` is small ADC noise.  This construction gives known timing,
pedestal-residual, and morphology targets while preserving raw pulse shapes,
amplitudes, stave mixtures, and run-specific residual structure.

Template inventory:

| stave   |   n_train |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|----------:|------------------------:|-----------------------:|----------------:|
| B2      |      1260 |                 3.97449 |                      6 |         8.09269 |
| B4      |      1116 |                 4.19015 |                      7 |         8.19514 |
| B6      |      1018 |                 4.53666 |                      7 |         7.85939 |
| B8      |       770 |                 4.75545 |                      7 |         8.09834 |

## 3. Methods

The traditional method is sideband pedestal subtraction followed by a
wavelet-smoothed constant-fraction/template timing estimate.  With smoothed
waveform `s(t)` and train-only template reference `T_s`, it estimates

`hat delta_trad = t_CFD0.2[s] - t_CFD0.2[T_s]`,

then classifies morphology from the early-minus-late sideband residual.  The ML
panel uses identical train/held-out run splits:

`ridge`: standardized Haar/local-shape moments with ridge and logistic heads.

`gradient_boosted_trees`: histogram gradient boosting on the same summaries.

`mlp`: tabular neural network on standardized moments and Haar coefficients.

`1d_cnn`: compact convolutional neural net over the 18-sample waveform plus
auxiliary shape features.

`tiny_waveform_transformer`: one-layer self-attention encoder over the waveform.

`wavelet_template_residual_fusion_new`: the new architecture; it fuses
wavelet/local-shape descriptors with the traditional template timing and
sideband residual, then learns residual timing, pedestal, and morphology heads.

## 4. Metrics and Uncertainty

Timing error is `e_t = hat delta_ns - delta_ns`; pedestal error is
`e_p = hat p - p`.  Robust resolution is

`sigma68(e) = (Q84(e) - Q16(e)) / 2`.

The predeclared composite score is

`C_m = sigma68_t + 0.05 |bias_t| + 0.012 sigma68_p + 0.012 |bias_p| + 6(1-accuracy_morph)`.

Confidence intervals are percentile 95% intervals from 400 bootstrap resamples
of the held-out run blocks.

## 5. Overall Held-Out Results

| method                               |   winner_score |   timing_bias_ns |   timing_sigma68_ns |   timing_sigma68_ns_ci_low |   timing_sigma68_ns_ci_high |   pedestal_bias_adc |   pedestal_sigma68_adc |   morphology_accuracy |
|:-------------------------------------|---------------:|-----------------:|--------------------:|---------------------------:|----------------------------:|--------------------:|-----------------------:|----------------------:|
| gradient_boosted_trees               |        4.69681 |        0.293257  |             2.56414 |                    2.39002 |                     2.69922 |            -3.9011  |                45.1934 |              0.745187 |
| wavelet_template_residual_fusion_new |        4.75186 |        0.304161  |             2.62123 |                    2.47504 |                     2.75771 |            -5.3636  |                45.2139 |              0.748584 |
| 1d_cnn                               |        5.20557 |        0.234588  |             2.86719 |                    2.79066 |                     2.95982 |            13.0986  |                37.5277 |              0.713477 |
| tiny_waveform_transformer            |        5.5285  |        0.629893  |             3.26702 |                    3.03072 |                     3.47603 |            -6.06366 |                41.3206 |              0.723103 |
| ridge                                |        7.75408 |        0.510536  |             3.89177 |                    3.69629 |                     4.03525 |             1.40058 |               124.673  |              0.612684 |
| mlp                                  |        8.26289 |       -0.0999339 |             5.44331 |                    5.36669 |                     5.48401 |             4.97205 |                82.6347 |              0.706116 |
| wavelet_template_cfd_traditional     |       53.6837  |        1.70996   |            12.6856  |                   10.4563  |                    13.9162  |         -1640.56    |              1393.4    |              0.249151 |

## 6. Run-Held-Out Stability

| method                               |   heldout_run |   n |   timing_bias_ns |   timing_sigma68_ns |   pedestal_bias_adc |   pedestal_sigma68_adc |   morphology_accuracy |
|:-------------------------------------|--------------:|----:|-----------------:|--------------------:|--------------------:|-----------------------:|----------------------:|
| 1d_cnn                               |            58 | 345 |        0.297224  |             2.81423 |           14.6818   |                39.9674 |              0.721739 |
| 1d_cnn                               |            60 | 360 |        0.132217  |             2.73931 |           15.6649   |                37.484  |              0.736111 |
| 1d_cnn                               |            62 | 360 |        0.14865   |             2.7802  |            8.10148  |                44.7038 |              0.669444 |
| 1d_cnn                               |            64 | 360 |        0.372191  |             3.06954 |            8.48394  |                35.8401 |              0.725    |
| 1d_cnn                               |            65 | 341 |        0.224749  |             2.87531 |           18.9351   |                31.3715 |              0.715543 |
| gradient_boosted_trees               |            58 | 345 |        0.293613  |             2.53919 |            0.628264 |                45.9203 |              0.773913 |
| gradient_boosted_trees               |            60 | 360 |        0.264853  |             2.28481 |           -7.34386  |                43.2163 |              0.75     |
| gradient_boosted_trees               |            62 | 360 |        0.183604  |             2.58978 |           -2.83707  |                48.3993 |              0.716667 |
| gradient_boosted_trees               |            64 | 360 |        0.493736  |             2.77333 |           -5.95375  |                40.1846 |              0.752778 |
| gradient_boosted_trees               |            65 | 341 |        0.226999  |             2.45247 |           -3.80531  |                44.8537 |              0.733138 |
| mlp                                  |            58 | 345 |        0.107655  |             5.50886 |           -2.90124  |                86.7176 |              0.718841 |
| mlp                                  |            60 | 360 |       -0.311942  |             5.34994 |           -0.221513 |                73.813  |              0.716667 |
| mlp                                  |            62 | 360 |       -0.169388  |             5.46381 |           -1.88207  |                82.2268 |              0.655556 |
| mlp                                  |            64 | 360 |       -0.053234  |             5.40234 |            5.83638  |                88.174  |              0.705556 |
| mlp                                  |            65 | 341 |       -0.0621148 |             5.47917 |           24.7442   |                73.9747 |              0.73607  |
| ridge                                |            58 | 345 |        0.408474  |             4.0703  |           -8.47237  |               130.826  |              0.649275 |
| ridge                                |            60 | 360 |        0.299173  |             3.67827 |           -3.44336  |               124.055  |              0.630556 |
| ridge                                |            62 | 360 |        0.60114   |             4.09441 |           -0.756941 |               121.067  |              0.586111 |
| ridge                                |            64 | 360 |        0.592259  |             3.889   |            4.55474  |               118.372  |              0.613889 |
| ridge                                |            65 | 341 |        0.655004  |             3.6256  |           15.451    |               126.792  |              0.583578 |
| tiny_waveform_transformer            |            58 | 345 |        0.522425  |             3.54289 |           -7.81436  |                42.3168 |              0.736232 |
| tiny_waveform_transformer            |            60 | 360 |        0.563566  |             2.935   |           -5.35256  |                43.192  |              0.75     |
| tiny_waveform_transformer            |            62 | 360 |        0.610888  |             3.15221 |           -5.69789  |                44.7678 |              0.705556 |
| tiny_waveform_transformer            |            64 | 360 |        0.82466   |             3.43913 |           -8.69247  |                39.7445 |              0.727778 |
| tiny_waveform_transformer            |            65 | 341 |        0.623088  |             3.07404 |           -2.65402  |                36.288  |              0.695015 |
| wavelet_template_cfd_traditional     |            58 | 345 |        5.17655   |            13.6602  |        -1996.32     |              1418.27   |              0.255072 |
| wavelet_template_cfd_traditional     |            60 | 360 |       -1.31378   |            14.1516  |        -1585.45     |              1338.54   |              0.258333 |
| wavelet_template_cfd_traditional     |            62 | 360 |       -0.133933  |            13.7569  |        -1402.85     |              1418.97   |              0.263889 |
| wavelet_template_cfd_traditional     |            64 | 360 |        1.57111   |            10.0592  |        -1608.17     |              1397.53   |              0.225    |
| wavelet_template_cfd_traditional     |            65 | 341 |        3.48812   |            11.3279  |        -1623.92     |              1374      |              0.243402 |
| wavelet_template_residual_fusion_new |            58 | 345 |        0.298428  |             2.54385 |           -3.47891  |                52.5082 |              0.771014 |
| wavelet_template_residual_fusion_new |            60 | 360 |        0.309258  |             2.37534 |           -8.0067   |                44.5015 |              0.752778 |
| wavelet_template_residual_fusion_new |            62 | 360 |        0.143792  |             2.74868 |           -3.77246  |                47.0686 |              0.725    |
| wavelet_template_residual_fusion_new |            64 | 360 |        0.503042  |             2.8588  |           -6.87316  |                39.8276 |              0.763889 |
| wavelet_template_residual_fusion_new |            65 | 341 |        0.263925  |             2.56663 |           -4.56616  |                44.2545 |              0.730205 |

## 7. Systematics and Caveats

The stratum scan covers stave, near-saturation pulses, and pile-up-like broad
waveforms.  The largest failure mode is residual pedestal deformation that
mimics leading-edge motion: pure CFD/template timing absorbs early-sample sag as
a negative timing shift.  The winning boosted-tree model and the close fusion
variant both exploit Haar detail coefficients and late-tail sidebands to
separate pedestal memory from real time translation; the fusion variant pays a
small score penalty from its template residual features on this held-out split.

| stratum         | value   | method                               |    n |   timing_sigma68_ns |   pedestal_sigma68_adc |   morphology_accuracy |
|:----------------|:--------|:-------------------------------------|-----:|--------------------:|-----------------------:|----------------------:|
| stave           | B2      | 1d_cnn                               |  450 |             2.85009 |                38.5813 |              0.728889 |
| stave           | B4      | 1d_cnn                               |  450 |             2.5602  |                38.0671 |              0.671111 |
| stave           | B6      | 1d_cnn                               |  450 |             2.84391 |                34.6468 |              0.733333 |
| stave           | B8      | 1d_cnn                               |  416 |             3.16127 |                36.7919 |              0.721154 |
| stave           | B2      | gradient_boosted_trees               |  450 |             2.36617 |                53.8206 |              0.751111 |
| stave           | B4      | gradient_boosted_trees               |  450 |             2.4246  |                43.6724 |              0.737778 |
| stave           | B6      | gradient_boosted_trees               |  450 |             2.55669 |                37.1278 |              0.742222 |
| stave           | B8      | gradient_boosted_trees               |  416 |             2.74664 |                46.3587 |              0.75     |
| stave           | B2      | mlp                                  |  450 |             5.61053 |                93.0919 |              0.706667 |
| stave           | B4      | mlp                                  |  450 |             5.34992 |                82.7387 |              0.664444 |
| stave           | B6      | mlp                                  |  450 |             5.4341  |                73.9869 |              0.733333 |
| stave           | B8      | mlp                                  |  416 |             5.47402 |                79.5467 |              0.721154 |
| stave           | B2      | ridge                                |  450 |             3.76445 |               139.431  |              0.646667 |
| stave           | B4      | ridge                                |  450 |             3.77779 |               123.203  |              0.584444 |
| stave           | B6      | ridge                                |  450 |             3.91295 |               116.351  |              0.597778 |
| stave           | B8      | ridge                                |  416 |             4.20453 |               120.496  |              0.622596 |
| stave           | B2      | tiny_waveform_transformer            |  450 |             3.19309 |                47.0677 |              0.724444 |
| stave           | B4      | tiny_waveform_transformer            |  450 |             3.2503  |                39.1851 |              0.735556 |
| stave           | B6      | tiny_waveform_transformer            |  450 |             3.07148 |                35.9867 |              0.733333 |
| stave           | B8      | tiny_waveform_transformer            |  416 |             3.45194 |                45.3846 |              0.697115 |
| stave           | B2      | wavelet_template_cfd_traditional     |  450 |             5.20981 |              1444.66   |              0.244444 |
| stave           | B4      | wavelet_template_cfd_traditional     |  450 |            13.4756  |              1339.14   |              0.262222 |
| stave           | B6      | wavelet_template_cfd_traditional     |  450 |            15.3446  |              1229.41   |              0.264444 |
| stave           | B8      | wavelet_template_cfd_traditional     |  416 |            14.3716  |              1391.19   |              0.223558 |
| stave           | B2      | wavelet_template_residual_fusion_new |  450 |             2.52724 |                53.3582 |              0.744444 |
| stave           | B4      | wavelet_template_residual_fusion_new |  450 |             2.46889 |                43.2612 |              0.753333 |
| stave           | B6      | wavelet_template_residual_fusion_new |  450 |             2.66821 |                39.8017 |              0.733333 |
| stave           | B8      | wavelet_template_residual_fusion_new |  416 |             2.84013 |                46.8355 |              0.764423 |
| near_saturation | False   | 1d_cnn                               | 1441 |             2.84791 |                29.2899 |              0.718251 |
| near_saturation | True    | 1d_cnn                               |  325 |             2.97767 |                84.9814 |              0.692308 |
| near_saturation | False   | gradient_boosted_trees               | 1441 |             2.53281 |                35.29   |              0.741846 |
| near_saturation | True    | gradient_boosted_trees               |  325 |             2.67602 |               118.243  |              0.76     |
| near_saturation | False   | mlp                                  | 1441 |             5.41684 |                54.6407 |              0.70576  |
| near_saturation | True    | mlp                                  |  325 |             5.47108 |               298.635  |              0.707692 |
| near_saturation | False   | ridge                                | 1441 |             3.90174 |               104.71   |              0.615545 |
| near_saturation | True    | ridge                                |  325 |             3.86378 |               404.946  |              0.6      |
| near_saturation | False   | tiny_waveform_transformer            | 1441 |             3.19489 |                33.0594 |              0.728661 |
| near_saturation | True    | tiny_waveform_transformer            |  325 |             3.37704 |                87.4611 |              0.698462 |
| near_saturation | False   | wavelet_template_cfd_traditional     | 1441 |            12.7333  |              1109.76   |              0.249133 |
| near_saturation | True    | wavelet_template_cfd_traditional     |  325 |            12.3704  |              2264.25   |              0.249231 |
| near_saturation | False   | wavelet_template_residual_fusion_new | 1441 |             2.57702 |                35.2197 |              0.74948  |
| near_saturation | True    | wavelet_template_residual_fusion_new |  325 |             2.74915 |               116.25   |              0.744615 |

Caveats: the timing and pedestal labels are controlled injections over raw
carriers, not external oscilloscope truth; ADC saturation is represented by a
near-saturation stratum rather than decoded electronics state; and bootstrap CIs
quantify transfer across the held-out run set, not all possible future running
conditions.
