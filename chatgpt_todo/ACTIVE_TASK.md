# Active Task

- **Task ID:** `WKS-NULL-SCALE-001`
- **Owner:** hourly Atomic Research Universe audit session
- **Session stamp:** `2026-08-10T132700Z`
- **Current remote main SHA:** `a1d7afe17e526c0e90761e8d7da4924eea5862e5`
- **Just validated/merged:** PR `#1165` exact head `930f08df435bd42532707f078501c396fb1da37d`; MC Validation run `31391922666` succeeded with `1337 passed, 1 skipped, 8 xfailed, 1 xpassed`; squash merge `a1d7afe17e526c0e90761e8d7da4924eea5862e5` preserves the event-cluster representation falsifier under #1164.
- **Selected atom:** issue `#1166`, fitted Sample-II median-ratio scale and fit/test membership topology inside any future weighted-null calibration.
- **Repository topology:** canonical DATA Sample-I analysis runs 44–57 are disjoint from Sample-II analysis runs 58–63,65; MC Sample I is a coincidence subset of Sample II (`ENTER B`). The Sample-II scale is reused in Sample-I and Sample-II discrepancies.
- **Synthetic nuisance falsifier:** equal-weight lognormal null, 200 trials, 80 DATA, 160 MC, 99 bootstrap replicates/trial, seed base 20260810. Fixed fitted scale rejects 0.000/0.015 at alpha 0.05/0.10; refitting inside each replicate gives 0.060/0.095. Method research only.
- **Synthetic topology falsifier:** 2,000 trials, seed 20260811. Preserving MC-I subset-of-MC-II gives corr(scale, median MC-I) `-0.43589`; replacing MC-I with an independent same-marginal sample gives `0.00332` and shifts mean/95th-percentile Sample-I `D` from `0.14927/0.24080` to `0.15842/0.25758`.
- **Implementation branch:** `research/wks-null-scale-topology` adds executable research-only scale/topology falsifiers, focused tests, machine-readable results and immutable ARU record. No production p-value is implemented.
- **Cross-scale blockers:** #1164 source-event IDs/membership, #1052 matched event/stave detector response, #994 truth-type-specific ADC/MeV quantity identity, #880/#1022 weights, #1027 saturation/ties.
- **Claim state:** weighted `D` remains descriptive; legacy numeric p-value remains `NONAUTHORISING_BLOCKED_ISSUE_1049`; CL-013 remains `GATED`; no detector-performance number changed.
- **Next atom after this branch:** producer-level event/membership metadata and matched event/stave response (#1164/#1052), then rerun the nuisance/null design with real source-bound clusters and nonuniform weights.
- **Status:** `ACTIVE / PARTIAL`
