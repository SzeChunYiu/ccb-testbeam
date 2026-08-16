# Issue #1320: B4-B6 Pair Timing Residual

## Summary

B4-B6 pair timing residual computed on complete authorising 8×16 population (Sample II runs: 58, 59, 60, 61, 62, 63, 65).

**Key numbers (CFD 20%, first_local_peak mode, unconditioned):**
- Events: 228697
- Median: -9.673 ns
- sigma68: 0.146 ns (68% CI: [0.144, 0.148])
- RMS: 3.947 ns
- Tails (>2ns): 4.4%, (>5ns): 1.2%, (>10ns): 0.8%

**Publication contract:**
- This is a **PAIR RESIDUAL**, not detector resolution. sqrt(2) deconvolution is NOT justified.
- TOF correction: 0.312 ns for B4-B6 (4 cm spacing)
- TOF sensitivity: TOF uncertainty effect is <0.1% of residual width; conclusion insensitive
- Component-safe CFD: first_local_peak mode per #1059
- Uncertainty: 1000 bootstrap replicates

**Figure:** `reports/issue_1320_timing/timing_b4_b6_residual_sample_II.pdf`

## Validation tests

- Synthetic two-pulse: PASS (fraction correct: 100.0%)
- Wrong-component rejection: PASS

## Fraction dependence

All fractions [0.1, 0.2, 0.3, 0.4, 0.5, 0.6] reported; no selection by width minimization.
