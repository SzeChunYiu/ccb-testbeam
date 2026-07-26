# Active Task

- **Task ID:** `AUD-TIMING-003-R1`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T190253Z`
- **Initial remote main SHA:** `be97e1a1e77de3bba6305f28802d1c876d2d1605`
- **Concurrent change detected:** PR #939 merged as the initial main head after prior audits had already demonstrated event-identity, residual-visualization, and single-stave-inference defects.
- **Scope:** remediate the merged real-data CFD producer and quarantine its generated bundle without fabricating a ROOT rerun.
- **Policy:** `REAL_DATA_CFD_REQUIRES_COMPOSITE_EVENT_KEYS_AND_PAIR_ONLY_INFERENCE`.
- **Files:** `scripts/real_data_cfd_contract.py`, `scripts/real_data_cfd_timing.py`, focused tests, report/result quarantine, reproducible JSON/SVG evidence, audit record, archive, and handoff.
- **Assumptions:** `EVENTNO` may repeat across runs; B6-B8 pair data alone do not identify either individual stave; existing PNGs cannot be regenerated without immutable ROOT inputs.
- **Validation plan:** compile changed Python, run focused functional regressions, run deterministic composite-key/tail controls, parse JSON/SVG, inspect line lengths, verify direct-main history and remote file identities.
- **Progress:** `ACTIVE`.
- **Acceptance target:** focused software remediation `VALIDATED`; physics result remains `PAIR_ONLY_PENDING_CONTENT_ADDRESSED_RERUN`.
