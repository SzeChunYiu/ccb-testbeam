# Ticket 2376: P08 Waveform-Only Weak-Label PID Bakeoff

**Ticket:** 2376  
**Worker:** testbeam-laptop-2  
**Input:** raw B-stack `HRDv` ROOT from `data/root/root`  
**Status:** null-label stability and falsification audit only; no truth PID adoption claim.

## Abstract
This ticket 2376 P08 analysis asks whether raw HRD waveform or charge-shape PID weak labels
are stable under null relabellings, geometry/depth-only baselines, and matched
saturation, dropout, baseline, anomaly, amplitude, and run-family support. The
study reproduces the raw B-stack selected-pulse count exactly, rebuilds
duplicate-readout PSTAR/depth residual weak labels, and benchmarks a transparent
DeltaE-E/depth ridge score against ridge, gradient-boosted trees, MLP, 1D-CNN,
and a new support-residual hybrid MLP under leave-one-run-out evaluation. The
winner stored in `result.json` is
**support_residual_hybrid_mlp_new** with ROC AUC 0.998 [0.996,
0.999], but this is explicitly a weak-label winner, not a
particle-ID truth result.


## Claim Recovery Note

The required single command `tn-ticket claim testbeam-laptop-2 --project testbeam` was run once and returned the known null pseudo-ticket (`null`, `# null`, `null`). The queue was not empty, so issue #2376 was recovered by direct GitHub label transition to `factory:claimed` and `worker:testbeam-laptop-2` without rerunning the claim command.

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

Matched nuisance-support audit:

| quantity | rows | fraction |
|---|---:|---:|
| evaluated_rows_before_support_matching | 15694 | 1.000 |
| evaluated_rows_in_matched_support_cells | 7422 | 0.473 |
| support_collapse_fraction | 8272 | 0.527 |
| matched_support_cells | 20 | 0.106 |

| method | ROC AUC | AP | Brier | ECE | purity at 80% efficiency |
|---|---:|---:|---:|---:|---:|
| support_residual_hybrid_mlp_new | 0.998 [0.996, 0.999] | 0.996 [0.993, 0.999] | 0.079 [0.075, 0.083] | 0.252 | 0.999 [0.997, 1.000] |
| mlp | 0.989 [0.982, 0.995] | 0.990 [0.984, 0.995] | 0.093 [0.085, 0.101] | 0.220 | 0.996 [0.991, 0.998] |
| gradient_boosted_trees | 0.988 [0.982, 0.995] | 0.989 [0.984, 0.995] | 0.093 [0.086, 0.101] | 0.219 | 0.996 [0.992, 1.000] |
| traditional_deltae_depth_ridge | 0.986 [0.976, 0.993] | 0.982 [0.973, 0.990] | 0.102 [0.093, 0.112] | 0.224 | 0.989 [0.966, 0.995] |
| ridge | 0.960 [0.943, 0.974] | 0.930 [0.914, 0.945] | 0.116 [0.108, 0.127] | 0.219 | 0.973 [0.939, 0.982] |
| cnn_1d | 0.900 [0.861, 0.932] | 0.855 [0.801, 0.905] | 0.143 [0.129, 0.159] | 0.169 | 0.838 [0.780, 0.893] |

## Null Relabelling Stability
The fitted out-of-fold scores are re-evaluated against four null labels:
global shuffling, shuffling within held-out run, shuffling within run/depth
atoms, and shuffling within the full nuisance-support cells. These checks do
not retrain on noise; they ask whether the produced score remains spuriously
aligned with labels after the weak-label assignment is destroyed while retaining
run or support composition. The first three relabellings are expected to be
near chance; a non-chance full-support-cell shuffle means the support cell is
too coarse and still contains within-cell charge or waveform substructure.

| null variant | method | null ROC AUC | null AP | null ECE |
|---|---|---:|---:|---:|
| global_shuffle | cnn_1d | 0.499 [0.489, 0.507] | 0.500 | 0.193 |
| global_shuffle | support_residual_hybrid_mlp_new | 0.502 [0.493, 0.512] | 0.503 | 0.229 |
| global_shuffle | traditional_deltae_depth_ridge | 0.500 [0.492, 0.508] | 0.500 | 0.206 |
| within_run_depth_shuffle | cnn_1d | 0.503 [0.495, 0.510] | 0.498 | 0.188 |
| within_run_depth_shuffle | support_residual_hybrid_mlp_new | 0.503 [0.495, 0.509] | 0.500 | 0.227 |
| within_run_depth_shuffle | traditional_deltae_depth_ridge | 0.502 [0.495, 0.509] | 0.501 | 0.205 |
| within_run_shuffle | cnn_1d | 0.494 [0.484, 0.504] | 0.494 | 0.196 |
| within_run_shuffle | support_residual_hybrid_mlp_new | 0.492 [0.484, 0.500] | 0.495 | 0.237 |
| within_run_shuffle | traditional_deltae_depth_ridge | 0.490 [0.481, 0.498] | 0.490 | 0.214 |
| within_support_cell_shuffle | cnn_1d | 0.883 [0.853, 0.906] | 0.838 | 0.151 |
| within_support_cell_shuffle | support_residual_hybrid_mlp_new | 0.960 [0.949, 0.969] | 0.955 | 0.200 |
| within_support_cell_shuffle | traditional_deltae_depth_ridge | 0.965 [0.953, 0.976] | 0.962 | 0.202 |

## Matched Support Performance
The table below repeats the primary metric only on support cells with at least
the configured minimum number of positive and negative rows. The support cell is
`run-family x depth x B2-amplitude-bin x saturation x dropout x baseline x
anomaly`, where dropout, baseline, and anomaly are raw-waveform proxies defined
in the script before model fitting. `support_collapse_fraction` is the fraction
of evaluated rows removed because their nuisance cell did not contain both
weak-label classes.

| method | matched-support ROC AUC | AP | purity at 80% efficiency | support-collapse fraction |
|---|---:|---:|---:|---:|
| support_residual_hybrid_mlp_new | 0.994 [0.987, 0.998] | 0.994 | 0.998 [0.996, 1.000] | 0.527 |
| mlp | 0.962 [0.936, 0.982] | 0.977 | 0.989 [0.944, 0.997] | 0.527 |
| traditional_deltae_depth_ridge | 0.962 [0.929, 0.986] | 0.975 | 0.983 [0.890, 0.997] | 0.527 |
| gradient_boosted_trees | 0.961 [0.931, 0.983] | 0.977 | 0.988 [0.919, 0.999] | 0.527 |
| ridge | 0.907 [0.843, 0.955] | 0.931 | 0.958 [0.716, 0.989] | 0.527 |
| cnn_1d | 0.812 [0.737, 0.883] | 0.842 | 0.784 [0.679, 0.890] | 0.527 |

## ML Minus Conventional
Positive deltas favor the named ML/NN method over the conventional ridge score.

| method | AUC delta vs traditional | 95% CI | bootstrap draws |
|---|---:|---:|---:|
| ridge | -0.026 | [-0.034, -0.017] | 500 |
| gradient_boosted_trees | 0.003 | [-0.001, 0.006] | 500 |
| mlp | 0.003 | [-0.000, 0.008] | 500 |
| cnn_1d | -0.085 | [-0.122, -0.052] | 500 |
| support_residual_hybrid_mlp_new | 0.012 | [0.005, 0.022] | 500 |

## Falsification, Nuisance, and Leakage Sentinels
The following probes deliberately restrict information channels. A high
charge-only score means the weak label is dominated by duplicate-readout
charge-scale closure; high depth-only or topology-only scores mean the apparent
PID axis is mostly support geometry; shuffled and target-permuted labels test
software and label-source leakage. Feature knockouts quantify whether the
classification survives removal of charge, depth/topology, or waveform samples.

| probe | ROC AUC | AP | ECE |
|---|---:|---:|---:|
| knockout_no_depth_topology_gbt | 0.996 [0.993, 0.998] | 0.996 [0.994, 0.998] | 0.240 |
| knockout_no_charge_gbt | 0.988 [0.982, 0.995] | 0.989 [0.984, 0.995] | 0.219 |
| knockout_no_waveform_gbt | 0.984 [0.976, 0.991] | 0.980 [0.974, 0.987] | 0.218 |
| sentinel_charge_only_ridge | 0.983 [0.974, 0.991] | 0.982 [0.973, 0.989] | 0.228 |
| sentinel_depth_only_ridge | 0.793 [0.766, 0.820] | 0.729 [0.702, 0.758] | 0.112 |
| sentinel_topology_only_ridge | 0.791 [0.736, 0.847] | 0.865 [0.820, 0.902] | 0.128 |
| sentinel_target_permutation_gbt | 0.487 [0.438, 0.540] | 0.472 [0.443, 0.509] | 0.156 |
| sentinel_group_event_order_ridge | 0.485 [0.478, 0.491] | 0.484 [0.478, 0.491] | 0.140 |
| sentinel_shuffled_label_gbt | 0.481 [0.425, 0.546] | 0.469 [0.435, 0.517] | 0.141 |

Interpretation ledger:

| probe | value | interpretation |
|---|---:|---|
| sentinel_charge_only_ridge | 0.983 | Allowed even-readout charge closure probe; high AUC means the weak label is mainly charge-scale support. |
| sentinel_depth_only_ridge | 0.793 | Penetration-depth-only probe; high AUC means range support explains the weak axis. |
| sentinel_topology_only_ridge | 0.791 | Topology/saturation-only probe; high AUC means terminal topology or saturation explains the weak axis. |
| sentinel_group_event_order_ridge | 0.485 | Run-family/event-order current proxy; high AUC indicates run-condition drift. |
| sentinel_shuffled_label_gbt | 0.481 | Shuffled-label software leakage guard; should be near chance. |
| sentinel_target_permutation_gbt | 0.487 | Within-depth target permutation guard; should be near chance if label-source ordering is not leaked. |
| knockout_no_charge_gbt | 0.988 | Feature-family knockout removing charge summary terms; residual AUC estimates waveform/support-only separability. |
| knockout_no_depth_topology_gbt | 0.996 | Feature-family knockout removing explicit depth/topology terms; residual AUC estimates charge/waveform separability. |
| knockout_no_waveform_gbt | 0.984 | Feature-family knockout removing waveform samples; high AUC means conventional support variables are sufficient. |

## Systematics
The dominant systematic is label circularity: the positive class is a quantile
of the odd duplicate-readout calibrated residual, and the even readout can share
real charge-scale drift. The leave-one-run split prevents row leakage but cannot
turn duplicate-readout closure into truth PID. The depth-only and topology-only
sentinels separate terminal/penetrating geometry leakage from residual waveform
information. Matched nuisance-support cells explicitly track saturation,
dropout, baseline, anomaly, amplitude, and run-family support loss. The
support-residual hybrid tests whether waveform shape survives after support
variables predict the samples; if it loses to charge/support sentinels, that is
evidence against a standalone B2 waveform PID claim. The CNN is compact by
design to avoid fitting a high-capacity classifier to a weak-label nuisance.

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
null-label and support ledger prevents PID adoption: global, within-run, and
within-run/depth relabellings collapse the score to chance, but the
within-support-cell shuffle remains highly separable. That failure mode means
the nuisance cell is still too coarse to remove all charge or waveform
substructure. Charge-only and no-waveform controls are already near the
traditional score, and support matching removes a documented fraction of rows.
The working hypothesis is therefore that the S15b weak axis is mostly a
charge/support closure with a small residual waveform component, not a
validated proton/deuteron separator. The queued follow-up asks whether external
PID truth can be joined at the event level; without that join, future PID uses
should remain explicitly weak-label diagnostics.

## Reproducibility
```bash
/home/billy/anaconda3/bin/python scripts/ticket_2376_p08_waveform_pid_bakeoff.py
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`,
`input_sha256.csv`, `reproduction_match_table.csv`, `method_metrics.csv`,
`ml_minus_traditional.csv`, `leakage_checks.csv`, `fold_audit.csv`,
`heldout_run_label_counts.csv`, `support_fraction_ledger.csv`,
`support_collapse_summary.csv`, `support_cells.csv`,
`null_label_stability.csv`, `matched_support_method_metrics.csv`,
`benchmark_balanced_counts.csv`, and `heldout_predictions.csv.gz`.
