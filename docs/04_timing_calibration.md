# 04 — Timing calibration

The corrected per-pulse time is

```
t_i^corr = t_i,OF^raw − f_i(A_i, x_i) − C_i − R_{i,run} − t_{i,TOF}
```

stored as **`t_v3_ns`**, where:
- **f_i(A_i, x_i)** — empirical amplitude/shape **timewalk** correction (per stave),
- **C_i** — fixed stave offset,
- **R_{i,run}** — run-dependent offset,
- **t_{i,TOF}** — expected time-of-flight offset (only when forming inter-stave residuals).

## Timewalk correction f_i
- A **robust regression** of clean same-particle multi-stave residuals on shape observables
  **x_i = {log A, tail fraction, late fraction, area/peak, plateau width, template residual}**.
- **Fit only on clean same-particle candidates** (`usable_for_precision_timing=True`, ≥2
  recalculated staves). Terminal-B2 / secondary / late-overlap topologies are **excluded** —
  the rule is "timewalk calibration ⇔ clean same-particle candidate only".
- **B2-blind:** in the newer report B2 is excluded entirely from the timewalk correction
  (δ_B2 = 0); the downstream reference set is {B4, B6, B8}.

## Offsets
- **Newer report: no per-run/per-stave offset** (C_i and R_{i,run} set to 0) — deliberate, to
  avoid circularly using inter-stave timing to align staves.
- Older v41 note: included fixed stave offset C_i and run offset R_{i,run}.
- **TOF reference energy changed 100 MeV → 40 MeV** between notes.

## Expected offsets (40 MeV proton, 2 cm/layer)
- Inter-stave TOF: B2–B4 0.156 ns, B2–B6 0.312, …, B6–B8 0.156 ns.
- ±10° angular spread: 0.001–0.004 ns (negligible).
- Pairwise WLS shift: ≤ 0.062 ns. **Absolute one-ended WLS over 1 m = 5.88 ns (1.70 ns RMS)**
  but common-mode for same-end parallel staves — cancels in pair residuals.

## Event-level timing "labels"
Event timing span **Δt_B = max(t_i^corr) − min(t_i^corr)** over selected B-pulses:
- "similar" Δt_B < 10 ns, "intermediate" 10–20 ns, "different" ≥ 20 ns.
These are **diagnostic categories, not hard cuts**.

## ⚠ Circularity to watch
The timewalk correction is fit on inter-stave residuals and then judged on the same residuals.
The authors mitigate this by excluding B2 and unclean events and by adding no run/stave
offset — but any **closure / held-out-run test** is still owed (Study S03). The validity of
the correction is *conditional on the same-particle topology being true*.

## Calibration strategy (recommended in the notes)
Keep the template **global** per stave/amplitude bin (do not refit run-by-run unless a closure
test fails); timewalk global per stave excluding terminal Sample I B2 pairs; absorb run drift
only into a low-dimensional R_{i,run}; use `q_template` as a run-by-run stability monitor;
**validate with a held-out-run closure test**.
