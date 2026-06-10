# S02i: Pretrigger-Proxy Timing Transfer Atom Map

- **Study ID:** S02i
- **Ticket:** 1781032083.463.2d9c6a45
- **Worker:** testbeam-laptop-4
- **Date:** 2026-06-10
- **Input:** raw B-stack `h101/HRDv` ROOT files under `data/root/root`
- **Split:** Sample-II leave-one-run-out by run, held-out runs [58, 59, 60, 61, 62, 63, 65]
- **Primary metric:** mean held-out-run pairwise sigma68 after correction, with run/event bootstrap 95% CIs
- **Git commit:** `4b86213cd4ec385feabd43c5c84d649d6757dc20`

## 1. Question And Reproduction Gate

The ticket asks which S16e-style pretrigger proxy atoms improve S02b/S02d timing closure under leave-one-run-out transfer, and where ML residual terms transfer worse than frozen traditional pretrigger corrections. Before any modeling, the script reruns the selected-pulse count gate directly from raw ROOT: the median of samples 0-3 is subtracted per B stave, and pulses with baseline-subtracted amplitude `A > 1000 ADC` are counted.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | yes |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | 0 | yes |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | 0 | yes |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | 0 | yes |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | 0 | yes |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | 0 | yes |

The timing benchmark then keeps events in held-out runs where B4, B6, and B8 all pass the same cut. This produced `3820` events and `11460` pair residual rows.

## 2. Timing Target

For pair \(p=(a,b)\) in event \(i\), the uncorrected CFD20 residual is

\[
r_i = \left(t_{ia}^{20} - x_a/v\right) - \left(t_{ib}^{20} - x_b/v\right),
\]

with stave spacing \(x\) in steps of `2.0` cm and \(1/v = 0.078\) ns/cm. A model \(f_m(X_i)\) trained only on non-held-out runs predicts the residual, and the evaluated residual is

\[
\epsilon_i^{(m)} = r_i - f_m(X_i).
\]

The headline resolution is

\[
\sigma_{68}(\epsilon) = \frac{Q_{84}(\epsilon)-Q_{16}(\epsilon)}{2},
\]

reported both per held-out run and after a paired run/event bootstrap. The tail metric is \(P(|\epsilon| > 5.0\,\mathrm{ns})\).

## 3. Traditional Atom Map

The frozen traditional comparator is a robust Huber regression on analytic timewalk features: pair identity, log mean amplitude, log amplitude ratio, inverse minimum amplitude, amplitude asymmetry, minimum amplitude, maximum peak sample, and peak-sample difference. The atom-map rows add exactly one S16e-style pretrigger atom family at a time:

- `atom_mean`: pair mean pretrigger level and inter-stave mean difference.
- `atom_slope`: pair mean pretrigger slope and inter-stave slope difference.
- `atom_early_minus_late`: samples 0-1 minus samples 2-3, averaged over staves and differenced across staves.
- `atom_quiet_proxy_bin`: train-run quartile bin of pair pretrigger RMS.
- `atom_large_lowering_flag`: train-run 95th-percentile flag for sample-0 minus sample-3 lowering.

The quiet-bin and lowering thresholds are recalculated inside each fold from training runs only.

## 4. ML And Neural Benchmarks

All ML methods use the same folds and the same train-only feature transforms. None uses run id, event id, held-out labels, or corrected residuals as inputs.

- `ridge`: Ridge regression with alpha selected by inner leave-one-train-run-out sigma68.
- `gradient_boosted_trees`: histogram gradient-boosted absolute-error regressor.
- `mlp`: two-layer MLP regressor on standardized tabular atoms.
- `cnn1d`: compact 1D convolutional regressor using only the two four-sample pretrigger traces.
- `siamese_cnn_meta`: new pair-symmetric architecture with a shared convolutional branch for each stave trace, absolute embedding difference, and tabular atom metadata.

## 5. Head-To-Head Results

| Method | Mean run sigma68 ns [95% CI] | Pooled sigma68 ns [95% CI] | Tail frac [95% CI] | MAE ns [95% CI] |
|---|---:|---:|---:|---:|
| uncorrected_cfd20 | 3.141 [3.031, 3.251] | 3.150 [3.005, 3.303] | 0.2180 [0.1855, 0.2522] | 3.510 [3.326, 3.731] |
| traditional_base_huber | 1.448 [1.351, 1.535] | 1.440 [1.390, 1.511] | 0.0148 [0.0100, 0.0192] | 1.567 [1.375, 1.752] |
| traditional_atom_mean | 1.430 [1.347, 1.514] | 1.399 [1.357, 1.467] | 0.0143 [0.0100, 0.0187] | 1.545 [1.361, 1.717] |
| traditional_atom_slope | 1.366 [1.293, 1.446] | 1.345 [1.301, 1.393] | 0.0136 [0.0093, 0.0175] | 1.489 [1.295, 1.694] |
| traditional_atom_early_minus_late | 1.368 [1.298, 1.437] | 1.343 [1.299, 1.400] | 0.0136 [0.0090, 0.0180] | 1.489 [1.312, 1.671] |
| traditional_atom_quiet_proxy_bin | 1.470 [1.371, 1.544] | 1.431 [1.390, 1.499] | 0.0142 [0.0099, 0.0189] | 1.560 [1.383, 1.730] |
| traditional_atom_large_lowering_flag | 1.368 [1.294, 1.447] | 1.351 [1.304, 1.403] | 0.0137 [0.0098, 0.0177] | 1.492 [1.312, 1.711] |
| ridge | 1.860 [1.742, 1.986] | 1.843 [1.678, 2.050] | 0.0371 [0.0268, 0.0493] | 1.942 [1.718, 2.190] |
| gradient_boosted_trees | 1.170 [1.103, 1.236] | 1.142 [1.101, 1.185] | 0.0123 [0.0083, 0.0167] | 1.315 [1.135, 1.494] |
| mlp | 1.364 [1.317, 1.418] | 1.354 [1.293, 1.412] | 0.0189 [0.0144, 0.0236] | 1.463 [1.268, 1.667] |
| cnn1d | 2.696 [2.585, 2.815] | 2.680 [2.548, 2.849] | 0.0476 [0.0418, 0.0526] | 2.391 [2.201, 2.632] |
| siamese_cnn_meta | 1.141 [1.073, 1.211] | 1.116 [1.077, 1.164] | 0.0129 [0.0082, 0.0175] | 1.306 [1.125, 1.536] |

Winner by mean held-out-run sigma68: **siamese_cnn_meta**. The uncorrected CFD20 baseline mean run sigma68 is `3.141 ns`; the best traditional row is `traditional_atom_slope` at `1.366 ns`; the winner is `1.141 ns`.

Paired ML-minus-traditional and method-minus-traditional deltas use the best traditional atom row as comparator:

| Method | Comparator | Delta pooled sigma68 ns [95% CI] |
|---|---|---:|
| siamese_cnn_meta | traditional_atom_slope | -0.229 [-0.264, -0.198] |
| gradient_boosted_trees | traditional_atom_slope | -0.203 [-0.237, -0.171] |
| traditional_atom_early_minus_late | traditional_atom_slope | -0.002 [-0.007, +0.008] |
| traditional_atom_large_lowering_flag | traditional_atom_slope | +0.005 [-0.009, +0.016] |
| mlp | traditional_atom_slope | +0.009 [-0.051, +0.078] |
| traditional_atom_mean | traditional_atom_slope | +0.054 [+0.038, +0.090] |
| traditional_atom_quiet_proxy_bin | traditional_atom_slope | +0.086 [+0.057, +0.124] |
| traditional_base_huber | traditional_atom_slope | +0.095 [+0.065, +0.129] |
| ridge | traditional_atom_slope | +0.498 [+0.364, +0.666] |
| cnn1d | traditional_atom_slope | +1.335 [+1.161, +1.504] |
| uncorrected_cfd20 | traditional_atom_slope | +1.805 [+1.659, +1.934] |

Representative per-run rows:

| Held-out run | Method | n events | sigma68 ns | tail frac | full RMS ns |
|---:|---|---:|---:|---:|---:|
| 58 | siamese_cnn_meta | 73 | 1.038 | 0.0228 | 4.788 |
| 58 | traditional_base_huber | 73 | 1.234 | 0.0183 | 4.378 |
| 58 | uncorrected_cfd20 | 73 | 3.115 | 0.2283 | 5.704 |
| 59 | siamese_cnn_meta | 763 | 1.066 | 0.0162 | 3.803 |
| 59 | traditional_base_huber | 763 | 1.367 | 0.0188 | 5.329 |
| 59 | uncorrected_cfd20 | 763 | 3.190 | 0.2294 | 6.434 |
| 60 | siamese_cnn_meta | 808 | 1.077 | 0.0157 | 7.808 |
| 60 | traditional_base_huber | 808 | 1.394 | 0.0144 | 6.781 |
| 60 | uncorrected_cfd20 | 808 | 3.139 | 0.2232 | 7.858 |
| 61 | siamese_cnn_meta | 933 | 1.106 | 0.0161 | 5.651 |
| 61 | traditional_base_huber | 933 | 1.420 | 0.0171 | 6.155 |
| 61 | uncorrected_cfd20 | 933 | 2.914 | 0.1615 | 7.105 |
| 62 | siamese_cnn_meta | 807 | 1.149 | 0.0050 | 3.132 |
| 62 | traditional_base_huber | 807 | 1.426 | 0.0091 | 4.327 |
| 62 | uncorrected_cfd20 | 807 | 3.232 | 0.2317 | 5.611 |
| 63 | siamese_cnn_meta | 370 | 1.145 | 0.0099 | 5.738 |
| 63 | traditional_base_huber | 370 | 1.556 | 0.0153 | 6.107 |
| 63 | uncorrected_cfd20 | 370 | 3.404 | 0.2811 | 7.196 |
| 65 | siamese_cnn_meta | 66 | 1.409 | 0.0000 | 1.348 |
| 65 | traditional_base_huber | 66 | 1.737 | 0.0051 | 1.829 |
| 65 | uncorrected_cfd20 | 66 | 2.993 | 0.2879 | 4.119 |

Per-stave-pair summaries are written to `per_pair_summary.csv`. Composition drift of the pretrigger atom distribution for each held-out run is in `composition_drift.csv`; the mean absolute atom z-drift ranges from `0.015` to `0.323`.

## 6. Leakage, Systematics, And Caveats

| Check | Value | Pass? |
|---|---:|---|
| loro_runs_match_config | 58,59,60,61,62,63,65 | yes |
| train_heldout_event_id_overlap_max | 0 | yes |
| features_exclude_run_event_residual_labels |  | yes |
| all_corrected_residuals_finite | 137520 | yes |
| one_prediction_per_method_pair_row | 1 | yes |

The analysis is intentionally a transfer benchmark, not a causal proof that pretrigger structure creates timing tails. Pair residual rows are not independent because each event contributes three pairs; therefore CIs resample runs and then events within sampled runs. The raw pretrigger window has only four samples, so neural architectures are deliberately small and regularized. A method that improves sigma68 may still change the accepted timing-support composition; downstream charge, PID, and energy consumers should audit support drift before adopting the correction.

The traditional Huber rows are strong but still approximate the larger S02b template/timewalk family: they keep analytic amplitude and peak-time terms and add pretrigger atoms one at a time. The ML rows are allowed to combine all atoms, so their failure or success should be read as whether flexible residual learning transfers beyond the frozen atom map, not as whether pretrigger atoms carry no information.

## 7. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s02i_1781032083_463_2d9c6a45_pretrigger_atom_transfer.py --config configs/s02i_1781032083_463_2d9c6a45_pretrigger_atom_transfer.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `sample_ii_pair_table.csv.gz`, `per_run_metrics.csv`, `method_summary.csv`, `method_delta_vs_best_traditional.csv`, `per_pair_summary.csv`, `composition_drift.csv`, `leakage_checks.csv`, `heldout_predictions.csv.gz`, and figures.
