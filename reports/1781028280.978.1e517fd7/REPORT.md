# Study report: S10g - censored live-time estimator

- **Ticket:** `1781028280.978.1e517fd7`
- **Worker:** `testbeam-laptop-2`
- **Date:** 2026-06-10
- **Inputs:** raw B-stack ROOT, runs 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57
- **Config:** `configs/s10g_1781028280_978_1e517fd7_censored_livetime.json`

## Reproduction first

The S10c/S10d raw-ROOT gate was rerun before the censored analysis. It passed
14/14 checks, including the S10d template and naive empirical live-time numbers at
5%, 10%, 20%, and noise-floor thresholds. See `reproduction_match_table.csv`.

## Methods

The traditional censored method treats a pulse as right-censored when the threshold is still
above the final acquired sample. It reports a Kaplan-Meier restricted mean inside the sampled
window and a fixed-shape Weibull, equivalent to a censored exponential MLE, for the inferred
uncensored tail. The ML method is a
run-held-out Ridge AFT regressor trained only on uncensored training pulses with IPCW weights
from the training-run censoring distribution. All CIs bootstrap held-out runs.

## Results

- 5%: template 141.06 ns, censored exponential 2832.98 ns [2030.42, 3646.84], KM restricted 156.90 ns, ML-IPCW 192.60 ns; right-censored fraction 0.94.
- 10%: template 124.79 ns, censored exponential 1357.24 ns [934.58, 1801.07], KM restricted 151.64 ns, ML-IPCW 179.05 ns; right-censored fraction 0.86.
- 20%: template 101.87 ns, censored exponential 690.89 ns [468.44, 920.80], KM restricted 141.67 ns, ML-IPCW 127.38 ns; right-censored fraction 0.74.
- noise floor: template 161.18 ns, censored exponential 2250.29 ns [1614.67, 2865.24], KM restricted 148.33 ns, ML-IPCW 405.68 ns; right-censored fraction 0.92.

The 10% censored exponential mean is 1357.24 ns, +1232.45 ns relative to the
exponential template crossing. The noise-floor censored exponential mean is 2250.29 ns,
+2089.10 ns relative to the template. At the most censored thresholds, the KM
restricted mean stays near the observable window, while the censored exponential fit exposes the extrapolated
uncensored tail needed for a like-for-like comparison to template extrapolation.

## Leakage checks

Leakage flags: **0**. Checks cover forbidden feature presence, run-held-out versus
random row-split advantage, shuffled uncensored targets, and near-deterministic held-out R2.
See `leakage_checks.csv`.

## Conclusion

The naive last-above means in S10d were biased toward the acquisition endpoint because most
low-threshold pulses were censored. Explicit censoring moves the 5%, 10%, and noise-floor
tail estimates upward relative to the naive means; the 20% estimate remains closest to the
observable window. The inferred uncensored tail is not identical to the median-template
exponential crossing, but it gives the same operational warning: low-threshold pile-up windows
cannot be summarized by an uncensored 90 ns assumption.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`,
`censored_by_run.csv`, `censored_summary.csv`, `final_comparison.csv`,
`ml_ipcw_heldout_by_run.csv`, `leakage_checks.csv`, and three PNG diagnostics are in this
folder.
