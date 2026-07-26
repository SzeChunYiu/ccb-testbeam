# Active Task

- **Task ID:** `AUD-TIMING-002`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T130822Z`
- **Initial remote main SHA:** `0f7a8e50960d01156ea87cac435f6e25925cd1d9`
- **Validated handoff commit on remote main:** `39dd54760827ec1a155b8c3761005183690059be`
- **Scope:** audit whether PR #939 residual PNGs visually cover the same distributions used for their timing-width labels.
- **Policy:** `REAL_DATA_CFD_RESIDUAL_PLOTS_MUST_COVER_THE_REPORTED_DISTRIBUTION`.
- **Finding:** the producer plots raw B6-B8 residuals in a fixed `[-10, 10] ns` window while reporting `sigma68` from the full vectors. From the recorded medians and sigma68 values alone, at least 84% of every plotted CFD10/CFD20 distribution is guaranteed outside that window.
- **Delivered:** fail-closed AST/result auditor, six focused regressions, version-controlled connector-inspected fixtures, machine-readable JSON, SVG evidence, Markdown audit, immutable archive, and reproducible handoff.
- **Validation:** `python -m py_compile` passed; focused pytest returned `6 passed in 0.08s`; the current fixture returned `FLAWED` with six findings; centered and dynamic-range fixtures returned zero findings; JSON and SVG parsed; changed Python lines are at most 100 characters.
- **Acceptance:** audit implementation and evidence `VALIDATED / COMPLETE`; PR #939 residual visualization and scientific timing acceptance remain `FLAWED / PARTIAL`.
- **Scientific boundary:** no ROOT bytes were rerun and no event identity, channel map, waveform calibration, CFD estimator, timing resolution, single-stave inference, or `CL-002` claim was validated.
- **Next action:** repair PR #939 using `(run,event_id)` keys, regenerate residual figures with full-range and/or median-centered coverage plus underflow/overflow counts, bind outputs to immutable ROOT hashes, and rerun scientific validation before merge.
- **Status:** `COMPLETE`
