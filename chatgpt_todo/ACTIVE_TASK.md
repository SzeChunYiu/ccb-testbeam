# Active Task

- **Task ID:** AUD-LEDGER-002
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-24T200310Z
- **Initial remote main SHA:** `ad5a19a2dece0f0973573362004d558eb1a4cad5`
- **Latest remote head after focused evidence writes:** `e6f313f211fe005187e50d864ad05bd3719a1706`
- **Scope:** audit canonical MV3 rows CL-019/020/021 against the tracked exact `mv3_summary.json`, independently reconstruct the profile statistic, and define a fail-closed correction contract.
- **Confirmed defect:** the ledger and its v1.0 validator say exact per-stave counts, underlying chi2/ndf components, and a machine-readable result are absent, while the tracked summary contains exact counts, chi2 `204808.2179684494`, ndf `3`, and chi2/ndf `68269.40598948313`.
- **Validation:** focused compile and pytest passed (`5 passed in 0.70s`); the current-like ledger fixture returns `FLAWED` with 32 explicit findings; a corrected fixture returns `VALIDATED` with zero findings; mutated summary values and invalid UTF-8 fail closed.
- **Evidence:** `tools/audit/audit_mv3_summary_provenance.py`, `tests/test_audit_mv3_summary_provenance.py`, and `docs/validation/mv3_summary_provenance_{audit.md,validation.json,svg}`.
- **Required correction:** update CL-019/020 with exact B8 numerators, denominators, fractions, and summary path; update CL-021 with the exact Pearson construction; replace the old validator contract; synchronize WIKI GAP-01 prose.
- **Scientific boundary:** exact source provenance and arithmetic reconstruction only; geometry, selection transfer, covariance, gain response, p-value interpretation, and detector/model systematics remain unresolved.
- **Status:** PARTIAL — validated defect and remediation gate delivered; canonical rows and public prose are not yet corrected.
