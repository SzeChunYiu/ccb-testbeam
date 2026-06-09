# Study report: S10c - threshold-scan tau_eff stability

- **Ticket:** `1781007337.1308.7dc86005`
- **Worker:** `testbeam-laptop-1`
- **Date:** 2026-06-09
- **Inputs:** raw B-stack ROOT, runs 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57
- **Command:** `/home/billy/anaconda3/bin/python reports/1781007337.1308.7dc86005/s10c_threshold_scan_tau_eff.py`

## Reproduction first
The S10b anchor was recomputed from raw B-stack ROOT before the scan. The 10% template
live-time is **124.790 ns**, versus the S10b reported **124.790 ns**
(`delta=0.0000 ns`). The S10 occupancy reproduction also remains
intact: `mu_max=0.380`, `tau_eff=90 ns`, `R_max=4.222 MHz`, and
6/6 current-topology checks pass.

## Traditional method
For each run, selected pulses (`A > 1000 ADC`) were pedestal-subtracted, timed with CFD20,
aligned by stave, median-combined, and fit on the post-peak tail with `c + a exp(-t/tau)`.
The scan uses 5%, 10%, 20%, and a train-derived noise floor (`max(3*MAD_baseline/A, 0.5%)`),
weighted by the held-out run's stave composition. CIs bootstrap held-out runs.

- 5%: traditional **141.06 ns** (95% CI [139.29, 143.01]), ML **124.75 ns** (95% CI [122.59, 126.69]).
- 10%: traditional **124.79 ns** (95% CI [123.32, 126.33]), ML **123.22 ns** (95% CI [120.71, 125.61]).
- 20%: traditional **101.87 ns** (95% CI [100.90, 102.83]), ML **119.18 ns** (95% CI [115.60, 122.48]).
- noise floor: traditional **161.18 ns** (95% CI [158.76, 163.61]), ML **120.30 ns** (95% CI [117.03, 123.22]).

The 124.8 ns live10 result is threshold-definition dependent in magnitude, but the qualitative
S10b conclusion is stable: every scanned threshold stays above 90 ns. The 20% definition is the shortest scanned crossing and still
lands above 90 ns.

## ML method
The ML method is a run-held-out standardized Ridge regressor from pulse-shape features to
per-pulse live-time targets. It excludes run, event id, current, and direct last-above-threshold
width features. Live10 ML gives **123.22 ns**,
mean MAE **4.16 ns**, and mean R2
**0.884**.

## Leakage checks
Leakage flags: **0**. The checks cover run-split R2, random row-split advantage,
shuffled-target prediction per target, and forbidden feature presence. See `leakage_checks.csv`.

## Conclusion
The 10% template live-time is reproduced at **124.8 ns**. Moving the crossing threshold
changes the absolute window (5% and noise-floor are longer, 20% is shorter), but it does not
restore the original 90 ns assumption. The 10% rescaled combined `R_max` is
**3.05 MHz**; the noise-floor analogue is
**2.36 MHz**.

## Artifacts
`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`,
`poisson_rmax_table.csv`, `template_fit_by_run_stave.csv`, `heldout_run_summary.csv`,
`threshold_summary.csv`, `ml_heldout_by_run.csv`, `leakage_checks.csv`, and three PNG
diagnostics are in this folder.
