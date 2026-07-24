# Active Task

- **Task ID:** AUD-LEDGER-002
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T210523Z
- **Initial remote main SHA:** `a52ea7c3f76eddff204e8ebb990a55cfe8793e7f`
- **Latest validated evidence head:** `72f295425fee337a63d94364e1e3c27376f0a4ab`
- **Scope:** reconcile CL-019/020/021 with the exact tracked MV3 summary, independently reconstruct the Pearson diagnostic, replace the obsolete validator contract, update regressions, and produce reproducible visual evidence.
- **Completed:** CL-019/020 now bind exact B8 numerators, denominators, and fractions; CL-021 binds exact Pearson chi-square/ndf while retaining `FLAWED`; validator v2.0 and focused regression expectations are aligned; machine-readable and SVG evidence are committed.
- **Validation:** Python compilation passed; focused suites returned `11 passed`; the direct exact-source contract returned `VALIDATED` with zero issues; former ledger blob `bb552aa5ed70e7d81dcda888c5aa61402c01e03c` failed with 33 findings; JSON and SVG parsing passed.
- **Scientific boundary:** exact fixed-source arithmetic is reproducible, but geometry/material modelling, trigger and selection transfer, gain response, covariance, p-value interpretation, and detector/model systematics remain unresolved under `BLK-MV3-LEGACY-001`.
- **Remaining primary action:** synchronize stale root-WIKI MV3/GAP-01 absence wording through a byte-safe complete-file patch, then validate the public front door against the exact ledger while retaining the `FLAWED` acceptance boundary.
- **Status:** PARTIAL — canonical ledger, validator, regressions, and evidence are corrected; root-WIKI synchronization remains open.
