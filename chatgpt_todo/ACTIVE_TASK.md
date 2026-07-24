# Active Task

- **Task ID:** AUD-WIKI-003
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T190317Z
- **First observed remote main SHA:** `d34f99513550892e98f3e396a279952618f8623c`
- **Latest remote base before focused WIKI writes:** `51b63d9ffad4c9eb9f95cbfbfe14516c1e5780f2`
- **Scope:** validate the public WIKI canonical-results table against exact-width claim-ledger rows, remove unsupported values/status upgrades/uncertainties, and add reproducible machine-readable and visual evidence.
- **Confirmed defect:** exact pre-remediation WIKI bytes produced 31 findings across withheld timing values, unsupported uncertainties, status/truth mismatches, a missing canonical MV3 row, an analytic-timing-as-ML label, and stale PCA wording.
- **Correction:** added `validate_wiki_canonical_results.py`, focused regressions, exact-current integration coverage, synchronized the public canonical table and repeated high-level sections, and added JSON/Markdown/SVG evidence.
- **Validation:** `python -m py_compile` passed; focused suites returned `8 passed in 1.14s`; exact pre-remediation WIKI returned `FLAWED` with 31 findings; exact remote WIKI blob `fee0e1a15243904dbeb46254878ade4650a8e1f6` returned `VALIDATED` with zero findings for 11 exact 43-field bindings.
- **Evidence:** `docs/validation/wiki_canonical_results_audit.md`, `wiki_canonical_results_validation.json`, and `wiki_canonical_results.svg`.
- **Residual risk:** GAP-01 still uses a coarse MV3 geometry-failure shorthand based on a non-reconstructable legacy statistic; schedule a separate exact-prose synchronization to `CL-021`.
- **Scientific boundary:** documentation/provenance validation only; no detector value, calibration, ROOT output, simulation, or performance estimate was generated.
- **Status:** COMPLETE for the canonical-results remediation unit; repository-wide WIKI audit remains PARTIAL.
