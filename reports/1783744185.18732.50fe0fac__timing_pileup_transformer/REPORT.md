# Study report: timing-pileup disentanglement with waveform transformers

- **Ticket:** `1783744185.18732.50fe0fac`
- **Worker:** `testbeam-laptop-3`
- **Input raw ROOT:** `/home/billy/ccb-data/extracted/root/root`
- **Run split:** leave-one-run-out over Sample-II analysis runs `58, 59, 60, 61, 62, 63, 65`

## Abstract
This benchmark asks whether learned waveform models improve timing-pileup disentanglement over a strong traditional comparator. The raw ROOT reproduction gate reads `h101/HRDv`, subtracts the median of samples 0--3, and applies the canonical B-stave amplitude threshold `A > 1000` to even physical B channels in report-domain runs 31--65 with run 43 removed. The gate reproduces the S00 count exactly before model training. Timing is evaluated as event-internal residual correction, and pile-up is evaluated on injected two-pulse mixtures built from real selected B-stave waveforms. The named winner in `result.json` is selected by a composite rank of timing robust width and pile-up recovery.

## Raw ROOT reproduction
| quantity | report_value | reproduced | delta | pass |
| --- | --- | --- | --- | --- |
| total selected B-stave pulses | 640737 | 640737 | 0 | True |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | True |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | True |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | True |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | True |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | True |

## Methods
For an event `e` and B-stave channel `i`, the baseline-subtracted waveform is `w_{e,i,k}=HRDv_{e,i,k}-median(HRDv_{e,i,0:3})`. A selected pulse satisfies `max_k w_{e,i,k}>1000`. The timing pickoff is a CFD crossing at 30% amplitude, corrected by a fixed propagation term `x_i/v`, `v^{-1}=0.078 ns/cm`. The supervised residual target is

`r_{e,i}=t_{e,i}^{CFD30}-x_i/v-median_{j != i}(t_{e,j}^{CFD30}-x_j/v)`.

Each model predicts `hat r_{e,i}` from the same pulse waveform only, and the corrected residual is `r_{e,i}-hat r_{e,i}`. The traditional method is a regularized template/timewalk surrogate using amplitude, log-amplitude, peak phase, saturation, and channel indicators. Ridge, gradient-boosted trees, and MLP use the full handcrafted pulse descriptor plus normalized waveform samples. The 1D-CNN and compact waveform transformer consume only normalized 18-sample waveforms. Pile-up positives are formed as `w_a + alpha w_b(k-delta)` using real selected waveforms; negatives are single pulses with matched noise. The traditional two-pulse method scans separations, solves constrained non-negative template amplitudes by least squares, and scores the one-pulse versus two-pulse SSE improvement.

## Timing residual correction
| model | sigma68_ns | sigma68_ci | timing_bias_ns | timing_bias_ci | tail_frac_abs_gt3ns | n_pulses |
| --- | --- | --- | --- | --- | --- | --- |
| mlp | 0.8714 | [0.7345, 1.023] | 0.02553 | [-0.07972, 0.1127] | 0.05 | 6300 |
| gradient_boosted_trees | 0.9996 | [0.8475, 1.164] | -0.0002472 | [-0.08867, 0.0754] | 0.05524 | 6300 |
| ridge | 1.013 | [0.8344, 1.197] | -0.0007635 | [-0.1274, 0.1098] | 0.06127 | 6300 |
| traditional_template_timewalk | 1.022 | [0.9045, 1.146] | 0.001787 | [-0.1116, 0.1083] | 0.05476 | 6300 |
| 1d_cnn | 2.01 | [1.971, 2.057] | -0.3247 | [-0.4591, -0.2171] | 0.09746 | 6300 |
| compact_waveform_transformer | 2.02 | [1.97, 2.084] | 0.06944 | [0.01401, 0.1346] | 0.07968 | 6300 |

## Two-pulse recovery
| model | average_precision | average_precision_ci | separation_rmse_samples | separation_rmse_ci | separation_bias_samples | n_waveforms |
| --- | --- | --- | --- | --- | --- | --- |
| mlp | 0.9405 | [0.9059, 0.9644] | 1.289 | [1.231, 1.365] | -0.02609 | 2940 |
| gradient_boosted_trees | 0.912 | [0.8764, 0.9425] | 1.234 | [1.208, 1.268] | -0.0009593 | 2940 |
| ridge | 0.8823 | [0.8475, 0.917] | 1.277 | [1.244, 1.317] | 0.0009611 | 2940 |
| 1d_cnn | 0.7948 | [0.7693, 0.8186] | 1.42 | [1.393, 1.452] | 0.3337 | 2940 |
| compact_waveform_transformer | 0.7285 | [0.6844, 0.7748] | 1.361 | [1.346, 1.378] | 0.1049 | 2940 |
| traditional_template_deconvolution | 0.6753 | [0.6364, 0.712] | 2.274 | [2.145, 2.396] | -0.4958 | 2940 |

## Composite result
The overall winner is **mlp**. The timing winner is **mlp** with sigma68 0.871 ns, and the pile-up winner is **mlp** with AP 0.941 and separation RMSE 1.289 samples.

## Systematics and caveats
- **Run splitting:** all reported confidence intervals bootstrap over held-out run summaries, not over rows, so event multiplicity within a run does not masquerade as independent exposure.
- **Pedestal sensitivity:** the baseline estimator is fixed to the canonical median of samples 0--3; pretrigger standard deviation is exposed to tabular models as a nuisance coordinate. A future forced-trigger pedestal transfer should vary this explicitly.
- **Saturation failure modes:** saturated or near-saturated pulses are retained. The `max ADC >= 4090` indicator is available to tabular models, while waveform-only neural methods must infer clipping from shape.
- **Two-pulse truth:** pile-up labels and separations are injected from real raw waveforms rather than externally labeled beam pile-up. This gives controlled separation truth but may understate pathologies from real multi-particle event topology.
- **Transformer capacity:** the compact transformer has one encoder layer and two attention heads. It is deliberately small to keep the comparison in the data-limited regime; this is an architecture test, not a maximum-capacity sweep.

## Novel follow-up ticket
At most one follow-up is appended in `result.json`: validate the winning compact waveform model on externally tagged pile-up or forced-trigger pedestal runs, because this study uses injected overlap truth.
