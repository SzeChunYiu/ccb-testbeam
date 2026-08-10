# Active Task

- **Task ID:** `ARU-MC01-LAYERUNIT-001 / WKS-NULL-CLUSTER-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T133600Z`
- **Current remote main SHA:** `4268175da2e282a755b7f59acc235cffee512ed4`
- **Just validated/merged:** PR `#1167` exact head `90b1688a4f0f58f3d2bc23611b8854a9b9d9d21c`; MC Validation run `31393379296` succeeded with `1347 passed, 1 skipped, 8 xfailed, 1 xpassed`; squash merge `4268175da2e282a755b7f59acc235cffee512ed4` puts the research-only fitted-scale/topology falsifiers on main.
- **Resolved local hypotheses:** freezing a scale fitted from the same comparison population is rejected as a harmless default; independently resampling MC Sample I and Sample II is rejected because the real MC trigger design has `Sample I subset Sample II`.
- **Surviving local hypotheses:** refit the nuisance inside each replicate while preserving source-event membership, or use a rigorously source-disjoint held-out calibration sample. Neither is yet validated for CCB.
- **Selected next atom:** #1164/#1052 producer boundary — preserve immutable DAQ/generator event IDs plus Sample-I/Sample-II membership and construct an event/stave detector-response hierarchy compatible with DATA rather than the legacy MC hit-record EDep array.
- **Required contract:** every inference row must bind observable/measurand, units, source-event cluster, sample-membership graph, event weight, aggregation rule, source hash/config and nuisance role. Generator weights must be applied once to the final event-level statistical unit.
- **Cross-scale blockers:** #994 truth-type-specific ADC/MeV identity, #880/#1022 weight semantics, #1027 saturation/ties, quenching/optical/SiPM/electronics chain for final detector-level closure.
- **Claim state:** weighted `D` remains descriptive; legacy numeric p-value remains `NONAUTHORISING_BLOCKED_ISSUE_1049`; CL-013 remains `GATED`; no detector-performance number changed.
- **Status:** `ACTIVE / PARTIAL`
