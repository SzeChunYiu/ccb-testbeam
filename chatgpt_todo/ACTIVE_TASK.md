# Active Task

- **Task ID:** `ARU-WKS-NULL-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T122500Z`
- **Current remote main SHA:** `97386889c1820e45b6ce04ba7ddfbda7128f2f46`
- **Just validated/merged:** PR `#1162` on exact head `b8f9c6a363f9a2a7f658978641392f76605c9a46`; MC Validation run `31387574136` succeeded with `1329 passed, 1 skipped, 8 xfailed, 1 xpassed`; squash merge `97386889c1820e45b6ce04ba7ddfbda7128f2f46` closed #1051.
- **Observed-statistic state:** `scripts/compare_data_mc.py` v5 now uses a unique-support, tie-aggregated, right-continuous weighted ECDF and exact union-support supremum `D`; interpolation-based ECDF evaluation is no longer canonical.
- **Inference boundary:** the retained numerical permutation p-value is explicitly `NONAUTHORISING_BLOCKED_ISSUE_1049`; no goodness-of-fit probability is authorised by #1162.
- **External-data boundary:** real DATA/MC campaign artifacts were not available in this runtime, so corrected real `D` values have not been regenerated and no detector-performance claim changes.
- **Selected next atom:** issue `#1049` / `ARU-WKS-NULL-001`, define and validate a design-consistent null/calibration for the weighted DATA/MC discrepancy without discarding PrimaryWeight, while accounting for the fitted MeV->ADC nuisance scale and the actual statistical unit.
- **Dependencies:** #880 documents non-unit positive PrimaryWeight in the audited MC campaign; #1022 remains open for canonical DeltaE-E/penetration weight propagation; #1027 owns ADC saturation semantics. Do not invent signed-weight or iid assumptions not established by the concrete product.
- **Status:** `ACTIVE / TRIAGED`
