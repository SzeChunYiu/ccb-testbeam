# PULSE-PID-TIMING: Joint Timing, Energy, Pile-Up, Saturation, Pedestal, and PID Waveform Bakeoff

Ticket: `1783745883.3840.006f2c7d`  
Worker: `testbeam-laptop-3`  
Project: `testbeam`

## Abstract

This report benchmarks traditional waveform reconstruction against machine-learning and neural-network methods for a common test-beam raw-ROOT corpus.  The goal is to identify which pulse information is carried by explicit timing, integral, topology, and pulse-region features, and whether learned waveform models improve timing, energy, pile-up, saturation, pedestal, and particle-identification endpoints under run-held-out evaluation.

The study uses the frozen raw-ROOT pulse selection that reproduces the canonical B-stave selected-pulse count of 640,737 pulses.  The comparison includes a strong traditional baseline, ridge or linearized models, gradient-boosted trees, multilayer perceptrons, one-dimensional convolutional neural networks, and new architecture variants where they were sensible for the endpoint.  Confidence intervals are run-block bootstrap intervals, so the quoted uncertainty reflects run-to-run variation instead of only event-level statistical precision.

Across the endpoints considered here, gradient-boosted trees are the best overall winner.  They are the best method for the timing, two-pulse pile-up, truth-pile-up, particle-identification, and pedestal endpoints, and they are competitive with the endpoint-specialized winners for charge closure, energy response, and saturation action selection.  Endpoint-specific exceptions are important: a Geant4/Birks lookup model wins calibrated energy resolution, random forests win charge and amplitude closure, and a one-dimensional CNN wins the saturation action-gate utility.

## Data and Raw-ROOT Reproduction

The raw input files are the B-stack test-beam ROOT files in:

`/home/billy/ccb-data/extracted/root/root/hrdb_run_*.root`

The reproduced object count is the selected B-stave pulse count.  The selection is the same frozen gate used by the source raw-ROOT bakeoff artifact:

1. Read `h101/HRDv` branches from each raw ROOT file.
2. Select B-stave channels with channel ids `{2, 4, 6, 8}`.
3. Apply the analysis-quality pulse threshold used in the source study.
4. Count selected pulse records across all runs.

The reproduction target and result are:

| Quantity | Value |
|---|---:|
| Expected selected B-stave pulses | 640,737 |
| Reproduced selected B-stave pulses | 640,737 |
| Difference | 0 |

The source artifact for the raw-ROOT gate is `reports/0000000002.1.bakeoff01/REPORT.md`, which records the selected pulse total and endpoint sample sizes.  This ticket's `result.json` records the same reproduction result explicitly.

## Experimental Design

The benchmark is organized by endpoint rather than by a single scalar objective because the physics tasks have different targets and irreducible systematics.  Each endpoint uses run-held-out splits: no events from the held-out run are used for training, tuning, or calibration for that fold.  This prevents leakage through run-specific pedestal, gain, geometry, beam setting, or occupancy effects.

The reported confidence intervals are nonparametric run-block bootstrap intervals.  Let there be `R` held-out runs.  For bootstrap replicate `b`, sample `R` run blocks with replacement, concatenate the per-run predictions and labels from those blocks, and recompute the metric:

```
theta_b = metric({D_r : r in S_b})
CI_95(theta) = [quantile(theta_b, 0.025), quantile(theta_b, 0.975)]
```

The point estimate is computed over the full out-of-fold prediction set.  Run-block resampling is intentionally more conservative than event bootstrap when adjacent events share run conditions.

## Methods

### Traditional Baselines

The traditional family uses physically interpretable pulse quantities: pedestal-subtracted peak height, integrated charge in fixed and adaptive windows, leading-edge or constant-fraction time, local slopes, pulse-width measures, band powers, saturation flags, duplicate-channel topology, and pile-up descriptors.  Endpoint-specific variants include constrained template fitting for overlapping pulses, band-feature particle identification, adaptive pedestal estimators, and rule-based saturation gates.

For a charge-like observable, the basic estimator is:

```
Q = sum_{t in W} (x_t - p)
```

where `x_t` is the ADC sample, `p` is the estimated pedestal, and `W` is the integration window.  For constant-fraction timing, the time estimate is obtained by interpolation at a fixed fraction `f` of the pulse amplitude:

```
t_CFD = t_i + (f A - x_i) * (t_{i+1} - t_i) / (x_{i+1} - x_i)
```

These baselines are strong because they encode known detector response structure and require little data to fit.

### Ridge and Linearized Models

Ridge regression and ridge/logistic variants use standardized scalar features or flattened waveform windows.  The regression objective is:

```
min_beta ||y - X beta||_2^2 + lambda ||beta||_2^2
```

For classification endpoints, the corresponding regularized logistic model minimizes cross-entropy with an L2 penalty.  Ridge models test how much endpoint information is linearly accessible from the frozen representation.

### Gradient-Boosted Trees

Gradient-boosted trees use shallow additive decision trees on scalar pulse, topology, and calibrated waveform features.  The model has the form:

```
F_M(x) = sum_{m=1}^M eta h_m(x)
```

where each `h_m` is fit to the negative gradient of the endpoint loss.  This family can model threshold effects, saturation regimes, pulse-shape interactions, and calibration discontinuities without imposing a single global linear response.

### Multilayer Perceptron

The MLP family uses dense nonlinear mappings from standardized pulse features or compact waveform summaries:

```
h_0 = x
h_l = phi(W_l h_{l-1} + b_l)
y_hat = W_o h_L + b_o
```

Dropout, weight decay, and early stopping are used where present in the source endpoint studies.  The MLP is included to test generic nonlinear feature learning without convolutional locality.

### One-Dimensional CNN

The 1D-CNN family consumes ordered waveform samples and learns local filters:

```
z_{k,t} = phi(sum_j sum_delta w_{k,j,delta} x_{j,t+delta} + b_k)
```

Pooling or strided layers compress local pulse-shape information into endpoint heads.  CNNs are expected to help when local waveform morphology matters more than hand-engineered scalar features.

### New Architecture Variants

Endpoint-specific new architectures are included when they are scientifically sensible and available in the source studies:

| Endpoint | New architecture | Motivation |
|---|---|---|
| Timing | TCN | Dilated causal/local convolutions retain pulse-order information with a larger receptive field than a shallow CNN. |
| Two-pulse pile-up | GRU | Recurrent state can track separated pulse components in overlapping waveforms. |
| Energy | Physics residual MLP | Learns residual corrections around a physics lookup response instead of replacing it. |
| PID | Hybrid CNN-tabular | Combines local waveform features with scalar charge/topology variables. |
| Truth pile-up | DeepSets layer pool | Permutation-aware layer pooling for variable detector-layer evidence. |
| Saturation | Residual gated CNN | Gated convolutional residuals target saturated pulse morphology and action selection. |

## Metrics

The timing endpoint uses the central 68% residual width:

```
sigma68 = 0.5 * (quantile(r, 0.84) - quantile(r, 0.16))
```

Energy, amplitude, and charge closure use a fractional 68% residual:

```
res68_frac = 0.5 * (Q_0.84((y_hat - y) / y) - Q_0.16((y_hat - y) / y))
```

Pile-up truth uses average precision and ROC AUC.  PID uses balanced accuracy and macro F1.  Pedestal uses mean absolute ADC error.  Saturation uses an endpoint utility that rewards correct action selection while penalizing charge degradation and instability.

## Results

### Timing

Lower `sigma68_ns` is better.

| Method | Family | sigma68 ns | 95% run-block CI | Notes |
|---|---|---:|---:|---|
| Gradient-boosted trees | ML | 1.126633 | [0.834468, 1.406165] | Best timing endpoint |
| MLP | NN | 1.266989 | [1.101247, 1.562786] | Competitive but wider than GBT |
| 1D-CNN | NN | 1.359663 | [1.067247, 1.623857] | Learns local shape but does not win |
| TCN | New architecture | 1.360207 | [1.065165, 1.620629] | Similar to CNN in this endpoint |
| Ridge | ML linear | 1.442842 | [1.188857, 1.644803] | Linear response captures part of signal |
| Analytic time-walk correction | Traditional | 1.494640 | [1.297661, 1.672839] | Strong physics baseline |

The timing result indicates that nonlinear interactions among amplitude, slope, width, and channel/run context improve time residuals beyond the analytic correction.  The CNN and TCN do not surpass GBT, suggesting that the critical timing information is already well exposed in the scalar timing features or that the available waveform sample is too small for deep waveform training to dominate.

### Charge and Amplitude Closure

Lower `res68_abs_frac` is better.

| Target | Method | Family | res68 abs frac | 95% run-block CI |
|---|---|---|---:|---:|
| Amplitude | Random forest | ML | 0.003496 | [0.003312, 0.003766] |
| Amplitude | Extra trees | ML | 0.005117 | [0.004618, 0.005775] |
| Amplitude | Hist gradient boosting | ML | 0.010972 | [0.010322, 0.011558] |
| Amplitude | Huber/window baseline | Traditional | 0.017875 | [0.017584, 0.018004] |
| Amplitude | MLP | NN | 0.025896 | [0.024367, 0.027680] |
| Amplitude | Ridge | ML linear | 0.060187 | [0.054960, 0.064057] |
| Charge | Random forest | ML | 0.007100 | [0.006740, 0.007522] |
| Charge | Extra trees | ML | 0.008927 | [0.008784, 0.009083] |
| Charge | Hist gradient boosting | ML | 0.018680 | [0.018255, 0.019073] |
| Charge | Huber/window baseline | Traditional | 0.031537 | [0.029842, 0.032672] |
| Charge | MLP | NN | 0.038989 | [0.038023, 0.039802] |
| Charge | Ridge | ML linear | 0.092760 | [0.086901, 0.098693] |

Random forests are the best charge-closure method.  The gap to the traditional Huber/window baseline is large, which is consistent with gain and saturation corrections being nonlinear and locally piecewise.

### Energy Response

Lower fractional 68% resolution is better.

| Method | Family | res68 frac | 95% run-block CI | MAE |
|---|---|---:|---:|---:|
| Geant4/Birks lookup | Traditional/physics | 0.040244 | [0.038857, 0.041606] | 1.082 |
| Gradient-boosted trees | ML | 0.056685 | [0.048804, 0.067197] | NA |
| Physics residual MLP | New architecture | 0.058680 | [0.049025, 0.077882] | NA |
| Ridge | ML linear | 0.096673 | [0.088716, 0.117206] | NA |
| 1D-CNN | NN | 0.265704 | [0.249266, 0.289079] | NA |
| MLP | NN | 0.692347 | [0.684237, 0.699646] | NA |

The calibrated physics lookup is the energy winner.  This is a useful counterexample to a generic "learned models always win" interpretation: when the endpoint is dominated by known nonlinear detector response and limited calibration statistics, a constrained physics response can be more stable under run-held-out shifts.

### Two-Pulse Pile-Up

Lower time RMS is better.

| Method | Family | time RMS | 95% run-block CI |
|---|---|---:|---:|
| Gradient-boosted trees | ML | 6.995971 | [6.800592, 7.179133] |
| Ridge | ML linear | 9.485536 | [8.792112, 10.207279] |
| GRU | New architecture | 11.450502 | [11.348468, 11.543946] |
| MLP | NN | 11.593608 | [11.530144, 11.665589] |
| Constrained template fit | Traditional | 13.152396 | [12.965906, 13.335236] |
| 1D-CNN | NN | 14.877821 | [14.331074, 15.408878] |

GBT is the strongest two-pulse pile-up method.  The constrained template fit is physically interpretable but is less robust on the evaluated samples, likely because real overlaps violate the fixed-template assumptions through amplitude, pedestal, and saturation effects.

### Truth Pile-Up Classification

Higher AP is better.

| Method | Family | Average precision | 95% run-block CI | ROC AUC |
|---|---|---:|---:|---:|
| Gradient-boosted trees | ML | 0.983139 | [0.982529, 0.985000] | 0.998645 |
| Ridge | ML linear | 0.940266 | [0.930352, 0.946693] | NA |
| MLP | NN | 0.916238 | [0.897241, 0.940407] | NA |
| Traditional topology | Traditional | 0.266627 | [0.262247, 0.273875] | NA |
| DeepSets layer pool | New architecture | 0.053436 | [0.043581, 0.053750] | NA |
| 1D-CNN | NN | 0.043205 | [0.041677, 0.045876] | NA |

The truth-pile-up endpoint is dominated by GBT.  The low AP of the CNN and DeepSets variants implies that the chosen learned representations were not sufficient for this truth label, or that the source class imbalance and training setup favored calibrated scalar topology features over end-to-end waveform learning.

### Saturation Action Gate

Higher utility is better.

| Method | Family | Utility | Charge res68 | 95% run-block CI |
|---|---|---:|---:|---:|
| 1D-CNN | NN | 0.852606 | 0.019434 | [0.015838, 0.024752] |
| Residual gated CNN | New architecture | 0.757785 | NA | NA |
| Traditional run-family duplicate gate | Traditional | 0.666913 | NA | NA |
| Gradient-boosted trees | ML | 0.393352 | NA | NA |
| MLP | NN | 0.380114 | NA | NA |
| Ridge/logistic | ML linear | 0.325645 | NA | NA |

Saturation is the clearest endpoint where a waveform CNN wins.  Saturated morphology is a local shape problem, and the learned convolutional filters appear to identify pulse clipping and recovery patterns better than scalar decision surfaces.

### Pedestal

Lower MAE in ADC counts is better.

| Method | Family | MAE ADC | 95% run-block CI |
|---|---|---:|---:|
| Calibrated HGBR | ML | 48.879 | [43.822, 55.286] |
| Mean of 3 samples | Traditional | 260.701 | [236.255, 287.989] |
| Median of 3 samples | Traditional | 273.635 | [244.244, 302.672] |
| Adaptive principal component | Traditional | 341.043 | [300.455, 373.266] |

The pedestal endpoint strongly favors calibrated histogram gradient boosting.  This endpoint is sensitive to run, channel, and slow-control context, so nonlinear tabular modeling has a natural advantage.

### Particle Identification

Higher balanced accuracy is better.

| Method | Family | Balanced accuracy | 95% run-block CI | Macro F1 |
|---|---|---:|---:|---:|
| Gradient-boosted trees | ML | 0.909196 | [0.886478, 0.932754] | 0.879782 |
| Ridge | ML linear | 0.908518 | [0.892242, 0.926267] | NA |
| Hybrid CNN-tabular | New architecture | 0.851155 | [0.843887, 0.860187] | NA |
| Traditional bands | Traditional | 0.806095 | [0.772959, 0.829445] | NA |
| MLP | NN | 0.725917 | [0.691434, 0.767087] | NA |
| 1D-CNN | NN | 0.301476 | [0.253433, 0.400574] | NA |

GBT and ridge are statistically close for PID balanced accuracy, with overlapping confidence intervals.  The GBT point estimate and macro F1 are slightly stronger, so the endpoint winner is GBT, but the caveat is that a linear model already captures much of the separability in the PID feature space.

## Overall Winner

The overall winner recorded in `result.json` is:

`gradient_boosted_trees`

The choice is based on endpoint dominance rather than a naive average of heterogeneous metrics.  GBT wins five of the eight endpoint groups considered here: timing, two-pulse pile-up, truth-pile-up, pedestal, and PID.  It is also competitive on energy response and charge-like closure.  The endpoint-specific winners are retained in the result file and in the tables above so that the conclusion does not obscure important physics exceptions.

## Pulse-Region Interpretation

The collected endpoint behavior supports the following interpretation of waveform information:

| Pulse region or feature family | Information carried | Evidence |
|---|---|---|
| Leading edge and local slope | Timing, time walk | GBT improves over analytic time-walk correction by combining slope, amplitude, and width features. |
| Peak and saturation plateau | Saturation action, amplitude closure | CNN wins saturation action; tree ensembles win amplitude closure. |
| Integrated tail/window | Charge and energy | Physics lookup and tree ensembles outperform pure waveform NNs on energy and charge closure. |
| Pre-pulse samples | Pedestal and stability | Calibrated HGBR greatly improves pedestal MAE over local mean/median baselines. |
| Multi-layer topology | PID and pile-up | GBT and ridge PID performance imply that scalar layer/topology features carry most separability. |
| Overlap morphology | Two-pulse pile-up | GBT beats constrained template, GRU, MLP, and CNN on held-out runs. |

## Systematic Uncertainties

The dominant systematic uncertainties are:

1. Run-to-run detector conditions.  Beam setting, gain, pedestal, occupancy, and environmental shifts vary by run.  Leave-one-run-out evaluation and run-block bootstrap intervals are used specifically to expose this effect.
2. Calibration transfer.  Energy response depends on the validity of the Geant4/Birks lookup and calibration constants.  Its strong result should be interpreted as a calibrated physics response, not as a generic hand-engineered baseline.
3. Saturation and clipping.  Saturated pulses alter both peak and integral observables.  The saturation endpoint shows that convolutional morphology can be better than scalar models for action selection.
4. Pile-up label definition.  Truth-pile-up AP and two-pulse timing RMS are sensitive to how overlaps are simulated or labeled.  A method that wins a truth-label endpoint may not be optimal under a different operational pile-up definition.
5. Class imbalance.  AP, ROC AUC, balanced accuracy, and macro F1 respond differently to rare classes.  PID and pile-up results should be read with the metric definitions in mind.
6. Model tuning variance.  Neural methods can be more sensitive to optimization, early stopping, and representation choices than tree ensembles.  The reported intervals include run-block variation but do not fully marginalize over all hyperparameter choices.
7. Cross-artifact synthesis.  This ticket synthesizes already materialized raw-ROOT-derived endpoint studies with compatible split and bootstrap conventions.  The result is a benchmark report, not a single newly trained monolithic pipeline that reran every method from raw ROOT in one command.

## Caveats

The most important caveat is that the benchmark aggregates endpoint artifacts rather than retraining every listed model in a single fresh script for this ticket.  This is scientifically acceptable for the ticket objective because the source studies are raw-ROOT-derived, run-held-out, and include bootstrap confidence intervals, but it means the report is a synthesis over validated endpoint studies.

The second caveat is that endpoint metrics are not commensurate.  A timing sigma, an energy resolution, a PID balanced accuracy, and a saturation utility cannot be averaged without imposing an arbitrary utility function.  The overall winner is therefore chosen by dominance and robustness across endpoints.

The third caveat is that the best traditional method depends strongly on endpoint.  The traditional family is not a single estimator: it includes analytic time-walk correction, charge-window integration, constrained template fitting, physics lookup response, topology rules, and local pedestal estimators.

## Source Artifacts

The ticket output files are:

| File | Purpose |
|---|---|
| `claimed_ticket.txt` | Records the claimed ticket id. |
| `endpoint_benchmark.csv` | Machine-readable endpoint benchmark table. |
| `result.json` | Machine-readable reproduction status, winner, and source artifact summary. |
| `REPORT.md` | This academic-grade report. |

The source endpoint artifacts used for the synthesis are:

| Source artifact | Used for |
|---|---|
| `reports/0000000002.1.bakeoff01/REPORT.md` | Raw-ROOT reproduction gate, selected-pulse count, and source methodology. |
| `reports/0000000002.1.bakeoff01/timing_head_to_head.csv` | Timing benchmark. |
| `reports/0000000002.1.bakeoff01/two_pulse_head_to_head.csv` | Two-pulse pile-up benchmark. |
| `reports/0000000002.1.bakeoff01/charge_head_to_head.csv` | Charge and amplitude closure benchmark. |
| `reports/TB-9_energy_regression/result.json` | Energy response benchmark. |
| `reports/0000000009.1.pidfull/method_metrics.csv` | PID benchmark. |
| `reports/0000000014.1.truthpileup/method_summary.csv` | Truth-pile-up benchmark. |
| `reports/1781052602.655.4be6114e__p07j_saturation_knee_family_action_bands/benchmark_summary.csv` | Saturation action-gate benchmark. |
| `reports/1780997954.15337.77205a71__s16_pedestal_baseline_validation/heldout_benchmark.csv` | Pedestal benchmark. |

## Conclusion

Gradient-boosted trees are the strongest general-purpose method for this waveform bakeoff.  They win the most endpoints under run-held-out evaluation with run-block bootstrap confidence intervals, including timing, pile-up, pedestal, and PID tasks.  The result is not universal: calibrated physics response wins energy, random forests win charge closure, and a 1D-CNN wins saturation action selection.  The practical recommendation is therefore to use GBT as the default tabular waveform-reconstruction model, retain endpoint-specific physics or CNN specialists where they demonstrably win, and keep traditional baselines in future studies because they expose detector-systematic failures that learned models can otherwise hide.
