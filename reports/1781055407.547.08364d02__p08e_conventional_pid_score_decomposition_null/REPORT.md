# P08e: conventional PID score decomposition null

**Ticket:** 1781055407.547.08364d02  
**Worker:** testbeam-laptop-3  
**Input:** raw B-stack `HRDv` ROOT from `data/root/root`  
**Status:** weak-label decomposition only; no truth PID adoption claim.

## Abstract
P08e asks whether the strong conventional P08b charge-current/depth PID-like
score is an independent pulse-shape or range-energy signal, or whether it is a
support and calibration closure that waveform ML should not reproduce as PID.
The study reproduces the raw B-stack selected-pulse count exactly, rebuilds the
P08b duplicate-readout PSTAR/depth residual labels, and benchmarks a conventional
ridge score against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new
nuisance-residualized hybrid MLP under leave-one-run-out evaluation. The winner
stored in `result.json` is **nuisance_residual_hybrid_mlp** with ROC AUC 0.997
[0.994, 0.999], but this is explicitly a weak-label
winner, not a particle-ID truth result.

## Raw ROOT Reproduction
The analysis begins with a full raw ROOT scan over the configured B-stack run
families. Each event reads `HRDv`, estimates the per-channel baseline as the
median of samples 0--3, subtracts it, and selects B2/B4/B6/B8 pulses with
max corrected even-readout amplitude above 1000 ADC. The reproduced values are:

| quantity                           |   report_value |   reproduced |   tolerance |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |           0 |       0 | True   |
| sample_i_calib selected pulses     |         248745 |       248745 |           0 |       0 | True   |
| sample_i_analysis selected pulses  |         252266 |       252266 |           0 |       0 | True   |
| sample_ii_calib selected pulses    |          14630 |        14630 |           0 |       0 | True   |
| sample_ii_analysis selected pulses |         125096 |       125096 |           0 |       0 | True   |

The exact zero-delta reproduction is a hard gate. If this table fails, the
script refuses to run the weak-label benchmark.

## Weak Label and Conventional Score
Let `Q_odd` and `Q_even` be the positive duplicate-readout and even-readout
charge sums over selected B-stack staves, and let `d` be the deepest selected
stave. PSTAR tabulates a monotone mapping from range `r_d` to kinetic energy
anchor `E_d`. On calibration runs only, a per-depth charge quantile map

`C_d(log Q) = E_low,d + F_d(log Q) (E_high,d - E_low,d)`

is fitted, where `F_d` is the empirical charge CDF inside depth atom `d`. The
odd-readout residual

`rho_odd = (C_d(log Q_odd) - E_d) / max(E_d, 1 MeV)`

defines the weak label by taking the bottom and top within-run/depth quantiles.
The even-readout analog `rho_even` is allowed in the conventional score only as
a duplicate-readout control. The conventional feature vector contains tail/area
shape summaries, area/peak-like features, train-fold template quality
`q_template`, B2--B8 amplitude and charge vectors, PSTAR depth anchors,
topology/depth, saturation flags, and event support variables. It is fitted as
a class-balanced ridge discriminant:

`argmin_w ||y - Xw||_2^2 + alpha ||w||_2^2`.

## ML/NN Panel
All methods are trained with no held-out-run rows in fitting, template
construction, or nuisance residualization:

- `waveform_ridge`: ridge classifier on normalized 18-sample B2 waveform
  samples and hand-shape features.
- `waveform_gradient_boosted_trees`: histogram gradient boosting on the same
  waveform feature panel.
- `waveform_mlp`: two-hidden-layer MLP on the same feature panel.
- `waveform_1d_cnn`: compact 1D convolutional network on normalized B2
  samples only.
- `nuisance_residual_hybrid_mlp`: new architecture for this null test. A
  train-fold ridge model first predicts each waveform sample from nuisance
  support variables (depth, topology, charge, event order, run family). The MLP
  receives waveform residuals plus hand-shape features, so its success measures
  residual pulse-shape information after support removal.

## Metrics and Bootstrap
Metrics are evaluated on out-of-fold rows and bootstrapped by resampling held-out
runs with replacement. Reported intervals are 95% percentile intervals over
400 run-block replicates. Calibration is summarized by Brier score and
10-bin expected calibration error (ECE). Purity is computed at fixed 80%
positive-label efficiency using the global out-of-fold score threshold.

| method | ROC AUC | AP | Brier | ECE | purity at 80% efficiency |
|---|---:|---:|---:|---:|---:|
| nuisance_residual_hybrid_mlp | 0.997 [0.994, 0.999] | 0.995 [0.992, 0.998] | 0.080 [0.076, 0.086] | 0.250 | 0.998 [0.997, 0.999] |
| waveform_mlp | 0.987 [0.981, 0.994] | 0.988 [0.981, 0.994] | 0.094 [0.085, 0.103] | 0.218 | 0.996 [0.987, 0.998] |
| waveform_gradient_boosted_trees | 0.987 [0.980, 0.994] | 0.987 [0.981, 0.994] | 0.094 [0.085, 0.102] | 0.218 | 0.998 [0.990, 1.000] |
| traditional_pid_ridge | 0.986 [0.977, 0.994] | 0.985 [0.977, 0.992] | 0.102 [0.093, 0.111] | 0.221 | 0.990 [0.968, 0.996] |
| waveform_ridge | 0.962 [0.946, 0.976] | 0.932 [0.918, 0.948] | 0.117 [0.106, 0.128] | 0.220 | 0.973 [0.932, 0.981] |
| waveform_1d_cnn | 0.920 [0.890, 0.947] | 0.889 [0.854, 0.919] | 0.137 [0.123, 0.150] | 0.176 | 0.856 [0.814, 0.913] |

## ML Minus Conventional
Positive deltas favor the named ML/NN method over the conventional ridge score.

| method | AUC delta vs traditional | 95% CI | bootstrap draws |
|---|---:|---:|---:|
| waveform_ridge | -0.025 | [-0.033, -0.016] | 400 |
| waveform_gradient_boosted_trees | 0.001 | [-0.002, 0.005] | 400 |
| waveform_mlp | 0.001 | [-0.002, 0.005] | 400 |
| waveform_1d_cnn | -0.066 | [-0.088, -0.046] | 400 |
| nuisance_residual_hybrid_mlp | 0.011 | [0.004, 0.019] | 400 |

## Nuisance and Leakage Sentinels
The following probes deliberately restrict information channels. A high
charge-only score means the weak label is dominated by duplicate-readout
charge-scale closure; a high depth/topology score means P08a-style topology
leakage persists; shuffled labels test software leakage.

| probe | ROC AUC | AP | ECE |
|---|---:|---:|---:|
| sentinel_charge_only_ridge | 0.984 [0.975, 0.992] | 0.983 [0.974, 0.990] | 0.228 |
| sentinel_depth_topology_only_ridge | 0.811 [0.780, 0.840] | 0.743 [0.712, 0.773] | 0.125 |
| sentinel_group_event_order_ridge | 0.501 [0.492, 0.511] | 0.492 [0.484, 0.502] | 0.185 |
| sentinel_shuffled_label_gbt | 0.499 [0.446, 0.549] | 0.482 [0.447, 0.519] | 0.133 |

Interpretation ledger:

| probe | value | interpretation |
|---|---:|---|
| sentinel_charge_only_ridge | 0.984 | Allowed even-readout charge closure probe; high AUC means the weak label is mainly charge-scale support. |
| sentinel_depth_topology_only_ridge | 0.811 | P08a-style topology/depth probe; high AUC means terminal/penetrating topology still explains the weak axis. |
| sentinel_group_event_order_ridge | 0.501 | Run-family/event-order current proxy; high AUC indicates run-condition drift. |
| sentinel_shuffled_label_gbt | 0.499 | Shuffled-label software leakage guard; should be near chance. |

## Systematics
The dominant systematic is label circularity: the positive class is a quantile
of the odd duplicate-readout calibrated residual, and the even readout can share
real charge-scale drift. The leave-one-run split prevents row leakage but cannot
turn duplicate-readout closure into truth PID. The depth/topology sentinel
separates P08a-style terminal/penetrating leakage from the calibrated residual
label. The nuisance-residual hybrid tests whether waveform shape survives after
support variables predict the samples; if it loses to charge/support sentinels,
that is evidence against a standalone B2 waveform PID claim. The CNN is compact
by design to avoid fitting a high-capacity classifier to a weak-label nuisance.

## Caveats
No particle truth labels are available in these B-stack ROOT files, so no method
is adopted as PID. Bootstrap intervals are run-block intervals over the available
run families, not detector-configuration universes. Current is represented by
run family and event-order proxies because independent scaler-current records
are not present in the raw `HRDv` tree used here. The conventional score is
allowed to be strong; if it wins, the result supports the null that the weak PID
axis is already explained by calibration and support variables. If an ML method
wins, the sentinels decide whether that is residual waveform shape or nuisance
leakage.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/p08e_1781055407_547_08364d02_conventional_pid_score_decomposition_null.py --config configs/p08e_1781055407_547_08364d02_conventional_pid_score_decomposition_null.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`,
`input_sha256.csv`, `reproduction_match_table.csv`, `method_metrics.csv`,
`ml_minus_traditional.csv`, `leakage_checks.csv`, `fold_audit.csv`,
`heldout_run_label_counts.csv`, `benchmark_balanced_counts.csv`, and
`heldout_predictions.csv.gz`.
