# G4-05: event-aligned digitized GEANT4 waveform closure

## Abstract

This study implements the G4-05 digitizer closure requested by ticket
`1783752394.31275.28c6033a`.  The analysis starts with a hard reproduction gate on the raw
test-beam ROOT files and then constructs event-aligned HRD-like waveforms from
GEANT4 `hibeam/Sci_bar` hit truth.  The benchmark compares the G4-04 response
card style traditional calibration against ridge regression, gradient-boosted
trees, a multilayer perceptron, a compact 1D convolutional filterbank network,
and a new physics-residual gated CNN architecture.  The selected winner is
`gradient_boosted_trees` by the primary fractional central-resolution metric.

## Raw ROOT Reproduction

The raw gate reads `h101/HRDv` directly from `data/root/root/hrdb_run_NNNN.root`.
Each event is reshaped into an `8 x 18` waveform array, the median of samples
0--3 is subtracted, and B-stack channels B2/B4/B6/B8 are the zero-based channels
0/2/4/6.  A pulse is selected when its baseline-subtracted amplitude exceeds
1000 ADC.  No cached count table is used by the gate.

The reproduced total is `640737` selected B-stave pulses versus the
canonical target `640737`.  This exact equality is required before any
simulation benchmark is interpreted.

| group | selected_pulses |
| --- | --- |
| sample_i_analysis | 252266 |
| sample_i_calib | 248745 |
| sample_ii_analysis | 125096 |
| sample_ii_calib | 14630 |

## Digitizer Model

For GEANT4 event `i`, Sci_bar hits with `LayerID1 = 2` are interpreted as the
B-stack.  Layer IDs 0, 2, 4, and 6 map to B2, B4, B6, and B8.  For each channel
`c`, the visible hit energy is

`E_vis,c = E_dep,c / (1 + k_q E_dep,c / max(l_c, l_min))`

with `k_q = 0.018` and `l_min = 0.15 cm`.  Duplicate-readout response is modeled
with a near-diagonal response matrix `R`, so the channel energy presented to the
electronics is `E_ro = R E_vis`.  The ADC waveform is a pedestal plus a smeared
semi-Gaussian pulse with a small exponential tail:

`A_c(t) = p_c + g_c E_ro,c [0.72 G(t; t0_c, sigma_c) + 0.28 exp(-(t-t0_c)/tau_c)] + eta_c(t)`.

The digitizer includes run-dependent pedestal offsets, per-channel gain jitter,
time smearing, duplicate-readout cross-talk, and 12-bit saturation at 4095 ADC.
The supervised target is the known GEANT4 B-stack deposited energy summed over
B2/B4/B6/B8, so labels are event-aligned by construction.

## Benchmark Protocol

The split unit is pseudo-run, defined deterministically from the GEANT4 event
index.  There are twelve pseudo-runs.  Each method is evaluated out of fold by
holding out one pseudo-run at a time; all preprocessing and calibration are fit
only on the other pseudo-runs.  Confidence intervals are non-parametric
bootstrap intervals over run blocks with `250` replicates.

The primary metric is central fractional resolution

`res68 = (Q_0.84((E_hat-E)/E) - Q_0.16((E_hat-E)/E)) / 2`.

Lower is better.  Secondary metrics are absolute error in MeV, RMSE in MeV,
mean fractional bias, and median absolute fractional error.

## Methods

`response_card_winner` is the strong traditional baseline.  It uses integrated
charge, saturation count, multiplicity, peak timing, and pre-trigger activity
in a calibrated response-card ridge fit on the training runs.  It is deliberately
small and physics-shaped.

`ridge` uses standardized waveform summary features and an L2 linear model.
`gradient_boosted_trees` uses histogram gradient boosting on the same summary
features.  `mlp` uses both summary features and the flattened 18-sample
waveforms.  `cnn_1d` applies a compact 1D convolutional filterbank over each
channel and feeds the resulting local waveform activations to an MLP.  The new
`physics_residual_gated_cnn` adds a boosted residual head on top of the response
card prediction, with waveform-filter features and support atoms acting as the
gating variables.

## Results

| method | res68_frac | res68_frac_ci_low | res68_frac_ci_high | mae_mev | mae_mev_ci_low | mae_mev_ci_high | bias_frac |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | 0.024317 | 0.023217 | 0.025346 | 0.90148 | 0.8422 | 0.96808 | 0.02679 |
| ridge | 0.029736 | 0.028501 | 0.030853 | 1.0585 | 0.98297 | 1.1239 | 0.025428 |
| physics_residual_gated_cnn | 0.040346 | 0.038095 | 0.044384 | 1.403 | 1.3388 | 1.4737 | 0.022132 |
| mlp | 0.0589 | 0.051875 | 0.064578 | 1.7641 | 1.5823 | 1.922 | 0.036723 |
| cnn_1d | 0.058974 | 0.057342 | 0.060748 | 1.8441 | 1.7915 | 1.8905 | 0.028924 |
| response_card_winner | 0.20496 | 0.19296 | 0.21232 | 6.3585 | 5.9587 | 6.6642 | 0.14197 |

The winner is `gradient_boosted_trees` with `res68 = 0.02432`
and 95% run-bootstrap CI
`[0.02322, 0.02535]`.

## Run Dependence

The held-out pseudo-run rows in `per_run_metrics.csv` show no train/test leakage:
each pseudo-run receives predictions only from models fit without that run.
The widest residual blocks are retained in the CSV rather than removed.

| method | run | res68_frac | mae_mev | bias_frac |
| --- | --- | --- | --- | --- |
| cnn_1d | 1000 | 0.055823 | 1.7263 | -0.015118 |
| cnn_1d | 1001 | 0.060103 | 1.8668 | 0.0023658 |
| cnn_1d | 1002 | 0.061481 | 1.9224 | 0.022712 |
| cnn_1d | 1003 | 0.055132 | 1.8019 | 0.022062 |
| cnn_1d | 1004 | 0.056427 | 1.845 | 0.15757 |
| cnn_1d | 1005 | 0.060866 | 1.903 | -0.010244 |
| gradient_boosted_trees | 1000 | 0.023152 | 0.92294 | -0.00076622 |
| gradient_boosted_trees | 1001 | 0.022442 | 0.78628 | 0.018854 |
| gradient_boosted_trees | 1002 | 0.024986 | 0.86983 | 0.028242 |
| gradient_boosted_trees | 1003 | 0.024995 | 1.0266 | 0.032706 |
| gradient_boosted_trees | 1004 | 0.025539 | 0.88881 | 0.08493 |
| gradient_boosted_trees | 1005 | 0.025472 | 0.91681 | -0.0019795 |
| mlp | 1000 | 0.067197 | 2.0037 | -0.011376 |
| mlp | 1001 | 0.066397 | 1.9744 | 0.034473 |
| mlp | 1002 | 0.049835 | 1.4587 | 0.011252 |
| mlp | 1003 | 0.059832 | 1.7955 | 0.049695 |
| mlp | 1004 | 0.049793 | 1.507 | 0.13498 |
| mlp | 1005 | 0.058236 | 1.8179 | 0.0023277 |

## Residual Atoms and Real-Run Comparison

Residual atoms compare broad waveform support statistics between digitized
GEANT4 and real held-out runs.  The real side uses held-out run groups
`sample_i_analysis` and `sample_ii_analysis`; it is not given GEANT4 truth, so
only detector-observable atoms are compared.

| domain | n | saturation_fraction | multiplicity_mean | peak_bin_mean | pretrigger_q95 | log_charge_mean |
| --- | --- | --- | --- | --- | --- | --- |
| geant4_digitized | 1639 | 0.99146 | 2.2361 | 6.25 | 1976.9 | 10.786 |
| real_heldout_runs | 650970 | 6.9002 | 0.57969 | nan | nan | 8.4521 |

The dominant mismatch is not a label issue; it is an electronics-support issue.
Real held-out runs have a lower selected-pulse multiplicity per event than the
digitized GEANT4 pseudo-runs because the simulated sample is conditioned on
B-stack energy deposition, while the raw gate scans every DAQ event.  This is
why the benchmark winner is reported as a GEANT4 waveform-closure result, not
as an absolute real-data energy calibration.

## Systematics

The largest systematic terms are the B-stack mapping (`LayerID1 = 2` and layers
0/2/4/6), the assumed duplicate-readout response matrix, saturation clipping at
4095 ADC, and the simplified quenching expression.  The pseudo-run split tests
run-external generalization within the digitizer but does not replace a real
run-matched simulation campaign.  The sklearn 1D-CNN implementation uses a
compact convolutional filterbank plus MLP because the project environment used
for this ticket does not include PyTorch; the method still consumes local
18-sample convolutional activations and is evaluated in the same run-heldout
protocol as the other methods.

## Caveats

The closure is event-aligned between GEANT4 truth and digitized waveforms, but
the residual-atom comparison to real held-out runs is distributional rather than
event-key aligned.  GEANT4 truth energy is a known target, while real HRD data
has no per-event B-stack deposited-energy label in this artifact.  The raw ROOT
reproduction validates the detector-data parsing and count convention, not the
absolute GEANT4 material model.

## Reproducibility

Run:

```bash
uv run --extra root python scripts/g4_05_1783752394_31275_28c6033a_digitized_waveform_closure.py
```

Primary artifacts:

- `result.json`
- `benchmark_metrics.csv`
- `per_run_metrics.csv`
- `raw_reproduction_by_run.csv`
- `residual_atoms.csv`
- `raw_root_inventory.csv`
