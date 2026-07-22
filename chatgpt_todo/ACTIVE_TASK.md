# Active Task

- **Task ID:** AUD-DELTAE-001
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-22T09:01:34Z
- **Base main SHA:** `59739b65e8b8002984196a6d924f39c4eec75a7b`
- **Primary scope:** audit and correct A-002 ΔE–E event-table cardinality.
- **Files inspected:** `reports/reaudit_20260720/lunarc_results/deltaE_a002/REPORT.md`, `result.json`, `scripts/single_stave/deltaE_E_data_bridge.py`, canonical `deltaE_E.py`, and coordination files.
- **Observed fact:** the report declares 385,984 physical events, while its mutually exclusive stopping bins sum to 632,939. The bridge included `eventno` in the pivot index, splitting one physical `(run, evt)` into multiple rows.
- **Implementation:** bridge now aggregates by `(run, evt, stave)`, excludes `eventno` from event identity, records multi-eventno physical keys, and enforces output/stopping cardinality invariants.
- **Validation:** synthetic regression suite passed with `2 passed in 2.65s`.
- **Evidence boundary:** the approximately 38% eventno-collision diagnostic remains internally consistent; the committed stopping profile, event CSV row count, and ΔE–E density are quarantined pending a real-table rerun.
- **Progress:** code, regression tests, invalidation notice, and backlog task are on remote `main`.
- **Acceptance status:** PARTIAL — code correction validated; real A-002 JSON/CSV/figure regeneration remains BLOCKED_COMPUTE.
