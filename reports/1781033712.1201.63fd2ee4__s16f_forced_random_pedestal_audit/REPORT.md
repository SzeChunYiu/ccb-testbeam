# S16f: Dedicated B-Stack Forced/Random Pedestal Audit And Fallback Veto Benchmark

- **Study ID:** S16f
- **Ticket:** 1781033712.1201.63fd2ee4
- **Author:** testbeam-laptop-4
- **Date:** 2026-06-10
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `2453b203bc4db1178d3d4e56e58cfeebf2220cd5`
- **Config:** `configs/s16f_1781033712_1201_63fd2ee4_forced_random_pedestal_audit.json`

## 0. Question And Pre-Registered Decision Rule

The ticket asks whether S16e can be rerun with a true non-beam-trigger B-stack
forced/random pedestal ROOT sample instead of physics-event pre-trigger samples.
The decision rule is:

1. Inventory accessible raw B-stack ROOT inputs and trigger codes.
2. If a dedicated forced/random pedestal ROOT source is present, use it as the
   pedestal target for the timing-tail study.
3. If no such source is present, record the absence as the primary result and
   run the established pre-trigger fallback benchmark without promoting it to a
   true-pedestal validation.

## 1. Dedicated Pedestal Source Audit

The accessible mirror contains `hrdb_run_NNNN.root` files under `data/root/root`.
Each file exposes `h101` with `TRIGGER`, `EVENTNO`, `EVT`, `NO`, `HRD`, `HRDI`,
and `HRDv`.  The audit below is from direct ROOT inspection, not from cached
tables.

| Audit item | Value |
|---|---:|
| B-stack raw ROOT files | 53 |
| nonempty B-stack raw ROOT files | 51 |
| unique TRIGGER codes | 1 |
| files with TRIGGER != 1 | 0 |
| keyword-matched ROOT files for forced/random/pedestal | 0 |
| dedicated pedestal ROOT found | no |

All nonempty B-stack raw ROOT files carry trigger code `1` only.  The keyword
search over accessible data and repo metadata found no ROOT file whose name
indicates forced, random, or pedestal acquisition.  Therefore the requested
true-pedestal substitution is not possible with the current data mirror.  The
rest of this report is a fallback benchmark on physics-event pre-trigger
samples and must not be cited as a true forced/random pedestal validation.

## 2. Raw ROOT Reproduction Gate

The raw reproduction gate reads `h101/HRDv`, reshapes each event to 8 channels
by 18 samples, subtracts the median of samples 0--3 per B stave, and counts
pulses with baseline-subtracted amplitude `A > 1000 ADC`.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | yes |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | 0 | yes |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | 0 | yes |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | 0 | yes |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | 0 | yes |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | 0 | yes |

For timing, events must have B4, B6, and B8 all passing the same cut.  This
produced `3820` Sample-II all-downstream events and `11460` pair
residuals across held-out runs [58, 59, 60, 61, 62, 63, 65].

## 3. Methods

For pair `i=(a,b)`, the residual is

```text
r_i = (t_a - x_a/v) - (t_b - x_b/v),
```

where `t` is CFD20 time, `x` is the B-stack position at 2.0 cm spacing,
and `1/v = 0.078` ns/cm.  In each leave-one-run-out fold, pair centers
`m_p` are train-run medians only, and the timing-tail proxy label is

```text
y_i = 1(|r_i - m_p(i)| > 5.0 ns).
```

The strong traditional method is a train-frozen empirical quantile envelope over
pre-trigger-only proxies: maximum absolute pre-trigger amplitude, peak-to-peak
range, RMS, absolute slope, and last-minus-first excursion.  Its score is

```text
s_i = max_j F_hat_train,j(z_ij).
```

It is compared with ridge, gradient-boosted trees, MLP, 1D-CNN, and the new
`siamese_cnn_meta` architecture.  The Siamese model applies a shared
convolutional branch to the two stave pre-trigger traces, concatenates both
embeddings and their absolute difference, then adds tabular pre-trigger
metadata.  All models exclude run id, event id, residuals, labels, post-trigger
samples, amplitude, and peak sample.  Thresholds are selected on train runs
only from the configured quantile grid with minimum train timing efficiency
0.85.

## 4. Head-To-Head Benchmark With Bootstrap CIs

Primary metric: held-out post-veto tail fraction, with timing efficiency and
sigma68 reported as safety metrics.  Confidence intervals resample runs and then
events within each sampled run.

| Method | Timing efficiency [95% CI] | Tail capture [95% CI] | Post-veto tail fraction [95% CI] | Sigma68 after [95% CI] ns | Delta sigma68 [95% CI] ns | AUC | AP |
|---|---:|---:|---:|---:|---:|---:|---:|
| traditional_quantile | 0.900 [0.885, 0.918] | 0.316 [0.235, 0.467] | 0.0115 [0.0069, 0.0149] | 1.565 [1.518, 1.607] | -0.126 [-0.158, -0.104] | 0.701 | 0.051 |
| ridge | 0.899 [0.889, 0.912] | 0.489 [0.407, 0.637] | 0.0086 [0.0044, 0.0121] | 1.561 [1.521, 1.610] | -0.130 [-0.165, -0.109] | 0.732 | 0.149 |
| gradient_boosted_trees | 0.899 [0.890, 0.908] | 0.517 [0.414, 0.642] | 0.0082 [0.0048, 0.0107] | 1.625 [1.572, 1.669] | -0.067 [-0.101, -0.042] | 0.745 | 0.254 |
| mlp | 0.899 [0.888, 0.908] | 0.454 [0.256, 0.574] | 0.0092 [0.0069, 0.0113] | 1.655 [1.615, 1.735] | -0.036 [-0.067, -0.005] | 0.667 | 0.152 |
| cnn1d | 0.910 [0.883, 0.937] | 0.534 [0.387, 0.660] | 0.0078 [0.0047, 0.0106] | 1.622 [1.580, 1.680] | -0.069 [-0.086, -0.042] | 0.755 | 0.306 |
| siamese_cnn_meta | 0.901 [0.888, 0.917] | 0.546 [0.426, 0.665] | 0.0077 [0.0044, 0.0111] | 1.617 [1.559, 1.665] | -0.074 [-0.096, -0.054] | 0.748 | 0.314 |

Winner by support-constrained post-veto tail fraction: **siamese_cnn_meta**.  The
baseline pre-veto tail fraction was `0.0152`, with baseline
sigma68 `1.691 ns`.

Per-held-out-run winner metrics:

| Held-out run | n pairs | efficiency | tail capture | post-veto tail fraction | sigma68 after ns | delta sigma68 ns |
|---:|---:|---:|---:|---:|---:|---:|
| 58 | 219 | 0.922 | 1.000 | 0.0000 | 1.542 | -0.098 |
| 59 | 2289 | 0.923 | 0.611 | 0.0066 | 1.552 | -0.056 |
| 60 | 2424 | 0.876 | 0.462 | 0.0099 | 1.591 | -0.067 |
| 61 | 2799 | 0.900 | 0.544 | 0.0103 | 1.627 | -0.070 |
| 62 | 2421 | 0.895 | 0.652 | 0.0037 | 1.591 | -0.095 |
| 63 | 1110 | 0.911 | 0.412 | 0.0099 | 1.671 | -0.148 |
| 65 | 198 | 0.949 | 0.000 | 0.0000 | 1.561 | -0.003 |

## 5. Falsification And Leakage Checks

The shuffled-proxy control permutes train-run pre-trigger proxies relative to
labels before fitting each method.  A method is rejected if its median
tail-capture advantage over the shuffled control is below -0.05.  Splits,
normalizers, centers, thresholds, and neural training are fold-local.

| Check | Value | Pass? |
|---|---:|---|
| loro_runs_match_config | 58,59,60,61,62,63,65 | yes |
| train_heldout_event_id_overlap_max | 0 | yes |
| features_exclude_run_event_residual_labels |  | yes |
| all_predictions_finite | 137520 | yes |
| one_row_per_method_fold_shuffled_state | 84 | yes |
| cnn1d_actual_tail_capture_ge_shuffled_proxy_median | 0.47368421052631576 | yes |
| gradient_boosted_trees_actual_tail_capture_ge_shuffled_proxy_median | 0.24561403508771928 | yes |
| mlp_actual_tail_capture_ge_shuffled_proxy_median | 0.33333333333333337 | yes |
| ridge_actual_tail_capture_ge_shuffled_proxy_median | 0.3333333333333333 | yes |
| siamese_cnn_meta_actual_tail_capture_ge_shuffled_proxy_median | 0.456140350877193 | yes |
| traditional_quantile_actual_tail_capture_ge_shuffled_proxy_median | 0.19444444444444448 | yes |

## 6. Systematics, Caveats, And Interpretation

The key systematic is source validity: no accessible dedicated B-stack
forced/random pedestal ROOT sample was found, and all nonempty B-stack raw ROOT
runs report trigger code `1`.  This means the fallback benchmark measures how
well pre-trigger summaries identify timing-tail pairs inside beam-triggered
physics events.  It does not validate a true pedestal estimator.

The tail label is also a proxy.  It is useful for operational veto design, but
it is not a physical contamination truth label.  Sigma68 can improve by
deleting difficult events, so efficiency and tail capture are always reported
beside width.  Pair rows share events, so uncertainty is estimated by
run/event bootstrap rather than iid pair bootstrap.  Multiple methods were
compared, so the winner is an operational model choice under a fixed metric,
not a discovery claim.

## 7. Verdict And Next Experiment

The requested true-pedestal rerun cannot be completed from the accessible data:
there is no dedicated forced/random B-stack ROOT source in the current mirror.
As a fallback timing-tail veto benchmark, **siamese_cnn_meta** gives the lowest held-out
post-veto tail fraction.  Because the source audit failed, this result should be
used only as a pre-trigger diagnostic until a real pedestal acquisition is added.

The next highest-information experiment is to ingest or record an external
forced/random B-stack pedestal ROOT run with DAQ trigger-code provenance, then
rerun this exact benchmark with the physics-event pre-trigger fallback frozen as
the negative control.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16f_1781033712_1201_63fd2ee4_forced_random_pedestal_audit.py --config configs/s16f_1781033712_1201_63fd2ee4_forced_random_pedestal_audit.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`,
`trigger_inventory.csv`, `source_inventory.csv`, `input_sha256.csv`,
`reproduction_match_table.csv`, `sample_ii_pair_table.csv.gz`,
`fold_metrics.csv`, `heldout_predictions.csv.gz`, `threshold_scans.csv`,
`head_to_head_benchmark.csv`, `bootstrap_cis.csv`, and `leakage_checks.csv`.
