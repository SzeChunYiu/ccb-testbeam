# 09 — Open questions and caveats

This is the residual-risk list after the current synthesis. Closed studies remain cited in the
chapter files; this page tracks what still limits a physics-facing result.

---

## MC validation closure status (2026-06-28)

All six MC validation studies have been executed on LUNARC (account lu2026-2-51, partition lu48)
as of 2026-06-28. Results are archived in `reports/mc_validation/mv*/`. See
`docs/mc_validation/MC_VALIDATION_RESULTS.md` for the full summary.

| Study | Topic | Status | Key result |
|-------|-------|--------|------------|
| MV0 | Digitizer gain calibration | PASS (corrected) | gain = 92 ± 28 ADC/MeV (v2 method) |
| MV1 | Proton/deuteron PID (AUC) | PASS | AUC = 0.986 |
| MV2 | Range–energy relation | PASS | validated |
| MV3 | Stopping-depth profile | **FAIL — structural** | χ²/ndf = 68,269; MC B8 = 22% vs data 2% |
| MV4 | Timing σ₆₈ | PASS (raw) / TENSION (corrected) | raw pull = −1.05; corrected pull = +2.68 |
| MV5 | Pile-up R_max | PASS | R_max = 3.044 MHz vs data 3.05 MHz |
| MV6 | Anomaly species identification | DONE — CLOSED | C12 recoils 55% dominant; frac = 0.32% |

Items marked PASS/DONE/CLOSED do not appear as open questions below.
MV3 (structural FAIL) and MV4 (timewalk tension) generate concrete open items in the sections
that follow.

---

## Reproduction gaps (must close first)

- The selected-pulse table count gate is **closed**: S00 reproduced 640,737 B-stave records
  exactly from raw `HRDv` using even physical-stave channels and `A>1000 ADC`.
- The raw-count gate follows the newer split with Sample II calibration run 64. The older run
  61 calibration choice still matters for timing-calibration comparisons, not for selected-pulse
  counting. (S03, S04)
- The 2 cm vs 4 cm stave-spacing ambiguity is **closed**: S12a (`reports/0000000012.1.truthtiming/`)
  measured the analysed-stave median separation directly from GEANT4 truth hit positions for the
  B2-B4, B4-B6, and B6-B8 pairs (mapped to Sci_bar layer pairs 0-2, 2-4, 4-6) and found a median
  path separation of 4.0258 cm. The 4 cm centre-to-centre convention is within +0.65% of this
  truth value; the 2 cm interpretation underestimates the true path length by approximately 50.3%
  and is rejected. All downstream TOF and range-interpretation code should use the 4 cm
  convention; see `docs/mc_validation/` and the wiki page `02-Experimental-Setup-and-Detector`
  for the resolved geometry.
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
- **Two-ended √2 projection ignores correlated terms** — quantify the correlated fraction.
  Falsifying test: measure same-event left/right residuals and fit ρ; if |ρ| > 0.1 the
  projection underestimates the true single-stave σ. (S05)
- **Absolute time / TOF scale unvalidated** against an independent reference. Falsifying test:
  compare β reconstruction from dE/dx-selected proton tracks (known kinematics) to the
  TOF-implied β. (S06)

### MV4 residual: timewalk B coefficient (OPEN — toy-digitizer limitation)

MV4 raw σ₆₈ = 1.744 ± 0.007 ns passes (pull = −1.05). The timewalk-corrected σ₆₈ =
1.770 ± 0.011 ns shows tension (pull = +2.68 vs data 1.50 ns corrected). Root cause: the
toy digitizer returns B = −23.00 ns·√ADC (unphysical negative slope). A realistic pulse-shape
model with proper CFD simulation is needed before corrected timing can be validated. This
affects only the corrected path; the raw σ₆₈ comparison remains valid.

**Fix applied, not yet verified by rerun (2026-07-01):** `scripts/mv4_timing_study.py` --
the actual production script behind SLURM job 3328641 -- has been switched from fitting
`dt = A + B/sqrt(amp)` to the physically-derived `dt = A + B/amp`. This is committed and
pushed to `main`. It has NOT been re-run (LUNARC access currently blocked, see
`RUN_BLOCKED.md`), so the corrected-path pull is not yet confirmed to have improved; re-run
this script against the same MC ROOT file to close this item.

Falsifying test: generate pulses from the measured template library, apply the experimental
CFD threshold, extract B empirically; if B < 0 survives, the data timewalk correction itself
is suspect.

## Pile-up

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

### MV3: Stopping-depth profile — structural FAIL (OPEN — requires new MC production)

MV3 returns χ²/ndf = 68,269 (three stave bins). The MC stopping profile is qualitatively
inverted relative to data: MC B8 = 22%, B6 = 13%, B4 = 18%, B2 = 47%; data B8 = 2%, B6 = 4%,
B4 = 6%, B2 = 88%. The root cause is identified as **missing upstream material budget** in the
current GEANT4 macro: target, entrance window, air gaps, and SciBar material upstream of the
HRD stack are not fully implemented, causing simulated protons to penetrate further than observed.

This is a structural failure; it cannot be fixed analytically. A new GEANT4 production run with
a corrected geometry is required. MV3 is therefore marked as a known-bad simulation artifact
until the geometry PR is merged and re-simulated.

**MV3c update (2026-07-01):** a source-code audit of the actual geometry builder
(`HIBEAM-NNBAR/hibeam_g4_geobuilder`, `src/krakow.cxx`) found that the CD2 target, a beam
window, and T1/T2-style trigger scintillators (added to source 2026-01-26) are already
present -- contradicting part of the "not in current MC" assumption above -- while the
inter-stave dead-material gap is confirmed genuinely absent. See
`reports/mv3c_geometry_source_audit/REPORT.md`. A candidate code fix (tunable
`interstaveDeadMat_areal_gcm2` constant, Al-proxy dead layers between consecutive HRDBar
layers) is written and self-consistency-verified on a local branch
(`fix/mv3-interstave-dead-material` in a local clone), but not pushed to the shared
collaboration repo, not built, and not run -- that needs LUNARC plus a maintainer decision
on the PR.

Falsifying test: run a geometry scan varying the total upstream material thickness and identify
the value that brings B8/B6/B4/B2 within 2σ of data. If no single thickness achieves this, a
partial-geometry model (layer-by-layer) is needed.

- Event-level energy and PID remain truth-limited. The current GEANT4 bridge is useful, but not
  yet an event-aligned production calibration for HRD data. (S14, S15, S17)
- **Adaptive-pedestal "0% below tolerance"** is true by construction — needs an independent
  validation against a forced-trigger / empty-pulse pedestal sample. (S16)
- GEANT4 truth currently supplies a layer-level prior and smoke-tested truth tree, but the exact
  production macro and event-to-HRD alignment remain integration work.

## Infrastructure

- Raw data not yet mirrored to LUNARC with checksums. (S00)
- No unit/regression tests on the reconstruction pipeline. (cross-cutting)
