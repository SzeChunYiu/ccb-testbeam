# Active Task

- **Task ID:** AUD-MV3-SEL-002
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-25T230502Z
- **Initial remote main SHA:** `feddba9e3cc488fd77e7bc015f80af9d78f6edd1`
- **Scope:** remediate the merged MV3 selection-matched producer and source report after
  `AUD-MV3-SEL-001` confirmed fail-open MC weights, positive-charge-only selection,
  target-changing improvement arithmetic, and unsupported shape-closure wording.
- **Assumptions:** the tracked one-million-event summary and PNGs are preserved as historical
  unweighted diagnostics; no numerical production result is authorized without an immutable
  weighted rerun.
- **Files:** `scripts/studies/mv3_selection_matched.py`,
  `tests/test_mv3_selection_weighted_contract.py`,
  `reports/studies/mv3_selection_matched/REPORT.md`, focused validation evidence, archive,
  `HANDOFF.md`, and `SESSION_LOG.md` where a byte-safe append can be completed.
- **Correction:** require exactly one finite nonnegative `PrimaryWeight` per event, use canonical
  signed-charge selection, publish weighted primary plus unweighted sensitivity profiles, record
  sums and ESS, compare against one fixed Sample-I data target, hash declared inputs, and publish
  JSON atomically.
- **Validation plan:** compile producer/test/renderer; run focused pytest; regenerate and parse
  machine-readable and SVG evidence; verify changed Python line lengths; inspect staged content and
  remote-main history after every direct write.
- **Progress:** implementation, eight regressions, source-report quarantine, validation JSON,
  renderer, and SVG are locally validated on exact prepared bytes.
- **Focused status:** `ACTIVE` until the validated bytes and handoff are confirmed on remote
  `main`; expected completion is software-contract `VALIDATED`, production result `BLOCKED`.
- **Scientific boundary:** no ROOT or beam-data file has been rerun; no weighted stopping profile,
  covariance, scattering/material correction, calibration, PID result, or detector-performance
  result is claimed.
