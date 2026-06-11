# S15b: pulse-shape PID null-label stability audit

**Ticket:** 1781070978.487.042a7300  
**Worker:** testbeam-laptop-1  
**Input:** raw B-stack `HRDv` ROOT from `data/root/root`  
**Status:** null-label stability and falsification audit only; no truth PID adoption claim.

## Abstract
This S15b ticket asks whether raw HRD waveform or charge-shape PID weak labels
are stable under null relabellings, geometry/depth-only baselines, and matched
saturation, dropout, baseline, anomaly, amplitude, and run-family support. The
study reproduces the raw B-stack selected-pulse count exactly, rebuilds
duplicate-readout PSTAR/depth residual weak labels, and benchmarks a transparent
DeltaE-E/depth ridge score against ridge, gradient-boosted trees, MLP, 1D-CNN,
and a new support-residual hybrid MLP under leave-one-run-out evaluation. The
winner stored in `result.json` is
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

Matched nuisance-support audit:

| quantity | rows | fraction |
|---|---:|---:|
| evaluated_rows_before_support_matching | 15694 | 1.000 |
| evaluated_rows_in_matched_support_cells | 3734 | 0.238 |
| support_collapse_fraction | 11960 | 0.762 |
| matched_support_cells | 16 | 0.083 |

| method | ROC AUC | AP | Brier | ECE | purity at 80% efficiency |
|---|---:|---:|---:|---:|---:|
| support_residual_hybrid_mlp_new | 0.997 [0.994, 0.999] | 0.996 [0.994, 0.998] | 0.081 [0.076, 0.086] | 0.248 | 0.999 [0.998, 1.000] |
| gradient_boosted_trees | 0.988 [0.981, 0.995] | 0.989 [0.982, 0.995] | 0.093 [0.085, 0.102] | 0.219 | 0.996 [0.987, 1.000] |
| mlp | 0.988 [0.980, 0.994] | 0.988 [0.981, 0.994] | 0.094 [0.086, 0.103] | 0.216 | 0.997 [0.986, 0.999] |
| traditional_deltae_depth_ridge | 0.986 [0.976, 0.994] | 0.985 [0.975, 0.994] | 0.104 [0.095, 0.113] | 0.225 | 0.987 [0.962, 0.998] |
| ridge | 0.961 [0.945, 0.974] | 0.932 [0.920, 0.945] | 0.117 [0.106, 0.126] | 0.220 | 0.973 [0.933, 0.982] |
| cnn_1d | 0.903 [0.868, 0.941] | 0.857 [0.811, 0.910] | 0.141 [0.126, 0.156] | 0.175 | 0.845 [0.791, 0.910] |

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
| global_shuffle | cnn_1d | 0.502 [0.494, 0.510] | 0.500 | 0.191 |
| global_shuffle | support_residual_hybrid_mlp_new | 0.503 [0.493, 0.512] | 0.504 | 0.229 |
| global_shuffle | traditional_deltae_depth_ridge | 0.502 [0.492, 0.511] | 0.501 | 0.201 |
| within_run_depth_shuffle | cnn_1d | 0.501 [0.493, 0.510] | 0.500 | 0.191 |
| within_run_depth_shuffle | support_residual_hybrid_mlp_new | 0.496 [0.487, 0.505] | 0.499 | 0.229 |
| within_run_depth_shuffle | traditional_deltae_depth_ridge | 0.500 [0.493, 0.507] | 0.500 | 0.199 |
| within_run_shuffle | cnn_1d | 0.500 [0.492, 0.509] | 0.500 | 0.193 |
| within_run_shuffle | support_residual_hybrid_mlp_new | 0.497 [0.489, 0.504] | 0.498 | 0.231 |
| within_run_shuffle | traditional_deltae_depth_ridge | 0.496 [0.487, 0.504] | 0.495 | 0.202 |
| within_support_cell_shuffle | cnn_1d | 0.884 [0.862, 0.902] | 0.840 | 0.153 |
| within_support_cell_shuffle | support_residual_hybrid_mlp_new | 0.961 [0.951, 0.970] | 0.957 | 0.199 |
| within_support_cell_shuffle | traditional_deltae_depth_ridge | 0.966 [0.954, 0.978] | 0.965 | 0.204 |

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
| support_residual_hybrid_mlp_new | 0.968 [0.939, 0.987] | 0.989 | 0.995 [0.982, 0.999] | 0.762 |
| gradient_boosted_trees | 0.910 [0.868, 0.955] | 0.971 | 0.956 [0.881, 0.991] | 0.762 |
| mlp | 0.903 [0.848, 0.950] | 0.969 | 0.940 [0.840, 0.989] | 0.762 |
| traditional_deltae_depth_ridge | 0.851 [0.767, 0.925] | 0.953 | 0.858 [0.747, 0.981] | 0.762 |
| ridge | 0.786 [0.695, 0.869] | 0.907 | 0.800 [0.689, 0.966] | 0.762 |
| cnn_1d | 0.647 [0.546, 0.794] | 0.834 | 0.814 [0.697, 0.923] | 0.762 |

## ML Minus Conventional
Positive deltas favor the named ML/NN method over the conventional ridge score.

| method | AUC delta vs traditional | 95% CI | bootstrap draws |
|---|---:|---:|---:|
| ridge | -0.025 | [-0.032, -0.018] | 500 |
| gradient_boosted_trees | 0.002 | [-0.000, 0.006] | 500 |
| mlp | 0.002 | [-0.001, 0.005] | 500 |
| cnn_1d | -0.083 | [-0.112, -0.053] | 500 |
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
| knockout_no_depth_topology_gbt | 0.996 [0.993, 0.998] | 0.996 [0.993, 0.998] | 0.239 |
| knockout_no_charge_gbt | 0.988 [0.980, 0.995] | 0.989 [0.982, 0.995] | 0.220 |
| knockout_no_waveform_gbt | 0.985 [0.976, 0.992] | 0.983 [0.975, 0.990] | 0.221 |
| sentinel_charge_only_ridge | 0.984 [0.975, 0.992] | 0.983 [0.973, 0.991] | 0.231 |
| sentinel_depth_only_ridge | 0.806 [0.778, 0.834] | 0.741 [0.715, 0.772] | 0.114 |
| sentinel_topology_only_ridge | 0.788 [0.738, 0.847] | 0.864 [0.825, 0.903] | 0.127 |
| sentinel_shuffled_label_gbt | 0.532 [0.491, 0.577] | 0.504 [0.478, 0.536] | 0.109 |
| sentinel_group_event_order_ridge | 0.477 [0.466, 0.487] | 0.476 [0.466, 0.486] | 0.165 |
| sentinel_target_permutation_gbt | 0.459 [0.408, 0.509] | 0.458 [0.429, 0.494] | 0.136 |

Interpretation ledger:

| probe | value | interpretation |
|---|---:|---|
| sentinel_charge_only_ridge | 0.984 | Allowed even-readout charge closure probe; high AUC means the weak label is mainly charge-scale support. |
| sentinel_depth_only_ridge | 0.806 | Penetration-depth-only probe; high AUC means range support explains the weak axis. |
| sentinel_topology_only_ridge | 0.788 | Topology/saturation-only probe; high AUC means terminal topology or saturation explains the weak axis. |
| sentinel_group_event_order_ridge | 0.477 | Run-family/event-order current proxy; high AUC indicates run-condition drift. |
| sentinel_shuffled_label_gbt | 0.532 | Shuffled-label software leakage guard; should be near chance. |
| sentinel_target_permutation_gbt | 0.459 | Within-depth target permutation guard; should be near chance if label-source ordering is not leaked. |
| knockout_no_charge_gbt | 0.988 | Feature-family knockout removing charge summary terms; residual AUC estimates waveform/support-only separability. |
| knockout_no_depth_topology_gbt | 0.996 | Feature-family knockout removing explicit depth/topology terms; residual AUC estimates charge/waveform separability. |
| knockout_no_waveform_gbt | 0.985 | Feature-family knockout removing waveform samples; high AUC means conventional support variables are sufficient. |

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
/home/billy/anaconda3/bin/python scripts/s15b_1781070978_487_042a7300_pid_null_label_stability_audit.py --config configs/s15b_1781070978_487_042a7300_pid_null_label_stability_audit.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`,
`input_sha256.csv`, `reproduction_match_table.csv`, `method_metrics.csv`,
`ml_minus_traditional.csv`, `leakage_checks.csv`, `fold_audit.csv`,
`heldout_run_label_counts.csv`, `support_fraction_ledger.csv`,
`support_collapse_summary.csv`, `support_cells.csv`,
`null_label_stability.csv`, `matched_support_method_metrics.csv`,
`benchmark_balanced_counts.csv`, and `heldout_predictions.csv.gz`.
