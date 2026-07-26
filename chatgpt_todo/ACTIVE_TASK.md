# Active Task

- **Task ID:** `AUD-DELTAE-007`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T050335Z`
- **Initial remote main SHA:** `6c25424ae2507396d352d0b7e45d737752b2872d`
- **Scope:** prevent present malformed, missing-value, NaN, or infinite DeltaE signal cells from being
  silently converted to zero before stopping-layer, energy-sum, join, plotting, or result publication.
- **Policy:** `DELTAE_PRESENT_SIGNAL_CELLS_MUST_BE_FINITE_NUMERIC`.
- **Repository facts under review:** the current numerical core uses `pd.to_numeric(..., errors="coerce")`
  followed by `fillna(0.0)` for present B-layer columns; extra MC `edep_B*` columns participate in
  stopping and full-downstream energy but are not all validated for finiteness.
- **Assumption:** a wholly absent supported downstream layer may retain the documented zero-fill
  convention, but a present cell is measured input and must not be reclassified as an absent layer.
- **Planned files:** canonical DeltaE front door, focused tests, fail-closed audit, machine-readable
  validation, SVG evidence, audit report, backlog/session log, immutable archive, and handoff.
- **Validation plan:** compile exact proposed Python; run synthetic finite, malformed, NaN, infinity,
  extra-MC-layer, missing-column, metadata, CLI-failure, UTF-8, atomic-output, and alias controls;
  parse JSON/SVG; inspect line lengths and exact Git blobs; re-read remote `main` before final handoff.
- **Scientific boundary:** this software-integrity unit does not authorize the A-002 amplitude
  convention, pulse polarity, stopping fractions, DeltaE-E PID, uncertainty, calibration, or detector
  performance.
- **Status:** `ACTIVE`
