# MV0 -- Digitizer Gain Calibration (v2, corrected)

- status: **PRODUCTION (v2)**  
- generated: 2026-06-28T22:40:00+00:00  
- MC: `geant4/data/output_krakow_1M.root`  
- data: `s00_selected_b_pulses.csv.gz` (640,737 B-pulse records)

## Summary

Gain = **92 ± 28 ADC/MeV** (median matching, B2 stave, ±30% systematic).  
The gain converts MC truth EDep (MeV) to expected digitized peak amplitude (ADC), after subtracting the hardware baseline.

## Reproduce

```
python3 scripts/mv0_calibrate_from_data.py \
  --mc geant4/data/output_krakow_1M.root \
  --data <path to s00_selected_b_pulses.csv.gz> \
  --out reports/mv0_calibration/
```

## Data Amplitude Convention

The HRD ADC records are negative-going (particle signal drives the ADC below the DC pedestal):

| Column | Meaning |
|--------|---------|
| `baseline_adc` | Hardware pedestal, estimated from pre-pulse samples ≈ 6752 ADC (B2), range 6737–7029 |
| `amplitude_adc` | Absolute ADC value at the pulse peak (NOT pedestal-subtracted) |
| **net signal** | `abs(amplitude_adc − baseline_adc)` — the quantity comparable to MC |

B4/B6/B8: 100% negative-going pulses (amplitude < baseline). B2: 65% negative, 35% positive (due to baseline instability under pile-up; std(baseline_B2)=844 vs 500–630 for downstream staves).

## MC-to-Data Mapping

For each B-arm truth track, the expected B2 peak amplitude is:

```
peak_adc = gain × edep_B2 × peak_frac
```

where:
- `edep_B2 = edep_l0 + edep_l1` (truth EDep in layers 0 and 1 = B2 stave, from NPZ)
- `peak_frac = 0.733` — peak-bin value of the unit scintillation pulse (τ_rise=2.5 ns, τ_decay=42 ns, 10 ns bins, 5 sub-integration points): ∑f(t_sub)/N_sub at sample 0

## Calibration Result

| Quantity | Value |
|---------|-------|
| MC B2 edep median | 26.44 MeV |
| Data B2 net_adc median | 1781 ADC |
| **Gain (median matching)** | **92 ADC/MeV** |
| Peak fraction | 0.733 |
| KS optimal gain | 60 ADC/MeV (KS=0.119) |
| KS at gain=92 | 0.158 |

The shape mismatch (KS=0.12–0.16) arises because:
1. Data B2 includes pile-up events absent in MC (579k data vs 321k MC B2 hits)
2. Mixed pulse polarity in B2 suppresses the apparent median
3. The MC stopping-fraction distribution in B2 differs from data (no trigger-timing simulation)

## Systematic Uncertainty

±30% on the gain (range 64–120 ADC/MeV across staves and methods):

| Source | Stave | Implied gain |
|--------|-------|-------------|
| B2 median matching (net_adc) | B2 | 92 ADC/MeV |
| B4 median matching (net_adc, MC EDep from ROOT) | B4 | ~91 ADC/MeV (old calib, not corrected) |
| B6 median matching | B6 | ~64 ADC/MeV (old calib) |
| B8 median matching | B8 | ~78 ADC/MeV (old calib) |

The B2 estimate (92) is the most reliable: largest statistics, fewest MC extrapolation steps.

## Previous Error (v1)

v1 compared:
- Data: raw `amplitude_adc` (includes hardware pedestal of ~6752 ADC)  
- MC: `gain × edep × shape + digitizer_pedestal` (digitizer pedestal = 350 ADC — completely different scale)

This gave a spurious best gain of 110 ADC/MeV with χ²/ndf = 2934 and a nonsensical "pedestal" of 6758 ADC. The v2 comparison uses net signal in both data and MC, making the comparison self-consistent.

## Impact on Downstream Studies

| Study | Effect of gain update (110 → 92) |
|-------|----------------------------------|
| MV4 timing | σ₆₈_raw changes by < 0.05 ns (timing depends on SNR, weakly on absolute gain) |
| MV5 pile-up | Rmax from dead-time model is gain-independent |
| MV6 representation | PCA/GMM clusters shape depends on pulse shape, not gain scale |
| PID (MV1) | AUC unchanged (uses truth labels, not amplitude) |
| Energy (MV2) | Absolute scale shifts by 20% but relative ranking unchanged |
