# Active Task

- **Task ID:** `AUD-LEDGER-004-R1`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T091312Z`
- **Initial remote main SHA:** `a5d66f563029183e170c24f5412fffc4e336d602`
- **Scope:** remediate the data-side Rmax producer, report, and canonical `CL-010` row so selected-pulse occupancy cannot authorize an absolute rate.
- **Policy:** `OCCUPANCY_DOES_NOT_IDENTIFY_ABSOLUTE_RMAX_WITHOUT_RATE_EXPOSURE`.
- **Repository facts:** the selected table measures 640,737 pulses over 584,602 composite events; it does not measure arrival-rate exposure, an accepted `mu_max`, or a detector-wide live window. The exact `CL-011` estimand is 124.79018394263471 ns; `0.38 / tau` is a convention-dependent sensitivity only.
- **Delivered:** fail-closed producer contract; corrected report; quarantined `CL-010`; focused regression; JSON/renderer/SVG/Markdown evidence; immutable archive.
- **Validation:** compilation passed; focused pytest `2 passed in 0.32s`; exact producer/report/ledger contract `VALIDATED` with zero findings; 26/26 ledger rows have exactly 43 columns; remote blobs matched locally validated bytes; JSON and SVG parsed.
- **Acceptance:** focused remediation `COMPLETE`; accepted Rmax remains withheld under `S-STAT-003`; no raw-data rerun or detector-rate claim is authorized.
- **Status:** `COMPLETE`
