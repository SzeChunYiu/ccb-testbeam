# S15b: raw-HRD PID proxy falsification ledger

**Ticket:** 1781069565.648.74687e98  
**Worker:** testbeam-laptop-3  
**Input:** raw B-stack `HRDv` ROOT from `data/root/root`  
**Status:** falsification ledger only; no truth PID adoption claim.

## Abstract
S15b asks whether raw HRD pulse atoms carry PID-like information beyond
penetration depth, charge, run family, saturation, topology, and external-charge
support proxies. The study reproduces the raw B-stack selected-pulse count
exactly, rebuilds duplicate-readout PSTAR/depth residual weak labels, and
benchmarks a transparent DeltaE-E/depth ridge score against ridge,
gradient-boosted trees, MLP, 1D-CNN, and a new support-residual hybrid MLP under
leave-one-run-out evaluation. The winner stored in `result.json` is
**support_residual_hybrid_mlp_new** with ROC AUC 0.997 [0.994,
0.999], but this is explicitly a weak-label winner, not a
particle-ID truth result.

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

## Weak Label and Traditional Score
Let `Q_odd` and `Q_even` be the positive duplicate-readout and even-readout
charge sums over selected B-stack staves, and let `d` be the deepest selected
stave. PSTAR tabulates a monotone mapping from range `r_d` to kinetic energy
anchor `E_d`. On calibration runs only, a per-depth charge quantile map

`C_d(log Q) = E_low,d + F_d(log Q) (E_high,d - E_low,d)`

is fitted, where `F_d` is the empirical charge CDF inside depth atom `d`. The
odd-readout residual

`rho_odd = (C_d(log Q_odd) - E_d) / max(E_d, 1 MeV)`

defines the weak label by taking the bottom and top within-run/depth quantiles.
The even-readout analog `rho_even` is allowed in the traditional score only as
a duplicate-readout control. The traditional feature vector contains transparent
DeltaE-E, stopping-depth, charge-ratio, tail/total, penetration-depth,
saturation, and topology terms plus train-fold template quality `q_template`.
It is fitted as a class-balanced ridge discriminant:

`argmin_w ||y - Xw||_2^2 + alpha ||w||_2^2`.

## ML/NN Panel
All methods are trained with no held-out-run rows in fitting, template
construction, or nuisance residualization:

- `ridge`: ridge classifier on normalized 18-sample B2 waveform
  samples and hand-shape features.
- `gradient_boosted_trees`: histogram gradient boosting on the same
  waveform feature panel.
- `mlp`: two-hidden-layer MLP on the same feature panel.
- `cnn_1d`: compact 1D convolutional network on normalized B2
  samples only.
- `support_residual_hybrid_mlp_new`: new architecture for this null test. A
  train-fold ridge model first predicts each waveform sample from nuisance
  support variables (depth, topology, charge, event order, run family). The MLP
  receives waveform residuals plus hand-shape features, so its success measures
  residual pulse-shape information after support removal.

## Metrics and Bootstrap
Metrics are evaluated on out-of-fold rows and bootstrapped by resampling held-out
runs with replacement. Reported intervals are 95% percentile intervals over
500 run-block replicates. `method_metrics.csv` also includes topology-block
CIs from resampling topology codes with replacement. Calibration is summarized
by Brier score and 10-bin expected calibration error (ECE). Purity is computed
at fixed 80% positive-label efficiency using the global out-of-fold score
threshold.

Accepted support:

| quantity | rows | fraction of raw B2-selected rows |
|---|---:|---:|
| raw_b2_selected_rows | 579424 | 1.000 |
| weak_label_labeled_rows | 289626 | 0.500 |
| balanced_head_to_head_rows | 15694 | 0.027 |
| evaluated_oof_rows | 15694 | 0.027 |

| method | ROC AUC | AP | Brier | ECE | purity at 80% efficiency |
|---|---:|---:|---:|---:|---:|
| support_residual_hybrid_mlp_new | 0.997 [0.994, 0.999] | 0.995 [0.992, 0.998] | 0.080 [0.076, 0.086] | 0.250 | 0.998 [0.997, 0.999] |
| mlp | 0.987 [0.980, 0.994] | 0.988 [0.981, 0.994] | 0.094 [0.085, 0.103] | 0.218 | 0.996 [0.987, 0.998] |
| gradient_boosted_trees | 0.987 [0.980, 0.994] | 0.987 [0.981, 0.994] | 0.094 [0.085, 0.102] | 0.218 | 0.998 [0.989, 1.000] |
| traditional_deltae_depth_ridge | 0.986 [0.977, 0.994] | 0.985 [0.977, 0.992] | 0.102 [0.093, 0.111] | 0.221 | 0.990 [0.968, 0.996] |
| ridge | 0.962 [0.945, 0.976] | 0.932 [0.918, 0.948] | 0.117 [0.106, 0.128] | 0.220 | 0.973 [0.929, 0.981] |
| cnn_1d | 0.920 [0.891, 0.947] | 0.889 [0.853, 0.918] | 0.137 [0.123, 0.150] | 0.176 | 0.856 [0.813, 0.913] |

## ML Minus Conventional
Positive deltas favor the named ML/NN method over the conventional ridge score.

| method | AUC delta vs traditional | 95% CI | bootstrap draws |
|---|---:|---:|---:|
| ridge | -0.025 | [-0.033, -0.016] | 500 |
| gradient_boosted_trees | 0.001 | [-0.002, 0.005] | 500 |
| mlp | 0.001 | [-0.002, 0.005] | 500 |
| cnn_1d | -0.066 | [-0.090, -0.045] | 500 |
| support_residual_hybrid_mlp_new | 0.011 | [0.004, 0.019] | 500 |

## Falsification, Nuisance, and Leakage Sentinels
The following probes deliberately restrict information channels. A high
charge-only score means the weak label is dominated by duplicate-readout
charge-scale closure; high depth-only or topology-only scores mean the apparent
PID axis is mostly support geometry; shuffled and target-permuted labels test
software and label-source leakage. Feature knockouts quantify whether the
classification survives removal of charge, depth/topology, or waveform samples.

| probe | ROC AUC | AP | ECE |
|---|---:|---:|---:|
| knockout_no_depth_topology_gbt | 0.995 [0.992, 0.998] | 0.996 [0.992, 0.998] | 0.240 |
| knockout_no_charge_gbt | 0.987 [0.980, 0.994] | 0.987 [0.981, 0.994] | 0.219 |
| knockout_no_waveform_gbt | 0.984 [0.975, 0.992] | 0.983 [0.974, 0.990] | 0.219 |
| sentinel_charge_only_ridge | 0.984 [0.974, 0.992] | 0.983 [0.974, 0.990] | 0.228 |
| sentinel_depth_only_ridge | 0.805 [0.775, 0.833] | 0.744 [0.713, 0.777] | 0.113 |
| sentinel_topology_only_ridge | 0.787 [0.733, 0.845] | 0.861 [0.820, 0.900] | 0.126 |
| sentinel_group_event_order_ridge | 0.501 [0.490, 0.511] | 0.492 [0.483, 0.503] | 0.185 |
| sentinel_shuffled_label_gbt | 0.499 [0.447, 0.553] | 0.482 [0.449, 0.524] | 0.133 |
| sentinel_target_permutation_gbt | 0.478 [0.421, 0.529] | 0.467 [0.434, 0.501] | 0.139 |

Interpretation ledger:

| probe | value | interpretation |
|---|---:|---|
| sentinel_charge_only_ridge | 0.984 | Allowed even-readout charge closure probe; high AUC means the weak label is mainly charge-scale support. |
| sentinel_depth_only_ridge | 0.805 | Penetration-depth-only probe; high AUC means range support explains the weak axis. |
| sentinel_topology_only_ridge | 0.787 | Topology/saturation-only probe; high AUC means terminal topology or saturation explains the weak axis. |
| sentinel_group_event_order_ridge | 0.501 | Run-family/event-order current proxy; high AUC indicates run-condition drift. |
| sentinel_shuffled_label_gbt | 0.499 | Shuffled-label software leakage guard; should be near chance. |
| sentinel_target_permutation_gbt | 0.478 | Within-depth target permutation guard; should be near chance if label-source ordering is not leaked. |
| knockout_no_charge_gbt | 0.987 | Feature-family knockout removing charge summary terms; residual AUC estimates waveform/support-only separability. |
| knockout_no_depth_topology_gbt | 0.995 | Feature-family knockout removing explicit depth/topology terms; residual AUC estimates charge/waveform separability. |
| knockout_no_waveform_gbt | 0.984 | Feature-family knockout removing waveform samples; high AUC means conventional support variables are sufficient. |

## Systematics
The dominant systematic is label circularity: the positive class is a quantile
of the odd duplicate-readout calibrated residual, and the even readout can share
real charge-scale drift. The leave-one-run split prevents row leakage but cannot
turn duplicate-readout closure into truth PID. The depth-only and topology-only
sentinels separate terminal/penetrating geometry leakage from residual waveform
information. The support-residual hybrid tests whether waveform shape survives
after support variables predict the samples; if it loses to charge/support
sentinels, that is evidence against a standalone B2 waveform PID claim. The CNN
is compact by design to avoid fitting a high-capacity classifier to a weak-label
nuisance.

## Caveats
No particle truth labels are available in these B-stack ROOT files, so no method
is adopted as PID. Bootstrap intervals are run-block and topology-block
intervals over the available support blocks, not detector-configuration
universes. Current is represented by run family and event-order proxies because
independent scaler-current records are not present in the raw `HRDv` tree used
here. The traditional score is allowed to be strong; if it wins, the result
supports the null that the weak PID axis is already explained by calibration and
support variables. If an ML/NN method wins, the sentinels decide whether that is
residual waveform shape or nuisance leakage.

## Conclusion and Next Test
The point-estimate head-to-head winner is `support_residual_hybrid_mlp_new`, but the
falsification ledger prevents PID adoption: charge-only and no-waveform controls
are already near the traditional score, and the no-depth/topology knockout is
also very strong. The working hypothesis is therefore that the S15b weak axis is
mostly a charge/support closure with a small residual waveform component, not a
validated proton/deuteron separator. The queued follow-up asks whether external
PID truth can be joined at the event level; without that join, future PID uses
should remain explicitly weak-label diagnostics.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/s15b_1781069565_648_74687e98_raw_hrd_pid_proxy_falsification_ledger.py --config configs/s15b_1781069565_648_74687e98_raw_hrd_pid_proxy_falsification_ledger.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`,
`input_sha256.csv`, `reproduction_match_table.csv`, `method_metrics.csv`,
`ml_minus_traditional.csv`, `leakage_checks.csv`, `fold_audit.csv`,
`heldout_run_label_counts.csv`, `support_fraction_ledger.csv`,
`benchmark_balanced_counts.csv`, and `heldout_predictions.csv.gz`.
