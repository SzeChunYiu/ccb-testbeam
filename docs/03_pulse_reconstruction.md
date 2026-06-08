# 03 — Pulse reconstruction

From each 18-sample waveform we extract a pedestal, amplitude, time, and shape variables.
All of this is **traditional (non-ML)** signal processing — it is the baseline against which
any ML pulse model must be benchmarked.

## 1. Pedestal (baseline)
- **Seed:** b₀ = median(w₀..w₃) (first four samples). Provisional y_j = w_j − b₀,
  A⁽⁰⁾ = max y_j.
- **Adaptive, positivity-constrained pedestal:** negative tolerance
  ε(A⁽⁰⁾) = max(25 ADC, 0.015·A⁽⁰⁾). The pedestal is lowered only as needed so the minimum
  non-jagged corrected sample ≥ −ε. The lowering (b₀ − b_pc) is **kept as a diagnostic** (large
  lowering ⇒ contaminated first-four-sample pedestal, common in B2/late-overlap topologies).
- ⚠ The "fraction below tolerance = 0% after correction" is **0 by construction** — it is not
  an independent validation (see [09_open_questions.md](09_open_questions.md)).

## 2. Jagged-sample masking
A sample is "jagged" if it dips to ~0/negative between two high neighbours
(y_{j−1}>f_high·A and y_{j+1}>f_high·A while y_j ≲ f₀·A or < −y_neg). Jagged samples are
**masked** (excluded from the time fit), not the whole pulse; jagged fraction is recorded.

## 3. Amplitude-adaptive template
No single fixed template: high-amplitude B2 and downstream pulses change shape (ionisation
quenching / Birks, non-linear light transport). So a template **s_i(j; A)** is built **per
stave (B2/B4/B6/B8) and per amplitude bin**: align with a constant-fraction seed, divide by
amplitude, median-combine; interpolate in log₁₀A during fitting.
- ⚠ **Not yet evaluated on the full dataset** — the q_template numbers in the notes come from
  an old small subset. Re-running this is an explicit TODO (Study S01).

## 4. Time pickoff
- **Seed — CFD20:** software digital constant-fraction at **20% of peak** on the rising edge;
  level y₂₀ = 0.20·A, interpolated between bracketing samples. A *software* primitive, not a
  hardware discriminator. (Why 20%? Unscanned — Study S02.)
- **Optimal-filter (OF) fit:** linearised template + derivative model around the seed,
  y_j = c + A_fit s_j(A) − A_fit δ s′_j(A) + η u_j + n_j, solved by weighted least squares over
  **non-jagged** samples. Sub-sample shift δ ⇒ raw time
  t_OF^raw = (t_CFD20^bin + δ)·Δt_samp → column **`t_v3_raw_of_ns`**.
- This is a **leading-edge / template-phase** estimate, **not** a peak-time or centroid.

## 5. v3 vs v4
- **v3 = precision-timing definition** used for ALL timing tables/figures. Disables the bad B8
  full-pulse branch; leading-edge/amplitude-adaptive for every stave. Output **`t_v3_ns`**
  (after timewalk + offsets, see [04](04_timing_calibration.md)).
- **v4 = full-waveform description model** (13 parameters: templates, derivative, polynomial
  baseline, pre-peak + post-peak exponentials, end-exponentials; up-weighted start/end
  samples; quality `q_desc`). Used for **pulse description, not timing**.

## Pulse-shape variables (feature set)
`log A`, **tail fraction**, **late fraction**, **area/peak**, **plateau width**,
**template residual**, **quench proxy**, peak-bin & CFD positions, max negative step, number
of large downward steps, post-peak minimum, final-sample fraction, and the 18 normalised
samples. These feed both the traditional cuts/corrections and the ML models.
