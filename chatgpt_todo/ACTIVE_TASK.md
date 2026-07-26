# Active Task

- **Task ID:** `AUD-TIMING-003`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T143114Z`
- **Initial remote main SHA:** `f4b5f193838effbf0ab9c82911a4fb8652eced8a`
- **Scope:** audit whether PR #939 can convert the B6-B8 pair `sigma68` to a B6 single-stave resolution by dividing by `sqrt(2)`.
- **Policy:** `PAIR_SIGMA68_DIV_SQRT2_REQUIRES_VALIDATED_IDENTICAL_INDEPENDENT_GAUSSIAN_OR_EXPLICIT_DECONVOLUTION`.
- **Finding:** PR #939 promotes a pair-only robust width to `0.635 ns` single-stave resolution without individual B6/B8 constraints, covariance/common-mode treatment, distributional deconvolution, or propagated single-stave uncertainty. Its own diagnostics are strongly non-Gaussian (`RMS/sigma68 = 10.794`, tail fraction `0.159`).
- **Delivered:** fail-closed source/result auditor, six focused regressions, deterministic counterexamples, connector-inspected fixtures, JSON, SVG, Markdown audit, immutable archive, and reproducible handoff.
- **Validation:** `python -m py_compile` passed; focused pytest returned `6 passed in 0.24s`; current-like fixture returned `FLAWED` with eight findings; corrected pair-only fixture returned zero findings; JSON/SVG parsed; changed Python lines are at most 100 characters.
- **Acceptance:** audit implementation and evidence `VALIDATED / COMPLETE`; PR #939 single-stave inference and broader timing acceptance remain `FLAWED / PARTIAL`.
- **Scientific boundary:** no ROOT bytes were rerun and no event identity, channel map, waveform calibration, CFD estimator, pair width, single-stave resolution, or `CL-002` claim was validated.
- **Next action:** keep the result pair-only unless a three-detector/external-reference/hierarchical deconvolution with covariance and uncertainty is validated; fix the existing PR event-identity and visualization defects before any merge.
- **Status:** `COMPLETE`
