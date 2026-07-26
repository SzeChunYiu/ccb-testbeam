# Active Task

- **Task ID:** `AUD-LEDGER-004-R1`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T091312Z`
- **Initial remote main SHA:** `a5d66f563029183e170c24f5412fffc4e336d602`
- **Scope:** remediate the data-side Rmax producer, report, and canonical `CL-010` row so selected-pulse occupancy cannot authorize an absolute rate.
- **Policy:** `OCCUPANCY_DOES_NOT_IDENTIFY_ABSOLUTE_RMAX_WITHOUT_RATE_EXPOSURE`.
- **Repository facts:** the selected table measures 640,737 pulses over 584,602 composite events; it does not measure arrival-rate exposure, an accepted `mu_max`, or a detector-wide live window. The exact `CL-011` estimand is 124.79018394263471 ns; `0.38 / tau` is a convention-dependent sensitivity only.
- **Files:** `scripts/studies/data_side_real_beam.py`, `reports/studies/data_side/REPORT.md`, `docs/claim_ledger.csv`, focused regression, validation evidence, immutable archive, handoff, and session log.
- **Validation plan:** compile changed Python; run the direct Rmax regression; run the existing `audit_data_side_rmax_semantics.py` contract against the exact remediated tree; parse JSON/SVG; verify 43-column ledger width; inspect remote-main history and blobs after delivery.
- **Acceptance:** producer/report/ledger contract must return zero findings; accepted Rmax remains withheld under `S-STAT-003`; no raw-data rerun or detector-rate claim is authorized.
- **Status:** `ACTIVE`
