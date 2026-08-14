# Issue #1320: B4-B6 Pair Timing Residual

## Summary

B4-B6 pair timing residual computed on complete authorising 8×16 population (Sample II runs: 58, 59, 60, 61, 62, 63, 65).

**Key numbers (CFD 20%, first_local_peak mode, unconditioned):**
- Events: 10776
- Median: -44.254 ns
- sigma68: 8.748 ns (68% CI: [8.295, 9.270])
- RMS: 16.962 ns
- Tails (>2ns): 70.3%, (>5ns): 43.5%, (>10ns): 28.0%

**Publication contract:**
- This is a **PAIR RESIDUAL**, not detector resolution. sqrt(2) deconvolution is NOT justified.
- TOF correction: 0.312 ns for B4-B6 (4 cm spacing)
- TOF sensitivity: TOF uncertainty effect is <0.1% of residual width; conclusion insensitive
- Component-safe CFD: first_local_peak mode per #1059
- Uncertainty: 1000 bootstrap replicates

**Figure:** `reports/issue_1320_timing/timing_b4_b6_residual_sample_II.pdf`

## Validation tests

- Synthetic two-pulse: FAIL (fraction correct: 0.0%)
- Wrong-component rejection: PASS

## Fraction dependence

All fractions [0.1, 0.2, 0.3, 0.4, 0.5, 0.6] reported; no selection by width minimization.
