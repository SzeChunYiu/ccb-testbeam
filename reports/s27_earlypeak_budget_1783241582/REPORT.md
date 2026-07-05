# S27 — Early-peak class leakage budget (B-M8)

- Generated: 2026-07-05 08:53:11 UTC
- Git commit: `b85f11bc75f4d95e48a7037aad5c7939135262c3`
- Early-peak definition: peak_sample = argmax(baseline-subtracted) <= 3 (P02/P03f).
- Selection: A>1000 ADC, valid CFD20; downstream B4/B6/B8.
- Timing/tau_eff on raw analysis runs [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65]; counts/area from the canonical s00 table.

## Per-observable leakage bounds

| observable | with early-peak | early-peak excluded | leakage |
|---|---|---|---|
| (i) downstream pair sigma68 (ns) | 1.706 | 1.648 | +0.058 [+0.047, +0.068] |
| (ii) live10 tau_eff (ns) | 131.62 | 144.87 | -13.25 |
| (iii) pile-up/current: early-peak count share | 3.41% | — | area share -1.25% |

- Early-peak pulses are 4.09% of downstream pairs and 3.41% of selected pulses (A>1000). The standard A>1000 + valid-CFD selection does NOT remove them; the bounds above quantify what each headline carries.
- Current/charge proxy: the early class carries -1.25% of the integrated selected-pulse area (area/count excess factor -0.37 — >1 means early-peak pulses are on average smaller in area).

## Interpretation

- **Timing:** excluding the early-peak class moves the downstream pair sigma68 by +0.058 ns (95% CI [+0.047, +0.068]). This is the systematic the timing headline carries from the unexplained class.
- **tau_eff:** the live-time shifts by -13.25 ns when the class is excluded (data anchor 124.79 ns).
- **Pile-up/current:** the class is 3.41% of counts and -1.25% of integrated area — the fractional bound on any occupancy-/current-derived quantity.

## Caveats
- peak_sample<=3 is a coarse (10 ns sampling) morphological tag, not a physical class label;
  it over- and under-counts the true instrumental population at the edges.
- Timing/tau_eff are measured on the staged analysis runs (44-63,65); the canonical s00 table
  spans the full dataset (calibration runs included) for the count/area budget.
- The cause of the class remains open (C12 excluded, MV6b); this budget bounds its leakage, it
  does not identify it.
