# Paper figure report: #1045 trigger migration (Phase 4 corrected)

Generated: 2026-08-17T01:31:57.521986+00:00

## Method

Per-event JOINT classification of the 1M v3 MC run (real T1/T2 counters
instrumented from the baseline geometry; two-arm sample reproduced at 554
exactly, proving a geometry-only delta on the authorising source chain).
Proxy = two-arm charged coincidence (`sample_I`); hardware = per-hit
threshold + earliest-above-threshold coincidence on T1/T2 truth hits.

## Verdict @ 1.0 MeV / 15 ns

- both = 165, proxy-only = 389, hardware-only = 195
- two-arm retention = 165/554 = 0.2978 +/- 0.0194 (binomial); ray prediction 0.289
- retention is threshold-insensitive (0.5-5 MeV flat): the loss is geometric
- hardware sample is NOT a subset of the proxy sample (195/360 = 54% of hardware triggers lie outside the two-arm definition)

## Correction record

The aggregate matrix joined two scan JSONs arithmetically (both=256, proxy_only=298, hardware_only=0) under the false assumption that a
hardware pass implies proxy membership. Superseded by the per-event joint
matrix (this report). See phase4/JOINT_MATRIX_CORRECTION.md.

## Figures

- `figures/fig_trigger_migration_quadrants.png`
- `figures/fig_trigger_threshold_scan.png`

## Governance

MC method closure on the authorising corrected-source chain (CL-021
satisfied). NOT a beam-data trigger result; no hardware-validated
efficiency claim is made.
