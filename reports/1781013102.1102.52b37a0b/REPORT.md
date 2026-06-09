# S10e: threshold-scan tau_eff into pile-up separability limits

- **Ticket:** `1781013102.1102.52b37a0b`
- **Worker:** `testbeam-laptop-1`
- **Date:** 2026-06-09
- **Inputs:** raw B-stack HRD ROOT under `data/root/root`
- **Command:** `/home/billy/anaconda3/bin/python reports/1781013102.1102.52b37a0b/s10e_threshold_rmax_operational.py`

## Reproduction First

The raw ROOT gate passes before the new analysis: all S10 current-topology checks pass, the S10b
10% live-time anchor is reproduced at **124.790 ns**, and
the 10% measured-tau combined Rmax is **3.045 MHz**.

## Threshold Live-Time

Traditional values are run-held-out stave-weighted median-template tail crossings. ML values are
run-held-out Ridge predictions from pulse-shape features only; run, event id, current, and direct
last-above-threshold width are excluded.

| threshold | traditional tau_eff ns | ML tau_eff ns | ML mean R2 |
|---|---:|---:|---:|
| 5% | 141.06 [139.26, 142.98] | 124.75 [122.58, 126.80] | 0.884 |
| 10% | 124.79 [123.33, 126.29] | 123.22 [120.70, 125.70] | 0.884 |
| 20% | 101.87 [100.94, 102.86] | 119.18 [115.68, 122.46] | 0.890 |
| noise floor | 161.18 [158.89, 163.58] | 120.30 [116.97, 123.30] | 0.815 |

## Rmax Rescaling

The table below shows the combined timing-plus-charge requirement (`mu_max=0.380`). Full timing,
amplitude, charge, and combined rows are in `rmax_by_threshold_requirement.csv`.

| threshold | tau_eff ns | combined Rmax MHz | ratio vs original 90 ns |
|---|---:|---:|---:|
| 5% | 141.06 | 2.694 [2.658, 2.729] | 0.638 |
| 10% | 124.79 | 3.045 [3.009, 3.081] | 0.721 |
| 20% | 101.87 | 3.730 [3.694, 3.765] | 0.884 |
| noise floor | 161.18 | 2.358 [2.323, 2.392] | 0.558 |

The original 90 ns assumption gives **4.222 MHz** for the combined constraint. All raw-template
threshold definitions are longer than 90 ns and therefore reduce Rmax: the 20% definition is the
least restrictive at **3.730 MHz**, while the
noise-floor definition is the most restrictive at **2.358 MHz**.

## Operational Separability

The operational closure uses raw-pulse-derived templates plus real residuals, split by source run
(`train=[58, 59, 60, 61, 62]`, `heldout=[63, 65]`). The traditional method is a bounded
two-pulse template fit; ML is the compact MLP classifier/regressor. Bootstrap CIs resample held-out
runs.

| method | resolvable delay ns | 95% CI ns | AP | time RMS ns | charge bias | failure rate |
|---|---:|---:|---:|---:|---:|---:|
| constrained template fit | >=60.0 | [15.0, 60.0] | 0.752 | 13.81 | -0.023 | 0.170 |
| compact ML | 40.0 | [15.0, 60.0] | 0.848 | 9.94 | -0.005 | 0.300 |

Closest threshold-definition matches to the operational delays:

| operational source | closest threshold | tau_eff ns | operational delay ns | difference ns |
|---|---:|---:|---:|---:|
| compact_mlp_classifier_regressor | 20% | 101.87 | 40.0 | 61.87 |
| constrained_template_fit | 20% | 101.87 | >=60.0 | 41.87 |

## Leakage And Caution

Leakage flags: **0** for threshold ML and **4/4**
operational checks pass. When ML appears better than the constrained fit, it is treated as a
diagnostic rather than the production limit: its CI reaches the largest tested separation and the
per-run stable-delay table contains non-finite ML entries. See `run_heldout_resolvability.csv` and
`operational_leakage_checks.csv`.

## Conclusion

For S10 rate limits, the defensible raw-template threshold definition is **20%**:
it is the scanned definition closest to both operational closures and gives the largest measured
combined Rmax without returning to the unsupported 90 ns assumption. Numerically, use the 20%
combined limit **3.730 MHz** as the operational separability-oriented
threshold-scan value; retain 90 ns only as the historical assumption.
