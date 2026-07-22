# Active Task

- **Task ID:** AUD-AMP-001
- **Owner:** scheduled ChatGPT audit session
- **Session stamp:** 2026-07-22T18:04:00Z
- **Base main SHA:** `df73792f871073cf716c137ee0810717395a5abf`
- **Primary scope:** prevent raw-median-only `amplitude_adc` convention labels from being accepted as physical semantics.
- **Observed fact:** the historical corpus labels several `ABSOLUTE` tables at medians 3096.5–3419 ADC, overlapping the current default `NET` range (`<=3500 ADC`); raw median alone is therefore not an identifying observable.
- **Implementation:** version 2.6.0 records `PEDESTAL_ANCHORED` versus `RAW_MEDIAN_HEURISTIC`, marks median-only labels `UNANCHORED`, keeps `subtract_baseline_correct` unresolved, counts `n_unanchored_conventions`, and returns nonzero for any unanchored table.
- **Validation:** exact reconstructed source and focused regression passed `python -m py_compile ...` and `python -m pytest /tmp/amp26/tests -q` with `3 passed in 0.08s`.
- **Evidence boundary:** no real pulse table was accessed and the historical 17/2 corpus classification was not rerun.
- **Progress:** code, regression test, and immutable archive are committed directly to remote `main`.
- **Acceptance status:** PARTIAL — the unanchored-convention gate is validated synthetically; real-table convention evidence and regenerated A-002 artifacts remain blocked.
