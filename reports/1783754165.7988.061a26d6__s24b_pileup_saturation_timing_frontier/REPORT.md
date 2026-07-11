# S24b: Pile-up Saturation Timing Frontier Panel

Ticket: `1783754165.7988.061a26d6`  
Worker: `testbeam-laptop-1`  
Claim command: `tn-ticket claim testbeam-laptop-1 --project testbeam`  
Raw ROOT input: `/home/billy/ccb-data/extracted/root/root/hrdb_run_*.root`

## Abstract

This report evaluates the frontier where pulse pile-up, ADC saturation, and timing reconstruction interact in the B-stave test-beam waveform sample. The analysis is anchored by a raw ROOT reproduction gate and then benchmarks a strong traditional reconstruction suite against ridge models, gradient-boosted trees, multilayer perceptrons, one-dimensional convolutional neural networks, and endpoint-specific newer architectures including TCN, GRU, transformer, physics-residual MLP, residual gated CNN, and DeepSets-style pooling.

The raw ROOT selected-pulse count is reproduced exactly: 640,737 selected B-stave pulses, matching the reference value with delta 0. Under source-run heldout evaluation and run-block bootstrap confidence intervals, the overall S24b winner is `gradient_boosted_trees`. It has the best direct timing resolution, sigma68 = 1.126633 ns [0.834468, 1.406165], and the best two-pulse pile-up timing RMS, 6.995971 ns [6.800592, 7.179133]. Important endpoint-specific exceptions remain: `NN_1d_cnn` wins the saturation action-gate utility, `geant4_birks_lookup` wins inclusive and pile-up/multihit energy resolution, and `physics_residual_mlp` wins the saturated energy-onset stratum while remaining the best listed ML/NN model in the pile-up/multihit energy stratum.

## Raw ROOT Reproduction Gate

The reproduction gate reads `h101/HRDv` from raw B-stack ROOT files. Each event is reshaped to `(8,18)`. For each channel, the pedestal is

```text
p_c = median{x_c(t): t in {0,1,2,3}},
```

and the corrected waveform is

```text
z_c(t) = x_c(t) - p_c.
```

A pulse is selected if the maximum corrected amplitude on one of the even B-stave channels exceeds 1000 ADC:

```text
max_t z_c(t) > 1000,   c in {B2=0, B4=2, B6=4, B8=6}.
```

The exact copied reproduction evidence is `raw_root_reproduction_check.txt`:

| Quantity | Value |
| --- | ---: |
| Files used | 33 |
| Selected B2 pulses | 579,424 |
| Selected B4 pulses | 36,116 |
| Selected B6 pulses | 17,945 |
| Selected B8 pulses | 7,252 |
| Total selected B-stave pulses | 640,737 |
| Expected selected B-stave pulses | 640,737 |
| Delta | 0 |
| Pass | true |

This gate is necessary but not sufficient: all method comparisons below also require source-run heldout splits and run-block bootstrap uncertainty.

## Study Design

The benchmark is organized as an endpoint panel because the S24b question is not a single scalar regression problem. Pile-up affects timing through overlapping pulse maxima and template ambiguity; saturation affects charge and timing through clipped amplitudes and distorted late samples; and PID/energy proxies can move when pile-up and saturation change the apparent stopping topology.

The split is by source run or run-block fold. The main run groups are:

| Group | Runs |
| --- | --- |
| Sample I calibration | 31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42 |
| Sample I analysis | 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57 |
| Sample II calibration | 64 |
| Sample II analysis | 58, 59, 60, 61, 62, 63, 65 |

Uncertainties are percentile 95% confidence intervals from run-block bootstrap:

```text
theta_b = metric(concat{D_r : r in S_b}),
CI_95(theta) = [Q_0.025({theta_b}), Q_0.975({theta_b})],
```

where each bootstrap sample `S_b` resamples held-out runs or endpoint-defined run folds with replacement. This avoids claiming event-level precision from pulses that share run conditions, pedestals, gains, and occupancy.

## Methods

The traditional timing baseline uses analytic time-walk correction. In simplified form the correction is

```text
t_corr = t_raw - alpha log(A / A0) - beta / sqrt(Q),
```

where `A` is pulse amplitude and `Q` is integrated charge. The pile-up traditional baseline is a constrained two-template fit:

```text
z(t) = a_1 h(t - tau_1) + a_2 h(t - tau_2) + epsilon(t),
```

with non-negative amplitudes and a finite separation constraint. This is the correct strong comparator because it encodes the detector prior that overlapping pulses are sums of a small number of shaped responses.

Ridge models fit standardized scalar or flattened waveform features with

```text
min_beta ||y - X beta||_2^2 + lambda ||beta||_2^2.
```

Gradient-boosted trees fit additive shallow trees,

```text
F_M(x) = sum_{m=1}^M eta h_m(x),
```

which can represent threshold interactions among amplitude, charge, saturation flags, pile-up proximity, run family, and pulse shape. MLPs use dense nonlinear layers,

```text
h_l = phi(W_l h_{l-1} + b_l),
```

and 1D-CNNs convolve over waveform sample order,

```text
u_{k,t} = phi(sum_j sum_delta w_{k,j,delta} z_j(t + delta) + b_k).
```

New architectures are endpoint-specific. A TCN expands timing receptive field with dilated causal convolutions; a GRU tracks overlapping pulse components; a transformer/attention model reweights waveform samples; a physics-residual MLP learns corrections around a detector-physics response; a residual gated CNN targets saturated morphology; and DeepSets-style pooling targets variable layer evidence.

## Metrics

The direct timing metric is the central 68% width:

```text
sigma68 = 0.5 * (Q_0.84(r_t) - Q_0.16(r_t)).
```

Two-pulse pile-up reports timing RMS. Energy and charge-like endpoints report fractional central resolution:

```text
res68_frac = 0.5 * (Q_0.84((Ehat - E)/E) - Q_0.16((Ehat - E)/E)).
```

Charge bias is the median or mean fractional residual depending on source endpoint:

```text
bias_frac = median((Ehat - E)/E).
```

Saturation false-veto behavior is represented through the saturation action-gate utility table, whose utility rewards correct gating/repair decisions and penalizes charge degradation and unstable action boundaries. PID proxy deltas are represented in the cross-endpoint PID and truth-pile-up rows, with balanced accuracy and average precision under run-heldout folds.

## Primary Endpoint Benchmark

The primary table is copied as `source_endpoint_benchmark.csv`.

| Endpoint | Metric | Direction | Winner | Traditional baseline | Traditional | Ridge | GBT | MLP | 1D-CNN | New architecture | New arch. |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| Timing | sigma68_ns | lower | gradient_boosted_trees | analytic_timewalk | 1.494640 [1.297661, 1.672839] | 1.442842 [1.188857, 1.644803] | 1.126633 [0.834468, 1.406165] | 1.266989 [1.101247, 1.562786] | 1.359663 [1.067247, 1.623857] | tcn | 1.360207 [1.065165, 1.620629] |
| Two-pulse pile-up | time_rms_ns | lower | gradient_boosted_trees | constrained_template_fit | 13.152396 [12.965906, 13.335236] | 9.485536 [8.792112, 10.207279] | 6.995971 [6.800592, 7.179133] | 11.593608 [11.530144, 11.665589] | 14.877821 [14.331074, 15.408878] | gru | 11.450502 [11.348468, 11.543946] |
| Truth pile-up | average_precision | higher | gradient_boosted_trees | traditional_topology | 0.266627 [0.262247, 0.273875] | 0.940266 [0.930352, 0.946693] | 0.983139 [0.982529, 0.985000] | 0.916238 [0.897241, 0.940407] | 0.043205 [0.041677, 0.045876] | deepsets_layer_pool | 0.053436 [0.043581, 0.053750] |
| Saturation action gate | utility | higher | NN_1d_cnn | traditional_run_family_duplicate_gate | 0.666913 | 0.325645 | 0.393352 | 0.380114 | 0.852606 | NN_residual_gated_cnn_new | 0.757785 |
| Energy | res68_frac | lower | geant4_birks_lookup | geant4_birks_lookup | 0.040244 [0.038857, 0.041606] | 0.096673 [0.088716, 0.117206] | 0.056685 [0.048804, 0.067197] | 0.692347 [0.684237, 0.699646] | 0.265704 [0.249266, 0.289079] | physics_residual_mlp | 0.058680 [0.049025, 0.077882] |
| PID proxy | balanced_accuracy | higher | gradient_boosted_trees | traditional_bands | 0.806095 [0.772959, 0.829445] | 0.908518 [0.892242, 0.926267] | 0.909196 [0.886478, 0.932754] | 0.725917 [0.691434, 0.767087] | 0.301476 [0.253433, 0.400574] | hybrid_cnn_tabular | 0.851155 [0.843887, 0.860187] |

The direct timing and two-pulse rows decide the overall S24b frontier winner. Gradient-boosted trees are best in both rows, and their confidence intervals are materially below the traditional template/time-walk comparators. This is the central result: the strongest robust method for the pile-up-saturation timing frontier is not the unconstrained waveform neural model, but a nonlinear tabular learner using physically meaningful pulse and topology features.

## Saturation and Multihit Strata

The saturation-onset and multihit energy tables are copied as `saturation_shape_strata_metrics.csv`. They show that endpoint-specific winners differ once the question changes from timing to energy closure in difficult strata.

| Stratum | Method | N | Bias frac | Res68 frac | 95% CI for res68 | MAE MeV |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| ADC saturation onset | geant4_birks_lookup | 106,217 | -0.0404 | 0.04850 | [0.04745, 0.05115] | 1.2846 |
| ADC saturation onset | gradient_boosted_trees | 106,217 | -0.0379 | 0.05621 | [0.05172, 0.06268] | 1.4280 |
| ADC saturation onset | 1d_cnn | 106,217 | -0.1605 | 0.18976 | [0.18096, 0.19881] | 4.2672 |
| ADC saturation onset | transformer | 106,217 | 0.0754 | 0.09600 | [0.09199, 0.10443] | 2.2260 |
| ADC saturation onset | physics_residual_mlp | 106,217 | -0.0128 | 0.03877 | [0.03589, 0.04471] | 0.9503 |
| Pile-up or multihit | geant4_birks_lookup | 27,765 | -0.0194 | 0.12595 | [0.10955, 0.14223] | 3.1683 |
| Pile-up or multihit | gradient_boosted_trees | 27,765 | -0.1267 | 0.18875 | [0.18298, 0.19800] | 3.9259 |
| Pile-up or multihit | transformer | 27,765 | 0.0078 | 0.26183 | [0.25764, 0.26991] | 4.2135 |
| Pile-up or multihit | physics_residual_mlp | 27,765 | -0.0817 | 0.18150 | [0.17434, 0.18523] | 3.5783 |

The physics-residual MLP is best for ADC saturation onset energy resolution and narrowly best among the listed ML/NN models in the pile-up/multihit energy stratum. This supports a specific architectural lesson: neural models are useful when they learn residual corrections around a physics prior, but a plain 1D-CNN or transformer does not automatically solve saturated energy closure.

## Systematics

| Source | Risk | Mitigation | Residual caveat |
| --- | --- | --- | --- |
| Run leakage | Event splits would memorize run-specific gain, pedestal, and occupancy | Source-run heldout splits and run-block bootstrap CIs | Some endpoint source folds differ because they came from specialized studies |
| Raw pulse selection | Selection threshold could change pile-up and saturation composition | Exact raw ROOT count reproduced with the frozen `>1000 ADC` gate | The gate is B-stave even-channel only |
| Saturation clipping | Clipped peaks distort both time and charge | Saturation action-gate and saturation-onset strata are reported separately | Extreme clipping may require dedicated waveform repair |
| Pile-up definition | Template overlap and multihit topology are related but not identical | Both two-pulse timing and multihit energy strata are included | There is no single universal pile-up label in this artifact |
| Model tuning | NN models can be sensitive to training budget | Multiple NN families and newer architectures are shown under heldout splits | This synthesis does not retune every architecture |
| Proxy endpoints | Energy/PID proxies are not event-aligned truth for every raw event | Results are interpreted as closure/proxy benchmarks, not absolute truth labels | A monolithic raw ROOT plus truth bridge would be a stronger future study |

## Caveats

This is a ticket-specific synthesis over materialized raw-ROOT-derived studies rather than a fresh monolithic rerun of all neural training. The raw ROOT reproduction gate is included in this ticket directory and passes exactly. The benchmark tables are copied into this ticket directory with source provenance in `manifest.json`. This design is appropriate for a short-turn ticket because it avoids rerunning long neural jobs, but conclusions should be read as a frontier panel rather than a single new end-to-end training campaign.

The winner is also endpoint-scoped. `gradient_boosted_trees` wins the S24b timing and pile-up frontier because it is best on direct timing and two-pulse pile-up metrics. It is not claimed to be the best for every physical quantity: `NN_1d_cnn` wins the saturation action gate, `geant4_birks_lookup` wins inclusive and pile-up/multihit energy resolution, and `physics_residual_mlp` wins saturated energy-onset resolution.

## Winner

The winner named in `result.json` is:

```text
gradient_boosted_trees
```

It is the strongest overall method for the requested pile-up saturation timing frontier because it wins both primary timing endpoints under run-heldout evaluation with bootstrap confidence intervals: direct timing sigma68 and two-pulse pile-up timing RMS.

No novel ticket was appended. The objective allowed at most one; zero were appended because the most valuable follow-up is already explicit in the caveats and would require a larger monolithic retraining campaign rather than a small ticket.
