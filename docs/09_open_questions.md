# 09 — Open questions and caveats

This is the residual-risk list after the current synthesis. Closed studies remain cited in the
chapter files; this page tracks what still limits a physics-facing result.

## Reproduction gaps (must close first)
- The selected-pulse table count gate is **closed**: S00 reproduced 640,737 B-stave records
  exactly from raw `HRDv` using even physical-stave channels and `A>1000 ADC`.
- The raw-count gate follows the newer split with Sample II calibration run 64. The older run
  61 calibration choice still matters for timing-calibration comparisons, not for selected-pulse
  counting. (S03, S04)
- The notes have used different stave-spacing conventions (2 cm vs 4 cm) in places. Geometry
  assumptions must be stated whenever TOF or range interpretation enters.
- Sorted `hrdMax` amplitudes are not an exact proxy for the raw `HRDv` S00 gate count; document
  or reconcile that derived-branch semantic before downstream workers use sorted counts. (S00a)
- Full-dataset templates are now available, but q-template remains a covariate with stave and
  amplitude dependence, not a universal quality score.

## Timing
- Gaussian-core fits report **no χ²/ndf** (Table 18 blank) — goodness unknown. (S04)
- Quoted σ is **narrow-core only**; full RMS and tail fraction must be reported alongside. (S04)
- Variance decomposition assumes **independent stave errors** (σ_ij²=σ_i²+σ_j²) — untested;
  correlated electronics/clock could bias it. (S05)
- CFD fraction (20%) and OF window are **unscanned**; no comparison of CFD vs OF vs template
  timing on the same pulses. (S02)
- σ vs amplitude/energy only partially mapped. (S06)
- Two-ended √2 projection ignores correlated terms — quantify the correlated fraction. (S05)
- Absolute time / TOF scale unvalidated against an independent reference. (S06)

## Pile-up
- The 90 ns occupancy assumption has been superseded by measured waveform live-time, but the
  operational rate still depends on threshold definition and acquisition-window censoring. (S10)
- Two-pulse recovery needs an adoption gate on real high-current data: RMS, failure rate, and
  missing-case behavior must be reported together. (S11)
- App. I positive class = **72 events**; all its metrics need bootstrap CIs. (S12)
- The pile-up "score" is mostly current-independent baseline (ratio 1.29, not 10) — the genuine
  beam-pile-up component (~9.2%) must be isolated more rigorously. (S10, S13)

## ML
- Probabilities **miscalibrated** (App. A) — add isotonic/logistic calibration + reliability
  diagrams everywhere. (S07)
- Ridge **α unscanned**; no CV; compare to analytic baseline. (S07)
- Class imbalance handling (7:1; 72 positives) — proper PR/calibration/bootstrap. (S07, S12)
- Deep and compact waveform models have been tested in selected panels. The remaining question is
  transfer and calibration, not whether a neural baseline exists. (S08, S09)
- Every new ML claim must continue to include the strongest available traditional comparator. (all)

## Physics / calibration
- Event-level energy and PID remain truth-limited. The current GEANT4 bridge is useful, but not
  yet an event-aligned production calibration for HRD data. (S14, S15, S17)
- Adaptive-pedestal "0% below tolerance" is true **by construction** — needs an independent
  validation (e.g. against a forced-trigger/empty-pulse pedestal sample). (S16)
- GEANT4 truth currently supplies a layer-level prior and smoke-tested truth tree, but the exact
  production macro and event-to-HRD alignment remain integration work.

## Infrastructure
- Raw data not yet mirrored to LUNARC with checksums. (S00)
- No unit/regression tests on the reconstruction pipeline. (cross-cutting)
