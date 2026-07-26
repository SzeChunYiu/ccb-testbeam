# Active Task

- **Task ID:** `AUD-TIMING-001`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T083435Z`
- **Initial remote main SHA:** `a8c446732e9a73d6880b313939868162ec4e2d74`
- **Observed concurrent advance:** remote `main` moved from `bd0e9254f49f963da96fc0bbafd3c7620c743645` to `a8c446732e9a73d6880b313939868162ec4e2d74` while the previous claim-ledger session finalized; the reviewed PR #939 source blob remained `ef13a859bb756dbf4b7ea6fa40f681d8858a7ac7`.
- **Scope:** audit whether open PR #939 preserves multi-run event identity when selecting in-time B6/B8 pairs, computing timing residuals, and plotting residuals.
- **Policy:** `REAL_DATA_CFD_EVENTS_MUST_USE_RUN_AND_EVENT_ID_TOGETHER`.
- **Assumptions:** `EVENTNO` is run-local unless immutable input evidence proves global uniqueness; no raw ROOT bytes are available in this environment; a software failure-mode demonstration does not prove that a retained production event was actually mispaired.
- **Files:** `tools/audit/audit_real_data_cfd_event_identity.py`, focused tests, renderer, validation JSON/SVG/Markdown, `chatgpt_todo/` ledgers, immutable archive, session log, and handoff.
- **Validation plan:** strict-UTF8/AST audit of the connector-inspected source contract; synthetic false-cross-run and duplicate-event controls; corrected composite-key fixture; invalid-UTF8, alias, and atomic-publication regressions; JSON and SVG parsing; changed-line review.
- **Progress:** exact PR head/source blob and current-main concurrency inspected; source carries `run` and `event_id` but three pivots and one selection filter use `event_id` alone; focused local implementation is under validation before direct-main delivery.
- **Scientific boundary:** no channel-map, waveform, calibration, CFD bias, timing-resolution, single-stave `pair/sqrt(2)`, or canonical `CL-002` claim is authorized by this task.
- **Status:** `ACTIVE`
