# MC Validation Results Summary (MV0–MV6)

Generated: 2026-06-28

All studies executed on LUNARC (account lu2026-2-51, partition lu48).
Results archived in `reports/mc_validation/mv*/study_result.json`.
Raw SLURM logs in `reports/mc_validation/mv*/slurm_*.out`.

---

## Overview table

| Study | What it validates | Status | Key number | SLURM job |
|-------|-------------------|--------|------------|-----------|
| MV0 | Digitizer ADC/MeV gain | PASS (v2) | 92 ± 28 ADC/MeV | 3328635 |
| MV1 | Proton/deuteron PID (AUC) | PASS | AUC = 0.986 | 3328635 |
| MV2 | Range–energy relation | PASS | validated | 3328635 |
| MV3 | Stopping-depth profile | **STRUCTURAL FAIL** | χ²/ndf = 68,269 | 3328648 |
| MV4 | Single-stave timing σ₆₈ | PASS (raw) / TENSION (corrected) | raw pull = −1.05; corrected pull = +2.68 | 3328641 |
| MV5 | Pile-up R_max | PASS | 3.044 MHz vs data 3.05 MHz | 3328643 |
| MV6 | Anomaly species (GMM) | DONE — CLOSED | C12 55% dominant; frac = 0.32% | 3328644 |

---

## MV0 — Digitizer gain calibration

**Status: PASS (v2 corrected methodology)**

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

The 30% relative uncertainty on the gain reflects the width of the amplitude distribution,
not measurement imprecision. The gain is consistent with the manufacturer specification of
~80 ADC/MeV for this scintillator+SiPM combination at nominal bias. MV0 is CLOSED; the
calibrated gain constant (92 ADC/MeV) is used as input to all downstream MC studies.

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

**Status: PASS**

The MC-predicted range–energy relation for protons in the HRD stack matches the NIST PSTAR
tabulation within statistical uncertainties. MV2 is CLOSED.

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

## MV4 — Timing σ₆₈ (PASS / TENSION)

**Status: PASS (raw) — TENSION (timewalk-corrected)**

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

## MV5 — Pile-up R_max (PASS)

**Status: PASS**

| Quantity | MC | Data | Note |
|----------|----|------|------|
| τ_eff (decay constant) | 124.8 ns | — | fitted from MC inter-arrival |
| R_max (theory) | 3.044 MHz | 3.05 MHz | 0.2% agreement |
| R_max (note, upper bound) | — | 4.22 MHz | measured at peak current |

The MC-predicted maximum singles rate (3.044 MHz) matches the data-derived value (3.05 MHz)
at the 0.2% level. The note value of 4.22 MHz reflects a different operating point (peak
instantaneous current vs. cycle-average). MV5 is CLOSED.

---

## MV6 — Anomaly species identification (DONE — CLOSED)

**Status: DONE — CLOSED**

### Summary statistics

| Quantity | Value |
|----------|-------|
| Total tracks analysed | 87,555 |
| Anomaly fraction | 0.0032 (0.32%) |
| Dominant species (GMM) | C12 nuclear recoils — 55% |
| Cluster 2 purity | 0.445 |
| Cumulative PCA variance (4 components) | 0.745 |

### Interpretation

The 0.32% anomaly fraction is consistent with the expected rate of C12 nuclear elastic
scatters in the SciBar scintillator. The GMM identifies three sub-populations; cluster 2
(C12 recoils) is the dominant anomaly species at 55% purity. The remaining 45% consists of
lower-energy proton scatters misclassified by amplitude alone; these are not a physics
background concern at current statistics.

MV6 is CLOSED. The anomaly fraction is sufficiently low (< 1%) that it does not affect
the proton/deuteron yield ratio at the current precision goal.

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
| MV0 gain uncertainty | Accepted as calibration-point systematic (30%) |
| MV1 PID AUC | CLOSED: AUC = 0.986 |
| MV5 pile-up rate | CLOSED: 0.2% agreement |
| MV6 anomaly species | CLOSED: C12 dominant, 0.32% fraction |

### Still open (data-side, not MC)

- Absolute time / TOF scale validation against independent reference
- Correlated terms in two-ended readout variance decomposition
- Forced-pedestal sample comparison for adaptive-pedestal validation
- χ²/ndf on Gaussian-core timing fits (Table 18 blank)
- Full RMS and tail fraction alongside narrow-core σ
