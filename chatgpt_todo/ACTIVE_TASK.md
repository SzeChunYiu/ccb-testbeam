# Active Task

- **Task ID:** `AUD-FIG-006-R1`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T192823Z`
- **Initial remote main SHA:** `cbc5ef1cc194ae976ffb05a0f7a2305ec8428088`
- **Trigger:** `AUD-FIG-006` proved that BLOCKED, QUARANTINED, failed, removed, or kind-changed registry entries can leave older managed paper artifacts at canonical paths.
- **Policy:** `FIGURE_REGISTRY_BUILD_MUST_NOT_LEAVE_STALE_ARTIFACTS`.
- **Scope:** implement a complete per-entry managed-output inventory; reconcile previous report paths against the current registry; remove stale outputs for non-PASS, failed, removed, and kind/suffix-changed entries; reject path escape or unsafe prior-report paths; roll managed artifacts back if final report publication fails; add direct regressions and reproducible JSON/SVG evidence.
- **Assumptions:** `build_report.json` is the authoritative prior managed-output manifest when present; no scientific value is authorized merely because an artifact exists; unrelated files beneath the output directory must be preserved.
- **Files:** `tools/figure_registry/builder.py`, focused tests, remediation evidence/report, `chatgpt_todo/` archive/handoff/session records, and directly affected coordination indexes.
- **Validation plan:** reconstruct exact current sources locally; compile changed Python; run existing figure-registry integrity suites plus new direct lifecycle regressions; run the exact-source stale-artifact auditor; parse JSON/SVG; inspect diffs and line lengths; verify remote-main delivery without force-push.
- **Progress:** `ACTIVE`.
- **Acceptance target:** focused software remediation `VALIDATED / COMPLETE`; no paper or detector-performance claim changed.
