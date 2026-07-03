# 08 — A-stack (Samples III / IV)

The A-stack analysis is **deliberately decoupled** from the B-stack: *no A-stack result is used
to calibrate or interpret any B-stack result, and vice versa*.

> **Corrected interpretation (2026-07-03, experiment-owner setup facts):** Stack A and Stack B are
> **independent detectors at conjugate angles**, each ~100 cm from the CD₂ target and each behind
> its own trigger scintillators (TPC in front of A). They measure **different particles** —
> pd-elastic sends the proton into one arm and the kinematically-correlated deuteron into the
> other; an A·B coincidence is a correlated **pair** sharing the event T0, never the same particle
> twice. A-stack results are therefore an **independent methodology check on different particles**,
> not an "external cross-check" of the same particles seen in B.

## Channels
Only **A1 and A3** are usable (A2/A4 channels have no selected pulses; odd duplicate
readout-side channels dropped). So the A-stack is a **two-stave** telescope — weaker than the
four-stave B-stack.

## Samples
- **Sample III** = same runs/split as Sample I (calib 31–42, analysis 44–57) — runs taken with
  the **A·B trigger coincidence**.
- **Sample IV** = same as Sample II (calib 64, analysis 58–63, 65) — runs taken with the
  **B trigger only** (A ignored), consistent with the **very low** A-stack statistics
  (trigger definitions: experiment-owner setup facts, 2026-07-03).

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
  correlation is broad — A-stack is **not** an amplitude calibration of B. *(Corrected reading,
  2026-07-03: this is expected — A and B record **different members of a kinematically-correlated
  pd pair**, not the same particle twice, so the event-level correlation is kinematic (pair
  correlation plus shared event T0), and any A–B timing comparison carries the pair's kinematic
  spread on top of the shared T0.)*
- For B2>7000 ADC events, ~97–98% have **no downstream B companion** and only ~1% have an
  A1/A3 partner >2000 ADC → the high-B2 population is overwhelmingly **B2-local/terminal**, not
  through-going. An A1/A3 partner, when present, is the **conjugate pair member** (a different
  particle), not the same particle re-detected. A-tag must be carried as a **topology label, not
  a veto**.

## Status
Only **Sample III** has useful A-stack statistics. Treat all A-stack numbers as an
**independent-arm methodology check** of the timing chain — the same calibration and
width-extraction machinery run on an independent detector seeing different particles, not a
cross-check of the B-stack on the same particles (2026-07-03) — and reproduce them independently
(they are a good, smaller-scale warm-up for the atomic-reproduction studies).
