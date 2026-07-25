# Active Task

- **Task ID:** AUD-MV3-SEL-003
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T233022Z
- **Initial remote main SHA:** `0aa777457fff37a817bce29a7ea1656683210ddf`
- **Scope:** audit the weighted MV3 producer's Pearson chi-square implementation for unsupported
  observed categories, malformed profile normalization, and fail-closed statistical semantics.
- **Repository fact under review:** `_chi2` currently masks bins with zero expected count before
  calculating the statistic. With at least two supported bins, an observed positive count in a
  zero-probability category can therefore be omitted rather than rejected.
- **Assumptions:** this is a software/statistical-contract review. No production ROOT or beam-data
  input is available, and no canonical `CL-021` upgrade is authorized.
- **Files:** `tools/audit/audit_mv3_chi2_support.py`, focused tests, validation JSON/SVG/report,
  immutable archive, this record, `HANDOFF.md`, and an append to `SESSION_LOG.md` when complete.
- **Validation plan:** run exact synthetic controls against the current and corrected contracts;
  compile all new Python; run focused pytest; parse JSON and SVG; verify deterministic atomic output,
  invalid UTF-8 handling, input/output alias protection, and changed-line length.
- **Focused status:** `ACTIVE`.
- **Scientific boundary:** the audit can establish a statistical implementation defect and a
  fail-closed replacement contract only. It cannot establish stopping-profile closure, covariance,
  material/scattering attribution, calibration, PID, or detector performance.
