# Timing supervisor pack

This folder freezes the current CCB timing-study diagnosis and the sequence required to rebuild it
from raw waveforms without promoting an analysis artifact to detector performance.

## Start here

1. Read `TIMING_STUDY_STEP_BY_STEP.md`.
2. Run `timing_result_diagnostics.py` against the repository result and polarity map.
3. Use `diagnostic_plot_manifest.csv` as the raw-data analysis checklist.
4. Continue the atomic queue in `HANDOFF.md`.

## Generated outputs

The diagnostic producer writes:

- `01_reported_width_scan.*` — the central core narrows while the full RMS stays around four
  nanoseconds;
- `02_non_gaussianity_ratio.*` — the RMS/core mismatch;
- `03_gaussian_fit_quality.*` — the reported core model has chi2/ndf of hundreds;
- `04_sqrt2_counterexamples.*` — why pair `sigma68/sqrt(2)` is not a general single-stave estimator;
- `05_resolution_inference_gate.*` — the fail-closed path to a stave-resolution claim;
- `audit_summary.json` and `AUDIT_SUMMARY.md` — machine- and human-readable findings.

## Current verdict

```text
Issue #1320 sub-nanosecond value: historical pair-core diagnostic
physical pair timing authorized: false (retracted map/frame interpretation)
single-stave timing resolution authorized: false
next required evidence: correctly decoded raw frame + real-pulse identity + held-out multi-pair closure
```
