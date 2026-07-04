# Phase 4 — species/dE/dx-dependent scintillation (Birks) & A-arm digitization

**Date:** 2026-07-04. **Jobs:** LUNARC 3347280 (B-arm Birks rebuild + MV6b, COMPLETED 00:02:25), 3347281 (A-arm table, COMPLETED 00:00:42), account `lu2026-2-51`, partition `lu48`.
**Fixes:** EXTERNAL_REVIEW_2026-07-02.md **F2.2** (birks.py dimensionally meaningless) and **F6.2** (MV6 ran unquenched; C12 light overstated ~10×).

---

## 1. Birks implementation (F2.2 fix)

`src/ccb_mc_validation/digitizer/birks.py` rewritten to the physically correct per-hit law

```
light = edep / (1 + kB · dE/dx)
```

- **kB = 0.0126 g/(MeV cm²)** (Craun & Smith 1970, NE-102; GEANT4 polystyrene default) / ρ **1.06 g/cm³** → **0.011887 cm/MeV** (documented in module + card).
- **Per-hit dE/dx**, resolution order: (1) truth `edep_hit/step_length` — step lengths from **consecutive-hit differences of the cumulative `Sci_bar_TrackLength`** (verified on `output_krakow_1M.root`: the branch is cumulative in cm — ~112 cm at B-arm entry for target primaries = flight path, ~20 µm for in-bar alpha recoils = their range; the raw value is a step only for the *first hit of locally created tracks*, guard `FIRST_STEP_MAX_CM = 5`); (2) **PSTAR/ASTAR-anchored species+energy lookup** (proton table = PSTAR water anchors × 0.976 polystyrene/water ratio × 1.06 g/cm³; d/t by same-velocity scaling; ions by Z_eff² scaling with Barkas/Ziegler effective charge — alpha@5 MeV cross-checks ASTAR within ~5%) with per-hit E_kin from the momentum branches; (3) species defaults (p 150 / d 105 / α 5 / C12 3 MeV); (4) MIP 2.2 MeV/cm.
- **Card:** `apply_birks: true` (configs/mc_validation/digitizer_card.yaml); CLI override `--apply-birks` / `--no-birks` in `mc02_build_mc_pulse_table.py`; hit dicts extended with `pdg` / `ekin_mev` / `dedx_mev_per_cm` (backward compatible — absent keys degrade to the lookup).
- **Validation numbers** (`tests/test_birks_quench.py`, 13 tests; full suite 157 green):
  - 150 MeV proton hit: quench 6.3% (<10% required); MIP: 2.6%.
  - C12 recoil (3 MeV): light/edep < 1/5 (requirement >5×; actual ≈ 1/60–1/100).
  - Light strictly monotone decreasing in dE/dx over 0.1–2·10⁴ MeV/cm.
  - kB = 0 conserves edep exactly.
  - New table column `dedx_max_mev_per_cm`; smoke on truth: proton steps ≈ 2 cm → dE/dx ≈ 2–8 MeV/cm; C12 recoils 2·10³–10·10³ MeV/cm — physical.

## 2. MV6 honest redo (F6.2) — `reports/mv6b_anomaly_quenching_1783180742/`

Quenched B-arm table `mc02_pulse_table_birks_1783180742` vs its **unquenched twin** `mc02_pulse_table_1783107862` (identical card/seeds/noise; only the quench differs). DATA taxonomy: **A > 1000 net ADC** (gain-equivalent rescaled), **early-peak = `peak_sample ≤ 3`** (P02 §5: clusters 1&4 ≈ 4.4%, peak at sample 3). Phase-2 update folded in: **gain 60** (trigger-consistent MV3-grid optimum) primary with **sample_II** trigger proxy; gain 297 + all/sample_I as sensitivity.

| quantity | quenched | unquenched | data |
|---|---|---|---|
| early-peak fraction (gain 60, sample_II) | 0.000% (0 of 0*) | 0.000% [0, 1.2%] (0/312) | **4.4%** |
| early-peak fraction (gain 297, sample_II) | 0.000% (0/415,400) | 0.000% (0/458,651) | 4.4% |
| C12 passing A>1000 (gain 297) | **0 / 1,656** | 3 / 1,656 | — |
| C12 passing A>1000 (gain 60) | 0 / 1,656 | 0 / 1,656 | — |
| heavy-ion share of selection (gain 60) | 0% | 13.8% (α+He3+t) | — |
| alpha rows selected (gain 297) | 346 (0.08%) | 2,167 (0.47%) | — |

Species of the gain-297 selection: quenched **p 62.2% / d 37.7% / ions 0.10%**; unquenched p 64.4% / d 34.9% / ions 0.65%.

**Verdict:**
1. **C12 recoils cannot be the data's 4.4% early-peak class.** Quenched, not a single one of the 1,656 C12-dominant stave records passes A>1000 at *any* gain hypothesis (even unquenched only 3 pass at gain 297). Their light (few-MeV recoil / quench factor ~60–100 → tens of keV-equivalent) sits at the noise floor. The retracted MV6's C12 attribution is definitively dead — the review's expectation, now quantified.
2. **MC early-peak fraction is 0.000% in every configuration** (both tables) vs data 4.4%. With the trigger phase pinned at 50 ns (peak at sample ~5–6) and species content unable to reach A>1000 with early peaks, the early-peak class **cannot be a species/scintillation effect** — it must be instrumental (baseline/noise/bipolar artifacts, per P02/P09 leads) or trigger-phase-related, neither of which this MC models.
3. Quenching also thins the legitimate ion content of the selection ~6× (alpha 0.47%→0.08%) and shifts p/d composition by ~2% — relevant to P08 PSD ceilings.

*Caveat (important):* at gain 60 the **quenched** table has zero A>1000 rows — the gain-60 preference was fitted by Phase 2 on an **unquenched** threshold model, so with Birks on the trigger-consistent gain must be **re-scanned** (p/d light drops 10–30% → preferred gain rises accordingly, ~70–80). The C12 conclusion is robust to this (it holds at every gain from 60 to 297).

## 3. A-arm digitized table (S18 MC counterpart baseline) — `reports/mc02_pulse_table_aarm_1783180742/`

`mc02_build_mc_pulse_table.py --arm A --apply-birks` (LayerID1==2; **direct LayerID 0–3 → A1..A4**, verified on the truth file; Birks ON; **τ_decay 50 ns DEFAULT** for A staves — the data template-fit CSV `reports/1781000867.546870.5c124aaf/template_fit_by_run_stave.csv` contains only B-stave rows; caveat documented in the card). 1,000,000 events → **143,808 rows**.

| stave | rows | occupancy frac | median A [ADC] | p10 | p90 | n(A>1000) | median A>1000 [ADC] |
|---|---|---|---|---|---|---|---|
| A1 | 69,777 | 0.485 | 1088 | 697 | 1652 | 42,135 | 1294 |
| A2 | 46,728 | 0.325 | 938 | 585 | 1413 | 18,079 | 1281 |
| A3 | 18,627 | 0.130 | 1447 | 862 | 1668 | 15,201 | 1509 |
| A4 | 8,676 | 0.060 | 639 | 228 | 1317 | 1,368 | 1370 |

A>1000 companion: 76,783 rows; Sample I events 64,762 / Sample II 64,980. Data reference (docs/08_astack.md, Sample III): A1 median ~2562, A3 ~1952 ADC; only A1/A3 usable in data (A2/A4 channels empty). MC occupancy ordering A1>A2>A3>A4 is the raw range-telescope expectation; the data's usable-channel pattern and the placeholder gain mean this is a **shape/ordering baseline only** — the S18 counterpart comparison should use A1 and A3 and treat the amplitude scale as uncalibrated.

## 4. Program bookkeeping

- `studies/MC_VALIDATION_PROGRAM.md`: Phase-4 section added (Birks, MV6b, A-arm artifacts) + **not-MC-informable** records: **P06 DAQ dropouts** (acquisition-layer failure; the MC chain has no DAQ transport to drop) and **P13a noise floor** (a measured data *input* to the digitizer card; MC output cannot validate its own input).
- `STUDY_GAPS.md`: §8 Phase 4 Log added (same items, incl. §4.6 A-stack partial closure).
- `scripts/mc02_validate_pulse_table.py` caveat 5 now reflects the build's actual Birks status.

## 5. Caveats (carried forward)

1. Gain remains a placeholder (297 native; Phase-2 prefers ~60 **unquenched** — re-scan needed with Birks on before any absolute-amplitude claim).
2. Occupancy/spectrum weights inherit the unsimulated two-arm-trigger defect (Phase 2 root cause for MV3).
3. LayerID→stave mapping (B arm) still UNDER REVIEW (paired vs odd).
4. A-stave τ_decay is a default, not a measurement; A-arm early-peak/timing comparisons need the trigger-phase model first.
5. Effective-charge (Z_eff²) ion dE/dx is ~40% accurate at few MeV/u — irrelevant for the saturated C12 quench conclusion, relevant if alpha light yields are ever used quantitatively.

## Files

- `src/ccb_mc_validation/digitizer/birks.py` (rewrite), `digitizer/pipeline.py` (per-hit wiring)
- `configs/mc_validation/digitizer_card.yaml` (apply_birks: true; A staves; provenance)
- `scripts/mc02_build_mc_pulse_table.py` (--arm, --apply-birks/--no-birks, per-hit dE/dx, dedx_max column, amplitude stats), `scripts/mc02_validate_pulse_table.py`
- `scripts/mv6b_anomaly_with_quenching.py` (new)
- `geant4/jobs/mc02_pulse_table_birks.sbatch`, `geant4/jobs/mc02_pulse_table_aarm.sbatch` (new)
- `tests/test_birks_quench.py` (new, 13), `tests/test_mc_pulse_table.py` (+6 Phase-4 tests); suite 157 passed
- Artifacts: `reports/mc02_pulse_table_birks_1783180742/`, `reports/mv6b_anomaly_quenching_1783180742/`, `reports/mc02_pulse_table_aarm_1783180742/` (LUNARC + local copies)
