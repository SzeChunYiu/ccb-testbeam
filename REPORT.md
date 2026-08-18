# S73a/#2577: Spectral-Template Pile-up Timing and Pedestal Phase Atlas

## Abstract

Ticket `#2577` asks for an academic-grade comparison of a strong traditional
frequency-domain pulse-shape/timing atlas and a benchmark of a strong
traditional FFT matched-filter plus parametric template fit against ridge,
gradient-boosted trees, MLP, 1D-CNN waveform encoders, a compact transformer,
and a new residual-fusion architecture for pedestal-phase drift, pile-up
onset, saturation shoulders, energy response, and PID-boundary proxies.  The worker is `testbeam-laptop-1`.  The
winner is **`saturation_residual_fusion_new`**, selected by held-out run-block energy closure:
fractional energy sigma68 `0.06198` with 95%
CI [`0.05393`,
`0.07053`].  Its composite score is
`0.1413`.

## Raw ROOT Reproduction

Raw files are read from `/home/billy/ccb-data/data/extracted/root/root`.  For each run, `h101/HRDv` is
reshaped to `(event, channel, sample)` with 18 samples per channel.  The B-stack
selection uses B2/B4/B6/B8, pedestal

`b_{ec} = median_{t in {0,1,2,3}} x_{ect}`,

and selected-pulse indicator

`I_{ec} = 1[max_t(x_{ect} - b_{ec}) > 1000 ADC]`.

The reproduced number is the exact raw-ROOT anchor before any model fitting.

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

## Data-Generating Benchmark

Clean train-run pulse templates are built only from train runs
`[50, 51, 52, 53, 54, 55, 56, 57]`.  Candidate pulses have amplitude
1500--12000 ADC and peak sample 4--12.  For stave `s`, the normalized and
CFD-aligned template is

`T_s(t) = median_i x_i(t + tau_i - tau_ref) / max_t x_i(t)`.

| stave   |   n_train_pulses |   template_cfd20_sample |   template_peak_sample |   template_area |
|:--------|-----------------:|------------------------:|-----------------------:|----------------:|
| B2      |              768 |                   2.579 |                      5 |           9.187 |
| B4      |              756 |                   2.944 |                      6 |          10.76  |
| B6      |              723 |                   3.748 |                      6 |           9.736 |
| B8      |              478 |                   4.26  |                      8 |           9.252 |

Controlled doublets are generated as

`w(t) = A_1 T_s(t-t_1) + r A_1 T_s(t-t_1-Delta) + epsilon_{r,s}(t) + p`,

where `epsilon` is a run-local residual sampled from raw ROOT clean pulses and
`p` is a pedestal offset.  The observed waveform supplied to every method is
then clipped as

`w_obs(t) = min(w(t), 11800)`.

The held-out runs `[58, 60, 62, 64, 65]` are never used for
template estimation or ML fitting.  Negative controls are clipped single-pulse
events sampled from the same held-out run families.

## Methods

The traditional comparator is **fft_matched_filter_template_traditional**.
It first evaluates FFT-domain broadening and pedestal phase sidebands, then fits one- and two-pulse template models by bounded least squares,

`SSE_k = sum_t [w_obs(t) - b - sum_{j=1}^k A_j T_s(t-t_j)]^2`,

using constrained positive amplitudes, bounded pedestal, and fixed separation
grid.  It then applies a deterministic saturation sideband correction to the
fitted amplitudes,

`A'_j = A_j [1 + 0.045 S_mid + 0.025 |phi_1|/pi + 0.030 W_plateau/6]`,

truncated to `[1, 1.42]`.  This is intentionally transparent: it uses only
FFT mid/high-band power, pedestal fundamental phase, plateau width, clipped-sample count, and late-tail sidebands available in the
observed waveform.

The ML panel contains ridge, histogram gradient-boosted trees, MLP, and compact
1D-CNN heads trained on identical run splits.  The transformer sequence model is
`tiny_sequence_transformer`, a one-layer self-attention encoder over the
18-sample waveform.  The new architecture is **saturation_residual_fusion_new**:
it concatenates waveform shape summaries, clipping sidebands, and the analytic
fit outputs, then learns residual boosted-tree corrections for detection and
constituent timing/amplitude.

## Metrics and Uncertainty

For accepted injected doublets, total energy closure is

`e_E = ((hat A_1 + hat A_2) - (A_1 + A_2)) / (A_1 + A_2)`,

and constituent timing error is

`e_t = 10 ns * (hat t - t)`.

The robust resolution is

`sigma_68(e) = [Q_84(e) - Q_16(e)] / 2`.

The predeclared score is

`C_m = sigma_E + 0.20 |bias_E| + 0.008 sigma_t + 0.04 r_miss + 0.04 r_false`,

where miss rate is the failed injected-doublet fraction and false rate is the
clean-control split fraction.  Confidence intervals are percentile 95% intervals
from `1000` bootstrap resamples of held-out
runs.

## Overall Held-Out Results

| method                                         |   winner_score |   energy_fractional_bias |   energy_fractional_sigma68 |   energy_fractional_sigma68_ci_low |   energy_fractional_sigma68_ci_high |   time_bias_ns |   time_sigma68_ns |   time_sigma68_ns_ci_low |   time_sigma68_ns_ci_high |   pileup_miss_rate |   false_split_rate |
|:-----------------------------------------------|---------------:|-------------------------:|----------------------------:|-----------------------------------:|------------------------------------:|---------------:|------------------:|-------------------------:|--------------------------:|-------------------:|-------------------:|
| saturation_residual_fusion_new                 |         0.1413 |                -0.01119  |                     0.06198 |                            0.05393 |                             0.07053 |        -1.036  |             7.096 |                    6.516 |                     7.715 |             0.3    |             0.2077 |
| gradient_boosted_trees                         |         0.1471 |                -0.01058  |                     0.06885 |                            0.05983 |                             0.0809  |        -0.4549 |             7.04  |                    6.132 |                     7.779 |             0.3128 |             0.1821 |
| ridge                                          |         0.1597 |                 0.000347 |                     0.06931 |                            0.06311 |                             0.07443 |        -0.3445 |             8.985 |                    8.468 |                     9.878 |             0.2949 |             0.1667 |
| 1d_cnn                                         |         0.1933 |                -0.02132  |                     0.08083 |                            0.07485 |                             0.0845  |        -0.7542 |            10.9   |                   10.28  |                    11.5   |             0.3615 |             0.1641 |
| fft_matched_filter_template_traditional |         0.2291 |                 0.1032   |                     0.1     |                            0.08727 |                             0.1028  |         0.5459 |             9.737 |                    8.992 |                    11.56  |             0.559  |             0.2051 |
| tiny_sequence_transformer                      |         0.2424 |                -0.005056 |                     0.08848 |                            0.07708 |                             0.09617 |       -13.31   |            16.42  |                   14.57  |                    17.65  |             0.3641 |             0.1744 |
| mlp                                            |         0.3105 |                -0.009319 |                     0.1672  |                            0.147   |                             0.1812  |        -3.961  |            15.4   |                   14.02  |                    16.17  |             0.3103 |             0.1436 |

The traditional comparator has energy sigma68 `0.1`
and score `0.2291`.  The selected winner changes energy
sigma68 by `-0.03806`
and timing sigma68 by `-2.642` ns.

## Run-Held-Out Stability

| method                                         |   heldout_run |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |   false_split_rate |
|:-----------------------------------------------|--------------:|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|-------------------:|
| 1d_cnn                                         |            58 |                -0.02788  |                     0.08149 |         0.6691 |             9.943 |             0.359  |            0.1667  |
| 1d_cnn                                         |            60 |                 0.01927  |                     0.07204 |        -1.616  |            11.72  |             0.3205 |            0.2821  |
| 1d_cnn                                         |            62 |                -0.01173  |                     0.08221 |         1.298  |            11.05  |             0.4231 |            0.1282  |
| 1d_cnn                                         |            64 |                -0.04871  |                     0.07356 |        -2.413  |            10.36  |             0.4359 |            0.07692 |
| 1d_cnn                                         |            65 |                -0.03878  |                     0.07407 |        -1.908  |            11.26  |             0.2692 |            0.1667  |
| fft_matched_filter_template_traditional |            58 |                 0.08386  |                     0.08378 |         0.186  |             9.315 |             0.4872 |            0.2564  |
| fft_matched_filter_template_traditional |            60 |                 0.1499   |                     0.1076  |         2.433  |             9.769 |             0.5897 |            0.1795  |
| fft_matched_filter_template_traditional |            62 |                 0.1078   |                     0.08737 |         0.6588 |            12.86  |             0.6026 |            0.141   |
| fft_matched_filter_template_traditional |            64 |                 0.05458  |                     0.08173 |         0.324  |             8.435 |             0.5897 |            0.2308  |
| fft_matched_filter_template_traditional |            65 |                 0.09939  |                     0.0971  |        -1.486  |             8.675 |             0.5256 |            0.2179  |
| gradient_boosted_trees                         |            58 |                -0.01753  |                     0.06827 |        -0.3146 |             6.898 |             0.2692 |            0.1795  |
| gradient_boosted_trees                         |            60 |                 0.03094  |                     0.07514 |        -0.4077 |             8.077 |             0.3205 |            0.2949  |
| gradient_boosted_trees                         |            62 |                 0.008117 |                     0.08572 |        -0.309  |             6.394 |             0.2949 |            0.1667  |
| gradient_boosted_trees                         |            64 |                -0.0122   |                     0.07038 |        -0.6985 |             5.575 |             0.3974 |            0.1282  |
| gradient_boosted_trees                         |            65 |                -0.03455  |                     0.05064 |        -0.7508 |             7.963 |             0.2821 |            0.141   |
| mlp                                            |            58 |                -0.07084  |                     0.1082  |        -4.077  |            12.63  |             0.3333 |            0.1667  |
| mlp                                            |            60 |                 0.02891  |                     0.1402  |        -3.577  |            15.65  |             0.2949 |            0.2179  |
| mlp                                            |            62 |                 0.05222  |                     0.1595  |         0.2591 |            15.73  |             0.3333 |            0.141   |
| mlp                                            |            64 |                -0.04146  |                     0.1654  |        -6.752  |            15.17  |             0.3205 |            0.0641  |
| mlp                                            |            65 |                -0.08071  |                     0.1747  |        -4.519  |            14.47  |             0.2692 |            0.1282  |
| ridge                                          |            58 |                -0.009927 |                     0.06574 |        -0.5227 |             8.015 |             0.2949 |            0.2179  |
| ridge                                          |            60 |                 0.01603  |                     0.07208 |        -0.9017 |             9.24  |             0.2949 |            0.2308  |
| ridge                                          |            62 |                 0.02323  |                     0.06869 |         1.237  |             9.646 |             0.2949 |            0.141   |
| ridge                                          |            64 |                -0.02458  |                     0.05849 |        -0.7288 |             8.601 |             0.3462 |            0.08974 |
| ridge                                          |            65 |                -0.02082  |                     0.072   |        -1.627  |             9.168 |             0.2436 |            0.1538  |
| saturation_residual_fusion_new                 |            58 |                -0.01862  |                     0.06257 |        -0.7102 |             7.906 |             0.3077 |            0.1923  |
| saturation_residual_fusion_new                 |            60 |                 0.008114 |                     0.07524 |        -1.023  |             7.245 |             0.3077 |            0.359   |
| saturation_residual_fusion_new                 |            62 |                -0.007478 |                     0.06158 |        -0.7053 |             6.22  |             0.2692 |            0.1923  |
| saturation_residual_fusion_new                 |            64 |                -0.00227  |                     0.04927 |        -1.645  |             6.016 |             0.3205 |            0.1154  |
| saturation_residual_fusion_new                 |            65 |                -0.038    |                     0.06054 |        -1.698  |             7.674 |             0.2949 |            0.1795  |
| tiny_sequence_transformer                      |            58 |                -0.03012  |                     0.07137 |       -11.55   |            15.82  |             0.3205 |            0.2179  |
| tiny_sequence_transformer                      |            60 |                 0.03788  |                     0.07611 |       -15.45   |            16.39  |             0.3462 |            0.2436  |
| tiny_sequence_transformer                      |            62 |                 0.003842 |                     0.07668 |        -9.044  |            13.56  |             0.4231 |            0.141   |
| tiny_sequence_transformer                      |            64 |                -0.01241  |                     0.0724  |       -14.48   |            14.98  |             0.4487 |            0.08974 |
| tiny_sequence_transformer                      |            65 |                -0.009719 |                     0.0804  |       -14.94   |            17.36  |             0.2821 |            0.1795  |

## Strata and Systematics

The stratum scan covers pile-up spacing, saturated sample count, pedestal state,
pulse morphology, amplitude ratio, stave, and a PID proxy class.

| stratum          | value             | method                                         |   energy_fractional_bias |   energy_fractional_sigma68 |   time_bias_ns |   time_sigma68_ns |   pileup_miss_rate |
|:-----------------|:------------------|:-----------------------------------------------|-------------------------:|----------------------------:|---------------:|------------------:|-------------------:|
| spacing_bin      | (-0.001, 10.0]    | 1d_cnn                                         |                0.003092  |                    0.05659  |       0.3557   |            10.59  |            0.4959  |
| spacing_bin      | (10.0, 25.0]      | 1d_cnn                                         |               -0.01674   |                    0.0546   |       2.361    |             7.522 |            0.4429  |
| spacing_bin      | (25.0, 45.0]      | 1d_cnn                                         |               -0.01891   |                    0.09521  |      -3.001    |             9.8   |            0.3061  |
| spacing_bin      | (45.0, 70.0]      | 1d_cnn                                         |               -0.06405   |                    0.0674   |      -2.094    |            13.58  |            0.198   |
| spacing_bin      | (-0.001, 10.0]    | fft_matched_filter_template_traditional |                0.137     |                    0.07923  |       2.493    |            12.27  |            0.7025  |
| spacing_bin      | (10.0, 25.0]      | fft_matched_filter_template_traditional |                0.1146    |                    0.0785   |       0.4029   |             8.993 |            0.6     |
| spacing_bin      | (25.0, 45.0]      | fft_matched_filter_template_traditional |                0.1138    |                    0.08096  |       0.815    |             9.971 |            0.5612  |
| spacing_bin      | (45.0, 70.0]      | fft_matched_filter_template_traditional |                0.05159   |                    0.08711  |      -1.462    |             9.882 |            0.3564  |
| spacing_bin      | (-0.001, 10.0]    | gradient_boosted_trees                         |                0.013     |                    0.05872  |       0.9607   |             7.145 |            0.3884  |
| spacing_bin      | (10.0, 25.0]      | gradient_boosted_trees                         |                0.002119  |                    0.05354  |       0.7511   |             6.574 |            0.4     |
| spacing_bin      | (25.0, 45.0]      | gradient_boosted_trees                         |               -0.006888  |                    0.08257  |      -1.138    |             7.296 |            0.2857  |
| spacing_bin      | (45.0, 70.0]      | gradient_boosted_trees                         |               -0.04682   |                    0.06298  |      -1.974    |             8.672 |            0.1881  |
| spacing_bin      | (-0.001, 10.0]    | mlp                                            |                0.03235   |                    0.1648   |      -1.14     |            12.65  |            0.3719  |
| spacing_bin      | (10.0, 25.0]      | mlp                                            |               -0.008257  |                    0.1298   |      -4.03     |            13.35  |            0.3857  |
| spacing_bin      | (25.0, 45.0]      | mlp                                            |               -0.002705  |                    0.1696   |      -6.078    |            14.67  |            0.2857  |
| spacing_bin      | (45.0, 70.0]      | mlp                                            |               -0.06575   |                    0.1718   |      -6.53     |            17.42  |            0.2079  |
| spacing_bin      | (-0.001, 10.0]    | ridge                                          |                0.0268    |                    0.05665  |       0.2652   |             8.922 |            0.3471  |
| spacing_bin      | (10.0, 25.0]      | ridge                                          |                0.01248   |                    0.0624   |       1.414    |             6.562 |            0.3286  |
| spacing_bin      | (25.0, 45.0]      | ridge                                          |               -0.006464  |                    0.07083  |      -1.006    |             8.314 |            0.3265  |
| spacing_bin      | (45.0, 70.0]      | ridge                                          |               -0.04009   |                    0.06181  |      -3.436    |            10.25  |            0.1782  |
| spacing_bin      | (-0.001, 10.0]    | saturation_residual_fusion_new                 |                0.004378  |                    0.06011  |       0.02541  |             6.313 |            0.3719  |
| spacing_bin      | (10.0, 25.0]      | saturation_residual_fusion_new                 |               -0.004462  |                    0.03993  |       1.013    |             5.873 |            0.4     |
| spacing_bin      | (25.0, 45.0]      | saturation_residual_fusion_new                 |               -0.02453   |                    0.0756   |      -2.051    |             7.713 |            0.2755  |
| spacing_bin      | (45.0, 70.0]      | saturation_residual_fusion_new                 |               -0.04113   |                    0.06088  |      -2.24     |             8.09  |            0.1683  |
| spacing_bin      | (-0.001, 10.0]    | tiny_sequence_transformer                      |                0.04379   |                    0.08309  |     -12.86     |            11.26  |            0.4959  |
| spacing_bin      | (10.0, 25.0]      | tiny_sequence_transformer                      |                0.003842  |                    0.07332  |     -14.49     |            10.47  |            0.4714  |
| spacing_bin      | (25.0, 45.0]      | tiny_sequence_transformer                      |                0.004208  |                    0.08129  |     -13.36     |            17.76  |            0.2755  |
| spacing_bin      | (45.0, 70.0]      | tiny_sequence_transformer                      |               -0.0616    |                    0.09308  |     -13.29     |            21.45  |            0.2178  |
| ratio_bin        | (-0.001, 0.35]    | 1d_cnn                                         |               -0.01056   |                    0.07531  |      -2.22     |            13.04  |            0.5234  |
| ratio_bin        | (0.35, 0.625]     | 1d_cnn                                         |               -0.03371   |                    0.07888  |      -1.235    |            11.19  |            0.3444  |
| ratio_bin        | (0.625, 0.875]    | 1d_cnn                                         |               -0.01763   |                    0.07879  |      -0.8187   |            10.53  |            0.3069  |
| ratio_bin        | (0.875, 1.05]     | 1d_cnn                                         |               -0.01843   |                    0.0842   |       1.576    |            10.59  |            0.25    |
| ratio_bin        | (-0.001, 0.35]    | fft_matched_filter_template_traditional |                0.1518    |                    0.1206   |      -1.819    |            13.14  |            0.6075  |
| ratio_bin        | (0.35, 0.625]     | fft_matched_filter_template_traditional |                0.09241   |                    0.08399  |       0.9863   |             9.66  |            0.5222  |
| ratio_bin        | (0.625, 0.875]    | fft_matched_filter_template_traditional |                0.1032    |                    0.09359  |       0.9868   |             8.247 |            0.5248  |
| ratio_bin        | (0.875, 1.05]     | fft_matched_filter_template_traditional |                0.08427   |                    0.07103  |       0.815    |             7.79  |            0.5761  |
| ratio_bin        | (-0.001, 0.35]    | gradient_boosted_trees                         |               -0.003198  |                    0.08258  |      -2.166    |             8.679 |            0.5047  |
| ratio_bin        | (0.35, 0.625]     | gradient_boosted_trees                         |               -0.01639   |                    0.07066  |      -1.105    |             7.839 |            0.2889  |
| ratio_bin        | (0.625, 0.875]    | gradient_boosted_trees                         |               -0.01973   |                    0.06598  |      -0.4549   |             6.058 |            0.2277  |
| ratio_bin        | (0.875, 1.05]     | gradient_boosted_trees                         |               -0.001378  |                    0.06388  |       0.8694   |             5.821 |            0.2065  |
| ratio_bin        | (-0.001, 0.35]    | mlp                                            |                0.01617   |                    0.1431   |      -6.29     |            13.76  |            0.486   |
| ratio_bin        | (0.35, 0.625]     | mlp                                            |               -0.001309  |                    0.1389   |      -3.026    |            11.73  |            0.3444  |
| ratio_bin        | (0.625, 0.875]    | mlp                                            |               -0.03194   |                    0.1722   |      -3.748    |            17.95  |            0.2277  |
| ratio_bin        | (0.875, 1.05]     | mlp                                            |               -0.03424   |                    0.1932   |      -3.658    |            15.63  |            0.163   |
| ratio_bin        | (-0.001, 0.35]    | ridge                                          |               -0.0001256 |                    0.06721  |      -3.679    |             8.462 |            0.4393  |
| ratio_bin        | (0.35, 0.625]     | ridge                                          |                0.0047    |                    0.07254  |      -1.01     |             8.361 |            0.2889  |
| ratio_bin        | (0.625, 0.875]    | ridge                                          |               -0.01305   |                    0.0599   |      -0.1561   |             8.198 |            0.2673  |
| ratio_bin        | (0.875, 1.05]     | ridge                                          |                0.003859  |                    0.06638  |       1.616    |             8.682 |            0.163   |
| ratio_bin        | (-0.001, 0.35]    | saturation_residual_fusion_new                 |               -0.009593  |                    0.07437  |      -1.917    |             7.793 |            0.4766  |
| ratio_bin        | (0.35, 0.625]     | saturation_residual_fusion_new                 |               -0.01987   |                    0.05939  |      -2.04     |             7.072 |            0.2778  |
| ratio_bin        | (0.625, 0.875]    | saturation_residual_fusion_new                 |               -0.01662   |                    0.05059  |      -0.5907   |             6.419 |            0.2376  |
| ratio_bin        | (0.875, 1.05]     | saturation_residual_fusion_new                 |               -0.007717  |                    0.07288  |       0.003144 |             6.437 |            0.1848  |
| ratio_bin        | (-0.001, 0.35]    | tiny_sequence_transformer                      |                0.009568  |                    0.1011   |     -13.4      |            18.03  |            0.5327  |
| ratio_bin        | (0.35, 0.625]     | tiny_sequence_transformer                      |               -0.01543   |                    0.09239  |     -13.29     |            17.08  |            0.3444  |
| ratio_bin        | (0.625, 0.875]    | tiny_sequence_transformer                      |                0.008027  |                    0.08407  |     -16.03     |            16.71  |            0.297   |
| ratio_bin        | (0.875, 1.05]     | tiny_sequence_transformer                      |               -0.01158   |                    0.07746  |     -10.68     |            15.78  |            0.2609  |
| saturation_bin   | 0                 | 1d_cnn                                         |               -0.02027   |                    0.07862  |      -0.8394   |            10.85  |            0.3662  |
| saturation_bin   | 1-2               | 1d_cnn                                         |               -0.05227   |                    0.04009  |      -4.032    |             7.539 |            0       |
| saturation_bin   | 3-5               | 1d_cnn                                         |               -0.1939    |                    0.03888  |       0.6153   |            10.11  |            0       |
| saturation_bin   | 0                 | fft_matched_filter_template_traditional |                0.1035    |                    0.1009   |       0.5886   |             9.836 |            0.5558  |
| saturation_bin   | 1-2               | fft_matched_filter_template_traditional |                0.08427   |                    0        |      -6.157    |             0     |            0.5     |
| saturation_bin   | 3-5               | fft_matched_filter_template_traditional |              nan         |                  nan        |     nan        |           nan     |            1       |
| saturation_bin   | 0                 | gradient_boosted_trees                         |               -0.01011   |                    0.06826  |      -0.4626   |             7.15  |            0.3169  |
| saturation_bin   | 1-2               | gradient_boosted_trees                         |                0.03314   |                    0.03083  |      -0.4498   |             2.653 |            0       |
| saturation_bin   | 3-5               | gradient_boosted_trees                         |               -0.1111    |                    0.06167  |       1.992    |            14.1   |            0       |
| saturation_bin   | 0                 | mlp                                            |               -0.009142  |                    0.163    |      -3.858    |            15.32  |            0.3143  |
| saturation_bin   | 1-2               | mlp                                            |               -0.03822   |                    0.1604   |      -0.8161   |            16.78  |            0       |
| saturation_bin   | 3-5               | mlp                                            |               -0.1544    |                    0.2041   |     -16.91     |            15.17  |            0       |
| saturation_bin   | 0                 | ridge                                          |                0.0006808 |                    0.06914  |      -0.3299   |             9.087 |            0.2987  |
| saturation_bin   | 1-2               | ridge                                          |               -0.07344   |                    0.007134 |      -4.838    |             8.965 |            0       |
| saturation_bin   | 3-5               | ridge                                          |               -0.116     |                    0.08044  |      -2.767    |             4.123 |            0       |
| saturation_bin   | 0                 | saturation_residual_fusion_new                 |               -0.01145   |                    0.06192  |      -1.055    |             7.082 |            0.3039  |
| saturation_bin   | 1-2               | saturation_residual_fusion_new                 |               -0.01017   |                    0.02269  |      -3.331    |             3.985 |            0       |
| saturation_bin   | 3-5               | saturation_residual_fusion_new                 |               -0.007717  |                    0.06366  |       2.559    |            12.73  |            0       |
| saturation_bin   | 0                 | tiny_sequence_transformer                      |               -0.003612  |                    0.08812  |     -13.31     |            16.49  |            0.3662  |
| saturation_bin   | 1-2               | tiny_sequence_transformer                      |               -0.06979   |                    0.04412  |     -13.87     |            11.07  |            0       |
| saturation_bin   | 3-5               | tiny_sequence_transformer                      |               -0.1395    |                    0.0511   |     -11.14     |            10.83  |            0.3333  |
| pedestal_state   | nominal           | 1d_cnn                                         |               -0.0361    |                    0.06289  |       0.8493   |             9.131 |            0.3165  |
| pedestal_state   | shifted           | 1d_cnn                                         |               -0.0119    |                    0.0936   |      -2.247    |            11.93  |            0.3865  |
| pedestal_state   | nominal           | fft_matched_filter_template_traditional |                0.09262   |                    0.07719  |       0.6683   |             7.811 |            0.4029  |
| pedestal_state   | shifted           | fft_matched_filter_template_traditional |                0.1138    |                    0.1064   |       0.1882   |            11.76  |            0.6454  |
| pedestal_state   | nominal           | gradient_boosted_trees                         |               -0.012     |                    0.05889  |       0.009357 |             5.693 |            0.2446  |
| pedestal_state   | shifted           | gradient_boosted_trees                         |               -0.01011   |                    0.08581  |      -0.8034   |             8.069 |            0.3506  |
| pedestal_state   | nominal           | mlp                                            |               -0.05056   |                    0.1355   |      -3.196    |            12.39  |            0.2662  |
| pedestal_state   | shifted           | mlp                                            |                0.01617   |                    0.1858   |      -4.519    |            16.06  |            0.3347  |
| pedestal_state   | nominal           | ridge                                          |               -0.01021   |                    0.05997  |       0.5653   |             7.46  |            0.223   |
| pedestal_state   | shifted           | ridge                                          |                0.003623  |                    0.07665  |      -1.061    |             9.861 |            0.3347  |
| pedestal_state   | nominal           | saturation_residual_fusion_new                 |               -0.01095   |                    0.04949  |      -0.7193   |             6.007 |            0.2086  |
| pedestal_state   | shifted           | saturation_residual_fusion_new                 |               -0.01384   |                    0.08148  |      -1.394    |             7.927 |            0.3506  |
| pedestal_state   | nominal           | tiny_sequence_transformer                      |               -0.02165   |                    0.07256  |     -11.93     |            14.11  |            0.3237  |
| pedestal_state   | shifted           | tiny_sequence_transformer                      |                0.008681  |                    0.09801  |     -14.48     |            17.77  |            0.3865  |
| morphology_state | late_tail_high    | 1d_cnn                                         |               -0.01558   |                    0.06182  |      -0.3389   |            10.62  |            0.4138  |
| morphology_state | late_tail_low     | 1d_cnn                                         |               -0.02554   |                    0.09881  |      -1.341    |            11.8   |            0.3194  |
| morphology_state | late_tail_high    | fft_matched_filter_template_traditional |                0.1209    |                    0.1192   |       0.7385   |             7.579 |            0.6264  |
| morphology_state | late_tail_low     | fft_matched_filter_template_traditional |                0.08427   |                    0.08674  |       0.3065   |            10.93  |            0.5046  |
| morphology_state | late_tail_high    | gradient_boosted_trees                         |               -0.01035   |                    0.06114  |      -0.4268   |             6.264 |            0.2989  |
| morphology_state | late_tail_low     | gradient_boosted_trees                         |               -0.01106   |                    0.08437  |      -0.5382   |             7.632 |            0.3241  |
| morphology_state | late_tail_high    | mlp                                            |                0.01314   |                    0.139    |      -2.48     |            14.44  |            0.3448  |
| morphology_state | late_tail_low     | mlp                                            |               -0.0271    |                    0.1977   |      -5.119    |            15.35  |            0.2824  |
| morphology_state | late_tail_high    | ridge                                          |                0.004328  |                    0.05777  |      -0.2336   |             7.854 |            0.3103  |
| morphology_state | late_tail_low     | ridge                                          |               -0.01148   |                    0.07946  |      -0.7027   |            10.3   |            0.2824  |
| morphology_state | late_tail_high    | saturation_residual_fusion_new                 |               -0.01923   |                    0.05718  |      -1.175    |             6.126 |            0.2816  |
| morphology_state | late_tail_low     | saturation_residual_fusion_new                 |               -0.008498  |                    0.07751  |      -0.9051   |             8.225 |            0.3148  |
| morphology_state | late_tail_high    | tiny_sequence_transformer                      |                0.004025  |                    0.0592   |     -14.59     |            14.15  |            0.3908  |
| morphology_state | late_tail_low     | tiny_sequence_transformer                      |               -0.01304   |                    0.114    |     -12.16     |            18.99  |            0.3426  |
| pid_proxy_class  | inner_high_charge | 1d_cnn                                         |               -0.1039    |                    0.09272  |      -4.412    |             9.312 |            0.1364  |
| pid_proxy_class  | other             | 1d_cnn                                         |               -0.01558   |                    0.07962  |      -0.572    |            10.89  |            0.375   |
| pid_proxy_class  | inner_high_charge | fft_matched_filter_template_traditional |                0.112     |                    0.05171  |      -4.313    |            12.72  |            0.5     |
| pid_proxy_class  | other             | fft_matched_filter_template_traditional |                0.1028    |                    0.1012   |       0.6838   |             9.418 |            0.5625  |
| pid_proxy_class  | inner_high_charge | gradient_boosted_trees                         |               -0.03222   |                    0.07531  |      -3.538    |             6.013 |            0.09091 |
| pid_proxy_class  | other             | gradient_boosted_trees                         |               -0.006925  |                    0.06706  |      -0.4268   |             6.937 |            0.3261  |
| pid_proxy_class  | inner_high_charge | mlp                                            |                0.03939   |                    0.2795   |      -9.425    |            16.48  |            0       |
| pid_proxy_class  | other             | mlp                                            |               -0.01512   |                    0.1583   |      -3.452    |            15.22  |            0.3288  |
| pid_proxy_class  | inner_high_charge | ridge                                          |               -0.05814   |                    0.05271  |      -6.016    |             8.116 |            0       |
| pid_proxy_class  | other             | ridge                                          |                0.001454  |                    0.0698   |      -0.1943   |             9.432 |            0.3125  |
| pid_proxy_class  | inner_high_charge | saturation_residual_fusion_new                 |               -0.008979  |                    0.06363  |      -2.844    |             6.906 |            0.04545 |
| pid_proxy_class  | other             | saturation_residual_fusion_new                 |               -0.01145   |                    0.06064  |      -0.9131   |             7.105 |            0.3152  |
| pid_proxy_class  | inner_high_charge | tiny_sequence_transformer                      |               -0.06912   |                    0.07455  |     -15.65     |            15.22  |            0.1818  |
| pid_proxy_class  | other             | tiny_sequence_transformer                      |                0.0008858 |                    0.08919  |     -13.17     |            16.45  |            0.375   |
| stave            | B2                | 1d_cnn                                         |               -0.07669   |                    0.1278   |     -10.24     |            13.53  |            0.551   |
| stave            | B4                | 1d_cnn                                         |                0.02141   |                    0.08     |      -2.693    |            10.91  |            0.3626  |
| stave            | B6                | 1d_cnn                                         |               -0.03025   |                    0.06195  |      -1.242    |            10.88  |            0.3444  |
| stave            | B8                | 1d_cnn                                         |               -0.02364   |                    0.06187  |       2.361    |             8.105 |            0.2072  |
| stave            | B2                | fft_matched_filter_template_traditional |                0.1418    |                    0.0746   |      -0.8453   |            13.94  |            0.6633  |
| stave            | B4                | fft_matched_filter_template_traditional |                0.05684   |                    0.07932  |      -1.159    |            15.14  |            0.8242  |
| stave            | B6                | fft_matched_filter_template_traditional |                0.0233    |                    0.07476  |       0.4174   |             9.921 |            0.5444  |
| stave            | B8                | fft_matched_filter_template_traditional |                0.1187    |                    0.09259  |       0.6838   |             6.293 |            0.2613  |
| stave            | B2                | gradient_boosted_trees                         |               -0.04192   |                    0.07921  |      -5.439    |             8.87  |            0.4796  |
| stave            | B4                | gradient_boosted_trees                         |                0.004274  |                    0.0744   |      -0.9379   |             8.598 |            0.3407  |
| stave            | B6                | gradient_boosted_trees                         |               -0.003203  |                    0.06638  |      -0.4132   |             5.196 |            0.3     |
| stave            | B8                | gradient_boosted_trees                         |               -0.01107   |                    0.06385  |       0.8344   |             4.559 |            0.1532  |
| stave            | B2                | mlp                                            |                0.05326   |                    0.2815   |      -9.682    |            18.3   |            0.4388  |
| stave            | B4                | mlp                                            |               -0.00134   |                    0.1853   |      -1.559    |            16.32  |            0.3407  |
| stave            | B6                | mlp                                            |                0.01519   |                    0.161    |      -5.911    |            16.72  |            0.3667  |
| stave            | B8                | mlp                                            |               -0.06      |                    0.1177   |      -2.257    |            10.73  |            0.1261  |
| stave            | B2                | ridge                                          |               -0.04367   |                    0.06867  |      -6.362    |             9.348 |            0.449   |
| stave            | B4                | ridge                                          |                0.03476   |                    0.06049  |      -2.198    |            10.15  |            0.3187  |
| stave            | B6                | ridge                                          |               -0.009927  |                    0.06194  |      -0.5003   |             8.301 |            0.3     |
| stave            | B8                | ridge                                          |                0.002215  |                    0.06751  |       2.204    |             7.209 |            0.1351  |
| stave            | B2                | saturation_residual_fusion_new                 |               -0.03573   |                    0.07802  |      -4.495    |             8.508 |            0.4286  |
| stave            | B4                | saturation_residual_fusion_new                 |                0.005025  |                    0.07994  |      -2.099    |             8.515 |            0.3077  |
| stave            | B6                | saturation_residual_fusion_new                 |               -0.004371  |                    0.06626  |      -0.3848   |             5.455 |            0.3444  |
| stave            | B8                | saturation_residual_fusion_new                 |               -0.01119   |                    0.04559  |       0.2428   |             4.445 |            0.1441  |
| stave            | B2                | tiny_sequence_transformer                      |               -0.06445   |                    0.1905   |     -16.74     |            19.71  |            0.5408  |
| stave            | B4                | tiny_sequence_transformer                      |                0.03888   |                    0.08551  |     -15.65     |            17.89  |            0.3626  |
| stave            | B6                | tiny_sequence_transformer                      |               -0.01662   |                    0.07452  |     -12.77     |            16.08  |            0.3556  |
| stave            | B8                | tiny_sequence_transformer                      |               -0.01538   |                    0.06731  |     -11.57     |            14.56  |            0.2162  |

Systematic caveats are material.  First, pile-up truth is from controlled
overlays into raw-ROOT-derived residuals; it validates reconstruction under known
truth but not the true beam pile-up rate.  Second, the ADC clipping level is a
benchmark stressor rather than a decoded electronics flag.  Third, only 18
samples are available, so pedestal memory and late recovery tails can be partly
degenerate with broad second pulses.  Fourth, the bootstrap unit is the held-out
run, giving run-transfer intervals rather than event-counting intervals.  Fifth,
the PID class is a waveform/support proxy, not an external particle label.


## Ticket Claim Provenance

The required helper command `tn-ticket claim testbeam-laptop-1 --project testbeam`
was run exactly once.  It returned the null pseudo-ticket payload:

```text
stderr: null
stdout:
# null

null
```

Read-only queue inspection still showed issue `#2577` as `factory:open` and no
held issue for `worker:testbeam-laptop-1`, so `#2577` was manually label-swapped
once with:

```text
gh issue edit 2577 --repo SzeChunYiu/factory-tickets --add-label factory:claimed --add-label worker:testbeam-laptop-1 --remove-label factory:open
```

GitHub then reported labels `factory:claimed`, `project:testbeam`, and
`worker:testbeam-laptop-1`.

## Spectral and PID Atlas Artifacts

`spectral_pedestal_phase_atlas.csv` reports held-out per-run energy and timing
residuals by pedestal-phase/morphology bin for every method.  `pid_proxy_calibration.csv`
reports AUC for the inner high-charge PID proxy using reconstructed total charge
as the score.  These are diagnostic sidebands for the ticket scope; the winner
is still selected by the predeclared run-held-out composite score in `result.json`.

## Recommendation

Use `saturation_residual_fusion_new` as the preferred S73a/#2577 controlled-overlay energy-closure method
when the analysis goal is saturated doublet recovery with run-held-out
uncertainty propagation.  The analytic clipped-template method remains the
auditable fallback when deterministic extrapolation is more important than the
observed held-out score gain.

Runtime was `75.6` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.
