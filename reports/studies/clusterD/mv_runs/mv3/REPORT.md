# MV3 v3 — Stopping-Depth Fraction (threshold-corrected)

- status: **PRODUCTION (v3)**
- generated: 2026-07-25T16:34:17.876897+00:00
- MC file: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root`
- Data: `s00_selected_b_pulses.csv.gz`
- MC tracks above threshold: 57808
  (below threshold: 3060 = 5.0%)
- Data events: 364938
- **χ²/ndf = 86135.5 → FAIL**

## Methodology

For each event/track, the "stopping depth" is the deepest stave where the predicted
(MC) or measured (data) amplitude exceeds the selection threshold of 100 ADC net.

**MC threshold rule:**
`peak_adc = gain × edep_stave × peak_frac`; stave counted if `peak_adc > 100 ADC`.
- gain = 92.0 ADC/MeV (from MV0 v2)
- peak_frac = 0.7500 (digitizer model, τ_r=2.5 ns, τ_d=42 ns)
- Threshold EDep ≈ 1.4 MeV per stave

**v3 vs v2 correction:** v2 used all MC hits regardless of predicted amplitude.
Through-going protons deposit ~1.2 MeV in 2 × 3 mm of scintillator → peak ≈ 83 ADC
(below threshold). v2 incorrectly counted these as "stopping" in the deepest traversed stave.
v3 removes 3060 such tracks (5.0% of all charged tracks) from the comparison.

## Stopping Fractions

| Stave | MC (v3) | Data (all) | Data S-I | Data S-II |
|-------|---------|-----------|---------|---------|
| B2 | 0.475 | 0.894 | 0.944 | 0.712 |
| B4 | 0.188 | 0.054 | 0.031 | 0.137 |
| B6 | 0.117 | 0.032 | 0.016 | 0.091 |
| B8 | 0.220 | 0.020 | 0.009 | 0.060 |

## Physical Interpretation

The threshold removes all through-going protons from the MC comparison (they deposit
< 1.4 MeV per stave). The remaining MC tracks are:
- Stopping protons/deuterons in each stave (Bragg peak deposits all remaining KE)
- Near-stopping tracks with high dE/dx (approaching end of range)

Remaining χ²/ndf = 86135.5 discrepancy sources:
1. Sample I/II trigger not simulated in MC (Sample II data has deeper stopping profile)
2. Gain uncertainty ±30% shifts all MC fractions
3. Data B2 includes pile-up events (extra B2 pulses inflate B2 stopping fraction)
4. CD₂ target thickness and upstream material budget uncertainty

## MC Verdict

**FAIL**: Significant discrepancy persists. Possible: CD2 geometry or material budget error in MC.
