# Active Task

- **Task ID:** AUD-LEDGER-004
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T210216Z
- **Initial remote main SHA:** `5f4847036ab6d3ee8fb268f9ed96abc36852bbc4`
- **Scope:** audit the new real-beam occupancy-to-Rmax claim upgrade for estimand,
  uncertainty, source, and public-report integrity.
- **Confirmed defect:** selected-pulse multiplicity was used to authorize an absolute
  `Rmax=2.92 MHz` even though `mu_max=0.38` and `tau=130 ns` are assumed inputs and no
  event-arrival exposure or luminosity is present. The ledger also added unsupported
  `0.10` and `0.20 MHz` uncertainty components and removed blocker `S-STAT-003`.
- **Validated progress:** added a fail-closed validator, six focused regressions,
  machine-readable evidence, SVG evidence, an audit report, and immutable handoff.
- **Independent calculation:** the exact `CL-011` estimand gives
  `0.38 / 124.79018394263471 ns = 3.045111305987686 MHz`; this remains a model-only
  sensitivity, not a data-derived rate.
- **Validation:** `python -m py_compile` passed; focused pytest returned
  `6 passed in 0.03s`; JSON and SVG parsing passed.
- **Current repository audit:** `FLAWED` with 34 current-like contract findings.
- **Focused status:** `VALIDATED` audit gate; production claim remains `BLOCKED`.
- **Next action:** remediate the producer, report, figure metadata, and `CL-010` row in
  one content-addressed unit and require both Rmax validators to return zero findings.
- **Scientific boundary:** no raw ROOT rerun, exposure measurement, absolute rate,
  accepted Rmax, calibration, or detector-performance result was produced.
