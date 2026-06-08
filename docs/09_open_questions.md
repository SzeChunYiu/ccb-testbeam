# 09 — Open questions, caveats, and TODOs

A running list of everything not yet settled. Each maps to one or more studies in
[studies/STUDIES.md](../studies/STUDIES.md).

## Reproduction gaps (must close first)
- The selected-pulse table count gate is **closed**: S00 reproduced 640,737 B-stave records
  exactly from raw `HRDv` using even physical-stave channels and `A>1000 ADC`.
- The raw-count gate follows the newer split with Sample II calibration run 64. The older run
  61 calibration choice still matters for timing-calibration comparisons, not for selected-pulse
  counting. (S03, S04)
- The **two notes still disagree** on stave spacing (2 cm vs 4 cm) and per-stave resolutions.
  Reconcile in timing studies where geometry enters. (S02, S04)
- Sorted `hrdMax` amplitudes are not an exact proxy for the raw `HRDv` S00 gate count; document
  or reconcile that derived-branch semantic before downstream workers use sorted counts. (S00a)
- The amplitude-adaptive **template + q_template were never evaluated on the full dataset** —
  the notes use an old small subset. (S01)

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
- τ_eff = 90 ns occupancy assumption untested; need a measured live-time/shaping time. (S10)
- Constrained **two-pulse template fit** (the recommended traditional recovery) **not built**. (S11)
- App. I positive class = **72 events**; all its metrics need bootstrap CIs. (S12)
- The pile-up "score" is mostly current-independent baseline (ratio 1.29, not 10) — the genuine
  beam-pile-up component (~9.2%) must be isolated more rigorously. (S10, S13)

## ML
- Probabilities **miscalibrated** (App. A) — add isotonic/logistic calibration + reliability
  diagrams everywhere. (S07)
- Ridge **α unscanned**; no CV; compare to analytic baseline. (S07)
- Class imbalance handling (7:1; 72 positives) — proper PR/calibration/bootstrap. (S07, S12)
- No **deep model** (CNN on waveforms, GNN on the 4-stave event) actually trained — only
  proposed. (S08, S09)
- No fair **ML-vs-traditional benchmark** reported for most claims — this is now mandatory. (all)

## Physics / calibration
- Energy scale is a 2-parameter power-law, not PSTAR/GEANT4; Birks quenching not modelled. (S14)
- p vs d particle ID is sample-level only; no event-by-event ΔE–E PID built. (S15)
- Adaptive-pedestal "0% below tolerance" is true **by construction** — needs an independent
  validation (e.g. against a forced-trigger/empty-pulse pedestal sample). (S16)
- No GEANT4 simulation of the CCB setup exists — building one would provide the **only** route
  to true MC labels for validating every data-driven method. (S17, stretch)

## Infrastructure
- Raw data not yet mirrored to LUNARC with checksums. (S00)
- No unit/regression tests on the reconstruction pipeline. (cross-cutting)
