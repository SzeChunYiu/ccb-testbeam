# MC Validation Results Summary (MV0–MV6)

Generated: 2026-06-28. **Corrected 2026-07-03** following External Review 2026-07-02
(`EXTERNAL_REVIEW_2026-07-02.md`): MV0, MV2, MV5 and MV6 verdicts are retracted; MV4 is under
review pending a matched rerun.

All studies executed on LUNARC (account lu2026-2-51, partition lu48).
Results archived in `reports/mc_validation/mv*/study_result.json`.
Raw SLURM logs in `reports/mc_validation/mv*/slurm_*.out`.

---

## Overview table

| Study | What it validates | Status | Key number | SLURM job |
|-------|-------------------|--------|------------|-----------|
| MV0 | Digitizer ADC/MeV gain | ⛔ **RETRACTED (2026-07-03)** | v2 gain 92 ± 28 ADC/MeV invalid (anchor variable wrong); gain unknown | 3328635 |
| MV1 | Proton/deuteron PID (AUC) | PASS | AUC = 0.986 | 3328635 |
| MV2 | Range–energy relation | ⛔ **RETRACTED pending rerun (2026-07-03)** | momentum unit error (eV-scale ekin) | 3328635 |
| MV3 | Stopping-depth profile | **STRUCTURAL FAIL** | χ²/ndf = 68,269 | 3328648 |
| MV4 | Single-stave timing σ₆₈ | ⚠️ UNDER REVIEW (2026-07-03) | pulls −1.05/+2.68 unreliable (comparison mismatches); matched rerun required | 3328641 |
| MV5 | Pile-up R_max | ⛔ **RETRACTED as validation (2026-07-03)** | MC τ_eff was a hardcoded copy of the data value | 3328643 |
| MV6 | Anomaly species (GMM) | ⛔ **RETRACTED (2026-07-03)** | C12 attribution unsupported (invalid gain, no quenching, no threshold) | 3328644 |

---

## MV0 — Digitizer gain calibration

**Status: ⛔ RETRACTED (2026-07-03).** The v2 anchor (B2 net median 1781 ADC) was |net − pedestal|
of an already baseline-subtracted amplitude — a folded garbage variable; the true B2 net median is
5752 ADC. The 92 ± 28 ADC/MeV gain is unreproducible from any committed script, and the MC anchor
is circular with the MV3-failed geometry. Neither v1 (~246) nor v2 (92) is valid; the gain is
UNKNOWN pending a geometry-fixed MC and the correct anchor variable. The material below is retained
for the record only. (External Review 2026-07-02)

### Methodology

The v1 method divided total data ADC by MC deposited energy using mean values; this was
incorrect because the ADC→energy mapping is nonlinear across the amplitude range. The v2
method identifies the peak of the amplitude distribution (`peak_frac`) and scales by the
corresponding MC energy deposit at that fractile.

### Result table

| Quantity | Value |
|----------|-------|
| Data B2 net ADC (median) | 1781 ADC |
| MC energy deposit (median) | 26.44 MeV |
| peak_frac | 0.733 |
| Gain (v2) | **92 ± 28 ADC/MeV** |
| χ²/ndf | not applicable (calibration point) |

### Interpretation

(Retracted interpretation, retained for the record.) The 30% relative uncertainty on the gain
reflects the width of the amplitude distribution, not measurement imprecision. **Do not use
92 ADC/MeV (or 246 ADC/MeV) as input to any downstream study** — MV0 is reopened and the gain is
unknown.

---

## MV1 — Proton/deuteron PID (AUC)

**Status: PASS**

| Quantity | Value |
|----------|-------|
| AUC (histogram gradient boosting) | 0.986 |
| n_proton (truth-matched) | 100,549 |
| n_deuteron (truth-matched) | 141,047 |

The PID classifier reaches AUC = 0.986 on the full 1M-event MC sample. This confirms that
the dE/dx feature set carries sufficient separation for physics-grade particle identification.
MV1 is CLOSED.

---

## MV2 — Range–energy relation

**Status: ⛔ RETRACTED pending rerun (2026-07-03).** A momentum-unit error (GeV momenta mixed with
MeV masses) left the published ekin values at eV scale; all ekin-based MV2 numbers are invalid.
The edep medians were also misquoted downstream (the artifact says proton 101.1 / deuteron
73.4 MeV, not 23/89). A rerun after the unit fix, with a punch-through/containment flag, is
required. The qualitative p/d range ordering remains supported. (External Review 2026-07-02)

---

## MV3 — Stopping-depth profile (STRUCTURAL FAIL)

**Status: STRUCTURAL FAIL — requires new GEANT4 production run**

### χ² decomposition

| Quantity | Value |
|----------|-------|
| χ² | 204,807 (= 68,269 × 3) |
| ndf | 3 |
| χ²/ndf | **68,269** |
| p-value | < 10⁻³⁰⁰ |

### Layer-by-layer stopping fractions

| Layer | MC fraction | Data fraction | Pull |
|-------|-------------|---------------|------|
| B2 | 0.470 | 0.876 | −62σ |
| B4 | 0.182 | 0.063 | +17σ |
| B6 | 0.125 | 0.039 | +13σ |
| B8 | 0.223 | 0.023 | +29σ |

### Root cause diagnosis

The MC stopping profile is qualitatively inverted: simulated protons penetrate roughly four
layers too deep. The single most likely cause is **missing upstream material budget** in the
current GEANT4 macro. Candidate missing elements (not yet confirmed individually):

1. CD₂ target material and holder (nominal thickness ~2 mm)
2. Beam-pipe exit window (aluminium foil, ~0.1 mm)
3. Air gap between beam exit and first SciBar layer (~10–30 cm)
4. SciBar scintillator material upstream of the HRD entrance

A geometry scan varying total upstream material (0–100 mm aluminium equivalent) is required
to identify the dominant contribution. If the profile can be matched by adding material, the
fix is purely a GEANT4 macro update; if it cannot, an additional systematic (e.g., beam
energy spread) must be considered.

MV3 remains a **known-bad artifact** of the current simulation geometry. It does not
invalidate MV0–MV2 (which use truth-level MC independently of absolute stopping depth) or
MV4–MV6 (which use selected-layer subsets).

---

## MV4 — Timing σ₆₈ (UNDER REVIEW)

**Status: ⚠️ UNDER REVIEW (2026-07-03) — matched rerun required.** The comparison is not
apples-to-apples: the data anchor 1.85 ns is the ML-corrected value (raw CFD20 = 2.99 ns);
single-trace MC vs pair-difference data; merged-track MC waveforms vs per-stave data pulses;
σ_data = 0.10 ns assumed, not measured — the pulls below are not reliable.

### Results table

| Path | MC σ₆₈ | Data σ₆₈ | Pull |
|------|--------|---------|------|
| Raw (no timewalk correction) | 1.744 ± 0.007 ns | 1.85 ns | **−1.05** (PASS) |
| Corrected (timewalk subtracted) | 1.770 ± 0.011 ns | 1.50 ns | **+2.68** (TENSION) |

### Timewalk B coefficient diagnosis

The toy digitizer in the MC chain returns B = −23.00 ns·√ADC (the timewalk correction
formula is Δt = B/√A). A negative B is unphysical: it implies that larger pulses arrive
**later**, opposite to the observed behaviour in real CFD circuits.

Root cause: the toy digitizer uses a fixed-threshold comparator without a proper pulse-shape
model. At high amplitude, the simulated comparator fires at the same fractional threshold as
at low amplitude, and the resulting correction has the wrong sign.

Consequence: the corrected-path pull (+2.68) reflects a systematic error in the MC timewalk
model, not genuine disagreement in the physical timing resolution. The **raw comparison
(pull = −1.05) is the reliable cross-check**; it avoids the buggy correction chain entirely.

Fix path: replace the toy digitizer with a template-pulse convolution model that applies
an empirical CFD threshold, then re-derive B from MC-truth timing. This requires a new MC
production run or a post-hoc reweighting of the existing run.

---

## MV5 — Pile-up R_max (RETRACTED as validation)

**Status: ⛔ RETRACTED as validation (2026-07-03).**

| Quantity | MC | Data | Note |
|----------|----|------|------|
| τ_eff | — | 124.79 ns | measured from data (10% tail-crossing live-time, S10b); the "MC τ_eff = 124.8 ns" was a hardcoded copy of this value, **not** fitted from MC inter-arrival |
| R_max (data-driven bound) | — | ≤ 3.05 MHz | one-sided upper bound; censoring-aware estimators (KM 151.6 ns, IPCW 179.1 ns) suggest ≈2.1 MHz or lower |
| R_max (note) | — | 4.22 MHz | an *assumption* (τ_eff = 90 ns), not a measurement at peak current |

No independent MC live-time measurement exists; the claimed 0.2% agreement was the rounding error
of the same number. Given the toy τ_decay = 42 ns vs measured data tails 49–57 ns, an honest MC
measurement would have disagreed. The 4.22 → 3.05 MHz correction of the note's 90 ns assumption
stands, but as a data-driven one-sided upper bound. MV5 is REOPENED as a validation item.
(External Review 2026-07-02)

---

## MV6 — Anomaly species identification (RETRACTED)

**Status: ⛔ RETRACTED (2026-07-03).** MV6 ran with the invalidated gain (246), no Birks quenching,
no amplitude threshold (despite claiming "threshold-corrected"), and per-track whole-arm waveforms
vs per-stave data pulses. The C12 attribution is unsupported, and the data ~4% vs MC 0.32% figures
use different denominators and taxonomies (selected pulses with A>1000 vs all charged tracks) — the
~12× rate mismatch is unresolved. The numbers below are retained for the record only.
(External Review 2026-07-02)

### Summary statistics

| Quantity | Value |
|----------|-------|
| Total tracks analysed | 87,555 |
| Anomaly fraction | 0.0032 (0.32%) |
| Dominant species (GMM) | C12 nuclear recoils — 55% |
| Cluster 2 purity | 0.445 |
| Cumulative PCA variance (4 components) | 0.745 |

### Interpretation

(Retracted interpretation, retained for the record only — see status above.) MV6 is REOPENED:
the anomaly species identity is an open question pending an honest redo with Birks quenching, an
amplitude threshold, and a data-matched selection.

---

## Remaining open questions

### Requires a new MC production run

| Item | Blocking condition |
|------|-------------------|
| MV3 stopping-depth fix | New GEANT4 macro with corrected upstream material budget |
| MV4 corrected-timing tension | Template-pulse digitizer replacing toy comparator |

### Closed analytically or by existing data

| Item | Resolution |
|------|-----------|
| MV0 gain | ⛔ REOPENED 2026-07-03: v1 and v2 both retracted; gain unknown pending geometry-fixed MC + correct anchor |
| MV1 PID AUC | CLOSED: AUC = 0.986 |
| MV5 pile-up rate | ⛔ REOPENED 2026-07-03: retracted as validation; only a data-driven one-sided bound (≤3.05 MHz) exists |
| MV6 anomaly species | ⛔ REOPENED 2026-07-03: C12 attribution retracted; species identity open |
| MV2 range–energy | ⛔ REOPENED 2026-07-03: retracted pending rerun (momentum unit error) |

### Still open (data-side, not MC)

- Absolute time / TOF scale validation against independent reference
- Correlated terms in two-ended readout variance decomposition
- Forced-pedestal sample comparison for adaptive-pedestal validation
- χ²/ndf on Gaussian-core timing fits (Table 18 blank)
- Full RMS and tail fraction alongside narrow-core σ
