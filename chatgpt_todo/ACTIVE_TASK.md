# Active Task

- **Task ID:** AUD-DATA-001
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T200019Z
- **Initial remote main SHA:** `39378e21c436344b43e9f659f5a76bce2bca1228`
- **Concurrent change:** `c39aba2c55091aec501acbe402523e2d94be2c58` merged the
  separate single-stave review during this run; it did not modify the audited Cluster A
  script, summary, tests, or validation artifacts.
- **Scope:** review and remediate the new Cluster A derived beam-data path for statistical
  unit, numeric-input, MC-weight, plot-label, and provenance integrity.
- **Confirmed defects:** nonnumeric values were silently replaced by zero; NaN and infinity
  were accepted; `PrimaryWeight` was loaded but ignored by the MC hexbin; and a table with
  632,939 rows but 385,984 composite event keys was described with event-count and stopping-
  distribution language.
- **Validated progress:** the script now performs a strict UTF-8 snapshot, rejects malformed
  or nonfinite numeric values, distinguishes row and event denominators, withholds event-level
  authorization, aligns finite nonnegative `PrimaryWeight` values to selected MC events,
  sums them in plotted bins, records full source hashes, and publishes JSON atomically.
- **Validation:** `python -m py_compile` passed; focused pytest returned `6 passed in 0.31s`;
  JSON and SVG parsing passed; changed Python lines are at most 95 characters.
- **Evidence:** `docs/validation/clusterA_data_side_semantics_audit.md`, matching JSON and
  SVG, and `tests/test_clusterA_data_side_contract.py` are committed directly to `main`.
- **Unrun checks:** production CSV/ROOT execution, regeneration of production PNGs, canonical
  composite merge, repository-wide pytest/ruff, full link inventory, and GitHub Actions.
- **Scientific boundary:** the software contract is validated; no production correlation,
  stopping distribution, data/MC closure, beam-data PID, calibration, or detector-performance
  result was regenerated or accepted.
- **Focused status:** VALIDATED software remediation.
- **Cumulative status:** PARTIAL until content-addressed production inputs are rerun and an
  event-level canonical composite-merge study passes its own acceptance gates.
