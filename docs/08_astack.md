# 08 — A-stack (Samples III / IV)

The A-stack analysis is **deliberately decoupled** from the B-stack: *no A-stack result is used
to calibrate or interpret any B-stack result, and vice versa*. It serves as an **external
cross-check** only.

## Channels
Only **A1 and A3** are usable (A2/A4 channels have no selected pulses; odd duplicate
readout-side channels dropped). So the A-stack is a **two-stave** telescope — weaker than the
four-stave B-stack.

## Samples
- **Sample III** = same runs/split as Sample I (calib 31–42, analysis 44–57).
- **Sample IV** = same as Sample II (calib 64, analysis 58–63, 65) — **very low statistics**.

## Counts (A>1000 ADC)
- Sample III analysis: 7,168 events / 9,682 A-pulses (mult 1.351).
- Sample IV analysis: 767 events / 894 A-pulses (mult 1.166).
- Amplitudes: A1 median ~2562 (III) / 1945 (IV); A3 ~1952 (III) / 2227 (IV). **0% above 7000
  ADC** — no high-amplitude A pulses (contrast B2's 30–40% tail).

## Timing
A-stack timing = a simple two-stave empirical amplitude correction from A-stack calibration
data, applied to A-stack analysis runs.
- **Sample III A1–A3 residual:** robust width **1.43 ns**, 84.3% within |Δt|<2 ns;
  Gaussian-core σ **1.41 ns** (χ²/ndf 1.79).
- **Sample IV:** robust width 1.61 ns (core σ 1.60 ns) — flagged as a **limited-statistics
  stability check**, not a precision result.

## A–B cross-stack (App. C/D)
- Event-matched by (run, event). A/B are correlated at the **event** level but the **amplitude**
  correlation is broad — A-stack is **not** an amplitude calibration of B.
- For B2>7000 ADC events, ~97–98% have **no downstream B companion** and only ~1% have an
  A1/A3 partner >2000 ADC → the high-B2 population is overwhelmingly **B2-local/terminal**, not
  through-going. A-tag must be carried as a **topology label, not a veto**.

## Status
Only **Sample III** has useful A-stack statistics. Treat all A-stack numbers as a cross-check
on the B-stack timing scale, and reproduce them independently (they are a good, smaller-scale
warm-up for the atomic-reproduction studies).
