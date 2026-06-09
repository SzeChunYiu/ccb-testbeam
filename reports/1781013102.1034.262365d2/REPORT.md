# Study report: S10d follow-up - live-time threshold reconciliation

- **Ticket:** `1781013102.1034.262365d2`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-06-09
- **Inputs:** raw B-stack ROOT, runs 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57
- **Config:** `configs/s10d_1781013102_1034_262365d2_reconcile_livetime.json`

## Reproduction first

The S10c raw-ROOT pipeline was rerun before the reconciliation. It reproduced the S10c/S10b
10% template live-time anchor at **124.790 ns** and passed
6/6
S10 current-topology checks. The 20% and noise-floor S10c anchors were also reproduced within
the configured tolerance; see `reproduction_match_table.csv`.

## Methods

The traditional template method is the S10c leave-one-run-out median waveform tail fit
`c + a exp(-t/tau)`, weighted by held-out run stave composition. The operational traditional
cross-check is the direct per-pulse last-above-threshold live-time measured on the 18 sampled
ADC points. The ML method is the S10c run-held-out standardized Ridge regressor from pulse-shape
features to that operational target. CIs bootstrap held-out runs.

## Reconciliation

- 5%: template 141.06 ns, empirical 124.88 ns, ML 124.75 ns; observable endpoint 130.28 ns, censored 0.94; template exponential extrapolates past the per-pulse acquisition window.
- 10%: template 124.79 ns, empirical 123.26 ns, ML 123.22 ns; observable endpoint 130.28 ns, censored 0.86; template crossing and empirical operation agree within 10 ns.
- 20%: template 101.87 ns, empirical 119.03 ns, ML 119.18 ns; observable endpoint 130.28 ns, censored 0.74; empirical last-above is inflated by late samples/noise relative to smooth crossing.
- noise floor: template 161.18 ns, empirical 120.37 ns, ML 120.30 ns; observable endpoint 130.28 ns, censored 0.92; template exponential extrapolates past the per-pulse acquisition window.

The divergence is definitional, not evidence that one number is a failed reproduction.
At **20%**, the smooth exponential template crosses early (**101.87 ns**),
while the per-pulse last-above operation is longer (**119.03 ns**)
because late samples and residual structure can remain above 20% after the smooth median tail
has crossed. At the **noise floor**, the template fit reports **161.18 ns**,
but the empirical/ML target is limited to the sampled waveform window near
**120.37 ns**; the template is extrapolating beyond the observed
tail rather than measuring the same operational quantity.

## Leakage checks

Leakage flags: **0**. Checks include run-held-out R2, random row-split
advantage, shuffled-target prediction, forbidden feature presence, and a specific guard against
near-deterministic ML/template agreement. See `leakage_checks.csv`.

## Conclusion

The S10c numbers are internally consistent once the quantity is named precisely. The template
fit estimates a smooth tail crossing and can extrapolate beyond sampled data at low thresholds;
the empirical and ML methods estimate the discrete last-above-threshold operational live-time
within the acquired 18-sample waveform. For pile-up occupancy, 10% remains the least ambiguous
bridge between the two definitions; 20% and noise-floor definitions should not be mixed without
calling out the operational difference.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `threshold_summary.csv`,
`reconciliation_summary.csv`, `template_sampling_diagnostics.csv`,
`pulse_censoring_by_target.csv`, `ml_heldout_by_run.csv`, `leakage_checks.csv`, and three PNG
diagnostics are in this folder.
