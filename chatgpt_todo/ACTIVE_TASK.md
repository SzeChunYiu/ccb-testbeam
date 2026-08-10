# Active Task

- **Task ID:** `WKS-NULL-CLUSTER-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T130500Z`
- **Current remote main SHA:** `08edd7fa9acffe4ace1381a1fac9acc899084347`
- **Coordination repair:** PR `#1163` passed exact-head MC Validation and was squash-merged to main; issue `#1049` was then reopened because #1162 fixed only the observed weighted-ECDF distance, not its null calibration.
- **Selected atom:** source-event cluster identity required by any weighted DATA/MC null. New child issue `#1164` records the typed contract and links #1049 to the first-B statistical-unit defect #1052.
- **Research implementation:** branch `research/wks-null-cluster-contract` adds `tools/audit/research_weighted_null_cluster_contract.py`, focused tests, a machine-readable synthetic research result, and an immutable ARU record.
- **Local synthetic validation:** `PYTHONPATH=. pytest -q tests/test_weighted_null_cluster_research.py` -> `7 passed in 0.11s`. Five-way weighted-row splitting leaves observed `D` unchanged; cluster-bootstrap replicates agree to `3.33e-16`, while iid row-bootstrap replicates differ by up to `0.3618`.
- **Toy method boundary:** a known N(0,1) target / N(1,1) proposal importance-sampling study gave rejection fractions `0.045` at alpha 0.05 and `0.095` at alpha 0.10 over 200 trials. This is method research only, not CCB detector validation.
- **Repository blocker:** current comparison NPZs discard DAQ/generator event cluster IDs; MC first-B values are raw hit/step EDep rows and DATA values are pulse rows. A calibrated CCB null cannot be authorised from those products.
- **Claim state:** legacy numeric p-value remains `NONAUTHORISING_BLOCKED_ISSUE_1049`; CL-013 remains `GATED`; no detector-performance number changed.
- **Next atom:** implement #1164/#1052 producer-level event-cluster/statistical-unit metadata and compatible event/stave response product, then test nuisance-scale refitting inside the null.
- **Status:** `ACTIVE / PARTIAL`
