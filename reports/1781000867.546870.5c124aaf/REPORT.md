# Study report: S10b - timing-template tau_eff/live-time fit

- **Ticket:** `1781000867.546870.5c124aaf`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-06-09
- **Inputs:** raw B-stack ROOT, runs 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57
- **Command:** `/home/billy/anaconda3/bin/python reports/1781000867.546870.5c124aaf/s10b_tau_eff_template_fit.py`

## Reproduction first
S10's occupancy number reproduces from the raw B-stack run selection before the new fit:
the combined requirement uses `mu_max=0.380` and `tau_eff=90 ns`, giving
`R_max=4.222 MHz`. The current-topology fractions also pass the S10 tolerances
(6/6 checks).

## Traditional method
For each run held out in turn, pulses were pedestal-subtracted, selected with `A > 1000 ADC`,
timed with CFD20, aligned by stave, median-combined, and fit on the post-peak tail with
`c + a exp(-t/tau)`. The reported live-time is the fitted crossing below 10% of pulse
amplitude, measured relative to CFD20 and weighted by the held-out run's stave composition.

- Traditional template live10: **124.79 ns**
  with held-out-run bootstrap 95% CI **[123.33, 126.36] ns**.
- 20% crossing analogue: **101.87 ns**.
- Empirical pulse live10 mean cross-check: **123.26 ns**.

This does not support treating `90 ns` as a measured detector live-time for this waveform
definition; the fitted window is materially longer.

## ML method
The ML method is a run-held-out standardized Ridge regressor from pulse-shape features to the
per-pulse 10% live-time target. It excludes run, event id, current, and direct
last-above-threshold width features. Each fold trains on all other runs and predicts the
held-out run.

- ML held-out live10: **123.19 ns**
  with held-out-run bootstrap 95% CI **[120.72, 125.55] ns**.
- Mean held-out MAE: **4.44 ns**.
- Mean held-out R2: **0.877**.

## Leakage checks
Leakage flags: **0**. The checks cover group-split R2, random row-split advantage,
shuffled-target prediction, and forbidden feature presence. See `leakage_checks.csv`.

## Conclusion
S10's `tau_eff=90 ns` remains reproducible as an assumption in the occupancy calculation, but
the data-driven timing-template live-time measurement favors about
**124.8 ns** at the 10% crossing. Rescaling the
combined S10 `R_max` by this measured window gives **3.05 MHz**,
instead of 4.22 MHz.

## Artifacts
`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`,
`poisson_rmax_table.csv`, `template_fit_by_run_stave.csv`, `heldout_run_summary.csv`,
`ml_heldout_by_run.csv`, `leakage_checks.csv`, and three PNG diagnostics are in this folder.
