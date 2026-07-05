# B-M6 — Sample-I enrichment vs run-set / beam-condition drift

- Generated: 2026-07-05T18:26:40Z by `scripts/bm6_runset_confound.py`
- Data: `/home/billy/projects/ccb-testbeam/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz` (analysis runs only)
- Sample I (A.B coincidence) = runs [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]
- Sample II (B-only) = runs [58, 59, 60, 61, 62, 63, 65]
- Observable: B2 f(A>5000 ADC) (the S23 hardening signature) + B2 occupancy share.

## The confound

In data, Sample I and Sample II are **disjoint run sets** with different hardware triggers AND unmodelled beam/rate/detector drift. So the S23 cross-sample hardening (B2 f(A>5000): I=0.710 vs II=0.206, ratio 3.45) mixes the trigger physics with any run-condition drift across runs 44-65. This note bounds the drift part using the within-sample run-to-run spread of the SAME observable as the drift proxy, and treats the RUN as the dependence unit.

## Run-clustered ratio (dependence unit = run, not pulse)

- R_data = f_I/f_II = **3.452**, run-clustered 95% CI **[2.521, 4.639]** (bootstrap resampling whole runs, 20000 reps). Excludes 1: **True**.
- Pulse-pooled (S23-style) R_data = 3.452. The run-clustered CI is the honest one: it is far wider than the pulse-level CI but still excludes 1 by a large margin.

## Run-level separation (each run = one measurement)

| Observable | mean I | mean II | SD I | SD II | Welch t (df~run) | Cohen d |
|---|---|---|---|---|---|---|
| B2 f(A>5000) | 0.6161 | 0.1967 | 0.219 | 0.0693 | 6.5 | 2.26 |
| B2 occupancy share | 0.9542 | 0.7175 | 0.0201 | 0.155 | 4.0 | 2.67 |
| B2 median amp [ADC] | 5722 | 3348 | 1.4e+03 | 335 | 6.0 | 2.02 |

- The between-sample gap in B2 f(A>5000) is **3.5x** the within-sample run-to-run SD (pooled, in log space). Equivalently, a **1-SD** run-condition excursion moves log f by only **29%** of the observed I->II gap.

## Linear-drift attribution

- Within-sample trend of log f(A>5000) vs run: slope_I = 0.0463/run (R^2=0.26), slope_II = -0.0391/run (R^2=0.09).
- Extrapolating that smooth drift across the mean run gap (10.6 runs) predicts a log-drop of 0.038, i.e. **3%** of the actual I->II log-drop (-1.239). The remaining ~97% is a STEP coincident with the trigger change, not smooth run drift.

## Verdict (reframed claim)

The Sample-I hardening is **directionally consistent with, and quantitatively dominated by, the trigger** and is NOT attributable to run-set/beam drift: (i) the effect is 3.5x the within-sample run-to-run SD; (ii) the run-clustered ratio CI [2.52, 4.64] excludes 1; (iii) a smooth linear-drift model reproduces only ~3% of the gap (central estimate). But because the run sets are disjoint, this is a **directional/consistent** result with an explicit confound bound, NOT a clean same-run confirmation.

**Confound bound.** A *conservative* attribution — a full 1-SD within-sample run-condition excursion acting coherently across the run gap — accounts for at most **~29%** of the log(f_I/f_II) hardening (1 SD / gap = 1/3.5); the central linear-drift estimate is ~3%. Reframe: replace 'confirmed in data' with '**directionally confirmed in data, with the run-set/beam-drift confound bounded at <~29% of the effect** (conservative 1-SD; central estimate ~3%)'.

## Caveats
- No external beam-current/HV metadata exists; the drift proxy is the observable's own within-sample run-to-run dispersion, which absorbs current/rate/HV drift to the extent they move B2 hardening. A same-run or interspersed A.B-vs-B-only control remains the only way to fully break the confound.
- The MC double ratio (DR=0.738) is unaffected here (this is a data-only confound check); DR remains the gain/geometry-robust cross-check reported in S23.
