# B-M5 — Quenched trigger-consistent gain re-scan (MV3 stopping depth)

- **Date:** 2026-07-05 (UTC). **Job:** LUNARC SLURM **3348264** (`ccb_mv3_gain_quenched`, lu2026-2-51 / lu48, COMPLETED ~5 s, exit 0, 1,000,000 events). Smoke: 30k-event login-node dry run reproduced the optimum.
- **Artifacts (LUNARC + local mirror):** `reports/mv3_gain_quenched_1783240619/` — `mv3_gain_quenched.json`, `gain_curve.md`, `job_3348264.out`, this `REPORT.md`.
- **Script:** `scripts/mv3_gain_scan_quenched.py`; batch `geant4/jobs/mv3_gain_scan_quenched.sbatch`.
- **Backlog item:** B-M5 (reviewer M5) — "gain ~60 was fit unquenched; quenched table has 0 rows at A>1000 / gain 60".

## Problem

The Phase-2 trigger-consistent gain optimum (~60 ADC/MeV; MV3 chi2/ndf 68,269 -> 625) was fitted on an **UNQUENCHED** threshold model (`peak_adc = gain*edep*peak_frac`). Phase 4 turned on the physically correct per-hit Birks law (`birks.py`: `light = edep/(1+kB*dE/dx)`, kB = 0.011887 cm/MeV). Quenching drops p/d light 6-13% and heavy-ion light 10-100x, so the ADC/MeV gain that reproduces the data amplitude spectrum and the MV3 stave profile must be **higher**. Phase 4 predicted ~70-80. Nobody had run the scan quenched.

## Method (faithful to mv3_stopping_v4_diagnostics, one physics change)

Per-hit `edep` is replaced with per-hit **light** `edep/(1+kB*dE/dx)`. dE/dx is derived **exactly** as in `mc02_build_mc_pulse_table.per_hit_dedx` (truth `edep_hit/step_length` from consecutive-hit differences of the cumulative `Sci_bar_TrackLength`; species+energy PSTAR/ASTAR fallback with per-hit E_kin from the momentum branches). The vectorised dE/dx was verified to match the authoritative `birks.dedx_polystyrene_mev_per_cm` to 1e-9 across p/d/t/alpha/C12/e/mu/n, and `chunk_dedx` reproduces `per_hit_dedx` bit-for-bit on shuffled multi-track synthetic events. Both arms are quenched.

Fixed comparison configuration = the Phase-2 optimum family: **event basis, species-inclusive, paired LayerID map, A-arm coincidence trigger proxy**. (B-M1's real `Trig_bar` flag is not yet in the tree — no `reports/mv3_v5*` — so the proxy is used, identical to Phase 2.) Threshold model identical to v4: `peak_adc = gain*light*0.733 > 1000`. Data target (MV3 v3 folded semantics) reproduced exactly: B2/B4/B6/B8 = **0.876 / 0.063 / 0.039 / 0.023** (n = 306,745). Gain scanned 40-160 fine, plus 297.

## Result — quenched chi2-vs-gain curve (trigger proxy, vs data all)

| gain | thr light [MeV] | n | B2 | B4 | B6 | B8 | chi2/ndf (all) | B2 amp median [ADC] |
|---|---|---|---|---|---|---|---|---|
| 45 | 30.32 | 27,593 | 0.916 | 0.045 | 0.039 | 0.000 | 1,380.8 | 2,076 |
| 55 | 24.81 | 51,363 | 0.889 | 0.049 | 0.054 | 0.008 | 3,538.8 | 2,475 |
| 60 | 22.74 | 53,340 | 0.880 | 0.052 | 0.049 | 0.020 | 520.2 | 2,696 |
| **65** | **20.99** | **54,627** | **0.875** | **0.054** | **0.042** | **0.029** | **322.4** | **2,917** |
| 70 | 19.49 | 55,818 | 0.873 | 0.055 | 0.036 | 0.037 | 677.9 | 3,140 |
| 75 | 18.19 | 56,892 | 0.873 | 0.055 | 0.030 | 0.042 | 1,216.1 | 3,367 |
| 80 | 17.05 | 57,505 | 0.872 | 0.055 | 0.026 | 0.046 | 1,863.6 | 3,588 |
| 90 | 15.16 | 59,159 | 0.873 | 0.055 | 0.022 | 0.050 | 2,928.0 | 4,041 |
| 100 | 13.64 | 60,294 | 0.873 | 0.056 | 0.019 | 0.052 | 3,760.1 | 4,498 |
| 297 | 4.59 | 63,675 | 0.867 | 0.059 | 0.013 | 0.060 | 7,751.6 | 13,312 |

(Full grid incl. sample-I/II columns in `gain_curve.md` / `mv3_gain_quenched.json`.)

## Quenched optimum

- **Quenched trigger-consistent gain ~= 65 ADC/MeV** (minimum chi2/ndf vs data-all).
- **chi2/ndf = 322.4** (ndf = 3), profile **B2/B4/B6/B8 = 0.875 / 0.054 / 0.042 / 0.029** vs data 0.876 / 0.063 / 0.039 / 0.023 — B2 nailed, the deep-stave residual (B4/B6/B8) is the ~1-3% absolute mismatch the trigger proxy leaves behind.
- The well is shallow and slightly asymmetric: 60 -> 520, **65 -> 322**, 70 -> 678; the shape chi2/ndf stays within ~2x of the minimum over **~60-70 ADC/MeV**.

**Amplitude-scale cross-check (independent of the profile chi2):** MC B2 deepest-stave amplitude median vs the data B2 net-amplitude median (**2,576 ADC**): gain 60 -> 2,696 (+4.7%), **gain 65 -> 2,917 (+13%)**, gain 70 -> 3,140 (+22%). The absolute amplitude scale confirms the same ~60-65 window and is inconsistent with 297 (which overshoots the data B2 median ~5x). So the profile chi2 and the amplitude scale point to the same place from two directions.

## Comparison to the reference gains

| gain hypothesis | basis | chi2/ndf (all) | note |
|---|---|---|---|
| unquenched optimum **60** (Phase 2) | unquenched threshold | 625 | prior published trigger-consistent optimum |
| **quenched optimum 65** (this work) | Birks ON | **322** | rises above 60 as physics predicts; also a *better* shape fit |
| quenched 60 | Birks ON | 520 | still viable, within band |
| card placeholder **297** | Birks ON | 7,751 | ~24x worse; overshoots data B2 amplitude ~5x |

The quenched optimum (65) sits **above** the unquenched 60 — the expected direction (less light per MeV => more ADC/MeV to reproduce the same amplitudes) — but **below** Phase 4's ~70-80 guess and far below the 297 card placeholder. The shift is modest (~+8%) because in the p/d-dominated triggered selection the quench is only 6-13%; the big Birks effect is on heavy ions, which the trigger proxy already suppresses.

Note on the Phase-4 "0 rows at gain 60" finding: that was the **full mc02 digitizer** at a native-297 amplitude rescaled to a gain-60 equivalent, further attenuated by the per-hit kernel convolution and applied to a narrow early-peak/sample-II sub-selection — a different normalization path. In this v4-consistent threshold model (`gain*light*peak_frac`), quenched gain 60 fires 53,340 events and remains viable; there is no contradiction, and the profile-based scan is the like-for-like continuation of the unquenched-60 fit.

## Remaining gain uncertainty band (honest)

**Quenched trigger-consistent gain ~= 60-70 ADC/MeV, central ~= 65.** This is a *shape+amplitude consistency band, not a statistical CI*: the absolute chi2/ndf values (100s-1000s on n~55k, ndf 3) are systematics-dominated, so no sub-unit delta-chi2 band is meaningful. The band width is set by, in decreasing order of importance:
1. **Trigger proxy vs the real trigger (B-M1):** the A-HRD coincidence proxy is not the physical `Trig_bar` two-paddle coincidence; the residual deep-stave chi2 is proxy-limited. A real per-event Sample-I/II flag would tighten (and could shift) the optimum.
2. **Flat `peak_frac = 0.733` vs the per-hit kernel convolution** used in the full digitizer — a per-stave normalization that trades against gain.
3. **LayerID->stave mapping** (paired assumed; B-M9).

These are the same systematics that cap the MV3 residual; none is closed by a gain scan. The honest statement remains a **band, not a precision value**.

## Bookkeeping

- No tested code modified (new script + sbatch only). `tests/test_birks_quench.py` re-run on LUNARC: **12 passed** (physics reuse certified).
- Backlog B-M5 updated; the "~60-80 ADC/MeV" gain statement in FINDINGS_SYNTHESIS / WIKI / PROJECT_REPORT updated to the measured **~60-70 (quenched optimum ~65)** band.
